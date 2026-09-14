"""Source-derived ServiceNow behavior; modeled business failures keep prior effects."""

from ..storage.database import Database


def lookup(db: Database, arguments: dict):
    for key, column in (
        ("user_id", "sys_id"),
        ("user_name", "user_name"),
        ("email", "email"),
    ):
        if arguments.get(key):
            return db.connection.execute(
                f"SELECT * FROM servicenow_users WHERE {column} = ?", (arguments[key],)
            ).fetchone()
    return None


def get_user(db: Database, arguments: dict, step: int, clock: int) -> tuple[dict, bool]:
    if not any(arguments.get(key) for key in ("user_id", "user_name", "email")):
        return {
            "success": False,
            "message": "At least one search parameter is required",
        }, False
    row = lookup(db, arguments)
    if row is None:
        return {"success": False, "message": "User not found"}, False
    db.record(step, clock, "read", "servicenow", row["sys_id"])
    user = dict(row)
    from .servicenow_users import profile

    user.update(profile(db, "sys_user", row["sys_id"]))
    user["active"] = "true" if user["active"] else "false"
    return {"success": True, "message": "User found", "user": user}, False


def add_group_members(
    db: Database, arguments: dict, step: int, clock: int
) -> tuple[dict, bool]:
    group_id = arguments["group_id"]
    failed = []
    for member in arguments["members"]:
        user_id = member
        if not member.startswith("sys_id:"):
            user = lookup(db, {"user_name": member})
            if user is None:
                user = lookup(db, {"email": member})
            if user is None:
                failed.append(member)
                continue
            user_id = user["sys_id"]
        # Explicit modeled reference failure; unexpected SQLite errors must propagate.
        user_exists = db.connection.execute(
            "SELECT 1 FROM servicenow_users WHERE sys_id = ?", (user_id,)
        ).fetchone()
        group_exists = db.connection.execute(
            "SELECT 1 FROM servicenow_groups WHERE sys_id = ? AND available = 1",
            (group_id,),
        ).fetchone()
        if user_exists is None or group_exists is None:
            failed.append(member)
            continue
        from .servicenow_store import identifier

        membership_id = identifier(db, "sys_user_grmember")
        db.connection.execute(
            "INSERT INTO servicenow_memberships VALUES (?, ?, ?)",
            (membership_id, user_id, group_id),
        )
        db.record(step, clock, "membership_added", "servicenow", user_id, group_id)
    message = (
        f"Some members could not be added to the group: {', '.join(failed)}"
        if failed
        else "All members added to the group successfully"
    )
    return {
        "success": not failed,
        "message": message,
        "group_id": group_id,
        "group_name": None,
    }, False
