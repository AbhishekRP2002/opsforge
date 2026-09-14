"""Explicit directed links, epic parents and finite fixture workflows."""

import json
from itertools import pairwise

from . import jira_relations as a
from . import jira_store as s


def status_snapshot(metadata, status):
    return dict(s.named(metadata["statuses"], status, "status"))


def is_epic(db, record):
    return (
        s.named(
            s.project(db, record["data"]["project_key"])["issue_types"],
            record["data"]["issue_type"],
            "issue_type",
        )["name"].casefold()
        == "epic"
    )


def initial_history(db, record):
    status = status_snapshot(
        s.project(db, record["data"]["project_key"]), record["data"]["status"]
    )
    db.connection.execute(
        "INSERT INTO jira_status_history(issue_id,status,entered) VALUES (?,?,?)",
        (
            record["id"],
            json.dumps(status),
            a.timestamp(record["data"]["created"], "created"),
        ),
    )


def transitions(db, record):
    current = status_snapshot(
        s.project(db, record["data"]["project_key"]), record["data"]["status"]
    )["name"]
    return [
        json.loads(row[0])
        for row in db.connection.execute(
            "SELECT data FROM jira_transitions WHERE project_id=? ORDER BY id",
            (record["project_id"],),
        )
        if json.loads(row[0])["from_status"] == current
    ]


def available(db, record):
    return [
        {k: t[k] for k in ("id", "name", "to_status")} for t in transitions(db, record)
    ]


def changelogs(db, record):
    visits = list(
        db.connection.execute(
            "SELECT * FROM jira_status_history WHERE issue_id=? ORDER BY id",
            (record["id"],),
        )
    )
    return [
        {
            "id": str(row["id"]),
            "created": row["entered"],
            "author": s.public_user(s.user_by_id(db, row["author_id"]))
            if row["author_id"]
            else None,
            "items": [
                {
                    "field": "status",
                    "from": json.loads(previous["status"])["id"],
                    "from_string": json.loads(previous["status"])["name"],
                    "to": json.loads(row["status"])["id"],
                    "to_string": json.loads(row["status"])["name"],
                }
            ],
        }
        for previous, row in pairwise(visits)
    ]


@s.handler()
def get_transitions(db, args, step, clock):
    return available(db, s.issue(db, args.get("issue_key")))


def transition_record(db, record, transition_id, clock, *, fields=None, comment=None):
    from .jira_core import projection

    identifier = s.text(transition_id, "transition_id")
    choices = transitions(db, record)
    matches = [t for t in choices if t["id"] == identifier]
    if not matches:
        matches = [t for t in choices if t["name"].casefold() == identifier.casefold()]
    if len(matches) != 1:
        raise s.BusinessError("Transition is not available from the current status")
    selected = matches[0]
    changes = {
        k: v
        for k, v in s.obj(fields if fields is not None else {}, "fields").items()
        if v is not None
    }
    if {
        "id",
        "key",
        "project_id",
        "parent_id",
        "project_key",
        "created",
        "updated",
        "status",
        "issue_type",
    }.intersection(changes):
        raise s.BusinessError(
            "Transition fields cannot override identity or workflow status"
        )
    if "assignee" in changes:
        value = changes["assignee"]
        if isinstance(value, str):
            try:
                assigned = s.resolve_assignee(db, value)
            except s.UnresolvedIdentity:
                # Source sanitizer skips unresolved string assignees.
                del changes["assignee"]
            else:
                if assigned is not None:
                    s.validate_assignment(assigned, record["data"]["project_key"])
                changes["assignee"] = assigned["id"] if assigned is not None else None
        else:
            changes["assignee"] = s.assignee(db, value, record["data"]["project_key"])
    a.optional_text(comment, "comment")
    if comment and a.guarded(db, record):
        raise s.BusinessError(
            "Transition comments are blocked for internal-only projects"
        )
    metadata = s.project(db, record["data"]["project_key"])
    data = record["data"] | changes | {"status": selected["to_status"]}
    target = status_snapshot(metadata, selected["to_status"])
    if target.get("category", {}).get("key") == "done" or target["name"].casefold() in (
        "done",
        "closed",
        "resolved",
    ):
        data["resolutiondate"] = s.now(db, clock)
    else:
        data.pop("resolutiondate", None)
        data.pop("resolution", None)
    s.validate_fields(data, metadata)
    u = a.author(db)
    record["data"] = data
    a.touch(db, record, clock)
    db.connection.execute(
        "UPDATE jira_status_history SET exited=? WHERE issue_id=? AND exited IS NULL",
        (s.now(db, clock), record["id"]),
    )
    db.connection.execute(
        "INSERT INTO jira_status_history(issue_id,status,entered,author_id,transition_id) VALUES (?,?,?,?,?)",
        (record["id"], json.dumps(target), s.now(db, clock), u["id"], selected["id"]),
    )
    if comment:
        a.add_comment_record(db, record, comment, clock)
    return projection(db, record)


