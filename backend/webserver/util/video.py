"""Import a video by saving frames at a fixed interval as dataset images.

Frames go to ``<dataset>/<video name>/<video name>_<time>.jpg`` (the time
as minutes-seconds-milliseconds, so names sort in playback order) and
are added to the dataset straight away. Runs as a background task.
"""
import logging
import os
import re
import threading

import cv2

from database import DatasetModel, ImageModel, TaskModel

logger = logging.getLogger('gunicorn.error')

VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv")


def safe_stem(name):
    stem = os.path.splitext(os.path.basename(name or "video"))[0]
    stem = re.sub(r'[\\/:*?"<>|\s]+', "_", stem).strip("._")
    return stem[:80] or "video"


def frame_name(stem, ms):
    minutes, rest = divmod(int(round(ms)), 60000)
    seconds, millis = divmod(rest, 1000)
    return f"{stem}_{minutes:03d}m{seconds:02d}s{millis:03d}.jpg"


def extract_frames(video_path, out_dir, stem, every_seconds=1.0, max_frames=1000,
                   on_progress=None, quality=95):
    """Save one frame every ``every_seconds``. Returns the saved paths."""
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise ValueError("The video could not be opened (unsupported format or codec)")
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 0
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or fps > 1000:
            fps = 30.0
        step = max(1, int(round(every_seconds * fps)))
        expected = min(max_frames, (total + step - 1) // step) if total > 0 else max_frames
        os.makedirs(out_dir, exist_ok=True)

        saved, index = [], 0
        while len(saved) < max_frames:
            if not capture.grab():
                break
            if index % step == 0:
                ok, frame = capture.retrieve()
                if ok and frame is not None:
                    path = os.path.join(out_dir, frame_name(stem, index * 1000.0 / fps))
                    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
                    saved.append(path)
                    if on_progress and expected:
                        on_progress(min(99.0, 100.0 * len(saved) / expected))
            index += 1
        return saved, {"fps": round(fps, 3), "frames": total, "step": step}
    finally:
        capture.release()


def _run(task_id, dataset_id, video_path, original_name, every_seconds, max_frames, socket):
    task = TaskModel.objects.get(id=task_id)
    dataset = DatasetModel.objects.get(id=dataset_id)
    task.update(status="PROGRESS")
    stem = safe_stem(original_name)
    out_dir = os.path.join(dataset.directory, stem)
    created = 0
    try:
        task.info(f"Extracting a frame every {every_seconds} s (at most {max_frames}) from {original_name}")
        paths, info = extract_frames(
            video_path, out_dir, stem, every_seconds, max_frames,
            on_progress=lambda p: task.set_progress(p, socket=socket))
        task.info(f"Video: {info['fps']} fps, {info['frames']} frames; kept every {info['step']}th frame")
        for path in paths:
            if ImageModel.objects(path=path).first() is not None:
                continue
            try:
                image = ImageModel.create_from_path(path, dataset.id)
                image.save()
                created += 1
            except Exception as e:  # e.g. created by the folder watcher at the same time
                logger.info(f"Frame {path} not added: {e}")
        task.info(f"Added {created} frames to {dataset.name}/{stem}/")
        if len(paths) >= max_frames:
            task.warning(f"Stopped at the limit of {max_frames} frames")
    except Exception as e:
        logger.exception("Video import failed")
        task.error(str(e))
    finally:
        try:
            os.remove(video_path)
        except OSError:
            pass
        task.set_progress(100, socket=socket)


def import_video(dataset, video_path, original_name, every_seconds=1.0, max_frames=1000,
                 user=None, socket=None, background=True):
    task = TaskModel(
        name=f"Importing video {os.path.basename(original_name)} into {dataset.name}",
        dataset_id=dataset.id,
        group="Video Import",
    )
    if user is not None:
        task.creator = user.username
    task.save()
    args = (task.id, dataset.id, video_path, original_name, every_seconds, max_frames, socket)
    if background:
        threading.Thread(target=_run, args=args, daemon=True).start()
    else:
        _run(*args)
    return {"id": task.id, "name": task.name, "folder": safe_stem(original_name)}
