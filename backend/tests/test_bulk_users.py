import pytest

pytestmark = pytest.mark.order(-1)


def test_bulk_create_students(world):
    from database import DatasetModel, UserModel
    from webserver import app
    UserModel.objects(username="smoke").update(set__is_admin=True)
    c = world["client"]
    ds = world["dataset"]["id"]
    r = c.post("/api/admin/users/bulk", json={"datasetId": ds, "users": [
        {"username": "b11223344", "name": "王小明"},
        {"username": "B11223355", "name": "陳小華", "password": "given-pw"},
        {"username": "B11223355", "name": "dup"},
        {"username": "12345678", "name": "no letter"},
        {"username": "B1234567", "name": "too short"},
    ]})
    assert r.status_code == 200, r.data
    body = r.get_json()
    names = {u["username"]: u for u in body["created"]}
    assert set(names) == {"B11223344", "B11223355"}
    assert len(names["B11223344"]["password"]) == 8
    assert names["B11223355"]["password"] == "given-pw"
    assert {i["reason"] for i in body["invalid"]} == {"format", "duplicate"}

    # members of the dataset, can log in, not admins
    assert {"B11223344", "B11223355"} <= set(DatasetModel.objects(id=ds).first().users)
    s = app.test_client()
    assert s.post("/api/user/login", json={"username": "B11223355", "password": "given-pw"}).status_code == 200
    assert not UserModel.objects(username="B11223355").first().is_admin
    assert world["dataset"]["name"] in [d["name"] for d in s.get("/api/dataset/data").get_json()["datasets"]]

    # running it again skips existing accounts
    r = c.post("/api/admin/users/bulk", json={"users": [{"username": "B11223344"}]})
    assert r.get_json()["created"] == [] and r.get_json()["existing"] == ["B11223344"]

    # students cannot create accounts
    assert s.post("/api/admin/users/bulk", json={"users": [{"username": "B99999999"}]}).status_code == 401
