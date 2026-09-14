"""Official SDK attachment content, capability ownership and bounded wire input."""

import asyncio
import base64
import json

import httpx
from itops_env import ItopsAction, ItopsEnv
from itops_env.server.itops_environment import ItopsEnvironment
from mcp.types import BlobResourceContents, EmbeddedResource, TextContent
from test_mcp_episode import TOKEN, configuration, native
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def test_native_erpnext_attachment_bytes_and_exact_shared_accounting(live_server):
    url, _ = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset(episode_id="erpnext-native")
            config = await configuration(control)
            async with native(config, "erpnext") as (client, http, session_id):
                catalog = (await client.list_tools()).tools
                assert len(catalog) == 127
                assert (await owner.state()).step_count == 0
                created = await client.call_tool(
                    "erpnext_doc_create",
                    {"doctype": "Customer", "data": {"customer_name": "Native"}},
                )
                assert not created.isError and isinstance(
                    created.content[0], TextContent
                )
                parent = json.loads(created.content[0].text)["data"]["name"]
                arguments = {
                    "file_name": "résumé report.txt",
                    "content_base64": base64.b64encode(b"asset evidence").decode(),
                    "attached_to_doctype": "Customer",
                    "attached_to_name": parent,
                }
                uploaded = await client.call_tool("erpnext_file_upload", arguments)
                assert not uploaded.isError and isinstance(
                    uploaded.content[0], TextContent
                )
                metadata = json.loads(uploaded.content[0].text)["data"]
                download_args = {
                    "file_id": metadata["name"],
                    "attached_to_doctype": "Customer",
                    "attached_to_name": parent,
                }
                downloaded = await client.call_tool(
                    "erpnext_file_download", download_args
                )
                assert not downloaded.isError and len(downloaded.content) == 2
                resource = downloaded.content[1]
                assert isinstance(resource, EmbeddedResource) and isinstance(
                    resource.resource, BlobResourceContents
                )
                assert base64.b64decode(resource.resource.blob) == b"asset evidence"
                assert (await owner.state()).step_count == 3
                assert (await owner.state()).simulated_clock == 3
                artifact = await control.get(
                    "/control/artifacts/" + metadata["artifact_path"]
                )
                assert (
                    artifact.status_code == 200
                    and artifact.content == b"asset evidence"
                )
                async with httpx.AsyncClient(base_url=url) as outsider:
                    assert (
                        await outsider.get(
                            "/control/artifacts/" + metadata["artifact_path"]
                        )
                    ).status_code == 401
                large = await client.call_tool(
                    "erpnext_file_upload",
                    arguments
                    | {"content_base64": base64.b64encode(b"x" * 524288).decode()},
                )
                assert not large.isError
                assert (await owner.state()).step_count == 4
                endpoint = config["mcpServers"]["erpnext"]
                native_session_id = session_id()
                assert native_session_id is not None
                oversized = await http.post(
                    endpoint["url"],
                    headers={
                        "mcp-session-id": native_session_id,
                        "Accept": "application/json, text/event-stream",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 999,
                        "method": "tools/call",
                        "params": {
                            "name": "erpnext_file_upload",
                            "arguments": arguments | {"content_base64": "x" * 1048576},
                        },
                    },
                )
                assert oversized.status_code == 413
                assert (await owner.state()).step_count == 4
                assert (await owner.state()).simulated_clock == 4
            await owner.reset(episode_id="erpnext-reset")
            assert (
                await control.get("/control/artifacts/" + metadata["artifact_path"])
            ).status_code == 404

        direct = ItopsEnvironment()
        direct.reset()
        try:
            direct.step(
                ItopsAction(
                    provider="erpnext",
                    tool_name="erpnext_doc_create",
                    arguments={
                        "doctype": "Customer",
                        "data": {"customer_name": "Native"},
                    },
                )
            )
            direct.step(
                ItopsAction(
                    provider="erpnext",
                    tool_name="erpnext_file_upload",
                    arguments=arguments,
                )
            )
            result = direct.step(
                ItopsAction(
                    provider="erpnext",
                    tool_name="erpnext_file_download",
                    arguments=download_args,
                )
            )
            assert result.content == [
                block.model_dump(mode="json", exclude_none=True, by_alias=True)
                for block in downloaded.content
            ]
            assert direct.state.step_count == 3 and direct.state.simulated_clock == 3
        finally:
            direct.close()

    asyncio.run(check())


def test_native_all_sdk_content_block_types(live_server, monkeypatch):
    from itops_env.server.mcp_servers import tools
    from itops_env.server.services.results import ServiceContent

    blocks = [
        {"type": "text", "text": "typed"},
        {"type": "image", "data": "YWJj", "mimeType": "image/png"},
        {"type": "audio", "data": "YWJj", "mimeType": "audio/wav"},
        {"type": "resource_link", "uri": "attachment://one", "name": "one"},
        {
            "type": "resource",
            "resource": {
                "uri": "attachment://one",
                "blob": "YWJj",
                "mimeType": "application/octet-stream",
            },
        },
    ]
    original = tools.HANDLER_RESOLVERS["erpnext"]
    monkeypatch.setitem(
        tools.HANDLER_RESOLVERS,
        "erpnext",
        lambda: (
            dict(original())
            | {
                "erpnext_kpi_orders": lambda db, args, step, clock: (
                    ServiceContent.model_validate({"content": blocks}),
                    False,
                )
            }
        ),
    )
    url, _ = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset(episode_id="typed-content")
            async with native(await configuration(control), "erpnext") as (
                client,
                _,
                _,
            ):
                result = await client.call_tool("erpnext_kpi_orders", {})
                assert not result.isError
                assert [
                    block.model_dump(mode="json", exclude_none=True, by_alias=True)
                    for block in result.content
                ] == blocks
                assert (await owner.state()).step_count == 1 and (
                    await owner.state()
                ).simulated_clock == 1

    asyncio.run(check())
