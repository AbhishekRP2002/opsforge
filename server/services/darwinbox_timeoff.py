"""Pending requests and paid balances derived from terminal decisions."""

from . import darwinbox_store as store


def entitlement(db, employee, name):
    matches = [
        a
        for a in store.rows(db, "allocation")
        if a["employee_no"] == employee and a["leave_name"] == name
    ]
    if len(matches) != 1:
        raise store.BusinessError(
            "Exactly one explicit employee leave allocation is required"
        )
    return matches[0]


def balance(db, allocation):
    charged = sum(
        request["days"]
        for request in store.rows(db, "leave")
        if request["employee_no"] == allocation["employee_no"]
        and request["leave_name"] == allocation["leave_name"]
        and request["state"] == "approved"
        and request["is_paid_or_unpaid"] == "paid"
    )
    store.number(charged, "charged leave")
    return store.number(allocation["balance"] - charged, "remaining leave"), charged


def request_fields(entry):
    store.obj(entry, "leave entry")
    for field in ("employee_no", "leave_name", "message"):
        store.text(entry.get(field), field)
    low, high = store.span(entry.get("from_date"), entry.get("to_date"))
    half = store.choice(entry.get("is_half_day"), ("Yes", "No"), "is_half_day")
    store.choice(
        entry.get("is_paid_or_unpaid"), ("paid", "unpaid"), "is_paid_or_unpaid"
    )
    store.choice(
        entry.get("is_firsthalf_secondhalf", "1"), ("1", "2"), "is_firsthalf_secondhalf"
    )
    revoking = (
        store.choice(entry.get("revoke_leave"), ("Yes", "No"), "revoke_leave") == "Yes"
    )
    if revoking:
        store.text(entry.get("revoke_reason"), "revoke_reason")
    if half == "Yes" and low != high:
        raise store.BusinessError("A half day must have identical from and to dates")
    if {"leave_id", "state", "days", "modified"}.intersection(entry):
        raise store.BusinessError("Internal leave fields cannot be supplied")
    return low, high, 0.5 if half == "Yes" else (high - low).days + 1, revoking


def record_action(db, request, decision, message, clock):
    store.append(
        db,
        "leave_action",
        {
            "employee_no": request["employee_no"],
            "leave_id": request["leave_id"],
            "action": decision,
            "message": message,
            "unpaid": "1" if request["is_paid_or_unpaid"] == "unpaid" else "0",
            "modified": store.now(db, clock),
        },
    )


def revoke(db, entry, clock):
    identity_fields = ("employee_no", "leave_name", "from_date", "to_date")
    matches = [
        request
        for request in store.rows(db, "leave")
        if all(request[key] == entry[key] for key in identity_fields)
    ]
    if len(matches) != 1:
        raise store.BusinessError("Revocation must identify exactly one request")
    request = matches[0]
    for key in ("is_half_day", "is_paid_or_unpaid", "is_firsthalf_secondhalf"):
        if request.get(key, "1") != entry.get(key, "1"):
            raise store.BusinessError(
                "Revocation details differ from the original request"
            )
    if request["state"] == "rejected":
        raise store.BusinessError("A rejected request cannot be revoked")
    if request["state"] == "revoked":
        return request
    request.update(state="revoked", revoke_reason=entry["revoke_reason"])
    store.put(db, "leave", request["leave_id"], request)
    record_action(db, request, "revoke", entry["revoke_reason"], clock)
    return request


@store.handler
def apply(db, arguments, step, clock):
    results = []
    for entry in store.array(arguments["data"], "data"):
        low, high, days, revoking = request_fields(entry)
        employee = store.get(db, "employee", entry["employee_no"])
        entitlement(db, entry["employee_no"], entry["leave_name"])
        if revoking:
            results.append(revoke(db, entry, clock))
            continue
        if employee["status"] != "active":
            raise store.BusinessError("Leave requires an active employee")
        for request in store.rows(db, "leave"):
            if request["employee_no"] != entry["employee_no"] or request[
                "state"
            ] not in ("pending", "approved"):
                continue
            old_low, old_high = store.span(request["from_date"], request["to_date"])
            if low <= old_high and old_low <= high:
                raise store.BusinessError("Overlapping pending or approved leave")
        request = entry | {
            "days": days,
            "state": "pending",
            "modified": store.now(db, clock),
            "is_firsthalf_secondhalf": entry.get("is_firsthalf_secondhalf", "1"),
        }
        request["leave_id"] = store.append(db, "leave", request)
        store.put(db, "leave", request["leave_id"], request)
        record_action(db, request, "apply", entry["message"], clock)
        results.append(request)
    return results


@store.handler
def decide(db, arguments, step, clock):
    employee = store.get(db, "employee", arguments["employee_no"])
    request = store.get(db, "leave", arguments["leave_id"])
    decision = store.choice(arguments["action"], ("approve", "reject"), "action")
    if request["employee_no"] != employee["employee_no"]:
        raise store.BusinessError("Leave belongs to another employee")
    terminal = {"approve": "approved", "reject": "rejected"}[decision]
    if request["state"] == terminal:
        return request
    if request["state"] != "pending":
        raise store.BusinessError("Conflicting terminal decision")
    if terminal == "approved" and request["is_paid_or_unpaid"] == "paid":
        remaining, _ = balance(
            db, entitlement(db, request["employee_no"], request["leave_name"])
        )
        if request["days"] > remaining:
            raise store.BusinessError("Insufficient paid leave balance")
    request["state"] = terminal
    store.put(db, "leave", request["leave_id"], request)
    record_action(db, request, decision, arguments.get("manager_message", ""), clock)
    return request


@store.handler
def balances(db, arguments, step, clock):
    identifiers = store.employees(db, arguments["employee_nos"])
    rounding = store.choice(
        arguments.get("ignore_rounding", "0"), ("0", "1"), "ignore_rounding"
    )
    output = []
    for allocation in store.rows(db, "allocation"):
        if allocation["employee_no"] not in identifiers:
            continue
        remaining, charged = balance(db, allocation)
        output.append(
            {
                "employee_no": allocation["employee_no"],
                "employee_name": store.get(
                    db, "employee", allocation["employee_no"]
                ).get("employee_name", ""),
                "leave_id": allocation["leave_id"],
                "leave_name": allocation["leave_name"],
                "currently_availabel_balance": round(remaining, 2)
                if rounding == "0"
                else remaining,
                "accrued_so_far_this_year": allocation.get(
                    "accrued_so_far_this_year", 0
                ),
                "previous_balance": allocation.get("previous_balance", 0),
                "adjustment_balance": allocation.get("adjustment_balance", 0),
                "yearly_allotment": str(allocation["balance"]),
                "taken": charged,
                "utilized_leaves_this_year": charged,
            }
        )
    return output


@store.handler
def actions(db, arguments, step, clock):
    selectors = store.obj(arguments["history"], "history")
    low, high = store.span(selectors.get("from"), selectors.get("to"))
    identifiers = store.employees(db, selectors.get("employee_no"))
    decision = store.choice(
        selectors.get("action"), ("apply", "approve", "reject", "revoke"), "action"
    )
    unpaid = store.choice(selectors.get("unpaid"), ("0", "1"), "unpaid")
    return [
        action
        for action in store.rows(db, "leave_action")
        if action["employee_no"] in identifiers
        and action["action"] == decision
        and action["unpaid"] == unpaid
        and low <= store.date(action["modified"].split()[0]) <= high
    ]


HANDLERS = {
    "apply_leave": apply,
    "approve_leave": decide,
    "get_leave_balance": balances,
    "get_leave_action_history": actions,
}
