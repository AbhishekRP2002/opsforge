"""Explicit unmounted issue and user handlers; Episode integration follows in 6d."""

import json

from . import jira_store as s

DEFAULT_FIELDS = "summary,description,status,assignee,reporter,labels,versions,priority,created,updated,issuetype"


def custom_value(value):
    if isinstance(value, list):
        return [custom_value(item) for item in value]
    if isinstance(value, dict):
        if "value" in value:
            return value["value"]
        if "name" in value and "self" in value:
            return value["name"]
    return value


def projection(db, record, fields=DEFAULT_FIELDS, use_display_names=False):
    data = record["data"]
    metadata = s.project(db, data["project_key"])
    selected = (
        [field.strip() for field in fields.split(",")] if fields != "*all" else None
    )
    result = {"id": str(record["id"]), "key": record["key"]}
    mapping = {"issue_type": "issuetype", "project_key": "project"}
    for name, value in data.items():
        wire = mapping.get(name, name)
        if selected is not None and wire not in [f.strip() for f in selected]:
            continue
        if name == "project_key":
            result["project"] = {k: metadata[k] for k in ("id", "key", "name")}
        elif name in ("issue_type", "status"):
            result[name] = {
                "name": s.named(
                    metadata["issue_types" if name == "issue_type" else "statuses"],
                    value,
                    name,
                )["name"]
            }
        elif name == "assignee":
            result[name] = (
                s.public_user(s.user_by_id(db, value))
                if value
                else {"display_name": "Unassigned"}
            )
        elif name.startswith("customfield_"):
            label = metadata["field_names"][name]
            result[label if use_display_names else name] = {
                "value": custom_value(value),
                **({"field_id": name} if use_display_names else {"name": label}),
            }
        elif value is not None:
            result[name] = value
    if record["parent_id"] is not None and (selected is None or "parent" in selected):
        parent = db.connection.execute(
            "SELECT id,key FROM jira_issues WHERE id=?", (record["parent_id"],)
        ).fetchone()
        result["parent"] = {"id": str(parent["id"]), "key": parent["key"]}
    from . import jira_relations as activity
    from . import jira_workflow as workflow

    if selected is None or "timetracking" in selected:
        result["timetracking"] = activity.tracking(db, record)
    if selected is None or "comment" in selected:
        result["comments"] = activity.comments(db, record)
    if selected is None or "worklog" in selected:
        result["worklogs"] = activity.worklogs(db, record)
    if selected is None or "issuelinks" in selected:
        result["issuelinks"] = workflow.local_links(db, record)
    if selected is None or "sprint" in selected:
        from .jira_agile import member_sprint

        result["sprint"] = member_sprint(db, record)
    return result


def prepare_issue(db, args, clock, *, batch=False):
    from .jira_workflow import is_epic

    args = s.obj(args, "issue")
    p = s.project(db, args.get("project_key"))
    extra = (
        {
            k: v
            for k, v in args.items()
            if k
            not in (
                "project_key",
                "summary",
                "issue_type",
                "description",
                "assignee",
                "components",
            )
        }
        if batch
        else s.json_object(args.get("additional_fields"), "additional_fields")
    )
    protected = {
        "id",
        "key",
        "project_id",
        "project_key",
        "parent_id",
        "created",
        "updated",
        "assignee",
        "issue_type",
        "summary",
    }
    if protected.intersection(extra):
        raise s.BusinessError(
            "Additional fields cannot replace issue identity or explicit fields"
        )
    parent = extra.pop("parent", None)
    epic = extra.pop("epicKey", extra.pop("epic_link", None))
    if epic is not None:
        if parent is not None and parent != epic:
            raise s.BusinessError("Conflicting parent and epic")
        parent = epic
    parent_row = s.issue(db, parent) if parent is not None else None
    if epic is not None and parent_row is not None and not is_epic(db, parent_row):
        raise s.BusinessError("Epic reference must identify an Epic")
    kind = s.named(p["issue_types"], args.get("issue_type"), "issue_type")
    if kind.get("subtask", False) and parent_row is None:
        raise s.BusinessError("Subtask requires a parent")
    components = args.get("components")
    if components is None:
        components = []
    if not batch and isinstance(components, str):
        components = [c.strip() for c in components.split(",") if c.strip()]
    data = {
        "project_key": p["key"],
        "summary": args.get("summary"),
        "issue_type": kind["name"],
        "status": p["statuses"][0]["name"],
        "description": args.get("description"),
        "labels": [],
        "components": components,
        "created": s.now(db, clock),
        "updated": s.now(db, clock),
    } | extra
    s.validate_fields(data, p)
    if args.get("assignee") is not None and not isinstance(args["assignee"], str):
        raise s.BusinessError("Create assignee must be a string or null")
    try:
        data["assignee"] = s.assignee(db, args.get("assignee"), p["key"])
    except s.BusinessError:
        # Pinned create helper intentionally recovers failed user resolution.
        data["assignee"] = None
    return {
        "project_id": p["id"],
        "parent_id": parent_row["id"] if parent_row else None,
        "data": data,
    }


