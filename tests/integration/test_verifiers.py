"""Verifiers adapter contracts against the actual OpsForge server."""

import asyncio
import inspect
import json
import subprocess
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
import test_mcp_episode
from fastapi import Request
from itops_env import ItopsEnv
from itops_env.runner import replay

TOKEN = test_mcp_episode.TOKEN
live_server = test_mcp_episode.live_server


def test_episode_scores_canonical_and_releases_owner(live_server):
    from itops_env.integrations.verifiers.episode import episode_session

    url, _ = live_server

    async def check():
        async with episode_session(url, TOKEN) as session:
            await replay(session.config)
            result = await session.finalize()
            assert result["result"]["reward"] == 1.0
            assert result == await session.finalize()
            assert result["trace_id"]
            endpoint = session.config["mcpServers"]["okta"]
        async with httpx.AsyncClient() as http:
            response = await http.post(endpoint["url"], headers=endpoint["headers"])
            assert response.status_code == 401
        async with ItopsEnv(base_url=url, controller_token=TOKEN) as owner:
            assert not (await owner.reset()).done

    asyncio.run(check())


@pytest.mark.parametrize("mode", ["cancel", "timeout"])
def test_verifiers_interrupted_model_releases_episode(live_server, monkeypatch, mode):
    import verifiers.v1 as vf
    from itops_env.integrations.verifiers import OpsForgeEnv
    from itops_env.integrations.verifiers.adapter import OpsForgeEnvConfig

    url, app = live_server
    monkeypatch.setenv("OPSFORGE_CONTROLLER_TOKEN", TOKEN)
    entered, release = threading.Event(), threading.Event()

    @app.post("/stall/chat/completions")
    async def stall():
        entered.set()
        while not release.is_set():
            await asyncio.sleep(0.01)
        return {}

    async def check():
        config = OpsForgeEnvConfig(base_url=url)
        if mode == "timeout":
            config.agent.timeout.rollout = 0.5
        env = OpsForgeEnv(config)
        task = asyncio.create_task(
            env.run_episode(
                next(iter(env.taskset)),
                vf.ModelContext(
                    model="stall",
                    client=vf.EvalClientConfig(
                        base_url=f"{url}/stall", api_key_var="TEST_MODEL_KEY"
                    ),
                ),
            )
        )
        try:
            async with asyncio.timeout(10):
                while not entered.is_set():
                    await asyncio.sleep(0.01)
                backend_episode = app.state.binding.require()
                if mode == "cancel":
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                else:
                    episode = await task
                    assert not episode.ok
                    assert episode.traces[0].rewards.get("canonical") is None
            assert backend_episode.result().terminal_reason == "abandoned"
            async with ItopsEnv(base_url=url, controller_token=TOKEN) as owner:
                assert not (await owner.reset()).done
        finally:
            release.set()
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

    asyncio.run(check())


def test_native_reconnect_and_parallel_backends_are_isolated(live_server):
    from itops_env.integrations.verifiers.episode import episode_session, native_tools

    url, _ = live_server
    with contextmanager(inspect.unwrap(test_mcp_episode.live_server))() as (
        other_url,
        _,
    ):

        async def check():
            async with (
                episode_session(url, TOKEN) as first,
                episode_session(other_url, TOKEN) as second,
            ):
                assert first.config["episode_id"] != second.config["episode_id"]
                async with native_tools(first.config) as native:
                    assert not (
                        await native.call("okta__get_user", {"user_id": "00u-target"})
                    )["isError"]
                # New MCP sessions reconnect to the same controller-owned episode.
                async with native_tools(first.config) as native:
                    assert not (
                        await native.call(
                            "servicenow__get_user", {"email": "alex.chen@example.test"}
                        )
                    )["isError"]
                await asyncio.gather(replay(first.config), replay(second.config))
                results = await asyncio.gather(first.finalize(), second.finalize())
                assert [result["result"]["reward"] for result in results] == [1.0, 1.0]
                assert results[0]["trace_id"] != results[1]["trace_id"]
                assert (
                    results[0]["transport_trace_id"] != results[1]["transport_trace_id"]
                )

        asyncio.run(check())


@pytest.mark.parametrize(
    "override",
    [
        {"agent": {"retries": {"max_retries": 1}}},
        {"agent": {"harness": {"id": "null"}}},
        {"agent": {"runtime": {"type": "docker"}}},
        {
            "taskset": {
                "id": "opsforge_verifiers",
                "task": {"rewards": {"canonical": {"weight": 0}}},
            }
        },
        {
            "taskset": {
                "id": "opsforge_verifiers",
                "task": {"stops": {"episode_done": {}}},
            }
        },
    ],
)
def test_verifiers_rejects_contract_breaking_configuration(override):
    from itops_env.integrations.verifiers.adapter import OpsForgeEnvConfig

    with pytest.raises(ValueError):
        OpsForgeEnvConfig.model_validate(override)


