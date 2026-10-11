"""Training runs: permission, queue, the runner with a stand-in for Ultralytics."""
import os
import sys
import threading
import time

from webserver.util.passwords import hash_password

FAKE = r'''
import csv, os, sys, time
args = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
if "resume" in args:  # go on: runs/train/weights/last.pt
    out = os.path.dirname(os.path.dirname(args["resume"]))
    epochs = int(open(os.path.join(out, "epochs.txt")).read())
    done = len(open(os.path.join(out, "results.csv")).read().splitlines()) - 1
    mode = "a"
    print(f"Resuming from epoch {done + 1}", flush=True)
else:
    out = os.path.join(args["project"], args["name"])
    os.makedirs(os.path.join(out, "weights"), exist_ok=True)
    epochs = int(args["epochs"])
    assert os.path.exists(args["data"]), args["data"]
    open(os.path.join(out, "epochs.txt"), "w").write(str(epochs))
    done, mode = 0, "w"
with open(os.path.join(out, "results.csv"), mode, newline="") as fp:
    w = csv.writer(fp)
    if mode == "w":
        w.writerow(["                  epoch", "      train/box_loss", "   metrics/mAP50(B)", " metrics/mAP50-95(B)"])
    for e in range(done + 1, epochs + 1):
        w.writerow([e, 1.0 / e, 0.1 * e, 0.3 if e == 2 else 0.1]); fp.flush()
        open(os.path.join(out, "weights", "last.pt"), "wb").write(b"last")
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
        if p.get("resume"):
            from trainer import runner
            return [sys.executable, script, f"resume={runner.last_weights(run.id)}"]
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
    # best.pt is from epoch 2 (Ultralytics' fitness: 0.1 mAP50 + 0.9 mAP50-95 here)
    assert done["best"]["epoch"] == 2 and done["best"]["since"] == 1
    assert done["best"]["metrics"]["metrics/mAP50-95(B)"] == 0.3
    assert [r["best"]["epoch"] for r in t.get("/api/train/").get_json()["runs"] if r["id"] == run["id"]] == [2]
    assert done["model_name"] == f"trained/tr_ds-detect-run{run['id']}.pt"
    assert (models / done["model_name"]).read_bytes() == b"weights"
    # everything under runs/train, packed when it ended
    import io
    import zipfile
    assert done["archive"]["size"] > 0
    got = t.get(f"/api/train/{run['id']}/download")
    assert got.status_code == 200 and "tr_ds-detect-run" in got.headers["Content-Disposition"]
    names = zipfile.ZipFile(io.BytesIO(got.data)).namelist()
    top = f"tr_ds-detect-run{run['id']}/"
    assert {top + "weights/best.pt", top + "results.csv", top + "train.log"} <= set(names)
    assert plain.get(f"/api/train/{run['id']}/download").status_code == 403
    # runs from before: packed when downloaded
    os.remove(runner.archive_path(run["id"]))
    assert t.get(f"/api/train/{run['id']}").get_json()["archive"] == {"size": None}
    assert t.get(f"/api/train/{run['id']}/download").status_code == 200
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

    # removing a running one: stopped, then gone (no model kept)
    monkeypatch.setenv("FAKE_EPOCH_SECONDS", "0.3")
    r4 = t.post("/api/train/", json={"export_id": eid, "epochs": 50}).get_json()
    claimed = runner.claim_next()
    worker = threading.Thread(target=runner.execute, args=(claimed,), kwargs={"command": _fake_command(str(script))})
    worker.start()
    time.sleep(1)
    assert _login("tr_other3", role="trainer").delete(f"/api/train/{r4['id']}").status_code == 403
    assert t.delete(f"/api/train/{r4['id']}").get_json() == {"success": True, "deleting": True}
    worker.join(timeout=20)
    assert TrainRunModel.objects(id=r4["id"]).first() is None
    assert not os.path.exists(runner.work_dir(r4["id"]))
    assert not (models / f"trained/tr_ds-detect-run{r4['id']}.pt").exists()
    # a queued one goes at once
    r5 = t.post("/api/train/", json={"export_id": eid}).get_json()
    assert t.delete(f"/api/train/{r5['id']}").get_json() == {"success": True}
    assert TrainRunModel.objects(id=r5["id"]).first() is None
    monkeypatch.setenv("FAKE_EPOCH_SECONDS", "0")

    # a queued one is simply cancelled; finished ones can be removed
    assert t.get(f"/api/train/{r2['id']}").get_json()["archive"]["size"] > 0  # a stopped one too

    # go on from where it stopped
    monkeypatch.setenv("FAKE_EPOCH_SECONDS", "0")
    assert t.get(f"/api/train/{r2['id']}").get_json()["resumable"] is True
    assert plain.post(f"/api/train/{r2['id']}/resume").status_code == 403
    assert _login("tr_other2", role="trainer").post(f"/api/train/{r2['id']}/resume").status_code == 403
    steps = os.path.join(runner.work_dir(r2["id"]), "steps.jsonl")
    stopped_at = TrainRunModel.objects(id=r2["id"]).first().epoch
    with open(steps, "w") as fp:
        fp.write('{"x": 0.5}\n{"x": %d}\n{"x": %d.5}\n' % (stopped_at, stopped_at))
    resumed = t.post(f"/api/train/{r2['id']}/resume").get_json()
    assert resumed["status"] == "queued" and resumed["params"]["resume"] and resumed["params"]["resumes"] == 1
    claimed = runner.claim_next()
    assert claimed.id == r2["id"]
    runner.execute(claimed, command=_fake_command(str(script)))
    again = t.get(f"/api/train/{r2['id']}").get_json()
    assert again["status"] == "done", again
    assert [m["epoch"] for m in again["metrics"]] == list(range(1, 51))  # no epoch twice, none missing
    assert "resumed after epoch" in again["log_tail"] and again["resumable"] is False
    assert open(steps).read() == '{"x": 0.5}\n{"x": %d}\n' % stopped_at  # the cut-off epoch's points go
    assert t.post(f"/api/train/{r2['id']}/resume").status_code == 400  # finished: nothing to resume
    assert t.post(f"/api/train/{run['id']}/resume").status_code == 400

    # the trainer stopped in the middle (server restarted): queued again, to go on
    from database import TrainRunModel as Runs
    Runs.objects(id=r2["id"]).update_one(set__status="running", set__epoch=10)
    no_weights = Runs(name="x", creator="tr_owner", export_id=eid, dataset_id=ds, task="detect",
                      status="running", epochs=5)
    no_weights.save()
    runner.recover()
    assert Runs.objects(id=r2["id"]).first().status == "queued"
    assert Runs.objects(id=r2["id"]).first().params["resumes"] == 2
    assert Runs.objects(id=no_weights.id).first().status == "failed"
    Runs.objects(id=r2["id"]).update_one(set__status="done")
    r3 = t.post("/api/train/", json={"export_id": eid}).get_json()
    assert t.get(f"/api/train/{r3['id']}/download").status_code == 400  # not finished
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
    assert "export_augment" in p and p["export_augment"] is None  # the export was not augmented
    assert "export_augment" in t.get(f"/api/train/{r.get_json()['id']}").get_json()["params"]
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


def test_log_follower(tmp_path):
    """Progress bars (\\r ten times a second) keep only their last state."""
    from trainer.runner import LogFollower
    path = tmp_path / "train.log"
    with open(path, "wb") as fp:
        out = LogFollower(fp)
        out.feed("Ultralytics 8.4 \x1b[1mCPU\x1b[0m\r\nepoch 1/2\n".encode())
        for i in range(1, 2001):
            out.feed(f"\r\x1b[K  1/2  {i}/2000 \u2501\u2501 loss {1 / i:.3f}".encode())
            if i == 1000:
                tail = out.tail()
                assert tail.splitlines()[:2] == ["Ultralytics 8.4 CPU", "epoch 1/2"]
                assert tail.splitlines()[-1].strip().startswith("1/2  1000/2000")
        # a character cut in two between reads
        data = "\n驗證完成\n".encode()
        out.feed(data[:3])
        out.feed(data[3:])
        out.feed(b"")
    lines = path.read_text().splitlines()
    assert lines == ["Ultralytics 8.4 CPU", "epoch 1/2", "  1/2  2000/2000 \u2501\u2501 loss 0.001", "驗證完成"]
    assert path.stat().st_size < 200
    assert "\r" not in out.tail() and "\x1b" not in out.tail()


def test_live_output(tmp_path, monkeypatch):
    """The page watching a run gets its new lines and progress bar as written."""
    from database import RoleModel, TrainRunModel
    from webserver import app
    from webserver.sockets import socketio
    from webserver import train_live
    from trainer import runner
    monkeypatch.setenv("MODELS_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(train_live, "STATUS_SECONDS", 0.2)
    RoleModel.objects(key="trainer").delete()
    RoleModel(key="trainer", name="trainer", permissions=["train"]).save()
    run = TrainRunModel(name="live", creator="tr_live", export_id=1, dataset_id=1, task="detect", status="running")
    run.save()
    work = runner.work_dir(run.id)
    os.makedirs(work)
    log = open(os.path.join(work, "train.log"), "ab")
    log.write(b"$ yolo train\nUltralytics 8.4\n")
    log.flush()
    out = runner.LogFollower(log, os.path.join(work, "progress.txt"))

    import socketio as python_socketio
    queue_manager = socketio.server.manager
    socketio.server.manager = python_socketio.Manager()
    socketio.server.manager.set_server(socketio.server)
    try:
        s_plain = socketio.test_client(app, flask_test_client=_login("tr_live_plain"))
        assert s_plain.emit("train_watch", {"run_id": run.id}, callback=True)["ok"] is False
        s = socketio.test_client(app, flask_test_client=_login("tr_live", role="trainer"))
        first = s.emit("train_watch", {"run_id": run.id}, callback=True)
        assert first["ok"] and first["lines"] == ["$ yolo train", "Ultralytics 8.4"] and first["live"]

        def received(until, seconds=5):
            got, end = [], time.time() + seconds
            while time.time() < end:
                got += [m["args"][0] for m in s.get_received() if m["name"] == "train_log"]
                if until(got):
                    break
                time.sleep(0.05)
            return got

        out.feed(b"epoch 1/2\n\r\x1b[K 1/2 3/10 \xe2\x94\x81")
        got = received(lambda g: any(e["progress"] == "1/2 3/10 ━".rjust(len(e["progress"])) for e in g))
        assert ["epoch 1/2"] == [l for e in got for l in e["lines"]]
        assert got[-1]["progress"].strip() == "1/2 3/10 ━"
        t0 = time.time()
        out.feed(b"\r\x1b[K 1/2 4/10")
        got = received(lambda g: any(e["progress"].strip() == "1/2 4/10" for e in g))
        assert got and time.time() - t0 < 1  # live, not once a second
        # a second page shares the watcher, without lines twice
        s2 = socketio.test_client(app, flask_test_client=_login("tr_live2", role="trainer"))
        assert s2.emit("train_watch", {"run_id": run.id}, callback=True)["lines"][-1] == "epoch 1/2"
        out.feed(b"\ndone\n")
        got = received(lambda g: any("done" in e["lines"] for e in g))
        assert [l for e in got for l in e["lines"]] == ["1/2 4/10", "done"] or \
            [l.strip() for e in got for l in e["lines"]] == ["1/2 4/10", "done"]
        assert [m["args"][0]["lines"] for m in s2.get_received() if m["name"] == "train_log" and m["args"][0]["lines"]] \
            == [[" 1/2 4/10", "done"]]
        # finished: the watcher stops
        run.update(set__status="done")
        time.sleep(1)
        assert run.id not in train_live.WATCHERS
    finally:
        socketio.server.manager = queue_manager
    log.close()


def test_steps(tmp_path, monkeypatch):
    """Points within each epoch, from the progress bar: kept by the trainer,
    given by the API (thinned out), pushed live."""
    import json
    from database import RoleModel, TrainRunModel
    from trainer import runner
    monkeypatch.setenv("MODELS_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(runner, "STEP_SECONDS", 0)
    RoleModel.objects(key="trainer").delete()
    RoleModel(key="trainer", name="trainer", permissions=["train"]).save()
    run = TrainRunModel(name="steps", creator="tr_steps", export_id=1, dataset_id=1, task="detect", status="running")
    run.save()
    work = runner.work_dir(run.id)
    os.makedirs(work)
    steps = os.path.join(work, "steps.jsonl")
    with open(os.path.join(work, "train.log"), "ab") as log:
        out = runner.LogFollower(log, os.path.join(work, "progress.txt"), steps)
        out.feed(b"      Epoch    GPU_mem   box_loss   cls_loss   dfl_loss  Instances       Size\n")
        for e in (1, 2):
            for b in range(1, 11):
                bar = f"\r\x1b[K{e:>11}/2      1.5G      {2 / (e * b):.3f}      0.900      1.100         12        640: {b * 10}% ━━ {b}/10 3it/s"
                out.feed(bar.encode())
            out.feed(b"\n")
            out.feed("                 Class     Images  Instances      Box(P          R      mAP50  mAP50-95): 100% ━━ 1/1\n".encode())
    points = [json.loads(l) for l in open(steps)]
    assert len(points) == 20 and points[0] == {"box_loss": 2.0, "cls_loss": 0.9, "dfl_loss": 1.1, "x": 0.1, "gpu_mem": 1.5}
    assert points[9]["x"] == 1.0 and points[-1]["x"] == 2.0 and points[-1]["box_loss"] == 0.1

    t = _login("tr_steps", role="trainer")
    got = t.get(f"/api/train/{run.id}/steps").get_json()
    assert got["total"] == 20 and got["points"] == points
    from webserver.api import train as train_api
    monkeypatch.setattr(train_api, "MAX_STEPS", 4)
    thin = t.get(f"/api/train/{run.id}/steps").get_json()["points"]
    assert len(thin) < 20 and {1.0, 2.0} <= {p["x"] for p in thin}  # epoch ends kept
    assert _login("tr_steps_plain").get(f"/api/train/{run.id}/steps").status_code == 403
