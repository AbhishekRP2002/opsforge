"""Episode wait and explicit submission tools."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field, StrictInt


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def workflow_wait(seconds: Annotated[StrictInt, Field(ge=0)]) -> ToolResult:
        """Advance the episode's simulated clock.

        Args:
            seconds: Nonnegative integer number of simulated seconds to wait.
        """
        return await dispatch("workflow_wait", {"seconds": seconds})

    @mcp.tool
    async def workflow_submit(
        disposition: str, user_id: str, group_id: str, summary: str = ""
    ) -> ToolResult:
        """Submit the task for final verification.

        Args:
            disposition: Use completed when the requested work is finished.
            user_id: ServiceNow user sys_id.
            group_id: ServiceNow group sys_id.
            summary: Optional explanation; database effects determine the score.
        """
        return await dispatch(
            "workflow_submit",
            {
                "disposition": disposition,
                "user_id": user_id,
                "group_id": group_id,
                "summary": summary,
            },
        )

    return (workflow_wait, workflow_submit)
