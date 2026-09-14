"""Update sets and inert file payloads, with source-coded state writes."""

from . import servicenow_store as store


def list_changesets(db, arguments, step, clock):
    query = "^".join(
        value
        for value in (store.DATE_MACROS.get(arguments["timeframe"]), arguments["query"])
        if value
    )
    rows, _, error = store.page(
        store.all_rows(db, "sys_update_set"),
        arguments | {"query": query, "timeframe": None},
        ("state", "application", "developer"),
        clock=clock,
    )
    if error:
        return store.failure(error)
    return {"success": True, "changesets": rows, "count": len(rows)}, False


def get_changeset_details(db, arguments, step, clock):
    key = arguments["changeset_id"]
    row = store.get(db, "sys_update_set", key)
    if row is None:
        return store.failure("simulation_profile: changeset not found")
    changes = [
        item
        for item in store.all_rows(db, "sys_update_xml")
        if item.get("update_set") == key
    ]
    return {
        "success": True,
        "changeset": row,
        "changes": changes,
        "change_count": len(changes),
    }, False


def create_changeset(db, arguments, step, clock):
    data = {
        "name": arguments["name"],
        "application": arguments["application"],
    } | store.fields(arguments, ("name", "application"), truthy=True)
    if error := store.reference_error(
        db,
        data,
        {"application": "sys_scope", "developer": "sys_user"},
        required=("application",),
    ):
        return store.failure(error)
    return {
        "success": True,
        "message": "Changeset created successfully",
        "changeset": store.insert(db, "sys_update_set", data, step, clock),
    }, False


def _update(db, key, data, step, clock, verb):
    if not data:
        return store.failure("No fields to update")
    row = store.get(db, "sys_update_set", key)
    if row is None:
        return store.failure("simulation_profile: changeset not found")
    if error := store.reference_error(db, data, {"developer": "sys_user"}):
        return store.failure(error)
    return {
        "success": True,
        "message": f"Changeset {verb} successfully",
        "changeset": store.update(db, "sys_update_set", row, data, step, clock),
    }, False


def update_changeset(db, arguments, step, clock):
    return _update(
        db,
        arguments["changeset_id"],
        store.fields(arguments, ("changeset_id",), truthy=True),
        step,
        clock,
        "updated",
    )


def commit_changeset(db, arguments, step, clock):
    data = {"state": "complete"}
    if arguments["commit_message"]:
        data["description"] = arguments["commit_message"]
    return _update(db, arguments["changeset_id"], data, step, clock, "committed")


def publish_changeset(db, arguments, step, clock):
    data = {"state": "published"}
    if arguments["publish_notes"]:
        data["description"] = arguments["publish_notes"]
    return _update(db, arguments["changeset_id"], data, step, clock, "published")


def add_file_to_changeset(db, arguments, step, clock):
    if store.get(db, "sys_update_set", arguments["changeset_id"]) is None:
        return store.failure("simulation_profile: changeset not found")
    if len(arguments["file_content"].encode()) > 1_048_576:
        return store.failure("simulation_profile: opaque file exceeds 1 MiB")
    data = {
        "update_set": arguments["changeset_id"],
        "name": arguments["file_path"],
        "payload": arguments["file_content"],
        "type": "file",
    }
    return {
        "success": True,
        "message": "File added to changeset successfully",
        "file": store.insert(db, "sys_update_xml", data, step, clock),
    }, False


HANDLERS = {
    "list_changesets": list_changesets,
    "get_changeset_details": get_changeset_details,
    "create_changeset": create_changeset,
    "update_changeset": update_changeset,
    "commit_changeset": commit_changeset,
    "publish_changeset": publish_changeset,
    "add_file_to_changeset": add_file_to_changeset,
}
