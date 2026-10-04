import pytest

pytestmark = pytest.mark.order(-1)


@pytest.fixture(scope="module")
def admin_client():
    from webserver import app
    from database import UserModel

    client = app.test_client()
    if UserModel.objects(username="boss").first() is None:
        if UserModel.total() == 0:
            client.post("/api/user/register", json={"username": "boss", "password": "pw", "name": "Boss"})
        else:
            from webserver.util.passwords import hash_password
            UserModel(username="boss", password=hash_password("pw"), name="Boss", is_admin=True).save()
    r = client.post("/api/user/login", json={"username": "boss", "password": "pw"})
    assert r.status_code == 200, r.data
    return client


def test_toggle_admin(admin_client):
    c = admin_client
    r = c.post("/api/admin/user/", json={"username": "student", "password": "pw", "name": "S", "isAdmin": True})
    assert r.status_code == 200, r.data

    r = c.patch("/api/admin/user/student", json={"isAdmin": False})
    assert r.status_code == 200, r.data
    assert r.get_json()["is_admin"] is False
    assert "password" not in r.get_json()

    # name/password only: admin flag unchanged
    r = c.patch("/api/admin/user/student", json={"name": "Student"})
    assert r.get_json()["is_admin"] is False
    assert r.get_json()["name"] == "Student"

    r = c.patch("/api/admin/user/student", json={"isAdmin": True})
    assert r.get_json()["is_admin"] is True
    assert "password" not in c.get("/api/admin/user/student").get_json()


def test_cannot_demote_or_delete_self(admin_client):
    r = admin_client.patch("/api/admin/user/boss", json={"isAdmin": False})
    assert r.status_code == 400
    r = admin_client.delete("/api/admin/user/boss")
    assert r.status_code == 400
