"""Runs queued trainings one at a time: unpack the YOLO export, run
Ultralytics in a child process, follow results.csv, keep the best weights
in the models folder (where pre-annotation finds them)."""
import csv
import datetime
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile

from database import ExportModel, TrainRunModel, TrainerStatusModel

logger = logging.getLogger("trainer")

POLL_SECONDS = 3
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
LOG_TAIL_CHARS = 6000
# model name suffix of each task (yolo26s-seg.pt)
TASK_SUFFIX = {"detect": "", "segment": "-seg", "obb": "-obb", "pose": "-pose", "classify": "-cls"}


def models_dir():
    return os.getenv("MODELS_DIRECTORY", "/models")


def work_dir(run_id):
    # hidden: the models page lists every .pt it finds, not these
    return os.path.join(models_dir(), ".training", f"run-{run_id}")


def safe_name(text):
    return re.sub(r"[^\w.-]+", "_", str(text or "")).strip("_.")[:80] or "model"


def _unpack(export, dest, task):
    """Unzip the export; returns what Ultralytics' ``data=`` takes."""
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    with zipfile.ZipFile(export.path) as zf:
        for member in zf.namelist():
            target = os.path.realpath(os.path.join(dest, member))
            if not target.startswith(os.path.realpath(dest) + os.sep):
                raise ValueError(f"unsafe path in the export: {member}")
        zf.extractall(dest)
    if task == "classify":
        folder = getattr(export, "folder", None)
        candidates = [os.path.join(dest, folder)] if folder else []
        candidates += [os.path.join(dest, d) for d in sorted(os.listdir(dest)) if os.path.isdir(os.path.join(dest, d))]
        for c in candidates:
            if os.path.isdir(os.path.join(c, "train")):
                return c
        raise ValueError("no train/ folder in the export")
    data = os.path.join(dest, "data.yaml")
    if not os.path.isfile(data):
        raise ValueError("no data.yaml in the export (is it a YOLO export?)")
    return data


def uploads_dir():
    return os.path.join(models_dir(), ".training", "uploads")


def _weights(name):
    """Official .pt weights by name: downloaded once into a hidden folder and
    kept for the next runs. Anything else (a path, a .yaml) as it is."""
    if not name.endswith(".pt") or os.sep in name or "/" in name:
        return name
    base = os.path.join(models_dir(), ".training", "base")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, name)


def _value(v):
    if isinstance(v, bool):
        return "True" if v else "False"
    return str(v)


def build_command(run, data, out_dir):
    """The Ultralytics command line (replaced in tests)."""
    p = run.params or {}
    args = [
        f"model={_weights(p.get('model') or '')}", f"data={data}", f"epochs={int(p.get('epochs', 100))}",
        f"imgsz={int(p.get('imgsz', 640))}", f"batch={p.get('batch', -1)}",
        f"patience={int(p.get('patience', 50))}", "plots=True",
    ]
    if p.get("device"):
        args.append(f"device={p['device']}")
    # the page's own arguments (checked by the API); "pretrained" may name
    # official weights to start a .yaml architecture from
    for key, value in (p.get("extra") or {}).items():
        if key == "pretrained" and isinstance(value, str) and value.endswith(".pt"):
            value = _weights(value)
        args.append(f"{key}={_value(value)}")
    # where the results go: last, so nothing overrides it
    args += [f"project={out_dir}", "name=train", "exist_ok=True"]
    # the "yolo" command line (it reads sys.argv)
    return [sys.executable, "-c", "from ultralytics.cfg import entrypoint; entrypoint()",
            run.task or "detect", "train", *args]


def _read_results(path):
    """results.csv rows with numbers, header names without spaces."""
    if not os.path.isfile(path):
        return []
    rows = []
    with open(path, newline="") as fp:
        for row in csv.DictReader(fp):
            clean = {}
            for k, v in row.items():
                if k is None:
                    continue
                try:
                    clean[k.strip()] = round(float(v), 5)
                except (TypeError, ValueError):
                    pass
            if clean:
                rows.append(clean)
    return rows


def _tail(path):
    if not os.path.isfile(path):
        return ""
    with open(path, "rb") as fp:
        fp.seek(0, os.SEEK_END)
        size = fp.tell()
        fp.seek(max(0, size - LOG_TAIL_CHARS * 3))
        text = fp.read().decode("utf-8", "replace")
    # colours / cursor moves of the terminal output, and progress bars that
    # rewrite their line with \r: keep the last state of each line
    text = ANSI.sub("", text)
    lines = [line.split("\r")[-1] for line in text.split("\n")]
    return "\n".join(lines)[-LOG_TAIL_CHARS:]


