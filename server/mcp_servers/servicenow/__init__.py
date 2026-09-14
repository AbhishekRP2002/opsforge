"""Agent-facing ServiceNow tools."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from . import (
    agile,
    catalog,
    changes,
    changesets,
    incidents,
    knowledge,
    optimization,
    scripts,
    users,
    variables,
    workflows,
)


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

    return (
        get_user,
        add_group_members,
        *incidents.register_tools(mcp, dispatch),
        *users.register_tools(mcp, dispatch),
        *scripts.register_tools(mcp, dispatch),
        *changesets.register_tools(mcp, dispatch),
        *workflows.register_tools(mcp, dispatch),
        *changes.register_tools(mcp, dispatch),
        *agile.register_tools(mcp, dispatch),
        *knowledge.register_tools(mcp, dispatch),
        *catalog.register_tools(mcp, dispatch),
        *variables.register_tools(mcp, dispatch),
        *optimization.register_tools(mcp, dispatch),
    )
