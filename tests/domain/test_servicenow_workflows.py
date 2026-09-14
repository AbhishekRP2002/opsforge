import pytest
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment

from .test_servicenow_incidents import call

WF = "dddddddddddddddddddddddddddddddd"
VERSION = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"


@pytest.mark.parametrize("value", [-1, "-1", "+2", " 3 ", "١"])
def test_supported_integer_representations_remain_readable(env, value):
    result = call(
        env,
        "add_workflow_activity",
        workflow_version_id=VERSION,
        name="Valid",
        activity_type="custom",
        attributes={"order": value, "opaque": {"x": []}},
    )[0]
    assert result["activity"]["order"] == value
    assert call(env, "get_workflow_activities", workflow_id=WF)[0]["count"] == 1


def test_activity_parent_cannot_be_cleared_by_attributes(env):
    result = call(
        env,
        "add_workflow_activity",
        workflow_version_id=VERSION,
        name="Valid",
        activity_type="custom",
    )[0]
    key = result["activity"]["sys_id"]
    before = call(env, "get_workflow_activities", workflow_id=WF)[0]
    rejected, error = call(
        env,
        "update_workflow_activity",
        activity_id=key,
        attributes={"workflow_version": ""},
    )
    assert not error and "simulation_profile" in rejected["error"]
    assert call(env, "get_workflow_activities", workflow_id=WF)[0] == before


@pytest.mark.parametrize("value", ["--1", "²"])
def test_invalid_integer_strings_do_not_enter_workflow_state(env, value):
    result, error = call(
        env,
        "add_workflow_activity",
        workflow_version_id=VERSION,
        name="Bad",
        activity_type="custom",
        attributes={"order": value},
    )
    assert not error and "simulation_profile" in result["error"]
    assert call(env, "get_workflow_activities", workflow_id=WF)[0]["count"] == 0


