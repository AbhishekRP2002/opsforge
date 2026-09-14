"""Source-qualified public application declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_applications(
        q: str | None = None,
        after: str | None = None,
        limit: int | None = None,
        filter: str | None = None,
        expand: str | None = None,
        include_non_deleted: bool | None = None,
        fetch_all: bool = False,
    ) -> ToolResult:
        return await dispatch("list_applications", locals())

    @mcp.tool
    async def get_application(app_id: str, expand: str | None = None) -> ToolResult:
        return await dispatch("get_application", locals())

    @mcp.tool
    async def create_application(app_config: dict, activate: bool = True) -> ToolResult:
        return await dispatch("create_application", locals())

    @mcp.tool
    async def update_application(app_id: str, app_config: dict) -> ToolResult:
        return await dispatch("update_application", locals())

    @mcp.tool
    async def delete_application(app_id: str) -> ToolResult:
        return await dispatch("delete_application", locals())

    @mcp.tool
    async def confirm_delete_application(app_id: str, confirmation: str) -> ToolResult:
        return await dispatch("confirm_delete_application", locals())

    @mcp.tool
    async def activate_application(app_id: str) -> ToolResult:
        return await dispatch("activate_application", locals())

    @mcp.tool
    async def deactivate_application(app_id: str) -> ToolResult:
        return await dispatch("deactivate_application", locals())

    @mcp.tool
    async def list_catalog_apps(
        q: str | None = None,
        after: str | None = None,
        limit: int | None = None,
        fetch_all: bool = False,
    ) -> ToolResult:
        return await dispatch("list_catalog_apps", locals())

    @mcp.tool
    async def get_catalog_app(app_name: str) -> ToolResult:
        return await dispatch("get_catalog_app", locals())

    @mcp.tool
    async def install_oin_app(
        name: str,
        label: str,
        sign_on_mode: str,
        settings: dict | None = None,
        activate: bool = True,
    ) -> ToolResult:
        return await dispatch("install_oin_app", locals())

    return (
        list_applications,
        get_application,
        create_application,
        update_application,
        delete_application,
        confirm_delete_application,
        activate_application,
        deactivate_application,
        list_catalog_apps,
        get_catalog_app,
        install_oin_app,
    )