def test_verifiers_failure_keeps_trace_link_and_drops_private_state(
    live_server, monkeypatch
):
    import verifiers.v1 as vf
    from itops_env.integrations.verifiers import OpsForgeEnv
    from itops_env.integrations.verifiers.adapter import (
        OpsForgeEnvConfig,
        OpsForgeState,
    )

    url, _ = live_server
    monkeypatch.setenv("OPSFORGE_CONTROLLER_TOKEN", TOKEN)

    async def check():
        env = OpsForgeEnv(OpsForgeEnvConfig(base_url=url))
        episode = await env.run_episode(
            next(iter(env.taskset)),
            vf.ModelContext(
                model="fail",
                client=vf.EvalClientConfig(
                    base_url=f"{url}/nonexistent", api_key_var="TEST_MODEL_KEY"
                ),
            ),
        )
        assert not episode.ok
        trace = episode.traces[0]
        assert trace.info["opsforge"]["trace_id"]
        assert trace.rewards.get("canonical") is None
        assert isinstance(trace.state, OpsForgeState)
        assert trace.state._session is None

    asyncio.run(check())


def test_verifiers_cli_writes_local_canonical_trace(live_server, monkeypatch, tmp_path):
    url, app = live_server
    monkeypatch.setenv("OPSFORGE_CONTROLLER_TOKEN", TOKEN)

    @app.post("/cli-model/chat/completions")
    async def model(request: Request):
        body = await request.json()
        return {
            "id": "cli-completion",
            "object": "chat.completion",
            "created": 1,
            "model": body["model"],
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "No action taken."},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    process = subprocess.run(
        [
            str(Path(sys.executable).with_name("eval")),
            "opsforge_verifiers",
            "--model",
            "local-scripted",
            "--client.base-url",
            f"{url}/cli-model",
            "--client.api-key-var",
            "TEST_MODEL_KEY",
            "--env.base-url",
            url,
            "--no-push",
            "--no-rich",
            "-c",
            "1",
            "-n",
            "1",
            "-r",
            "1",
            "--output-dir",
            str(tmp_path / "eval"),
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    traces = list((tmp_path / "eval").rglob("traces.jsonl"))
    assert len(traces) == 1
    record = json.loads(traces[0].read_text().strip())
    assert record["ok"] is True
    assert len(record["traces"]) == 1
    trace = record["traces"][0]
    assert trace["rewards"]["canonical"]["score"] == 0.0
    assert trace["info"]["opsforge"]["result"]["terminal_reason"] == "abandoned"
    assert TOKEN not in traces[0].read_text()


@pytest.mark.parametrize(
    "policy",
    [
        "success",
        "give_up",
        "turn_limit",
        "provider_error",
        "infrastructure_error",
        "invalid_json",
        "nonobject",
        "unknown",
        "terminal_batch",
    ],
)
def test_verifiers_rollout_uses_native_tools_and_canonical_score(
    live_server, monkeypatch, policy
):
    import verifiers.v1 as vf
    from itops_env.integrations.verifiers import OpsForgeEnv
    from itops_env.integrations.verifiers.adapter import OpsForgeEnvConfig

    url, app = live_server
    monkeypatch.setenv("OPSFORGE_CONTROLLER_TOKEN", TOKEN)
    requests = []
    if policy == "infrastructure_error":
        import sqlite3

        from itops_env.server.services import okta

        def fail(*args):
            raise sqlite3.OperationalError("private-grader-secret")

        monkeypatch.setattr(okta, "get_user", fail)

    @app.post("/model/chat/completions")
    async def model(request: Request):
        from fastapi.responses import JSONResponse

        body = await request.json()
        requests.append(body)
        if policy == "provider_error":
            return JSONResponse(
                {"error": {"message": "test provider unavailable"}}, status_code=500
            )
        step = len(requests) - 1
        calls = [
            ("okta__get_user", {"user_id": "alex.chen@example.test"}),
            ("servicenow__get_user", {"email": "alex.chen@example.test"}),
            (
                "servicenow__add_group_members",
                {"group_id": "a" * 32, "members": ["alex.chen"]},
            ),
            (
                "benchmark__workflow_submit",
                {"disposition": "completed", "user_id": "1" * 32, "group_id": "a" * 32},
            ),
        ]
        message = {"role": "assistant", "content": "I am done."}
        if policy != "give_up" and step < len(calls):
            name, args = calls[step]
            arguments = json.dumps(args)
            if step == 0:
                if policy == "invalid_json":
                    arguments = "{"
                elif policy == "nonobject":
                    arguments = "[]"
                elif policy == "unknown":
                    name = "control__snapshot"
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"call-{step}",
                        "type": "function",
                        "function": {"name": name, "arguments": arguments},
                    }
                ],
            }
            if policy == "terminal_batch" and step == 3:
                message["tool_calls"].append(
                    {
                        "id": "after-submit",
                        "type": "function",
                        "function": {
                            "name": "benchmark__workflow_wait",
                            "arguments": '{"seconds": 0}',
                        },
                    }
                )
        return {
            "id": f"completion-{step}",
            "object": "chat.completion",
            "created": 1,
            "model": body["model"],
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls"
                    if "tool_calls" in message
                    else "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
        }

    async def check():
        config = OpsForgeEnvConfig(base_url=url)
        if policy == "turn_limit":
            config.agent.max_turns = 1
        env = OpsForgeEnv(config)
        task = next(iter(env.taskset))
        episode = await env.run_episode(
            task,
            vf.ModelContext(
                model="test-policy",
                client=vf.EvalClientConfig(
                    base_url=f"{url}/model", api_key_var="TEST_MODEL_KEY"
                ),
            ),
        )
        assert episode.traces, episode.errors
        trace = episode.traces[0]
        assert episode.ok == (
            policy not in {"provider_error", "infrastructure_error"}
        ), (
            episode.errors,
            trace.errors,
        )
        if policy in {"provider_error", "infrastructure_error"}:
            assert trace.rewards.get("canonical") is None
        else:
            assert trace.reward == (
                1.0 if policy in {"success", "terminal_batch"} else 0.0
            )
            assert trace.info["opsforge"]["result"]["reward"] == trace.reward
            assert trace.info["opsforge"]["transport_trace_id"]
        wire = episode.model_dump_json()
        assert TOKEN not in wire
        assert "Bearer " not in wire
        assert "mcpServers" not in wire
        assert "private-grader-secret" not in wire
        assert TOKEN not in json.dumps(requests)
        assert "workflow_submit" in json.dumps(requests[0]["tools"])
        if policy == "success":
            assert len(requests) == 4  # Stop before a fifth paid model request.
            assert [message.role for message in trace.messages].count("tool") == 4
        if policy == "terminal_batch":
            assert trace.info["opsforge"]["result"]["metrics"]["steps"] == 4
            assert len(trace.tool_messages) == 5
            content = trace.tool_messages[-1].content
            assert isinstance(content, str)
            assert json.loads(content)["isError"] is True
        if policy in {"invalid_json", "nonobject", "unknown"}:
            content = trace.tool_messages[0].content
            assert isinstance(content, str)
            assert json.loads(content)["isError"] is True
            assert trace.info["opsforge"]["result"]["metrics"]["steps"] == 3
        async with ItopsEnv(base_url=url, controller_token=TOKEN) as owner:
            assert not (await owner.reset()).done

    asyncio.run(check())


