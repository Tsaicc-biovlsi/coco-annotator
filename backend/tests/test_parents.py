"""Parent categories: several per category, COCO round trip."""
import io
import json


def test_parents_create_update_import_export(world):
    from database import CategoryModel
    c = world["client"]
    r = c.post("/api/category/", json={"name": "sedan", "supercategories": ["car", " vehicle ", "car"]})
    cat = r.get_json()
    assert cat["supercategories"] == ["car", "vehicle"] and cat["supercategory"] == "car"

    # the old single field still works, a list in one string is split
    r = c.post("/api/category/", json={"name": "cablecar", "supercategory": "rail, vehicle"})
    assert r.get_json()["supercategories"] == ["rail", "vehicle"]

    r = c.put(f"/api/category/{cat['id']}", json={"name": "sedan", "supercategories": ["vehicle"]})
    assert r.status_code == 200
    model = CategoryModel.objects(id=cat["id"]).first()
    assert model.parents() == ["vehicle"] and model.supercategory == "vehicle"
    # nothing else changed: parents alone count as a change
    r = c.put(f"/api/category/{cat['id']}", json={"name": "sedan", "supercategories": []})
    assert r.get_json().get("success") and CategoryModel.objects(id=cat["id"]).first().supercategory == ""

    # import: new categories take their parents from the file
    d = world["dataset"]["id"]
    coco = {"images": [], "annotations": [],
            "categories": [{"id": 1, "name": "ferry", "supercategory": "boat"},
                           {"id": 2, "name": "kayak", "supercategories": ["boat", "small"]}]}
    r = c.post(f"/api/dataset/{d}/coco", data={"coco": (io.BytesIO(json.dumps(coco).encode()), "c.json")},
               content_type="multipart/form-data")
    assert r.status_code == 200, r.data
    assert CategoryModel.objects(name="ferry").first().parents() == ["boat"]
    assert CategoryModel.objects(name="kayak").first().parents() == ["boat", "small"]

    # export carries both fields
    from webserver.util import coco_util
    from database import DatasetModel
    out = coco_util.get_dataset_coco(DatasetModel.objects(id=d).first())
    kayak = next(x for x in out["categories"] if x["name"] == "kayak")
    assert kayak["supercategory"] == "boat" and kayak["supercategories"] == ["boat", "small"]
