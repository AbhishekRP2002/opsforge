"""Finite offline table operations, never a provider client or script evaluator."""

import json
import re
from datetime import UTC, datetime, timedelta

from ..storage.database import Database


def timestamp(clock: int) -> str:
    return (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=clock)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def identifier(db: Database, name: str) -> str:
    db.connection.execute(
        "INSERT INTO servicenow_sequences VALUES (?,0) ON CONFLICT DO NOTHING", (name,)
    )
    while True:
        row = db.connection.execute(
            "UPDATE servicenow_sequences SET value=value+1 WHERE name=? RETURNING value",
            (name,),
        ).fetchone()
        key = f"{row[0]:032x}"
        inserted = db.connection.execute(
            "INSERT INTO servicenow_allocated_ids VALUES (?,?) ON CONFLICT DO NOTHING",
            (name, key),
        )
        if inserted.rowcount:
            return key


def all_rows(db: Database, table: str) -> list[dict]:
    return [
        json.loads(row[0])
        for row in db.connection.execute(
            "SELECT data FROM servicenow_records WHERE table_name=? ORDER BY rowid",
            (table,),
        )
    ]


def get(db: Database, table: str, key: str) -> dict | None:
    row = db.connection.execute(
        "SELECT data FROM servicenow_records WHERE table_name=? AND sys_id=?",
        (table, key),
    ).fetchone()
    return json.loads(row[0]) if row else None


def reference_error(
    db: Database, data: dict, refs: dict[str, str], *, required=()
) -> str | None:
    for field in required:
        if not data.get(field):
            return f"simulation_profile: required {field} reference"
    for field, table in refs.items():
        key = data.get(field)
        if key is not None and not isinstance(key, str):
            return f"simulation_profile: {field} reference must be text"
        if not key:
            continue
        if table in {"sys_user", "sys_user_group"}:
            sql_table = (
                "servicenow_users" if table == "sys_user" else "servicenow_groups"
            )
            exists = db.connection.execute(
                f"SELECT 1 FROM {sql_table} WHERE sys_id=?", (key,)
            ).fetchone()
        else:
            exists = get(db, table, key)
        if not exists:
            return f"simulation_profile: missing {field} reference {key}"
    return None


def insert(
    db: Database,
    table: str,
    data: dict,
    step: int,
    clock: int,
    prefix: str | None = None,
) -> dict:
    key = identifier(db, table)
    while get(db, table, key):
        key = identifier(db, table)
    record = dict(
        data,
        sys_id=key,
        sys_created_on=timestamp(clock),
        sys_updated_on=timestamp(clock),
    )
    if prefix:
        record["number"] = f"{prefix}{int(key, 16):07d}"
    db.connection.execute(
        "INSERT INTO servicenow_records VALUES (?,?,?)",
        (table, key, json.dumps(record)),
    )
    db.record(step, clock, "created", "servicenow", key)
    return record


def update(
    db: Database, table: str, record: dict, data: dict, step: int, clock: int
) -> dict:
    value = record | data | {"sys_updated_on": timestamp(clock)}
    db.connection.execute(
        "UPDATE servicenow_records SET data=? WHERE table_name=? AND sys_id=?",
        (json.dumps(value), table, record["sys_id"]),
    )
    db.record(step, clock, "updated", "servicenow", record["sys_id"])
    return value


def delete(db: Database, table: str, key: str, step: int, clock: int) -> None:
    db.connection.execute(
        "DELETE FROM servicenow_records WHERE table_name=? AND sys_id=?", (table, key)
    )
    db.record(step, clock, "deleted", "servicenow", key)


def fields(arguments: dict, exclude=(), *, truthy=False) -> dict:
    return {
        key: value
        for key, value in arguments.items()
        if key not in exclude and (bool(value) if truthy else value is not None)
    }


