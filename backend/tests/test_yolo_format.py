"""COCO <-> YOLO label conversion (pure functions and the API)."""
import io
import os
import zipfile

import pytest

from geometry.yolo_format import coco_to_yolo, data_yaml, detect_task, parse_names, read_zip, yolo_to_coco

W, H = 200, 100
IMAGES = [{"id": 1, "file_name": "a.jpg", "width": W, "height": H},
          {"id": 2, "file_name": "sub/b.png", "width": W, "height": H}]


def _coco(annotations, keypoints=None):
    cats = [{"id": 10, "name": "ship"}, {"id": 20, "name": "car"}]
    if keypoints:
        cats[0]["keypoints"] = keypoints
    return {"images": IMAGES, "categories": cats, "annotations": annotations}


def _values(line):
    return [float(v) for v in line.split()]


def test_detect_round_trip():
    coco = _coco([{"id": 1, "image_id": 1, "category_id": 20, "bbox": [20, 10, 40, 30],
                   "segmentation": [[20, 10, 60, 10, 60, 40, 20, 40]]}])
    out = coco_to_yolo(coco, "detect")
    assert out["names"] == ["ship", "car"]
    assert _values(out["labels"][1][0]) == pytest.approx([1, 0.2, 0.25, 0.2, 0.3])
    assert out["labels"][2] == []

    back, stats = yolo_to_coco({"a": out["labels"][1][0]}, IMAGES, names=out["names"])
    assert stats["task"] == "detect" and stats["matched"] == 1
    ann = back["annotations"][0]
    assert ann["bbox"] == pytest.approx([20, 10, 40, 30])
    assert back["categories"][ann["category_id"] - 1]["name"] == "car"


def test_segment_merges_multi_polygons():
    poly1 = [10, 10, 30, 10, 30, 30, 10, 30]
    poly2 = [100, 50, 120, 50, 120, 70]
    coco = _coco([{"id": 1, "image_id": 1, "category_id": 10, "segmentation": [poly1, poly2]}])
    line = coco_to_yolo(coco, "segment")["labels"][1][0]
    values = _values(line)
    assert values[0] == 0 and (len(values) - 1) // 2 == 4 + 3 + 2  # both rings + 2 bridge points

    back, stats = yolo_to_coco({"a.txt": "0 0.1 0.1 0.5 0.1 0.5 0.9"}, IMAGES, names=["ship"])
    assert stats["task"] == "segment"
    ann = back["annotations"][0]
    assert ann["segmentation"] == [[20, 10, 100, 10, 100, 90]]
    assert ann["area"] == pytest.approx(80 * 80 / 2)


def test_obb_round_trip_keeps_orientation():
    from geometry import rbbox_to_polygon
    rbbox = [100, 50, 60, 20, 30]
    coco = _coco([{"id": 1, "image_id": 1, "category_id": 10, "isrbbox": True, "rbbox": rbbox,
                   "segmentation": [rbbox_to_polygon(rbbox)]},
                  # a plain polygon gets the minimum-area rectangle
                  {"id": 2, "image_id": 2, "category_id": 10,
                   "segmentation": [[10, 10, 50, 10, 50, 30, 10, 30, 30, 20]]}])
    out = coco_to_yolo(coco, "obb")
    assert len(_values(out["labels"][1][0])) == 9 and len(out["labels"][2]) == 1
    assert coco_to_yolo(coco, "obb", only_rbbox=True)["skipped"] == 1

    back, stats = yolo_to_coco({"a": out["labels"][1][0]}, IMAGES, names=out["names"])
    assert stats["task"] == "obb"
    ann = back["annotations"][0]
    assert ann["isrbbox"] and ann["rbbox"] == pytest.approx(rbbox, abs=0.05)


