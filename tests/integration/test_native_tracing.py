"""Controller-only trace export and MCP transport-to-episode correlation."""

import asyncio
import json

import httpx
from itops_env import ItopsEnv
from test_mcp_episode import TOKEN, configuration, native
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def test_native_trace_and_archived_controller_export(live_server):
    url, app = live_server

    async def check():
        async with httpx.AsyncClient(
            base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
        ) as control:
            async with ItopsEnv(base_url=url, controller_token=TOKEN) as owner:
                await owner.reset()
                config = await configuration(control)
                async with native(config, "okta") as (client, http, sid):
                    assert not (
                        await client.call_tool("get_user", {"user_id": "00u-target"})
                    ).isError
                    assert (await client.call_tool("get_user", {"user_id": 42})).isError
                    invalid = await http.post(
                        config["mcpServers"]["okta"]["url"],
                        headers={
                            "mcp-session-id": sid(),
                            "Accept": "application/json, text/event-stream",
                        },
                        json={
                            "jsonrpc": "2.0",
                            "id": 900,
                            "method": "tools/call",
                            "params": {"name": "get_user", "arguments": []},
                        },
                    )
                    assert invalid.json()["error"]["code"] == -32602
                    denied = await http.get(url + "/control/trace")
                    assert denied.status_code == 401
                assert (await owner.state()).step_count == 2
                result = (await control.get("/control/result")).json()
                trace_id = result["trace_id"]
                export = await control.get("/control/trace")
                assert export.status_code == 200
                assert export.headers["content-type"].startswith("application/x-ndjson")
                events = [json.loads(line) for line in export.text.splitlines()]
                calls = [event for event in events if event["event"] == "tool.started"]
                assert len(calls) == 2
                transport_id = result["transport_trace_id"]
                transport = (await control.get(f"/control/trace/{transport_id}")).text
                transport_events = [json.loads(line) for line in transport.splitlines()]
                request_ids = {
                    event["request_id"]
                    for event in transport_events
                    if event["event"] == "mcp.request_started"
                }
                assert all(
                    event["context"]["request_id"] in request_ids for event in calls
                )
                assert all(event["context"]["transport"] == "mcp" for event in calls)
                assert any(
                    (event.get("envelope") or {}).get("error", {}).get("code") == -32602
                    for event in transport_events
                )
                assert (
                    config["mcpServers"]["okta"]["headers"]["Authorization"]
                    not in transport + export.text
                )
                assert TOKEN not in transport + export.text
            archived = await control.get(f"/control/trace/{trace_id}")
            assert archived.status_code == 200
            assert "episode.closed" in archived.text
            assert (await control.get("/control/trace/invalid")).status_code == 404
            assert (await control.get("/control/trace/" + "0" * 32)).status_code == 404
        async with httpx.AsyncClient(base_url=url) as anonymous:
            assert (
                await anonymous.get(f"/control/trace/{trace_id}")
            ).status_code == 401
            assert (await anonymous.post("/mcp/okta/", json={})).status_code == 401
        requests = [
            json.loads(line)
            for line in app.state.binding.traces.read(transport_id).splitlines()
        ]
        assert any(
            event["event"] == "mcp.request_completed" and event["status"] == 401
            for event in requests
        )

    asyncio.run(check())


def test_decorated_defaults_preserve_wire_identity(live_server):
    url, _ = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset()
            config = await configuration(control)
            async with native(config, "servicenow") as (_, http, sid):
                wire = {
                    "jsonrpc": "2.0",
                    "id": 100,
                    "method": "tools/call",
                    "params": {
                        "name": "get_user",
                        "arguments": {"email": "alex.chen@example.test"},
                    },
                }
                headers = {
                    "mcp-session-id": sid(),
                    "Accept": "application/json, text/event-stream",
                }

                async def send():
                    response = await http.post(
                        config["mcpServers"]["servicenow"]["url"],
                        headers=headers,
                        json=wire,
                    )
                    response.raise_for_status()
                    return response.json()

                first = await send()
                assert first["result"]["isError"] is False
                assert await send() == first
                wire["params"]["arguments"]["user_id"] = None
                conflict = await send()
                assert conflict["result"]["isError"] is True
                assert "conflicts" in conflict["result"]["content"][0]["text"]
                assert (await owner.state()).step_count == 2
            async with native(config, "benchmark") as (client, _, _):
                for seconds in (1.0, True, -1):
                    assert (
                        await client.call_tool("workflow_wait", {"seconds": seconds})
                    ).isError
                assert not (
                    await client.call_tool("workflow_wait", {"seconds": 0})
                ).isError
                assert (
                    await client.call_tool(
                        "workflow_wait", {"seconds": 0, "extra": "value"}
                    )
                ).isError
                assert (await owner.state()).step_count == 7

    asyncio.run(check())
