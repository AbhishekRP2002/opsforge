"""Validated punch events, backdated rows and fixture-only rosters."""

import json

from . import darwinbox_store as s


def validate_punch(row):
    s.obj(row, "punch")
    for key in ("id", "machineid", "status"):
        s.text(row.get(key), key)
    s.date(row.get("timestamp"), s.PUNCH)


def validate_backdated(row):
    s.obj(row, "backdated row")
    for key in ("employee_no", "shift_name", "policy_name", "weekly_off_name"):
        s.text(row.get(key), key)
    s.date(row.get("shift_date"), s.ISO_DAY)
    for key in ("in_time", "out_time"):
        s.date(row.get(key), "%H:%M:%S")
    s.span(row.get("in_time_date"), row.get("out_time_date"), s.ISO_DAY)
    start = s.date(row["in_time_date"] + " " + row["in_time"], s.PUNCH)
    end = s.date(row["out_time_date"] + " " + row["out_time"], s.PUNCH)
    duration = s.text(row.get("break_duration"), "break_duration")
    if not duration.isascii() or not duration.isdecimal() or len(duration) > 8:
        raise s.BusinessError("break_duration requires bounded integer minutes")
    if start > end or int(duration) * 60 > (end - start).total_seconds():
        raise s.BusinessError("Invalid attendance interval or break duration")


@s.handler
def record_attendance_punches(db, a, step, clock):
    batch = s.obj(a["attendance"], "attendance")
    writes = {}
    existing = {
        json.dumps([r["employee_no"], r["machineid"], r["id"]]): r
        for r in s.rows(db, "punch")
    }
    for employee, punches in batch.items():
        s.get(db, "employee", employee)
        for punch in s.array(punches, "punches"):
            validate_punch(punch)
            if "employee_no" in punch and punch["employee_no"] != employee:
                raise s.BusinessError("Punch employee must agree with wrapper")
            row = punch | {"employee_no": employee}
            key = json.dumps([employee, row["machineid"], row["id"]])
            if key in (existing | writes) and (existing | writes)[key] != row:
                raise s.BusinessError("Conflicting duplicate punch")
            writes[key] = row
    for key, row in writes.items():
        s.put(db, "punch", key, row)
    return list(writes.values())


@s.handler
def record_backdated_attendance(db, a, step, clock):
    batch = s.array(
        s.obj(a["attendance"], "attendance").get("attendance_data"), "attendance_data"
    )
    writes = {}
    for row in batch:
        validate_backdated(row)
        s.get(db, "employee", row["employee_no"])
        key = json.dumps([row["employee_no"], row["shift_date"]])
        if key in writes and writes[key] != row:
            raise s.BusinessError("Conflicting backdated attendance")
        writes[key] = row
    for key, row in writes.items():
        s.put(db, "backdated", key, row)
    return list(writes.values())


def attendance(db, a):
    ids = s.employees(db, a["emp_number_list"])
    start, end = s.span(a["from_date"], a["to_date"], s.ISO_DAY)
    result = {}
    for row in s.rows(db, "punch"):
        day = row["timestamp"].split()[0]
        if row["employee_no"] in ids and start <= s.date(day, s.ISO_DAY) <= end:
            key = (row["employee_no"], day)
            result.setdefault(key, {"employee_no": key[0], "date": day, "punches": []})[
                "punches"
            ].append(row)
    for row in s.rows(db, "backdated"):
        if (
            row["employee_no"] in ids
            and start <= s.date(row["shift_date"], s.ISO_DAY) <= end
        ):
            key = (row["employee_no"], row["shift_date"])
            result.setdefault(
                key, {"employee_no": key[0], "date": key[1], "punches": []}
            )["backdated"] = row
    for row in result.values():
        row["punches"].sort(key=lambda p: (p["timestamp"], p["machineid"], p["id"]))
    return [result[key] for key in sorted(result)]


@s.handler
def get_daily_attendance(db, a, step, clock):
    return attendance(db, a)


@s.handler
def get_monthly_attendance(db, a, step, clock):
    s.date(a["month"], "%Y-%m")
    return [
        row for row in attendance(db, a) if row["date"].startswith(a["month"] + "-")
    ]


@s.handler
def get_attendance_roster(db, a, step, clock):
    ids = s.employees(db, a["emp_number_list"])
    start, end = s.span(a["from_date"], a["to_date"], s.ISO_DAY)
    return [
        row
        for row in s.rows(db, "roster")
        if row["employee_no"] in ids and start <= s.date(row["date"], s.ISO_DAY) <= end
    ]


HANDLERS = {
    "record_attendance_punches": record_attendance_punches,
    "record_backdated_attendance": record_backdated_attendance,
    "get_daily_attendance": get_daily_attendance,
    "get_monthly_attendance": get_monthly_attendance,
    "get_attendance_roster": get_attendance_roster,
}
