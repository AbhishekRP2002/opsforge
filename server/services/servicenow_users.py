"""User/group profiles and source-compatible secondary membership effects."""

import json

from . import servicenow as legacy
from . import servicenow_store as store


def profile(db, table, key):
    row = db.connection.execute(
        "SELECT data FROM servicenow_profiles WHERE table_name=? AND sys_id=?",
        (table, key),
    ).fetchone()
    return json.loads(row[0]) if row else {}


def _save_profile(db, table, key, data):
    value = profile(db, table, key) | data
    db.connection.execute(
        "INSERT INTO servicenow_profiles VALUES (?,?,?) ON CONFLICT(table_name,sys_id) DO UPDATE SET data=excluded.data",
        (table, key, json.dumps(value)),
    )


def _user_data(arguments):
    data = store.fields(arguments, ("user_id", "roles", "active"), truthy=True)
    if "password" in data:
        data["user_password"] = data.pop("password")
    if arguments.get("active") is not None:
        data["active"] = arguments["active"]
    return data


def _assign_roles(db, key, roles, step, clock):
    for name in roles or []:
        role = next(
            (
                row
                for row in store.all_rows(db, "sys_user_role")
                if row.get("name") == name
            ),
            None,
        )
        if role and not any(
            row.get("user") == key and row.get("role") == role["sys_id"]
            for row in store.all_rows(db, "sys_user_has_role")
        ):
            store.insert(
                db,
                "sys_user_has_role",
                {"user": key, "role": role["sys_id"]},
                step,
                clock,
            )


def _user_failure(message):
    return store.failure(message, user_id=None, user_name=None)


def create_user(db, arguments, step, clock):
    data = _user_data(arguments)
    if error := store.reference_error(
        db,
        data,
        {
            "manager": "sys_user",
            "department": "cmn_department",
            "location": "cmn_location",
        },
    ):
        return _user_failure(error)
    if db.connection.execute(
        "SELECT 1 FROM servicenow_users WHERE user_name=? OR email=?",
        (arguments["user_name"], arguments["email"]),
    ).fetchone():
        return _user_failure("simulation_profile: username or email already exists")
    key = store.identifier(db, "sys_user")
    while legacy.lookup(db, {"user_id": key}):
        key = store.identifier(db, "sys_user")
    db.connection.execute(
        "INSERT INTO servicenow_users VALUES (?,?,?,?,?)",
        (
            key,
            arguments["user_name"],
            arguments["email"],
            f"{arguments['first_name']} {arguments['last_name']}",
            bool(arguments["active"]),
        ),
    )
    _save_profile(
        db,
        "sys_user",
        key,
        {k: v for k, v in data.items() if k not in {"user_name", "email", "active"}},
    )
    db.record(step, clock, "created", "servicenow", key)
    _assign_roles(db, key, arguments["roles"], step, clock)
    return {
        "success": True,
        "message": "User created successfully",
        "user_id": key,
        "user_name": arguments["user_name"],
    }, False


def update_user(db, arguments, step, clock):
    key = arguments["user_id"]
    row = legacy.lookup(db, {"user_id": key})
    if row is None:
        return _user_failure("simulation_profile: user not found")
    data = _user_data(arguments)
    if error := store.reference_error(
        db,
        data,
        {
            "manager": "sys_user",
            "department": "cmn_department",
            "location": "cmn_location",
        },
    ):
        return _user_failure(error)
    public = dict(row) | profile(db, "sys_user", key) | data
    if db.connection.execute(
        "SELECT 1 FROM servicenow_users WHERE sys_id != ? AND (user_name=? OR email=?)",
        (key, public["user_name"], public["email"]),
    ).fetchone():
        return _user_failure("simulation_profile: username or email already exists")
    name = (
        f"{public.get('first_name', '')} {public.get('last_name', '')}".strip()
        if {"first_name", "last_name"} & data.keys()
        else row["name"]
    )
    db.connection.execute(
        "UPDATE servicenow_users SET user_name=?, email=?, name=?, active=? WHERE sys_id=?",
        (public["user_name"], public["email"], name, public["active"], key),
    )
    _save_profile(
        db,
        "sys_user",
        key,
        {k: v for k, v in data.items() if k not in {"user_name", "email", "active"}},
    )
    _assign_roles(db, key, arguments["roles"], step, clock)
    db.record(step, clock, "updated", "servicenow", key)
    return {
        "success": True,
        "message": "User updated successfully",
        "user_id": key,
        "user_name": public["user_name"],
    }, False


def list_users(db, arguments, step, clock):
    rows = [
        dict(row) | profile(db, "sys_user", row["sys_id"])
        for row in db.connection.execute(
            "SELECT * FROM servicenow_users ORDER BY rowid"
        )
    ]
    for row in rows:
        row["active"] = bool(row["active"])
    rows, _, error = store.page(
        rows,
        arguments,
        ("active", "department"),
        search_fields=("name", "user_name", "email"),
    )
    if error:
        return store.failure(error)
    for row in rows:
        row["active"] = "true" if row["active"] else "false"
    return {
        "success": True,
        "message": f"Found {len(rows)} users",
        "users": rows,
        "count": len(rows),
    }, False


