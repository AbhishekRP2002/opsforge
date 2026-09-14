"""Employee lifecycle and owned personal documents; local response profile."""

import base64
import binascii

from . import darwinbox_store as s


def history(db, before, after, clock):
    s.append(
        db,
        "history",
        {
            "employee_no": after["employee_no"],
            "before": before,
            "after": after,
            "modified": s.now(db, clock),
            "effective_date": after.get("effective_date", s.now(db, clock).split()[0]),
        },
    )


@s.handler
def add_employee(db, a, step, clock):
    data = dict(s.obj(a["employees"], "employees"))
    identifier = s.employee_data(data)
    if any(row["employee_no"] == identifier for row in s.rows(db, "employee")):
        raise s.BusinessError("Employee already exists")
    if "modified" in data or data.get("status", "active") != "active":
        raise s.BusinessError(
            "Employee must be added active without internal modified field"
        )
    data.update(employee_no=identifier, status="active", modified=s.now(db, clock))
    s.put(db, "employee", identifier, data)
    history(db, None, data, clock)
    return data


@s.handler
def update_employee(db, a, step, clock):
    patch = dict(s.obj(a["employee_data"], "employee_data"))
    identifier = s.employee_data(patch)
    before = s.get(db, "employee", identifier)
    if "status" in patch or "modified" in patch:
        raise s.BusinessError(
            "Lifecycle and modified fields are managed by the simulator"
        )
    after = (
        before
        | patch
        | {
            "employee_no": identifier,
            "modified": s.now(db, clock),
            "effective_date": patch.get("effective_date", s.now(db, clock).split()[0]),
        }
    )
    s.employee_data(after)
    s.put(db, "employee", identifier, after)
    history(db, before, after, clock)
    return after


@s.handler
def get_employee_details(db, a, step, clock):
    rows = s.rows(db, "employee")
    if "employee_ids" in a:
        ids = s.employees(db, a["employee_ids"])
        return [row for row in rows if row["employee_no"] in ids]
    if "last_modified" in a:
        after = s.date(a["last_modified"], s.STAMP)
        rows = [row for row in rows if s.date(row["modified"], s.STAMP) > after]
    return rows


@s.handler
def get_employee_history(db, a, step, clock):
    start, end = s.span(a["from"], a["to"])
    flag = s.choice(a["filter_on_effective_date"], (0, 1), "filter_on_effective_date")
    return [
        row
        for row in s.rows(db, "history")
        if start
        <= s.date(row["effective_date"] if flag else row["modified"].split()[0])
        <= end
    ]


@s.handler
def deactivate_employee(db, a, step, clock):
    batch = s.array(a["employees"], "employees")
    seen = set()
    for row in batch:
        s.obj(row, "employee")
        if "employee_no" in row:
            s.employee_data(row)
        before = s.get(db, "employee", row.get("employee_id"))
        if before["employee_no"] in seen or before["status"] != "active":
            raise s.BusinessError("Duplicate or inactive employee")
        seen.add(before["employee_no"])
        for key in ("deactivate_type", "deactivate_reason"):
            s.text(row.get(key), key)
        s.span(row.get("date_of_resignation"), row.get("date_of_exit"))
    result = []
    for row in batch:
        before = s.get(db, "employee", row["employee_id"])
        after = before | {
            "status": "inactive",
            "modified": s.now(db, clock),
            "effective_date": row["date_of_exit"],
        }
        s.put(db, "employee", before["employee_no"], after)
        history(db, before, after, clock)
        separation = row | {
            "employee_no": before["employee_no"],
            "separation_status": row["deactivate_type"],
        }
        s.put(db, "separation", before["employee_no"], separation)
        result.append(separation)
    return result


@s.handler
def get_separation_details(db, a, step, clock):
    ids = s.employees(db, a["employee_ids"])
    status = s.text(a["separation_status"], "separation_status")
    return [
        r
        for r in s.rows(db, "separation")
        if r["employee_no"] in ids and r["separation_status"] == status
    ]


@s.handler
def upload_profile_attachments(db, a, step, clock):
    s.get(db, "employee", a["employee_no"])
    for field in ("section", "section_attribute"):
        s.text(a[field], field)
    raw = s.text(a["attachment"], "attachment")
    if len(raw) > 699052:
        raise s.BusinessError("Attachment exceeds 512 KiB")
    try:
        content = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as error:
        raise s.BusinessError("Attachment must contain base64 bytes") from error
    if not content or len(content) > 524288:
        raise s.BusinessError("Attachment must contain 1..524288 bytes")
    identifier = s.append(db, "attachment", {})
    path = f"artifacts/darwinbox/{identifier}.bin"
    record = {
        "employee_no": a["employee_no"],
        "section": a["section"],
        "section_attribute": a["section_attribute"],
        "artifact_path": path,
    }
    s.put(db, "attachment", identifier, record)
    db.connection.execute(
        "INSERT INTO episode_artifacts VALUES (?,?,?,?,?)",
        (path, content, "application/octet-stream", step, clock),
    )
    return record


@s.handler
def download_personal_docs(db, a, step, clock):
    s.get(db, "employee", a["employee_no"])
    kind = s.text(a["for"], "for")
    records = [
        row
        for row in s.rows(db, "attachment")
        if row["employee_no"] == a["employee_no"] and row["section_attribute"] == kind
    ]
    if not records:
        raise s.BusinessError("Personal document does not exist")
    for row in records:
        artifact = db.artifact(row["artifact_path"])
        if artifact is None:
            raise RuntimeError("Owned attachment content is missing")
        row["content_base64"] = base64.b64encode(artifact["content"]).decode()
    return records


HANDLERS = {
    "add_employee": add_employee,
    "update_employee": update_employee,
    "get_employee_details": get_employee_details,
    "get_employee_history": get_employee_history,
    "deactivate_employee": deactivate_employee,
    "get_separation_details": get_separation_details,
    "upload_profile_attachments": upload_profile_attachments,
    "download_personal_docs": download_personal_docs,
}
