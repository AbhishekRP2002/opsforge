"""Public extended Okta calls use the native MCP episode dispatch boundary."""

import asyncio
import json

import httpx
from itops_env import ItopsEnv
from mcp.types import TextContent
from test_mcp_episode import TOKEN, configuration, native
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def test_native_extended_families_share_one_metered_episode(live_server):
    url, _ = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset(episode_id="native-okta-extended")
            config = await configuration(control)
            async with native(config, "okta") as (client, _, _):
                assert len((await client.list_tools()).tools) == 112
                assert (await owner.state()).step_count == 0

                async def call(name, arguments):
                    result = await client.call_tool(name, arguments)
                    assert not result.isError, result
                    assert isinstance(result.content[0], TextContent)
                    return json.loads(result.content[0].text)

                app = await call(
                    "create_application",
                    {"app_config": {"label": "Native", "signOnMode": "BOOKMARK"}},
                )
                assert (await call("get_application", {"app_id": app["id"]}))[
                    "label"
                ] == "Native"
                policy = await call(
                    "create_policy",
                    {"policy_data": {"name": "Native", "type": "ACCESS_POLICY"}},
                )
                assert (
                    await call(
                        "create_policy_rule",
                        {
                            "policy_id": policy["id"],
                            "rule_data": {
                                "name": "Native rule",
                                "type": "ACCESS_POLICY",
                            },
                        },
                    )
                )["name"] == "Native rule"
                brand = await call("create_brand", {"name": "Native"})
                assert (await call("list_brand_themes", {"brand_id": brand["id"]}))[
                    "total_fetched"
                ] == 1
                assert (
                    await call(
                        "replace_preview_error_page",
                        {
                            "brand_id": brand["id"],
                            "page_content": "<h1>Native preview</h1>",
                        },
                    )
                )["pageContent"] == "<h1>Native preview</h1>"
                assert (
                    await call("get_preview_error_page", {"brand_id": brand["id"]})
                )["pageContent"] == "<h1>Native preview</h1>"
                assert (
                    await call(
                        "create_email_customization",
                        {
                            "brand_id": brand["id"],
                            "template_name": "UserActivation",
                            "language": "en",
                            "subject": "Native",
                            "body": "Open ${activationLink}",
                        },
                    )
                )["subject"] == "Native"
                assert (
                    await call(
                        "send_test_email",
                        {"brand_id": brand["id"], "template_name": "UserActivation"},
                    )
                )["success"] is True
                device = await call(
                    "create_device_assurance_policy",
                    {"policy_data": {"name": "Native", "platform": "MACOS"}},
                )
                assert (
                    await call(
                        "get_device_assurance_policy",
                        {"device_assurance_id": device["id"]},
                    )
                )["name"] == "Native"
                assert (
                    await call("get_logs", {"filter": 'outcome.result eq "UNKNOWN"'})
                )["total_fetched"] == 13
                assert (await owner.state()).step_count == 13
                assert (await owner.state()).simulated_clock == 13

    asyncio.run(check())
