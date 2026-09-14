"""Nonempty source-typed recruitment and master fixtures exercise every filter."""

from contextlib import closing

import pytest
from pydantic import ValidationError

from .test_darwinbox import fixture_world, ok, records


def job():
    listing = {
        "job_id": "J1",
        "job_code": "ENG",
        "group_company": "Acme",
        "parent_department": "Product",
        "department": "Engineering",
        "division": None,
        "business_unit": "Software",
        "location": ["Remote"],
        "location_city": [],
        "location_country": "IN",
        "job_title": "Engineer",
        "post_on_careers_page": 1,
        "post_on_refer_page": 1,
        "post_on_ijp_page": 0,
        "employee_type": "Full time",
        "job_created_timestamp": "01-01-2025 00:00:00",
        "job_updated_timestamp": "03-01-2026 12:00:00",
        "experience_to": "5",
        "experience_from": "2",
        "is_remote": 1,
    }
    detail = {
        key: listing[key]
        for key in (
            "job_title",
            "group_company",
            "department",
            "parent_department",
            "employee_type",
            "experience_from",
            "experience_to",
            "location",
            "location_city",
            "location_country",
            "post_on_careers_page",
            "post_on_refer_page",
            "post_on_ijp_page",
            "job_created_timestamp",
            "job_updated_timestamp",
        )
    }
    detail.update(
        department_code="ENG",
        designation_code="SWE",
        designation="Engineer",
        band="B",
        grade="G",
        salary_min="100",
        salary_max="200",
        salary_currency="INR",
        unit_experience="years",
        job_decription="Build services",
        total_positions=2,
        open_positions=1,
        job_status="open",
        hiring_lead=[],
        screening_team=[],
        shortlisting_team=[],
        scheduling_team=[],
        hiring_group=[],
        applicant_fields={},
    )
    return {"kind": "job", "id": "J1", "data": {"listing": listing, "detail": detail}}


def candidate():
    return {
        "kind": "candidate",
        "id": "C1",
        "data": {
            "modified": "04-01-2026 12:00:00",
            "candidate": {
                "unique_id": "C1",
                "candidate_id": None,
                "firstname": "Ada",
                "lastname": "L",
                "email": "ada@example.test",
                "phone": "123",
                "job_id": "J1",
                "status": "applied",
                "source_type": "career",
                "source_name": "website",
                "tags": [],
                "created_date": "01-01-2025",
                "application_data": {
                    "Biographical": {
                        "First Name": "Ada",
                        "Last Name": "L",
                        "Sub Community Details": "",
                        "Phonepe test": "",
                        "employee typee": "",
                    },
                    "Contact": {
                        "Personal Email ID": "ada@example.test",
                        "Country Code Personal": "+91",
                        "Personal mobile no": "123",
                    },
                    "Work Experience": [],
                    "References": [],
                    "Professional References": [],
                },
            },
        },
    }


def master_records():
    return records() + [
        job(),
        candidate(),
        {
            "kind": "position",
            "id": "P1",
            "data": {
                "employee_no": "E1",
                "status": 1,
                "need_to_hire": 0,
                "title": "Engineer",
            },
        },
        {
            "kind": "form",
            "id": "F1",
            "data": {
                "employee_no": "E1",
                "form_id": "Review",
                "type": "annual",
                "form_type": "HR",
                "date": "03-01-2026",
                "answers": {"rating": 4},
            },
        },
        {
            "kind": "holiday",
            "id": "H1",
            "data": {"employee_no": "E1", "date": "01-01-2026", "name": "New year"},
        },
        {
            "kind": "roster",
            "id": "R1",
            "data": {
                "employee_no": "E1",
                "date": "2026-01-03",
                "shift_name": "Morning",
            },
        },
    ]


