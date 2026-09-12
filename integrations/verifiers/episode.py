"""Private controller lifetime and authenticated, persistent native MCP clients."""

from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ...client import ItopsEnv


@dataclass
class EpisodeSession:
    control: httpx.AsyncClient = field(repr=False)
    config: dict = field(default_factory=dict, repr=False)
    result: dict | None = None

    async def terminal(self) -> bool:
        response = await self.control.get("/control/result")
        response.raise_for_status()
        return response.json()["result"] is not None

    async def finalize(self) -> dict:
        if self.result is None:
            response = await self.control.post("/control/finalize")
            response.raise_for_status()
            self.result = response.json()
        assert self.result is not None
        if self.result["result"]["status"] == "infrastructure_error":
            raise RuntimeError(
                "OpsForge infrastructure failure; episode is not scoreable"
            )
        return self.result


@asynccontextmanager
async def episode_session(base_url: str, controller_token: str):
    """Finalize even failed/cancelled attempts, then close the controller owner."""
    async with (
        ItopsEnv(base_url=base_url, controller_token=controller_token) as owner,
        httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {controller_token}"},
            timeout=30,
        ) as control,
    ):
        await owner.reset()
        session = EpisodeSession(control)
        try:
            response = await control.get("/control/session")
            response.raise_for_status()
            session.config = response.json()
            yield session
        finally:
            await session.finalize()


@dataclass
class NativeTools:
    tools: list[dict[str, Any]]
    routes: dict[str, tuple[ClientSession, str]] = field(repr=False)

    async def call(self, alias: str, arguments: dict) -> dict:
        if alias not in self.routes:
            raise ValueError(f"Unknown tool: {alias}")
        client, name = self.routes[alias]
        # Never retry a write with a new MCP request identity.
        result = await client.call_tool(name, arguments)
        return result.model_dump(mode="json")


@asynccontextmanager
async def native_tools(config: dict):
    """Discover public schemas; preserve error flags and structured MCP results."""
    async with AsyncExitStack() as stack:
        tools = []
        routes = {}
        for provider, endpoint in config["mcpServers"].items():
            http = await stack.enter_async_context(
                httpx.AsyncClient(headers=endpoint["headers"], timeout=30)
            )
            read, write, _ = await stack.enter_async_context(
                streamable_http_client(endpoint["url"], http_client=http)
            )
            client = await stack.enter_async_context(ClientSession(read, write))
            await client.initialize()
            cursor = None
            while True:
                page = await client.list_tools(cursor=cursor)
                for tool in page.tools:
                    alias = f"{provider}__{tool.name}"
                    if alias in routes:
                        raise ValueError(f"Duplicate tool alias: {alias}")
                    routes[alias] = client, tool.name
                    tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": alias,
                                "description": tool.description or "",
                                "parameters": tool.inputSchema,
                            },
                        }
                    )
                cursor = page.nextCursor
                if cursor is None:
                    break
        yield NativeTools(tools, routes)
