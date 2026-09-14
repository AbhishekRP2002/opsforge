import asyncio
import json

import httpx
from itops_env import ItopsAction
from itops_env.server.app import create_opsforge_app
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment


def test_nested_theme_artifact_is_controller_authenticated_and_retrievable():
    async def check():
        scenario = Scenario.model_validate(
            load_scenario().model_dump()
            | {
                "initial_artifacts": [
                    {
                        "path": "/tmp/logo.svg",
                        "content": "<svg/>",
                        "media_type": "image/svg+xml",
                    }
                ]
            }
        )
        app = create_opsforge_app("media-secret")
        env = ItopsEnvironment(scenario=scenario, binding=app.state.binding)
        async with app.router.lifespan_context(app):
            env.reset()
            env.step(
                ItopsAction(
                    provider="okta",
                    tool_name="create_brand",
                    arguments={"name": "Media"},
                )
            )
            result = env.step(
                ItopsAction(
                    provider="okta",
                    tool_name="upload_brand_theme_logo",
                    arguments={
                        "brand_id": "bnd000001",
                        "theme_id": "thm000001",
                        "file_path": "/tmp/logo.svg",
                    },
                )
            )
            assert not result.is_error
            path = json.loads(result.content[0]["text"])["url"].removeprefix(
                "episode-artifact:"
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                assert (
                    await client.get(f"/control/artifacts/{path}")
                ).status_code == 401
                response = await client.get(
                    f"/control/artifacts/{path}",
                    headers={"Authorization": "Bearer media-secret"},
                )
                assert response.status_code == 200
                assert response.content == b"<svg/>"
                for invalid in (
                    "etc/passwd",
                    "artifacts/%252e%252e/secret",
                    "artifacts/unknown",
                ):
                    assert (
                        await client.get(
                            f"/control/artifacts/{invalid}",
                            headers={"Authorization": "Bearer media-secret"},
                        )
                    ).status_code == 404
            env.close()

    asyncio.run(check())
