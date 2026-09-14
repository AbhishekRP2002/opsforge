import asyncio

import httpx
import pytest
from itops_env.server.app import create_opsforge_app
from itops_env.server.itops_environment import ItopsEnvironment
from itops_env.server.mcp_servers import tools


@pytest.fixture(autouse=True)
def clear_tool_definition_cache():
    tools.tool_definitions.cache_clear()
    yield
    tools.tool_definitions.cache_clear()


def test_registry_rejects_orphan_handler_provider(monkeypatch):
    monkeypatch.setitem(tools.HANDLER_RESOLVERS, "orphan", dict)
    with pytest.raises(ValueError, match="provider keys"):
        tools.validate_registry()


def test_registry_rejects_missing_business_handler(monkeypatch):
    monkeypatch.setitem(tools.HANDLER_RESOLVERS, "okta", dict)
    tools.tool_definitions.cache_clear()
    with pytest.raises(ValueError, match="handler mismatch"):
        tools.validate_registry()
    tools.tool_definitions.cache_clear()


def test_registry_rejects_noncallable_business_handler(monkeypatch):
    monkeypatch.setitem(tools.HANDLER_RESOLVERS, "okta", lambda: {"get_user": None})
    tools.tool_definitions.cache_clear()
    with pytest.raises(ValueError, match="non-callable handler"):
        tools.validate_registry()
    tools.tool_definitions.cache_clear()


def test_registry_rejects_duplicate_decorated_tool_names(monkeypatch):
    async def duplicate(value: str):
        return None

    async def duplicate_again(value: str):
        return None

    duplicate_again.__name__ = "duplicate"

    def register_tools(mcp, dispatch):
        return (duplicate, duplicate_again)

    monkeypatch.setitem(tools.REGISTRARS, "duplicate_provider", register_tools)
    monkeypatch.setitem(
        tools.HANDLER_RESOLVERS,
        "duplicate_provider",
        lambda: {"duplicate": lambda db, arguments, step, clock: ({}, False)},
    )
    tools.tool_definitions.cache_clear()
    with pytest.raises(ValueError, match="duplicate tool"):
        tools.validate_registry()
    tools.tool_definitions.cache_clear()


def test_only_registered_business_tools_resolve_to_handlers():
    assert callable(tools.tool_handler("okta", "get_user"))
    for provider, name in (("unknown", "get_user"), ("benchmark", "workflow_wait")):
        with pytest.raises(KeyError):
            tools.tool_handler(provider, name)


def test_native_routes_and_control_config_follow_registry(monkeypatch):
    def register_tools(mcp, dispatch):
        @mcp.tool
        async def inspect_target(target: str):
            return await dispatch("inspect_target", {"target": target})

        return (inspect_target,)

    def inspect_handler(db, arguments, step, clock):
        return {"target": arguments["target"]}, False

    monkeypatch.setitem(tools.REGISTRARS, "test_provider", register_tools)
    monkeypatch.setitem(
        tools.HANDLER_RESOLVERS,
        "test_provider",
        lambda: {"inspect_target": inspect_handler},
    )
    tools.tool_definitions.cache_clear()
    app = create_opsforge_app("test-token")
    env = ItopsEnvironment(binding=app.state.binding)

    async def check():
        async with app.router.lifespan_context(app):
            env.reset()
            try:
                assert "/mcp/test_provider" in {
                    path
                    for route in app.router.routes
                    if (path := getattr(route, "path", None)) is not None
                }
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    response = await client.get(
                        "/control/session",
                        headers={"Authorization": "Bearer test-token"},
                    )
                    config = response.json()["mcpServers"]["test_provider"]
                    initialized = await client.post(
                        "/mcp/test_provider/",
                        headers=config["headers"]
                        | {"Accept": "application/json, text/event-stream"},
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-06-18",
                                "capabilities": {},
                                "clientInfo": {"name": "test", "version": "1"},
                            },
                        },
                    )
                    native_headers = config["headers"] | {
                        "Accept": "application/json, text/event-stream",
                        "mcp-session-id": initialized.headers["mcp-session-id"],
                        "mcp-protocol-version": initialized.json()["result"][
                            "protocolVersion"
                        ],
                    }
                    await client.post(
                        "/mcp/test_provider/",
                        headers=native_headers,
                        json={
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                        },
                    )
                    called = await client.post(
                        "/mcp/test_provider/",
                        headers=native_headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/call",
                            "params": {
                                "name": "inspect_target",
                                "arguments": {"target": "alpha"},
                            },
                        },
                    )
                assert response.json()["mcpServers"]["test_provider"]["url"].endswith(
                    "/mcp/test_provider/"
                )
                assert (
                    called.json()["result"]["content"][0]["text"]
                    == '{"target": "alpha"}'
                )
            finally:
                env.close()

    asyncio.run(check())
