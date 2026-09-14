"""Stable Jira identities and bounded, explicit fixture-domain validation."""

import json
import re
from datetime import datetime, timedelta
from functools import wraps


class BusinessError(ValueError):
    pass


class UnresolvedIdentity(BusinessError):
    """A valid public identifier has no unique matching user."""


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise BusinessError(f"{field} must be a nonempty string")
    return value


def obj(value, field):
    if not isinstance(value, dict):
        raise BusinessError(f"{field} must be an object")
    return value


def array(value, field):
    if not isinstance(value, list):
        raise BusinessError(f"{field} must be an array")
    return value


def json_object(value, field):
    if value is None or value == "":
        return {}
    try:
        parsed = json.loads(text(value, field))
    except json.JSONDecodeError as error:
        raise BusinessError(f"Invalid JSON in {field}") from error
    return obj(parsed, field)


def config(db):
    return json.loads(
        db.connection.execute(
            "SELECT value FROM metadata WHERE key='scenario'"
        ).fetchone()[0]
    )


def now(db, clock):
    return (
        datetime.fromisoformat(config(db)["jira_epoch"]) + timedelta(seconds=clock)
    ).isoformat()


def project(db, key):
    key = text(key, "project_key")
    row = db.connection.execute(
        "SELECT * FROM jira_projects WHERE key=?", (key,)
    ).fetchone()
    if row is None:
        raise BusinessError(f"Project {key} not found")
    allowed = config(db)["jira_projects_filter"]
    if allowed and key not in allowed:
        raise BusinessError(f"Project {key} restricted by configuration")
    return json.loads(row["data"])


def issue(db, key):
    row = db.connection.execute(
        "SELECT * FROM jira_issues WHERE key=?", (text(key, "issue_key"),)
    ).fetchone()
    if row is None:
        raise BusinessError(f"Issue {key} not found")
    result = dict(row)
    result["data"] = json.loads(result["data"])
    project(db, result["data"]["project_key"])
    return result


def user_by_id(db, identifier):
    """Resolve a stored reference exactly, without public alias matching."""
    row = db.connection.execute(
        "SELECT data FROM jira_users WHERE id=?", (text(identifier, "user ID"),)
    ).fetchone()
    if row is None:
        raise BusinessError(f"User ID {identifier} not found")
    return json.loads(row[0])


def user(db, identifier):
    identifier = text(identifier, "user identifier")
    if identifier.lower() == "me":
        identifier = config(db)["jira_current_user"]
        if identifier is None:
            raise BusinessError("Current Jira user is not configured")
        return user_by_id(db, identifier)
    if identifier.startswith("accountid:"):
        identifier = text(identifier.removeprefix("accountid:"), "account ID")
    matches = [
        json.loads(row[0])
        for row in db.connection.execute("SELECT data FROM jira_users ORDER BY id")
    ]
    matches = [
        u
        for u in matches
        if identifier.casefold()
        in [u[k].casefold() for k in ("id", "name", "display_name", "email")]
    ]
    if len(matches) != 1:
        raise UnresolvedIdentity(f"User {identifier} not found or ambiguous")
    return matches[0]


def public_user(record):
    return {
        "account_id": record["id"],
        "name": record["name"],
        "display_name": record["display_name"],
        "email": record["email"],
        "avatar_url": None,
    }


def validate_assignment(record, project_key):
    if not record["active"] or project_key not in record["project_keys"]:
        raise BusinessError("User is not assignable in this project")


def resolve_assignee(db, value):
    """Resolve public assignment input without deciding project eligibility."""
    if value is None or value == "":
        return None
    if isinstance(value, str) and value.lstrip().startswith("{"):
        value = json_object(value, "assignee")
    if isinstance(value, dict):
        keys = (
            ("accountId", "account_id")
            if config(db)["jira_edition"] == "cloud"
            else ("name", "username", "key", "accountId", "account_id")
        )
        identifiers = [text(value[k], "assignee " + k) for k in keys if k in value]
        value = identifiers[0] if identifiers else None
    return user(db, value)


def assignee(db, value, project_key):
    record = resolve_assignee(db, value)
    if record is None:
        return None
    validate_assignment(record, project_key)
    return record["id"]


def save(db, record):
    db.connection.execute(
        "UPDATE jira_issues SET key=?,project_id=?,parent_id=?,data=? WHERE id=?",
        (
            record["key"],
            record["project_id"],
            record["parent_id"],
            json.dumps(record["data"], allow_nan=False),
            record["id"],
        ),
    )


def next_key(db, project_key):
    row = db.connection.execute(
        "SELECT next_number FROM jira_projects WHERE key=?", (project_key,)
    ).fetchone()
    db.connection.execute(
        "UPDATE jira_projects SET next_number=next_number+1 WHERE key=?", (project_key,)
    )
    return f"{project_key}-{row[0]}"


