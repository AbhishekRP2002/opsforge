"""Persistent OpenEnv client for the shared provider episode."""

import asyncio
import json
import os
from typing import Any

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_client import _is_localhost_ws_url
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

from .models import ItopsAction, ItopsObservation, ItopsState


class ItopsEnv(EnvClient[ItopsAction, ItopsObservation, ItopsState]):
    def __init__(self, *args, controller_token: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._controller_token = (
            controller_token
            if controller_token is not None
            else os.getenv("OPSFORGE_CONTROLLER_TOKEN")
        )

    def _create_session_client(self):
        client = super()._create_session_client()
        client._controller_token = self._controller_token
        return client

    async def _connect_async(self):
        # OpenEnv 0.4.2 has no header hook; retain its connection lifecycle.
        if self._ws is not None:
            if self._ws_loop is asyncio.get_running_loop():
                return self
            self._ws = None
            self._ws_loop = None
        try:
            self._start_provider_if_needed()
        except Exception:
            await self.close()
            raise
        assert self._ws_url is not None
        options: dict[str, Any] = {}
        if _is_localhost_ws_url(self._ws_url):
            options["proxy"] = None
        if self._controller_token:
            options["additional_headers"] = {
                "Authorization": f"Bearer {self._controller_token}"
            }
        try:
            self._ws = await ws_connect(
                self._ws_url,
                open_timeout=self._connect_timeout,
                max_size=self._max_message_size,
                ping_interval=self._websocket_ping_interval_s,
                ping_timeout=self._websocket_ping_timeout_s,
                **options,
            )
            self._ws_loop = asyncio.get_running_loop()
        except Exception as error:
            await self.close()
            raise ConnectionError(
                f"Failed to connect to {self._ws_url}: {error}"
            ) from error
        return self

    async def _disconnect_async(self) -> None:
        # OpenEnv 0.4.2 destroys the session before sending its close frame.
        # Let the server initiate that frame instead of racing it with ws.close().
        ws, loop = self._ws, self._ws_loop
        self._ws = None
        self._ws_loop = None
        if ws is None or loop is not asyncio.get_running_loop():
            return
        try:
            try:
                await ws.send(json.dumps({"type": "close"}))
            except ConnectionClosed:
                await ws.wait_closed()
                return
            try:
                await asyncio.wait_for(ws.wait_closed(), timeout=self._connect_timeout)
            except TimeoutError:
                # A stalled server must not keep controller cleanup unbounded.
                await ws.close()
        finally:
            await ws.close()

    def _step_payload(self, action: ItopsAction) -> dict:
        return action.model_dump()

    def _parse_result(self, payload: dict) -> StepResult[ItopsObservation]:
        observation = ItopsObservation.model_validate(
            payload.get("observation", {})
            | {
                "done": payload.get("done", False),
                "reward": payload.get("reward", 0.0),
            }
        )
        return StepResult(
            observation=observation,
            reward=observation.reward,
            done=observation.done,
            metadata=payload.get("metadata"),
        )

    def _parse_state(self, payload: dict) -> ItopsState:
        return ItopsState.model_validate(payload)
