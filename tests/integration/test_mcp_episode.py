"""Official SDK tests through a real socket and app lifespan."""

import asyncio
import json
import socket
import threading
import time
from contextlib import asynccontextmanager

import httpx
import pytest
import uvicorn
from itops_env import ItopsAction, ItopsEnv
from itops_env.models import ItopsObservation
from itops_env.server.app import OwnedHTTPEnvServer, create_opsforge_app
from itops_env.server.interfaces.control import EpisodeBinding
from itops_env.server.interfaces.mcp_bridge import DuplicateRequestGuard
from itops_env.server.itops_environment import ItopsEnvironment
from itops_env.server.mcp_servers.tools import tool_definitions
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus

TOKEN = "integration-controller"


@pytest.fixture
def live_server():
    app = create_opsforge_app(TOKEN)
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
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(0.01)
            yield url, app
        finally:
            server.should_exit = True
            thread.join(10)
            assert not thread.is_alive()


@asynccontextmanager
async def native(config, provider):
    endpoint = config["mcpServers"][provider]
    async with (
        httpx.AsyncClient(headers=endpoint["headers"]) as http,
        streamable_http_client(endpoint["url"], http_client=http) as (
            read,
            write,
            session_id,
        ),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        yield client, http, session_id


async def configuration(http):
    response = await http.get("/control/session")
    response.raise_for_status()
    return response.json()


def test_native_shared_episode_and_redelivery(live_server):
    url, app = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset(episode_id="reused")
            config = await configuration(control)
            capability = config["mcpServers"]["okta"]["headers"]["Authorization"]
            assert capability not in str((await owner.state()).model_dump())
            async with (
                native(config, "okta") as (okta, http, sid),
                native(config, "servicenow") as (snow, _, _),
                native(config, "benchmark") as (benchmark, _, _),
            ):
                for name, client in [("okta", okta), ("servicenow", snow)]:
                    discovered = await client.list_tools()
                    assert {
                        tool.name: tool.inputSchema for tool in discovered.tools
                    } == {
                        tool.name: tool.parameters
                        for tool in tool_definitions(name).values()
                    }
                assert {tool.name for tool in (await benchmark.list_tools()).tools} == {
                    "workflow_wait",
                    "workflow_submit",
                }
                assert (await owner.state()).step_count == 0
                results = await asyncio.gather(
                    okta.call_tool("get_user", {"user_id": "alex.chen@example.test"}),
                    snow.call_tool("get_user", {"email": "alex.chen@example.test"}),
                    owner.step(
                        ItopsAction(
                            provider="benchmark",
                            tool_name="workflow_wait",
                            arguments={"seconds": 0},
                        )
                    ),
                )
                assert not results[0].isError and not results[1].isError
                assert (await owner.state()).step_count == 3
                assert (await okta.call_tool("snapshot", {})).isError
                assert (await okta.call_tool("get_user", {"user_id": 12})).isError
                assert (
                    await okta.call_tool(
                        "add_group_members", {"provider": "servicenow"}
                    )
                ).isError
                assert (await owner.state()).step_count == 6
                headers = {
                    "mcp-session-id": sid(),
                    "Accept": "application/json, text/event-stream",
                    "mcp-protocol-version": "2025-11-25",
                }
                wire = {
                    "jsonrpc": "2.0",
                    "id": 100,
                    "method": "tools/call",
                    "params": {
                        "name": "get_user",
                        "arguments": {"user_id": "00u-target"},
                    },
                }
                first = await http.post(
                    config["mcpServers"]["okta"]["url"], json=wire, headers=headers
                )
                repeated = await http.post(
                    config["mcpServers"]["okta"]["url"], json=wire, headers=headers
                )
                assert first.status_code == repeated.status_code == 200
                assert first.json() == repeated.json()
                assert (await owner.state()).step_count == 7
                wire["id"] = "100"
                assert (
                    await http.post(
                        config["mcpServers"]["okta"]["url"], json=wire, headers=headers
                    )
                ).status_code == 200
                assert (await owner.state()).step_count == 8
                wire["params"]["arguments"]["user_id"] = "00u-other"
                conflict = await http.post(
                    config["mcpServers"]["okta"]["url"], json=wire, headers=headers
                )
                assert conflict.json()["result"]["isError"]
                assert (await owner.state()).step_count == 9
                user = json.loads(results[1].content[0].text)["user"]
                added = await snow.call_tool(
                    "add_group_members",
                    {"group_id": "a" * 32, "members": [user["user_name"]]},
                )
                assert not added.isError
                submit = await owner.step(
                    ItopsAction(
                        provider="benchmark",
                        tool_name="workflow_submit",
                        arguments={
                            "disposition": "completed",
                            "user_id": user["sys_id"],
                            "group_id": "a" * 32,
                        },
                    )
                )
                assert submit.reward == 1 and submit.done
                again = await benchmark.call_tool(
                    "workflow_submit",
                    {
                        "disposition": "completed",
                        "user_id": user["sys_id"],
                        "group_id": "a" * 32,
                    },
                )
                assert again.isError
                result = (await control.get("/control/result")).json()["result"]
                assert result["status"] == "success" and result["reward"] == 1
                assert (await control.post("/control/finalize")).json()[
                    "result"
                ] == result
                snapshot = await control.get("/control/snapshot")
                assert snapshot.content.startswith(b"SQLite format 3")
                await owner.reset(episode_id="reused")
                stale = await http.post(
                    config["mcpServers"]["okta"]["url"], json=wire, headers=headers
                )
                assert stale.status_code == 401
                fresh = await configuration(control)
                assert (
                    fresh["mcpServers"]["okta"]["headers"]
                    != config["mcpServers"]["okta"]["headers"]
                )
                new_cap_old_session = await http.post(
                    config["mcpServers"]["okta"]["url"],
                    json=wire,
                    headers=headers | fresh["mcpServers"]["okta"]["headers"],
                )
                assert new_cap_old_session.status_code in (403, 404)
            async with native(fresh, "okta") as (client, _, _):
                await client.call_tool("get_user", {"user_id": "00u-target"})
            async with native(fresh, "okta") as (client, _, _):
                await client.call_tool("get_user", {"user_id": "00u-target"})
            assert (await owner.state()).step_count == 2
        for _ in range(100):
            if app.state.binding.env is None:
                break
            await asyncio.sleep(0.01)
        assert app.state.binding.env is None
        async with httpx.AsyncClient() as http:
            assert (
                await http.post(
                    fresh["mcpServers"]["okta"]["url"],
                    headers=fresh["mcpServers"]["okta"]["headers"],
                    json=wire,
                )
            ).status_code == 401

    asyncio.run(check())


def test_auth_surfaces_capacity_and_abrupt_disconnect(live_server):
    url, app = live_server

    async def check():
        async with httpx.AsyncClient(base_url=url) as http:
            assert (await http.get("/health")).json() == {"status": "healthy"}
            for path in (
                "/reset",
                "/step",
                "/state",
                "/schema",
                "/mcp",
                "/mcp/",
                "/web",
                "/docs",
                "/openapi.json",
            ):
                assert (await http.post(path)).status_code == 404
            for path in ("/control/session", "/control/result", "/control/snapshot"):
                assert (await http.get(path)).status_code == 401
                assert (
                    await http.get(path, headers={"Authorization": "Bearer wrong"})
                ).status_code == 401
            assert (await http.post("/control/finalize")).status_code == 401
            for bearer in (None, "wrong"):
                with pytest.raises(ConnectionError):
                    async with ItopsEnv(base_url=url, controller_token=bearer):
                        pass
            with pytest.raises(InvalidStatus):
                async with connect(url.replace("http", "ws") + "/mcp"):
                    pass
            owner = ItopsEnv(base_url=url, controller_token=TOKEN)
            await owner.connect()
            await owner.reset()
            cfg = (
                await http.get(
                    "/control/session", headers={"Authorization": f"Bearer {TOKEN}"}
                )
            ).json()
            agent_headers = cfg["mcpServers"]["okta"]["headers"]
            assert (
                await http.get("/control/result", headers=agent_headers)
            ).status_code == 401
            assert (
                await http.post(
                    "/mcp/okta/", headers={"Authorization": f"Bearer {TOKEN}"}
                )
            ).status_code == 401
            with pytest.raises(ConnectionError):
                async with ItopsEnv(
                    base_url=url, controller_token=agent_headers["Authorization"][7:]
                ):
                    pass
            with pytest.raises((ConnectionError, RuntimeError)):
                async with ItopsEnv(base_url=url, controller_token=TOKEN) as other:
                    await other.reset()
            episode = app.state.binding.env.episode
            owner._ws.transport.abort()
            await owner.close()
            for _ in range(100):
                if app.state.binding.env is None:
                    break
                await asyncio.sleep(0.01)
            assert app.state.binding.env is None
            assert episode.state.phase == "closed"
            async with ItopsEnv(base_url=url, controller_token=TOKEN) as next_owner:
                await next_owner.reset()
                assert (await next_owner.state()).step_count == 0

    asyncio.run(check())


def test_independent_apps_and_reset_revalidation():
    first, second = create_opsforge_app("one"), create_opsforge_app("two")
    a, b = first.state.binding, second.state.binding
    env = ItopsEnvironment(binding=a)
    other = ItopsEnvironment(binding=b)
    env.reset()
    old = a.capability
    other.reset()
    assert a.matches(old) and not b.matches(old)
    with pytest.raises(ValueError):
        env.reset(seed=-1)
    assert a.matches(old)
    env.reset()
    assert not a.matches(old)
    env.close()
    assert b.env is other
    other.close()


def test_duplicate_transport_guard():
    async def check():
        binding = EpisodeBinding()
        env = ItopsEnvironment(binding=binding)
        env.reset()
        entered, release = asyncio.Event(), asyncio.Event()

        async def downstream(scope, receive, send):
            await receive()
            entered.set()
            await release.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        guard = DuplicateRequestGuard(downstream, binding, "okta")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=guard), base_url="http://test"
        ) as http:
            headers = {
                "Authorization": f"Bearer {binding.capability}",
                "mcp-session-id": "session",
            }
            initial = asyncio.create_task(
                http.post("/", headers=headers, json={"id": 1})
            )
            await entered.wait()
            duplicate = await http.post("/", headers=headers, json={"id": "1"})
            assert duplicate.status_code == 409
            release.set()
            assert (await initial).status_code == 200
            assert (
                await http.post("/", headers=headers, json={"id": 1})
            ).status_code == 200
            assert not guard.inflight
        events = [
            json.loads(line)
            for line in binding.traces.read(binding.traces.transport_id).splitlines()
        ]
        assert [
            event["status"]
            for event in events
            if event["event"] == "mcp.request_completed"
        ] == [409, 200, 200]
        env.close()

    asyncio.run(check())