def handler(*, write=False, envelope=None):
    def decorate(function):
        @wraps(function)
        def execute(db, arguments, step, clock):
            db.connection.execute("SAVEPOINT jira_business")
            try:
                if write and config(db)["jira_read_only"]:
                    raise BusinessError("Jira is in read-only mode")
                result = function(db, arguments, step, clock)
            except BusinessError as error:
                db.connection.execute("ROLLBACK TO jira_business")
                db.connection.execute("RELEASE jira_business")
                if envelope:
                    return {
                        "success": False,
                        "error": str(error),
                        envelope: arguments.get(envelope),
                    }, False
                return {"error": str(error)}, True
            db.connection.execute("RELEASE jira_business")
            return result, False

        return execute

    return decorate


def named(items, identifier, field):
    identifier = text(identifier, field)
    matches = [item for item in items if identifier in (item["id"], item["name"])]
    if len(matches) != 1:
        raise BusinessError(f"Unknown or ambiguous {field}: {identifier}")
    return matches[0]


def validate_fields(data, metadata):
    allowed = {
        "project_key",
        "summary",
        "issue_type",
        "status",
        "description",
        "labels",
        "priority",
        "components",
        "assignee",
        "created",
        "updated",
        "resolution",
        "resolutiondate",
    }
    for field in data:
        if field not in allowed and field not in metadata["field_names"]:
            raise BusinessError(f"Unsupported issue field in core profile: {field}")
    text(data.get("summary"), "summary")
    named(metadata["issue_types"], data.get("issue_type"), "issue_type")
    named(metadata["statuses"], data.get("status"), "status")
    if data.get("description") is not None and not isinstance(data["description"], str):
        raise BusinessError("description must be text")
    for label in array(data.get("labels", []), "labels"):
        text(label, "label")
    if "priority" in data:
        text(obj(data["priority"], "priority").get("name"), "priority name")
    if "resolution" in data:
        text(obj(data["resolution"], "resolution").get("name"), "resolution name")
    if "resolutiondate" in data:
        from .jira_relations import timestamp

        timestamp(data["resolutiondate"], "resolutiondate")
    for component in array(data.get("components", []), "components"):
        named(metadata["components"], component, "component")
    for key in data:
        if key.startswith("customfield_") and key not in metadata["field_names"]:
            raise BusinessError(f"Unconfigured custom field {key}")
    try:
        json.dumps(data, allow_nan=False)
    except ValueError as error:
        raise BusinessError("Fields must contain finite JSON values") from error


