"""Own an OpenEnv episode while official MCP clients or an external agent act."""

import argparse
import asyncio
import json
import os
import re
import sys
from contextlib import AsyncExitStack

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import TextContent

from .client import ItopsEnv


async def replay(config: dict) -> list[dict]:
    """Deterministic test policy for the public identity-group-v1 instruction."""
    trace = []
    async with AsyncExitStack() as stack:
        clients = {}
        for provider, endpoint in config["mcpServers"].items():
            http = await stack.enter_async_context(
                httpx.AsyncClient(headers=endpoint["headers"])
            )
            read, write, _ = await stack.enter_async_context(
                streamable_http_client(endpoint["url"], http_client=http)
            )
            client = await stack.enter_async_context(ClientSession(read, write))
            await client.initialize()
            clients[provider] = client

        async def call(provider, name, arguments):
            result = await clients[provider].call_tool(name, arguments)
            trace.append(
                {
                    "provider": provider,
                    "tool": name,
                    "arguments": arguments,
                    "result": result.model_dump(mode="json"),
                }
            )
            if result.isError:
                raise RuntimeError(f"{provider}.{name} failed")
            if len(result.content) != 1 or not isinstance(
                result.content[0], TextContent
            ):
                raise RuntimeError("Alpha provider must return exactly one text block")
            return json.loads(result.content[0].text)

        email = re.search(r"[\w.+-]+@[\w.-]+", config["instruction"])
        group = re.search(r"\b[a-f0-9]{32}\b", config["instruction"])
        if email is None or group is None:
            raise ValueError("Replay requires the public identity-group-v1 instruction")
        okta = await call("okta", "get_user", {"user_id": email.group()})
        user = await call(
            "servicenow", "get_user", {"email": okta[0]["profile"]["email"]}
        )
        record = user["user"]
        await call(
            "servicenow",
            "add_group_members",
            {"group_id": group.group(), "members": [record["user_name"]]},
        )
        await call(
            "benchmark",
            "workflow_submit",
            {
                "disposition": "completed",
                "user_id": record["sys_id"],
                "group_id": group.group(),
            },
        )
    return trace


async def run(
    mode: str,
    base_url: str,
    controller_token: str,
    wall_time: float = 300,
    output=print,
) -> dict:
    if wall_time <= 0:
        raise ValueError("wall_time must be positive")
    headers = {"Authorization": f"Bearer {controller_token}"}
    async with (
        ItopsEnv(base_url=base_url, controller_token=controller_token) as owner,
        httpx.AsyncClient(base_url=base_url, headers=headers) as control,
    ):
        await owner.reset()
        trace = []
        try:
            response = await control.get("/control/session")
            response.raise_for_status()
            config = response.json()
            if mode == "connect":
                output(json.dumps(config), flush=True)
            async with asyncio.timeout(wall_time):
                if mode == "replay":
                    trace = await replay(config)
                while True:
                    response = await control.get("/control/result")
                    response.raise_for_status()
                    result = response.json()["result"]
                    if result is not None:
                        return {
                            "policy": "deterministic replay"
                            if mode == "replay"
                            else "external MCP agent",
                            "trace": trace,
                            "trace_id": response.json()["trace_id"],
                            "transport_trace_id": response.json()["transport_trace_id"],
                            "result": result,
                        }
                    await asyncio.sleep(0.1)
        except TimeoutError:
            response = await control.post("/control/finalize")
            response.raise_for_status()
            return {"policy": mode, "trace": trace, **response.json()}
        finally:
            # Finalization is idempotent; preserve an already-submitted result.
            response = await control.post("/control/finalize")
            response.raise_for_status()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("replay", "connect"))
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--wall-time", type=float, default=300)
    args = parser.parse_args()
    token = os.getenv("OPSFORGE_CONTROLLER_TOKEN")
    if not token:
        parser.error("Set OPSFORGE_CONTROLLER_TOKEN")
    try:
        report = asyncio.run(run(args.mode, args.url, token, args.wall_time))
    except KeyboardInterrupt:
        print("Episode finalized and controller closed", file=sys.stderr)
        raise SystemExit(130) from None
    print(json.dumps(report))


if __name__ == "__main__":
    main()