@pytest.mark.parametrize(
    "field,table", [("order", "wf_activity"), ("version", "wf_workflow_version")]
)
@pytest.mark.parametrize("value", ["--1", "²"])
def test_invalid_integer_fixture_strings(field, table, value):
    from pydantic import ValidationError

    raw = load_scenario().model_dump()
    raw["servicenow_records"] = [{"table": table, "sys_id": WF, "data": {field: value}}]
    with pytest.raises(ValidationError, match="Workflow fixture"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize(
    "table,data",
    [
        ("wf_workflow", {"name": []}),
        ("wf_activity", {"order": {}}),
        ("wf_workflow_version", {"version": "invalid"}),
    ],
)
def test_workflow_fixture_interpreted_fields_are_validated(table, data):
    from pydantic import ValidationError

    raw = load_scenario().model_dump()
    raw["servicenow_records"] = [{"table": table, "sys_id": WF, "data": data}]
    with pytest.raises(ValidationError, match="Workflow fixture"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize(
    "attributes",
    [
        {"name": []},
        {"table": {}},
        {"active": []},
        {"order": {}},
        {"workflow_version": [VERSION]},
    ],
)
def test_interpreted_attributes_are_validated_without_mutation(env, attributes):
    before = call(env, "get_workflow_details", workflow_id=WF)[0]
    created, error = call(env, "create_workflow", name="Probe", attributes=attributes)
    assert not error and "simulation_profile" in created["error"]
    updated, error = call(env, "update_workflow", workflow_id=WF, attributes=attributes)
    assert not error and "simulation_profile" in updated["error"]
    assert call(env, "get_workflow_details", workflow_id=WF)[0] == before
    assert call(env, "list_workflows", name="Probe")[0]["total"] == 0
    added, error = call(
        env,
        "add_workflow_activity",
        workflow_version_id=VERSION,
        name="Probe",
        activity_type="custom",
        attributes=attributes,
    )
    assert not error and "simulation_profile" in added["error"]
    assert call(env, "get_workflow_activities", workflow_id=WF)[0]["count"] == 0


@pytest.fixture
def env():
    raw = load_scenario().model_dump() | {
        "step_budget": 500,
        "horizon": 2000,
        "servicenow_records": [
            {
                "table": "wf_workflow",
                "sys_id": WF,
                "data": {"name": "Seed", "active": True},
            },
            {
                "table": "wf_workflow_version",
                "sys_id": VERSION,
                "data": {"workflow": WF, "version": "2", "published": True},
            },
        ],
    }
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    yield world
    world.close()


def test_workflow_lifecycle_attributes_and_real_totals(env):
    created, error = call(
        env, "create_workflow", name="New", attributes={"custom": {"nested": [1]}}
    )
    assert not error and created["workflow"]["custom"] == {"nested": [1]}
    key = created["workflow"]["sys_id"]
    assert (
        call(env, "update_workflow", workflow_id=key, description="Updated")[0][
            "workflow"
        ]["description"]
        == "Updated"
    )
    assert (
        call(env, "deactivate_workflow", workflow_id=key)[0]["workflow"]["active"]
        == "false"
    )
    assert (
        call(env, "activate_workflow", workflow_id=key)[0]["workflow"]["active"]
        == "true"
    )
    detail = call(env, "get_workflow_details", workflow_id=key, include_versions=True)[
        0
    ]
    assert set(detail) == {"workflow"} and detail["workflow"]["name"] == "New"
    listed = call(env, "list_workflows", limit=1)[0]
    assert listed["count"] == 1 and listed["total"] == 2


def test_workflow_versions_activity_order_partial_failure_and_deletion(env):
    versions = call(env, "list_workflow_versions", workflow_id=WF)[0]
    assert versions["total"] == 1 and versions["versions"][0]["sys_id"] == VERSION
    added, error = call(
        env,
        "add_workflow_activity",
        workflow_version_id=VERSION,
        name="Task",
        activity_type="custom",
        attributes={"order": 900},
    )
    assert not error and added["activity"]["workflow_version"] == VERSION
    key = added["activity"]["sys_id"]
    assert (
        call(env, "update_workflow_activity", activity_id=key, name="Renamed")[0][
            "activity"
        ]["name"]
        == "Renamed"
    )
    reordered = call(
        env, "reorder_workflow_activities", workflow_id=WF, activity_ids=[key, "absent"]
    )[0]
    assert reordered["results"][0] == {
        "activity_id": key,
        "new_order": 100,
        "success": True,
    }
    assert reordered["results"][1]["success"] is False
    activities = call(env, "get_workflow_activities", workflow_id=WF)[0]
    assert (
        activities["version_id"] == VERSION
        and activities["activities"][0]["order"] == 100
    )
    assert (
        call(env, "delete_workflow_activity", activity_id=key)[0]["activity_id"] == key
    )
    assert call(env, "get_workflow_activities", workflow_id=WF)[0]["count"] == 0


@pytest.mark.parametrize(
    "tool,args",
    [
        ("create_workflow", {"name": ""}),
        ("update_workflow", {"workflow_id": WF}),
        ("activate_workflow", {"workflow_id": "absent"}),
        ("deactivate_workflow", {"workflow_id": "absent"}),
        ("get_workflow_details", {"workflow_id": "absent"}),
        ("list_workflows", {"query": "nameINa,b"}),
        ("list_workflow_versions", {"workflow_id": ""}),
        ("get_workflow_activities", {"workflow_id": "absent"}),
        (
            "add_workflow_activity",
            {"workflow_version_id": "absent", "name": "Bad", "activity_type": "task"},
        ),
        ("update_workflow_activity", {"activity_id": "absent", "name": "Bad"}),
        ("delete_workflow_activity", {"activity_id": "absent"}),
        ("reorder_workflow_activities", {"workflow_id": WF, "activity_ids": []}),
    ],
)
def test_workflow_errors_preserve_error_envelope_and_mcp_success(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and "error" in value and "success" not in value