def page(
    rows: list[dict], arguments: dict, filters=(), *, search_fields=(), clock=0
) -> tuple[list[dict], int, str | None]:
    limit, offset = arguments.get("limit"), arguments.get("offset")
    limit = 10 if limit is None else limit
    offset = 0 if offset is None else offset
    if limit < 0 or offset < 0 or limit > 1000:
        return (
            [],
            0,
            "simulation_profile: pagination requires 0 <= limit <= 1000 and offset >= 0",
        )
    timeframe = arguments.get("timeframe")
    now = timestamp(clock)
    if timeframe == "upcoming":
        rows = [row for row in rows if row.get("start_date", "") > now]
    elif timeframe == "completed":
        rows = [row for row in rows if row.get("end_date") and row["end_date"] < now]
    elif timeframe == "in-progress":
        rows = [
            row
            for row in rows
            if row.get("start_date")
            and row["start_date"] < now < row.get("end_date", "")
        ]
    for field in filters:
        if arguments.get(field) is not None:
            rows = [
                row
                for row in rows
                if str(row.get(field)).lower() == str(arguments[field]).lower()
            ]
    query = arguments.get("query")
    if query and search_fields:
        if "^" in query:
            return [], 0, "unsupported_simulation_query"
        rows = [
            row
            for row in rows
            if any(
                query.casefold() in str(row.get(field, "")).casefold()
                for field in search_fields
            )
        ]
    elif query:
        ordering = []
        for clause in query.split("^"):
            order = re.fullmatch(r"ORDERBY(DESC)?([a-z_][a-z0-9_]*)", clause)
            condition = re.fullmatch(r"([a-z_][a-z0-9_]*)(LIKE|=)([^^]*)", clause)
            date = re.fullmatch(
                r"(start_date|end_date|sys_created_on)([<>])(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
                clause,
            )
            if order:
                ordering.append((order[2], bool(order[1])))
            elif date:
                field, op, value = date.groups()
                rows = [
                    row
                    for row in rows
                    if row.get(field)
                    and (row[field] > value if op == ">" else row[field] < value)
                ]
            elif clause in DATE_MACROS.values():
                beginning, end = date_bounds(clause, clock)
                rows = [
                    row
                    for row in rows
                    if beginning <= row.get("sys_created_on", "") < end
                ]
            elif condition and not any(
                token in clause for token in ("javascript:", "!=", ">", "<")
            ):
                field, op, value = condition.groups()
                rows = [
                    row
                    for row in rows
                    if (
                        value.casefold() in str(row.get(field, "")).casefold()
                        if op == "LIKE"
                        else str(row.get(field, "")).lower() == value.lower()
                    )
                ]
            else:
                return [], 0, "unsupported_simulation_query"
        for field, descending in reversed(ordering):
            rows = sorted(
                rows, key=lambda row: str(row.get(field, "")), reverse=descending
            )
    return rows[offset : offset + limit], len(rows), None


def failure(message: str, **values) -> tuple[dict, bool]:
    return {"success": False, "message": message, **values}, False


ASSIGNMENT_REFS = {"assigned_to": "sys_user", "assignment_group": "sys_user_group"}

DATE_MACROS = {
    "recent": "sys_created_onONLast 7 days@javascript:gs.beginningOfLast7Days()@javascript:gs.endOfToday()",
    "last_week": "sys_created_onONLast week@javascript:gs.beginningOfLastWeek()@javascript:gs.endOfLastWeek()",
    "last_month": "sys_created_onONLast month@javascript:gs.beginningOfLastMonth()@javascript:gs.endOfLastMonth()",
}


def date_bounds(macro: str, clock: int) -> tuple[str, str]:
    today = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=clock)
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)
    if macro == DATE_MACROS["recent"]:
        start, end = today - timedelta(days=7), today + timedelta(days=1)
    elif macro == DATE_MACROS["last_week"]:
        end = today - timedelta(days=today.weekday())
        start = end - timedelta(days=7)
    else:
        end = today.replace(day=1)
        start = (end - timedelta(days=1)).replace(day=1)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def denied(db: Database, operation: str, key: str) -> str | None:
    scenario = json.loads(
        db.connection.execute(
            "SELECT value FROM metadata WHERE key='scenario'"
        ).fetchone()[0]
    )
    identifiers = scenario.get("servicenow_denied_operations", {}).get(operation, [])
    return (
        f"simulation_profile: denied {operation} for {key}"
        if "*" in identifiers or key in identifiers
        else None
    )
