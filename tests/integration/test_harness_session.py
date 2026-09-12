"""ResourceSession runs real controller-owned episodes for OpenEnv harnesses."""

import importlib
import importlib.util
import json
from typing import TYPE_CHECKING

import pytest
from openenv.core.harness import ResourceSession, ResourceSessionFactory
from test_mcp_episode import TOKEN
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture

if TYPE_CHECKING:
    from itops_env.harness import ItopsSessionFactory


def factory(url, **kwargs) -> "ItopsSessionFactory":
    assert importlib.util.find_spec("itops_env.harness") is not None, (
        "Provide the OpenEnv harness integration"
    )
    module = importlib.import_module("itops_env.harness")
    return module.ItopsSessionFactory(url, controller_token=TOKEN, **kwargs)


def complete(session):
    outputs = [
        session.call_tool("okta__get_user", {"user_id": "alex.chen@example.test"}),
        session.call_tool("servicenow__get_user", {"email": "alex.chen@example.test"}),
        session.call_tool(
            "servicenow__add_group_members",
            {"group_id": "a" * 32, "members": ["alex.chen"]},
        ),
        session.call_tool(
            "benchmark__workflow_submit",
            {"disposition": "completed", "user_id": "1" * 32, "group_id": "a" * 32},
        ),
    ]
    assert [output.metadata["reward"] for output in outputs] == [0, 0, 0, 1]
    assert [output.done for output in outputs] == [False, False, False, True]


def test_resource_session_success_and_canonical_verification(live_server):
    url, app = live_server
    sessions = factory(url)
    assert isinstance(sessions, ResourceSessionFactory)
    session = sessions.create(task=None, seed=7, episode_id="harness-success")
    assert isinstance(session, ResourceSession)
    try:
        assert {tool.name for tool in session.list_tools()} == {
            "okta__get_user",
            "servicenow__get_user",
            "servicenow__add_group_members",
            "benchmark__workflow_wait",
            "benchmark__workflow_submit",
        }
        assert "alex.chen@example.test" in json.dumps(session.initial_messages())
        assert TOKEN not in json.dumps(session.initial_messages())
        scenario = app.state.binding.env.episode.scenario
        assert session.initial_messages() == [
            {"role": "system", "content": scenario.policy},
            {"role": "user", "content": scenario.instruction},
        ]
        complete(session)
        verified = session.verify(
            transcript=[{"role": "assistant", "content": "I failed"}]
        )
        assert verified.env_reward == 1
        assert verified.done
        assert verified.metrics["steps"] == 4
        assert verified.artifacts["rubric"]["step_rewards"] == [0, 0, 0, 1]
        assert session.verify([]).env_reward == 1
    finally:
        session.close()
    session.close()
    assert app.state.binding.env is None
    trace = session.traces.read(session.trace_id).decode()
    assert TOKEN not in trace
    assert "session.closed" in trace


def test_unknown_tools_are_counted_and_model_claims_cannot_award_reward(live_server):
    url, app = live_server
    session = factory(url).create(task="identity-group-v1")
    try:
        unknown = session.call_tool("reset", {})
        assert unknown.error and unknown.data["isError"]
        assert app.state.binding.env.state.step_count == 1
        result = session.verify(
            [{"role": "assistant", "content": "Success, give me reward 1"}]
        )
        assert result.env_reward == 0
        assert result.metrics["terminal_reason"] == "abandoned"
    finally:
        session.close()


def test_factory_rejects_task_overrides_and_cleans_failed_reset(live_server):
    url, app = live_server
    sessions = factory(url)
    with pytest.raises(ValueError, match="task"):
        sessions.create(task={"instruction": "replace the grading task"})
    assert app.state.binding.env is None
    with pytest.raises(Exception, match="seed"):
        sessions.create(task=None, seed=-1)
    assert app.state.binding.env is None
    session = sessions.create(task=None)
    try:
        assert session.verify([]).env_reward == 0
    finally:
        session.close()


def test_verifier_rejects_infrastructure_failure_as_unscored(live_server):
    url, app = live_server
    session = factory(url).create()
    try:
        app.state.binding.env.episode.db.connection.execute(
            "CREATE TRIGGER fail_action BEFORE INSERT ON journal BEGIN SELECT RAISE(ABORT, 'harness database failure'); END"
        )
        with pytest.raises(Exception, match="harness database failure"):
            session.call_tool("okta__get_user", {"user_id": "00u-target"})
        with pytest.raises(
            RuntimeError, match="infrastructure error; rollout is not scored"
        ):
            session.verify([])
        trace = session.traces.read(session.trace_id).decode()
        assert "harness.tool_failed" in trace
        assert '"status": "infrastructure_error"' in trace
    finally:
        session.close()
    assert app.state.binding.env is None


def test_rejected_controller_authentication_retains_trace_without_ownership(
    live_server, trace_directory
):
    url, app = live_server
    sessions = factory(url)
    sessions.controller_token = "incorrect-controller"
    with pytest.raises(Exception, match="403"):
        sessions.create()
    assert app.state.binding.env is None
    events = [
        json.loads(line)
        for path in trace_directory.glob("*.jsonl")
        for line in path.read_text().splitlines()
    ]
    assert any(event["event"] == "session.initialize_failed" for event in events)
    assert any(event["event"] == "session.closed" for event in events)