def test_cancelled_session_creation_releases_capacity():
    async def check():
        entered, release = threading.Event(), threading.Event()

        def factory():
            entered.set()
            assert release.wait(5)
            return ItopsEnvironment()

        server = OwnedHTTPEnvServer(
            factory, ItopsAction, ItopsObservation, max_concurrent_envs=1
        )
        task = asyncio.create_task(server._create_session())
        while not entered.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not server._sessions and not server._session_executors
        session_id, _ = await server._create_session()
        await server._destroy_session(session_id)

    asyncio.run(check())


def test_native_terminal_replay_malformed_envelope_and_callback_failure(
    live_server, monkeypatch
):
    url, app = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset()
            config = await configuration(control)
            async with native(config, "benchmark") as (_, http, sid):
                endpoint = config["mcpServers"]["benchmark"]["url"]
                headers = {
                    "mcp-session-id": sid(),
                    "Accept": "application/json, text/event-stream",
                }
                malformed = await http.post(
                    endpoint,
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 90,
                        "method": "tools/call",
                        "params": {"name": "workflow_wait", "arguments": []},
                    },
                )
                assert malformed.status_code == 200
                assert malformed.json()["error"]["code"] == -32602
                assert "result" not in malformed.json()
                assert (await owner.state()).step_count == 0
                wire = {
                    "jsonrpc": "2.0",
                    "id": 91,
                    "method": "tools/call",
                    "params": {
                        "name": "workflow_submit",
                        "arguments": {
                            "disposition": "completed",
                            "user_id": "1" * 32,
                            "group_id": "a" * 32,
                        },
                    },
                }
                submitted = await http.post(endpoint, headers=headers, json=wire)
                replayed = await http.post(endpoint, headers=headers, json=wire)
                assert submitted.status_code == replayed.status_code == 200
                assert submitted.json() == replayed.json()
                assert (await owner.state()).step_count == 1
                assert (await control.get("/control/result")).json()["result"][
                    "status"
                ] == "failure"
            await owner.reset()
            config = await configuration(control)
            # A provider bug is a trusted infrastructure result, never a success or
            # unaccounted recoverable business call. Domain rollback remains authoritative.
            import sqlite3

            from itops_env.server.services import okta

            def failed_provider(*args):
                raise sqlite3.OperationalError(
                    "/private/secret-grader.sqlite controller-secret"
                )

            monkeypatch.setattr(okta, "get_user", failed_provider)
            async with native(config, "okta") as (client, _, _):
                result = await client.call_tool("get_user", {"user_id": "00u-target"})
                assert result.isError
                assert "/private/" not in str(
                    result
                ) and "controller-secret" not in str(result)
            assert (await control.get("/control/result")).json()["result"][
                "status"
            ] == "infrastructure_error"
            assert (
                app.state.binding.env.episode.result().status == "infrastructure_error"
            )

    asyncio.run(check())


