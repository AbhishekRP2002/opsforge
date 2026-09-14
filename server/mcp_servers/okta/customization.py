"""Source-qualified brand and domain declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_brands(
        expand: list[str] | None = None,
        after: str | None = None,
        limit: int | None = None,
        q: str | None = None,
        fetch_all: bool = False,
    ) -> ToolResult:
        return await dispatch("list_brands", locals())

    @mcp.tool
    async def get_brand(brand_id: str, expand: list[str] | None = None) -> ToolResult:
        return await dispatch("get_brand", locals())

    @mcp.tool
    async def create_brand(name: str) -> ToolResult:
        return await dispatch("create_brand", locals())

    @mcp.tool
    async def replace_brand(
        brand_id: str,
        name: str,
        agree_to_custom_privacy_policy: bool | None = None,
        custom_privacy_policy_url: str | None = None,
        remove_powered_by_okta: bool | None = None,
        locale: str | None = None,
        email_domain_id: str | None = None,
        default_app: dict | None = None,
    ) -> ToolResult:
        return await dispatch("replace_brand", locals())

    @mcp.tool
    async def delete_brand(brand_id: str) -> ToolResult:
        return await dispatch("delete_brand", locals())

    @mcp.tool
    async def list_brand_domains(brand_id: str) -> ToolResult:
        return await dispatch("list_brand_domains", locals())

    @mcp.tool
    async def list_custom_domains() -> ToolResult:
        return await dispatch("list_custom_domains", {})

    @mcp.tool
    async def create_custom_domain(
        domain: str, certificate_source_type: str
    ) -> ToolResult:
        return await dispatch("create_custom_domain", locals())

    @mcp.tool
    async def get_custom_domain(domain_id: str) -> ToolResult:
        return await dispatch("get_custom_domain", locals())

    @mcp.tool
    async def replace_custom_domain(domain_id: str, brand_id: str) -> ToolResult:
        return await dispatch("replace_custom_domain", locals())

    @mcp.tool
    async def delete_custom_domain(domain_id: str) -> ToolResult:
        return await dispatch("delete_custom_domain", locals())

    @mcp.tool
    async def upsert_custom_domain_certificate(
        domain_id: str,
        certificate: str,
        certificate_chain: str,
        private_key_file_path: str,
    ) -> ToolResult:
        return await dispatch("upsert_custom_domain_certificate", locals())

    @mcp.tool
    async def verify_custom_domain(domain_id: str) -> ToolResult:
        return await dispatch("verify_custom_domain", locals())

    @mcp.tool
    async def list_email_domains(expand_brands: bool = False) -> ToolResult:
        return await dispatch("list_email_domains", locals())

    @mcp.tool
    async def create_email_domain(
        brand_id: str,
        domain: str,
        display_name: str,
        user_name: str,
        validation_subdomain: str = "mail",
    ) -> ToolResult:
        return await dispatch("create_email_domain", locals())

    @mcp.tool
    async def get_email_domain(
        email_domain_id: str, expand_brands: bool = False
    ) -> ToolResult:
        return await dispatch("get_email_domain", locals())

    @mcp.tool
    async def replace_email_domain(
        email_domain_id: str, display_name: str, user_name: str
    ) -> ToolResult:
        return await dispatch("replace_email_domain", locals())

    @mcp.tool
    async def delete_email_domain(email_domain_id: str) -> ToolResult:
        return await dispatch("delete_email_domain", locals())

    @mcp.tool
    async def verify_email_domain(email_domain_id: str) -> ToolResult:
        return await dispatch("verify_email_domain", locals())

    return (
        list_brands,
        get_brand,
        create_brand,
        replace_brand,
        delete_brand,
        list_brand_domains,
        list_custom_domains,
        create_custom_domain,
        get_custom_domain,
        replace_custom_domain,
        delete_custom_domain,
        upsert_custom_domain_certificate,
        verify_custom_domain,
        list_email_domains,
        create_email_domain,
        get_email_domain,
        replace_email_domain,
        delete_email_domain,
        verify_email_domain,
    )
