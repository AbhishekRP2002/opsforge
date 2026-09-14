"""Workflow and activity operations from the pinned unwrapped handlers."""

from . import servicenow_store as store


def _attribute_error(data):
    for field in (
        "name",
        "table",
        "description",
        "activity_type",
        "workflow_version",
        "sys_created_on",
    ):
        if field in data and not isinstance(data[field], str):
            return f"simulation_profile: {field} must be text"
    if "active" in data and not (
        isinstance(data["active"], bool) or data["active"] in ("true", "false")
    ):
        return "simulation_profile: active must be a boolean or boolean string"
    if "order" in data and (
        isinstance(data["order"], bool) or not isinstance(data["order"], (int, str))
    ):
        return "simulation_profile: order must be an integer or integer string"
    if "order" in data:
        try:
            int(data["order"])
        except ValueError:
            return "simulation_profile: order must be an integer or integer string"
    return None


def _error(message):
    return {"error": message}, False


def list_workflows(db, arguments, step, clock):
    rows = store.all_rows(db, "wf_workflow")
    if arguments["name"]:
        rows = [
            row
            for row in rows
            if arguments["name"].casefold() in row.get("name", "").casefold()
        ]
    rows, total, error = store.page(rows, arguments, ("active",))
    if error:
        return _error(error)
    return {"workflows": rows, "count": len(rows), "total": total}, False


def get_workflow_details(db, arguments, step, clock):
    row = store.get(db, "wf_workflow", arguments["workflow_id"])
    return (
        ({"workflow": row}, False)
        if row
        else _error("simulation_profile: workflow not found")
    )


def list_workflow_versions(db, arguments, step, clock):
    key = arguments["workflow_id"]
    if not key:
        return _error("Workflow ID is required")
    rows = [
        row
        for row in store.all_rows(db, "wf_workflow_version")
        if row.get("workflow") == key
    ]
    rows, total, error = store.page(rows, arguments)
    if error:
        return _error(error)
    return {
        "versions": rows,
        "count": len(rows),
        "total": total,
        "workflow_id": key,
    }, False


def get_workflow_activities(db, arguments, step, clock):
    key = arguments["workflow_id"]
    if not key:
        return _error("Workflow ID is required")
    version = arguments["version"]
    if not version:
        versions = [
            row
            for row in store.all_rows(db, "wf_workflow_version")
            if row.get("workflow") == key
            and str(row.get("published")).lower() == "true"
        ]
        versions.sort(key=lambda row: int(row.get("version", 0)), reverse=True)
        if not versions:
            return {
                "error": f"No published versions found for workflow {key}",
                "workflow_id": key,
            }, False
        version = versions[0]["sys_id"]
    elif store.get(db, "wf_workflow_version", version) is None:
        return _error("simulation_profile: workflow version not found")
    rows = [
        row
        for row in store.all_rows(db, "wf_activity")
        if row.get("workflow_version") == version
    ]
    rows.sort(key=lambda row: int(row.get("order", 0)))
    return {
        "activities": rows,
        "count": len(rows),
        "workflow_id": key,
        "version_id": version,
    }, False


def _data(arguments, *, create=False):
    data = {
        key: arguments[key]
        for key in ("name", "table", "activity_type")
        if arguments.get(key)
    }
    if arguments.get("description") is not None and (
        not create or arguments["description"]
    ):
        data["description"] = arguments["description"]
    if arguments.get("active") is not None:
        data["active"] = str(arguments["active"]).lower()
    return data | (arguments.get("attributes") or {})


def create_workflow(db, arguments, step, clock):
    if not arguments["name"]:
        return _error("Workflow name is required")
    data = _data(arguments, create=True)
    if error := _attribute_error(data):
        return _error(error)
    if "sys_id" in data:
        return _error("simulation_profile: generated sys_id cannot be overridden")
    return {
        "workflow": store.insert(db, "wf_workflow", data, step, clock),
        "message": "Workflow created successfully",
    }, False


