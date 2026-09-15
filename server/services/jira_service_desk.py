"""Explicit service-desk, queue, and customer-request behavior."""

import base64
import binascii
import json
import re

from . import jira_store as s


def page(args, values):
    start, limit = args.get("start_at", 0), args.get("limit", 50)
    if (
        type(start) is not int
        or start < 0
        or type(limit) is not int
        or not 1 <= limit <= 50
    ):
        raise s.BusinessError("Pagination requires start_at >= 0 and limit 1..50")
    selected = values[start : start + limit]
    return {
        "size": len(selected),
        "start": start,
        "limit": limit,
        "isLastPage": start + len(selected) >= len(values),
        "values": selected,
    }


def desk(db, identifier):
    identity = s.text(identifier, "service_desk_id")
    row = db.connection.execute(
        "SELECT * FROM jira_service_desks WHERE id=?", (identity,)
    ).fetchone()
    if row is None:
        raise s.BusinessError(f"Service desk {identity} not found")
    project = json.loads(
        db.connection.execute(
            "SELECT data FROM jira_projects WHERE id=?", (row["project_id"],)
        ).fetchone()[0]
    )
    s.project(db, project["key"])
    return {"id": row["id"], "project": project, **json.loads(row["data"])}


def request_type(db, desk_id, identifier):
    identity = s.text(identifier, "request_type_id")
    row = db.connection.execute(
        "SELECT data FROM jira_request_types WHERE service_desk_id=? AND id=?",
        (desk_id, identity),
    ).fetchone()
    if row is None:
        raise s.BusinessError(f"Request type {identity} not found")
    return {"id": identity, "serviceDeskId": desk_id, **json.loads(row[0])}


@s.handler()
def get_service_desk_for_project(db, args, step, clock):
    project = s.project(db, args.get("project_key"))
    row = db.connection.execute(
        "SELECT id,data FROM jira_service_desks WHERE project_id=?", (project["id"],)
    ).fetchone()
    if row is None:
        raise s.BusinessError(f"Project {project['key']} has no service desk")
    return {
        "id": row["id"],
        "projectId": project["id"],
        "projectKey": project["key"],
        **json.loads(row["data"]),
    }


@s.handler()
def get_service_desk_queues(db, args, step, clock):
    record = desk(db, args.get("service_desk_id"))
    values = [
        {"id": row["id"], "serviceDeskId": record["id"], **json.loads(row["data"])}
        for row in db.connection.execute(
            "SELECT * FROM jira_queues WHERE service_desk_id=? ORDER BY id",
            (record["id"],),
        )
    ]
    return page(args, values)


@s.handler()
def get_queue_issues(db, args, step, clock):
    from .jira_core import DEFAULT_FIELDS, projection
    from .jira_query import select

    record = desk(db, args.get("service_desk_id"))
    queue_id = s.text(args.get("queue_id"), "queue_id")
    row = db.connection.execute(
        "SELECT data FROM jira_queues WHERE id=? AND service_desk_id=?",
        (queue_id, record["id"]),
    ).fetchone()
    if row is None:
        raise s.BusinessError(f"Queue {queue_id} not found")
    query = json.loads(row[0]).get("jql", f"project={record['project']['key']}")
    issues = [
        projection(db, issue, DEFAULT_FIELDS)
        for issue in select(db, query, record["project"]["key"])
    ]
    return page(args, issues)


@s.handler()
def get_request_types(db, args, step, clock):
    record = desk(db, args.get("service_desk_id"))
    values = [
        {"id": row["id"], "serviceDeskId": record["id"], **json.loads(row["data"])}
        for row in db.connection.execute(
            "SELECT * FROM jira_request_types WHERE service_desk_id=? ORDER BY id",
            (record["id"],),
        )
    ]
    return page(args, values)


@s.handler()
def get_request_type_fields(db, args, step, clock):
    record = desk(db, args.get("service_desk_id"))
    kind = request_type(db, record["id"], args.get("request_type_id"))
    return {"requestTypeFields": kind.get("fields", [])}


