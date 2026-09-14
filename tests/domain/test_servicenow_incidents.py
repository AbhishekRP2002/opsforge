import json

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import load_scenario
from itops_env.server.itops_environment import ItopsEnvironment


@pytest.fixture
def env():
    scenario = load_scenario().model_copy(update={"step_budget": 500, "horizon": 2000})
    world = ItopsEnvironment(scenario=scenario)
    world.reset()
    yield world
    world.close()


def call(env, tool, **arguments):
    result = env.step(
        ItopsAction(provider="servicenow", tool_name=tool, arguments=arguments)
    )
    return json.loads(result.content[0]["text"]), result.is_error


def test_incident_mutations_resolve_number_and_preserve_source_mapping(env):
    created, error = call(
        env, "create_incident", short_description="Network", ignored="raw"
    )
    assert error
    assert env.state.step_count == 1 and env.state.simulated_clock == 1
    assert call(env, "list_incidents")[0]["incidents"] == []
    created, error = call(env, "create_incident", short_description="Network")
    assert not error and created["success"]
    number, identifier = created["incident_number"], created["incident_id"]
    assert call(
        env, "update_incident", incident_id=number, description="WAN", state="custom"
    )[0]["success"]
    assert call(env, "add_comment", incident_id=identifier, comment="Investigating")[0][
        "success"
    ]
    assert call(
        env,
        "resolve_incident",
        incident_id=number,
        resolution_code="Solved",
        resolution_notes="Fixed",
    )[0]["success"]
    found, error = call(env, "get_incident_by_number", incident_number=number)
    assert not error and found["incident"]["description"] == "WAN"
    assert found["incident"]["state"] == "6"
    listed, error = call(env, "list_incidents", state="6", query="WAN")
    assert not error and len(listed["incidents"]) == 1
    assert listed["incidents"][0]["sys_id"] == identifier


@pytest.mark.parametrize(
    "tool,args",
    [
        ("create_incident", {"short_description": "Bad", "assigned_to": "absent"}),
        ("update_incident", {"incident_id": "absent"}),
        ("add_comment", {"incident_id": "absent", "comment": "note"}),
        (
            "resolve_incident",
            {"incident_id": "absent", "resolution_code": "x", "resolution_notes": "x"},
        ),
        ("get_incident_by_number", {"incident_number": "absent"}),
        ("list_incidents", {"limit": -1}),
    ],
)
def test_incident_business_failures_keep_mcp_success(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and value["success"] is False


def test_source_defaults_and_extra_keys_do_not_change_raw_invocation(env):
    action = ItopsAction(
        provider="servicenow",
        tool_name="create_incident",
        arguments={"short_description": "Defaults", "extra": 9},
        invocation_id="raw",
    )
    result = env.step(action)
    assert result.is_error
    assert action.arguments == {"short_description": "Defaults", "extra": 9}
    assert env.step(action).content == result.content
    assert env.state.step_count == 1
    assert env.state.simulated_clock == 1
    assert call(env, "list_incidents")[0]["incidents"] == []
    valid = ItopsAction(
        provider="servicenow",
        tool_name="create_incident",
        arguments={"short_description": "Defaults"},
        invocation_id="valid-defaults",
    )
    result = env.step(valid)
    assert not result.is_error
    assert valid.arguments == {"short_description": "Defaults"}
    assert env.step(valid).content == result.content
    assert env.state.step_count == 3 and env.state.simulated_clock == 3
