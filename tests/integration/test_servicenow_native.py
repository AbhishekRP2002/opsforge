"""Real authenticated MCP discovery and shared Episode accounting."""

import asyncio
import json

import httpx
from itops_env import ItopsEnv
from mcp.types import TextContent
from test_mcp_episode import TOKEN, configuration, native
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def test_native_servicenow_schema_defaults_and_exact_accounting(live_server):
    url, _ = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset(episode_id="native-servicenow")
            config = await configuration(control)
            async with native(config, "servicenow") as (client, _, _):
                catalog = {
                    tool.name: tool for tool in (await client.list_tools()).tools
                }
                assert len(catalog) == 82
                assert catalog["create_incident"].inputSchema["required"] == [
                    "short_description"
                ]
                assert (
                    catalog["create_workflow"].inputSchema["properties"]["active"][
                        "default"
                    ]
                    is True
                )
                assert (await owner.state()).step_count == 0
                assert (await owner.state()).simulated_clock == 0

                async def call(name, arguments):
                    result = await client.call_tool(name, arguments)
                    assert not result.isError
                    assert isinstance(result.content[0], TextContent)
                    assert result.content[0].text.startswith("{\n")
                    return json.loads(result.content[0].text)

                rejected = await client.call_tool(
                    "create_incident",
                    {"short_description": "Native", "extra": "ignored"},
                )
                assert rejected.isError
                assert (await owner.state()).step_count == 1
                assert (await owner.state()).simulated_clock == 1
                assert (await call("list_incidents", {}))["incidents"] == []
                incident = await call(
                    "create_incident", {"short_description": "Native"}
                )
                listed = await call("list_incidents", {})
                assert listed["incidents"][0]["sys_id"] == incident["incident_id"]
                invalid = await client.call_tool(
                    "create_incident", {"short_description": 7}
                )
                assert invalid.isError
                workflow = await call(
                    "create_workflow",
                    {"name": "Native workflow", "attributes": {"nested": [1]}},
                )
                assert workflow["workflow"]["nested"] == [1]
                assert (
                    await call(
                        "get_workflow_details",
                        {"workflow_id": workflow["workflow"]["sys_id"]},
                    )
                )["workflow"]["name"] == "Native workflow"
                assert (await owner.state()).step_count == 7
                assert (await owner.state()).simulated_clock == 7

    asyncio.run(check())
