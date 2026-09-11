"""Single-writer episode transitions shared by all transports."""

import json
import sqlite3
from pathlib import Path
from threading import RLock
from time import perf_counter
from uuid import uuid4

from itops_env.models import ItopsAction, ItopsObservation, ItopsState

from ..mcp_servers.tools import argument_error
from ..services import okta, servicenow
from ..storage.database import Database
from .events import advance
from .grading import EpisodeResult, ResultMetrics, grade
from .scenarios import Scenario
from .tracing import TraceStore, call_context, record_failure


def response(value, *, error=False, provider=None, done=False, reward=0.0):
    return ItopsObservation(
        content=[
            {
                "type": "text",
                "text": json.dumps(
                    value, indent=2 if provider == "servicenow" else None
                ),
            }
        ],
        is_error=error,
        done=done,
        reward=reward,
    )


class Episode:
    def __init__(
        self,
        scenario: Scenario,
        episode_id: str,
        seed: int,
        lock=None,
        traces: TraceStore | None = None,
    ):
        self.scenario = scenario
        self.episode_id = episode_id
        self.seed = seed
        self._lock = lock if lock is not None else RLock()
        self._db: Database | None = None
        self._state = ItopsState(episode_id=episode_id)
        self._result: EpisodeResult | None = None
        self.traces = traces if traces is not None else TraceStore()
        self.trace_id = uuid4().hex

    def trace(self, event: str, **fields) -> None:
        self.traces.emit(
            self.trace_id,
            event,
            episode_id=self.episode_id,
            state=self._state.model_dump(mode="json"),
            result=self._result.model_dump(mode="json") if self._result else None,
            **fields,
        )

    @property
    def db(self) -> Database:
        if self._db is None or not self._db.is_open:
            raise RuntimeError("Episode is not open")
        return self._db

    def initialize(self) -> None:
        with self._lock:
            if self._db is not None:
                raise RuntimeError("Episode already initialized")
            self.trace(
                "episode.initializing",
                seed=self.seed,
                scenario=self.scenario.model_dump(mode="json"),
            )
            try:
                self._db = Database.create(self.scenario, self.episode_id, self.seed)
                with self.db.connection:
                    advance(self.db, 0)
                self._state = ItopsState(
                    episode_id=self.episode_id,
                    phase="active",
                    remaining_budget=self.scenario.step_budget,
                )
                self.trace("episode.ready")
            except BaseException as error:
                record_failure(self.trace, "episode.initialize_failed", error)
                raise

    @property
    def state(self) -> ItopsState:
        with self._lock:
            return self._state.model_copy(deep=True)

    def result(self) -> EpisodeResult | None:
        with self._lock:
            return self._result

    def _save_state(self) -> None:
        for key, value in {
            "clock": self._state.simulated_clock,
            "step_count": self._state.step_count,
            "phase": self._state.phase,
        }.items():
            self.db.connection.execute(
                "UPDATE metadata SET value = ? WHERE key = ?", (json.dumps(value), key)
            )

    def _freeze(self, reason: str, submission: dict | None = None) -> EpisodeResult:
        if self._result is None:
            self._result = grade(
                self.db,
                self.scenario,
                self.episode_id,
                self._state.step_count,
                self._state.simulated_clock,
                reason,
                submission,
            )
            self.db.connection.execute(
                "INSERT INTO result VALUES (1, ?)", (self._result.model_dump_json(),)
            )
            self._state.phase = "terminal"
            self._save_state()
        return self._result

    def _infrastructure_failure(self, exception: sqlite3.Error) -> None:
        self._state.phase = "terminal"
        self._result = EpisodeResult(
            episode_id=self.episode_id,
            status="infrastructure_error",
            terminal_reason="infrastructure_error",
            reward=0,
            scenario_version=self.scenario.version,
            policy_version=self.scenario.policy_version,
            metrics=ResultMetrics(
                steps=self._state.step_count,
                simulated_clock=self._state.simulated_clock,
                membership_count=None,
                effect_count=None,
            ),
            evidence=None,
        )
        try:
            with self.db.connection:
                self.db.connection.execute(
                    "INSERT INTO result VALUES (1, ?)",
                    (self._result.model_dump_json(),),
                )
                self._save_state()
        except sqlite3.Error as persistence_error:
            # The immutable in-memory artifact remains authoritative if storage is unavailable.
            exception.add_note(
                f"Infrastructure result could not be persisted: {persistence_error}"
            )

    def dispatch(self, action: ItopsAction) -> ItopsObservation:
        with self._lock:
            started = perf_counter()
            attempt_id = uuid4().hex
            self.trace(
                "tool.started",
                attempt_id=attempt_id,
                action=action.model_dump(),
                context=call_context.get() or {"transport": "openenv_or_direct"},
            )
            previous_result = self._result
            try:
                observation, outcome, committed = self._dispatch(action)
            except BaseException as error:
                record_failure(
                    self.trace,
                    "tool.failed",
                    error,
                    attempt_id=attempt_id,
                    duration_ms=(perf_counter() - started) * 1000,
                )
                raise
            self.trace(
                "tool.completed",
                attempt_id=attempt_id,
                outcome=outcome,
                committed=committed,
                observation=observation.model_dump(mode="json"),
                duration_ms=(perf_counter() - started) * 1000,
            )
            if previous_result is None and self._result is not None:
                self.trace(
                    "episode.finalized",
                    attempt_id=attempt_id,
                    reason=self._result.terminal_reason,
                )
            return observation

    def _dispatch(self, action: ItopsAction) -> tuple[ItopsObservation, str, dict]:
        with self._lock:
            if self._db is None or not self._db.is_open:
                raise RuntimeError("Episode is not open")
            payload = json.dumps(
                {
                    "provider": action.provider,
                    "tool_name": action.tool_name,
                    "arguments": action.arguments,
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            before = self._state.model_copy(deep=True)
            previous_result = self._result
            try:
                cached = self.db.connection.execute(
                    "SELECT * FROM delivery WHERE invocation_id = ?",
                    (action.invocation_id,),
                ).fetchone()
                if cached is not None and cached["payload"] == payload:
                    replay = ItopsObservation.model_validate_json(cached["response"])
                    return (
                        replay.model_copy(
                            update={
                                "reward": 0.0,
                                "done": self._state.phase == "terminal" or replay.done,
                            }
                        ),
                        "replayed",
                        {},
                    )
                if self._state.phase == "terminal":
                    return (
                        response(
                            {"error": "Episode is terminal"}, error=True, done=True
                        ),
                        "terminal_rejected",
                        {},
                    )
                with self.db.connection:
                    observation, outcome = self._transition(
                        action, conflict=cached is not None
                    )
                    self._save_state()
                    if cached is None:
                        self.db.connection.execute(
                            "INSERT INTO delivery VALUES (?, ?, ?)",
                            (
                                action.invocation_id,
                                payload,
                                observation.model_dump_json(),
                            ),
                        )
                    committed = {
                        "journal": [
                            dict(row)
                            for row in self.db.connection.execute(
                                "SELECT * FROM journal WHERE step = ? ORDER BY sequence",
                                (self._state.step_count,),
                            )
                        ],
                        "events": [
                            dict(row)
                            for row in self.db.connection.execute(
                                "SELECT * FROM events WHERE applied = 1 AND at > ? AND at <= ? ORDER BY at, sequence",
                                (before.simulated_clock, self._state.simulated_clock),
                            )
                        ],
                    }
                return observation, outcome, committed
            except sqlite3.Error as exception:
                self._state = before
                self._result = previous_result
                if self._result is None:
                    self._infrastructure_failure(exception)
                raise

    def _transition(
        self, action: ItopsAction, conflict: bool
    ) -> tuple[ItopsObservation, str]:
        error = "Invocation ID conflicts with an earlier payload" if conflict else None
        if not error:
            error = argument_error(action.provider, action.tool_name, action.arguments)
        key = f"{action.provider}.{action.tool_name}"
        duration = self.scenario.costs.get(key, self.scenario.costs["invalid"])
        if error:
            duration = self.scenario.costs["invalid"]
        elif key == "benchmark.workflow_wait":
            duration = action.arguments["seconds"]
        self._state.step_count += 1
        self._state.remaining_budget -= 1
        end = self._state.simulated_clock + duration
        self._state.simulated_clock = min(end, self.scenario.horizon)
        advance(self.db, self._state.simulated_clock)
        if end > self.scenario.horizon:
            self._freeze("horizon")
            return response(
                {"error": "Action exceeds the episode horizon"}, error=True, done=True
            ), "horizon"
        self.db.record(
            self._state.step_count,
            self._state.simulated_clock,
            "action",
            action.provider,
            action.tool_name,
        )
        if error:
            observation = response({"error": error}, error=True)
        elif key == "benchmark.workflow_submit":
            result = self._freeze("submitted", action.arguments)
            observation = response({"submitted": True}, done=True, reward=result.reward)
        elif key == "benchmark.workflow_wait":
            observation = response(
                {
                    "waited_seconds": duration,
                    "simulated_clock": self._state.simulated_clock,
                }
            )
        else:
            service = {
                "okta.get_user": okta.get_user,
                "servicenow.get_user": servicenow.get_user,
                "servicenow.add_group_members": servicenow.add_group_members,
            }[key]
            value, is_error = service(
                self.db,
                action.arguments,
                self._state.step_count,
                self._state.simulated_clock,
            )
            observation = response(value, error=is_error, provider=action.provider)
        if self._state.remaining_budget == 0 and self._result is None:
            self._freeze("step_budget")
            observation.done = True
        return (
            observation,
            "conflict" if conflict else "rejected" if error else "executed",
        )

    def finalize(self, reason: str = "abandoned") -> EpisodeResult:
        with self._lock:
            if self._result is not None:
                return self._result
            if self._db is None or not self._db.is_open:
                raise RuntimeError("Episode is not open")
            before = self._state.model_copy(deep=True)
            self.trace("episode.finalizing", reason=reason)
            try:
                with self.db.connection:
                    result = self._freeze(reason)
            except sqlite3.Error as exception:
                self._state = before
                self._result = None
                self._infrastructure_failure(exception)
                record_failure(self.trace, "episode.finalize_failed", exception)
                raise
            self.trace("episode.finalized", reason=reason)
            return result

    def snapshot(self, destination: Path) -> None:
        with self._lock:
            if self._db is None or not self._db.is_open:
                raise RuntimeError("Episode is not open")
            self.db.snapshot(destination)

    def close(self) -> None:
        with self._lock:
            if self._db is not None and self._db.is_open:
                try:
                    self.finalize()
                except BaseException as error:
                    try:
                        self._close_storage()
                    except (sqlite3.Error, OSError) as cleanup_error:
                        error.add_note(f"Episode cleanup failed: {cleanup_error}")
                    raise
                else:
                    self._close_storage()

    def _close_storage(self) -> None:
        self.db.close()
        self._state.phase = "closed"
        self.trace("episode.closed")