def test_pose_round_trip():
    labels = ["nose", "left_eye", "right_eye"]
    coco = _coco([{"id": 1, "image_id": 1, "category_id": 10, "bbox": [0, 0, 100, 50],
                   "keypoints": [50, 25, 2, 0, 0, 0, 80, 40, 1]}], keypoints=labels)
    out = coco_to_yolo(coco, "pose")
    assert out["kpt_shape"] == [3, 3]
    assert out["flip_idx"] == [0, 2, 1]
    yaml_text = data_yaml(out["names"], "pose", out["kpt_shape"], out["flip_idx"])
    names, kpt_shape = parse_names(yaml_text, "data.yaml")
    assert names == ["ship", "car"] and kpt_shape == [3, 3]

    back, stats = yolo_to_coco({"a": out["labels"][1][0]}, IMAGES, names=names, kpt_shape=kpt_shape)
    assert stats["task"] == "pose"
    ann = back["annotations"][0]
    assert ann["keypoints"] == pytest.approx([50, 25, 2, 0, 0, 0, 80, 40, 1])
    assert ann["isbbox"] and ann["bbox"] == pytest.approx([0, 0, 100, 50])
    assert back["categories"][0]["keypoints"] == ["1", "2", "3"]


def test_task_detection_and_matching():
    assert detect_task(["0 .5 .5 .1 .1"]) == "detect"
    assert detect_task(["0 .1 .1 .2 .1 .2 .2 .1 .2"]) == "obb"
    assert detect_task(["0 .1 .1 .2 .1 .2 .2", "0 .5 .5 .1 .1"]) == "segment"
    assert detect_task(["0 .5 .5 .1 .1 .2 .2 2 .3 .3 1"]) == "pose"

    coco, stats = yolo_to_coco({"zzz": "0 .5 .5 .1 .1", "b": "3 .5 .5 .1 .1\nbad line"}, IMAGES)
    assert stats["matched"] == 1 and stats["unmatched"] == ["zzz"]
    assert coco["images"][0]["file_name"] == "sub/b.png"
    assert [c["name"] for c in coco["categories"]] == ["class_3"]


def test_read_zip_layouts():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("ds/data.yaml", "names:\n  0: ship\n  1: car\n")
        zf.writestr("ds/labels/train/a.txt", "1 .5 .5 .2 .2\n")
        zf.writestr("ds/labels/val/b.txt", "0 .5 .5 .2 .2\n")
        zf.writestr("ds/classes.txt", "wrong\n")
        zf.writestr("__MACOSX/ds/labels/._a.txt", "junk")
    texts, names, shape = read_zip(io.BytesIO(buf.getvalue()))
    assert sorted(texts) == ["a", "b"] and names == ["ship", "car"] and shape is None


# ------------------------------------------------------------------ API

@pytest.fixture(scope="module")
def yolo_world(world, dataset_directory):
    from PIL import Image
    c = world["client"]
    r = c.post("/api/dataset/", json={"name": "yolo_conv", "categories": ["ship"]})
    assert r.status_code == 200, r.data
    ds = r.get_json()
    folder = os.path.join(dataset_directory, "yolo_conv")
    os.makedirs(folder, exist_ok=True)
    for name in ("p1.jpg", "p2.jpg"):
        Image.new("RGB", (W, H), (10, 80, 120)).save(os.path.join(folder, name))
    assert c.get(f"/api/dataset/{ds['id']}/scan").status_code == 200
    images = {i["file_name"]: i for i in c.get(f"/api/dataset/{ds['id']}/data").get_json()["images"]}
    return {"client": c, "dataset": ds, "images": images}


def _upload(c, ds_id, files, task="auto"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)
    buf.seek(0)
    return c.post(f"/api/dataset/{ds_id}/yolo", data={"yolo": (buf, "labels.zip"), "task": task},
                  content_type="multipart/form-data")


