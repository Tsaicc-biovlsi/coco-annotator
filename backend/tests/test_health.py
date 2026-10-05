"""Dataset health endpoint."""
import os


def test_dataset_health(world, dataset_directory):
    from PIL import Image
    from database import AnnotationModel, CategoryModel
    c = world["client"]
    r = c.post("/api/dataset/", json={"name": "health_ds", "categories": ["car", "bike", "bus"]})
    ds = r.get_json()["id"]
    folder = os.path.join(dataset_directory, "health_ds")
    os.makedirs(folder, exist_ok=True)
    for i in range(3):
        Image.new("RGB", (200, 100)).save(os.path.join(folder, f"h{i}.jpg"))
    c.get(f"/api/dataset/{ds}/scan")
    images = sorted(c.get(f"/api/dataset/{ds}/data").get_json()["images"], key=lambda i: i["file_name"])
    car = CategoryModel.objects(name="car").first().id
    bike = CategoryModel.objects(name="bike").first().id

    def box(image_id, cat, x, y, w, h):
        a = AnnotationModel(image_id=image_id, category_id=cat, dataset_id=ds,
                            segmentation=[[x, y, x + w, y, x + w, y + h, x, y + h]], bbox=[x, y, w, h], area=w * h)
        a.save()
    h0, h1 = images[0]["id"], images[1]["id"]
    for k in range(12):
        box(h0, car, 5 + k, 5, 20, 10)          # 12 cars, two of them near-duplicates below
    box(h0, car, 5, 5, 20, 10)                   # exact duplicate of the first car
    box(h1, bike, 190, 50, 30, 20)               # sticks out of the 200 px wide image
    box(h1, bike, 10, 10, 1, 1)                  # degenerate

    health = c.get(f"/api/dataset/{ds}/health").get_json()
    t = health["totals"]
    assert t["images"] == 3 and t["annotated_images"] == 2 and t["annotations"] == 15
    codes = {i["code"]: i for i in health["issues"]}
    assert codes["unannotated"]["n"] == 1 and codes["unannotated"]["examples"][0]["file_name"] == "h2.jpg"
    assert "bus" in codes["emptyClasses"]["names"]
    assert any(n.startswith("bike") for n in codes["fewAnnotations"]["names"])
    assert "imbalance" not in codes          # 13 cars vs 2 bikes is below the 10x threshold
    assert codes["duplicates"]["n"] >= 1
    assert codes["outside"]["n"] == 1 and codes["degenerate"]["n"] == 1
    assert [r["name"] for r in health["classes"]][:2] == ["car", "bike"]
    objects = {b["label"]: b["n"] for b in health["objects_per_image"]}
    assert objects["0"] == 1 and objects["11-20"] == 1 and objects["2"] == 1
    assert sum(map(sum, health["heatmap"])) == 14
    assert health["box_sizes"]["small"] == 14
    assert health["resolutions"][0] == {"width": 200, "height": 100, "n": 3}
