"""
db.py — SQLite storage for shared lists.

Schema:
    users(username PRIMARY KEY)
    lists(id, name, share_code UNIQUE, owner_username)
    list_members(list_id, username)   -- who can see/edit a list
    items(id, list_id, text, done, added_by)
"""

import sqlite3
import secrets

DB_PATH = "listapp.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            share_code TEXT UNIQUE NOT NULL,
            owner_username TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS list_members (
            list_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            PRIMARY KEY (list_id, username)
        );
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            added_by TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def create_list(name: str, owner_username: str) -> dict:
    share_code = secrets.token_urlsafe(4)
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO lists (name, share_code, owner_username) VALUES (?, ?, ?)",
        (name, share_code, owner_username),
    )
    list_id = cur.lastrowid
    conn.execute(
        "INSERT OR IGNORE INTO list_members (list_id, username) VALUES (?, ?)",
        (list_id, owner_username),
    )
    conn.commit()
    conn.close()
    return {"id": list_id, "name": name, "share_code": share_code, "owner_username": owner_username}


def get_list_by_share_code(share_code: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM lists WHERE share_code = ?", (share_code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_member(list_id: int, username: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO list_members (list_id, username) VALUES (?, ?)",
        (list_id, username),
    )
    conn.commit()
    conn.close()


def get_items(list_id: int) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM items WHERE list_id = ? ORDER BY id", (list_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_item(list_id: int, text: str, added_by: str) -> dict:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO items (list_id, text, added_by) VALUES (?, ?, ?)",
        (list_id, text, added_by),
    )
    item_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": item_id, "list_id": list_id, "text": text, "done": 0, "added_by": added_by}


def toggle_item(item_id: int) -> None:
    conn = get_connection()
    conn.execute("UPDATE items SET done = 1 - done WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def delete_item(item_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
