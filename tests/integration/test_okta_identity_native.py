"""New Okta identity calls through an initialized official MCP SDK session."""

import asyncio
import json

import httpx
from itops_env import ItopsEnv
from mcp.types import TextContent
from test_mcp_episode import TOKEN, configuration, native
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def test_native_sdk_discovers_and_mutates_new_okta_identity_tool(live_server):
    url, _ = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset(episode_id="native-okta-identity")
            config = await configuration(control)
            async with native(config, "okta") as (client, _, _):
                names = {tool.name for tool in (await client.list_tools()).tools}
                assert {"create_group", "get_group", "list_group_apps"} <= names
                created = await client.call_tool(
                    "create_group", {"profile": {"name": "Native SDK"}}
                )
                assert not created.isError
                assert isinstance(created.content[0], TextContent)
                payload = json.loads(created.content[0].text)
                assert payload == [
                    {
                        "id": "00g-sim-000001",
                        "profile": {"name": "Native SDK"},
                    }
                ]
                fetched = await client.call_tool(
                    "get_group", {"group_id": "00g-sim-000001"}
                )
                assert not fetched.isError
                assert isinstance(fetched.content[0], TextContent)
                assert json.loads(fetched.content[0].text) == payload
                state = await owner.state()
                assert state.step_count == 2
                assert state.simulated_clock == 2

    asyncio.run(check())
