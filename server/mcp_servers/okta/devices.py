"""Source-qualified devices declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_device_assurance_policies(
        version_threshold: str | None = None,
    ) -> ToolResult:
        return await dispatch("list_device_assurance_policies", locals())

    @mcp.tool
    async def get_device_assurance_policy(device_assurance_id: str) -> ToolResult:
        return await dispatch("get_device_assurance_policy", locals())

    @mcp.tool
    async def create_device_assurance_policy(
        policy_data: dict, user_stated_os_version: str | None = None
    ) -> ToolResult:
        return await dispatch("create_device_assurance_policy", locals())

    @mcp.tool
    async def replace_device_assurance_policy(
        device_assurance_id: str,
        policy_data: dict,
        user_stated_os_version: str | None = None,
    ) -> ToolResult:
        return await dispatch("replace_device_assurance_policy", locals())

    @mcp.tool
    async def delete_device_assurance_policy(device_assurance_id: str) -> ToolResult:
        return await dispatch("delete_device_assurance_policy", locals())

    return (
        list_device_assurance_policies,
        get_device_assurance_policy,
        create_device_assurance_policy,
        replace_device_assurance_policy,
        delete_device_assurance_policy,
    )
