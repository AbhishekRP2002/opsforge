"""Incident table behavior from the pinned ServiceNow handlers."""

import re

from . import servicenow_store as store


def _find(db, identifier):
    if re.fullmatch(r"[0-9a-f]{32}", identifier):
        return store.get(db, "incident", identifier)
    return next(
        (
            row
            for row in store.all_rows(db, "incident")
            if row.get("number") == identifier
        ),
        None,
    )


def _response(row, message):
    return {
        "success": True,
        "message": message,
        "incident_id": row["sys_id"],
        "incident_number": row["number"],
    }, False


def _failure(message):
    return store.failure(message, incident_id=None, incident_number=None)


def create_incident(db, arguments, step, clock):
    data = {"short_description": arguments["short_description"]} | store.fields(
        arguments, ("short_description",), truthy=True
    )
    if error := store.reference_error(
        db, data, store.ASSIGNMENT_REFS | {"caller_id": "sys_user"}
    ):
        return _failure(error)
    return _response(
        store.insert(db, "incident", data, step, clock, "INC"),
        "Incident created successfully",
    )


def _mutate(db, identifier, data, step, clock, message):
    row = _find(db, identifier)
    if row is None:
        return _failure(f"Incident not found: {identifier}")
    if error := store.reference_error(db, data, store.ASSIGNMENT_REFS):
        return _failure(error)
    return _response(store.update(db, "incident", row, data, step, clock), message)


def update_incident(db, arguments, step, clock):
    return _mutate(
        db,
        arguments["incident_id"],
        store.fields(arguments, ("incident_id",), truthy=True),
        step,
        clock,
        "Incident updated successfully",
    )


def add_comment(db, arguments, step, clock):
    return _mutate(
        db,
        arguments["incident_id"],
        {
            "work_notes" if arguments["is_work_note"] else "comments": arguments[
                "comment"
            ]
        },
        step,
        clock,
        "Comment added successfully",
    )


def resolve_incident(db, arguments, step, clock):
    return _mutate(
        db,
        arguments["incident_id"],
        {
            "state": "6",
            "close_code": arguments["resolution_code"],
            "close_notes": arguments["resolution_notes"],
            "resolved_at": store.timestamp(clock),
        },
        step,
        clock,
        "Incident resolved successfully",
    )


def _format(row):
    result = {
        key: row.get(key)
        for key in (
            "sys_id",
            "number",
            "short_description",
            "description",
            "state",
            "priority",
            "assigned_to",
            "category",
            "subcategory",
        )
    }
    result.update(
        created_on=row.get("sys_created_on"), updated_on=row.get("sys_updated_on")
    )
    return result


def list_incidents(db, arguments, step, clock):
    rows, _, error = store.page(
        store.all_rows(db, "incident"),
        arguments,
        ("state", "assigned_to", "category"),
        search_fields=("short_description", "description"),
    )
    if error:
        return store.failure(error, incidents=[])
    return {
        "success": True,
        "message": f"Found {len(rows)} incidents",
        "incidents": [_format(row) for row in rows],
    }, False


def get_incident_by_number(db, arguments, step, clock):
    number = arguments["incident_number"]
    row = next(
        (row for row in store.all_rows(db, "incident") if row.get("number") == number),
        None,
    )
    if row is None:
        return store.failure(f"Incident not found: {number}")
    return {
        "success": True,
        "message": f"Incident {number} found",
        "incident": _format(row),
    }, False


HANDLERS = {
    "create_incident": create_incident,
    "update_incident": update_incident,
    "add_comment": add_comment,
    "resolve_incident": resolve_incident,
    "list_incidents": list_incidents,
    "get_incident_by_number": get_incident_by_number,
}