def test_native_admission_rechecks_capability(monkeypatch):
    from types import SimpleNamespace

    from fastmcp.exceptions import ToolError
    from itops_env.server.interfaces import mcp_bridge

    binding = EpisodeBinding()
    env = ItopsEnvironment(binding=binding)
    env.reset()
    authenticated = SimpleNamespace(token=binding.capability)
    context = SimpleNamespace(
        request_context=SimpleNamespace(
            request=SimpleNamespace(headers={"mcp-session-id": "validated-session"}),
            request_id=1,
        )
    )
    monkeypatch.setattr(mcp_bridge, "get_access_token", lambda: authenticated)
    monkeypatch.setattr(mcp_bridge, "get_context", lambda: context)
    env.reset()
    with pytest.raises(ToolError, match="expired"):
        asyncio.run(
            mcp_bridge.dispatch_native(
                binding, "okta", "get_user", {"user_id": "00u-target"}
            )
        )
    assert env.state.step_count == 0
    env.close()


def test_app_lifespan_closes_owned_database():
    async def check():
        app = create_opsforge_app(TOKEN)
        async with app.router.lifespan_context(app):
            env = ItopsEnvironment(binding=app.state.binding)
            env.reset()
            episode = env.episode
            capability = app.state.binding.capability
        assert episode.state.phase == "closed"
        assert not app.state.binding.matches(capability)

    asyncio.run(check())


