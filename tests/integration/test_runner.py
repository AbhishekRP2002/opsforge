"""Replay and external attachment share the same controller lifecycle."""

import asyncio
import json

import httpx
from itops_env.runner import replay, run
from test_mcp_episode import TOKEN, native
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def test_replay_report(live_server, caplog, capfd):
    url, app = live_server
    report = asyncio.run(run("replay", url, TOKEN))
    assert report["result"]["status"] == "success"
    assert report["result"]["metrics"]["steps"] == 4
    assert len(report["trace"]) == 4
    assert report["trace"][2]["arguments"]["members"] == ["alex.chen"]
    assert TOKEN not in json.dumps(report)
    events = [
        json.loads(line)
        for line in app.state.binding.traces.read(report["trace_id"]).splitlines()
    ]
    assert len([event for event in events if event["event"] == "tool.completed"]) == 4
    assert events[-1]["result"]["status"] == "success"
    assert "Exception in ASGI application" not in capfd.readouterr().err
    assert not any(
        "Exception in ASGI application" in record.getMessage()
        for record in caplog.records
    )


def test_connect_attachment_timeout_and_cancel(live_server):
    url, app = live_server

    async def check():
        ready = asyncio.Event()
        configs = []

        def capture(value, **kwargs):
            configs.append(json.loads(value))
            ready.set()

        running = asyncio.create_task(run("connect", url, TOKEN, output=capture))
        await ready.wait()
        assert TOKEN not in json.dumps(configs)
        await replay(configs[0])
        report = await running
        assert report["result"]["status"] == "success"
        events = [
            json.loads(line)
            for line in app.state.binding.traces.read(report["trace_id"]).splitlines()
        ]
        assert (
            len([event for event in events if event["event"] == "tool.completed"]) == 4
        )
        abandoned = await run("connect", url, TOKEN, wall_time=0.05, output=capture)
        assert abandoned["result"]["terminal_reason"] == "abandoned"
        ready.clear()
        running = asyncio.create_task(run("connect", url, TOKEN, output=capture))
        await ready.wait()
        episode = app.state.binding.env.episode
        running.cancel()
        try:
            await running
        except asyncio.CancelledError:
            pass
        assert episode.result().terminal_reason == "abandoned"
        async with httpx.AsyncClient() as http:
            response = await http.get(
                url + "/control/session", headers={"Authorization": f"Bearer {TOKEN}"}
            )
            # Disconnect cleanup can finish on the server's next loop turn.
            if response.status_code == 200:
                await asyncio.sleep(0.05)
                response = await http.get(
                    url + "/control/session",
                    headers={"Authorization": f"Bearer {TOKEN}"},
                )
            assert response.status_code == 409

    asyncio.run(check())


def test_runner_cancellation_drains_attached_agent(live_server):
    url, app = live_server

    async def check():
        ready = asyncio.Event()
        configs = []

        def capture(value, **kwargs):
            configs.append(json.loads(value))
            ready.set()

        running = asyncio.create_task(run("connect", url, TOKEN, output=capture))
        await ready.wait()
        async with (
            native(configs[0], "okta"),
            native(configs[0], "servicenow"),
            native(configs[0], "benchmark"),
        ):
            old = [
                transport
                for manager in app.state.binding.native_managers
                for transport in manager._server_instances.values()
            ]
            assert len(old) == 3
            running.cancel()
            try:
                await running
            except asyncio.CancelledError:
                pass
            assert all(
                transport.is_terminated and not transport._request_streams
                for transport in old
            )
            assert all(
                not manager._server_instances and not manager._session_owners
                for manager in app.state.binding.native_managers
            )

    asyncio.run(check())
