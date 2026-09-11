# SPDX-License-Identifier: BSD-3-Clause

"""
Itops Env Environment Implementation.

A simple test environment that echoes back messages sent to it.
Perfect for testing HTTP server infrastructure.
"""

from typing import Any
from uuid import uuid4

from itops_env.models import ItopsAction, ItopsObservation
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State


class ItopsEnvironment(Environment[ItopsAction, ItopsObservation, State]):
    """
    A simple echo environment that echoes back messages.

    This environment is designed for testing the HTTP server infrastructure.
    It maintains minimal state and simply echoes back whatever message it receives.

    Example:
        >>> env = ItopsEnvironment()
        >>> obs = env.reset()
        >>> print(obs.echoed_message)  # "Itops Env environment ready!"
        >>>
        >>> obs = env.step(ItopsAction(message="Hello"))
        >>> print(obs.echoed_message)  # "Hello"
        >>> print(obs.message_length)  # 5
    """

    # Enable concurrent WebSocket sessions.
    # Set to True if your environment isolates state between instances.
    # When True, multiple WebSocket clients can connect simultaneously, each
    # getting their own environment instance (when using factory mode in app.py).
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        """Initialize the itops_env environment."""
        super().__init__()
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._reset_count = 0

    def reset(
        self,
        seed: int | None = None,
        episode_id: str | None = None,
        **kwargs: Any,
    ) -> ItopsObservation:
        """
        Reset the environment.

        Echo behavior is deterministic, so seed does not affect the result.

        Returns:
            ItopsObservation with a ready message
        """
        self._state = State(
            episode_id=episode_id if episode_id is not None else str(uuid4()),
            step_count=0,
        )
        self._reset_count += 1

        return ItopsObservation(
            echoed_message="Itops Env environment ready!",
            message_length=0,
            done=False,
            reward=0.0,
        )

    def step(
        self,
        action: ItopsAction,
        timeout_s: float | None = None,
        **kwargs: Any,
    ) -> ItopsObservation:
        """
        Execute a step in the environment by echoing the message.

        Args:
            action: ItopsAction containing the message to echo

        Returns:
            ItopsObservation with the echoed message and its length
        """
        self._state.step_count += 1

        message = action.message
        length = len(message)

        # Simple reward: longer messages get higher rewards
        reward = length * 0.1

        return ItopsObservation(
            echoed_message=message,
            message_length=length,
            done=False,
            reward=reward,
            metadata={"original_message": message, "step": self._state.step_count},
        )

    @property
    def state(self) -> State:
        """
        Get the current environment state.

        Returns:
            Current State with episode_id and step_count
        """
        return self._state