def _group_failure(message):
    return store.failure(message, group_id=None, group_name=None)


def create_group(db, arguments, step, clock):
    data = store.fields(arguments, ("members", "active"), truthy=True) | {
        "active": arguments["active"]
    }
    if error := store.reference_error(
        db, data, {"manager": "sys_user", "parent": "sys_user_group"}
    ):
        return _group_failure(error)
    if db.connection.execute(
        "SELECT 1 FROM servicenow_groups WHERE name=?", (arguments["name"],)
    ).fetchone():
        return _group_failure("simulation_profile: group name already exists")
    key = store.identifier(db, "sys_user_group")
    while db.connection.execute(
        "SELECT 1 FROM servicenow_groups WHERE sys_id=?", (key,)
    ).fetchone():
        key = store.identifier(db, "sys_user_group")
    db.connection.execute(
        "INSERT INTO servicenow_groups VALUES (?,?,1)", (key, arguments["name"])
    )
    _save_profile(
        db, "sys_user_group", key, {k: v for k, v in data.items() if k != "name"}
    )
    db.record(step, clock, "created", "servicenow", key)
    if arguments["members"]:
        legacy.add_group_members(
            db, {"group_id": key, "members": arguments["members"]}, step, clock
        )
    return {
        "success": True,
        "message": "Group created successfully",
        "group_id": key,
        "group_name": arguments["name"],
    }, False


def update_group(db, arguments, step, clock):
    key = arguments["group_id"]
    row = db.connection.execute(
        "SELECT * FROM servicenow_groups WHERE sys_id=?", (key,)
    ).fetchone()
    if row is None:
        return _group_failure("simulation_profile: group not found")
    data = store.fields(arguments, ("group_id", "active"), truthy=True)
    if arguments["active"] is not None:
        data["active"] = arguments["active"]
    if error := store.reference_error(
        db, data, {"manager": "sys_user", "parent": "sys_user_group"}
    ):
        return _group_failure(error)
    name = data.get("name", row["name"])
    if db.connection.execute(
        "SELECT 1 FROM servicenow_groups WHERE name=? AND sys_id != ?", (name, key)
    ).fetchone():
        return _group_failure("simulation_profile: group name already exists")
    db.connection.execute(
        "UPDATE servicenow_groups SET name=? WHERE sys_id=?", (name, key)
    )
    _save_profile(
        db, "sys_user_group", key, {k: v for k, v in data.items() if k != "name"}
    )
    db.record(step, clock, "updated", "servicenow", key)
    return {
        "success": True,
        "message": "Group updated successfully",
        "group_id": key,
        "group_name": name,
    }, False


def list_groups(db, arguments, step, clock):
    rows = [
        {"sys_id": row["sys_id"], "name": row["name"], "active": True}
        | profile(db, "sys_user_group", row["sys_id"])
        for row in db.connection.execute(
            "SELECT * FROM servicenow_groups ORDER BY rowid"
        )
    ]
    rows, _, error = store.page(
        rows, arguments, ("active", "type"), search_fields=("name", "description")
    )
    if error:
        return store.failure(error)
    for row in rows:
        row["active"] = str(row["active"]).lower()
    return {
        "success": True,
        "message": f"Found {len(rows)} groups",
        "groups": rows,
        "count": len(rows),
    }, False


def remove_group_members(db, arguments, step, clock):
    failed = []
    group_id = arguments["group_id"]
    for member in arguments["members"]:
        key = member
        if not member.startswith("sys_id:"):
            user = legacy.lookup(db, {"user_name": member})
            if user is None:
                user = legacy.lookup(db, {"email": member})
            if user is None:
                failed.append(member)
                continue
            key = user["sys_id"]
        row = db.connection.execute(
            "SELECT sys_id FROM servicenow_memberships WHERE group_id=? AND user_id=? ORDER BY rowid LIMIT 1",
            (group_id, key),
        ).fetchone()
        if row is None:
            failed.append(member)
            continue
        db.connection.execute(
            "DELETE FROM servicenow_memberships WHERE sys_id=?", (row[0],)
        )
        db.record(step, clock, "membership_removed", "servicenow", key, group_id)
    message = (
        f"Some members could not be removed from the group: {', '.join(failed)}"
        if failed
        else "All members removed from the group successfully"
    )
    return {
        "success": not failed,
        "message": message,
        "group_id": group_id,
        "group_name": None,
    }, False


HANDLERS = {
    "create_user": create_user,
    "update_user": update_user,
    "list_users": list_users,
    "create_group": create_group,
    "update_group": update_group,
    "list_groups": list_groups,
    "remove_group_members": remove_group_members,
}
