import pytest

from .test_servicenow_incidents import call
from .test_servicenow_incidents import env as snow_fixture

env = snow_fixture


def test_changes_tasks_and_first_approval_state_transitions(env):
    created, error = call(
        env, "create_change_request", short_description="Deploy", type="custom"
    )
    assert not error and created["success"]
    key = created["change_request"]["sys_id"]
    assert (
        call(env, "update_change_request", change_id=key, description="Plan")[0][
            "change_request"
        ]["description"]
        == "Plan"
    )
    task = call(env, "add_change_task", change_id=key, short_description="Deploy task")[
        0
    ]
    assert task["change_task"]["change_request"] == key
    assert len(call(env, "get_change_request_details", change_id=key)[0]["tasks"]) == 1
    assert (
        call(
            env, "submit_change_for_approval", change_id=key, approval_comments="Review"
        )[0]["approval"]["state"]
        == "requested"
    )
    assert call(
        env,
        "approve_change",
        change_id=key,
        approver_id="ignored",
        approval_comments="Approved",
    )[0] == {"success": True, "message": "Change request approved successfully"}
    assert (
        call(env, "get_change_request_details", change_id=key)[0]["change_request"][
            "state"
        ]
        == "implement"
    )
    assert call(
        env,
        "reject_change",
        change_id=key,
        rejection_reason="Rollback",
        approver_id="ignored",
    )[0]["success"]
    detail = call(env, "get_change_request_details", change_id=key)[0]["change_request"]
    assert (
        detail["state"] == "canceled"
        and detail["work_notes"] == "Change request rejected: Rollback"
    )
    listed = call(
        env, "list_change_requests", query="short_descriptionLIKEDeploy", limit=1
    )[0]
    assert listed["count"] == listed["total"] == 1


@pytest.mark.parametrize(
    "tool,args",
    [
        (
            "create_change_request",
            {"short_description": "Bad", "type": "normal", "requested_by": "absent"},
        ),
        ("update_change_request", {"change_id": "absent"}),
        ("list_change_requests", {"query": "stateIN1,2"}),
        ("get_change_request_details", {"change_id": "absent"}),
        ("add_change_task", {"change_id": "absent", "short_description": "Bad"}),
        ("submit_change_for_approval", {"change_id": "absent"}),
        ("approve_change", {"change_id": "absent"}),
        ("reject_change", {"change_id": "absent", "rejection_reason": "Bad"}),
    ],
)
def test_change_business_failures(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and value["success"] is False
