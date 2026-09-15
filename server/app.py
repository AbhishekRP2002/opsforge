"""One trusted OpenEnv owner with registry-defined agent-only MCP endpoints."""

import asyncio
import os
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from itops_env.models import ItopsAction, ItopsObservation
from openenv.core.env_server.http_server import HTTPEnvServer

from .core.scenarios import Scenario
from .interfaces.control import ControllerAuth, EpisodeBinding, register_control
from .interfaces.mcp_bridge import DuplicateRequestGuard
from .itops_environment import ItopsEnvironment
from .mcp_servers.providers import bind_native_lifecycle, provider_app
from .mcp_servers.tools import REGISTRARS, validate_registry


class OwnedHTTPEnvServer(HTTPEnvServer):
    """Pinned 0.4.2 adapter: drain creation before cleaning a cancelled owner."""

    def __init__(self, *args, binding=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.binding = binding

    async def _destroy_session(self, session_id):
        try:
            await super()._destroy_session(session_id)
        finally:
            if self.binding is not None:
                await self.binding.drain_native()

    async def _create_session(self):
        pending = asyncio.create_task(super()._create_session())
        try:
            return await asyncio.shield(pending)
        except asyncio.CancelledError:
            session_id, _ = await pending
            await self._destroy_session(session_id)
            raise


def create_opsforge_app(
    controller_token: str | None = None,
    scenario: Scenario | str = "identity-group-v1",
) -> FastAPI:
    validate_registry()
    token = (
        controller_token
        if controller_token is not None
        else os.getenv("OPSFORGE_CONTROLLER_TOKEN")
    )
    binding = EpisodeBinding()
    server = OwnedHTTPEnvServer(
        lambda: ItopsEnvironment(scenario=scenario, binding=binding),
        ItopsAction,
        ItopsObservation,
        binding=binding,
        max_concurrent_envs=1,
        env_name="opsforge",
    )
    application = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    server.register_routes(application)
    application.router.routes[:] = [
        route
        for route in application.router.routes
        if getattr(route, "path", None) == "/ws"
    ]
    application.add_middleware(ControllerAuth, token=token)
    register_control(application, binding)

    @application.get("/health")
    def health():
        return {"status": "healthy"}

    children = []
    for provider in REGISTRARS:
        child = provider_app(binding, provider)
        children.append(child)
        application.mount(
            f"/mcp/{provider}", DuplicateRequestGuard(child, binding, provider)
        )
    parent_lifespan = application.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(parent_lifespan(app))
            for child in children:
                await stack.enter_async_context(child.lifespan(child))
                bind_native_lifecycle(child, binding)
            binding.native_loop = asyncio.get_running_loop()
            try:
                yield
            finally:
                try:
                    binding.close()
                finally:
                    await binding.drain_native()
                    binding.native_loop = None
                    for session_id in list(server._sessions):
                        await server._destroy_session(session_id)

    application.router.lifespan_context = lifespan
    application.state.binding = binding
    application.state.openenv_server = server
    return application


app = create_opsforge_app()


def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn

    if not os.getenv("OPSFORGE_CONTROLLER_TOKEN"):
        raise SystemExit("Set OPSFORGE_CONTROLLER_TOKEN before starting OpsForge")
    uvicorn.run(create_opsforge_app(), host=host, port=port, workers=1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    main(port=args.port)
