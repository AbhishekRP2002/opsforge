"""Fixture-backed board scopes, finite sprint lifecycle and atomic membership."""

import json
import re

from . import jira_relations as a
from . import jira_store as s


def numeric_id(value, field, *, fixture=False):
    value = s.text(value, field)
    if not re.fullmatch(r"[1-9][0-9]{0,18}", value) or int(value) > (
        999999999 if fixture else 9223372036854775807
    ):
        raise s.BusinessError(f"{field} must be a bounded positive numeric string")
    return value


def board_projects(db, board_id):
    return [
        r[0]
        for r in db.connection.execute(
            "SELECT p.key FROM jira_projects p JOIN jira_board_projects b ON p.id=b.project_id WHERE b.board_id=? ORDER BY p.key",
            (board_id,),
        )
    ]


def board(db, identifier, *, scrum=False):
    row = db.connection.execute(
        "SELECT data FROM jira_boards WHERE id=?", (s.text(identifier, "board_id"),)
    ).fetchone()
    if row is None:
        raise s.BusinessError("Board not found")
    result = json.loads(row[0])
    allowed = s.config(db)["jira_projects_filter"]
    if allowed and not set(board_projects(db, identifier)).intersection(allowed):
        raise s.BusinessError("Board projects restricted by configuration")
    if scrum and result["type"] != "scrum":
        raise s.BusinessError("Sprints require a scrum board")
    return result


def sprint(db, identifier):
    row = db.connection.execute(
        "SELECT * FROM jira_sprints WHERE id=?", (numeric_id(identifier, "sprint_id"),)
    ).fetchone()
    if row is None:
        raise s.BusinessError("Sprint not found")
    board(db, row["board_id"], scrum=True)
    return json.loads(row["data"]) | {"id": str(row["id"]), "board_id": row["board_id"]}


def public_sprint(row):
    return {
        k: row[k]
        for k in ("id", "name", "state", "start_date", "end_date", "goal")
        if row.get(k)
    }


def member_sprint(db, record):
    row = db.connection.execute(
        "SELECT sprint_id FROM jira_sprint_issues WHERE issue_id=?", (record["id"],)
    ).fetchone()
    return public_sprint(sprint(db, str(row[0]))) if row else None


def resolve_sprint(db, value):
    value = s.text(value, "sprint")
    matches = [
        str(r["id"])
        for r in db.connection.execute("SELECT * FROM jira_sprints ORDER BY id")
        if str(r["id"]) == value
        or json.loads(r["data"])["name"].casefold() == value.casefold()
    ]
    if len(matches) != 1:
        raise s.BusinessError("Unknown or ambiguous sprint")
    sprint(db, matches[0])
    return matches[0]


def bounds(args):
    start, limit = args.get("start_at", 0), args.get("limit", 10)
    if (
        type(start) is not int
        or start < 0
        or type(limit) is not int
        or not 1 <= limit <= 50
    ):
        raise s.BusinessError("Agile pagination requires start >= 0 and limit 1..50")
    return start, limit


@s.handler()
def get_agile_boards(db, args, step, clock):
    start, limit = bounds(args)
    name = a.optional_text(args.get("board_name"), "board_name")
    kind = a.optional_text(args.get("board_type"), "board_type")
    if kind is not None and kind not in ("scrum", "kanban"):
        raise s.BusinessError("Unsupported board type")
    key = args.get("project_key")
    if key is not None:
        s.project(db, key)
    allowed = s.config(db)["jira_projects_filter"]
    results = []
    for row in db.connection.execute("SELECT * FROM jira_boards ORDER BY id"):
        data = json.loads(row["data"])
        projects = board_projects(db, row["id"])
        if (
            (not allowed or set(projects).intersection(allowed))
            and (key is None or key in projects)
            and (kind is None or data["type"] == kind)
            and (name is None or name.casefold() in data["name"].casefold())
        ):
            results.append({k: data[k] for k in ("id", "name", "type")})
    return results[start : start + limit]


@s.handler()
def get_board_issues(db, args, step, clock):
    from .jira_core import DEFAULT_FIELDS, projection
    from .jira_query import select

    b = board(db, args.get("board_id"))
    start, limit = bounds(args)
    records = select(db, args.get("jql"), ",".join(board_projects(db, b["id"])))
    return {
        "total": len(records),
        "start_at": start,
        "max_results": limit,
        "issues": [
            projection(db, r, args.get("fields", DEFAULT_FIELDS))
            for r in records[start : start + limit]
        ],
    }