def _update(db, table, key, data, step, clock, entity, message):
    if error := _attribute_error(data):
        return _error(error)
    if not data:
        return _error("No update parameters provided")
    if "sys_id" in data:
        return _error("simulation_profile: generated sys_id cannot be overridden")
    row = store.get(db, table, key)
    if row is None:
        return _error(f"simulation_profile: {entity} not found")
    if error := store.reference_error(
        db,
        data,
        {"workflow_version": "wf_workflow_version"},
        required=("workflow_version",)
        if table == "wf_activity" and "workflow_version" in data
        else (),
    ):
        return _error(error)
    return {
        entity: store.update(db, table, row, data, step, clock),
        "message": message,
    }, False


def update_workflow(db, arguments, step, clock):
    return _update(
        db,
        "wf_workflow",
        arguments["workflow_id"],
        _data(arguments),
        step,
        clock,
        "workflow",
        "Workflow updated successfully",
    )


def activate_workflow(db, arguments, step, clock):
    return _update(
        db,
        "wf_workflow",
        arguments["workflow_id"],
        {"active": "true"},
        step,
        clock,
        "workflow",
        "Workflow activated successfully",
    )


def deactivate_workflow(db, arguments, step, clock):
    return _update(
        db,
        "wf_workflow",
        arguments["workflow_id"],
        {"active": "false"},
        step,
        clock,
        "workflow",
        "Workflow deactivated successfully",
    )


def add_workflow_activity(db, arguments, step, clock):
    if not arguments["workflow_version_id"]:
        return _error("Workflow version ID is required")
    if not arguments["name"]:
        return _error("Activity name is required")
    data = {"workflow_version": arguments["workflow_version_id"]} | _data(
        arguments, create=True
    )
    if error := _attribute_error(data):
        return _error(error)
    if "sys_id" in data:
        return _error("simulation_profile: generated sys_id cannot be overridden")
    if error := store.reference_error(
        db,
        data,
        {"workflow_version": "wf_workflow_version"},
        required=("workflow_version",),
    ):
        return _error(error)
    return {
        "activity": store.insert(db, "wf_activity", data, step, clock),
        "message": "Workflow activity added successfully",
    }, False


def update_workflow_activity(db, arguments, step, clock):
    return _update(
        db,
        "wf_activity",
        arguments["activity_id"],
        _data(arguments),
        step,
        clock,
        "activity",
        "Activity updated successfully",
    )


def delete_workflow_activity(db, arguments, step, clock):
    key = arguments["activity_id"]
    if store.get(db, "wf_activity", key) is None:
        return _error("simulation_profile: activity not found")
    store.delete(db, "wf_activity", key, step, clock)
    return {"message": "Activity deleted successfully", "activity_id": key}, False


def reorder_workflow_activities(db, arguments, step, clock):
    if not arguments["workflow_id"]:
        return _error("Workflow ID is required")
    if not arguments["activity_ids"]:
        return _error("Activity IDs are required")
    results = []
    for index, key in enumerate(arguments["activity_ids"]):
        row = store.get(db, "wf_activity", key)
        if row is None:
            results.append(
                {
                    "activity_id": key,
                    "error": "simulation_profile: activity not found",
                    "success": False,
                }
            )
            continue
        order = (index + 1) * 100
        store.update(db, "wf_activity", row, {"order": order}, step, clock)
        results.append({"activity_id": key, "new_order": order, "success": True})
    return {
        "message": "Activities reordered",
        "workflow_id": arguments["workflow_id"],
        "results": results,
    }, False


HANDLERS = {
    "list_workflows": list_workflows,
    "get_workflow_details": get_workflow_details,
    "list_workflow_versions": list_workflow_versions,
    "get_workflow_activities": get_workflow_activities,
    "create_workflow": create_workflow,
    "update_workflow": update_workflow,
    "activate_workflow": activate_workflow,
    "deactivate_workflow": deactivate_workflow,
    "add_workflow_activity": add_workflow_activity,
    "update_workflow_activity": update_workflow_activity,
    "delete_workflow_activity": delete_workflow_activity,
    "reorder_workflow_activities": reorder_workflow_activities,
}
