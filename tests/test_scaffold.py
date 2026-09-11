"""Exercise the installed package through a real OpenEnv WebSocket server."""

import asyncio
import json
import socket
import threading
import time

import pytest
import uvicorn
from itops_env import ItopsAction, ItopsEnv
from itops_env.server.app import create_opsforge_app

CONTROLLER_TOKEN = "scaffold-controller"
from itops_env.server.itops_environment import ItopsEnvironment


@pytest.fixture
def server_url():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        address = f"http://127.0.0.1:{listener.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(
                create_opsforge_app(CONTROLLER_TOKEN),
                log_level="error",
                ws="websockets-sansio",
            )
        )
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listener]}, daemon=True
        )
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not server.started:
                assert thread.is_alive(), "OpenEnv server exited during startup"
                assert time.monotonic() < deadline, "OpenEnv server did not start"
                time.sleep(0.01)
            yield address
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive(), "OpenEnv server did not stop"


def test_async_client_roundtrip_and_reset(server_url):
    async def run_episode():
        async with ItopsEnv(
            base_url=server_url, controller_token=CONTROLLER_TOKEN
        ) as client:
            initial = await client.reset()
            initial_state = await client.state()
            assert initial.reward == 0.0
            assert initial_state.step_count == 0

            result = await client.step(
                ItopsAction(
                    provider="okta",
                    tool_name="get_user",
                    arguments={"user_id": "00u-target"},
                )
            )
            assert (
                json.loads(result.observation.content[0]["text"])[0]["id"]
                == "00u-target"
            )
            assert result.reward == 0.0
            assert result.done is False
            assert (await client.state()).step_count == 1

            await client.reset()
            reset_state = await client.state()
            assert reset_state.episode_id != initial_state.episode_id
            assert reset_state.step_count == 0

    asyncio.run(run_episode())


def test_sync_client_reconnect_starts_a_fresh_session(server_url):
    with ItopsEnv(
        base_url=server_url, controller_token=CONTROLLER_TOKEN
    ).sync() as client:
        client.reset()
        first_id = client.state().episode_id
        client.step(
            ItopsAction(
                provider="okta",
                tool_name="get_user",
                arguments={"user_id": "00u-target"},
            )
        )
        assert client.state().step_count == 1

    with ItopsEnv(
        base_url=server_url, controller_token=CONTROLLER_TOKEN
    ).sync() as client:
        client.reset()
        assert client.state().episode_id != first_id
        assert client.state().step_count == 0
        result = client.step(
            ItopsAction(
                provider="servicenow",
                tool_name="get_user",
                arguments={"email": "alex.chen@example.test"},
            )
        )
        assert (
            json.loads(result.observation.content[0]["text"])["user"]["sys_id"]
            == "1" * 32
        )
        assert result.reward == 0.0


def test_async_lifecycle_accepts_openenv_parameters():
    async def run_episode():
        env = ItopsEnvironment()
        initial = await env.reset_async(seed=42, episode_id="scaffold-episode")
        assert initial.reward == 0.0
        assert env.state.episode_id == "scaffold-episode"
        result = await env.step_async(
            ItopsAction(
                provider="okta",
                tool_name="get_user",
                arguments={"user_id": "00u-target"},
            ),
            timeout_s=1.0,
        )
        assert json.loads(result.content[0]["text"])[0]["status"] == "ACTIVE"
        assert result.reward == 0.0
        assert env.state.step_count == 1
        env.close()

    asyncio.run(run_episode())
