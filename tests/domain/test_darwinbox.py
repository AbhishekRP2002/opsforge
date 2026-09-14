"""Real Episode business workflows; expectations are independent literals."""

import base64
import json
from contextlib import closing

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment


@pytest.fixture
def env():
    world = ItopsEnvironment(
        scenario=load_scenario().model_copy(
            update={"step_budget": 1000, "horizon": 5000}
        )
    )
    world.reset()
    yield world
    world.close()


def call(env, tool, **arguments):
    result = env.step(
        ItopsAction(provider="darwinbox", tool_name=tool, arguments=arguments)
    )
    return json.loads(result.content[0]["text"]), result.is_error


def ok(env, tool, **arguments):
    result, error = call(env, tool, **arguments)
    assert not error, result
    return result["data"]


def employee(env, name="E1"):
    return ok(
        env, "add_employee", employees={"employee_no": name, "employee_name": "Ada"}
    )


def test_employee_lifecycle_and_history(env):
    employee(env)
    assert ok(env, "get_employee_details", employee_ids=[]) == []
    assert len(ok(env, "get_employee_details")) == 1
    updated = ok(
        env,
        "update_employee",
        employee_data={
            "employee_id": "E1",
            "employee_name": "Grace",
            "effective_date": "02-01-2026",
        },
    )
    assert updated["employee_no"] == "E1" and updated["employee_name"] == "Grace"
    assert (
        ok(env, "get_employee_details", employee_ids=["E1"], last_modified="invalid")[
            0
        ]["employee_name"]
        == "Grace"
    )
    history = ok(
        env,
        "get_employee_history",
        **{"from": "02-01-2026", "to": "02-01-2026", "filter_on_effective_date": 1},
    )
    assert len(history) == 1 and history[0]["before"]["employee_name"] == "Ada"
    assert history[0]["after"]["employee_name"] == "Grace"
    ok(
        env,
        "deactivate_employee",
        employees=[
            {
                "employee_id": "E1",
                "deactivate_type": "resigned",
                "deactivate_reason": "new role",
                "date_of_resignation": "01-01-2026",
                "date_of_exit": "03-01-2026",
            }
        ],
    )
    separated = ok(
        env, "get_separation_details", separation_status="resigned", employee_ids=["E1"]
    )
    assert len(separated) == 1 and separated[0]["deactivate_reason"] == "new role"
    assert ok(env, "get_employee_details")[0]["status"] == "inactive"


def test_employee_validation_and_batch_atomicity(env):
    employee(env)
    assert call(env, "add_employee", employees={"employee_no": "E1"})[1]
    assert call(
        env,
        "update_employee",
        employee_data={"employee_no": "E1", "employee_id": "other"},
    )[1]
    assert call(
        env, "update_employee", employee_data={"employee_no": "E1", "status": []}
    )[1]
    assert call(
        env,
        "deactivate_employee",
        employees=[
            {
                "employee_id": "E1",
                "deactivate_type": "x",
                "deactivate_reason": "y",
                "date_of_resignation": "01-01-2026",
                "date_of_exit": "02-01-2026",
            },
            {},
        ],
    )[1]
    assert ok(env, "get_employee_details")[0]["status"] == "active"


def test_deactivate_rejects_conflicting_alias_without_mutation(env):
    employee(env)
    assert call(
        env,
        "deactivate_employee",
        employees=[
            {
                "employee_id": "E1",
                "employee_no": "other",
                "deactivate_type": "resigned",
                "deactivate_reason": "new role",
                "date_of_resignation": "01-01-2026",
                "date_of_exit": "03-01-2026",
            }
        ],
    )[1]
    assert ok(env, "get_employee_details")[0]["status"] == "active"


def test_employee_modified_filter_is_exclusive_and_ids_are_authoritative(env):
    employee(env)
    assert (
        ok(env, "get_employee_details", last_modified="01-01-2026 00:00:00")[0][
            "employee_no"
        ]
        == "E1"
    )
    assert ok(env, "get_employee_details", last_modified="01-01-2026 00:00:01") == []
    assert (
        ok(
            env,
            "get_employee_details",
            employee_ids=[],
            last_modified="01-01-2026 00:00:00",
        )
        == []
    )


def test_personal_document_roundtrip_and_reset(env):
    employee(env)
    doc = ok(
        env,
        "upload_profile_attachments",
        employee_no="E1",
        section="personal",
        section_attribute="id_proof",
        attachment=base64.b64encode(b"evidence").decode(),
    )
    read = ok(env, "download_personal_docs", employee_no="E1", **{"for": "id_proof"})
    assert read[0]["artifact_path"] == doc["artifact_path"]
    assert base64.b64decode(read[0]["content_base64"]) == b"evidence"
    assert call(
        env, "download_personal_docs", employee_no="missing", **{"for": "id_proof"}
    )[1]
    assert call(
        env,
        "upload_profile_attachments",
        employee_no="E1",
        section="personal",
        section_attribute="id_proof",
        attachment="/etc/passwd",
    )[1]
    env.reset()
    assert ok(env, "get_employee_details") == []


