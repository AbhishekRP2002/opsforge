"""Typed OpenEnv boundary around one shared episode and one transition lock."""

import sqlite3
from threading import RLock
from typing import Any
from uuid import uuid4

from itops_env.models import ItopsAction, ItopsObservation, ItopsState
from openenv.core.env_server.interfaces import Environment

from .core.episode import Episode
from .core.scenarios import Scenario, load_scenario
from .core.tracing import TraceStore, record_failure
from .rubrics import ItopsOutcomeRubric


class ItopsEnvironment(Environment[ItopsAction, ItopsObservation, ItopsState]):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(
        self, scenario: Scenario | str = "identity-group-v1", lock=None, binding=None
    ):
        super().__init__(rubric=ItopsOutcomeRubric())
        self._scenario = scenario
        self._binding = binding
        self._lock = (
            binding.lock
            if binding is not None
            else (lock if lock is not None else RLock())
        )
        self.episode: Episode | None = None
        self.traces = binding.traces if binding is not None else TraceStore()

    def reset(
        self, seed: int | None = None, episode_id: str | None = None, **kwargs: Any
    ) -> ItopsObservation:
        with self._lock:
            reset_id = uuid4().hex

            def emit(event, **fields):
                self.traces.emit(
                    self.traces.transport_id,
                    event,
                    reset_id=reset_id,
                    episode_trace_id=self.episode.trace_id if self.episode else None,
                    **fields,
                )

            emit(
                "environment.reset_started",
                requested={"seed": seed, "episode_id": episode_id, **kwargs},
            )
            try:
                observation = self._reset(seed=seed, episode_id=episode_id, **kwargs)
            except BaseException as error:
                record_failure(emit, "environment.reset_failed", error)
                raise
            emit("environment.reset_completed")
            return observation

    def _reset(
        self, seed: int | None = None, episode_id: str | None = None, **kwargs: Any
    ) -> ItopsObservation:
        with self._lock:
            if self._binding is not None and self._binding.env not in (None, self):
                raise RuntimeError("Another controller owns the episode")
            if seed is not None and (
                type(seed) is not int or seed < 0 or seed > 2**63 - 1
            ):
                raise ValueError("seed must be an integer in [0, 2**63 - 1]")
            if kwargs:
                raise ValueError(
                    "Reset accepts seed and episode_id only; scenario selection is controller-owned"
                )
            if episode_id is not None and (
                not isinstance(episode_id, str) or not episode_id
            ):
                raise ValueError("episode_id must be a nonempty string")
            scenario = (
                load_scenario(self._scenario)
                if isinstance(self._scenario, str)
                else Scenario.model_validate(self._scenario.model_dump())
            )
            fresh = Episode(
                scenario,
                episode_id or str(uuid4()),
                seed if seed is not None else 0,
                self._lock,
                traces=self.traces,
            )
            try:
                fresh.initialize()
            except BaseException as error:
                try:
                    fresh.close()
                except (sqlite3.Error, OSError) as cleanup_error:
                    error.add_note(
                        f"Failed initialization cleanup failed: {cleanup_error}"
                    )
                raise
            try:
                # Revoke the old identity even if its finalization fails. Do not
                # publish the replacement until the old resources are closed.
                self.close()
            except BaseException as error:
                try:
                    fresh.close()
                except (sqlite3.Error, OSError) as cleanup_error:
                    error.add_note(
                        f"Unpublished replacement cleanup failed: {cleanup_error}"
                    )
                raise
            self.episode = fresh
            self._reset_rubric()
            if self._binding is not None:
                self._binding.bind(self)
            return ItopsObservation(
                instruction=scenario.instruction, policy=scenario.policy
            )

    async def reset_async(
        self, seed: int | None = None, episode_id: str | None = None, **kwargs: Any
    ) -> ItopsObservation:
        try:
            return self.reset(seed=seed, episode_id=episode_id, **kwargs)
        finally:
            if self._binding is not None:
                await self._binding.drain_native()

    def step(
        self, action: ItopsAction, timeout_s: float | None = None, **kwargs: Any
    ) -> ItopsObservation:
        with self._lock:
            if self.episode is None:
                raise RuntimeError("Reset is required before stepping")
            before = self.episode.state.step_count
            observation = self.episode.dispatch(action)
            if self.episode.state.step_count > before:
                assert isinstance(self.rubric, ItopsOutcomeRubric)
                self._apply_rubric(
                    action.model_copy(deep=True), observation.model_copy(deep=True)
                )
                self.episode.trace("rubric.updated", rubric=self.rubric.diagnostics())
            return observation

    async def step_async(
        self, action: ItopsAction, timeout_s: float | None = None, **kwargs: Any
    ) -> ItopsObservation:
        return self.step(action, timeout_s=timeout_s, **kwargs)

    @property
    def state(self) -> ItopsState:
        with self._lock:
            return self.episode.state if self.episode is not None else ItopsState()

    def close(self):
        with self._lock:
            try:
                if self.episode is not None:
                    self.episode.close()
            finally:
                if self._binding is not None and self._binding.env is self:
                    self._binding.env = None
                    self._binding.capability = None
                    self._binding.generation = None
                    self._binding.schedule_native_drain()
