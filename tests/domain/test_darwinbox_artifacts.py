import json
import sqlite3

import pytest
from itops_env import ItopsAction

from .test_darwinbox import call, employee
from .test_darwinbox import env as world_fixture

env = world_fixture


def test_attachment_replay_rollback_and_cross_provider_independence(env):
    assert env.episode is not None
    db = env.episode.db
    before = {
        table: [tuple(row) for row in db.connection.execute(f"SELECT * FROM {table}")]
        for table in ("okta_users", "servicenow_users", "erpnext_documents")
    }
    employee(env)
    request = ItopsAction(
        provider="darwinbox",
        tool_name="upload_profile_attachments",
        arguments={
            "employee_no": "E1",
            "section": "personal",
            "section_attribute": "proof",
            "attachment": "ZXZpZGVuY2U=",
        },
        invocation_id="same-attachment",
    )
    first = env.step(request)
    replay = env.step(request)
    assert not first.is_error and first.content == replay.content
    assert env.state.step_count == 2 and env.state.simulated_clock == 2
    doc = json.loads(first.content[0]["text"])["data"]
    assert db.artifact(doc["artifact_path"])["content"] == b"evidence"
    employee(env, "E2")
    assert call(env, "download_personal_docs", employee_no="E2", **{"for": "proof"})[1]
    db.connection.execute(
        "CREATE TRIGGER reject_darwinbox_artifact BEFORE INSERT ON episode_artifacts BEGIN SELECT RAISE(ABORT, 'artifact denied'); END"
    )
    step = env.state.step_count
    with pytest.raises(sqlite3.IntegrityError, match="artifact denied"):
        env.step(
            ItopsAction(
                provider="darwinbox",
                tool_name="upload_profile_attachments",
                arguments=request.arguments,
            )
        )
    assert env.state.step_count == step
    assert (
        db.connection.execute(
            "SELECT count(*) FROM darwinbox_records WHERE kind='attachment'"
        ).fetchone()[0]
        == 1
    )
    assert (
        db.connection.execute("SELECT count(*) FROM episode_artifacts").fetchone()[0]
        == 1
    )
    after = {
        table: [tuple(row) for row in db.connection.execute(f"SELECT * FROM {table}")]
        for table in before
    }
    assert after == before
    env.reset()
    assert (
        env.episode is not None
        and env.episode.db.artifact(doc["artifact_path"]) is None
    )


@pytest.mark.parametrize(
    "tool,args",
    [
        ("add_employee", {"employees": {"employee_no": []}}),
        ("update_employee", {"employee_data": {"employee_no": {}}}),
        (
            "deactivate_employee",
            {
                "employees": [
                    {
                        "employee_id": "E1",
                        "deactivate_type": [],
                        "deactivate_reason": "x",
                        "date_of_resignation": "01-01-2026",
                        "date_of_exit": "02-01-2026",
                    }
                ]
            },
        ),
        ("record_backdated_attendance", {"attendance": {"attendance_data": [None]}}),
        ("record_attendance_punches", {"attendance": {"E1": [{}]}}),
        (
            "get_leave_action_history",
            {
                "history": {
                    "from": "01-01-2026",
                    "to": "02-01-2026",
                    "action": [],
                    "employee_no": ["E1"],
                    "unpaid": "0",
                }
            },
        ),
        ("get_holiday_list", {"list": {"year": "2026", "employee_no": []}}),
    ],
)
def test_schema_open_wrappers_reject_malformed_inner_fields(env, tool, args):
    employee(env)
    value, error = call(env, tool, **args)
    assert error and value["error"]
    assert env.state.phase == "active"
