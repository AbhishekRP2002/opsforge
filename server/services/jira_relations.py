"""Issue activity with stable references; helpers never own Episode accounting."""

import json
import re
from datetime import UTC, datetime

from . import jira_store as s


def timestamp(value, field):
    try:
        date = datetime.fromisoformat(s.text(value, field))
        if date.tzinfo is None:
            raise s.BusinessError(f"{field} requires a timezone")
        return date.astimezone(UTC).isoformat()
    except (ValueError, OverflowError) as error:
        raise s.BusinessError(f"Invalid {field} timestamp") from error


def identity(value, field):
    if type(value) is not int or not 1 <= value <= 1_000_000_000:
        raise s.BusinessError(f"{field} requires a bounded positive integer")
    return value


def optional_text(value, field):
    if value is not None and not isinstance(value, str):
        raise s.BusinessError(f"{field} must be text")
    return value


def visibility(value):
    if value is None or isinstance(value, str) and not value.strip():
        return None
    try:
        parsed = json.loads(s.text(value, "visibility"))
    except json.JSONDecodeError as error:
        raise s.BusinessError("Invalid visibility JSON") from error
    return validate_visibility(parsed)


def validate_visibility(value):
    if value is None:
        return None
    s.obj(value, "visibility")
    if set(value) - {"type", "value"}:
        raise s.BusinessError("Unsupported visibility fields")
    kind = s.text(value.get("type"), "visibility type")
    if kind not in ("group", "role"):
        raise s.BusinessError("Visibility type must be group or role")
    s.text(value.get("value"), "visibility value")
    return dict(value)


def duration(value, field, *, zero=False):
    value = s.text(value, field).strip()
    if len(value) > 128 or not re.fullmatch(
        r"(?:[0-9]+[wdhms]\s*)+|[0-9]+(?:\.[0-9]+)?", value
    ):
        raise s.BusinessError(f"Invalid finite {field} duration")
    units = {"w": 604800, "d": 86400, "h": 3600, "m": 60, "s": 1}
    parts = re.findall(r"([0-9]+)([wdhms])", value)
    seconds = sum(int(n) * units[u] for n, u in parts) if parts else int(float(value))
    if not (0 if zero else 1) <= seconds <= 1_000_000_000:
        raise s.BusinessError(f"{field} duration outside finite profile")
    return seconds


def guarded(db, record):
    return record["data"]["project_key"] in s.config(db)["jira_internal_only_projects"]


def request_issue(db, record):
    return (
        db.connection.execute(
            "SELECT 1 FROM jira_request_issues WHERE issue_id=?", (record["id"],)
        ).fetchone()
        is not None
    )


def author(db):
    identifier = s.config(db)["jira_current_user"]
    if identifier is None:
        raise s.BusinessError("Current Jira user is not configured")
    result = s.user_by_id(db, identifier)
    if not result["active"]:
        raise s.BusinessError("Current Jira user is inactive")
    return result


def touch(db, record, clock):
    current = s.now(db, clock)
    if current < timestamp(record["data"]["updated"], "updated"):
        raise s.BusinessError("Mutation timestamp precedes issue update")
    record["data"]["updated"] = current
    s.save(db, record)


def watchers(db, record):
    ids = [
        r[0]
        for r in db.connection.execute(
            "SELECT user_id FROM jira_watchers WHERE issue_id=? ORDER BY user_id",
            (record["id"],),
        )
    ]
    return {
        "issue_key": record["key"],
        "watcher_count": len(ids),
        "is_watching": s.config(db)["jira_current_user"] in ids,
        "watchers": [s.public_user(s.user_by_id(db, i)) for i in ids],
    }


def watcher_user(db, value):
    value = s.text(value, "watcher identity")
    if s.config(db)["jira_edition"] == "cloud":
        return s.user_by_id(db, value)
    users = [
        json.loads(row[0])
        for row in db.connection.execute("SELECT data FROM jira_users ORDER BY id")
    ]
    matches = [u for u in users if u["name"] == value]
    if len(matches) != 1:
        raise s.BusinessError("Unknown or ambiguous watcher username")
    return matches[0]