def test_duplicate_guard_cancellation_drains_sdk_response():
    async def check():
        binding = EpisodeBinding()
        env = ItopsEnvironment(binding=binding)
        env.reset()
        entered, release = asyncio.Event(), asyncio.Event()

        async def downstream(scope, receive, send):
            await receive()
            entered.set()
            await release.wait()

        guard = DuplicateRequestGuard(downstream, binding, "okta")
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [
                (b"authorization", f"Bearer {binding.capability}".encode()),
                (b"mcp-session-id", b"session"),
            ],
        }

        async def receive():
            return {"type": "http.request", "body": b'{"id": 1}', "more_body": False}

        sent = []

        async def send(message):
            sent.append(message)

        active = asyncio.create_task(guard(scope, receive, send))
        await entered.wait()
        active.cancel()
        await asyncio.sleep(0)
        assert guard.inflight
        await guard(scope, receive, send)
        assert sent[0]["status"] == 409
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await active
        assert not guard.inflight
        env.close()

    asyncio.run(check())


def test_generation_rollover_drains_attached_native_sessions(live_server):
    url, app = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset()
            config = await configuration(control)
            async with (
                native(config, "okta"),
                native(config, "servicenow"),
                native(config, "benchmark"),
            ):
                old = [
                    transport
                    for manager in app.state.binding.native_managers
                    for transport in manager._server_instances.values()
                ]
                assert len(old) == 3
                assert any(
                    transport._request_streams for transport in old
                )  # SDK GET streams remain attached.
                await owner.reset()
                assert all(
                    transport.is_terminated and not transport._request_streams
                    for transport in old
                )
                assert all(
                    not manager._server_instances and not manager._session_owners
                    for manager in app.state.binding.native_managers
                )
                fresh = await configuration(control)
                async with native(fresh, "okta") as (client, _, _):
                    await client.call_tool("get_user", {"user_id": "00u-target"})
                    assert (
                        sum(
                            len(manager._server_instances)
                            for manager in app.state.binding.native_managers
                        )
                        == 1
                    )
                    assert (await owner.state()).step_count == 1
            config = await configuration(control)
            async with (
                native(config, "okta"),
                native(config, "servicenow"),
                native(config, "benchmark"),
            ):
                old = [
                    transport
                    for manager in app.state.binding.native_managers
                    for transport in manager._server_instances.values()
                ]
                owner._ws.transport.abort()
                await owner.close()
                for _ in range(100):
                    if all(transport.is_terminated for transport in old):
                        break
                    await asyncio.sleep(0.01)
                assert all(
                    transport.is_terminated and not transport._request_streams
                    for transport in old
                )
                assert all(
                    not manager._server_instances and not manager._session_owners
                    for manager in app.state.binding.native_managers
                )

    asyncio.run(check())