def validate_fixtures(world):
    epoch = datetime.fromisoformat(world.jira_epoch)
    if epoch.utcoffset() != timedelta(0):
        raise BusinessError("Jira epoch must be UTC")
    projects = {}
    ids = set()
    for p in world.jira_projects:
        for key in ("id", "key", "name"):
            text(p.get(key), key)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]+", p["key"]):
            raise BusinessError("Invalid project key")
        if p["key"] in projects or p["id"] in ids:
            raise BusinessError("Duplicate project identity")
        ids.add(p["id"])
        projects[p["key"]] = p
        for field in ("issue_types", "statuses", "components"):
            entries = array(p.setdefault(field, []), field)
            if field != "components" and not entries:
                raise BusinessError(f"Project requires {field}")
            seen = set()
            for item in entries:
                item = obj(item, field)
                identity = text(item.get("id"), "id")
                name = text(item.get("name"), "name")
                if "subtask" in item and type(item["subtask"]) is not bool:
                    raise BusinessError("subtask metadata must be boolean")
                if field == "statuses" and "category" in item:
                    category = obj(item["category"], "status category")
                    for category_field in ("id", "key", "name"):
                        text(category.get(category_field), "category " + category_field)
                if identity in seen or name in seen:
                    raise BusinessError(f"Duplicate {field}")
                seen.update((identity, name))
        names = obj(p.setdefault("field_names", {}), "field_names")
        reserved = {
            "id",
            "key",
            "summary",
            "description",
            "status",
            "assignee",
            "reporter",
            "project",
            "issue_type",
            "labels",
            "priority",
            "created",
            "updated",
            "parent",
            "comments",
            "watchers",
            "changelogs",
            "transitions",
            "worklogs",
            "attachments",
            "remote_links",
            "components",
            "issuelinks",
            "sprint",
            "timetracking",
            "resolution",
            "resolutiondate",
        }
        seen_names = set()
        for key, value in names.items():
            text(key, "field id")
            text(value, "field name")
            if (
                not re.fullmatch(r"customfield_[0-9]+", key)
                or value in reserved
                or value in seen_names
                or value in names
            ):
                raise BusinessError(
                    "Custom fields require unique nonreserved display names and numeric IDs"
                )
            seen_names.add(value)
    users = set()
    user_records = {}
    for u in world.jira_users:
        for field in ("id", "name", "display_name", "email"):
            text(u.get(field), field)
        if u["id"] in users:
            raise BusinessError("Duplicate user ID")
        users.add(u["id"])
        user_records[u["id"]] = u
        if type(u.get("active")) is not bool:
            raise BusinessError("active must be boolean")
        for key in array(u.get("project_keys"), "project_keys"):
            if text(key, "project reference") not in projects:
                raise BusinessError("Unknown user project")
    if world.jira_current_user is not None and world.jira_current_user not in users:
        raise BusinessError("Unknown current user")
    for key in world.jira_projects_filter:
        if key not in projects:
            raise BusinessError("Unknown project filter")
    keys, issue_ids = set(), set()
    for row in world.jira_issues:
        if (
            type(row.get("id")) is not int
            or not 1 <= row["id"] <= 1_000_000_000
            or row["id"] in issue_ids
        ):
            raise BusinessError("Issue fixture ID must be a unique positive integer")
        issue_ids.add(row["id"])
        key = text(row.get("key"), "issue key")
        data = obj(row.get("data"), "issue fields")
        project_key = text(data.get("project_key"), "project_key")
        if (
            project_key not in projects
            or not re.fullmatch(re.escape(project_key) + r"-[1-9][0-9]*", key)
            or key in keys
        ):
            raise BusinessError("Invalid or duplicate issue key")
        keys.add(key)
        if (
            len(key.rsplit("-", 1)[1]) > 10
            or int(key.rsplit("-", 1)[1]) > 1_000_000_000
        ):
            raise BusinessError("Fixture issue numbers exceed the finite profile bound")
        if {"id", "key", "parent_id", "project_id"}.intersection(data):
            raise BusinessError("Issue fields cannot shadow identity")
        validate_fields(data, projects[project_key])
        kind = named(
            projects[project_key]["issue_types"], data["issue_type"], "issue_type"
        )
        if kind.get("subtask", False) and row.get("parent_id") is None:
            raise BusinessError("Subtask fixture requires parent")
        if (
            data.get("assignee") is not None
            and text(data["assignee"], "assignee") not in users
        ):
            raise BusinessError("Unknown fixture assignee")
        if data.get("assignee") is not None:
            assigned = user_records[data["assignee"]]
            validate_assignment(assigned, project_key)
        for field in ("created", "updated"):
            value = datetime.fromisoformat(text(data.get(field), field))
            if value.utcoffset() != timedelta(0):
                raise BusinessError("Issue timestamps must be UTC")
        if datetime.fromisoformat(data["updated"]) < datetime.fromisoformat(
            data["created"]
        ):
            raise BusinessError("Issue updated precedes created")
    for row in world.jira_issues:
        parent = row.get("parent_id")
        if parent is not None and (
            type(parent) is not int or parent not in issue_ids or parent == row["id"]
        ):
            raise BusinessError("Invalid parent identity")
    parents = {row["id"]: row.get("parent_id") for row in world.jira_issues}
    for identity in parents:
        visited = set()
        current = identity
        while current is not None:
            if current in visited:
                raise BusinessError("Cyclic issue parent relationship")
            visited.add(current)
            current = parents[current]
    from .jira_relations import validate_fixtures as validate_activity

    validate_activity(world)
    from .jira_workflow import validate_fixtures as validate_workflow

    validate_workflow(world)
    from .jira_agile import validate_fixtures as validate_agile

    validate_agile(world)


def seed(db, world):
    for p in world.jira_projects:
        db.connection.execute(
            "INSERT INTO jira_projects(id,key,data) VALUES (?,?,?)",
            (p["id"], p["key"], json.dumps(p)),
        )
    for u in world.jira_users:
        db.connection.execute(
            "INSERT INTO jira_users VALUES (?,?)", (u["id"], json.dumps(u))
        )
    for row in world.jira_issues:
        p = next(
            p for p in world.jira_projects if p["key"] == row["data"]["project_key"]
        )
        db.connection.execute(
            "INSERT INTO jira_issues(id,key,project_id,data) VALUES (?,?,?,?)",
            (row["id"], row["key"], p["id"], json.dumps(row["data"])),
        )
        db.connection.execute(
            "UPDATE jira_projects SET next_number=max(next_number,?) WHERE id=?",
            (int(row["key"].rsplit("-", 1)[1]) + 1, p["id"]),
        )
    for row in world.jira_issues:
        db.connection.execute(
            "UPDATE jira_issues SET parent_id=? WHERE id=?",
            (row.get("parent_id"), row["id"]),
        )
    from .jira_relations import seed as seed_activity

    seed_activity(db, world)
    from .jira_workflow import seed as seed_workflow

    seed_workflow(db, world)
    from .jira_agile import seed as seed_agile

    seed_agile(db, world)
