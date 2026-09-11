# SPDX-License-Identifier: BSD-3-Clause

"""
Data models for the Itops Env Environment.

The itops_env environment is a simple test environment that echoes back messages.
"""

from openenv.core.env_server.types import Action, Observation
from pydantic import Field


class ItopsAction(Action):
    """Action for the Itops Env environment - just a message to echo."""

    message: str = Field(..., description="Message to echo back")


class ItopsObservation(Observation):
    """Observation from the Itops Env environment - the echoed message."""

    echoed_message: str = Field(default="", description="The echoed message")
    message_length: int = Field(default=0, description="Length of the echoed message")