def insert_issue(db, prepared):
    key = s.next_key(db, prepared["data"]["project_key"])
    cursor = db.connection.execute(
        "INSERT INTO jira_issues(key,project_id,parent_id,data) VALUES (?,?,?,?)",
        (
            key,
            prepared["project_id"],
            prepared["parent_id"],
            json.dumps(prepared["data"], allow_nan=False),
        ),
    )
    record = prepared | {"id": cursor.lastrowid, "key": key}
    from .jira_workflow import initial_history

    initial_history(db, record)
    return record


@s.handler(write=True)
def create_issue(db, args, step, clock):
    record = insert_issue(db, prepare_issue(db, args, clock))
    return {
        "message": "Issue created successfully",
        "issue": projection(db, record, "*all"),
    }


@s.handler()
def get_issue(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    result = projection(
        db,
        record,
        args.get("fields", DEFAULT_FIELDS),
        args.get("use_display_names", False),
    )
    from . import jira_relations as activity

    sections = {v.strip().lower() for v in (args.get("include") or "").split(",")}
    if "watchers" in sections or "all" in sections:
        result["watchers"] = activity.watchers(db, record)
    if sections.intersection({"all", "comments", "comment"}) or "comments" in result:
        result["comments"] = activity.comments(
            db, record, args.get("comment_limit", 10)
        )
    if sections.intersection({"all", "worklogs", "worklog"}):
        result["worklogs"] = activity.worklogs(db, record)
    from . import jira_workflow as workflow

    if sections.intersection({"all", "remote_links"}):
        result["remote_links"] = workflow.remote_links(db, record)
    if sections.intersection({"all", "transitions"}):
        result["transitions"] = workflow.available(db, record)
    if sections.intersection({"all", "changelog"}) or "changelog" in (
        args.get("expand") or ""
    ).split(","):
        result["changelogs"] = workflow.changelogs(db, record)
    return result


@s.handler(write=True)
def assign_issue(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    record["data"]["assignee"] = s.assignee(
        db, args.get("assignee"), record["data"]["project_key"]
    )
    record["data"]["updated"] = s.now(db, clock)
    s.save(db, record)
    return {
        "message": f"Issue {record['key']} assigned successfully",
        "issue": projection(db, record, "*all"),
    }


@s.handler(write=True)
def move_issue(db, args, step, clock):
    if s.config(db)["jira_edition"] != "cloud":
        raise s.BusinessError(
            "Cross-project issue move is only available on Jira Cloud"
        )
    record = s.issue(db, args.get("issue_key"))
    p = s.project(db, args.get("target_project_key"))
    data = record["data"] | {"project_key": p["key"]}
    s.validate_fields(data, p)
    if data.get("assignee") is not None:
        s.validate_assignment(s.user_by_id(db, data["assignee"]), p["key"])
    from .jira_agile import validate_move

    validate_move(db, record, p)
    old_key = record["key"]
    record.update(key=s.next_key(db, p["key"]), project_id=p["id"], data=data)
    s.save(db, record)
    return {
        "message": f"Issue moved successfully from {old_key} to project {p['key']}",
        "issue": projection(db, record, "*all"),
    }


@s.handler(write=True)
def delete_issue(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    if db.connection.execute(
        "SELECT 1 FROM jira_issues WHERE parent_id=?", (record["id"],)
    ).fetchone():
        raise s.BusinessError("Cannot delete an issue with children")
    db.connection.execute("DELETE FROM jira_issues WHERE id=?", (record["id"],))
    return {"message": f"Issue {record['key']} has been deleted successfully."}


@s.handler(envelope="user_identifier")
def get_user_profile(db, args, step, clock):
    return {
        "success": True,
        "user": s.public_user(s.user(db, args.get("user_identifier"))),
    }


@s.handler(envelope="query")
def search_assignable_users(db, args, step, clock):
    if bool(args.get("project_key")) == bool(args.get("issue_key")):
        raise s.BusinessError(
            "Exactly one of project_key or issue_key must be provided."
        )
    key = (
        s.issue(db, args["issue_key"])["data"]["project_key"]
        if args.get("issue_key")
        else args["project_key"]
    )
    s.project(db, key)
    query = args.get("query", "")
    if not isinstance(query, str):
        raise s.BusinessError("query must be text")
    limit = args.get("limit", 20)
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise s.BusinessError("limit must be between 1 and 1000")
    users = [
        json.loads(row[0])
        for row in db.connection.execute("SELECT data FROM jira_users ORDER BY id")
    ]
    users = [
        s.public_user(u)
        for u in users
        if u["active"]
        and key in u["project_keys"]
        and any(
            query.casefold() in u[k].casefold()
            for k in ("name", "email", "display_name")
        )
    ][:limit]
    return {"success": True, "count": len(users), "users": users}


@s.handler(write=True)
def batch_create_issues(db, args, step, clock):
    try:
        entries = json.loads(s.text(args.get("issues"), "issues"))
    except json.JSONDecodeError as error:
        raise s.BusinessError("Invalid JSON in issues") from error
    prepared = []
    for entry in s.array(entries, "issues"):
        try:
            record = prepare_issue(db, entry, clock, batch=True)
        except s.BusinessError:
            if args.get("validate_only", False) or not prepared:
                raise
            continue
        if not args.get("validate_only", False):
            prepared.append(record)
    return {
        "message": "Issues validated successfully"
        if args.get("validate_only", False)
        else "Issues created successfully",
        "issues": [
            projection(db, insert_issue(db, record), "*all") for record in prepared
        ],
    }


def search_result(db, args):
    from .jira_query import page, select

    records = select(db, args.get("jql"), args.get("projects_filter"))
    result, selected = page(db, args, records)
    return result | {
        "issues": [
            projection(
                db,
                record,
                args.get("fields", DEFAULT_FIELDS),
                args.get("use_display_names", False),
            )
            for record in selected
        ]
    }


@s.handler()
def search(db, args, step, clock):
    return search_result(db, args)


@s.handler()
def get_project_issues(db, args, step, clock):
    p = s.project(db, args.get("project_key"))
    return search_result(db, args | {"jql": f"project = {p['key']}"})


HANDLERS = {
    "jira_batch_create_issues": batch_create_issues,
    "jira_search": search,
    "jira_get_project_issues": get_project_issues,
    "jira_create_issue": create_issue,
    "jira_get_issue": get_issue,
    "jira_assign_issue": assign_issue,
    "jira_move_issue": move_issue,
    "jira_delete_issue": delete_issue,
    "jira_get_user_profile": get_user_profile,
    "jira_search_assignable_users": search_assignable_users,
}
