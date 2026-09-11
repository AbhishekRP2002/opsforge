"""Agent-facing Okta tools; business effects remain in the shared episode."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_user(user_id: str) -> ToolResult:
        """Get an Okta user by their ID or login.

        Args:
            user_id: The Okta user ID or login to retrieve.
        """
        return await dispatch("get_user", {"user_id": user_id})

    return (get_user,)