@s.handler()
def get_sprints_from_board(db, args, step, clock):
    b = board(db, args.get("board_id"), scrum=True)
    start, limit = bounds(args)
    state = a.optional_text(args.get("state"), "state")
    if state is not None and state not in ("future", "active", "closed"):
        raise s.BusinessError("Invalid sprint state")
    rows = [
        sprint(db, str(r[0]))
        for r in db.connection.execute(
            "SELECT id FROM jira_sprints WHERE board_id=? ORDER BY id", (b["id"],)
        )
    ]
    return [public_sprint(r) for r in rows if state is None or r["state"] == state][
        start : start + limit
    ]


@s.handler()
def get_sprint_issues(db, args, step, clock):
    from .jira_core import search_result

    row = sprint(db, args.get("sprint_id"))
    bounds(args)
    return search_result(db, args | {"jql": f"sprint={row['id']}"})


def validate_sprint(data):
    s.text(data.get("name"), "sprint name")
    state = s.text(data.get("state"), "sprint state")
    if state not in ("future", "active", "closed"):
        raise s.BusinessError("Invalid sprint state")
    a.optional_text(data.get("goal"), "goal")
    start, end = (
        a.timestamp(data.get("start_date"), "start_date"),
        a.timestamp(data.get("end_date"), "end_date"),
    )
    if start >= end:
        raise s.BusinessError("Sprint start must precede end")
    return start, end


@s.handler(write=True)
def create_sprint(db, args, step, clock):
    b = board(db, args.get("board_id"), scrum=True)
    data = {
        k: args[k] for k in ("name", "start_date", "end_date", "goal") if k in args
    } | {"state": "future"}
    start, _ = validate_sprint(data)
    if start < s.now(db, clock):
        raise s.BusinessError("Sprint start cannot be in the past")
    cursor = db.connection.execute(
        "INSERT INTO jira_sprints(board_id,data) VALUES (?,?)",
        (b["id"], json.dumps(data)),
    )
    return public_sprint(data | {"id": str(cursor.lastrowid)})


@s.handler(write=True)
def update_sprint(db, args, step, clock):
    try:
        row = sprint(db, args.get("sprint_id"))
        data = row | {
            k: args[k]
            for k in ("name", "state", "start_date", "end_date", "goal")
            if args.get(k) is not None
        }
        validate_sprint(data)
        allowed = {
            "future": ("future", "active"),
            "active": ("active", "closed"),
            "closed": ("closed",),
        }
        if data["state"] not in allowed[row["state"]]:
            raise s.BusinessError("Impossible sprint lifecycle transition")
    except s.BusinessError:
        # Source client returns None on modeled failure; server emits this literal JSON.
        return {
            "error": f"Failed to update sprint {args.get('sprint_id')}. Check logs for details."
        }
    if data != row:
        db.connection.execute(
            "UPDATE jira_sprints SET data=? WHERE id=?",
            (
                json.dumps(
                    {k: v for k, v in data.items() if k not in ("id", "board_id")}
                ),
                row["id"],
            ),
        )
    return public_sprint(data)


def issue_list(db, value):
    keys = [k.strip() for k in s.text(value, "issue_keys").split(",") if k.strip()]
    if not keys or len(keys) > 50:
        raise s.BusinessError("Supply between 1 and 50 issue keys")
    return keys, [s.issue(db, k) for k in keys]


@s.handler(write=True)
def add_issues_to_sprint(db, args, step, clock):
    row = sprint(db, args.get("sprint_id"))
    if row["state"] == "closed":
        raise s.BusinessError("Cannot assign to a closed sprint")
    keys, records = issue_list(db, args.get("issue_keys"))
    projects = board_projects(db, row["board_id"])
    if any(r["data"]["project_key"] not in projects for r in records):
        raise s.BusinessError("Issue is outside the sprint board projects")
    for record in records:
        db.connection.execute(
            "INSERT INTO jira_sprint_issues VALUES (?,?) ON CONFLICT(issue_id) DO UPDATE SET sprint_id=excluded.sprint_id",
            (record["id"], row["id"]),
        )
    return {
        "message": f"Successfully added {len(keys)} issue(s) to sprint",
        "sprint_id": row["id"],
        "issue_keys": keys,
    }


