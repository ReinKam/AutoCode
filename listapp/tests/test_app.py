"""
tests/test_app.py — end-to-end tests for the shared list API.

Run: python3 -m pytest tests/test_app.py -v
(or: python3 tests/test_app.py, which runs everything with plain asserts)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def make_client():
    import db
    import app as app_module

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db.DB_PATH = path
    db.init_db()
    app_module.app.testing = True
    return app_module.app.test_client(), path


def test_create_list_and_add_item():
    client, db_path = make_client()
    try:
        r = client.post("/lists", json={"username": "alice", "name": "Groceries"})
        assert r.status_code == 201, r.get_json()
        share_code = r.get_json()["share_code"]

        r = client.post(f"/lists/{share_code}/items", json={"username": "alice", "text": "Milk"})
        assert r.status_code == 201, r.get_json()

        r = client.get(f"/lists/{share_code}", query_string={"username": "alice"})
        assert r.status_code == 200
        items = r.get_json()["items"]
        assert len(items) == 1 and items[0]["text"] == "Milk"
    finally:
        os.remove(db_path)


def test_second_user_cannot_see_list_before_joining():
    client, db_path = make_client()
    try:
        r = client.post("/lists", json={"username": "alice", "name": "Groceries"})
        share_code = r.get_json()["share_code"]

        r = client.get(f"/lists/{share_code}", query_string={"username": "bob"})
        assert r.status_code == 403, "bob should not see the list before joining"
    finally:
        os.remove(db_path)


def test_second_user_can_join_and_then_share_list():
    client, db_path = make_client()
    try:
        r = client.post("/lists", json={"username": "alice", "name": "Groceries"})
        share_code = r.get_json()["share_code"]

        r = client.post(f"/lists/{share_code}/join", json={"username": "bob"})
        assert r.status_code == 200

        r = client.post(f"/lists/{share_code}/items", json={"username": "bob", "text": "Eggs"})
        assert r.status_code == 201

        r = client.get(f"/lists/{share_code}", query_string={"username": "alice"})
        items = r.get_json()["items"]
        assert any(i["text"] == "Eggs" and i["added_by"] == "bob" for i in items), \
            "alice should see the item bob added"
    finally:
        os.remove(db_path)


def test_toggle_and_delete_item():
    client, db_path = make_client()
    try:
        r = client.post("/lists", json={"username": "alice", "name": "Todo"})
        share_code = r.get_json()["share_code"]
        r = client.post(f"/lists/{share_code}/items", json={"username": "alice", "text": "Task 1"})
        item_id = r.get_json()["id"]

        r = client.patch(f"/lists/{share_code}/items/{item_id}", json={"username": "alice"})
        assert r.status_code == 200

        r = client.get(f"/lists/{share_code}", query_string={"username": "alice"})
        assert r.get_json()["items"][0]["done"] == 1

        r = client.delete(f"/lists/{share_code}/items/{item_id}", json={"username": "alice"})
        assert r.status_code == 200

        r = client.get(f"/lists/{share_code}", query_string={"username": "alice"})
        assert r.get_json()["items"] == []
    finally:
        os.remove(db_path)


if __name__ == "__main__":
    tests = [
        test_create_list_and_add_item,
        test_second_user_cannot_see_list_before_joining,
        test_second_user_can_join_and_then_share_list,
        test_toggle_and_delete_item,
    ]
    failures = []
    for t in tests:
        try:
            t()
            print(f"[PASS] {t.__name__}")
        except AssertionError as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failures.append(t.__name__)
    print()
    if failures:
        print(f"{len(failures)} of {len(tests)} tests FAILED: {failures}")
        sys.exit(1)
    print(f"All {len(tests)} tests passed.")