def test_authenticated_initialize_cannot_register_after_reset(live_server):
    url, app = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset()
            config = await configuration(control)
            manager = app.state.binding.native_managers[0]
            entered = threading.Event()
            release = threading.Event()
            original_lock = manager._session_creation_lock

            class BlockAdmission:
                async def __aenter__(self):
                    entered.set()
                    while not release.is_set():
                        await asyncio.sleep(0.001)
                    return await original_lock.__aenter__()

                async def __aexit__(self, *args):
                    return await original_lock.__aexit__(*args)

            manager._session_creation_lock = BlockAdmission()
            async with httpx.AsyncClient() as http:
                stale = asyncio.create_task(
                    http.post(
                        config["mcpServers"]["okta"]["url"],
                        headers=config["mcpServers"]["okta"]["headers"]
                        | {"Accept": "application/json, text/event-stream"},
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-11-25",
                                "capabilities": {},
                                "clientInfo": {"name": "race", "version": "1"},
                            },
                        },
                    )
                )
                while not entered.is_set():
                    await asyncio.sleep(0.001)
                await owner.reset()
                release.set()
                response = await stale
                assert response.status_code == 503
                assert not manager._server_instances and not manager._session_owners
                manager._session_creation_lock = original_lock
                async with native(await configuration(control), "okta"):
                    assert len(manager._server_instances) == 1

    asyncio.run(check())


def test_sync_bound_reset_schedules_generation_cleanup(live_server):
    url, app = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset()
            async with native(await configuration(control), "okta"):
                manager = app.state.binding.native_managers[0]
                transport = next(iter(manager._server_instances.values()))
                app.state.binding.env.reset()
                for _ in range(100):
                    if transport.is_terminated:
                        break
                    await asyncio.sleep(0.01)
                assert transport.is_terminated and not manager._server_instances

    asyncio.run(check())


def test_reset_during_native_startup_drains_old_and_preserves_new(
    live_server, monkeypatch
):
    from mcp.server.streamable_http import StreamableHTTPServerTransport

    url, app = live_server
    entered, release = threading.Event(), threading.Event()
    original_connect = StreamableHTTPServerTransport.connect

    @asynccontextmanager
    async def blocked_first_connect(transport):
        if not entered.is_set():
            entered.set()
            while not release.is_set():
                await asyncio.sleep(0.001)
        async with original_connect(transport) as streams:
            yield streams

    monkeypatch.setattr(StreamableHTTPServerTransport, "connect", blocked_first_connect)

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
            httpx.AsyncClient() as http,
        ):
            await owner.reset()
            config = await configuration(control)
            old_generation = app.state.binding.generation
            endpoint = config["mcpServers"]["okta"]
            opening = asyncio.create_task(
                http.post(
                    endpoint["url"],
                    headers=endpoint["headers"]
                    | {"Accept": "application/json, text/event-stream"},
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "startup-race", "version": "1"},
                        },
                    },
                )
            )
            while not entered.is_set():
                await asyncio.sleep(0.001)
            manager = app.state.binding.native_managers[0]
            old = next(iter(manager._server_instances.values()))
            resetting = asyncio.create_task(owner.reset())
            while app.state.binding.generation == old_generation:
                await asyncio.sleep(0.001)
            async with native(await configuration(control), "okta") as (client, _, _):
                release.set()
                await resetting
                await opening
                assert old.is_terminated and not old._request_streams
                assert len(manager._server_instances) == 1
                assert all(
                    transport is not old
                    for transport in manager._server_instances.values()
                )
                result = await client.call_tool("get_user", {"user_id": "00u-target"})
                assert not result.isError
                assert (await owner.state()).step_count == 1
                assert not app.state.binding.native_starting

    asyncio.run(check())


