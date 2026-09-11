"""Trace attempts independently of business transactions and episode cleanup."""

import json
import sqlite3

import pytest
from itops_env.models import ItopsAction
from itops_env.server.core.scenarios import load_scenario
from itops_env.server.interfaces.control import EpisodeBinding
from itops_env.server.itops_environment import ItopsEnvironment


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_trace_retains_replays_conflicts_rejections_and_lifecycle(trace_directory):
    env = ItopsEnvironment()
    env.reset(episode_id="same")
    trace_id = env.episode.trace_id
    action = ItopsAction(
        provider="okta",
        tool_name="get_user",
        arguments={"user_id": "00u-target"},
        invocation_id="one",
    )
    env.step(action)
    env.step(action)
    env.step(action.model_copy(update={"arguments": {"user_id": "missing"}}))
    env.step(
        ItopsAction(
            provider="okta", tool_name="unknown", arguments={"password": "secret"}
        )
    )
    env.episode.finalize()
    env.step(action.model_copy(update={"invocation_id": "after-terminal"}))
    env.close()
    path = trace_directory / f"{trace_id}.jsonl"
    events = records(path)
    attempts = [event for event in events if event["event"] == "tool.started"]
    completed = [event for event in events if event["event"] == "tool.completed"]
    assert len(attempts) == len(completed) == 5
    assert [event["outcome"] for event in completed] == [
        "executed",
        "replayed",
        "conflict",
        "rejected",
        "terminal_rejected",
    ]
    assert len({event["attempt_id"] for event in attempts}) == 5
    assert [event["state"]["step_count"] for event in completed] == [1, 1, 2, 3, 3]
    assert completed[0]["observation"]["content"]
    assert all(event["duration_ms"] >= 0 for event in completed)
    assert events[-1]["event"] == "episode.closed"
    assert any(event["event"] == "episode.finalized" for event in events)
    assert "secret" not in path.read_text()
    assert attempts[3]["action"]["arguments"]["password"] == "[REDACTED]"
    assert path.stat().st_mode & 0o777 == 0o600
    env.reset(episode_id="same")
    assert env.episode.trace_id != trace_id
    env.close()
    assert records(path) == events


def test_sqlite_rollback_does_not_erase_error_trace(trace_directory):
    env = ItopsEnvironment()
    env.reset()
    path = trace_directory / f"{env.episode.trace_id}.jsonl"
    env.episode.db.connection.execute(
        "CREATE TRIGGER fail_insert BEFORE INSERT ON servicenow_memberships BEGIN SELECT RAISE(ABORT, 'trace rollback test'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="trace rollback test"):
        env.step(
            ItopsAction(
                provider="servicenow",
                tool_name="add_group_members",
                arguments={
                    "group_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "members": ["alex.chen"],
                },
            )
        )
    assert env.state.step_count == 0
    assert env.episode.result().status == "infrastructure_error"
    env.close()
    failure = next(event for event in records(path) if event["event"] == "tool.failed")
    assert failure["error"]["type"] == "IntegrityError"
    assert failure["state"]["step_count"] == 0
    assert failure["result"]["status"] == "infrastructure_error"


def test_trace_write_failure_prevents_action(trace_directory):
    env = ItopsEnvironment()
    env.reset()
    path = trace_directory / f"{env.episode.trace_id}.jsonl"
    saved = path.read_bytes()
    path.unlink()
    path.mkdir()
    try:
        with pytest.raises(IsADirectoryError):
            env.step(
                ItopsAction(
                    provider="okta",
                    tool_name="get_user",
                    arguments={"user_id": "00u-target"},
                )
            )
        assert env.state.step_count == 0
    finally:
        path.rmdir()
        path.write_bytes(saved)
        env.close()


def test_trace_records_committed_partial_effects_and_horizon_events(trace_directory):
    scenario = load_scenario().model_dump()
    scenario["events"] = [
        {
            "at": 5,
            "sequence": 1,
            "kind": "group_unavailable",
            "group_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        }
    ]
    from itops_env.server.core.scenarios import Scenario

    env = ItopsEnvironment(Scenario.model_validate(scenario))
    env.reset()
    path = trace_directory / f"{env.episode.trace_id}.jsonl"
    result = env.step(
        ItopsAction(
            provider="servicenow",
            tool_name="add_group_members",
            arguments={
                "group_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "members": ["alex.chen", "missing"],
            },
        )
    )
    assert json.loads(result.content[0]["text"])["success"] is False
    env.step(
        ItopsAction(
            provider="benchmark", tool_name="workflow_wait", arguments={"seconds": 100}
        )
    )
    env.close()
    completed = [event for event in records(path) if event["event"] == "tool.completed"]
    assert completed[0]["outcome"] == "executed"
    effects = [
        row
        for row in completed[0]["committed"]["journal"]
        if row["kind"] == "membership_added"
    ]
    assert len(effects) == 1
    assert completed[1]["outcome"] == "horizon"
    assert completed[1]["committed"]["events"][0]["kind"] == "group_unavailable"
    assert any(
        event["event"] == "episode.finalized"
        and event["result"]["terminal_reason"] == "horizon"
        for event in records(path)
    )


def test_trace_failure_during_close_still_disposes_and_revokes(trace_directory):
    binding = EpisodeBinding()
    env = ItopsEnvironment(binding=binding)
    env.reset()
    episode = env.episode
    directory = episode.db.directory
    path = trace_directory / f"{episode.trace_id}.jsonl"
    path.unlink()
    path.mkdir()
    with pytest.raises(IsADirectoryError) as error:
        env.close()
    assert not directory.exists()
    assert env.state.phase == "closed"
    assert binding.env is None and binding.capability is None
    assert any("cleanup failed" in note for note in error.value.__notes__)


def test_invalid_reset_is_traced_without_replacing_episode(trace_directory):
    env = ItopsEnvironment()
    env.reset()
    original = env.episode
    try:
        with pytest.raises(ValueError, match="seed"):
            env.reset(seed=-1)
        assert env.episode is original
        events = records(trace_directory / f"{env.traces.transport_id}.jsonl")
        assert events[-1]["event"] == "environment.reset_failed"
        assert events[-1]["error"]["type"] == "ValueError"
        assert events[-1]["episode_trace_id"] == original.trace_id
    finally:
        env.close()
