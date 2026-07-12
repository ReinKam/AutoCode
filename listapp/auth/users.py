"""
auth/users.py — minimal identity and access control for shared lists.

Scope for this first test: no passwords, no sessions. A "user" is just a
username string. Anyone can claim a username (this is intentionally the
simplest possible thing that lets multiple people share a list — real
authentication is out of scope for this first build, but is exactly the
kind of change that should land here and go through this same HIL gate).
"""

import db


def find_or_create_user(username: str) -> str:
    username = username.strip()
    if not username:
        raise ValueError("username must not be empty")
    conn = db.get_connection()
    conn.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", (username,))
    conn.commit()
    conn.close()
    return username


def is_member(share_code: str, username: str) -> bool:
    lst = db.get_list_by_share_code(share_code)
    if lst is None:
        return False
    conn = db.get_connection()
    row = conn.execute(
        "SELECT 1 FROM list_members WHERE list_id = ? AND username = ?",
        (lst["id"], username),
    ).fetchone()
    conn.close()
    return row is not None