@s.handler()
def get_issue_watchers(db, args, step, clock):
    return watchers(db, s.issue(db, args.get("issue_key")))


@s.handler(write=True)
def add_watcher(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    u = watcher_user(db, args.get("user_identifier"))
    s.validate_assignment(u, record["data"]["project_key"])
    db.connection.execute(
        "INSERT OR IGNORE INTO jira_watchers VALUES (?,?)", (record["id"], u["id"])
    )
    return {
        "success": True,
        "message": f"User '{args['user_identifier']}' added as watcher to {record['key']}",
        "issue_key": record["key"],
        "user": args["user_identifier"],
    }


@s.handler(write=True)
def remove_watcher(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    field, other = (
        ("account_id", "username")
        if s.config(db)["jira_edition"] == "cloud"
        else ("username", "account_id")
    )
    if args.get(other) is not None:
        raise s.BusinessError(f"This edition requires {field}, not {other}")
    u = watcher_user(db, args.get(field))
    db.connection.execute(
        "DELETE FROM jira_watchers WHERE issue_id=? AND user_id=?",
        (record["id"], u["id"]),
    )
    return {
        "success": True,
        "message": f"User '{args[field]}' removed from watching {record['key']}",
        "issue_key": record["key"],
        "user": args[field],
    }


def comments(db, record, limit=10):
    if type(limit) is not int or not 0 <= limit <= 100:
        raise s.BusinessError("comment_limit must be between 0 and 100")
    return [
        json.loads(row["data"])
        | {
            "id": str(row["id"]),
            "author": s.user_by_id(db, row["author_id"])["display_name"],
        }
        for row in db.connection.execute(
            "SELECT * FROM jira_comments WHERE issue_id=? ORDER BY id LIMIT ?",
            (record["id"], limit),
        )
    ]


def add_comment_record(db, record, body, clock, *, visibility_value=None, public=None):
    """Client-level helper; caller chooses source server public=False normalization."""
    s.text(body, "body")
    vis = validate_visibility(visibility_value)
    if public is not None and type(public) is not bool:
        raise s.BusinessError("public must be boolean")
    is_request = request_issue(db, record)
    if guarded(db, record):
        if not is_request:
            public = None
        elif public is not False:
            raise s.BusinessError("Internal-only request requires public=False")
    if public is not None and (vis is not None or not is_request):
        raise s.BusinessError(
            "public requires a JSM request and cannot combine with visibility"
        )
    u = author(db)
    touch(db, record, clock)
    data = {"body": body, "created": s.now(db, clock), "updated": s.now(db, clock)}
    if vis is not None:
        data["visibility"] = vis
    if public is not None:
        data["public"] = public
    cursor = db.connection.execute(
        "INSERT INTO jira_comments(issue_id,author_id,data) VALUES (?,?,?)",
        (record["id"], u["id"], json.dumps(data)),
    )
    return {
        "id": str(cursor.lastrowid),
        "body": body,
        "created": data["created"],
        "author": u["display_name"],
    } | ({"public": public} if public is not None else {})


@s.handler(write=True)
def add_comment(db, args, step, clock):
    args = dict(args)
    if ("body" in args) == ("comment" in args):
        raise s.BusinessError("Supply exactly one of body or comment")
    if "comment" in args:
        s.text(args["comment"], "comment")
        args.setdefault("body", args["comment"])
    record = s.issue(db, args.get("issue_key"))
    public = args.get("public")
    if public is False and not guarded(db, record):
        public = None
    return add_comment_record(
        db,
        record,
        args.get("body"),
        clock,
        visibility_value=visibility(args.get("visibility")),
        public=public,
    )


@s.handler(write=True)
def edit_comment(db, args, step, clock):
    if "comment" in args:
        raise s.BusinessError("edit_comment accepts body only")
    record = s.issue(db, args.get("issue_key"))
    body = s.text(args.get("body"), "body")
    row = db.connection.execute(
        "SELECT * FROM jira_comments WHERE id=? AND issue_id=?",
        (s.text(args.get("comment_id"), "comment_id"), record["id"]),
    ).fetchone()
    if row is None:
        raise s.BusinessError("Comment not found on this issue")
    data = json.loads(row["data"])
    if guarded(db, record) and data.get("public") is not False:
        raise s.BusinessError("Cannot verify an internal comment; edit refused")
    vis = visibility(args.get("visibility"))
    if vis is not None:
        data["visibility"] = vis
    data.update(body=body, updated=s.now(db, clock))
    touch(db, record, clock)
    db.connection.execute(
        "UPDATE jira_comments SET data=? WHERE id=?", (json.dumps(data), row["id"])
    )
    return {
        "id": str(row["id"]),
        "body": body,
        "updated": data["updated"],
        "author": s.user_by_id(db, row["author_id"])["display_name"],
    }


def worklogs(db, record):
    return [
        json.loads(row["data"])
        | {
            "id": str(row["id"]),
            "author": s.user_by_id(db, row["author_id"])["display_name"],
        }
        for row in db.connection.execute(
            "SELECT * FROM jira_worklogs WHERE issue_id=? ORDER BY id", (record["id"],)
        )
    ]


def tracking(db, record):
    row = db.connection.execute(
        "SELECT * FROM jira_estimates WHERE issue_id=?", (record["id"],)
    ).fetchone()
    result = {
        "timeSpentSeconds": sum(
            log["time_spent_seconds"] for log in worklogs(db, record)
        )
    }
    if row:
        for field, key in (
            ("original_seconds", "originalEstimateSeconds"),
            ("remaining_seconds", "remainingEstimateSeconds"),
        ):
            if row[field] is not None:
                result[key] = row[field]
    return result


def add_worklog_record(db, record, args, clock):
    seconds = duration(args.get("time_spent"), "time_spent")
    estimates = {
        k: duration(args[k], k, zero=True)
        for k in ("original_estimate", "remaining_estimate")
        if args.get(k) is not None
    }
    started = (
        timestamp(args["started"], "started")
        if args.get("started") is not None
        else s.now(db, clock)
    )
    comment = optional_text(args.get("comment"), "comment") or ""
    u = author(db)
    touch(db, record, clock)
    data = {
        "comment": comment,
        "started": started,
        "created": s.now(db, clock),
        "updated": s.now(db, clock),
        "time_spent": args["time_spent"],
        "time_spent_seconds": seconds,
    }
    cursor = db.connection.execute(
        "INSERT INTO jira_worklogs(issue_id,author_id,data) VALUES (?,?,?)",
        (record["id"], u["id"], json.dumps(data)),
    )
    if estimates:
        db.connection.execute(
            "INSERT OR IGNORE INTO jira_estimates(issue_id) VALUES (?)", (record["id"],)
        )
        if "original_estimate" in estimates:
            db.connection.execute(
                "UPDATE jira_estimates SET original_seconds=? WHERE issue_id=?",
                (estimates["original_estimate"], record["id"]),
            )
        if "remaining_estimate" in estimates:
            db.connection.execute(
                "UPDATE jira_estimates SET remaining_seconds=? WHERE issue_id=?",
                (estimates["remaining_estimate"], record["id"]),
            )
    if "remaining_estimate" not in estimates:
        db.connection.execute(
            "UPDATE jira_estimates SET remaining_seconds=max(0,remaining_seconds-?) WHERE issue_id=? AND remaining_seconds IS NOT NULL",
            (seconds, record["id"]),
        )
    return data | {
        "id": str(cursor.lastrowid),
        "author": u["display_name"],
        "original_estimate_updated": "original_estimate" in estimates,
        "remaining_estimate_updated": "remaining_estimate" in estimates,
    }


@s.handler()
def get_worklog(db, args, step, clock):
    return {"worklogs": worklogs(db, s.issue(db, args.get("issue_key")))}


@s.handler(write=True)
def add_worklog(db, args, step, clock):
    return {
        "message": "Worklog added successfully",
        "worklog": add_worklog_record(
            db, s.issue(db, args.get("issue_key")), args, clock
        ),
    }


def validate_fixtures(world):
    for records in (
        world.jira_watchers,
        world.jira_comments,
        world.jira_worklogs,
        world.jira_link_types,
        world.jira_issue_links,
        world.jira_remote_links,
        world.jira_transitions,
        world.jira_status_history,
        world.jira_boards,
        world.jira_sprints,
        world.jira_sprint_issues,
    ):
        try:
            json.dumps(records, allow_nan=False)
        except (ValueError, TypeError) as error:
            raise s.BusinessError(
                "Jira relation fixtures require finite JSON values"
            ) from error
    issues = {r["id"]: r for r in world.jira_issues}
    users = {u["id"]: u for u in world.jira_users}
    projects = {p["key"] for p in world.jira_projects}
    if any(p not in projects for p in world.jira_internal_only_projects):
        raise s.BusinessError("Unknown internal-only project")
    seen = set()
    for i in world.jira_request_issue_ids:
        if identity(i, "request issue") not in issues or i in seen:
            raise s.BusinessError("Unknown or duplicate request issue")
        seen.add(i)
    seen = set()
    for row in world.jira_watchers:
        i = identity(row.get("issue_id"), "watcher issue")
        u = s.text(row.get("user_id"), "watcher user")
        if i not in issues or u not in users or (i, u) in seen:
            raise s.BusinessError("Invalid watcher reference")
        s.validate_assignment(users[u], issues[i]["data"]["project_key"])
        seen.add((i, u))
    for kind, records in (
        ("comment", world.jira_comments),
        ("worklog", world.jira_worklogs),
    ):
        seen = set()
        for row in records:
            i = identity(row.get("id"), kind)
            parent = identity(row.get("issue_id"), "issue reference")
            u = s.text(row.get("author_id"), "author reference")
            if i in seen or parent not in issues or u not in users:
                raise s.BusinessError("Invalid activity identity/reference")
            seen.add(i)
            created = timestamp(row.get("created"), "created")
            updated = timestamp(row.get("updated"), "updated")
            if (
                updated < created
                or created < timestamp(issues[parent]["data"]["created"], "created")
                or updated > timestamp(issues[parent]["data"]["updated"], "updated")
            ):
                raise s.BusinessError("Invalid activity chronology")
            if kind == "comment":
                s.text(row.get("body"), "body")
                validate_visibility(row.get("visibility"))
                if "public" in row and (
                    type(row["public"]) is not bool
                    or parent not in world.jira_request_issue_ids
                    or row.get("visibility") is not None
                ):
                    raise s.BusinessError("Invalid fixture public comment")
            else:
                duration(row.get("time_spent"), "time_spent")
                timestamp(row.get("started"), "started")
                optional_text(row.get("comment"), "comment")


def seed(db, world):
    db.connection.executemany(
        "INSERT INTO jira_request_issues VALUES (?)",
        [(i,) for i in world.jira_request_issue_ids],
    )
    db.connection.executemany(
        "INSERT INTO jira_watchers VALUES (?,?)",
        [(r["issue_id"], r["user_id"]) for r in world.jira_watchers],
    )
    for row in world.jira_comments:
        data = {
            k: row[k]
            for k in ("body", "created", "updated", "visibility", "public")
            if k in row
        }
        db.connection.execute(
            "INSERT INTO jira_comments VALUES (?,?,?,?)",
            (row["id"], row["issue_id"], row["author_id"], json.dumps(data)),
        )
    for row in world.jira_worklogs:
        data = {
            k: row[k]
            for k in ("comment", "created", "updated", "started", "time_spent")
            if k in row
        }
        data["time_spent_seconds"] = duration(row["time_spent"], "time_spent")
        db.connection.execute(
            "INSERT INTO jira_worklogs VALUES (?,?,?,?)",
            (row["id"], row["issue_id"], row["author_id"], json.dumps(data)),
        )


HANDLERS = {
    "jira_get_issue_watchers": get_issue_watchers,
    "jira_add_watcher": add_watcher,
    "jira_remove_watcher": remove_watcher,
    "jira_add_comment": add_comment,
    "jira_edit_comment": edit_comment,
    "jira_get_worklog": get_worklog,
    "jira_add_worklog": add_worklog,
}
