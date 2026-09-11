"""Public OpenEnv boundary; trusted grading evidence stays in the episode."""

from typing import Any, Literal
from uuid import uuid4

from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field


class ItopsAction(Action):
    provider: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    invocation_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)


class ItopsObservation(Observation):
    content: list[dict[str, Any]] = Field(default_factory=list)
    structured_content: dict[str, Any] | None = None
    is_error: bool = False
    instruction: str | None = None
    policy: str | None = None
    reward: float = 0.0


class ItopsState(State):
    phase: Literal["uninitialized", "active", "terminal", "closed"] = "uninitialized"
    simulated_clock: int = 0
    remaining_budget: int = 0