def participants(db, value):
    if value is None or value == "":
        return []
    if isinstance(value, str) and value.lstrip().startswith("["):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise s.BusinessError("Invalid request_participants JSON") from error
    elif isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    records = []
    for item in s.array(value, "request_participants"):
        user = s.user(db, s.text(item, "request participant"))
        if not user["active"]:
            raise s.BusinessError("Request participant is inactive")
        if user["id"] not in [record["id"] for record in records]:
            records.append(user)
    return records


def add_attachment(db, record, item, step, clock):
    item = s.obj(item, "attachment")
    if set(item) != {"filename", "mime_type", "base64"}:
        raise s.BusinessError("Attachment requires filename, mime_type, and base64")
    filename = s.text(item["filename"], "filename")
    media_type = s.text(item["mime_type"], "mime_type")
    if len(filename) > 255 or not re.fullmatch(r"[A-Za-z0-9._ -]+", filename):
        raise s.BusinessError("Invalid attachment filename")
    try:
        content = base64.b64decode(s.text(item["base64"], "base64"), validate=True)
    except (binascii.Error, ValueError) as error:
        raise s.BusinessError("Invalid base64 attachment") from error
    if len(content) > 1_048_576:
        raise s.BusinessError("Attachment exceeds 1 MiB")
    path = f"artifacts/jira/{record['id']}/{filename}"
    if db.artifact(path) is not None:
        raise s.BusinessError(f"Attachment {filename} already exists")
    db.connection.execute(
        "INSERT INTO episode_artifacts VALUES (?,?,?,?,?)",
        (path, content, media_type, step, clock),
    )
    cursor = db.connection.execute(
        "INSERT INTO jira_attachments(issue_id,path,filename,media_type) VALUES (?,?,?,?)",
        (record["id"], path, filename, media_type),
    )
    return {
        "id": str(cursor.lastrowid),
        "filename": filename,
        "mimeType": media_type,
        "size": len(content),
    }


@s.handler(write=True)
def create_customer_request(db, args, step, clock):
    from .jira_core import insert_issue, prepare_issue, projection

    record = desk(db, args.get("service_desk_id"))
    kind = request_type(db, record["id"], args.get("request_type_id"))
    try:
        values = json.loads(
            s.text(args.get("request_field_values"), "request_field_values")
        )
    except json.JSONDecodeError as error:
        raise s.BusinessError("Invalid request_field_values JSON") from error
    values = s.obj(values, "request_field_values")
    missing = [
        field["fieldId"]
        for field in kind.get("fields", [])
        if field.get("required") and not values.get(field["fieldId"])
    ]
    if missing:
        raise s.BusinessError("Missing required request fields: " + ", ".join(missing))
    reporter, warning = None, None
    if args.get("raise_on_behalf_of"):
        try:
            reporter = s.user(db, args["raise_on_behalf_of"])
            if not reporter["active"]:
                raise s.BusinessError("Requested reporter is inactive")
        except s.BusinessError as error:
            if args.get("strict_on_behalf", False):
                raise
            warning = f"Could not raise on behalf of requested user: {error}"
    if reporter is None:
        reporter = s.user_by_id(db, s.config(db)["jira_current_user"])
    request_participants = participants(db, args.get("request_participants"))
    standard = {
        key: values.pop(key) for key in ("summary", "description") if key in values
    }
    issue = insert_issue(
        db,
        prepare_issue(
            db,
            {
                "project_key": record["project"]["key"],
                "summary": standard.get("summary"),
                "description": standard.get("description"),
                "issue_type": kind.get("issueType", "Task"),
                "additional_fields": json.dumps(values),
            },
            clock,
        ),
    )
    db.connection.execute("INSERT INTO jira_request_issues VALUES (?)", (issue["id"],))
    db.connection.execute(
        "INSERT INTO jira_requests VALUES (?,?,?,?,?)",
        (
            issue["id"],
            record["id"],
            kind["id"],
            reporter["id"],
            json.dumps([user["id"] for user in request_participants]),
        ),
    )
    attachments = []
    if args.get("attachments"):
        try:
            supplied = json.loads(s.text(args["attachments"], "attachments"))
        except json.JSONDecodeError as error:
            raise s.BusinessError("Invalid attachments JSON") from error
        attachments = [
            add_attachment(db, issue, item, step, clock)
            for item in s.array(supplied, "attachments")
        ]
    result = {
        "issueKey": issue["key"],
        "requestTypeId": kind["id"],
        "serviceDeskId": record["id"],
        "reporter": s.public_user(reporter),
        "requestParticipants": [s.public_user(user) for user in request_participants],
        "attachments": attachments,
        "issue": projection(db, issue, "*all"),
    }
    if warning:
        result["warning"] = warning
    return result


