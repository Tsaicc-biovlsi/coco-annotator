"""Runs queued trainings one at a time: unpack the YOLO export, run
Ultralytics in a child process, follow results.csv, keep the best weights
in the models folder (where pre-annotation finds them)."""
import codecs
import collections
import csv
import datetime
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import zipfile

from database import ExportModel, TrainRunModel, TrainerStatusModel

logger = logging.getLogger("trainer")

POLL_SECONDS = 3
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
LOG_TAIL_CHARS = 6000
# how often the page's view of the output is refreshed while training
LOG_SECONDS = 1
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


class LogFollower:
    """Reads the training's output as it comes. Progress bars rewrite their
    line with \r ten times a second: only the line's last state is kept, so
    the log stays small and its end always has the lines before the bar
    (reading the end of the raw output would be one huge bar line)."""

    def __init__(self, log_file, progress_path=None):
        self.log = log_file
        # the progress bar's state, for the page to follow live (the log
        # file only gets finished lines)
        self.progress_path = progress_path
        self._shown_progress = None
        self.lines = collections.deque(maxlen=400)
        self.current = ""
        self.version = 0
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._lock = threading.Lock()

    def feed(self, data):
        text = self._decoder.decode(data, final=not data).replace("\r\n", "\n")
        with self._lock:
            text = self.current + text
            *done, self.current = text.split("\n")
            for line in done:
                line = ANSI.sub("", line).split("\r")[-1].rstrip()
                self.lines.append(line)
                self.log.write((line + "\n").encode())
            if done:
                self.log.flush()
            # keep only the bar's last state (escape codes may be cut: strip at the end)
            if "\r" in self.current:
                parts = self.current.split("\r")
                last = parts[-1] or (parts[-2] if len(parts) > 1 else "")
                self.current = last if parts[-1] else last + "\r"
            self.version += 1
            self._write_progress()

    def _write_progress(self):
        if not self.progress_path:
            return
        text = ANSI.sub("", self.current).strip("\r").rstrip()
        if text == self._shown_progress:
            return
        self._shown_progress = text
        try:
            tmp = self.progress_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fp:
                fp.write(text)
            os.replace(tmp, self.progress_path)
        except OSError:
            pass

    def follow(self, stream):
        fd = stream.fileno()
        while True:
            chunk = os.read(fd, 65536)
            self.feed(chunk)
            if not chunk:
                break
        with self._lock:
            if self.current.strip("\r"):
                line = ANSI.sub("", self.current).strip("\r").rstrip()
                self.lines.append(line)
                self.log.write((line + "\n").encode())
                self.log.flush()
            self.current = ""
            self._write_progress()

    def tail(self):
        with self._lock:
            current = ANSI.sub("", self.current).strip("\r")
            text = "\n".join(list(self.lines) + ([current] if current else []))
        return text[-LOG_TAIL_CHARS:]


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
        # nothing left from an earlier run with this number
        shutil.rmtree(out_dir, ignore_errors=True)
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
        out = LogFollower(log, os.path.join(work, "progress.txt"))
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=work, env=env,
                                start_new_session=True)
        reader = threading.Thread(target=out.follow, args=(proc.stdout,), daemon=True)
        reader.start()
        stopped = False
        shown = -1
        last_poll = 0
        while True:
            code = proc.poll()
            if time.monotonic() - last_poll >= POLL_SECONDS or code is not None:
                # results, stop button, trainer alive
                last_poll = time.monotonic()
                rows = _read_results(results)
                run.reload("stop_requested")
                run.update(set__metrics=rows, set__epoch=len(rows))
                heartbeat()
            if out.version != shown:
                shown = out.version
                run.update(set__log_tail=out.tail())
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
            time.sleep(min(LOG_SECONDS, POLL_SECONDS))
        reader.join(timeout=10)
        proc.stdout.close()
        log_tail = out.tail()
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
        tail = log_tail.strip().splitlines()
        error = (tail[-1] if tail else f"exit code {code}")[:1000]
    run.update(set__status=status, set__metrics=rows, set__epoch=len(rows), set__log_tail=log_tail,
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
