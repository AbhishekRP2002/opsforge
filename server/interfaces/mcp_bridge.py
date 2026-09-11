"""Native invocation identity and pre-SDK duplicate admission guard."""

import asyncio
import json
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token, get_context
from fastmcp.tools import ToolResult
from itops_env.models import ItopsAction
from mcp.types import TextContent
from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from ..core.tracing import call_context, record_failure

raw_arguments: ContextVar[dict | None] = ContextVar("raw_tool_arguments", default=None)


async def dispatch_native(binding, provider, name, arguments):
    token = get_access_token()
    context = get_context().request_context
    if token is None or context is None or context.request is None:
        raise ToolError("Authenticated native request required")
    session = context.request.headers.get("mcp-session-id")
    if not session:
        raise ToolError("Validated native session required")
    with binding.lock:
        if not binding.matches(token.token) or binding.env is None:
            raise ToolError("Episode capability expired")
        request_id = context.request_id
        invocation_id = json.dumps(
            [
                binding.generation,
                provider,
                session,
                type(request_id).__name__,
                request_id,
            ],
            separators=(",", ":"),
        )
        supplied_arguments = raw_arguments.get()
        trace_context = call_context.set(
            {
                "transport": "mcp",
                "request_id": context.request.scope.get("state", {}).get(
                    "opsforge_request_id"
                ),
                "transport_trace_id": binding.traces.transport_id,
                "jsonrpc_id": request_id,
                "provider": provider,
            }
        )
        try:
            observation = await binding.env.step_async(
                ItopsAction(
                    provider=provider,
                    tool_name=name,
                    arguments=supplied_arguments
                    if supplied_arguments is not None
                    else arguments,
                    invocation_id=invocation_id,
                )
            )
        finally:
            call_context.reset(trace_context)
        return ToolResult(
            content=[
                TextContent.model_validate(block) for block in observation.content
            ],
            structured_content=observation.structured_content,
            is_error=observation.is_error,
        )


class DuplicateRequestGuard:
    """Reject overlapping wire IDs before SDK maps can overwrite a stream.

    Only current authenticated capabilities enter the guard. The SDK subsequently
    validates session ownership. No response cache or business validation lives here.
    """

    def __init__(self, app, binding, provider, max_body=1024 * 1024):
        self.app, self.binding, self.provider, self.max_body = (
            app,
            binding,
            provider,
            max_body,
        )
        self.inflight = set()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = perf_counter()
        request_id = uuid4().hex
        scope.setdefault("state", {})["opsforge_request_id"] = request_id
        with self.binding.lock:
            episode = self.binding.env.episode if self.binding.env is not None else None
            episode_trace_id = episode.trace_id if episode else None

        def emit(event, **fields):
            self.binding.traces.emit(
                self.binding.traces.transport_id,
                event,
                request_id=request_id,
                episode_trace_id=episode_trace_id,
                provider=self.provider,
                **fields,
            )

        emit("mcp.request_started", method=scope["method"], path=scope["path"])
        status = None
        response_body = bytearray()
        response_size = 0

        async def observe(message):
            nonlocal status, response_size
            if message["type"] == "http.response.start":
                status = message["status"]
                emit("mcp.response_started", status=status)
            elif message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                response_size += len(chunk)
                if len(response_body) < self.max_body:
                    response_body.extend(chunk[: self.max_body - len(response_body)])
            await send(message)

        try:
            await self._handle(scope, receive, observe, emit)
        except BaseException as error:
            record_failure(
                emit,
                "mcp.request_failed",
                error,
                status=status,
                duration_ms=(perf_counter() - started) * 1000,
            )
            raise
        envelope = None
        response_format = "empty" if not response_body else "truncated"
        if response_size <= self.max_body and response_body:
            try:
                envelope = json.loads(response_body)
            except (ValueError, UnicodeDecodeError):
                response_format = "non_json"  # Includes SSE; preserve status and size.
            else:
                response_format = "json"
        emit(
            "mcp.request_completed",
            status=status,
            duration_ms=(perf_counter() - started) * 1000,
            response_bytes=response_size,
            response_truncated=response_size > self.max_body,
            response_format=response_format,
            envelope=envelope,
        )

    async def _handle(self, scope, receive, send, emit):
        headers = Headers(scope=scope) if scope["type"] == "http" else None
        token = (
            headers.get("authorization", "").removeprefix("Bearer ") if headers else ""
        )
        if (
            scope["type"] != "http"
            or scope["method"] != "POST"
            or not self.binding.matches(token)
        ):
            await self.app(scope, receive, send)
            return
        assert headers is not None
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self.max_body:
                emit(
                    "mcp.request_rejected",
                    reason="body_too_large",
                    received_bytes=len(body),
                )
                await JSONResponse(
                    {"detail": "Request body too large"}, status_code=413
                )(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        try:
            envelope = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            envelope = None  # Replay invalid JSON to the SDK's protocol validator.
        emit("mcp.request_received", envelope=envelope, invalid_json=envelope is None)
        key = None
        if (
            isinstance(envelope, dict)
            and type(envelope.get("id")) in (int, str)
            and headers.get("mcp-session-id")
        ):
            key = (self.provider, headers["mcp-session-id"], str(envelope["id"]))
        if key is not None and key in self.inflight:
            await JSONResponse(
                {"detail": "Request ID already in flight; retry after completion"},
                status_code=409,
                headers={"Retry-After": "1"},
            )(scope, receive, send)
            return
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        if key is not None:
            self.inflight.add(key)
        pending = asyncio.create_task(self.app(scope, replay, send))
        try:
            try:
                await asyncio.shield(pending)
            except asyncio.CancelledError:
                # Keep the wire ID reserved until SDK response cleanup finishes.
                await pending
                raise
        finally:
            if key is not None:
                self.inflight.remove(key)
