"""App-scoped episode ownership and controller-only HTTP operations."""

import asyncio
import secrets
from concurrent.futures import Future
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from ..core.tracing import TraceStore

if TYPE_CHECKING:
    from mcp.server.streamable_http import StreamableHTTPServerTransport
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from ..core.episode import Episode
    from ..itops_environment import ItopsEnvironment

from ..rubrics import ItopsOutcomeRubric


class EpisodeBinding:
    def __init__(self):
        self.lock = RLock()
        self.traces = TraceStore()
        self.env: ItopsEnvironment | None = None
        self.capability: str | None = None
        self.generation: str | None = None
        self.native_managers: list[StreamableHTTPSessionManager] = []
        self.native_starting: dict[StreamableHTTPServerTransport, asyncio.Event] = {}
        self.native_loop: asyncio.AbstractEventLoop | None = None
        self.native_drains: list[Future[None]] = []

    def bind(self, env: "ItopsEnvironment") -> None:
        self.env = env
        self.capability = secrets.token_urlsafe(32)
        self.generation = secrets.token_hex(16)
        self.schedule_native_drain()

    def matches(self, token: str) -> bool:
        with self.lock:
            return (
                self.env is not None
                and self.capability is not None
                and secrets.compare_digest(token, self.capability)
            )

    def require(self) -> "Episode":
        if self.env is None or self.env.episode is None:
            raise HTTPException(
                409, "No owned episode; open controller WebSocket and reset first"
            )
        return self.env.episode

    def close(self):
        with self.lock:
            if self.env is not None:
                self.env.close()

    def schedule_native_drain(self):
        # reset()/close() are synchronous and may run on an OpenEnv executor.
        # Queue onto the owning loop; no transport await occurs under the writer lock.
        if self.native_loop is not None:
            self.native_drains.append(
                asyncio.run_coroutine_threadsafe(self._drain_stale(), self.native_loop)
            )

    async def _drain_stale(self) -> None:
        with self.lock:
            stale = [
                (manager, session_id, transport, self.native_starting.get(transport))
                for manager in self.native_managers
                for session_id, transport in list(manager._server_instances.items())
                if manager._session_owners.get(session_id, {}).get("subject")
                != self.generation
            ]
        for manager, session_id, transport, started in stale:
            if started is not None:
                # The SDK registers before task_group.start initializes streams.
                # Terminating before that point would leave newly created streams open.
                await started.wait()
            await manager._discard_session(session_id, transport)

    async def drain_native(self):
        """Await scheduled sync lifecycle cleanup and any stale native sessions."""
        with self.lock:
            scheduled, self.native_drains = self.native_drains, []
        pending = asyncio.gather(
            *(asyncio.wrap_future(future) for future in scheduled), self._drain_stale()
        )
        try:
            await asyncio.shield(pending)
        except asyncio.CancelledError:
            await pending
            raise


class ControllerAuth:
    def __init__(self, app, token: str | None):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"} and (
            scope["path"] == "/ws" or scope["path"].startswith("/control/")
        ):
            supplied = Headers(scope=scope).get("authorization", "")
            if not self.token or not secrets.compare_digest(
                supplied, f"Bearer {self.token}"
            ):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await JSONResponse(
                        {"detail": "Controller authentication required"},
                        status_code=401,
                    )(scope, receive, send)
                return
        await self.app(scope, receive, send)


def register_control(app: FastAPI, binding: EpisodeBinding):
    @app.get("/control/session")
    def session(request: Request):
        with binding.lock:
            episode = binding.require()
            base = str(request.base_url).rstrip("/")
            return {
                "instruction": episode.scenario.instruction,
                "policy": episode.scenario.policy,
                "episode_id": episode.episode_id,
                "mcpServers": {
                    provider: {
                        "url": f"{base}/mcp/{provider}/",
                        "headers": {"Authorization": f"Bearer {binding.capability}"},
                    }
                    for provider in ("okta", "servicenow", "benchmark")
                },
            }

    @app.get("/control/result")
    def result():
        with binding.lock:
            episode = binding.require()
            assert binding.env is not None
            assert isinstance(binding.env.rubric, ItopsOutcomeRubric)
            result = episode.result()
            return {
                "result": result.model_dump(mode="json") if result else None,
                "trace_id": episode.trace_id,
                "transport_trace_id": binding.traces.transport_id,
                "rubric": binding.env.rubric.diagnostics(),
            }

    @app.post("/control/finalize")
    def finalize():
        with binding.lock:
            episode = binding.require()
            assert binding.env is not None
            assert isinstance(binding.env.rubric, ItopsOutcomeRubric)
            return {
                "result": episode.finalize().model_dump(mode="json"),
                "trace_id": episode.trace_id,
                "transport_trace_id": binding.traces.transport_id,
                "rubric": binding.env.rubric.diagnostics(),
            }

    @app.get("/control/trace")
    def current_trace():
        with binding.lock:
            return trace_export(binding.require().trace_id)

    @app.get("/control/trace/{trace_id}")
    def trace_export(trace_id: str):
        try:
            content = binding.traces.read(trace_id)
        except (ValueError, FileNotFoundError):
            raise HTTPException(404, "Trace not found") from None
        return Response(
            content,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="{trace_id}.jsonl"'},
        )

    @app.get("/control/snapshot")
    def snapshot():
        with binding.lock, TemporaryDirectory(prefix="opsforge-export-") as directory:
            path = Path(directory) / "episode.sqlite3"
            binding.require().snapshot(path)
            return Response(
                path.read_bytes(),
                media_type="application/vnd.sqlite3",
                headers={
                    "Content-Disposition": 'attachment; filename="episode.sqlite3"'
                },
            )