def validate_fixtures(world):
    projects = {project["key"]: project for project in world.jira_projects}
    issues = {issue["id"] for issue in world.jira_issues}
    users = {user["id"] for user in world.jira_users}
    desks = {}
    for item in world.jira_service_desks:
        identity, key = (
            s.text(item.get("id"), "service desk id"),
            s.text(item.get("project_key"), "service desk project"),
        )
        if identity in desks or key not in projects:
            raise s.BusinessError("Invalid service desk fixture")
        desks[identity] = item
    queues = set()
    for item in world.jira_queues:
        identity = s.text(item.get("id"), "queue id")
        if identity in queues or item.get("service_desk_id") not in desks:
            raise s.BusinessError("Invalid queue fixture")
        s.text(item.get("name"), "queue name")
        s.text(item.get("jql"), "queue jql")
        queues.add(identity)
    request_types = set()
    for item in world.jira_request_types:
        key = (
            s.text(item.get("service_desk_id"), "service desk reference"),
            s.text(item.get("id"), "request type id"),
        )
        if key in request_types or key[0] not in desks:
            raise s.BusinessError("Invalid request type fixture")
        project = projects[desks[key[0]]["project_key"]]
        s.named(project["issue_types"], item.get("issue_type"), "request issue_type")
        for field in s.array(item.get("fields", []), "request fields"):
            s.text(s.obj(field, "request field").get("field_id"), "request field id")
            if type(field.get("required", False)) is not bool:
                raise s.BusinessError("Request field required must be boolean")
        request_types.add(key)
    for item in world.jira_requests:
        request_participants = s.array(item.get("participants", []), "participants")
        if (
            item.get("issue_id") not in issues
            or item.get("reporter_id") not in users
            or (item.get("service_desk_id"), item.get("request_type_id"))
            not in request_types
            or any(participant not in users for participant in request_participants)
        ):
            raise s.BusinessError("Invalid request fixture")


def seed(db, world):
    projects = {project["key"]: project for project in world.jira_projects}
    for item in world.jira_service_desks:
        data = {
            key: value
            for key, value in item.items()
            if key not in ("id", "project_key")
        }
        db.connection.execute(
            "INSERT INTO jira_service_desks VALUES (?,?,?)",
            (item["id"], projects[item["project_key"]]["id"], json.dumps(data)),
        )
    for item in world.jira_queues:
        data = {
            key: value
            for key, value in item.items()
            if key not in ("id", "service_desk_id")
        }
        db.connection.execute(
            "INSERT INTO jira_queues VALUES (?,?,?)",
            (item["id"], item["service_desk_id"], json.dumps(data)),
        )
    for item in world.jira_request_types:
        data = {
            "name": item.get("name", item["id"]),
            "description": item.get("description", ""),
            "issueType": item["issue_type"],
            "fields": [
                {
                    "fieldId": f["field_id"],
                    "name": f.get("name", f["field_id"]),
                    "required": f.get("required", False),
                }
                for f in item.get("fields", [])
            ],
        }
        db.connection.execute(
            "INSERT INTO jira_request_types VALUES (?,?,?)",
            (item["id"], item["service_desk_id"], json.dumps(data)),
        )
    for item in world.jira_requests:
        db.connection.execute(
            "INSERT OR IGNORE INTO jira_request_issues VALUES (?)", (item["issue_id"],)
        )
        db.connection.execute(
            "INSERT INTO jira_requests VALUES (?,?,?,?,?)",
            (
                item["issue_id"],
                item["service_desk_id"],
                item["request_type_id"],
                item["reporter_id"],
                json.dumps(item.get("participants", [])),
            ),
        )


HANDLERS = {
    "jira_get_service_desk_for_project": get_service_desk_for_project,
    "jira_get_service_desk_queues": get_service_desk_queues,
    "jira_get_queue_issues": get_queue_issues,
    "jira_get_request_types": get_request_types,
    "jira_get_request_type_fields": get_request_type_fields,
    "jira_create_customer_request": create_customer_request,
}
