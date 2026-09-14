"""Agent-facing Okta identity tools; all effects dispatch through Episode."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult

from . import (
    applications,
    customization,
    devices,
    logs,
    pages,
    policies,
    templates,
    themes,
)


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_users(
        search: str = "",
        filter: str | None = None,
        q: str | None = None,
        fetch_all: bool = False,
        after: str | None = None,
        limit: int | None = None,
    ) -> ToolResult:
        return await dispatch("list_users", locals())

    @mcp.tool
    async def get_user_profile_attributes() -> ToolResult:
        return await dispatch("get_user_profile_attributes", {})

    @mcp.tool
    async def get_user(user_id: str) -> ToolResult:
        """Get an Okta user by ID or login."""
        return await dispatch("get_user", {"user_id": user_id})

    @mcp.tool
    async def create_user(profile: dict, activate: bool = True) -> ToolResult:
        return await dispatch("create_user", locals())

    @mcp.tool
    async def update_user(user_id: str, profile: dict) -> ToolResult:
        return await dispatch("update_user", locals())

    @mcp.tool
    async def deactivate_user(user_id: str) -> ToolResult:
        """Headless simulation deactivates immediately; elicitation is not advertised."""
        return await dispatch("deactivate_user", locals())

    @mcp.tool
    async def delete_deactivated_user(user_id: str) -> ToolResult:
        """Headless simulation deletes a DEPROVISIONED user immediately."""
        return await dispatch("delete_deactivated_user", locals())

    @mcp.tool
    async def export_users_csv(
        output_path: str = "/tmp/okta_users_export.csv",
        search: str = "",
        filter: str | None = None,
        q: str | None = None,
    ) -> ToolResult:
        """Persist a bounded CSV as an episode-owned artifact."""
        return await dispatch("export_users_csv", locals())

    @mcp.tool
    async def list_groups(
        search: str = "",
        filter: str | None = None,
        q: str | None = None,
        fetch_all: bool = False,
        after: str | None = None,
        limit: int | None = None,
    ) -> ToolResult:
        return await dispatch("list_groups", locals())

    @mcp.tool
    async def get_group(group_id: str) -> ToolResult:
        return await dispatch("get_group", locals())

    @mcp.tool
    async def create_group(profile: dict) -> ToolResult:
        return await dispatch("create_group", locals())

    @mcp.tool
    async def delete_group(group_id: str) -> ToolResult:
        """Request explicit confirmation without deleting."""
        return await dispatch("delete_group", locals())

    @mcp.tool
    async def confirm_delete_group(group_id: str, confirmation: str) -> ToolResult:
        """Delete only after explicit human confirmation passed exactly as DELETE."""
        return await dispatch("confirm_delete_group", locals())

    @mcp.tool
    async def update_group(group_id: str, profile: dict) -> ToolResult:
        """Replace the complete group profile."""
        return await dispatch("update_group", locals())

    @mcp.tool
    async def list_group_users(
        group_id: str,
        fetch_all: bool = False,
        after: str | None = None,
        limit: int | None = None,
    ) -> ToolResult:
        return await dispatch("list_group_users", locals())

    @mcp.tool
    async def list_group_apps(
        group_id: str,
        after: str | None = None,
        limit: int | None = None,
        fetch_all: bool = False,
    ) -> ToolResult:
        return await dispatch("list_group_apps", locals())

    @mcp.tool
    async def add_user_to_group(group_id: str, user_id: str) -> ToolResult:
        return await dispatch("add_user_to_group", locals())

    @mcp.tool
    async def remove_user_from_group(group_id: str, user_id: str) -> ToolResult:
        return await dispatch("remove_user_from_group", locals())

    @mcp.tool
    async def list_user_groups(user_id: str) -> ToolResult:
        return await dispatch("list_user_groups", locals())

    return (
        applications.register_tools(mcp, dispatch)
        + policies.register_tools(mcp, dispatch)
        + customization.register_tools(mcp, dispatch)
        + themes.register_tools(mcp, dispatch)
        + pages.register_tools(mcp, dispatch)
        + templates.register_tools(mcp, dispatch)
        + devices.register_tools(mcp, dispatch)
        + logs.register_tools(mcp, dispatch)
        + (
            list_users,
            get_user_profile_attributes,
            get_user,
            create_user,
            update_user,
            deactivate_user,
            delete_deactivated_user,
            export_users_csv,
            list_groups,
            get_group,
            create_group,
            delete_group,
            confirm_delete_group,
            update_group,
            list_group_users,
            list_group_apps,
            add_user_to_group,
            remove_user_from_group,
            list_user_groups,
        )
    )
