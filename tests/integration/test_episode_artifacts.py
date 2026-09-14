import asyncio
import json

import httpx
import pytest
from itops_env import ItopsAction
from itops_env.server.app import create_opsforge_app
from itops_env.server.itops_environment import ItopsEnvironment


def test_csv_is_transactional_episode_storage_and_controller_authenticated():
    async def check():
        app = create_opsforge_app("controller-secret")
        env = ItopsEnvironment(binding=app.state.binding)
        async with app.router.lifespan_context(app):
            env.reset()
            result = env.step(
                ItopsAction(provider="okta", tool_name="export_users_csv", arguments={})
            )
            payload = json.loads(result.content[0]["text"])
            assert (
                not result.is_error
                and payload["output_path"] == "/tmp/okta_users_export.csv"
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                assert (
                    await client.get("/control/artifacts/okta_users_export.csv")
                ).status_code == 401
                fetched = await client.get(
                    "/control/artifacts/okta_users_export.csv",
                    headers={"Authorization": "Bearer controller-secret"},
                )
                assert fetched.status_code == 200
                assert fetched.text.startswith(
                    "id,status,login,email,firstName,lastName"
                )
            env.close()

    asyncio.run(check())


def test_csv_rejects_traversal_and_rolls_back_persistence_failure():
    env = ItopsEnvironment()
    env.reset()
    try:
        bad = env.step(
            ItopsAction(
                provider="okta",
                tool_name="export_users_csv",
                arguments={"output_path": "/tmp/../stolen.csv"},
            )
        )
        assert bad.is_error
        assert env.episode is not None
        env.episode.db.connection.execute(
            "CREATE TRIGGER reject_artifact BEFORE INSERT ON episode_artifacts BEGIN SELECT RAISE(ABORT, 'artifact rejected'); END"
        )
        with pytest.raises(Exception, match="artifact rejected"):
            env.step(
                ItopsAction(
                    provider="okta",
                    tool_name="export_users_csv",
                    arguments={"output_path": "/tmp/rollback.csv"},
                )
            )
        assert (
            env.episode.db.connection.execute(
                "SELECT count(*) FROM episode_artifacts"
            ).fetchone()[0]
            == 0
        )
    finally:
        env.close()


def test_csv_invocation_replay_is_single_step_and_reset_cleans_artifacts():
    env = ItopsEnvironment()
    env.reset(episode_id="artifact-first")
    action = ItopsAction(
        provider="okta",
        tool_name="export_users_csv",
        arguments={"output_path": "/tmp/replayed.csv"},
        invocation_id="same-export",
    )
    try:
        first = env.step(action)
        replay = env.step(action)
        assert replay.content == first.content
        assert env.state.step_count == 1
        assert env.state.simulated_clock == 1
        assert env.episode is not None
        assert (
            env.episode.db.connection.execute(
                "SELECT count(*) FROM episode_artifacts WHERE path='replayed.csv'"
            ).fetchone()[0]
            == 1
        )

        env.reset(episode_id="artifact-second")
        assert env.episode.db.artifact("replayed.csv") is None
        assert env.state.step_count == 0
        assert env.state.simulated_clock == 0
    finally:
        env.close()
