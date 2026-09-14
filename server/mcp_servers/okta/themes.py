"""Source-qualified theme declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_brand_themes(brand_id: str) -> ToolResult:
        return await dispatch("list_brand_themes", locals())

    @mcp.tool
    async def get_brand_theme(brand_id: str, theme_id: str) -> ToolResult:
        return await dispatch("get_brand_theme", locals())

    @mcp.tool
    async def replace_brand_theme(
        brand_id: str,
        theme_id: str,
        primary_color_hex: str,
        secondary_color_hex: str,
        sign_in_page_touch_point_variant: str,
        end_user_dashboard_touch_point_variant: str,
        error_page_touch_point_variant: str,
        email_template_touch_point_variant: str,
        primary_color_contrast_hex: str | None = None,
        secondary_color_contrast_hex: str | None = None,
        loading_page_touch_point_variant: str | None = None,
    ) -> ToolResult:
        return await dispatch("replace_brand_theme", locals())

    @mcp.tool
    async def upload_brand_theme_logo(
        brand_id: str, theme_id: str, file_path: str
    ) -> ToolResult:
        return await dispatch("upload_brand_theme_logo", locals())

    @mcp.tool
    async def upload_brand_theme_favicon(
        brand_id: str, theme_id: str, file_path: str
    ) -> ToolResult:
        return await dispatch("upload_brand_theme_favicon", locals())

    @mcp.tool
    async def upload_brand_theme_background_image(
        brand_id: str, theme_id: str, file_path: str
    ) -> ToolResult:
        return await dispatch("upload_brand_theme_background_image", locals())

    @mcp.tool
    async def delete_brand_theme_logo(brand_id: str, theme_id: str) -> ToolResult:
        return await dispatch("delete_brand_theme_logo", locals())

    @mcp.tool
    async def delete_brand_theme_favicon(brand_id: str, theme_id: str) -> ToolResult:
        return await dispatch("delete_brand_theme_favicon", locals())

    @mcp.tool
    async def delete_brand_theme_background_image(
        brand_id: str, theme_id: str
    ) -> ToolResult:
        return await dispatch("delete_brand_theme_background_image", locals())

    return (
        list_brand_themes,
        get_brand_theme,
        replace_brand_theme,
        upload_brand_theme_logo,
        upload_brand_theme_favicon,
        upload_brand_theme_background_image,
        delete_brand_theme_logo,
        delete_brand_theme_favicon,
        delete_brand_theme_background_image,
    )
