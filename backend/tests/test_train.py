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


CATALOG = {
    "version": "8.4.0",
    "families": [{"key": "yolo26", "label": "YOLO26", "items": [
        {"name": n, "kind": n.rsplit(".", 1)[1], "task": "segment" if "-seg" in n else "detect", "scale": n[6]}
        for n in ("yolo26n.pt", "yolo26s.pt", "yolo26s.yaml", "yolo26s-seg.pt")]}],
    "args": {"epochs": 100, "batch": 16, "lr0": 0.01, "mosaic": 1.0, "freeze": None, "pretrained": True,
             "optimizer": "auto", "cos_lr": False, "device": None},
}


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

    # what the trainer can train (it publishes this when it starts)
    runner.heartbeat("CPU", CATALOG)
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
    assert st["version"] == "8.4.0"

    # the catalog: official models (.pt / .yaml) and the arguments
    cat = t.get("/api/train/catalog").get_json()
    assert [i["name"] for i in cat["families"][0]["items"]][:2] == ["yolo26n.pt", "yolo26s.pt"]
    assert cat["args"]["lr0"] == 0.01 and "data" in cat["blocked"]
    assert plain.get("/api/train/catalog").status_code == 403

    def queue(**body):
        return t.post("/api/train/", json={"export_id": eid, **body})

    # a .yaml from scratch, with own arguments (epochs among them)
    r = queue(model="yolo26s.yaml", extra={"lr0": 0.002, "cos_lr": True, "freeze": [0, 1], "epochs": 7,
                                           "optimizer": "AdamW", "pretrained": "yolo26n.pt", "batch": 0.7})
    assert r.status_code == 200, r.data
    p = r.get_json()["params"]
    assert p["model"] == "yolo26s.yaml" and p["epochs"] == 7 and p["batch"] == 0.7
    assert p["extra"] == {"lr0": 0.002, "cos_lr": True, "freeze": [0, 1], "optimizer": "AdamW",
                          "pretrained": "yolo26n.pt"}
    cmd = runner.build_command(TrainRunModel.objects(id=r.get_json()["id"]).first(), "/d/data.yaml", "/out")
    assert "model=yolo26s.yaml" in cmd and "lr0=0.002" in cmd and "cos_lr=True" in cmd and "freeze=[0, 1]" in cmd
    assert f"pretrained={models}/.training/base/yolo26n.pt" in cmd
    assert cmd[-3:] == ["project=/out", "name=train", "exist_ok=True"]  # nothing overrides where it goes
    t.post(f"/api/train/{r.get_json()['id']}/stop")

    for bad in ({"model": "yolo26s-seg.pt"},                 # another task
                {"model": "yolo99.pt"},                      # not in the catalog
                {"model": "yolo26n.pt", "extra": {"data": "x"}},        # set by the trainer
                {"model": "yolo26n.pt", "extra": {"project": "x"}},
                {"model": "yolo26n.pt", "extra": {"nonsense": 1}},      # unknown
                {"model": "yolo26n.pt", "extra": {"optimizer": "../../etc"}},  # paths
                {"model": "yolo26n.pt", "extra": {"optimizer": "a\nb"}},
                {"model": "yolo26n.pt", "extra": {"pretrained": "yolo26s.pt"}},  # a .pt has its weights
                {"model": "yolo26s.yaml", "extra": {"pretrained": "yolo26s.yaml"}},
                {"source": "upload", "upload_id": 999}):
        assert queue(**bad).status_code == 400, bad

    # uploads: a model yaml, weights; anything else is refused
    import io
    arch = b"nc: 80\nscales:\n  s: [0.5, 0.5, 1024]\nbackbone: []\nhead: []\n"
    up = t.post("/api/train/uploads", data={"file": (io.BytesIO(arch), "my-yolo26s.yaml")},
                content_type="multipart/form-data")
    assert up.status_code == 200, up.data
    up = up.get_json()
    assert up["kind"] == "yaml" and up["name"] == "my-yolo26s.yaml"
    w = t.post("/api/train/uploads", data={"file": (io.BytesIO(b"PK\x03\x04weights"), "best.pt")},
               content_type="multipart/form-data").get_json()
    assert w["kind"] == "pt"
    for name, body in (("x.txt", b"hi"), ("x.yaml", b"lr0: 1\n"), ("x.pt", b"not torch")):
        assert t.post("/api/train/uploads", data={"file": (io.BytesIO(body), name)},
                      content_type="multipart/form-data").status_code == 400, name
    assert [u["id"] for u in t.get("/api/train/uploads").get_json()["uploads"]] == [w["id"], up["id"]]
    assert len(os.listdir(models / ".training" / "uploads")) == 2

    r = queue(source="upload", upload_id=up["id"], extra={"pretrained": f"upload:{w['id']}"})
    assert r.status_code == 200, r.data
    p = r.get_json()["params"]
    assert p["model"].endswith(f"u{up['id']}-my-yolo26s.yaml") and p["label"] == "my-yolo26s.yaml"
    assert p["extra"]["pretrained"].endswith(f"best-u{w['id']}.pt")
    cmd = runner.build_command(TrainRunModel.objects(id=r.get_json()["id"]).first(), "/d", "/o")
    assert f"pretrained={p['extra']['pretrained']}" in cmd
    t.post(f"/api/train/{r.get_json()['id']}/stop")

    other = _login("tr_other", role="trainer")
    assert other.delete(f"/api/train/uploads/{w['id']}").status_code == 403
    assert t.delete(f"/api/train/uploads/{w['id']}").get_json()["success"]
    assert len(os.listdir(models / ".training" / "uploads")) == 1

    # an args.yaml (e.g. of an earlier run): what can be used, what not
    args_yaml = (b"task: detect\nmodel: /x/yolo26n.pt\ndata: d.yaml\nepochs: 30\nlr0: 0.005\n"
                 b"mosaic: 1.0\nbogus: 3\noptimizer: SGD\n")
    parsed = t.post("/api/train/parse-args", data={"file": (io.BytesIO(args_yaml), "args.yaml")},
                    content_type="multipart/form-data").get_json()
    assert parsed["args"] == {"epochs": 30, "lr0": 0.005, "optimizer": "SGD"}  # mosaic is the default
    assert sorted(i["key"] for i in parsed["ignored"]) == ["bogus", "data", "model", "task"]
    assert t.post("/api/train/parse-args", data={"file": (io.BytesIO(b"- a\n- b\n"), "a.yaml")},
                  content_type="multipart/form-data").status_code == 400