@pytest.mark.parametrize("cancel", [False, True])
def test_episode_finalizes_on_error_or_cancellation(live_server, cancel):
    from itops_env.integrations.verifiers.episode import episode_session

    url, _ = live_server

    async def check():
        session = None
        error = asyncio.CancelledError if cancel else RuntimeError
        with pytest.raises(error):
            async with episode_session(url, TOKEN) as session:
                raise error("test interruption")
        assert session is not None and session.result is not None
        assert session.result["result"]["reward"] == 0.0
        assert session.result["result"]["terminal_reason"] == "abandoned"
        async with ItopsEnv(base_url=url, controller_token=TOKEN) as owner:
            assert not (await owner.reset()).done

    asyncio.run(check())


def test_native_aliases_and_errors_preserve_mcp_semantics(live_server):
    from itops_env.integrations.verifiers.episode import episode_session, native_tools

    url, _ = live_server

    async def check():
        async with (
            episode_session(url, TOKEN) as session,
            native_tools(session.config) as native,
        ):
            names = {tool["function"]["name"] for tool in native.tools}
            assert {"okta__get_user", "servicenow__get_user"} <= names
            result = await native.call("okta__get_user", {"user_id": 12})
            assert result["isError"] is True
            assert result["content"]
            assert "structuredContent" in result
            assert TOKEN not in json.dumps(native.tools)
            with pytest.raises(ValueError, match="Unknown tool"):
                await native.call("control__snapshot", {})

    asyncio.run(check())