@s.handler(write=True)
def transition_issue(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    result = transition_record(
        db,
        record,
        args.get("transition_id"),
        clock,
        fields=s.json_object(args.get("fields"), "fields"),
        comment=args.get("comment"),
    )
    return {
        "message": f"Issue {record['key']} transitioned successfully",
        "issue": result,
    }


def link_types(db):
    return [
        json.loads(row[0])
        for row in db.connection.execute("SELECT data FROM jira_link_types ORDER BY id")
    ]


@s.handler()
def get_link_types(db, args, step, clock):
    value = a.optional_text(args.get("name_filter"), "name_filter")
    return [
        t
        for t in link_types(db)
        if value is None or value.casefold() in t["name"].casefold()
    ]


def local_links(db, record):
    result = []
    for row in db.connection.execute(
        "SELECT * FROM jira_issue_links WHERE inward_id=? OR outward_id=? ORDER BY id",
        (record["id"], record["id"]),
    ):
        direction = "outward" if row["inward_id"] == record["id"] else "inward"
        target = db.connection.execute(
            "SELECT * FROM jira_issues WHERE id=?", (row[direction + "_id"],)
        ).fetchone()
        data = json.loads(target["data"])
        s.project(db, data["project_key"])
        result.append(
            {
                "id": str(row["id"]),
                "type": next(t for t in link_types(db) if t["id"] == row["type_id"]),
                direction + "_issue": {
                    "id": str(target["id"]),
                    "key": target["key"],
                    "fields": {
                        "summary": data["summary"],
                        "status": {"name": data["status"]},
                        "issuetype": {"name": data["issue_type"]},
                    },
                },
            }
        )
    return result


def remote_links(db, record):
    return [
        json.loads(row["data"]) | {"id": str(row["id"])}
        for row in db.connection.execute(
            "SELECT * FROM jira_remote_links WHERE issue_id=? ORDER BY id",
            (record["id"],),
        )
    ]


@s.handler(write=True)
def create_issue_link(db, args, step, clock):
    inward = s.issue(db, args.get("inward_issue_key"))
    outward = s.issue(db, args.get("outward_issue_key"))
    kind = s.named(link_types(db), args.get("link_type"), "link_type")
    if inward["id"] == outward["id"]:
        raise s.BusinessError("Self links are unsupported")
    comment = a.optional_text(args.get("comment"), "comment")
    vis = a.visibility(args.get("comment_visibility"))
    if comment:
        if a.guarded(db, inward) or a.guarded(db, outward):
            raise s.BusinessError(
                "Link comments are blocked for internal-only projects"
            )
        a.add_comment_record(db, inward, comment, clock, visibility_value=vis)
    db.connection.execute(
        "INSERT INTO jira_issue_links(type_id,inward_id,outward_id) VALUES (?,?,?)",
        (kind["id"], inward["id"], outward["id"]),
    )
    return {
        "success": True,
        "message": f"Link created between {inward['key']} and {outward['key']}",
        "link_type": kind["name"],
        "inward_issue": inward["key"],
        "outward_issue": outward["key"],
    }


@s.handler(write=True)
def create_remote_issue_link(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    obj: dict = {
        "url": s.text(args.get("url"), "url"),
        "title": s.text(args.get("title"), "title"),
    }
    for key in ("summary", "relationship", "icon_url"):
        a.optional_text(args.get(key), key)
    if args.get("summary"):
        obj["summary"] = args["summary"]
    if args.get("icon_url"):
        obj["icon"] = {"url16x16": args["icon_url"], "title": obj["title"]}
    data = {"object": obj}
    if args.get("relationship"):
        data["relationship"] = args["relationship"]
    db.connection.execute(
        "INSERT INTO jira_remote_links(issue_id,data) VALUES (?,?)",
        (record["id"], json.dumps(data)),
    )
    return {
        "success": True,
        "message": f"Remote link created for issue {record['key']}",
        "issue_key": record["key"],
        "link_title": obj["title"],
        "link_url": obj["url"],
        "relationship": args.get("relationship") or "",
    }


@s.handler(write=True)
def remove_issue_link(db, args, step, clock):
    identifier = s.text(args.get("link_id"), "link_id")
    row = db.connection.execute(
        "SELECT inward_id,outward_id FROM jira_issue_links WHERE id=?", (identifier,)
    ).fetchone()
    if row is None:
        raise s.BusinessError("Issue link not found")
    for i in row:
        key = db.connection.execute(
            "SELECT key FROM jira_issues WHERE id=?", (i,)
        ).fetchone()[0]
        s.issue(db, key)
    db.connection.execute("DELETE FROM jira_issue_links WHERE id=?", (identifier,))
    return {
        "success": True,
        "message": f"Link with ID {identifier} has been removed",
        "link_id": identifier,
    }


@s.handler(write=True)
def link_to_epic(db, args, step, clock):
    from .jira_core import projection

    record = s.issue(db, args.get("issue_key"))
    parent = s.issue(db, args.get("epic_key"))
    if not is_epic(db, parent):
        raise s.BusinessError("Parent must be an Epic")
    current = parent["id"]
    while current is not None:
        if current == record["id"]:
            raise s.BusinessError("Cyclic epic parent")
        current = db.connection.execute(
            "SELECT parent_id FROM jira_issues WHERE id=?", (current,)
        ).fetchone()[0]
    kind = s.named(
        s.project(db, record["data"]["project_key"])["issue_types"],
        record["data"]["issue_type"],
        "issue_type",
    )
    if kind.get("subtask"):
        raise s.BusinessError("Subtasks cannot directly become epic children")
    record["parent_id"] = parent["id"]
    a.touch(db, record, clock)
    return {
        "message": f"Issue {record['key']} has been linked to epic {parent['key']}.",
        "issue": projection(db, record, "*all"),
    }


def validate_fixtures(world):
    projects = {p["key"]: p for p in world.jira_projects}
    issues = {r["id"]: r for r in world.jira_issues}
    users = {u["id"] for u in world.jira_users}
    types = set()
    names = set()
    for row in world.jira_link_types:
        for field in ("id", "name", "inward", "outward"):
            s.text(row.get(field), field)
        if row["id"] in types or row["name"] in names:
            raise s.BusinessError("Duplicate link type")
        types.add(row["id"])
        names.add(row["name"])
    for records in (world.jira_issue_links, world.jira_remote_links):
        seen = set()
        for row in records:
            i = a.identity(row.get("id"), "link id")
            if i in seen:
                raise s.BusinessError("Duplicate link id")
            seen.add(i)
            if records is world.jira_issue_links:
                if (
                    a.identity(row.get("inward_id"), "inward issue") not in issues
                    or a.identity(row.get("outward_id"), "outward issue") not in issues
                    or row["inward_id"] == row["outward_id"]
                    or s.text(row.get("type_id"), "type reference") not in types
                ):
                    raise s.BusinessError("Invalid link references")
            else:
                if a.identity(row.get("issue_id"), "issue reference") not in issues:
                    raise s.BusinessError("Invalid remote issue reference")
                obj = s.obj(row.get("object"), "remote object")
                s.text(obj.get("url"), "url")
                s.text(obj.get("title"), "title")
                a.optional_text(obj.get("summary"), "summary")
                a.optional_text(row.get("relationship"), "relationship")
                if "icon" in obj:
                    icon = s.obj(obj["icon"], "icon")
                    s.text(icon.get("url16x16"), "icon URL")
                    s.text(icon.get("title"), "icon title")
    seen = set()
    for row in world.jira_transitions:
        key = s.text(row.get("project_key"), "transition project")
        i = s.text(row.get("id"), "transition id")
        s.text(row.get("name"), "transition name")
        if key not in projects or (key, i) in seen:
            raise s.BusinessError("Invalid transition identity/project")
        seen.add((key, i))
        for field in ("from_status", "to_status"):
            status = s.named(projects[key]["statuses"], row.get(field), field)
            row[field] = status["name"]
    histories = {}
    for row in world.jira_status_history:
        i = a.identity(row.get("issue_id"), "history issue")
        if i not in issues:
            raise s.BusinessError("Unknown history issue")
        status = s.obj(row.get("status"), "history status")
        expected = status_snapshot(
            projects[issues[i]["data"]["project_key"]], status.get("id")
        )
        if status != expected:
            raise s.BusinessError(
                "History status must preserve configured identity/category"
            )
        row["entered"] = a.timestamp(row.get("entered"), "entered")
        if row.get("exited") is not None:
            row["exited"] = a.timestamp(row["exited"], "exited")
            if row["exited"] < row["entered"]:
                raise s.BusinessError("History exit precedes entry")
        if (
            row.get("author_id") is not None
            and s.text(row["author_id"], "history author") not in users
        ):
            raise s.BusinessError("Unknown history author")
        a.optional_text(row.get("transition_id"), "transition_id")
        histories.setdefault(i, []).append(row)
    for i, rows in histories.items():
        rows.sort(key=lambda r: r["entered"])
        if (
            rows[0]["entered"] != a.timestamp(issues[i]["data"]["created"], "created")
            or rows[-1].get("exited") is not None
            or rows[-1]["status"]["name"]
            != status_snapshot(
                projects[issues[i]["data"]["project_key"]], issues[i]["data"]["status"]
            )["name"]
            or rows[-1]["entered"]
            > a.timestamp(issues[i]["data"]["updated"], "updated")
        ):
            raise s.BusinessError("History must cover creation through current status")
        for prev, row in pairwise(rows):
            if prev.get("exited") != row["entered"]:
                raise s.BusinessError("History visits must be contiguous and ordered")


def seed(db, world):
    for row in world.jira_link_types:
        db.connection.execute(
            "INSERT INTO jira_link_types VALUES (?,?)", (row["id"], json.dumps(row))
        )
    for row in world.jira_issue_links:
        db.connection.execute(
            "INSERT INTO jira_issue_links VALUES (?,?,?,?)",
            (row["id"], row["type_id"], row["inward_id"], row["outward_id"]),
        )
    for row in world.jira_remote_links:
        data = {k: row[k] for k in ("object", "relationship") if k in row}
        db.connection.execute(
            "INSERT INTO jira_remote_links VALUES (?,?,?)",
            (row["id"], row["issue_id"], json.dumps(data)),
        )
    for row in world.jira_transitions:
        project = next(p for p in world.jira_projects if p["key"] == row["project_key"])
        db.connection.execute(
            "INSERT INTO jira_transitions VALUES (?,?,?)",
            (row["id"], project["id"], json.dumps(row)),
        )
    for row in world.jira_issues:
        visits = sorted(
            [v for v in world.jira_status_history if v["issue_id"] == row["id"]],
            key=lambda v: v["entered"],
        )
        if not visits:
            # Seed ignores the runtime project allowlist; fixture validation already ran.
            metadata = next(
                p for p in world.jira_projects if p["key"] == row["data"]["project_key"]
            )
            visits = [
                {
                    "status": status_snapshot(metadata, row["data"]["status"]),
                    "entered": a.timestamp(row["data"]["created"], "created"),
                }
            ]
        for visit in visits:
            db.connection.execute(
                "INSERT INTO jira_status_history(issue_id,status,entered,exited,author_id,transition_id) VALUES (?,?,?,?,?,?)",
                (
                    row["id"],
                    json.dumps(visit["status"]),
                    visit["entered"],
                    visit.get("exited"),
                    visit.get("author_id"),
                    visit.get("transition_id"),
                ),
            )


HANDLERS = {
    "jira_get_transitions": get_transitions,
    "jira_transition_issue": transition_issue,
    "jira_get_link_types": get_link_types,
    "jira_create_issue_link": create_issue_link,
    "jira_create_remote_issue_link": create_remote_issue_link,
    "jira_remove_issue_link": remove_issue_link,
    "jira_link_to_epic": link_to_epic,
}