@s.handler(write=True)
def move_issues_to_backlog(db, args, step, clock):
    keys, records = issue_list(db, args.get("issue_keys"))
    for record in records:
        db.connection.execute(
            "DELETE FROM jira_sprint_issues WHERE issue_id=?", (record["id"],)
        )
    return {
        "message": f"Successfully moved {len(keys)} issue(s) to backlog",
        "issue_keys": keys,
    }


def validate_move(db, record, target):
    for row in db.connection.execute(
        "SELECT user_id FROM jira_watchers WHERE issue_id=?", (record["id"],)
    ):
        s.validate_assignment(s.user_by_id(db, row[0]), target["key"])
    member = member_sprint(db, record)
    if member is not None:
        assigned = sprint(db, member["id"])
        if target["key"] not in board_projects(db, assigned["board_id"]):
            raise s.BusinessError("Destination project is outside current sprint board")


def validate_fixtures(world):
    projects = {p["key"] for p in world.jira_projects}
    issues = {i["id"]: i for i in world.jira_issues}
    boards = {}
    for row in world.jira_boards:
        i = numeric_id(row.get("id"), "board id", fixture=True)
        s.text(row.get("name"), "board name")
        kind = s.text(row.get("type"), "board type")
        if i in boards or kind not in ("scrum", "kanban"):
            raise s.BusinessError("Invalid board identity/type")
        keys = s.array(row.get("project_keys"), "board projects")
        if not keys:
            raise s.BusinessError("Board requires projects")
        for key in keys:
            if s.text(key, "board project") not in projects:
                raise s.BusinessError("Unknown board project")
        if len(set(keys)) != len(keys):
            raise s.BusinessError("Duplicate board project")
        boards[i] = row
    sprints = {}
    for row in world.jira_sprints:
        i = numeric_id(row.get("id"), "sprint id", fixture=True)
        b = s.text(row.get("board_id"), "board reference")
        if i in sprints or b not in boards or boards[b]["type"] != "scrum":
            raise s.BusinessError("Invalid sprint identity/board")
        validate_sprint(row)
        sprints[i] = row
    seen = set()
    for row in world.jira_sprint_issues:
        i = a.identity(row.get("issue_id"), "sprint issue")
        sp = numeric_id(row.get("sprint_id"), "sprint reference")
        if i in seen or i not in issues or sp not in sprints:
            raise s.BusinessError("Invalid sprint membership")
        if (
            issues[i]["data"]["project_key"]
            not in boards[sprints[sp]["board_id"]]["project_keys"]
        ):
            raise s.BusinessError("Sprint issue outside board projects")
        seen.add(i)


def seed(db, world):
    for row in world.jira_boards:
        db.connection.execute(
            "INSERT INTO jira_boards VALUES (?,?)",
            (row["id"], json.dumps({k: row[k] for k in ("id", "name", "type")})),
        )
        for key in row["project_keys"]:
            project = next(p for p in world.jira_projects if p["key"] == key)
            db.connection.execute(
                "INSERT INTO jira_board_projects VALUES (?,?)",
                (row["id"], project["id"]),
            )
    for row in world.jira_sprints:
        db.connection.execute(
            "INSERT INTO jira_sprints VALUES (?,?,?)",
            (
                row["id"],
                row["board_id"],
                json.dumps(
                    {k: v for k, v in row.items() if k not in ("id", "board_id")}
                ),
            ),
        )
    for row in world.jira_sprint_issues:
        db.connection.execute(
            "INSERT INTO jira_sprint_issues VALUES (?,?)",
            (row["issue_id"], row["sprint_id"]),
        )


HANDLERS = {
    "jira_get_agile_boards": get_agile_boards,
    "jira_get_board_issues": get_board_issues,
    "jira_get_sprints_from_board": get_sprints_from_board,
    "jira_get_sprint_issues": get_sprint_issues,
    "jira_create_sprint": create_sprint,
    "jira_update_sprint": update_sprint,
    "jira_add_issues_to_sprint": add_issues_to_sprint,
    "jira_move_issues_to_backlog": move_issues_to_backlog,
}
