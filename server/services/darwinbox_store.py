"""Darwinbox finite records and deliberate atomic business errors."""

import json
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.database import Database


class BusinessError(ValueError):
    pass


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


def number(value, field):
    if (
        type(value) not in (int, float)
        or abs(value) > 1e308
        or not math.isfinite(value)
        or value < 0
    ):
        raise BusinessError(f"{field} must be a finite nonnegative number")
    return value


def choice(value, options, field):
    if type(value) not in (str, int, float) or value not in options:
        raise BusinessError(f"Unsupported {field}")
    return value


def finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise BusinessError("Records must contain finite JSON numbers")
    if isinstance(value, dict):
        for item in value.values():
            finite_json(item)
    elif isinstance(value, list):
        for item in value:
            finite_json(item)


DAY = "%d-%m-%Y"
ISO_DAY = "%Y-%m-%d"
STAMP = "%d-%m-%Y %H:%M:%S"
PUNCH = "%Y-%m-%d %H:%M:%S"


def date(value, fmt=DAY):
    value = text(value, "date")
    try:
        parsed = datetime.strptime(value, fmt).replace(tzinfo=UTC)
    except ValueError as error:
        raise BusinessError(f"Invalid date; expected {fmt}") from error
    if parsed.strftime(fmt) != value:
        raise BusinessError(f"Invalid date; expected {fmt}")
    return parsed


def span(start, end, fmt=DAY):
    start, end = date(start, fmt), date(end, fmt)
    if start > end:
        raise BusinessError("Reversed date range")
    return start, end


def now(db, clock):
    scenario = json.loads(
        db.connection.execute(
            "SELECT value FROM metadata WHERE key='scenario'"
        ).fetchone()[0]
    )
    return (
        datetime.fromisoformat(scenario["darwinbox_epoch"]).astimezone(UTC)
        + timedelta(seconds=clock)
    ).strftime(STAMP)


def rows(db, kind):
    return [
        json.loads(row[0])
        for row in db.connection.execute(
            "SELECT data FROM darwinbox_records WHERE kind=? ORDER BY id", (kind,)
        )
    ]


def get(db, kind, identifier):
    identifier = text(identifier, "identity")
    row = db.connection.execute(
        "SELECT data FROM darwinbox_records WHERE kind=? AND id=?", (kind, identifier)
    ).fetchone()
    if row is None:
        raise BusinessError(f"{kind} {identifier} does not exist")
    return json.loads(row[0])


def put(db, kind, identifier, data):
    db.connection.execute(
        "INSERT INTO darwinbox_records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
        (kind, identifier, json.dumps(data, allow_nan=False)),
    )


def append(db, kind, data):
    sequence = db.connection.execute(
        "INSERT INTO darwinbox_ids(kind) VALUES (?)", (kind,)
    ).lastrowid
    identifier = f"{kind}-{sequence:06d}"
    while db.connection.execute(
        "SELECT 1 FROM darwinbox_records WHERE kind=? AND id=?", (kind, identifier)
    ).fetchone():
        sequence = db.connection.execute(
            "INSERT INTO darwinbox_ids(kind) VALUES (?)", (kind,)
        ).lastrowid
        identifier = f"{kind}-{sequence:06d}"
    put(db, kind, identifier, data)
    return identifier


def employees(db, values):
    values = array(values, "employee IDs")
    for identifier in values:
        get(db, "employee", identifier)
    return values


def employee_data(data):
    obj(data, "employee")
    identifier = text(data.get("employee_no", data.get("employee_id")), "employee_no")
    if "employee_id" in data and text(data["employee_id"], "employee_id") != identifier:
        raise BusinessError("Employee identity aliases must agree")
    if "status" in data:
        choice(data["status"], ("active", "inactive"), "status")
    if "employee_name" in data and not isinstance(data["employee_name"], str):
        raise BusinessError("employee_name must be a string")
    if "effective_date" in data:
        date(data["effective_date"])
    if "modified" in data:
        date(data["modified"], STAMP)
    return identifier


def handler(
    function: Callable[["Database", dict, int, int], object],
) -> Callable[["Database", dict, int, int], tuple[object, bool]]:
    @wraps(function)
    def execute(db, arguments, step, clock):
        db.connection.execute("SAVEPOINT darwinbox_business")
        try:
            data = function(db, arguments, step, clock)
        except BusinessError as error:
            db.connection.execute("ROLLBACK TO darwinbox_business")
            db.connection.execute("RELEASE darwinbox_business")
            return {"error": str(error)}, True
        db.connection.execute("RELEASE darwinbox_business")
        return {
            "status": 1,
            "message": "Simulator operation completed",
            "data": data,
        }, False

    return execute
