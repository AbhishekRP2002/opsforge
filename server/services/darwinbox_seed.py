"""Finite trusted fixture profile; no generated entitlement or master records."""

import json
from datetime import datetime

from . import darwinbox_store as store
from .darwinbox_attendance import validate_backdated, validate_punch


def business_key(kind, identifier, data):
    if kind == "punch":
        return json.dumps([data["employee_no"], data["machineid"], data["id"]])
    if kind == "backdated":
        return json.dumps([data["employee_no"], data["shift_date"]])
    return identifier


def validate(records, epoch):
    time = datetime.fromisoformat(epoch)
    offset = time.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise store.BusinessError("Darwinbox fixture epoch must be UTC")
    keys = set()
    index = {}
    for item in records:
        store.finite_json(item.data)
        store.choice(
            item.kind,
            (
                "employee",
                "allocation",
                "punch",
                "backdated",
                "roster",
                "holiday",
                "position",
                "form",
                "job",
                "candidate",
            ),
            "fixture kind",
        )
        store.text(item.id, "fixture identity")
        if (item.kind, item.id) in index:
            raise store.BusinessError("Duplicate fixture identity")
        index[item.kind, item.id] = item.data
    for item in records:
        data, kind = item.data, item.kind
        if kind == "employee":
            if store.employee_data(data) != item.id:
                raise store.BusinessError("Employee identity must match fixture ID")
            data.setdefault("employee_no", item.id)
            data.setdefault("status", "active")
            data.setdefault("modified", time.strftime(store.STAMP))
        elif kind == "job":
            validate_job(data, item.id)
        elif kind == "candidate":
            store.date(data.get("modified"), store.STAMP)
            candidate = store.obj(data.get("candidate"), "candidate")
            reference(index, "job", candidate.get("job_id"))
            if candidate.get("unique_id") != item.id:
                raise store.BusinessError("Candidate unique_id must match fixture ID")
            validate_candidate(candidate)
        else:
            reference(index, "employee", data.get("employee_no"))
            if kind == "allocation":
                store.text(data.get("leave_name"), "leave_name")
                for field in (
                    "balance",
                    "accrued_so_far_this_year",
                    "previous_balance",
                    "adjustment_balance",
                ):
                    store.number(
                        data.get(field, 0 if field != "balance" else None), field
                    )
                if data.get("leave_id", item.id) != item.id:
                    raise store.BusinessError(
                        "Allocation leave_id must match fixture ID"
                    )
                data["leave_id"] = item.id
            elif kind == "punch":
                validate_punch(data)
            elif kind == "backdated":
                validate_backdated(data)
            elif kind == "position":
                store.number(data.get("status"), "status")
                store.choice(data.get("need_to_hire"), (0, 1), "need_to_hire")
            else:
                store.date(
                    data.get("date"), store.ISO_DAY if kind == "roster" else store.DAY
                )
                required = (
                    ("form_id", "type", "form_type")
                    if kind == "form"
                    else ("name",)
                    if kind == "holiday"
                    else ("shift_name",)
                )
                for field in required:
                    store.text(data.get(field), field)
        key = (
            (kind, data["employee_no"], data["leave_name"])
            if kind == "allocation"
            else (kind, business_key(kind, item.id, data))
        )
        if key in keys:
            raise store.BusinessError("Duplicate fixture business identity")
        keys.add(key)


def reference(index, kind, identity):
    if (kind, store.text(identity, "reference")) not in index:
        raise store.BusinessError(f"Missing {kind} fixture reference")


def text_fields(data, names):
    for name in names.split():
        if not isinstance(data.get(name), str):
            raise store.BusinessError(f"{name} must be a string")


def text_list(value):
    if any(not isinstance(item, str) for item in store.array(value, "string array")):
        raise store.BusinessError("Expected a string array")


def validate_job(data, identity):
    listing = store.obj(data.get("listing"), "listing")
    detail = store.obj(data.get("detail"), "detail")
    if listing.get("job_id") != identity:
        raise store.BusinessError("Job listing must match fixture ID")
    common = "job_title group_company parent_department department employee_type experience_from experience_to location_country job_created_timestamp job_updated_timestamp"
    text_fields(listing, common + " job_id job_code business_unit")
    text_fields(
        detail,
        common
        + " department_code designation_code designation band grade salary_min salary_max salary_currency unit_experience job_decription job_status",
    )
    if (
        "division" not in listing
        or listing["division"] is not None
        and not isinstance(listing["division"], str)
    ):
        raise store.BusinessError("division must be a string or null")
    for record in (listing, detail):
        for field in ("location", "location_city"):
            text_list(record.get(field))
        for field in ("post_on_careers_page", "post_on_refer_page", "post_on_ijp_page"):
            store.number(record.get(field), field)
        for field in ("job_created_timestamp", "job_updated_timestamp"):
            store.date(record[field], store.STAMP)
    store.number(listing.get("is_remote"), "is_remote")
    for field in ("total_positions", "open_positions"):
        store.number(detail.get(field), field)
    for field in ("job_created_timestamp", "job_updated_timestamp", "job_title"):
        if listing[field] != detail[field]:
            raise store.BusinessError("Job listing and detail must agree")
    for team in (
        "hiring_lead",
        "screening_team",
        "shortlisting_team",
        "scheduling_team",
        "hiring_group",
    ):
        for member in store.array(detail.get(team), team):
            text_fields(store.obj(member, "member"), "name employee_id email_id")
    for field in store.obj(detail.get("applicant_fields"), "applicant_fields").values():
        store.obj(field, "applicant field")
        text_fields(field, "name type dependentField optionEndpoint")
        store.number(field.get("order"), "order")
        for flag in (
            "required",
            "is_custom",
            "is_calculation_active",
            "rules",
            "has_dependency",
            "hasDependentDropdown",
        ):
            if type(field.get(flag)) is not bool:
                raise store.BusinessError("Applicant flags must be boolean")
        text_list(field.get("dependent_keys"))
        store.array(field.get("queryParam"), "queryParam")
        text_fields(
            store.obj(field.get("validation"), "validation"), "regex valid_extentions"
        )
        if not isinstance(field.get("options"), bool):
            for option in store.array(field.get("options"), "options"):
                if not isinstance(option, str):
                    text_fields(store.obj(option, "option"), "label value")


def validate_candidate(candidate):
    text_fields(
        candidate,
        "unique_id firstname lastname email phone job_id status source_type source_name created_date",
    )
    if (
        "candidate_id" not in candidate
        or candidate["candidate_id"] is not None
        and not isinstance(candidate["candidate_id"], str)
    ):
        raise store.BusinessError("candidate_id must be a string or null")
    text_list(candidate.get("tags"))
    application = store.obj(candidate.get("application_data"), "application_data")
    expected = {
        "Biographical": (
            "First Name",
            "Last Name",
            "Sub Community Details",
            "Phonepe test",
            "employee typee",
        ),
        "Contact": ("Personal Email ID", "Country Code Personal", "Personal mobile no"),
        "Work Experience": ("Currently working here",),
        "References": ("Reference Name", "Reference Email"),
        "Professional References": (
            "Reference Provider Name",
            "Reference Provider Email",
        ),
    }
    for section, fields in expected.items():
        entries = (
            [application.get(section)]
            if section in ("Biographical", "Contact")
            else store.array(application.get(section), section)
        )
        for entry in entries:
            entry = store.obj(entry, section)
            if any(not isinstance(entry.get(field), str) for field in fields):
                raise store.BusinessError(
                    "Candidate application fields must be strings"
                )
