"""Chat: one room per dataset."""
import os

from webserver.util.passwords import hash_password


def _login(username, name=""):
    from database import UserModel
    from webserver import app
    UserModel.objects(username=username).delete()
    UserModel(username=username, password=hash_password("pw"), name=name or username, is_admin=False).save()
    c = app.test_client()
    assert c.post("/api/user/login", json={"username": username, "password": "pw"}).status_code == 200
    return c


def _world(dataset_directory, prefix):
    from PIL import Image
    owner = _login(prefix + "_own", "老師")
    member = _login(prefix + "_mem", "阿明")
    stranger = _login(prefix + "_str")
    ds = owner.post("/api/dataset/", json={"name": prefix + "_ds"}).get_json()["id"]
    folder = os.path.join(dataset_directory, prefix + "_ds")
    os.makedirs(folder, exist_ok=True)
    Image.new("RGB", (32, 32)).save(os.path.join(folder, "a.jpg"))
    owner.get(f"/api/dataset/{ds}/scan")
    assert owner.post(f"/api/dataset/{ds}/members", json={"add": [prefix + "_mem"]}).status_code == 200
    image = owner.get(f"/api/dataset/{ds}/data").get_json()["images"][0]
    return owner, member, stranger, ds, image


def test_members_chat_and_unread(dataset_directory):
    owner, member, stranger, ds, image = _world(dataset_directory, "ch1")

    r = member.post(f"/api/chat/dataset/{ds}", json={"text": "  第一張是什麼？ ", "image_id": image["id"]})
    assert r.status_code == 200, r.data
    msg = r.get_json()
    assert msg["text"] == "第一張是什麼？" and msg["name"] == "阿明" and msg["file_name"] == "a.jpg"

    data = owner.get(f"/api/chat/dataset/{ds}").get_json()
    assert [m["text"] for m in data["messages"]] == ["第一張是什麼？"] and data["unread"] == 1
    # the sender has nothing unread
    assert member.get(f"/api/chat/dataset/{ds}").get_json()["unread"] == 0

    assert owner.post(f"/api/chat/dataset/{ds}/read", json={"last_id": msg["id"]}).get_json()["unread"] == 0
    owner.post(f"/api/chat/dataset/{ds}", json={"text": "是 vial"})
    assert member.get(f"/api/chat/dataset/{ds}").get_json()["unread"] == 1

    # not a member: no reading, no writing
    assert stranger.get(f"/api/chat/dataset/{ds}").status_code == 400
    assert stranger.post(f"/api/chat/dataset/{ds}", json={"text": "hi"}).status_code == 400
    # empty, too long, an image of another dataset
    assert member.post(f"/api/chat/dataset/{ds}", json={"text": "   "}).status_code == 400
    assert member.post(f"/api/chat/dataset/{ds}", json={"text": "x" * 1001}).status_code == 400
    assert member.post(f"/api/chat/dataset/{ds}", json={"text": "x", "image_id": 999999}).status_code == 400


def test_paging(dataset_directory):
    owner, member, _, ds, _ = _world(dataset_directory, "ch2")
    for i in range(7):
        owner.post(f"/api/chat/dataset/{ds}", json={"text": str(i)})
    page = member.get(f"/api/chat/dataset/{ds}?limit=3").get_json()
    assert [m["text"] for m in page["messages"]] == ["4", "5", "6"] and page["more"]
    older = member.get(f"/api/chat/dataset/{ds}?limit=5&before={page['messages'][0]['id']}").get_json()
    assert [m["text"] for m in older["messages"]] == ["0", "1", "2", "3"] and not older["more"]


def test_messages_reach_the_room_only(dataset_directory):
    from webserver import app
    from webserver.sockets import socketio
    import socketio as python_socketio
    owner, member, stranger, ds, _ = _world(dataset_directory, "ch3")

    queue_manager = socketio.server.manager
    socketio.server.manager = python_socketio.Manager()
    socketio.server.manager.set_server(socketio.server)
    try:
        s_member = socketio.test_client(app, flask_test_client=member)
        s_stranger = socketio.test_client(app, flask_test_client=stranger)
        assert s_member.emit("watch_chat", {"dataset_id": ds}, callback=True) is True
        assert s_stranger.emit("watch_chat", {"dataset_id": ds}, callback=True) is False
        for s in (s_member, s_stranger):
            s.get_received()
        owner.post(f"/api/chat/dataset/{ds}", json={"text": "大家好"})
        got = lambda s: [m["args"][0]["text"] for m in s.get_received() if m["name"] == "chat"]
        assert got(s_member) == ["大家好"]
        assert got(s_stranger) == []
    finally:
        socketio.server.manager = queue_manager