def test_api_yolo_import_then_export(yolo_world):
    from database import AnnotationModel, CategoryModel, ExportModel, TaskModel
    c, ds = yolo_world["client"], yolo_world["dataset"]["id"]
    p1 = yolo_world["images"]["p1.jpg"]

    r = _upload(c, ds, {"data.yaml": "names: [ship, kayak]\n",
                        "labels/p1.txt": "1 0.5 0.5 0.2 0.4\n0 0.1 0.1 0.3 0.1 0.3 0.3 0.1 0.3\n",
                        "labels/missing.txt": "0 .5 .5 .1 .1\n"})
    assert r.status_code == 200, r.data
    body = r.get_json()
    assert body["stats"]["matched"] == 1 and body["stats"]["unmatched"] == 1
    assert body["stats"]["task"] == "segment"  # mixed 5 / 9 values -> polygons + boxes
    task = TaskModel.objects(id=body["id"]).first()
    assert task.completed and task.errors == 0, task.logs

    kayak = CategoryModel.objects(name="kayak").first()
    anns = AnnotationModel.objects(image_id=p1["id"], deleted=False)
    assert anns.count() == 2
    box = anns.filter(category_id=kayak.id).first()
    assert box.isbbox and box.bbox == pytest.approx([80, 30, 40, 40])

    # nothing matches -> a clear error, no task
    r = _upload(c, ds, {"labels/nope.txt": "0 .5 .5 .1 .1\n"})
    assert r.status_code == 400 and "file name" in r.get_json()["message"]
    r = c.post(f"/api/dataset/{ds}/yolo", data={"yolo": (io.BytesIO(b"not a zip"), "x.zip")},
               content_type="multipart/form-data")
    assert r.status_code == 400

    # export the same dataset as YOLO detect, with images
    r = c.get(f"/api/dataset/{ds}/export?format=yolo&yolo_task=detect&with_images=true&with_empty_images=true")
    assert r.status_code == 200, r.data
    export = ExportModel.objects(dataset_id=ds).order_by("-created_at").first()
    assert export.path.endswith(".zip") and export.tags[:2] == ["YOLO", "detect"]
    d = c.get(f"/api/export/{export.id}/download")
    assert d.status_code == 200
    assert ".zip" in d.headers["Content-Disposition"]
    with zipfile.ZipFile(io.BytesIO(d.data)) as zf:
        names = set(zf.namelist())
        assert {"data.yaml", "classes.txt", "labels/p1.txt", "labels/p2.txt", "images/p1.jpg"} <= names
        lines = zf.read("labels/p1.txt").decode().split("\n")
        classes = zf.read("classes.txt").decode().split()
        assert zf.read("labels/p2.txt") == b""
    kayak_lines = [l for l in lines if l and classes[int(l.split()[0])] == "kayak"]
    assert _values(kayak_lines[0])[1:] == pytest.approx([0.5, 0.5, 0.2, 0.4])

    # COCO export still downloads as .json
    assert c.get(f"/api/dataset/{ds}/export").status_code == 200
    export = ExportModel.objects(dataset_id=ds).order_by("-created_at").first()
    d = c.get(f"/api/export/{export.id}/download")
    assert ".json" in d.headers["Content-Disposition"]


def test_api_category_counts_and_export_order(yolo_world):
    from database import CategoryModel, ExportModel
    c, ds = yolo_world["client"], yolo_world["dataset"]["id"]
    # runs after the import test above: p1 has a kayak box and a ship polygon
    ship = CategoryModel.objects(name="ship").first().id
    kayak = CategoryModel.objects(name="kayak").first().id

    counts = c.get(f"/api/dataset/{ds}/category_counts").get_json()
    assert counts[str(kayak)]["annotations"] == 1 and counts[str(kayak)]["boxes"] == 1
    assert counts[str(ship)]["polygons"] == 1 and counts[str(ship)]["images"] == 1

    # the order of the ids is the YOLO class order
    r = c.get(f"/api/dataset/{ds}/export?format=yolo&categories={kayak},{ship}")
    assert r.status_code == 200, r.data
    export = ExportModel.objects(dataset_id=ds).order_by("-id").first()
    with zipfile.ZipFile(export.path) as zf:
        assert zf.read("classes.txt").decode().split() == ["kayak", "ship"]
    r = c.get(f"/api/dataset/{ds}/export?format=yolo&categories={ship}")
    export = ExportModel.objects(dataset_id=ds).order_by("-id").first()
    with zipfile.ZipFile(export.path) as zf:
        assert zf.read("classes.txt").decode().split() == ["ship"]
        assert zf.read("labels/p1.txt").decode().count("\n") == 1
