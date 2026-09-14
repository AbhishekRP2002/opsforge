"""Projects, linked tasks, timesheets and native assignment simulation."""

import json

from . import erpnext_store as store


def assignment_users(db, args):
    if "assign_to" not in args:
        return []
    if args.get("notify_user", True) is not True:
        raise store.BusinessError(
            "notify_user=false is not supported for native assignments"
        )
    values = (
        [args["assign_to"]] if isinstance(args["assign_to"], str) else args["assign_to"]
    )
    if not isinstance(values, list) or not values:
        raise store.BusinessError("assign_to must contain users")
    users = list(dict.fromkeys(store.text(user, "assign_to") for user in values))
    if len(users) > 50:
        raise store.BusinessError("assign_to accepts at most 50 distinct users")
    for user in users:
        if "@" not in user or store.get(db, "User", user).get("enabled") != 1:
            raise store.BusinessError(
                f"User {user} is disabled or is not an email identity"
            )
    return users


def assign(db, kind, name, args, users, clock, committed=None):
    scenario = json.loads(
        db.connection.execute(
            "SELECT value FROM metadata WHERE key='scenario'"
        ).fetchone()[0]
    )
    if set(users).intersection(scenario.get("erpnext_assignment_failures", [])):
        if committed:
            raise store.PartialBusinessError(
                f"Task {name} {committed}, but assignment failed: modeled user assignment denial"
            )
        raise store.BusinessError("Assignment failed: modeled user assignment denial")
    doc = store.get(db, kind, name)
    todos = [
        row
        for row in store.all_docs(db, "ToDo")
        if row["reference_type"] == kind
        and row["reference_name"] == name
        and row["status"] == "Open"
    ]
    for user in users:
        if any(todo["owner"] == user for todo in todos):
            continue
        todo = store.create(
            db,
            "ToDo",
            {
                "owner": user,
                "reference_type": kind,
                "reference_name": name,
                "status": "Open",
                "description": args.get("assignment_description", ""),
                "priority": args.get("assignment_priority", "Medium"),
                "date": args.get("assignment_date"),
            },
            clock,
        )
        todos.append(todo)
        db.connection.execute(
            "INSERT INTO erpnext_notifications VALUES (?,?,?,?)",
            (todo["name"], user, kind, name),
        )
        db.connection.execute(
            "INSERT OR IGNORE INTO erpnext_shares VALUES (?,?,?)", (kind, name, user)
        )
    doc["_assign"] = json.dumps([todo["owner"] for todo in todos])
    doc["modified"] = store.now(db, clock)
    store.persist(db, kind, doc)
    return {
        "notify_user": True,
        "assignees": users,
        "todos": [{"owner": todo["owner"], "name": todo["name"]} for todo in todos],
    }


@store.handler
def doc_assign(db, args, step, clock):
    doc = store.get(db, args["doctype"], args["name"])
    users = assignment_users(db, args)
    info = assign(db, doc["doctype"], doc["name"], args, users, clock)
    return {
        "data": store.get(db, doc["doctype"], doc["name"]),
        "message": f"{doc['doctype']} {doc['name']} is now assigned to {', '.join(users)}",
        "assignment": info,
    }


@store.handler
def doc_unassign(db, args, step, clock):
    doc = store.get(db, args["doctype"], args["name"])
    user = store.text(args["assign_to"], "assign_to")
    remaining = []
    for todo in store.all_docs(db, "ToDo"):
        if (
            todo["reference_type"] != doc["doctype"]
            or todo["reference_name"] != doc["name"]
            or todo["status"] != "Open"
        ):
            continue
        if todo["owner"] == user:
            todo.update(status="Closed", modified=store.now(db, clock))
            store.persist(db, "ToDo", todo)
        else:
            remaining.append({"owner": todo["owner"], "name": todo["name"]})
    doc.update(
        _assign=json.dumps([todo["owner"] for todo in remaining]),
        modified=store.now(db, clock),
    )
    store.persist(db, doc["doctype"], doc)
    return {
        "data": doc,
        "message": f"{user} unassigned from {doc['doctype']} {doc['name']}",
        "assignment": {"removed": user, "remaining": remaining},
    }


@store.handler
def project_create(db, args, step, clock):
    doc = store.create(db, "Project", args, clock)
    return {"data": doc, "message": f"Project {doc['name']} created successfully"}


@store.handler
def task_create(db, args, step, clock):
    users = assignment_users(db, args)
    fields = {
        key: args[key]
        for key in (
            "project",
            "subject",
            "status",
            "priority",
            "exp_start_date",
            "exp_end_date",
        )
        if key in args
    }
    doc = store.create(db, "Task", fields, clock)
    result = {"data": doc, "message": f"Task {doc['name']} created successfully"}
    if users:
        result["assignment"] = assign(
            db, "Task", doc["name"], args, users, clock, committed="created"
        )
        result["data"] = store.get(db, "Task", doc["name"])
    return result


@store.handler
def task_update(db, args, step, clock):
    users = assignment_users(db, args)
    fields = {
        key: args[key]
        for key in ("status", "priority", "progress", "exp_end_date", "description")
        if key in args
    }
    if not fields and not users:
        raise store.BusinessError("At least one field to update is required")
    doc = (
        store.update(db, "Task", args["name"], fields, clock)
        if fields
        else store.get(db, "Task", args["name"])
    )
    result = {"data": doc, "message": f"Task {doc['name']} updated successfully"}
    if users:
        result["assignment"] = assign(
            db,
            "Task",
            doc["name"],
            args,
            users,
            clock,
            committed="updated" if fields else None,
        )
        result["data"] = store.get(db, "Task", doc["name"])
    return result


def get_document(kind):
    @store.handler
    def get(db, args, step, clock):
        return {"data": store.get(db, kind, args["name"])}

    return get


def list_documents(kind, fields, exact, start, end):
    @store.handler
    def listed(db, args, step, clock):
        filters = [[field, "=", args[field]] for field in exact if args.get(field)]
        if args.get("employee"):
            filters.append(
                [
                    "employee",
                    "=",
                    store.resolve(db, "Employee", args["employee"], "employee_name"),
                ]
            )
        if args.get("date_from"):
            filters.append([start, ">=", args["date_from"]])
        if args.get("date_to"):
            filters.append([end, "<=", args["date_to"]])
        docs = store.select(
            db, kind, fields=fields.split(), filters=filters, limit=args.get("limit")
        )
        return {"doctype": kind, "count": len(docs), "data": docs}

    return listed


HANDLERS = {
    "erpnext_doc_assign": doc_assign,
    "erpnext_doc_unassign": doc_unassign,
    "erpnext_project_create": project_create,
    "erpnext_task_create": task_create,
    "erpnext_task_update": task_update,
    "erpnext_project_get": get_document("Project"),
    "erpnext_task_get": get_document("Task"),
    "erpnext_timesheet_get": get_document("Timesheet"),
    "erpnext_project_list": list_documents(
        "Project",
        "name project_name status percent_complete expected_start_date expected_end_date estimated_costing",
        ("status", "company"),
        "expected_start_date",
        "expected_end_date",
    ),
    "erpnext_task_list": list_documents(
        "Task",
        "name subject project status priority exp_start_date exp_end_date progress",
        ("project", "status", "priority"),
        "exp_start_date",
        "exp_end_date",
    ),
    "erpnext_timesheet_list": list_documents(
        "Timesheet",
        "name employee start_date end_date status total_hours",
        ("project", "status"),
        "start_date",
        "end_date",
    ),
}
