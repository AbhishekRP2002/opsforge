"""Exercise the installed package through a real OpenEnv WebSocket server."""

import asyncio
import socket
import threading
import time

import pytest
import uvicorn
from itops_env import ItopsAction, ItopsEnv
from itops_env.server.app import app
from itops_env.server.itops_environment import ItopsEnvironment


@pytest.fixture
def server_url():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        address = f"http://127.0.0.1:{listener.getsockname()[1]}"
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
        async with ItopsEnv(base_url=server_url) as client:
            initial = await client.reset()
            initial_state = await client.state()
            assert initial.reward == 0.0
            assert initial_state.step_count == 0

            result = await client.step(ItopsAction(message="OpsForge"))
            assert result.observation.echoed_message == "OpsForge"
            assert result.observation.message_length == 8
            assert result.reward == pytest.approx(0.8)
            assert result.done is False
            assert (await client.state()).step_count == 1

            await client.reset()
            reset_state = await client.state()
            assert reset_state.episode_id != initial_state.episode_id
            assert reset_state.step_count == 0

    asyncio.run(run_episode())


def test_sync_client_reconnect_starts_a_fresh_session(server_url):
    with ItopsEnv(base_url=server_url).sync() as client:
        client.reset()
        first_id = client.state().episode_id
        client.step(ItopsAction(message="First session"))
        assert client.state().step_count == 1

    with ItopsEnv(base_url=server_url).sync() as client:
        client.reset()
        assert client.state().episode_id != first_id
        assert client.state().step_count == 0
        result = client.step(ItopsAction(message=""))
        assert result.observation.echoed_message == ""
        assert result.reward == 0.0


def test_inherited_async_lifecycle_accepts_openenv_parameters():
    async def run_episode():
        env = ItopsEnvironment()
        initial = await env.reset_async(seed=42, episode_id="scaffold-episode")
        assert initial.reward == 0.0
        assert env.state.episode_id == "scaffold-episode"
        result = await env.step_async(ItopsAction(message="Async"), timeout_s=1.0)
        assert result.echoed_message == "Async"
        assert result.reward == pytest.approx(0.5)
        assert env.state.step_count == 1

    asyncio.run(run_episode())
