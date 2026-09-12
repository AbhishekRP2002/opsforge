"""Native FastMCP tools delegate all business validation to the shared episode."""

import asyncio
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.server.auth import AccessToken, TokenVerifier
from fastmcp.server.http import StreamableHTTPASGIApp
from fastmcp.server.middleware import Middleware
from mcp.server.auth.middleware.bearer_auth import RequireAuthMiddleware
from starlette.routing import Route

from ..interfaces.mcp_bridge import dispatch_native, raw_arguments
from .tools import REGISTRARS, argument_error


class EpisodeVerifier(TokenVerifier):
    def __init__(self, binding):
        super().__init__(required_scopes=["agent"])
        self.binding = binding

    async def verify_token(self, token: str) -> AccessToken | None:
        with self.binding.lock:
            if not self.binding.matches(token):
                return None
            return AccessToken(
                token=token,
                client_id=self.binding.generation,
                subject=self.binding.generation,
                scopes=["agent"],
            )


class AccountInvalidCalls(Middleware):
    def __init__(self, provider, dispatch):
        self.provider, self.dispatch = provider, dispatch

    async def on_call_tool(self, context, call_next):
        arguments = context.message.arguments or {}
        if argument_error(self.provider, context.message.name, arguments):
            return await self.dispatch(context.message.name, arguments)
        token = raw_arguments.set(arguments)
        try:
            return await call_next(context)
        finally:
            raw_arguments.reset(token)


def create_provider_server(binding, provider):
    native = FastMCP(
        provider,
        auth=EpisodeVerifier(binding),
        strict_input_validation=False,
        dereference_schemas=False,
        mask_error_details=True,
    )

    async def dispatch(name, arguments):
        return await dispatch_native(binding, provider, name, arguments)

    REGISTRARS[provider](native, dispatch)
    native.add_middleware(AccountInvalidCalls(provider, dispatch))
    return native


def provider_app(binding, provider):
    native = create_provider_server(binding, provider)
    return native.http_app(
        path="/", transport="streamable-http", stateless_http=False, json_response=True
    )


def bind_native_lifecycle(child, binding):
    """Pinned FastMCP 3.4.7 / SDK 1.30.0 stateful manager lifecycle adapter.

    Install after the child's lifespan creates its manager. Recheck generation
    inside synchronous SDK admission so an earlier auth result cannot outlive a
    reset while waiting for the SDK's session-creation lock.
    """
    route = next(
        route
        for route in child.routes
        if isinstance(route, Route) and route.path == "/"
    )
    endpoint = route.endpoint
    assert isinstance(endpoint, RequireAuthMiddleware)
    transport_app = endpoint.app
    assert isinstance(transport_app, StreamableHTTPASGIApp)
    manager = transport_app.session_manager
    assert manager is not None
    original_admit = manager._admit_session

    def admit(requestor):
        with binding.lock:
            if (
                requestor is None
                or binding.generation is None
                or requestor["subject"] != binding.generation
            ):
                return None
            transport = original_admit(requestor)
            if transport is not None:
                ready = asyncio.Event()
                binding.native_starting[transport] = ready
                original_connect = transport.connect

                @asynccontextmanager
                async def connect():
                    async with original_connect() as streams:
                        ready.set()
                        binding.native_starting.pop(transport, None)
                        yield streams

                transport.connect = connect
            return transport

    original_serve = manager._serve_opening_request

    async def serve(http_transport, scope, receive, send):
        try:
            await original_serve(http_transport, scope, receive, send)
        finally:
            ready = binding.native_starting.pop(http_transport, None)
            if ready is not None:
                ready.set()

    manager._serve_opening_request = serve
    manager._admit_session = admit
    binding.native_managers.append(manager)
