"""Video import: frames at an interval become dataset images."""
import io
import os

import numpy as np


def _video_bytes(tmp_path, frames=30, fps=10):
    import cv2
    path = str(tmp_path / "clip.avi")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), fps, (160, 120))
    for i in range(frames):
        frame = np.full((120, 160, 3), i * 8, np.uint8)
        writer.write(frame)
    writer.release()
    with open(path, "rb") as f:
        return f.read()


def test_frame_names_sort_in_time():
    from webserver.util.video import frame_name, safe_stem
    assert frame_name("a", 0) == "a_000m00s000.jpg"
    assert frame_name("a", 61500) == "a_001m01s500.jpg"
    assert safe_stem("my clip (1).MP4") == "my_clip_(1)"


def test_video_import(world, dataset_directory, tmp_path):
    from database import ImageModel, TaskModel
    c = world["client"]
    ds = c.post("/api/dataset/", json={"name": "video_ds"}).get_json()["id"]
    data = _video_bytes(tmp_path)

    r = c.post(f"/api/dataset/{ds}/video", data={"video": (io.BytesIO(b"x"), "notes.txt")},
               content_type="multipart/form-data")
    assert r.status_code == 400
    r = c.post(f"/api/dataset/{ds}/video", data={"video": (io.BytesIO(data), "harbour cam.avi"),
                                                "every_seconds": "1", "max_frames": "100"},
               content_type="multipart/form-data")
    assert r.status_code == 200, r.data
    body = r.get_json()
    assert body["folder"] == "harbour_cam"
    task = TaskModel.objects(id=body["id"]).first()
    assert task.completed and task.errors == 0, task.logs

    # 3 seconds at 10 fps, one frame per second
    images = ImageModel.objects(dataset_id=ds).order_by("file_name")
    assert [i.file_name for i in images] == [
        "harbour_cam_000m00s000.jpg", "harbour_cam_000m01s000.jpg", "harbour_cam_000m02s000.jpg"]
    assert images[0].width == 160 and images[0].height == 120
    assert os.path.dirname(images[0].path).endswith("video_ds/harbour_cam")
    assert not os.listdir(os.path.join(dataset_directory, "video_ds", ".uploads"))   # video removed

    # the frame limit
    r = c.post(f"/api/dataset/{ds}/video", data={"video": (io.BytesIO(data), "short.avi"),
                                                "every_seconds": "0.1", "max_frames": "5"},
               content_type="multipart/form-data")
    task = TaskModel.objects(id=r.get_json()["id"]).first()
    assert ImageModel.objects(dataset_id=ds, file_name__startswith="short_").count() == 5
    assert task.warnings == 1
