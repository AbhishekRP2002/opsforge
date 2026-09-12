"""Real harness rollouts with deterministic model callbacks and actual server effects."""

import importlib
import json
import re
from pathlib import Path

import pytest
from openenv.core.harness import (
    CLIHarnessAdapter,
    HarnessRolloutResult,
    HarnessRunLimits,
    ModelStepResult,
    ToolResult,
    ToolTraceEntry,
)
from openenv.core.harness.collect import CollectRunner, RolloutSerializer
from openenv.core.llm_client import LLMResponse, ToolCall
from test_harness_session import complete, factory
from test_mcp_episode import TOKEN
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def scripted_step(messages, tools, sampling):
    """A deterministic callback exercises model interfaces without an API call."""
    assert {tool.name for tool in tools} >= {"okta__get_user", "servicenow__get_user"}
    responses = [message for message in messages if message["role"] == "tool"]
    instruction = next(
        message["content"] for message in messages if message["role"] == "user"
    )
    group_match = re.search(r"\b[a-f0-9]{32}\b", instruction)
    assert group_match is not None
    group = group_match.group()
    turn = len(responses)
    if turn == 0:
        email_match = re.search(r"[\w.+-]+@[\w.-]+", instruction)
        assert email_match is not None
        name, arguments = (
            "okta__get_user",
            {"user_id": email_match.group()},
        )
    else:
        values = [
            json.loads(json.loads(message["content"])["content"][0]["text"])
            for message in responses
        ]
        if turn == 1:
            name, arguments = (
                "servicenow__get_user",
                {"email": values[0][0]["profile"]["email"]},
            )
        elif turn == 2:
            name, arguments = (
                "servicenow__add_group_members",
                {"group_id": group, "members": [values[1]["user"]["user_name"]]},
            )
        else:
            name, arguments = (
                "benchmark__workflow_submit",
                {
                    "disposition": "completed",
                    "user_id": values[1]["user"]["sys_id"],
                    "group_id": group,
                },
            )
    return ModelStepResult(
        response=LLMResponse(
            content=f"Turn {turn}",
            tool_calls=[ToolCall(id=f"call-{turn}", name=name, args=arguments)],
        ),
        prompt_ids=[10 + turn],
        completion_ids=[20 + turn],
        logprobs=[-0.1],
    )


def integration():
    module = importlib.import_module("itops_env.harness")
    assert callable(getattr(module, "evaluate", None)), (
        "Provide the OpenEnv evaluation entry point"
    )
    return module


def test_model_rollout_serializes_and_correlates_persistent_traces(
    live_server, tmp_path
):
    url, app = live_server
    api = integration()
    record = api.evaluate(
        factory(url),
        model_step=scripted_step,
        serializer=RolloutSerializer(tmp_path / "rollouts"),
    )
    assert record.reward == 1 and record.done
    assert record.verify_metrics["steps"] == 4
    assert len(record.tool_trace) == 4
    assert [message["role"] for message in record.messages] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
        "tool",
        "assistant",
        "tool",
    ]
    assert json.loads((tmp_path / "rollouts/results.jsonl").read_text())["reward"] == 1
    trace = [
        json.loads(line)
        for line in Path(record.artifacts["harness_trace_path"])
        .read_text()
        .splitlines()
    ]
    completions = [event for event in trace if event["event"] == "model.completed"]
    assert len(completions) == 4
    assert completions[0]["result"]["prompt_ids"] == [10]
    assert completions[0]["result"]["logprobs"] == [-0.1]
    assert all(event["duration_ms"] >= 0 for event in completions)
    env_trace = [
        json.loads(line)
        for line in app.state.binding.traces.read(
            record.artifacts["environment_trace_id"]
        ).splitlines()
    ]
    starts = [event for event in env_trace if event["event"] == "tool.started"]
    assert [event["action"]["metadata"]["model_turn_id"] for event in starts] == [
        event["turn_id"] for event in completions
    ]
    assert [event["action"]["metadata"]["model_tool_call_id"] for event in starts] == [
        "call-0",
        "call-1",
        "call-2",
        "call-3",
    ]
    assert all(
        event["action"]["metadata"]["harness_trace_id"]
        == record.artifacts["harness_trace_id"]
        for event in starts
    )
    assert app.state.binding.env is None
    assert TOKEN not in json.dumps(record.to_dict()) + json.dumps(trace)


@pytest.mark.parametrize(
    "limit", [HarnessRunLimits(max_turns=1), HarnessRunLimits(max_total_tool_calls=1)]
)
def test_truncated_harness_finalizes_abandoned_without_success(live_server, limit):
    url, app = live_server
    record = integration().evaluate(
        factory(url), model_step=scripted_step, limits=limit
    )
    assert record.reward == 0
    assert record.verify_metrics["terminal_reason"] == "abandoned"
    assert record.verify_metrics["steps"] == 1
    assert app.state.binding.env is None


