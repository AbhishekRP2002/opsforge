"""Explicit employee-scoped forms, positions and calendar records."""

from . import darwinbox_store as store


@store.handler
def positions(db, arguments, step, clock):
    identifiers = store.employees(db, arguments["employee_nos"])
    status = store.number(arguments["status"], "status")
    hiring = store.choice(arguments["need_to_hire"], (0, 1), "need_to_hire")
    return [
        position
        for position in store.rows(db, "position")
        if position["employee_no"] in identifiers
        and position["status"] == status
        and position["need_to_hire"] == hiring
    ]


@store.handler
def forms(db, arguments, step, clock):
    low, high = store.span(arguments["from"], arguments["to"])
    selectors = {
        key: store.text(arguments[key], key) for key in ("form_id", "type", "form_type")
    }
    return [
        form
        for form in store.rows(db, "form")
        if all(form[key] == value for key, value in selectors.items())
        and low <= store.date(form["date"]) <= high
    ]


@store.handler
def holidays(db, arguments, step, clock):
    query = store.obj(arguments["list"], "list")
    year = store.date(query.get("year"), "%Y").year
    employee = store.get(db, "employee", query.get("employee_no"))["employee_no"]
    return [
        holiday
        for holiday in store.rows(db, "holiday")
        if holiday["employee_no"] == employee
        and store.date(holiday["date"]).year == year
    ]


HANDLERS = {
    "get_position_master": positions,
    "get_forms_data": forms,
    "get_holiday_list": holidays,
}
