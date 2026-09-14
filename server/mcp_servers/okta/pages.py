"""Source-qualified hosted-page declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_error_page_resources(
        brand_id: str, expand: list[str] | None = None
    ) -> ToolResult:
        return await dispatch("get_error_page_resources", locals())

    @mcp.tool
    async def get_customized_error_page(brand_id: str) -> ToolResult:
        return await dispatch("get_customized_error_page", locals())

    @mcp.tool
    async def replace_customized_error_page(
        brand_id: str,
        page_content: str | None = None,
        csp_mode: str | None = None,
        csp_report_uri: str | None = None,
        csp_src_list: list[str] | None = None,
    ) -> ToolResult:
        return await dispatch("replace_customized_error_page", locals())

    @mcp.tool
    async def delete_customized_error_page(brand_id: str) -> ToolResult:
        return await dispatch("delete_customized_error_page", locals())

    @mcp.tool
    async def get_default_error_page(brand_id: str) -> ToolResult:
        return await dispatch("get_default_error_page", locals())

    @mcp.tool
    async def get_preview_error_page(brand_id: str) -> ToolResult:
        return await dispatch("get_preview_error_page", locals())

    @mcp.tool
    async def replace_preview_error_page(
        brand_id: str,
        page_content: str | None = None,
        csp_mode: str | None = None,
        csp_report_uri: str | None = None,
        csp_src_list: list[str] | None = None,
    ) -> ToolResult:
        return await dispatch("replace_preview_error_page", locals())

    @mcp.tool
    async def delete_preview_error_page(brand_id: str) -> ToolResult:
        return await dispatch("delete_preview_error_page", locals())

    @mcp.tool
    async def get_sign_in_page_resources(
        brand_id: str, expand: list[str] | None = None
    ) -> ToolResult:
        return await dispatch("get_sign_in_page_resources", locals())

    @mcp.tool
    async def get_customized_sign_in_page(brand_id: str) -> ToolResult:
        return await dispatch("get_customized_sign_in_page", locals())

    @mcp.tool
    async def replace_customized_sign_in_page(
        brand_id: str,
        page_content: str | None = None,
        widget_version: str | None = None,
        widget_customizations: dict | None = None,
        csp_mode: str | None = None,
        csp_report_uri: str | None = None,
        csp_src_list: list[str] | None = None,
    ) -> ToolResult:
        return await dispatch("replace_customized_sign_in_page", locals())

    @mcp.tool
    async def delete_customized_sign_in_page(brand_id: str) -> ToolResult:
        return await dispatch("delete_customized_sign_in_page", locals())

    @mcp.tool
    async def get_default_sign_in_page(brand_id: str) -> ToolResult:
        return await dispatch("get_default_sign_in_page", locals())

    @mcp.tool
    async def get_preview_sign_in_page(brand_id: str) -> ToolResult:
        return await dispatch("get_preview_sign_in_page", locals())

    @mcp.tool
    async def replace_preview_sign_in_page(
        brand_id: str,
        page_content: str | None = None,
        widget_version: str | None = None,
        widget_customizations: dict | None = None,
        csp_mode: str | None = None,
        csp_report_uri: str | None = None,
        csp_src_list: list[str] | None = None,
    ) -> ToolResult:
        return await dispatch("replace_preview_sign_in_page", locals())

    @mcp.tool
    async def delete_preview_sign_in_page(brand_id: str) -> ToolResult:
        return await dispatch("delete_preview_sign_in_page", locals())

    @mcp.tool
    async def list_sign_in_widget_versions(brand_id: str) -> ToolResult:
        return await dispatch("list_sign_in_widget_versions", locals())

    @mcp.tool
    async def get_sign_out_page_settings(brand_id: str) -> ToolResult:
        return await dispatch("get_sign_out_page_settings", locals())

    @mcp.tool
    async def replace_sign_out_page_settings(
        brand_id: str, type: str, url: str | None = None
    ) -> ToolResult:
        return await dispatch("replace_sign_out_page_settings", locals())

    return (
        get_error_page_resources,
        get_customized_error_page,
        replace_customized_error_page,
        delete_customized_error_page,
        get_default_error_page,
        get_preview_error_page,
        replace_preview_error_page,
        delete_preview_error_page,
        get_sign_in_page_resources,
        get_customized_sign_in_page,
        replace_customized_sign_in_page,
        delete_customized_sign_in_page,
        get_default_sign_in_page,
        get_preview_sign_in_page,
        replace_preview_sign_in_page,
        delete_preview_sign_in_page,
        list_sign_in_widget_versions,
        get_sign_out_page_settings,
        replace_sign_out_page_settings,
    )
