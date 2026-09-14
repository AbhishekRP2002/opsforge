"""Stateful, source-qualified Okta identity simulation."""

import base64
import csv
import hashlib
import io
import json
import re
import sqlite3
from pathlib import PurePosixPath

from ..storage.database import Database

ID_PATTERN = re.compile(r"[a-zA-Z0-9_\-@.+]+")
PROFILE_COLUMNS = {
    "login": "login",
    "email": "email",
    "firstName": "first_name",
    "lastName": "last_name",
}


def _error(message: str, *, listed: bool = True):
    value = [{"error": message}] if listed else {"error": message}
    return value, True


def _valid(identifier: object, label: str):
    if (
        not isinstance(identifier, str)
        or not identifier
        or ".." in identifier
        or not ID_PATTERN.fullmatch(identifier)
    ):
        return _error(
            f"Invalid {label}: expected an Okta ID without traversal or URL-reserved characters"
        )
    return None


def _scope(db: Database, required: str, *, listed: bool):
    found = db.connection.execute(
        "SELECT 1 FROM okta_scopes WHERE scope = ?", (required,)
    ).fetchone()
    if found is None:
        return _error(
            f"Your token is missing required scope(s): {required}", listed=listed
        )
    return None


def _profile(row) -> dict:
    extras = json.loads(row["profile_json"])
    return {
        "login": row["login"],
        "email": row["email"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
    } | extras


def _user(row) -> dict:
    return {"id": row["id"], "status": row["status"], "profile": _profile(row)}


def _find_user(db: Database, identifier: str):
    return db.connection.execute(
        "SELECT * FROM okta_users WHERE id = ? OR login = ? ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END LIMIT 1",
        (identifier, identifier, identifier),
    ).fetchone()


def _group(row) -> dict:
    return {"id": row["id"], "profile": json.loads(row["profile_json"])}


def _next_id(db: Database, table: str, prefix: str) -> str:
    row = db.connection.execute(
        "SELECT value FROM simulated_sequences WHERE name=?", (table,)
    ).fetchone()
    count = (
        row["value"]
        if row is not None
        else db.connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    )
    while True:
        count += 1
        value = f"{prefix}{count:06d}"
        if (
            db.connection.execute(
                f"SELECT 1 FROM {table} WHERE id = ?", (value,)
            ).fetchone()
            is None
        ):
            db.connection.execute(
                "INSERT INTO simulated_sequences VALUES (?, ?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                (table, count),
            )
            return value


def _query_signature(kind: str, values: tuple[object, ...]) -> str:
    raw = json.dumps([kind, *values], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _cursor(signature: str, offset: int) -> str:
    return (
        base64.urlsafe_b64encode(f"{signature}:{offset}".encode()).decode().rstrip("=")
    )


def _offset(value: str | None, signature: str):
    if value is None:
        return 0, None
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
        found, raw_offset = decoded.split(":", 1)
        offset = int(raw_offset)
        if found != signature or offset < 0:
            raise ValueError
        return offset, None
    except (ValueError, UnicodeError):
        return 0, "Invalid or query-mismatched pagination cursor"


def _matches(record: dict, expression: str | None, kind: str) -> bool:
    if not expression:
        return True
    match = re.fullmatch(
        r'(status|profile\.[A-Za-z][A-Za-z0-9]*) eq "([^"]*)"', expression
    )
    if not match:
        raise ValueError(
            f'Unsupported {kind} expression; supported subset is field eq "value"'
        )
    field, expected = match.groups()
    actual = (
        record.get("status")
        if field == "status"
        else record.get("profile", {}).get(field[8:])
    )
    return actual == expected


def _page(
    items: list,
    *,
    kind: str,
    query: tuple[object, ...],
    after: str | None,
    limit: int | None,
    fetch_all: bool,
    minimum: int | None,
    maximum: int,
    max_pages: int,
    fetch_all_size: int | None = None,
):
    requested = 20 if limit is None else limit
    warning = None
    effective = requested
    if minimum is not None and effective < minimum:
        warning, effective = (
            f"limit {effective} is below minimum ({minimum}); clamped to {minimum}",
            minimum,
        )
    if effective > maximum:
        warning, effective = (
            f"limit {effective} exceeds maximum ({maximum}); clamped to {maximum}",
            maximum,
        )
    if fetch_all_size is not None and fetch_all:
        effective = fetch_all_size
    signature = _query_signature(kind, query)
    start, cursor_error = _offset(after, signature)
    if cursor_error:
        return None, cursor_error
    if start > len(items):
        return None, "Invalid pagination cursor offset"
    if fetch_all:
        cap = effective * max_pages
        selected = items[start : start + cap]
        stopped = start + len(selected) < len(items)
        result = {
            "items": selected,
            "total_fetched": len(selected),
            "has_more": False,
            "next_cursor": None,
            "fetch_all_used": True,
            "pagination_info": {
                "pages_fetched": max(1, (len(selected) + effective - 1) // effective),
                "total_items": len(selected),
                "stopped_early": stopped,
                "stop_reason": f"maximum {max_pages} pages reached"
                if stopped
                else None,
            },
        }
    else:
        selected = items[start : start + effective]
        has_more = start + len(selected) < len(items)
        result = {
            "items": selected,
            "total_fetched": len(selected),
            "has_more": has_more,
            "next_cursor": _cursor(signature, start + len(selected))
            if has_more
            else None,
            "fetch_all_used": False,
        }
    if warning:
        result["warning"] = warning
    return result, None


def list_users(db, arguments, step, clock):
    if denied := _scope(db, "okta.users.read", listed=False):
        return denied
    rows = db.connection.execute("SELECT * FROM okta_users ORDER BY id").fetchall()
    records = [_user(row) for row in rows if row["status"] != "DEPROVISIONED"]
    try:
        records = [
            r
            for r in records
            if _matches(r, arguments.get("search"), "search")
            and _matches(r, arguments.get("filter"), "filter")
        ]
    except ValueError as error:
        return _error(str(error), listed=False)
    q = arguments.get("q")
    if q:
        query = q.casefold()
        records = [
            r
            for r in records
            if query in json.dumps(r["profile"], sort_keys=True).casefold()
        ]
    items = [[r["profile"], r["id"]] for r in records]
    result, error = _page(
        items,
        kind="users",
        query=(arguments.get("search", ""), arguments.get("filter"), q),
        after=arguments.get("after"),
        limit=arguments.get("limit"),
        fetch_all=arguments.get("fetch_all", False),
        minimum=20,
        maximum=200,
        max_pages=10,
        fetch_all_size=200,
    )
    if error:
        return _error(error, listed=False)
    assert result is not None
    if arguments.get("fetch_all") and arguments.get("after"):
        result["pagination_note"] = (
            "fetch_all resumed from the provided cursor; total_fetched counts only users from that cursor onwards"
        )
    if result.get("pagination_info", {}).get("stopped_early"):
        result["warning"] = (
            "fetch_all stopped early; at least the returned users were found and the result is incomplete"
        )
    return result, False


def get_user_profile_attributes(db, arguments, step, clock):
    if denied := _scope(db, "okta.users.read", listed=True):
        return denied
    row = db.connection.execute(
        "SELECT * FROM okta_users ORDER BY id LIMIT 1"
    ).fetchone()
    return ([] if row is None else _profile(row)), False


def create_user(db, arguments, step, clock):
    if denied := _scope(db, "okta.users.manage", listed=True):
        return denied
    profile = arguments["profile"]
    login, email = profile.get("login"), profile.get("email")
    if (
        not isinstance(login, str)
        or not login
        or not isinstance(email, str)
        or not email
    ):
        return _error("profile.login and profile.email are required")
    user_id = _next_id(db, "okta_users", "00u-sim-")
    extras = {k: v for k, v in profile.items() if k not in PROFILE_COLUMNS}
    try:
        db.connection.execute(
            "INSERT INTO okta_users VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                login,
                email,
                profile.get("firstName", ""),
                profile.get("lastName", ""),
                "ACTIVE" if arguments.get("activate", True) else "STAGED",
                json.dumps(extras),
            ),
        )
    except sqlite3.IntegrityError:
        return _error("A user with that login or email already exists")
    db.record(step, clock, "create", "okta", user_id)
    return [_user(_find_user(db, user_id))], False


def update_user(db, arguments, step, clock):
    if denied := _scope(db, "okta.users.manage", listed=True):
        return denied
    if invalid := _valid(arguments["user_id"], "user_id"):
        return invalid
    row = _find_user(db, arguments["user_id"])
    if row is None:
        return _error("User not found")
    profile = _profile(row) | arguments["profile"]
    extras = {k: v for k, v in profile.items() if k not in PROFILE_COLUMNS}
    try:
        db.connection.execute(
            "UPDATE okta_users SET login=?, email=?, first_name=?, last_name=?, profile_json=? WHERE id=?",
            (
                profile["login"],
                profile["email"],
                profile.get("firstName", ""),
                profile.get("lastName", ""),
                json.dumps(extras),
                row["id"],
            ),
        )
    except sqlite3.IntegrityError:
        return _error("A user with that login or email already exists")
    db.record(step, clock, "update", "okta", row["id"])
    return [_user(_find_user(db, row["id"]))], False


def deactivate_user(db, arguments, step, clock):
    if denied := _scope(db, "okta.users.manage", listed=True):
        return denied
    if invalid := _valid(arguments["user_id"], "user_id"):
        return invalid
    row = _find_user(db, arguments["user_id"])
    if row is None:
        return _error("User not found")
    if row["status"] == "DEPROVISIONED":
        return _error("User is already deactivated")
    db.connection.execute(
        "UPDATE okta_users SET status='DEPROVISIONED' WHERE id=?", (row["id"],)
    )
    db.record(step, clock, "update", "okta", row["id"])
    return [{"message": f"User {row['id']} deactivated successfully."}], False


def delete_deactivated_user(db, arguments, step, clock):
    if denied := _scope(db, "okta.users.manage", listed=True):
        return denied
    if invalid := _valid(arguments["user_id"], "user_id"):
        return invalid
    row = _find_user(db, arguments["user_id"])
    if row is None:
        return _error("User not found")
    if row["status"] != "DEPROVISIONED":
        return _error("User must be deactivated before deletion")
    db.connection.execute("DELETE FROM okta_users WHERE id=?", (row["id"],))
    db.record(step, clock, "delete", "okta", row["id"])
    return [{"message": f"User {row['id']} deleted successfully."}], False


CSV_FIELDS = [
    "id",
    "status",
    "login",
    "email",
    "firstName",
    "lastName",
    "displayName",
    "mobilePhone",
    "primaryPhone",
    "department",
    "title",
    "organization",
    "userType",
    "employeeNumber",
    "costCenter",
    "division",
    "manager",
]


def export_users_csv(db, arguments, step, clock):
    output_path = arguments.get("output_path", "/tmp/okta_users_export.csv")
    path = PurePosixPath(output_path)
    if (
        not output_path.startswith("/tmp/")
        or path.parent != PurePosixPath("/tmp")
        or path.name in {"", ".", ".."}
        or not re.fullmatch(r"[A-Za-z0-9_.-]+\.csv", path.name)
    ):
        return _error(
            "output_path must be a traversal-free CSV filename directly under /tmp",
            listed=False,
        )
    list_args = {
        "search": arguments.get("search", ""),
        "filter": arguments.get("filter"),
        "q": arguments.get("q"),
        "fetch_all": True,
    }
    # Export intentionally has no simulated decorator scope, matching the selected wrapper.
    rows = db.connection.execute(
        "SELECT * FROM okta_users WHERE status != 'DEPROVISIONED' ORDER BY id"
    ).fetchall()
    records = [_user(row) for row in rows]
    try:
        records = [
            r
            for r in records
            if _matches(r, list_args["search"], "search")
            and _matches(r, list_args["filter"], "filter")
        ]
    except ValueError as error:
        return _error(str(error), listed=False)
    if list_args["q"]:
        records = [
            r
            for r in records
            if list_args["q"].casefold() in json.dumps(r["profile"]).casefold()
        ]
    if not records:
        return {"output_path": output_path, "total_users": 0, "pages_fetched": 1}, False
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for record in records:
        writer.writerow(
            {key: record.get(key, record["profile"].get(key, "")) for key in CSV_FIELDS}
        )
    content = stream.getvalue().encode()
    if len(content) > 1048576:
        return _error("CSV artifact exceeds the 1 MiB episode limit", listed=False)
    db.connection.execute(
        "INSERT OR REPLACE INTO episode_artifacts VALUES (?, ?, ?, ?, ?)",
        (path.name, content, "text/csv; charset=utf-8", step, clock),
    )
    db.record(step, clock, "artifact", "okta", path.name)
    return {
        "output_path": output_path,
        "total_users": len(records),
        "pages_fetched": 1,
        "stopped_early": False,
        "stop_reason": None,
    }, False


def list_groups(db, arguments, step, clock):
    if denied := _scope(db, "okta.groups.read", listed=False):
        return denied
    records = [
        _group(row)
        for row in db.connection.execute("SELECT * FROM okta_groups ORDER BY id")
    ]
    try:
        records = [
            r
            for r in records
            if _matches(r, arguments.get("search"), "search")
            and _matches(r, arguments.get("filter"), "filter")
        ]
    except ValueError as error:
        return _error(str(error), listed=False)
    q = arguments.get("q")
    if q:
        records = [
            r for r in records if q.casefold() in json.dumps(r["profile"]).casefold()
        ]
    result, error = _page(
        records,
        kind="groups",
        query=(arguments.get("search", ""), arguments.get("filter"), q),
        after=arguments.get("after"),
        limit=arguments.get("limit"),
        fetch_all=arguments.get("fetch_all", False),
        minimum=20,
        maximum=100,
        max_pages=500,
    )
    return _error(error, listed=False) if error else (result, False)


def get_group(db, arguments, step, clock):
    if denied := _scope(db, "okta.groups.read", listed=True):
        return denied
    if invalid := _valid(arguments["group_id"], "group_id"):
        return invalid
    row = db.connection.execute(
        "SELECT * FROM okta_groups WHERE id=?", (arguments["group_id"],)
    ).fetchone()
    return _error("Group not found") if row is None else ([_group(row)], False)


def create_group(db, arguments, step, clock):
    if denied := _scope(db, "okta.groups.manage", listed=True):
        return denied
    profile = arguments["profile"]
    if not isinstance(profile.get("name"), str) or not profile["name"]:
        return _error("profile.name is required")
    group_id = _next_id(db, "okta_groups", "00g-sim-")
    db.connection.execute(
        "INSERT INTO okta_groups VALUES (?, ?)", (group_id, json.dumps(profile))
    )
    db.record(step, clock, "create", "okta", group_id)
    return [{"id": group_id, "profile": profile}], False


def delete_group(db, arguments, step, clock):
    if denied := _scope(db, "okta.groups.manage", listed=True):
        return denied
    if invalid := _valid(arguments["group_id"], "group_id"):
        return invalid
    if (
        db.connection.execute(
            "SELECT 1 FROM okta_groups WHERE id=?", (arguments["group_id"],)
        ).fetchone()
        is None
    ):
        return _error("Group not found")
    return [
        {
            "confirmation_required": True,
            "group_id": arguments["group_id"],
            "tool_to_use": "confirm_delete_group",
            "message": "Explicit human confirmation is required; call confirm_delete_group with confirmation exactly DELETE.",
        }
    ], False


def confirm_delete_group(db, arguments, step, clock):
    if denied := _scope(db, "okta.groups.manage", listed=True):
        return denied
    if invalid := _valid(arguments["group_id"], "group_id"):
        return invalid
    if arguments["confirmation"] != "DELETE":
        return _error("Confirmation must be exactly DELETE")
    if (
        db.connection.execute(
            "SELECT 1 FROM okta_groups WHERE id=?", (arguments["group_id"],)
        ).fetchone()
        is None
    ):
        return _error("Group not found")
    db.connection.execute(
        "DELETE FROM okta_groups WHERE id=?", (arguments["group_id"],)
    )
    db.record(step, clock, "delete", "okta", arguments["group_id"])
    return [{"message": f"Group {arguments['group_id']} deleted successfully."}], False


def update_group(db, arguments, step, clock):
    if denied := _scope(db, "okta.groups.manage", listed=True):
        return denied
    if invalid := _valid(arguments["group_id"], "group_id"):
        return invalid
    if (
        db.connection.execute(
            "SELECT 1 FROM okta_groups WHERE id=?", (arguments["group_id"],)
        ).fetchone()
        is None
    ):
        return _error("Group not found")
    profile = arguments["profile"]
    if not isinstance(profile.get("name"), str) or not profile["name"]:
        return _error("replacement profile.name is required")
    db.connection.execute(
        "UPDATE okta_groups SET profile_json=? WHERE id=?",
        (json.dumps(profile), arguments["group_id"]),
    )
    db.record(step, clock, "update", "okta", arguments["group_id"])
    return [{"id": arguments["group_id"], "profile": profile}], False


def _list_group_records(
    db, arguments, table, converter, maximum, minimum: int | None = 20
):
    if denied := _scope(db, "okta.groups.read", listed=False):
        return denied
    if _valid(arguments["group_id"], "group_id"):
        return _error(
            "Invalid group_id: expected an Okta ID without traversal or URL-reserved characters",
            listed=False,
        )
    if (
        db.connection.execute(
            "SELECT 1 FROM okta_groups WHERE id=?", (arguments["group_id"],)
        ).fetchone()
        is None
    ):
        return _error("Group not found", listed=False)
    rows = db.connection.execute(
        f"SELECT * FROM {table} WHERE group_id=? ORDER BY 2", (arguments["group_id"],)
    ).fetchall()
    records = [converter(row) for row in rows]
    result, error = _page(
        records,
        kind=table,
        query=(arguments["group_id"],),
        after=arguments.get("after"),
        limit=arguments.get("limit"),
        fetch_all=arguments.get("fetch_all", False),
        minimum=minimum,
        maximum=maximum,
        max_pages=500,
        fetch_all_size=200 if table == "okta_group_apps" else None,
    )
    return _error(error, listed=False) if error else (result, False)


def list_group_users(db, arguments, step, clock):
    return _list_group_records(
        db,
        arguments,
        "okta_group_memberships",
        lambda row: _user(_find_user(db, row["user_id"])),
        100,
    )


def list_group_apps(db, arguments, step, clock):
    from .okta_store import get

    return _list_group_records(
        db,
        arguments,
        "okta_group_apps",
        lambda row: get(db, "okta_applications", row["app_id"]),
        200,
        None,
    )


def add_user_to_group(db, arguments, step, clock):
    if denied := _scope(db, "okta.groups.manage", listed=True):
        return denied
    for label in ("group_id", "user_id"):
        if invalid := _valid(arguments[label], label):
            return invalid
    if (
        db.connection.execute(
            "SELECT 1 FROM okta_groups WHERE id=?", (arguments["group_id"],)
        ).fetchone()
        is None
    ):
        return _error("Group not found")
    user = _find_user(db, arguments["user_id"])
    if user is None:
        return _error("User not found")
    existing = db.connection.execute(
        "SELECT 1 FROM okta_group_memberships WHERE group_id=? AND user_id=?",
        (arguments["group_id"], user["id"]),
    ).fetchone()
    if existing:
        return [
            {
                "message": f"User {user['id']} is already a member of group {arguments['group_id']}."
            }
        ], False
    db.connection.execute(
        "INSERT INTO okta_group_memberships VALUES (?, ?)",
        (arguments["group_id"], user["id"]),
    )
    db.record(step, clock, "membership_add", "okta", user["id"], arguments["group_id"])
    return [
        {
            "message": f"User {user['id']} added to group {arguments['group_id']} successfully."
        }
    ], False


def remove_user_from_group(db, arguments, step, clock):
    if denied := _scope(db, "okta.groups.manage", listed=True):
        return denied
    for label in ("group_id", "user_id"):
        if invalid := _valid(arguments[label], label):
            return invalid
    user = _find_user(db, arguments["user_id"])
    if user is None:
        return _error("User not found")
    deleted = db.connection.execute(
        "DELETE FROM okta_group_memberships WHERE group_id=? AND user_id=?",
        (arguments["group_id"], user["id"]),
    )
    if not deleted.rowcount:
        return _error("User is not a member of the group")
    db.record(
        step, clock, "membership_remove", "okta", user["id"], arguments["group_id"]
    )
    return [
        {
            "message": f"User {user['id']} removed from group {arguments['group_id']} successfully."
        }
    ], False


def list_user_groups(db, arguments, step, clock):
    if denied := _scope(db, "okta.users.read", listed=True):
        return denied
    if invalid := _valid(arguments["user_id"], "user_id"):
        return invalid
    user = _find_user(db, arguments["user_id"])
    if user is None:
        return _error("User not found")
    rows = db.connection.execute(
        "SELECT g.* FROM okta_groups g JOIN okta_group_memberships m ON m.group_id=g.id WHERE m.user_id=? ORDER BY g.id",
        (user["id"],),
    ).fetchall()
    return [_group(row) for row in rows], False