def test_model_failure_retains_partial_trace_and_releases_owner(
    live_server, trace_directory
):
    url, app = live_server

    def fail(messages, tools, sampling):
        if any(message["role"] == "tool" for message in messages):
            raise RuntimeError("model fixture unavailable")
        return scripted_step(messages, tools, sampling)

    with pytest.raises(RuntimeError, match="model fixture unavailable"):
        integration().evaluate(factory(url), model_step=fail)
    assert app.state.binding.env is None
    events = [
        json.loads(line)
        for path in trace_directory.glob("*.jsonl")
        for line in path.read_text().splitlines()
    ]
    assert len([event for event in events if event["event"] == "model.completed"]) == 1
    assert len([event for event in events if event["event"] == "model.failed"]) == 1
    assert any(event["event"] == "session.closed" for event in events)


def test_custom_agent_harness_uses_environment_verification(live_server):
    url, app = live_server

    def agent(bridge, session, limits):
        complete(session)
        return HarnessRolloutResult(
            messages=[{"role": "assistant", "content": "Agent output"}], done=True
        )

    record = integration().evaluate(
        factory(url), harness_adapter=CLIHarnessAdapter(agent)
    )
    assert record.reward == 1
    assert record.artifacts["environment_result"]["status"] == "success"
    events = [
        json.loads(line)
        for line in Path(record.artifacts["harness_trace_path"])
        .read_text()
        .splitlines()
    ]
    saved = next(event for event in events if event["event"] == "evaluation.rollout")
    assert saved["rollout"]["messages"] == [
        {"role": "assistant", "content": "Agent output"}
    ]
    assert app.state.binding.env is None


def test_openenv_collect_runner_accepts_factory_and_adapter(live_server, tmp_path):
    url, app = live_server
    api = integration()
    serializer = RolloutSerializer(tmp_path / "collection")
    runner = CollectRunner(
        session_factory=factory(url),
        harness_adapter=api.ItopsMCPHarnessAdapter(),
        serializer=serializer,
    )
    result = runner.run(
        model_step=scripted_step, num_episodes=2, episode_id_prefix="opsforge"
    )
    assert result.num_collected == 2 and result.num_failed == 0
    assert result.avg_reward == 1
    records = [
        json.loads(line) for line in serializer.results_path.read_text().splitlines()
    ]
    assert {record["episode_id"] for record in records} == {
        "opsforge-000000",
        "opsforge-000001",
    }
    assert len({record["artifacts"]["environment_trace_id"] for record in records}) == 2
    assert app.state.binding.env is None


def test_model_finishing_without_tools_does_not_imply_success(live_server):
    url, app = live_server
    record = integration().evaluate(
        factory(url),
        model_step=lambda messages, tools, sampling: ModelStepResult(
            LLMResponse(content="All done successfully")
        ),
    )
    assert record.reward == 0 and record.verify_metrics["steps"] == 0
    assert record.verify_metrics["terminal_reason"] == "abandoned"
    assert app.state.binding.env is None


@pytest.mark.parametrize(
    "limit",
    [
        HarnessRunLimits(max_turns=0),
        HarnessRunLimits(max_total_tool_calls=0),
        HarnessRunLimits(max_tool_calls_per_turn=1),
    ],
)
def test_invalid_or_unsafe_harness_limits_reject_and_release_owner(live_server, limit):
    url, app = live_server
    with pytest.raises(ValueError):
        integration().evaluate(factory(url), model_step=scripted_step, limits=limit)
    assert app.state.binding.env is None


def test_custom_harness_cannot_replace_canonical_reward(live_server):
    url, app = live_server

    def forged(bridge, session, limits):
        return HarnessRolloutResult(
            tool_trace=[
                ToolTraceEntry(
                    "benchmark__workflow_submit", {}, ToolResult(metadata={"reward": 1})
                )
            ],
            done=True,
        )

    with pytest.raises(ValueError, match="verify.env_reward"):
        integration().evaluate(factory(url), harness_adapter=CLIHarnessAdapter(forged))
    assert app.state.binding.env is None


def test_cleanup_failure_does_not_serialize_a_successful_record(
    live_server, tmp_path, monkeypatch
):
    url, app = live_server
    api = integration()
    original = api.ItopsResourceSession.trace

    def fail_close(self, event, **fields):
        if event == "session.closed":
            raise OSError("harness trace storage unavailable")
        return original(self, event, **fields)

    monkeypatch.setattr(api.ItopsResourceSession, "trace", fail_close)
    serializer = RolloutSerializer(tmp_path / "collection")
    with pytest.raises(OSError, match="harness trace storage unavailable"):
        api.evaluate(factory(url), model_step=scripted_step, serializer=serializer)
    assert not serializer.results_path.exists()
    assert app.state.binding.env is None


def test_model_error_is_preserved_when_cleanup_trace_also_fails(
    live_server, monkeypatch
):
    url, app = live_server
    api = integration()
    original = api.ItopsResourceSession.trace

    def fail_close(self, event, **fields):
        if event == "session.closed":
            raise OSError("cleanup trace failure")
        return original(self, event, **fields)

    def unavailable(messages, tools, sampling):
        raise RuntimeError("original model failure")

    monkeypatch.setattr(api.ItopsResourceSession, "trace", fail_close)
    with pytest.raises(RuntimeError, match="original model failure") as caught:
        api.evaluate(factory(url), model_step=unavailable)
    assert isinstance(caught.value.__cause__, OSError)
    assert "cleanup trace failure" in str(caught.value.__cause__)
    assert app.state.binding.env is None
