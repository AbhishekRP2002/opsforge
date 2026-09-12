"""Run user model/agent callbacks with OpenEnv's harness and rollout records."""

from copy import deepcopy
from dataclasses import asdict
from time import perf_counter
from typing import Any
from uuid import uuid4

from openenv.core.env_server.mcp_types import Tool
from openenv.core.harness import (
    HarnessAdapter,
    HarnessRolloutResult,
    HarnessRunLimits,
    MCPHarnessAdapter,
    Message,
    ModelStep,
    ModelStepResult,
    ResourceSession,
)
from openenv.core.harness.collect import EpisodeRecord, RolloutSerializer

from ..server.core.tracing import record_failure
from .session import ItopsResourceSession, ItopsSessionFactory


class ItopsMCPHarnessAdapter(MCPHarnessAdapter):
    """Use OpenEnv's tool loop and persist each normalized model step."""

    def run_white_box(
        self,
        model_step: ModelStep,
        session: ResourceSession,
        limits: HarnessRunLimits | None = None,
    ) -> HarnessRolloutResult:
        if not isinstance(session, ItopsResourceSession):
            raise TypeError("ItopsMCPHarnessAdapter requires ItopsResourceSession")
        run_limits = limits or HarnessRunLimits()
        if run_limits.max_turns < 1 or (
            run_limits.max_total_tool_calls is not None
            and run_limits.max_total_tool_calls < 1
        ):
            raise ValueError("Harness turn/tool limits must be positive")
        if run_limits.max_tool_calls_per_turn is not None:
            raise ValueError(
                "Use max_total_tool_calls; per-turn clipping can leave unanswered tool calls in OpenEnv 0.4.2"
            )
        session.trace("harness.started", limits=asdict(run_limits))

        def traced_step(
            messages: list[Message], tools: list[Tool], sampling: dict[str, Any]
        ) -> ModelStepResult:
            turn_id = uuid4().hex
            started = perf_counter()
            session.model_turn_id = turn_id
            session.model_tool_calls = []
            session.trace(
                "model.started",
                turn_id=turn_id,
                messages=messages,
                tools=[tool.model_dump(mode="json") for tool in tools],
                sampling=sampling,
            )
            try:
                result = model_step(messages, tools, sampling)
                session.trace(
                    "model.completed",
                    turn_id=turn_id,
                    result=asdict(result),
                    duration_ms=(perf_counter() - started) * 1000,
                )
                session.model_tool_calls = deepcopy(result.response.tool_calls)
                return result
            except BaseException as error:
                record_failure(
                    session.trace,
                    "model.failed",
                    error,
                    turn_id=turn_id,
                    duration_ms=(perf_counter() - started) * 1000,
                )
                raise

        try:
            result = super().run_white_box(traced_step, session, run_limits)
        except BaseException as error:
            record_failure(session.trace, "harness.failed", error)
            raise
        session.trace("harness.completed", done=result.done, metrics=result.metrics)
        return result


def evaluate(
    factory: ItopsSessionFactory,
    *,
    model_step: ModelStep | None = None,
    harness_adapter: HarnessAdapter | None = None,
    limits: HarnessRunLimits | None = None,
    task=None,
    seed: int | None = None,
    episode_id: str | None = None,
    serializer: RolloutSerializer | None = None,
) -> EpisodeRecord:
    """Evaluate one episode, forward its canonical reward, and release ownership."""
    if model_step is None and harness_adapter is None:
        raise ValueError("Provide model_step or a custom harness_adapter")
    adapter = (
        harness_adapter if harness_adapter is not None else ItopsMCPHarnessAdapter()
    )
    session = factory.create(task=task, seed=seed, episode_id=episode_id)
    try:
        rollout = (
            adapter.run_white_box(model_step, session, limits)
            if model_step is not None
            else adapter.run_black_box(session, limits)
        )
        session.trace("evaluation.rollout", rollout=asdict(rollout))
        verify = session.verify(
            rollout.messages,
            final_state={"done": rollout.done, "metrics": rollout.metrics},
        )
        record = EpisodeRecord.from_rollout(
            session.episode_id,
            rollout,
            verify,
            task=task,
            extra={
                "prompt_ids": rollout.prompt_ids,
                "completion_ids": rollout.completion_ids,
                "logprobs": rollout.logprobs,
            },
        )
    except BaseException as error:
        record_failure(session.trace, "evaluation.failed", error)
        try:
            session.close()
        except BaseException as cleanup_error:
            error.add_note(f"Resource session cleanup failed: {cleanup_error}")
            raise error from cleanup_error
        raise
    else:
        session.close()
        if serializer is not None:
            serializer.write_episode(record)
        return record
