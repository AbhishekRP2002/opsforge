"""Agent-facing ServiceNow tools."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_user(
        user_id: str | None = None,
        user_name: str | None = None,
        email: str | None = None,
    ) -> ToolResult:
        """Get a ServiceNow user using the first nonempty selector.

        Args:
            user_id: User sys_id, checked first.
            user_name: Username, checked after user_id.
            email: Email, checked after user_name.
        """
        return await dispatch(
            "get_user", {"user_id": user_id, "user_name": user_name, "email": email}
        )

    @mcp.tool
    async def add_group_members(group_id: str, members: list[str]) -> ToolResult:
        """Add members to a ServiceNow group, retaining partial business success.

        Args:
            group_id: Group sys_id.
            members: Usernames or emails to add; the alpha preserves literal sys_id: behavior.
        """
        return await dispatch(
            "add_group_members", {"group_id": group_id, "members": members}
        )

    return (get_user, add_group_members)
