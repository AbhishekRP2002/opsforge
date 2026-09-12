"""Expose one controller-owned simulation as an OpenEnv ResourceSession."""

import os
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from openenv.core.env_server.mcp_types import Tool
from openenv.core.harness import (
    Message,
    ResourceSession,
    ResourceSessionFactory,
    ToolResult,
    VerifyResult,
)
from openenv.core.llm_client import ToolCall
from openenv.core.sync_client import SyncEnvClient

from ..client import ItopsEnv
from ..models import ItopsAction, ItopsObservation, ItopsState
from ..server.core.tracing import TraceStore, record_failure
from ..server.mcp_servers.tools import REGISTRARS, tool_definitions


class ItopsResourceSession(ResourceSession):
    def __init__(
        self,
        base_url: str,
        controller_token: str,
        *,
        task: Any = None,
        seed: int | None = None,
        episode_id: str | None = None,
        trace_dir: Path | None = None,
    ) -> None:
        self.episode_id = str(uuid4()) if episode_id is None else episode_id
        self.traces = TraceStore(trace_dir)
        self.trace_id = uuid4().hex
        self.model_turn_id: str | None = None
        self.model_tool_calls: list[ToolCall] = []
        self._closed = False
        self._stack = ExitStack()
        self.trace("session.initializing", task=task, seed=seed)
        try:
            self._http = self._stack.enter_context(
                httpx.Client(
                    base_url=base_url,
                    headers={"Authorization": f"Bearer {controller_token}"},
                    timeout=30,
                )
            )
            self._client: SyncEnvClient[ItopsAction, ItopsObservation, ItopsState] = (
                ItopsEnv(base_url=base_url, controller_token=controller_token).sync()
            )
            self._stack.callback(self._client.close)
            initial = self._client.reset(seed=seed, episode_id=self.episode_id)
            self._messages: list[Message] = [
                {"role": "system", "content": initial.observation.policy},
                {"role": "user", "content": initial.observation.instruction},
            ]
            self._tools = [
                Tool(
                    name=f"{provider}__{tool.name}",
                    description=tool.description or "",
                    input_schema=deepcopy(tool.parameters),
                )
                for provider in REGISTRARS
                for tool in tool_definitions(provider).values()
            ]
            self.trace("session.ready", messages=self._messages)
        except BaseException as error:
            record_failure(self.trace, "session.initialize_failed", error)
            try:
                self.close()
            except BaseException as cleanup_error:
                error.add_note(f"Resource session cleanup failed: {cleanup_error}")
                raise error from cleanup_error
            raise

    def trace(self, event: str, **fields) -> None:
        self.traces.emit(self.trace_id, event, episode_id=self.episode_id, **fields)

    def initial_messages(self) -> list[Message]:
        return deepcopy(self._messages)

    def list_tools(self) -> list[Tool]:
        return [tool.model_copy(deep=True) for tool in self._tools]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if self._closed:
            raise RuntimeError("Resource session is closed")
        attempt_id = uuid4().hex
        provider, separator, tool_name = name.partition("__")
        if not separator:
            provider, tool_name = "unknown", name
        tool_call_id = None
        if self.model_tool_calls:
            candidate = self.model_tool_calls[0]
            if candidate.name == name and candidate.args == arguments:
                tool_call_id = self.model_tool_calls.pop(0).id
        correlation = {
            "harness_trace_id": self.trace_id,
            "model_turn_id": self.model_turn_id,
            "model_tool_call_id": tool_call_id,
        }
        started = perf_counter()
        self.trace(
            "harness.tool_started",
            attempt_id=attempt_id,
            name=name,
            arguments=arguments,
            **correlation,
        )
        try:
            result = self._client.step(
                ItopsAction(
                    provider=provider,
                    tool_name=tool_name,
                    arguments=arguments,
                    invocation_id=attempt_id,
                    metadata=correlation,
                )
            )
            observation = result.observation
            data: dict[str, Any] = {
                "content": observation.content,
                "isError": observation.is_error,
            }
            if observation.structured_content is not None:
                data["structuredContent"] = observation.structured_content
            output = ToolResult(
                data=data,
                done=result.done,
                metadata={"reward": result.reward, "invocation_id": attempt_id},
                error=observation.content[0]["text"] if observation.is_error else None,
            )
            self.trace(
                "harness.tool_completed",
                attempt_id=attempt_id,
                result={
                    "data": output.data,
                    "done": output.done,
                    "metadata": output.metadata,
                    "error": output.error,
                },
                duration_ms=(perf_counter() - started) * 1000,
            )
            return output
        except BaseException as error:
            record_failure(
                self.trace,
                "harness.tool_failed",
                error,
                attempt_id=attempt_id,
                duration_ms=(perf_counter() - started) * 1000,
            )
            raise

    def verify(
        self, transcript: list[Message], final_state: Any = None
    ) -> VerifyResult:
        if self._closed:
            raise RuntimeError("Resource session is closed")
        response = self._http.post("/control/finalize")
        response.raise_for_status()
        payload = response.json()
        result = payload["result"]
        self.trace(
            "session.verified",
            result=result,
            rubric=payload["rubric"],
            transcript_length=len(transcript),
        )
        if result["status"] == "infrastructure_error":
            raise RuntimeError(
                "Environment infrastructure error; rollout is not scored"
            )
        return VerifyResult(
            env_reward=result["reward"],
            done=True,
            metrics=result["metrics"]
            | {
                "status": result["status"],
                "terminal_reason": result["terminal_reason"],
            },
            artifacts={
                "environment_result": result,
                "environment_trace_id": payload["trace_id"],
                "transport_trace_id": payload["transport_trace_id"],
                "harness_trace_id": self.trace_id,
                "harness_trace_path": str(self.traces.path(self.trace_id)),
                "rubric": payload["rubric"],
            },
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._stack.close()
        except BaseException as error:
            record_failure(self.trace, "session.close_failed", error)
            raise
        self.trace("session.closed")


class ItopsSessionFactory(ResourceSessionFactory[ItopsResourceSession]):
    def __init__(
        self,
        base_url: str,
        controller_token: str | None = None,
        trace_dir: Path | None = None,
    ):
        self.base_url = base_url
        token = (
            controller_token
            if controller_token is not None
            else os.getenv("OPSFORGE_CONTROLLER_TOKEN")
        )
        if not token:
            raise ValueError("Set OPSFORGE_CONTROLLER_TOKEN or pass controller_token")
        self.controller_token = token
        self.trace_dir = trace_dir

    def create(
        self, task: Any = None, seed: int | None = None, episode_id: str | None = None
    ) -> ItopsResourceSession:
        if task is not None and task != "identity-group-v1":
            raise ValueError("Unknown task; use identity-group-v1 or None")
        return ItopsResourceSession(
            self.base_url,
            self.controller_token,
            task=task,
            seed=seed,
            episode_id=episode_id,
            trace_dir=self.trace_dir,
        )
