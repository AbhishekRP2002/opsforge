"""Finite JQL parser: conjunction, equality/IN and deterministic ordering."""

import hashlib
import json
import re

from . import jira_store as s

TOKEN = re.compile(
    r"""\s*(?:(?P<quoted>"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(?P<word>[A-Za-z0-9_@.:-]+)|(?P<punct>[=(),]))"""
)
FIELDS = {
    "project",
    "key",
    "issuetype",
    "status",
    "assignee",
    "priority",
    "labels",
    "parent",
    "sprint",
}


def parse(query):
    query = s.text(query, "jql")
    tokens = []
    position = 0
    while position < len(query.rstrip()):
        match = TOKEN.match(query, position)
        if not match:
            raise s.BusinessError("Unsupported JQL syntax in finite profile")
        quoted = match.group("quoted")
        tokens.append(
            (
                re.sub(r"\\(.)", r"\1", quoted[1:-1])
                if quoted
                else match.group("word") or match.group("punct"),
                quoted is not None,
            )
        )
        position = match.end()
    index = 0

    def peek(word):
        return (
            index < len(tokens)
            and not tokens[index][1]
            and tokens[index][0].upper() == word
        )

    def take():
        nonlocal index
        if index >= len(tokens):
            raise s.BusinessError("Incomplete JQL expression")
        token = tokens[index]
        index += 1
        return token

    def expect(word):
        if not peek(word):
            raise s.BusinessError(f"Expected JQL {word}")
        take()

    def value():
        val, quoted = take()
        if not quoted and val.lower() == "currentuser":
            expect("(")
            expect(")")
            return ("current", "")
        if not quoted and val in ("=", "(", ")", ","):
            raise s.BusinessError("Expected JQL scalar value")
        return ("literal", val)

    clauses, ordering = [], []
    while index < len(tokens) and not peek("ORDER"):
        field, quoted = take()
        field = field.lower()
        if quoted or field not in FIELDS:
            raise s.BusinessError("Unsupported JQL field")
        if peek("="):
            take()
            values = [value()]
        else:
            expect("IN")
            expect("(")
            values = [value()]
            while peek(","):
                take()
                values.append(value())
            expect(")")
        if field != "assignee" and any(v[0] == "current" for v in values):
            raise s.BusinessError("currentUser() is supported only for assignee")
        clauses.append((field, values))
        if index == len(tokens) or peek("ORDER"):
            break
        expect("AND")
        if index == len(tokens):
            raise s.BusinessError("Incomplete JQL conjunction")
    if index < len(tokens):
        expect("ORDER")
        expect("BY")
        while True:
            field, quoted = take()
            field = field.lower()
            if (
                quoted
                or field not in FIELDS | {"summary", "created", "updated"}
                or field == "labels"
            ):
                raise s.BusinessError("Unsupported JQL sort field")
            descending = peek("DESC")
            if peek("DESC") or peek("ASC"):
                take()
            ordering.append((field, descending))
            if not peek(","):
                break
            take()
    if index != len(tokens):
        raise s.BusinessError("Unsupported trailing JQL expression")
    return clauses, ordering


def field_value(db, record, field):
    data = record["data"]
    if field == "key":
        return record["key"]
    if field == "parent":
        row = db.connection.execute(
            "SELECT key FROM jira_issues WHERE id=?", (record["parent_id"],)
        ).fetchone()
        return row[0] if row else None
    if field == "priority":
        return data.get("priority", {}).get("name")
    if field == "sprint":
        row = db.connection.execute(
            "SELECT sprint_id FROM jira_sprint_issues WHERE issue_id=?", (record["id"],)
        ).fetchone()
        return str(row[0]) if row else None
    return data.get(
        {"project": "project_key", "issuetype": "issue_type"}.get(field, field)
    )


def select(db, query, projects_filter=None):
    clauses, ordering = parse(query)
    from .jira_agile import resolve_sprint

    config = s.config(db)
    narrowed = (
        [p.strip() for p in projects_filter.split(",")] if projects_filter else []
    )
    for key in narrowed:
        if not db.connection.execute(
            "SELECT 1 FROM jira_projects WHERE key=?", (key,)
        ).fetchone():
            raise s.BusinessError("Unknown projects_filter reference")
    resolved = []
    for field, values in clauses:
        resolved.append(
            (
                field,
                [
                    s.user(db, "me" if kind == "current" else value)["id"]
                    if field == "assignee"
                    else resolve_sprint(db, value)
                    if field == "sprint"
                    else value
                    for kind, value in values
                ],
            )
        )
    result = []
    for row in db.connection.execute("SELECT * FROM jira_issues ORDER BY id"):
        record = dict(row)
        record["data"] = json.loads(record["data"])
        key = record["data"]["project_key"]
        if (
            config["jira_projects_filter"]
            and key not in config["jira_projects_filter"]
            or narrowed
            and key not in narrowed
        ):
            continue
        if all(
            any(
                str(item).casefold() == str(want).casefold()
                for item in (actual if isinstance(actual, list) else [actual])
                for want in values
            )
            for field, values in resolved
            for actual in [field_value(db, record, field)]
        ):
            result.append(record)
    for field, descending in reversed(ordering):
        result.sort(
            key=lambda row: (
                field_value(db, row, field) is not None,
                str(field_value(db, row, field) or "").casefold(),
            ),
            reverse=descending,
        )
    return result


def page(db, arguments, records):
    config = s.config(db)
    cloud = config["jira_edition"] == "cloud"
    limit, start = arguments.get("limit", 10), arguments.get("start_at", 0)
    if type(limit) is not int or limit < 1 or type(start) is not int or start < 0:
        raise s.BusinessError("Invalid pagination bounds")
    limit = min(limit, 1000 if cloud else 50)
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                arguments.get("jql"),
                arguments.get("projects_filter"),
                arguments.get("fields"),
                arguments.get("use_display_names", False),
                config["jira_projects_filter"],
                [r["id"] for r in records],
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    token = arguments.get("page_token")
    if not cloud and token is not None:
        raise s.BusinessError("page_token is Cloud only")
    if cloud:
        start = 0
        if token is not None:
            if not isinstance(token, str) or not re.fullmatch(
                r"[0-9a-f]{64}:[0-9]{1,20}", token
            ):
                raise s.BusinessError("Invalid page token")
            digest, offset = token.split(":")
            if digest != fingerprint:
                raise s.BusinessError(
                    "Page token belongs to another query or result snapshot"
                )
            start = int(offset)
            if start > len(records):
                raise s.BusinessError("Page token outside result set")
    result: dict = {
        "total": -1 if cloud else len(records),
        "start_at": 0 if cloud else start,
        "max_results": limit,
    }
    if cloud and start + limit < len(records):
        result["next_page_token"] = f"{fingerprint}:{start + limit}"
    return result, records[start : start + limit]