@pytest.mark.parametrize("operation", ["reset", "close"])
def test_sqlite_finalization_failure_denies_stale_native_and_releases_owner(
    live_server, operation
):
    import sqlite3

    url, app = live_server

    async def check():
        async with (
            ItopsEnv(base_url=url, controller_token=TOKEN) as owner,
            httpx.AsyncClient(
                base_url=url, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as control,
        ):
            await owner.reset()
            config = await configuration(control)
            binding = app.state.binding
            env = binding.env
            old = env.episode
            directory = old.db.directory
            with binding.lock:
                old.db.connection.execute(
                    "CREATE TRIGGER fail_result BEFORE INSERT ON result BEGIN SELECT RAISE(ABORT, 'injected result persistence failure'); END"
                )
            async with native(config, "okta") as (_, http, sid):
                transport = next(
                    iter(binding.native_managers[0]._server_instances.values())
                )
                if operation == "reset":
                    with pytest.raises(
                        RuntimeError, match="injected result persistence failure"
                    ):
                        await owner.reset()
                else:
                    # Exercise the actual bound sync close in a trusted thread; it
                    # must propagate the SQLite error and independently schedule drain.
                    with pytest.raises(
                        sqlite3.IntegrityError,
                        match="injected result persistence failure",
                    ):
                        await asyncio.to_thread(env.close)
                for _ in range(100):
                    if transport.is_terminated:
                        break
                    await asyncio.sleep(0.01)
                assert transport.is_terminated and not transport._request_streams
                assert all(
                    not manager._server_instances and not manager._session_owners
                    for manager in binding.native_managers
                )
                assert (
                    env.episode is old and old.result().status == "infrastructure_error"
                )
                assert binding.env is None and not directory.exists()
                stale = await http.post(
                    config["mcpServers"]["okta"]["url"],
                    headers={
                        "mcp-session-id": sid(),
                        "Accept": "application/json, text/event-stream",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 99,
                        "method": "tools/call",
                        "params": {
                            "name": "get_user",
                            "arguments": {"user_id": "00u-target"},
                        },
                    },
                )
                assert stale.status_code == 401
                assert (await control.get("/control/session")).status_code == 409
        async with ItopsEnv(base_url=url, controller_token=TOKEN) as replacement:
            await replacement.reset()
            fresh = await replacement.step(
                ItopsAction(
                    provider="okta",
                    tool_name="get_user",
                    arguments={"user_id": "00u-target"},
                )
            )
            assert not fresh.observation.is_error
            assert (await replacement.state()).step_count == 1

    asyncio.run(check())


def test_app_shutdown_finalization_failure_still_drains_and_revokes():
    import sqlite3

    async def check():
        app = create_opsforge_app(TOKEN)
        binding = app.state.binding
        with pytest.RaisesGroup(
            pytest.RaisesExc(sqlite3.IntegrityError, match="shutdown result failure"),
            flatten_subgroups=True,
        ):
            async with app.router.lifespan_context(app):
                env = ItopsEnvironment(binding=binding)
                env.reset()
                old = env.episode
                directory = old.db.directory
                old.db.connection.execute(
                    "CREATE TRIGGER fail_result BEFORE INSERT ON result BEGIN SELECT RAISE(ABORT, 'shutdown result failure'); END"
                )
        assert binding.env is None and binding.capability is None
        assert binding.native_loop is None and not binding.native_drains
        assert old.result().status == "infrastructure_error"
        assert not directory.exists()

    asyncio.run(check())
