"""Project metadata and mutable version records for the finite Jira profile."""

import json
import sqlite3
from datetime import date

from . import jira_store as s

STANDARD_FIELDS = (
    {
        "id": "summary",
        "name": "Summary",
        "required": True,
        "schema": {"type": "string"},
    },
    {
        "id": "description",
        "name": "Description",
        "required": False,
        "schema": {"type": "string"},
    },
    {
        "id": "assignee",
        "name": "Assignee",
        "required": False,
        "schema": {"type": "user"},
    },
    {"id": "labels", "name": "Labels", "required": False, "schema": {"type": "array"}},
    {
        "id": "components",
        "name": "Components",
        "required": False,
        "schema": {"type": "array"},
    },
)


def bounded(value, field, default, maximum):
    value = default if value is None else value
    if type(value) is not int or not 1 <= value <= maximum:
        raise s.BusinessError(f"{field} must be between 1 and {maximum}")
    return value


def project_fields(project):
    configured = project.get("fields", [])
    if configured:
        return [dict(field) for field in configured]
    return [
        *map(dict, STANDARD_FIELDS),
        *(
            {
                "id": identity,
                "name": name,
                "required": False,
                "custom": True,
                "schema": {"type": "string"},
            }
            for identity, name in project["field_names"].items()
        ),
    ]


def public_project(project):
    return {
        key: project[key] for key in ("id", "key", "name", "archived") if key in project
    }


def visible_projects(db, include_archived=False):
    projects = [
        json.loads(row[0])
        for row in db.connection.execute("SELECT data FROM jira_projects ORDER BY key")
    ]
    allowed = s.config(db)["jira_projects_filter"]
    return [
        public_project(project)
        for project in projects
        if (not allowed or project["key"] in allowed)
        and (include_archived or not project.get("archived", False))
    ]


@s.handler()
def search_fields(db, args, step, clock):
    keyword = args.get("keyword", "")
    if not isinstance(keyword, str):
        raise s.BusinessError("keyword must be text")
    limit = bounded(args.get("limit"), "limit", 10, 1000)
    fields = {}
    for row in db.connection.execute("SELECT data FROM jira_projects ORDER BY key"):
        for field in project_fields(json.loads(row[0])):
            fields.setdefault(field["id"], field)
    needle = keyword.casefold()
    return [
        field
        for field in fields.values()
        if not needle
        or needle in field["id"].casefold()
        or needle in field["name"].casefold()
    ][:limit]


def flatten_values(options):
    values = []
    for option in options:
        values.append(option.get("value", option.get("name")))
        values.extend(flatten_values(option.get("children", [])))
    return values


@s.handler()
def get_field_options(db, args, step, clock):
    field_id = s.text(args.get("field_id"), "field_id")
    projects = (
        [s.project(db, args["project_key"])]
        if args.get("project_key")
        else [
            json.loads(row[0])
            for row in db.connection.execute(
                "SELECT data FROM jira_projects ORDER BY key"
            )
        ]
    )
    if s.config(db)["jira_edition"] == "server" and not args.get("project_key"):
        raise s.BusinessError("project_key is required on Jira Server/DC")
    if args.get("issue_type") is not None:
        for project in projects:
            s.named(project["issue_types"], args["issue_type"], "issue_type")
    options = []
    for project in projects:
        options.extend(project.get("field_options", {}).get(field_id, []))
    contains = args.get("contains")
    if contains is not None:
        needle = s.text(contains, "contains").casefold()
        options = [
            option
            for option in options
            if needle in str(option.get("value", option.get("name", ""))).casefold()
            or any(
                needle in str(value).casefold()
                for value in flatten_values(option.get("children", []))
            )
        ]
    if args.get("return_limit") is not None:
        options = options[: bounded(args["return_limit"], "return_limit", 1, 1000)]
    return flatten_values(options) if args.get("values_only", False) else options


@s.handler()
def get_project_issue_types(db, args, step, clock):
    return s.project(db, args.get("project_key"))["issue_types"]


@s.handler()
def get_create_fields(db, args, step, clock):
    project = s.project(db, args.get("project_key"))
    issue_type = s.named(
        project["issue_types"], args.get("issue_type_id"), "issue_type_id"
    )
    return {
        "project": public_project(project),
        "issue_type": issue_type,
        "fields": project_fields(project),
    }


def version_row(db, identifier):
    value = s.text(identifier, "version_id")
    if not value.isdigit():
        raise s.BusinessError("version_id must be numeric")
    row = db.connection.execute(
        "SELECT * FROM jira_versions WHERE id=?", (int(value),)
    ).fetchone()
    if row is None:
        raise s.BusinessError(f"Version {value} not found")
    data = json.loads(row["data"])
    project = json.loads(
        db.connection.execute(
            "SELECT data FROM jira_projects WHERE id=?", (row["project_id"],)
        ).fetchone()[0]
    )
    s.project(db, project["key"])
    return dict(row) | {"data": data}


def public_version(row):
    return {"id": str(row["id"]), **row["data"]}


@s.handler()
def get_project_versions(db, args, step, clock):
    project = s.project(db, args.get("project_key"))
    return [
        public_version(dict(row) | {"data": json.loads(row["data"])})
        for row in db.connection.execute(
            "SELECT * FROM jira_versions WHERE project_id=? ORDER BY id",
            (project["id"],),
        )
    ]


@s.handler()
def get_project_components(db, args, step, clock):
    return s.project(db, args.get("project_key"))["components"]


@s.handler()
def get_all_projects(db, args, step, clock):
    include_archived = args.get("include_archived", False)
    if type(include_archived) is not bool:
        raise s.BusinessError("include_archived must be boolean")
    return visible_projects(db, include_archived)


