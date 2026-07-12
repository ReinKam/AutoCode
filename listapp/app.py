"""
app.py — a small JSON API for shared lists (todo lists, shopping lists, etc.)

Access model (first-test scope, no passwords):
    - Anyone can claim a username.
    - Creating a list makes you its owner and first member.
    - Only members of a list can view/add/toggle/delete its items.
    - Anyone with the share_code can join a list as a member.

Endpoints:
    POST   /users                              {username} -> {username}
    POST   /lists                              {username, name} -> list (incl. share_code)
    POST   /lists/<share_code>/join            {username} -> membership confirmation
    GET    /lists/<share_code>?username=...    -> list + items (members only)
    POST   /lists/<share_code>/items           {username, text} -> item
    PATCH  /lists/<share_code>/items/<item_id> {username} -> toggles done
    DELETE /lists/<share_code>/items/<item_id> {username} -> removes item
"""

from flask import Flask, request, jsonify

import db
from auth import users as auth_users

app = Flask(__name__)


def _require_member(share_code, username):
    lst = db.get_list_by_share_code(share_code)
    if lst is None:
        return None, (jsonify(error="list not found"), 404)
    if not auth_users.is_member(share_code, username):
        return None, (jsonify(error="not a member of this list"), 403)
    return lst, None


@app.post("/users")
def create_or_get_user():
    body = request.get_json(force=True) or {}
    username = body.get("username", "")
    try:
        username = auth_users.find_or_create_user(username)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(username=username), 200


@app.post("/lists")
def create_list():
    body = request.get_json(force=True) or {}
    username = auth_users.find_or_create_user(body.get("username", ""))
    name = body.get("name", "").strip()
    if not name:
        return jsonify(error="name is required"), 400
    lst = db.create_list(name, username)
    return jsonify(lst), 201


@app.post("/lists/<share_code>/join")
def join_list(share_code):
    body = request.get_json(force=True) or {}
    username = auth_users.find_or_create_user(body.get("username", ""))
    lst = db.get_list_by_share_code(share_code)
    if lst is None:
        return jsonify(error="list not found"), 404
    db.add_member(lst["id"], username)
    return jsonify(joined=True, list=lst), 200


@app.get("/lists/<share_code>")
def view_list(share_code):
    username = request.args.get("username", "")
    lst, err = _require_member(share_code, username)
    if err:
        return err
    items = db.get_items(lst["id"])
    return jsonify(list=lst, items=items), 200


@app.post("/lists/<share_code>/items")
def add_item(share_code):
    body = request.get_json(force=True) or {}
    username = body.get("username", "")
    lst, err = _require_member(share_code, username)
    if err:
        return err
    text = body.get("text", "").strip()
    if not text:
        return jsonify(error="text is required"), 400
    item = db.add_item(lst["id"], text, username)
    return jsonify(item), 201


@app.patch("/lists/<share_code>/items/<int:item_id>")
def toggle_item(share_code, item_id):
    body = request.get_json(force=True) or {}
    username = body.get("username", "")
    lst, err = _require_member(share_code, username)
    if err:
        return err
    db.toggle_item(item_id)
    return jsonify(toggled=True), 200


@app.delete("/lists/<share_code>/items/<int:item_id>")
def remove_item(share_code, item_id):
    body = request.get_json(force=True) or {}
    username = body.get("username", "")
    lst, err = _require_member(share_code, username)
    if err:
        return err
    db.delete_item(item_id)
    return jsonify(deleted=True), 200


if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=5050)
