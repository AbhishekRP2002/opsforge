"""Official MCP client coverage for the complete Jira endpoint."""

import asyncio
import base64
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from itops_env import ItopsEnv
from itops_env.server.app import create_opsforge_app
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.mcp_servers.tools import tool_definitions
from mcp.types import BlobResourceContents, EmbeddedResource, ImageContent, TextContent
from test_mcp_episode import TOKEN, configuration, native


def jira_scenario():
    return Scenario.model_validate(
        load_scenario().model_dump()
        | {
            "jira_projects": [
                {
                    "id": "10",
                    "key": "OPS",
                    "name": "Operations",
                    "issue_types": [{"id": "1", "name": "Task"}],
                    "statuses": [{"id": "1", "name": "Open"}],
                    "components": [],
                    "field_names": {},
                }
            ],
            "jira_users": [
                {
                    "id": "u1",
                    "name": "ada",
                    "display_name": "Ada",
                    "email": "ada@example.test",
                    "active": True,
                    "project_keys": ["OPS"],
                }
            ],
            "jira_current_user": "u1",
            "jira_issues": [
                {
                    "id": 1,
                    "key": "OPS-1",
                    "data": {
                        "project_key": "OPS",
                        "summary": "Native",
                        "issue_type": "Task",
                        "status": "Open",
                        "assignee": "u1",
                        "created": "2026-01-01T00:00:00+00:00",
                        "updated": "2026-01-01T00:00:00+00:00",
                    },
                }
            ],
            "initial_artifacts": [
                {
                    "path": "artifacts/jira/native.png",
                    "content": "native-image",
                    "media_type": "image/png",
                }
            ],
            "jira_attachments": [
                {
                    "issue_id": 1,
                    "path": "artifacts/jira/native.png",
                    "filename": "native.png",
                    "media_type": "image/png",
                }
            ],
        }
    )


@pytest.fixture
def jira_live_server():
    app = create_opsforge_app(TOKEN, jira_scenario())
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="error", ws="websockets-sansio")
        )
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listener]}, daemon=True
        )
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            assert thread.is_alive() and time.monotonic() < deadline
            time.sleep(0.01)
        try:
            yield url
        finally:
            server.should_exit = True
            thread.join(10)
            assert not thread.is_alive()


def test_native_jira_discovery_calls_content_and_accounting(jira_live_server):
    async def check():
        async with (
            ItopsEnv(base_url=jira_live_server, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=jira_live_server, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset(episode_id="jira-native")
            async with native(await configuration(control), "jira") as (client, _, _):
                discovered = (await client.list_tools()).tools
                assert len(discovered) == 63
                assert {tool.name: tool.inputSchema for tool in discovered} == {
                    name: tool.parameters
                    for name, tool in tool_definitions("jira").items()
                }
                assert (await owner.state()).step_count == 0
                issue = await client.call_tool("jira_get_issue", {"issue_key": "OPS-1"})
                assert not issue.isError and isinstance(issue.content[0], TextContent)
                assert json.loads(issue.content[0].text)["summary"] == "Native"
                images = await client.call_tool(
                    "jira_get_issue_images", {"issue_key": "OPS-1"}
                )
                assert not images.isError and isinstance(
                    images.content[1], ImageContent
                )
                assert base64.b64decode(images.content[1].data) == b"native-image"
                downloads = await client.call_tool(
                    "jira_download_attachments", {"issue_key": "OPS-1"}
                )
                assert not downloads.isError and isinstance(
                    downloads.content[1], EmbeddedResource
                )
                assert isinstance(downloads.content[1].resource, BlobResourceContents)
                assert (
                    base64.b64decode(downloads.content[1].resource.blob)
                    == b"native-image"
                )
                invalid = await client.call_tool(
                    "jira_get_issue", {"issue_key": "BAD-1"}
                )
                assert invalid.isError
                state = await owner.state()
                assert state.step_count == state.simulated_clock == 4

    asyncio.run(check())
