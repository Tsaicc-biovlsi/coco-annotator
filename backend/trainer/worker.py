"""A trainer on another server ("worker"): it trains with this server's GPU
for the site at TRAINER_URL, connecting with TRAINER_TOKEN (from the
training page → 訓練伺服器). It takes trainings meant for it or for any
trainer, downloads the export, trains, and sends back the output, curves,
the trained model and the results zip. Nothing here touches the site's
database.

    python -m trainer.worker        (docker-compose.worker.yml runs it)
"""
import json
import logging
import os
import shutil
import threading
import time
from types import SimpleNamespace

import requests

from . import runner
from .runner import (POLL_SECONDS, _unpack, archive_path, execute, last_weights, package, work_dir)

logger = logging.getLogger("trainer.worker")

RETRY_SECONDS = 10
HEARTBEAT_SECONDS = 10


class Site:
    """The site's worker API (/api/worker)."""

    def __init__(self, url, token):
        self.url = url.rstrip("/") + "/api/worker"
        self.http = requests.Session()
        self.http.headers["X-Worker-Token"] = token

    def post(self, path, json_body=None, timeout=30, **kw):
        r = self.http.post(f"{self.url}/{path}", json=json_body, timeout=timeout, **kw)
        if r.status_code == 401:
            raise PermissionError("the site does not know this token (removed, or a new one was made)")
        r.raise_for_status()
        return r.json() if r.status_code != 204 and r.content else None

    def download(self, path, dest):
        tmp = dest + ".part"
        with self.http.get(f"{self.url}/{path}", stream=True, timeout=60) as r:
            if r.status_code == 404:
                raise ValueError((r.json() or {}).get("message") or "not found on the site")
            r.raise_for_status()
            with open(tmp, "wb") as fp:
                for chunk in r.iter_content(1024 * 1024):
                    fp.write(chunk)
        os.replace(tmp, dest)
        return dest


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


class _Tail:
    """New whole lines of a file, from where the last read stopped."""

    def __init__(self, path):
        self.path = path
        self.offset = 0

    def start_at_end(self):
        self.offset = _size(self.path)

    def peek(self):
        size = _size(self.path)
        if size < self.offset:  # started again
            self.offset = 0
        if size == self.offset:
            return [], self.offset
        with open(self.path, "rb") as fp:
            fp.seek(self.offset)
            data = fp.read(size - self.offset)
        end = data.rfind(b"\n")
        if end < 0:
            return [], self.offset
        lines = data[:end].decode("utf-8", "replace").split("\n")
        return lines, self.offset + end + 1


class RemoteIO:
    """How a training on this server reports to the site (see runner.LocalIO)."""

    def __init__(self, site, job, run):
        self.site = site
        self.job = job
        self.run = run
        work = work_dir(run.id)
        self.log = _Tail(os.path.join(work, "train.log"))
        self.steps = _Tail(os.path.join(work, "steps.jsonl"))
        self.progress_path = os.path.join(work, "progress.txt")
        self._polled = 0
        self._sent_progress = None
        self.stop = False
        self.delete = False

    def prepare(self, work, resume):
        # model files of the site (uploaded, from its Models page)
        folder = os.path.join(work, "files")
        os.makedirs(folder, exist_ok=True)
        for f in self.job.get("files") or []:
            dest = os.path.join(folder, os.path.basename(f["name"]))
            if not os.path.isfile(dest) or _size(dest) != f.get("size"):
                self.site.download(f"runs/{self.run.id}/files/{f['index']}", dest)
            if f["field"] == "model":
                self.run.params["model"] = dest
            elif f["field"] == "pretrained":
                self.run.params.setdefault("extra", {})["pretrained"] = dest
        # from here on, what is written goes to the site
        self.log.start_at_end()
        self.steps.start_at_end()
        if resume and os.path.isdir(os.path.join(work, "data")):
            return None
        export = self.job.get("export") or {}
        if not export.get("available"):
            raise ValueError("the unpacked data and the export are both gone" if resume
                             else "the export file no longer exists")
        zip_path = os.path.join(work, "export.zip")
        self.site.download(f"runs/{self.run.id}/export", zip_path)
        try:
            return _unpack(SimpleNamespace(path=zip_path, folder=export.get("folder")),
                           os.path.join(work, "data"), self.run.task)
        finally:
            os.remove(zip_path)

    def fail(self, error):
        try:
            self.site.post(f"runs/{self.run.id}/fail", {"error": error[:1000]})
        except Exception as e:
            logger.warning("could not report run %s failed: %s", self.run.id, e)

    def _send(self, rows=None, out=None):
        lines, log_end = self.log.peek()
        steps, steps_end = self.steps.peek()
        body = {"lines": lines, "steps": []}
        for line in steps:
            try:
                body["steps"].append(json.loads(line))
            except ValueError:
                pass
        try:
            with open(self.progress_path, encoding="utf-8", errors="replace") as fp:
                progress = fp.read()
        except OSError:
            progress = ""
        if progress != self._sent_progress:
            body["progress"] = progress
        if rows is not None:
            body["metrics"] = rows
        if out is not None:
            body["log_tail"] = out.tail()
        answer = self.site.post(f"runs/{self.run.id}/progress", body) or {}
        # sent: go on from there
        self.log.offset, self.steps.offset = log_end, steps_end
        self._sent_progress = progress
        self.stop = bool(answer.get("stop"))
        self.delete = bool(answer.get("delete"))

    def poll(self, rows, out, force=False):
        full = force or time.monotonic() - self._polled >= POLL_SECONDS
        try:
            if full:
                self._polled = time.monotonic()
                self._send(rows(), out)
            else:
                self._send()
        except Exception as e:  # the site is unreachable: keep training, send later
            logger.warning("run %s: could not reach the site: %s", self.run.id, e)
        return self.stop

    def removed(self):
        if not self.delete:
            return False
        try:
            self.site.post(f"runs/{self.run.id}/finish", data={"data": "{}"})
        except Exception:
            pass
        shutil.rmtree(work_dir(self.run.id), ignore_errors=True)
        return True

    def finish(self, status, rows, log_tail, error, best, has_last):
        try:  # the last lines
            self._send(rows, None)
        except Exception:
            pass
        try:
            package(self.run)
        except Exception as e:
            logger.warning("could not pack run %s: %s", self.run.id, e)
        data = json.dumps({"status": status, "metrics": rows, "log_tail": log_tail, "error": error,
                           "has_last": has_last})
        archive = archive_path(self.run.id) if os.path.isfile(archive_path(self.run.id)) else None
        # everything; if that is refused as too large (a proxy's upload limit)
        # or keeps failing: the model only; at last the status only
        sent = False
        for with_best, with_archive, tries in ((True, True, 3), (True, False, 2), (False, False, 2)):
            if (with_archive and not archive) or (with_best and not best and archive):
                continue
            for attempt in range(1, tries + 1):
                files = {}
                try:
                    if with_best and best:
                        files["best"] = ("best.pt", open(best, "rb"))
                    if with_archive and archive:
                        files["archive"] = ("results.zip", open(archive, "rb"))
                    self.site.post(f"runs/{self.run.id}/finish", data={"data": data}, files=files, timeout=1800)
                    sent = True
                    break
                except PermissionError:
                    raise
                except requests.HTTPError as e:
                    logger.warning("run %s: the site refused the results (%s)", self.run.id, e)
                    if e.response is not None and e.response.status_code == 413:
                        break  # too large: send less
                    time.sleep(RETRY_SECONDS * attempt)
                except Exception as e:
                    logger.warning("run %s: could not send the results (%s), try %s", self.run.id, e, attempt)
                    time.sleep(RETRY_SECONDS * attempt)
                finally:
                    for _, f in files.values():
                        f.close()
            if sent:
                if not (with_best and with_archive):
                    logger.warning("run %s: sent without %s; it stays in %s", self.run.id,
                                   "the results zip" if with_best else "the model and the results zip",
                                   work_dir(self.run.id))
                break
        # only what it needs to go on from where it stopped is kept here
        # (and all of it when the site did not get everything)
        if sent and not has_last and (with_best and with_archive or not archive):
            shutil.rmtree(work_dir(self.run.id), ignore_errors=True)


