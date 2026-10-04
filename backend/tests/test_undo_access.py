import pytest

pytestmark = pytest.mark.order(-1)


def test_undo_only_own_items(world):
    from webserver import app
    from webserver.util.passwords import hash_password
    from database import AnnotationModel, UserModel

    c = world["client"]
    image_id = world["images"][1]["id"]
    category = world["categories"]["ship"]
    r = c.post("/api/annotation/", json={"image_id": image_id, "category_id": category,
                                         "segmentation": [[1, 1, 30, 1, 30, 30]]})
    ann = r.get_json()["id"]
    assert c.delete(f"/api/annotation/{ann}").status_code == 200

    if UserModel.objects(username="stranger").first() is None:
        UserModel(username="stranger", password=hash_password("pw"), name="S", is_admin=False).save()
    s = app.test_client()
    assert s.post("/api/user/login", json={"username": "stranger", "password": "pw"}).status_code == 200

    listed = [i["id"] for i in s.get("/api/undo/list/?limit=100&type=annotation").get_json()]
    assert ann not in listed
    assert s.post(f"/api/undo/?id={ann}&instance=annotation").status_code == 400
    assert s.delete(f"/api/undo/?id={ann}&instance=dataset").status_code == 400
    assert AnnotationModel.objects(id=ann).first().deleted

    # the owner can restore it
    UserModel.objects(username="smoke").update(set__is_admin=True)
    assert c.post(f"/api/undo/?id={ann}&instance=annotation").status_code == 200
    assert not AnnotationModel.objects(id=ann).first().deleted
