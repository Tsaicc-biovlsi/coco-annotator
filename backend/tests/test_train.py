"""Training runs: permission, queue, the runner with a stand-in for Ultralytics."""
import os
import sys
import threading
import time

from webserver.util.passwords import hash_password

FAKE = r'''
import csv, os, sys, time
args = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
out = os.path.join(args["project"], args["name"])
os.makedirs(os.path.join(out, "weights"), exist_ok=True)
epochs = int(args["epochs"])
assert os.path.exists(args["data"]), args["data"]
with open(os.path.join(out, "results.csv"), "w", newline="") as fp:
    w = csv.writer(fp)
    w.writerow(["                  epoch", "      train/box_loss", "   metrics/mAP50(B)"])
    for e in range(1, epochs + 1):
        w.writerow([e, 1.0 / e, 0.1 * e]); fp.flush()
        print(f"\x1b[K\x1b[1mepoch {e}/{epochs}\x1b[0m", flush=True)
        time.sleep(float(os.environ.get("FAKE_EPOCH_SECONDS", "0")))
open(os.path.join(out, "weights", "best.pt"), "wb").write(b"weights")
'''


def _login(username, role=None):
    from database import UserModel
    from webserver import app
    UserModel.objects(username=username).delete()
    UserModel(username=username, password=hash_password("pw"), name=username, is_admin=False,
              role=role or "user").save()
    c = app.test_client()
    assert c.post("/api/user/login", json={"username": username, "password": "pw"}).status_code == 200
    return c


def _fake_command(script):
    def build(run, data, out_dir):
        p = run.params
        return [sys.executable, script, f"data={data}", f"epochs={p['epochs']}", f"project={out_dir}", "name=train"]
    return build


def test_training(dataset_directory, tmp_path, monkeypatch):
    from PIL import Image
    from database import RoleModel, TrainRunModel
    from trainer import runner
    from config import Config
    models = tmp_path / "models"
    models.mkdir()
    monkeypatch.setenv("MODELS_DIRECTORY", str(models))
    monkeypatch.setattr(Config, "MODELS_DIRECTORY", str(models))
    monkeypatch.setattr(runner, "POLL_SECONDS", 0.1)
    RoleModel.objects(key="trainer").delete()
    RoleModel(key="trainer", name="trainer", permissions=["train"]).save()
    script = tmp_path / "fake_yolo.py"
    script.write_text(FAKE)

    t = _login("tr_owner", role="trainer")
    plain = _login("tr_plain")
    ds = t.post("/api/dataset/", json={"name": "tr_ds", "categories": ["boat"]}).get_json()["id"]
    folder = os.path.join(dataset_directory, "tr_ds")
    os.makedirs(folder, exist_ok=True)
    Image.new("RGB", (64, 48)).save(os.path.join(folder, "a.jpg"))
    t.get(f"/api/dataset/{ds}/scan")
    image = t.get(f"/api/dataset/{ds}/data").get_json()["images"][0]
    cat = t.get(f"/api/dataset/{ds}/data").get_json()["dataset"]["categories"][0]
    t.post("/api/annotation/", json={"image_id": image["id"], "category_id": cat,
                                    "segmentation": [[5, 5, 30, 5, 30, 30, 5, 30]]})
    # an export without images can not be trained on; one with images can
    t.get(f"/api/dataset/{ds}/export", query_string={"format": "yolo", "yolo_task": "detect"})
    t.get(f"/api/dataset/{ds}/export", query_string={"format": "yolo", "yolo_task": "detect", "with_images": "true"})

    assert plain.get("/api/train/").status_code == 403
    exports = t.get("/api/train/exports").get_json()["exports"]
    mine = [e for e in exports if e["dataset_id"] == ds]
    assert len(mine) == 1 and mine[0]["task"] == "detect" and mine[0]["datasets"] == ["tr_ds"]
    eid = mine[0]["id"]

    assert t.post("/api/train/", json={"export_id": eid, "family": "nope"}).status_code == 400
    r = t.post("/api/train/", json={"export_id": eid, "family": "yolo26", "size": "s", "epochs": 3, "imgsz": 650})
    assert r.status_code == 200, r.data
    run = r.get_json()
    assert run["status"] == "queued" and run["params"]["model"] == "yolo26s.pt" and run["params"]["imgsz"] == 640
    assert t.get("/api/train/").get_json()["runs"][0]["queue_position"] == 1
    assert plain.post("/api/train/", json={"export_id": eid}).status_code == 403

    # the trainer picks it up and runs it
    claimed = runner.claim_next()
    assert claimed.id == run["id"] and runner.claim_next() is None
    runner.execute(claimed, command=_fake_command(str(script)))
    done = t.get(f"/api/train/{run['id']}").get_json()
    assert done["status"] == "done", done
    assert done["epoch"] == 3 and done["metrics"][-1]["metrics/mAP50(B)"] == 0.3
    assert done["model_name"] == f"trained/tr_ds-detect-run{run['id']}.pt"
    assert (models / done["model_name"]).read_bytes() == b"weights"
    assert "epoch 3/3" in done["log_tail"] and "\x1b" not in done["log_tail"]  # no terminal colour codes

    # stopping a running one
    monkeypatch.setenv("FAKE_EPOCH_SECONDS", "0.5")
    r2 = t.post("/api/train/", json={"export_id": eid, "epochs": 50}).get_json()
    claimed = runner.claim_next()
    worker = threading.Thread(target=runner.execute, args=(claimed,), kwargs={"command": _fake_command(str(script))})
    worker.start()
    time.sleep(1.5)
    assert t.post(f"/api/train/{r2['id']}/stop").get_json()["stop_requested"] is True
    worker.join(timeout=20)
    stopped = TrainRunModel.objects(id=r2["id"]).first()
    assert stopped.status == "stopped" and 0 < stopped.epoch < 50

    # a queued one is simply cancelled; finished ones can be removed
    r3 = t.post("/api/train/", json={"export_id": eid}).get_json()
    assert t.post(f"/api/train/{r3['id']}/stop").get_json()["status"] == "stopped"
    assert t.delete(f"/api/train/{run['id']}").get_json()["success"]
    assert (models / done["model_name"]).exists()  # the trained model stays

    st = t.get("/api/train/status").get_json()
    assert "alive" in st and st["tasks"][0] == "detect"