def heartbeat(device=None, catalog=None):
    update = {"set__seen_at": datetime.datetime.utcnow()}
    if device is not None:
        update["set__device"] = device
    if catalog is not None:
        update["set__catalog"] = catalog
        update["set__version"] = catalog.get("version") or ""
    TrainerStatusModel.objects(key="trainer").update_one(upsert=True, **update)


def execute(run, command=None):
    """Train one run to the end (or until stopped)."""
    now = datetime.datetime.utcnow
    export = ExportModel.objects(id=run.export_id).first()
    work = work_dir(run.id)
    log_path = os.path.join(work, "train.log")
    try:
        if export is None or not export.path or not os.path.isfile(export.path):
            raise ValueError("the export file no longer exists")
        os.makedirs(work, exist_ok=True)
        data = _unpack(export, os.path.join(work, "data"), run.task)
        out_dir = os.path.join(work, "runs")
        cmd = (command or build_command)(run, data, out_dir)
    except Exception as e:  # nothing started: say why
        run.update(set__status="failed", set__error=str(e)[:1000], set__ended_at=now())
        return
    results = os.path.join(out_dir, "train", "results.csv")
    # online: Ultralytics downloads the base weights the first time
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    env.pop("YOLO_OFFLINE", None)
    with open(log_path, "ab") as log:
        log.write(("$ " + " ".join(cmd) + "\n").encode())
        log.flush()
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=work, env=env,
                                start_new_session=True)
        stopped = False
        while True:
            code = proc.poll()
            rows = _read_results(results)
            run.reload("stop_requested")
            run.update(set__metrics=rows, set__epoch=len(rows), set__log_tail=_tail(log_path))
            heartbeat()
            if code is not None:
                break
            if run.stop_requested and not stopped:
                stopped = True
                # the whole process group (data loader workers too)
                os.killpg(proc.pid, signal.SIGINT)
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
            time.sleep(POLL_SECONDS)
    rows = _read_results(results)
    best = os.path.join(out_dir, "train", "weights", "best.pt")
    model_name = None
    if os.path.isfile(best) and rows:
        names = run.dataset_names or ["model"]
        name = f"{safe_name('+'.join(names))}-{run.task}-run{run.id}.pt"
        target_dir = os.path.join(models_dir(), "trained")
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(best, os.path.join(target_dir, name))
        model_name = f"trained/{name}"
    status = "stopped" if stopped else ("done" if code == 0 and model_name else "failed")
    error = ""
    if status == "failed":
        tail = _tail(log_path).strip().splitlines()
        error = (tail[-1] if tail else f"exit code {code}")[:1000]
    run.update(set__status=status, set__metrics=rows, set__epoch=len(rows), set__log_tail=_tail(log_path),
               set__model_name=model_name, set__error=error, set__ended_at=now())


def claim_next():
    """The oldest queued run, now running (None when there is none)."""
    first = TrainRunModel.objects(status="queued").order_by("id").first()
    if first is None:
        return None
    claimed = TrainRunModel.objects(id=first.id, status="queued").update_one(
        set__status="running", set__started_at=datetime.datetime.utcnow())
    return TrainRunModel.objects(id=first.id).first() if claimed else None


def _device_name():
    try:
        import ultralytics  # noqa: F401
    except ImportError:
        return "ultralytics not installed (build with SAM=cuda or SAM=cpu)"
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
        return "CPU"
    except Exception:
        return "CPU"


def serve():
    """Run queued trainings, forever."""
    # a run left "running" by a restart did not finish
    TrainRunModel.objects(status="running").update(
        set__status="failed", set__error="the trainer restarted during this training",
        set__ended_at=datetime.datetime.utcnow())
    device = _device_name()
    from .catalog import build
    heartbeat(device, build())
    logger.info("trainer ready (%s)", device)
    while True:
        heartbeat(device)
        run = claim_next()
        if run is None:
            time.sleep(POLL_SECONDS)
            continue
        logger.info("training run %s", run.id)
        try:
            execute(run)
        except Exception as e:  # pragma: no cover - keep serving the queue
            logger.exception("run %s", run.id)
            run.update(set__status="failed", set__error=str(e)[:1000], set__ended_at=datetime.datetime.utcnow())


def start_embedded():
    """TRAINER_EMBEDDED=true: train inside the webserver process (no
    separate trainer container)."""
    import threading
    thread = threading.Thread(target=serve, name="trainer", daemon=True)
    thread.start()
    return thread


def main():
    logging.basicConfig(level=logging.INFO)
    from database import connect_mongo
    connect_mongo("trainer")
    serve()
