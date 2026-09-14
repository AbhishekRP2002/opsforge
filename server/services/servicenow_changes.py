"""Change requests, tasks, and non-atomic approval operations."""

from . import servicenow_store as store


def create_change_request(db, arguments, step, clock):
    data = {
        "short_description": arguments["short_description"],
        "type": arguments["type"],
    } | store.fields(arguments, ("short_description", "type"), truthy=True)
    if error := store.reference_error(
        db, data, {"requested_by": "sys_user", "assignment_group": "sys_user_group"}
    ):
        return store.failure(error)
    return {
        "success": True,
        "message": "Change request created successfully",
        "change_request": store.insert(db, "change_request", data, step, clock, "CHG"),
    }, False


def update_change_request(db, arguments, step, clock):
    if error := store.denied(db, "change_request.update", arguments["change_id"]):
        return store.failure(error)
    row = store.get(db, "change_request", arguments["change_id"])
    if row is None:
        return store.failure("simulation_profile: change request not found")
    data = store.fields(arguments, ("change_id",), truthy=True)
    if error := store.reference_error(db, data, {"assignment_group": "sys_user_group"}):
        return store.failure(error)
    return {
        "success": True,
        "message": "Change request updated successfully",
        "change_request": store.update(db, "change_request", row, data, step, clock),
    }, False


def list_change_requests(db, arguments, step, clock):
    rows, _, error = store.page(
        store.all_rows(db, "change_request"),
        arguments,
        ("state", "type", "category", "assignment_group"),
        clock=clock,
    )
    if error:
        return store.failure(error)
    return {
        "success": True,
        "change_requests": rows,
        "count": len(rows),
        "total": len(rows),
    }, False


def get_change_request_details(db, arguments, step, clock):
    key = arguments["change_id"]
    row = store.get(db, "change_request", key)
    if row is None:
        return store.failure("simulation_profile: change request not found")
    tasks = [
        item
        for item in store.all_rows(db, "change_task")
        if item.get("change_request") == key
    ]
    return {"success": True, "change_request": row, "tasks": tasks}, False


def add_change_task(db, arguments, step, clock):
    data = {
        "change_request": arguments["change_id"],
        "short_description": arguments["short_description"],
    } | store.fields(arguments, ("change_id", "short_description"), truthy=True)
    if error := store.reference_error(
        db,
        data,
        {"change_request": "change_request", "assigned_to": "sys_user"},
        required=("change_request",),
    ):
        return store.failure(error)
    return {
        "success": True,
        "message": "Change task added successfully",
        "change_task": store.insert(db, "change_task", data, step, clock, "CTASK"),
    }, False


def submit_change_for_approval(db, arguments, step, clock):
    key = arguments["change_id"]
    if error := store.denied(db, "change_request.update", key):
        return store.failure(error)
    row = store.get(db, "change_request", key)
    if row is None:
        return store.failure("simulation_profile: change request not found")
    data = {"state": "assess"}
    if arguments["approval_comments"]:
        data["work_notes"] = arguments["approval_comments"]
    store.update(db, "change_request", row, data, step, clock)
    if error := store.denied(db, "sysapproval_approver.create", key):
        return store.failure(error)
    approval = store.insert(
        db,
        "sysapproval_approver",
        {"document_id": key, "source_table": "change_request", "state": "requested"},
        step,
        clock,
    )
    return {
        "success": True,
        "message": "Change request submitted for approval successfully",
        "approval": approval,
    }, False


def _decide(db, key, approval_data, change_data, step, clock, verb):
    approval = next(
        (
            row
            for row in store.all_rows(db, "sysapproval_approver")
            if row.get("document_id") == key
        ),
        None,
    )
    if approval is None:
        return store.failure("No approval record found for this change request")
    store.update(db, "sysapproval_approver", approval, approval_data, step, clock)
    if error := store.denied(db, "change_request.update", key):
        return store.failure(error)
    row = store.get(db, "change_request", key)
    if row is None:
        return store.failure("simulation_profile: change request not found")
    store.update(db, "change_request", row, change_data, step, clock)
    return {"success": True, "message": f"Change request {verb} successfully"}, False


def approve_change(db, arguments, step, clock):
    data = {"state": "approved"}
    if arguments["approval_comments"]:
        data["comments"] = arguments["approval_comments"]
    return _decide(
        db,
        arguments["change_id"],
        data,
        {"state": "implement"},
        step,
        clock,
        "approved",
    )


def reject_change(db, arguments, step, clock):
    reason = arguments["rejection_reason"]
    return _decide(
        db,
        arguments["change_id"],
        {"state": "rejected", "comments": reason},
        {"state": "canceled", "work_notes": f"Change request rejected: {reason}"},
        step,
        clock,
        "rejected",
    )


HANDLERS = {
    "create_change_request": create_change_request,
    "update_change_request": update_change_request,
    "list_change_requests": list_change_requests,
    "get_change_request_details": get_change_request_details,
    "add_change_task": add_change_task,
    "submit_change_for_approval": submit_change_for_approval,
    "approve_change": approve_change,
    "reject_change": reject_change,
}