def test_nonempty_master_and_recruitment_filters():
    with closing(fixture_world(master_records())) as env:
        env.reset()
        assert (
            ok(
                env,
                "get_position_master",
                status=1,
                need_to_hire=0,
                employee_nos=["E1"],
            )[0]["title"]
            == "Engineer"
        )
        assert (
            ok(
                env,
                "get_position_master",
                status=1,
                need_to_hire=1,
                employee_nos=["E1"],
            )
            == []
        )
        forms = {
            "form_id": "Review",
            "type": "annual",
            "form_type": "HR",
            "from": "03-01-2026",
            "to": "03-01-2026",
        }
        assert ok(env, "get_forms_data", **forms)[0]["answers"] == {"rating": 4}
        assert ok(env, "get_forms_data", **(forms | {"type": "other"})) == []
        assert (
            ok(env, "get_holiday_list", list={"year": "2026", "employee_no": "E1"})[0][
                "name"
            ]
            == "New year"
        )
        assert (
            ok(env, "get_holiday_list", list={"year": "2025", "employee_no": "E1"})
            == []
        )
        assert (
            ok(
                env,
                "get_attendance_roster",
                emp_number_list=["E1"],
                from_date="2026-01-03",
                to_date="2026-01-03",
            )[0]["shift_name"]
            == "Morning"
        )
        listing = ok(
            env, "get_job_listings", job_updated_timestamp_from="03-01-2026 11:59:59"
        )
        assert listing == [job()["data"]["listing"]]
        assert (
            ok(
                env,
                "get_job_listings",
                job_updated_timestamp_from="03-01-2026 12:00:00",
            )
            == []
        )
        assert ok(env, "get_job_detail", job_id="J1") == job()["data"]["detail"]
        candidates = ok(
            env,
            "get_bulk_candidates",
            updated_from="04-01-2026 12:00:00",
            updated_to="04-01-2026 12:00:00",
        )
        assert candidates == [candidate()["data"]["candidate"]]
        assert (
            "modified" not in candidates[0]
            and candidates[0]["created_date"] == "01-01-2025"
        )


@pytest.mark.parametrize(
    "row",
    [
        {"kind": "employee", "id": "E1", "data": {"employee_no": "E1"}},
        {
            "kind": "employee",
            "id": "E2",
            "data": {"employee_no": "E2", "employee_id": []},
        },
        {
            "kind": "allocation",
            "id": "A2",
            "data": {"employee_no": "E1", "leave_name": "Annual", "balance": 4},
        },
        {
            "kind": "allocation",
            "id": "A2",
            "data": {"employee_no": [], "leave_name": "Annual", "balance": 4},
        },
        {
            "kind": "allocation",
            "id": "A2",
            "data": {"employee_no": "E1", "leave_name": "Other", "balance": "4"},
        },
        {
            "kind": "allocation",
            "id": "A2",
            "data": {
                "employee_no": "E1",
                "leave_name": "Other",
                "balance": float("inf"),
            },
        },
        {
            "kind": "roster",
            "id": "R1",
            "data": {
                "employee_no": "missing",
                "date": "2026-01-01",
                "shift_name": "Morning",
            },
        },
        {
            "kind": "position",
            "id": "P1",
            "data": {"employee_no": "", "status": 1, "need_to_hire": 0},
        },
        {
            "kind": "form",
            "id": "F1",
            "data": {"employee_no": "E1", "form_id": {}, "date": "01-01-2026"},
        },
        {
            "kind": "candidate",
            "id": "C1",
            "data": candidate()["data"] | {"modified": []},
        },
    ],
)
def test_fixture_identity_types_and_references_rejected(row):
    with pytest.raises(ValidationError):
        fixture_world(records() + [row])


def test_fixture_punch_retry_is_idempotent_across_fixture_identity():
    punch = {
        "employee_no": "E1",
        "id": "P1",
        "machineid": "M1",
        "status": "in",
        "timestamp": "2026-01-02 09:00:00",
    }
    with closing(
        fixture_world(
            records() + [{"kind": "punch", "id": "fixture-P1", "data": punch}]
        )
    ) as env:
        env.reset()
        ok(
            env,
            "record_attendance_punches",
            attendance={"E1": [{k: v for k, v in punch.items() if k != "employee_no"}]},
        )
        result = ok(
            env,
            "get_daily_attendance",
            emp_number_list=["E1"],
            from_date="2026-01-02",
            to_date="2026-01-02",
        )
        assert len(result[0]["punches"]) == 1


def test_backdated_fixture_write_replaces_one_business_day():
    row = {
        "employee_no": "E1",
        "shift_date": "2026-01-03",
        "in_time_date": "2026-01-03",
        "in_time": "09:00:00",
        "out_time_date": "2026-01-03",
        "out_time": "17:00:00",
        "shift_name": "day",
        "policy_name": "standard",
        "weekly_off_name": "Sunday",
        "break_duration": "30",
    }
    with closing(
        fixture_world(
            records() + [{"kind": "backdated", "id": "fixture-B1", "data": row}]
        )
    ) as env:
        env.reset()
        ok(
            env,
            "record_backdated_attendance",
            attendance={"attendance_data": [row | {"out_time": "18:00:00"}]},
        )
        result = ok(
            env,
            "get_daily_attendance",
            emp_number_list=["E1"],
            from_date="2026-01-03",
            to_date="2026-01-03",
        )
        assert result[0]["backdated"]["out_time"] == "18:00:00"
