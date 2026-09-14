import json

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment
from itops_env.server.mcp_servers import tools
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def clear_tool_definition_cache():
    tools.tool_definitions.cache_clear()
    yield
    tools.tool_definitions.cache_clear()


def test_default_tool_duration_is_strictly_positive():
    raw = load_scenario().model_dump()
    for invalid in (0, -1, True, 1.5):
        with pytest.raises(ValidationError):
            Scenario.model_validate({**raw, "default_tool_cost": invalid})
    assert (
        Scenario.model_validate({**raw, "default_tool_cost": 7}).default_tool_cost == 7
    )


def test_only_registered_business_tools_can_override_costs():
    raw = load_scenario().model_dump()
    for name in ("unknown.action", "benchmark.workflow_wait"):
        with pytest.raises(ValidationError):
            Scenario.model_validate({**raw, "costs": raw["costs"] | {name: 2}})


def test_business_overrides_and_invalid_calls_use_separate_literal_durations(
    monkeypatch,
):
    def register_tools(mcp, dispatch):
        @mcp.tool
        async def inspect_target(target: str):
            return await dispatch("inspect_target", {"target": target})

        return (inspect_target,)

    def inspect_handler(db, arguments, step, clock):
        return {"target": arguments["target"]}, False

    monkeypatch.setitem(tools.REGISTRARS, "test_provider", register_tools)
    monkeypatch.setitem(
        tools.HANDLER_RESOLVERS,
        "test_provider",
        lambda: {"inspect_target": inspect_handler},
    )
    tools.tool_definitions.cache_clear()

    raw = load_scenario().model_dump()
    raw["default_tool_cost"] = 3
    raw["costs"] = raw["costs"] | {"invalid": 4}
    scenario = Scenario.model_validate(raw)
    env = ItopsEnvironment(scenario=scenario)
    env.reset()
    try:
        response = env.step(
            ItopsAction(
                provider="test_provider",
                tool_name="inspect_target",
                arguments={"target": "alpha"},
            )
        )
        assert json.loads(response.content[0]["text"]) == {"target": "alpha"}
        assert env.state.step_count == 1
        assert env.state.simulated_clock == 3

        invalid = env.step(
            ItopsAction(
                provider="test_provider",
                tool_name="inspect_target",
                arguments={"target": 1},
            )
        )
        assert invalid.is_error
        assert env.state.step_count == 2
        assert env.state.simulated_clock == 7
    finally:
        env.close()

    overridden = Scenario.model_validate(
        raw | {"costs": raw["costs"] | {"test_provider.inspect_target": 5}}
    )
    env = ItopsEnvironment(scenario=overridden)
    env.reset()
    try:
        env.step(
            ItopsAction(
                provider="test_provider",
                tool_name="inspect_target",
                arguments={"target": "alpha"},
            )
        )
        assert env.state.step_count == 1
        assert env.state.simulated_clock == 5
    finally:
        env.close()
        tools.tool_definitions.cache_clear()
