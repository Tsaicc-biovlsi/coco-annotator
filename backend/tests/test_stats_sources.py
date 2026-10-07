"""Statistics: annotations by hand per member, per model, and imported."""
import io
import json
import os


def test_stats_split_by_source(world, dataset_directory):
    from PIL import Image
    from database import AnnotationModel, CategoryModel, ImageModel
    from webserver.util import preannotate
    c = world["client"]
    ds = c.post("/api/dataset/", json={"name": "stats_src", "categories": ["car"]}).get_json()["id"]
    folder = os.path.join(dataset_directory, "stats_src")
    os.makedirs(folder, exist_ok=True)
    for i in range(2):
        Image.new("RGB", (100, 80)).save(os.path.join(folder, f"s{i}.jpg"))
    c.get(f"/api/dataset/{ds}/scan")
    images = sorted(ImageModel.objects(dataset_id=ds), key=lambda i: i.file_name)
    car = CategoryModel.objects(name="car").first().id

    # by hand
    c.post("/api/annotation/", json={"image_id": images[0].id, "category_id": car,
                                     "segmentation": [[1, 1, 20, 1, 20, 20, 1, 20]]})
    # a model run on one image
    class Resolver:
        skipped, keypoints_mismatch = set(), set()

        def get(self, name):
            return CategoryModel.objects(id=car).first()
    preds = [{"class_name": "car", "segmentation": [[5, 5, 30, 5, 30, 30, 5, 30]], "bbox": [5, 5, 25, 25],
              "area": 625, "isbbox": True}] * 3
    preannotate.apply_predictions(images[1], preds, Resolver(), username="smoke", model_name="yolo11n.pt")
    # an import
    coco = {"images": [{"id": 1, "file_name": "s0.jpg"}], "categories": [{"id": 1, "name": "car"}],
            "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [40, 40, 10, 10]},
                            {"id": 2, "image_id": 1, "category_id": 1, "bbox": [60, 40, 10, 10]}]}
    c.post(f"/api/dataset/{ds}/coco", data={"coco": (io.BytesIO(json.dumps(coco).encode()), "c.json")},
           content_type="multipart/form-data")

    stats = c.get(f"/api/dataset/{ds}/stats").get_json()
    assert stats["users"]["smoke"] == {"annotations": 1, "images": 1}
    model = next(s for s in stats["sources"] if s["kind"] == "model")
    assert model["name"] == "yolo11n.pt" and model["annotations"] == 3 and model["images"] == 1
    assert model["by"] == ["smoke"]
    imported = next(s for s in stats["sources"] if s["kind"] == "import")
    assert imported["annotations"] == 2 and imported["images"] == 1
    assert AnnotationModel.objects(dataset_id=ds, source="model").count() == 3
