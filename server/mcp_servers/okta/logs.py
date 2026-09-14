"""Source-qualified logs declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_logs(
        fetch_all: bool = False,
        after: str | None = None,
        limit: int | None = None,
        since: str | None = None,
        until: str | None = None,
        filter: str | None = None,
        q: str | None = None,
    ) -> ToolResult:
        return await dispatch("get_logs", locals())

    @mcp.tool
    async def get_login_failures(
        since: str | None = None,
        until: str | None = None,
        user_id: str | None = None,
        q: str | None = None,
    ) -> ToolResult:
        return await dispatch("get_login_failures", locals())

    return (get_logs, get_login_failures)