def _resumable_here():
    """Runs whose last finished epoch is on this server."""
    root = os.path.join(runner.models_dir(), ".training")
    out = []
    for name in os.listdir(root) if os.path.isdir(root) else []:
        if name.startswith("run-") and name[4:].isdigit() and os.path.isfile(last_weights(int(name[4:]))):
            out.append(int(name[4:]))
    return out


class _Beat:
    """Tells the site this worker is alive while it downloads or packs."""

    def __init__(self, site):
        self.site = site
        self.run_id = None
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while not self._stop.wait(HEARTBEAT_SECONDS):
            try:
                self.site.post("heartbeat", {"run_id": self.run_id}, timeout=10)
            except Exception:
                pass


def serve(url, token):
    site = Site(url, token)
    device = runner._device_name()
    from .catalog import build
    catalog = build()
    while True:
        try:
            hello = site.post("hello", {"device": device, "catalog": catalog, "resumable": _resumable_here()})
            break
        except PermissionError:
            raise
        except Exception as e:
            logger.warning("cannot reach %s yet: %s", url, e)
            time.sleep(RETRY_SECONDS)
    logger.info("worker %s ready (%s) for %s", hello.get("name"), device, url)
    beat = _Beat(site)
    while True:
        try:
            job = site.post("claim")
        except PermissionError:
            raise
        except Exception as e:
            logger.warning("cannot reach %s: %s", url, e)
            time.sleep(RETRY_SECONDS)
            continue
        if not job:
            time.sleep(POLL_SECONDS)
            continue
        run = SimpleNamespace(id=job["id"], task=job["task"], params=dict(job.get("params") or {}),
                              epoch=job.get("epoch") or 0, epochs=job.get("epochs") or 0,
                              dataset_names=job.get("dataset_names") or [])
        logger.info("training run %s", run.id)
        beat.run_id = run.id
        try:
            execute(run, io=RemoteIO(site, job, run))
        except PermissionError:
            raise
        except Exception as e:  # pragma: no cover - keep serving
            logger.exception("run %s", run.id)
            RemoteIO(site, job, run).fail(str(e))
        beat.run_id = None


def main():
    logging.basicConfig(level=logging.INFO)
    url = os.getenv("TRAINER_URL", "").strip()
    token = os.getenv("TRAINER_TOKEN", "").strip()
    if not url or not token:
        raise SystemExit("Set TRAINER_URL (the site, e.g. http://192.168.1.10:5000) and TRAINER_TOKEN "
                         "(from the training page → 訓練伺服器)")
    os.environ.setdefault("MODELS_DIRECTORY", "/work")
    serve(url, token)


if __name__ == "__main__":
    main()
