"""Source-qualified email template declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_email_templates(
        brand_id: str,
        expand: list[str] | None = None,
        after: str | None = None,
        fetch_all: bool = False,
    ) -> ToolResult:
        return await dispatch("list_email_templates", locals())

    @mcp.tool
    async def get_email_template(
        brand_id: str, template_name: str, expand: list[str] | None = None
    ) -> ToolResult:
        return await dispatch("get_email_template", locals())

    @mcp.tool
    async def list_email_customizations(
        brand_id: str,
        template_name: str,
        after: str | None = None,
        fetch_all: bool = False,
    ) -> ToolResult:
        return await dispatch("list_email_customizations", locals())

    @mcp.tool
    async def create_email_customization(
        brand_id: str,
        template_name: str,
        language: str,
        subject: str,
        body: str,
        is_default: bool | None = None,
    ) -> ToolResult:
        return await dispatch("create_email_customization", locals())

    @mcp.tool
    async def get_email_customization(
        brand_id: str, template_name: str, customization_id: str
    ) -> ToolResult:
        return await dispatch("get_email_customization", locals())

    @mcp.tool
    async def replace_email_customization(
        brand_id: str,
        template_name: str,
        customization_id: str,
        language: str,
        subject: str,
        body: str,
        is_default: bool | None = None,
    ) -> ToolResult:
        return await dispatch("replace_email_customization", locals())

    @mcp.tool
    async def delete_email_customization(
        brand_id: str,
        template_name: str,
        customization_id: str,
        language: str = "unknown",
    ) -> ToolResult:
        return await dispatch("delete_email_customization", locals())

    @mcp.tool
    async def delete_all_email_customizations(
        brand_id: str, template_name: str
    ) -> ToolResult:
        return await dispatch("delete_all_email_customizations", locals())

    @mcp.tool
    async def get_email_customization_preview(
        brand_id: str, template_name: str, customization_id: str
    ) -> ToolResult:
        return await dispatch("get_email_customization_preview", locals())

    @mcp.tool
    async def get_email_default_content(
        brand_id: str, template_name: str, language: str | None = None
    ) -> ToolResult:
        return await dispatch("get_email_default_content", locals())

    @mcp.tool
    async def get_email_default_content_preview(
        brand_id: str, template_name: str, language: str | None = None
    ) -> ToolResult:
        return await dispatch("get_email_default_content_preview", locals())

    @mcp.tool
    async def get_email_settings(brand_id: str, template_name: str) -> ToolResult:
        return await dispatch("get_email_settings", locals())

    @mcp.tool
    async def replace_email_settings(
        brand_id: str, template_name: str, recipients: str
    ) -> ToolResult:
        return await dispatch("replace_email_settings", locals())

    @mcp.tool
    async def send_test_email(
        brand_id: str, template_name: str, language: str | None = None
    ) -> ToolResult:
        return await dispatch("send_test_email", locals())

    return (
        list_email_templates,
        get_email_template,
        list_email_customizations,
        create_email_customization,
        get_email_customization,
        replace_email_customization,
        delete_email_customization,
        delete_all_email_customizations,
        get_email_customization_preview,
        get_email_default_content,
        get_email_default_content_preview,
        get_email_settings,
        replace_email_settings,
        send_test_email,
    )