@s.handler()
def search_projects(db, args, step, clock):
    needle = s.text(args.get("query"), "query").casefold()
    limit = bounded(args.get("max_results"), "max_results", 20, 50)
    excluded = {
        item.strip()
        for item in (args.get("current_project_ids") or "").split(",")
        if item.strip()
    }
    return [
        project
        for project in visible_projects(db)
        if project["id"] not in excluded
        and (
            project["key"].casefold().startswith(needle)
            or needle in project["name"].casefold()
        )
    ][:limit]


@s.handler()
def get_project_fields(db, args, step, clock):
    project = s.project(db, args.get("project_key"))
    return {"project": public_project(project), "fields": project_fields(project)}


def valid_date(value, field):
    if value is None:
        return None
    try:
        return date.fromisoformat(s.text(value, field)).isoformat()
    except ValueError as error:
        raise s.BusinessError(f"{field} must use YYYY-MM-DD") from error


def version_data(args, previous=None):
    args = dict(args)
    data: dict = dict(previous or {"archived": False, "released": False})
    aliases = {"startDate": "start_date", "releaseDate": "release_date"}
    for source, target in aliases.items():
        if source in args and target not in args:
            args[target] = args[source]
    for key in (
        "name",
        "description",
        "start_date",
        "release_date",
        "archived",
        "released",
    ):
        if key in args and args[key] is not None:
            data[key] = args[key]
    s.text(data.get("name"), "version name")
    if data.get("description") is not None and not isinstance(data["description"], str):
        raise s.BusinessError("description must be text")
    for key in ("archived", "released"):
        if type(data.get(key)) is not bool:
            raise s.BusinessError(f"{key} must be boolean")
    data["start_date"] = valid_date(data.get("start_date"), "start_date")
    data["release_date"] = valid_date(data.get("release_date"), "release_date")
    if (
        data["start_date"]
        and data["release_date"]
        and data["start_date"] > data["release_date"]
    ):
        raise s.BusinessError("Version start_date must not follow release_date")
    return data


def insert_version(db, project, args):
    data = version_data(dict(args))
    try:
        cursor = db.connection.execute(
            "INSERT INTO jira_versions(project_id,name,data) VALUES (?,?,?)",
            (project["id"], data["name"], json.dumps(data)),
        )
    except sqlite3.IntegrityError as error:
        raise s.BusinessError(f"Version {data['name']} already exists") from error
    return public_version({"id": cursor.lastrowid, "data": data})


@s.handler(write=True)
def create_version(db, args, step, clock):
    return insert_version(db, s.project(db, args.get("project_key")), args)


@s.handler(write=True)
def batch_create_versions(db, args, step, clock):
    try:
        entries = json.loads(s.text(args.get("versions"), "versions"))
    except json.JSONDecodeError as error:
        raise s.BusinessError("Invalid versions JSON") from error
    project = s.project(db, args.get("project_key"))
    created, failed = [], []
    for index, entry in enumerate(s.array(entries, "versions")):
        try:
            created.append(insert_version(db, project, s.obj(entry, "version")))
        except s.BusinessError as error:
            failed.append({"index": index, "error": str(error)})
    return {"created": created, "failed": failed}


@s.handler(write=True)
def update_version(db, args, step, clock):
    row = version_row(db, args.get("version_id"))
    data = version_data(args, row["data"])
    try:
        db.connection.execute(
            "UPDATE jira_versions SET name=?,data=? WHERE id=?",
            (data["name"], json.dumps(data), row["id"]),
        )
    except sqlite3.IntegrityError as error:
        raise s.BusinessError(f"Version {data['name']} already exists") from error
    return public_version({"id": row["id"], "data": data})


def validate_fixtures(world):
    projects = {project["key"]: project for project in world.jira_projects}
    for project in projects.values():
        if "archived" in project and type(project["archived"]) is not bool:
            raise s.BusinessError("Project archived flag must be boolean")
        fields = project_fields(project)
        identities = set()
        for field in fields:
            identity = s.text(field.get("id"), "field id")
            s.text(field.get("name"), "field name")
            if identity in identities:
                raise s.BusinessError("Duplicate project field")
            identities.add(identity)
        options = s.obj(project.get("field_options", {}), "field_options")
        if any(field not in identities for field in options):
            raise s.BusinessError("Options reference an unknown project field")
        for values in options.values():
            for option in s.array(values, "field options"):
                s.text(s.obj(option, "field option").get("value"), "option value")
    seen = set()
    for item in world.jira_versions:
        identity = item.get("id")
        if (
            type(identity) is not int
            or identity <= 0
            or identity in seen
            or item.get("project_key") not in projects
        ):
            raise s.BusinessError("Invalid version fixture")
        version_data(item)
        seen.add(identity)


def seed(db, world):
    projects = {project["key"]: project for project in world.jira_projects}
    for item in world.jira_versions:
        data = version_data(item)
        db.connection.execute(
            "INSERT INTO jira_versions(id,project_id,name,data) VALUES (?,?,?,?)",
            (
                item["id"],
                projects[item["project_key"]]["id"],
                data["name"],
                json.dumps(data),
            ),
        )


HANDLERS = {
    "jira_search_fields": search_fields,
    "jira_get_field_options": get_field_options,
    "jira_get_project_issue_types": get_project_issue_types,
    "jira_get_create_fields": get_create_fields,
    "jira_get_project_versions": get_project_versions,
    "jira_get_project_components": get_project_components,
    "jira_get_all_projects": get_all_projects,
    "jira_search_projects": search_projects,
    "jira_get_project_fields": get_project_fields,
    "jira_create_version": create_version,
    "jira_batch_create_versions": batch_create_versions,
    "jira_update_version": update_version,
}
