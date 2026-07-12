# listapp — shared lists (todo, shopping, etc.)

A minimal Flask JSON API for creating lists that multiple people can view
and edit together, via a shareable code. Built as AutoCode's first real
governed build — see `_autocode/` for the full decision trail.

## Run it

```bash
pip install -r requirements.txt --break-system-packages
python3 app.py
# -> listening on http://0.0.0.0:5050
```

## Run the tests

```bash
python3 tests/test_app.py
```

## API

| Method | Path | Body | Notes |
|---|---|---|---|
| POST | `/users` | `{username}` | Claims/confirms a username. No password (see `auth/users.py`). |
| POST | `/lists` | `{username, name}` | Creates a list, returns it including `share_code`. |
| POST | `/lists/<share_code>/join` | `{username}` | Adds the user as a member. |
| GET | `/lists/<share_code>?username=...` | — | List + items. Members only. |
| POST | `/lists/<share_code>/items` | `{username, text}` | Adds an item. Members only. |
| PATCH | `/lists/<share_code>/items/<id>` | `{username}` | Toggles done. Members only. |
| DELETE | `/lists/<share_code>/items/<id>` | `{username}` | Removes an item. Members only. |

## Example session

```bash
curl -X POST localhost:5050/lists -H 'Content-Type: application/json' \
     -d '{"username":"alice","name":"Groceries"}'
# -> {"id":1,"name":"Groceries","share_code":"aB3dEf","owner_username":"alice"}

curl -X POST localhost:5050/lists/aB3dEf/join -H 'Content-Type: application/json' \
     -d '{"username":"bob"}'

curl -X POST localhost:5050/lists/aB3dEf/items -H 'Content-Type: application/json' \
     -d '{"username":"bob","text":"Eggs"}'

curl localhost:5050/lists/aB3dEf?username=alice
# -> alice now sees the item bob added
```

## How this was built

Every real file write and shell command in this build was proposed to,
and evaluated by, the actual AutoCode Policy Engine (not a mock) before
being executed — see `_autocode/audit_log.jsonl` for the complete,
hash-chained trail of every decision made. Two writes to `auth/**`
(`auth/__init__.py`, `auth/users.py`) were blocked with `require_hil`
and required an explicit human approval before proceeding; every other
write/command matched an explicit allow rule in `_autocode/ruleset.json`.

## Known limitations (first-test scope, not gaps that were missed)

- No passwords/sessions — usernames are self-claimed. Real auth would
  land in `auth/users.py`, which is exactly the file this build's HIL
  gate already protects.
- No HTML UI — JSON API only.
- SQLite, single file, no migrations.
- No Git integration (repo init/commit) — out of scope for AutoCode's
  own MVP too (see the core AutoCode README).