def test_attendance_dedup_order_conflicts_and_backdated(env):
    employee(env)
    punches = [
        {
            "id": "out",
            "machineid": "M",
            "timestamp": "2026-01-02 17:00:00",
            "status": "out",
        },
        {
            "id": "in",
            "machineid": "M",
            "timestamp": "2026-01-02 09:00:00",
            "status": "in",
        },
    ]
    ok(env, "record_attendance_punches", attendance={"E1": punches})
    ok(env, "record_attendance_punches", attendance={"E1": punches})
    args = {
        "emp_number_list": ["E1"],
        "from_date": "2026-01-02",
        "to_date": "2026-01-02",
    }
    rows = ok(env, "get_daily_attendance", **args)
    assert [p["id"] for p in rows[0]["punches"]] == ["in", "out"]
    assert ok(env, "get_monthly_attendance", **args, month="2026-01") == rows
    assert call(
        env,
        "record_attendance_punches",
        attendance={"E1": [punches[0] | {"status": "in"}]},
    )[1]
    assert call(
        env,
        "record_attendance_punches",
        attendance={"E1": [punches[0] | {"id": "new"}], "missing": punches},
    )[1]
    assert ok(env, "get_daily_attendance", **args) == rows
    back = {
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
    ok(env, "record_backdated_attendance", attendance={"attendance_data": [back]})
    assert (
        ok(
            env,
            "get_daily_attendance",
            emp_number_list=["E1"],
            from_date="2026-01-03",
            to_date="2026-01-03",
        )[0]["backdated"]
        == back
    )


def leave(**updates):
    return {
        "employee_no": "E1",
        "leave_name": "Annual",
        "message": "rest",
        "from_date": "04-01-2026",
        "to_date": "05-01-2026",
        "is_half_day": "No",
        "is_paid_or_unpaid": "paid",
        "revoke_leave": "No",
    } | updates


def fixture_world(records):
    data = load_scenario().model_dump() | {
        "step_budget": 1000,
        "horizon": 5000,
        "darwinbox_records": records,
    }
    return ItopsEnvironment(scenario=Scenario.model_validate(data))


def records():
    return [
        {
            "kind": "employee",
            "id": "E1",
            "data": {"employee_no": "E1", "employee_name": "Ada"},
        },
        {
            "kind": "allocation",
            "id": "A1",
            "data": {"employee_no": "E1", "leave_name": "Annual", "balance": 10},
        },
    ]


def test_leave_approval_rejection_revocation_and_balance():
    with closing(fixture_world(records())) as world:
        world.reset()
        req = ok(world, "apply_leave", data=[leave()])[0]
        ok(
            world,
            "approve_leave",
            leave_id=req["leave_id"],
            employee_no="E1",
            action="approve",
        )
        ok(
            world,
            "approve_leave",
            leave_id=req["leave_id"],
            employee_no="E1",
            action="approve",
        )
        assert (
            ok(world, "get_leave_balance", employee_nos=["E1"])[0][
                "currently_availabel_balance"
            ]
            == 8
        )
        assert call(
            world,
            "approve_leave",
            leave_id=req["leave_id"],
            employee_no="E1",
            action="reject",
        )[1]
        ok(
            world,
            "apply_leave",
            data=[leave(revoke_leave="Yes", revoke_reason="cancelled")],
        )
        ok(
            world,
            "apply_leave",
            data=[leave(revoke_leave="Yes", revoke_reason="cancelled")],
        )
        assert (
            ok(world, "get_leave_balance", employee_nos=["E1"])[0][
                "currently_availabel_balance"
            ]
            == 10
        )
        history = ok(
            world,
            "get_leave_action_history",
            history={
                "from": "01-01-2026",
                "to": "01-01-2026",
                "action": "approve",
                "employee_no": ["E1"],
                "unpaid": "0",
            },
        )
        assert len(history) == 1 and history[0]["leave_id"] == req["leave_id"]


@pytest.mark.parametrize(
    "tool,args",
    [
        ("get_employee_details", {"last_modified": "bad"}),
        (
            "get_employee_history",
            {"from": "02-01-2026", "to": "01-01-2026", "filter_on_effective_date": 0},
        ),
        (
            "get_separation_details",
            {"separation_status": "x", "employee_ids": ["missing"]},
        ),
        (
            "get_daily_attendance",
            {"emp_number_list": [], "from_date": "bad", "to_date": "bad"},
        ),
        (
            "get_monthly_attendance",
            {
                "emp_number_list": [],
                "from_date": "2026-01-01",
                "to_date": "2026-01-02",
                "month": "bad",
            },
        ),
        (
            "get_attendance_roster",
            {
                "emp_number_list": ["missing"],
                "from_date": "2026-01-01",
                "to_date": "2026-01-02",
            },
        ),
        ("record_backdated_attendance", {"attendance": {"attendance_data": [{}]}}),
        ("apply_leave", {"data": [leave()]}),
        (
            "approve_leave",
            {"employee_no": "E1", "leave_id": "missing", "action": "approve"},
        ),
        ("get_leave_balance", {"employee_nos": [], "ignore_rounding": "2"}),
        ("get_leave_action_history", {"history": {"from": []}}),
        ("get_holiday_list", {"list": {"year": [], "employee_no": "E1"}}),
        ("get_position_master", {"status": 1, "need_to_hire": 2, "employee_nos": []}),
        (
            "get_forms_data",
            {"form_id": "F", "type": "x", "form_type": "x", "from": "bad", "to": "bad"},
        ),
        ("get_job_listings", {"job_updated_timestamp_from": "bad"}),
        ("get_job_detail", {"job_id": "missing"}),
        (
            "get_bulk_candidates",
            {
                "updated_from": "02-01-2026 00:00:00",
                "updated_to": "01-01-2026 00:00:00",
            },
        ),
    ],
)
def test_invalid_tools_are_deliberate_errors(env, tool, args):
    value, error = call(env, tool, **args)
    assert error and value["error"]
    assert env.state.phase == "active"
