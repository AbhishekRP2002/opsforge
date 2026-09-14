"""Opaque script storage; ServiceNow code is never evaluated."""

from . import servicenow_store as store


def _find(db, key):
    if key.startswith("sys_id:"):
        return store.get(db, "sys_script_include", key.replace("sys_id:", ""))
    return next(
        (
            row
            for row in store.all_rows(db, "sys_script_include")
            if row.get("name") == key
        ),
        None,
    )


def _format(row, *, script=False):
    keys = (
        "sys_id",
        "name",
        "description",
        "api_name",
        "client_callable",
        "active",
        "access",
    )
    value = {key: row.get(key) for key in keys}
    for key in ("active", "client_callable"):
        value[key] = row.get(key) is True or row.get(key) == "true"
    value.update(
        created_on=row.get("sys_created_on"),
        updated_on=row.get("sys_updated_on"),
        created_by=None,
        updated_by=None,
    )
    if script:
        value["script"] = row.get("script")
    return value


def list_script_includes(db, arguments, step, clock):
    rows, _, error = store.page(
        store.all_rows(db, "sys_script_include"),
        arguments,
        ("active", "client_callable"),
        search_fields=("name",),
    )
    value = {
        "script_includes": [_format(row) for row in rows],
        "total": len(rows),
        "limit": arguments["limit"],
        "offset": arguments["offset"],
    }
    return {
        "success": not error,
        "message": error or f"Found {len(rows)} script includes",
        **value,
    }, False


def get_script_include(db, arguments, step, clock):
    row = _find(db, arguments["script_include_id"])
    if row is None:
        return store.failure(
            f"Script include not found: {arguments['script_include_id']}"
        )
    return {
        "success": True,
        "message": f"Found script include: {row['name']}",
        "script_include": _format(row, script=True),
    }, False


def _result(row, verb):
    return {
        "success": True,
        "message": f"{verb} script include: {row['name']}",
        "script_include_id": row["sys_id"],
        "script_include_name": row["name"],
    }, False


def _failure(message):
    return store.failure(message, script_include_id=None, script_include_name=None)


def create_script_include(db, arguments, step, clock):
    if len(arguments["script"].encode()) > 1_048_576:
        return _failure("simulation_profile: opaque script exceeds 1 MiB")
    data = store.fields(arguments)
    row = store.insert(db, "sys_script_include", data, step, clock)
    return _result(row, "Created")


def update_script_include(db, arguments, step, clock):
    row = _find(db, arguments["script_include_id"])
    if row is None:
        return _failure(f"Script include not found: {arguments['script_include_id']}")
    data = store.fields(arguments, ("script_include_id",))
    if len(data.get("script", "").encode()) > 1_048_576:
        return _failure("simulation_profile: opaque script exceeds 1 MiB")
    if not data:
        return _result(row, "No changes to update for")
    return _result(
        store.update(db, "sys_script_include", row, data, step, clock), "Updated"
    )


def delete_script_include(db, arguments, step, clock):
    row = _find(db, arguments["script_include_id"])
    if row is None:
        return _failure(f"Script include not found: {arguments['script_include_id']}")
    store.delete(db, "sys_script_include", row["sys_id"], step, clock)
    return _result(row, "Deleted")


HANDLERS = {
    "list_script_includes": list_script_includes,
    "get_script_include": get_script_include,
    "create_script_include": create_script_include,
    "update_script_include": update_script_include,
    "delete_script_include": delete_script_include,
}
