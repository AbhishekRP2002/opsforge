"""Source-qualified policy declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_policies(
        type: str,
        status: str | None = None,
        q: str | None = None,
        limit: int | None = None,
        after: str | None = None,
        fetch_all: bool = False,
    ) -> ToolResult:
        return await dispatch("list_policies", locals())

    @mcp.tool
    async def get_policy(policy_id: str) -> ToolResult:
        return await dispatch("get_policy", locals())

    @mcp.tool
    async def create_policy(policy_data: dict) -> ToolResult:
        return await dispatch("create_policy", locals())

    @mcp.tool
    async def update_policy(policy_id: str, policy_data: dict) -> ToolResult:
        return await dispatch("update_policy", locals())

    @mcp.tool
    async def delete_policy(policy_id: str) -> ToolResult:
        return await dispatch("delete_policy", locals())

    @mcp.tool
    async def activate_policy(policy_id: str) -> ToolResult:
        return await dispatch("activate_policy", locals())

    @mcp.tool
    async def deactivate_policy(policy_id: str) -> ToolResult:
        return await dispatch("deactivate_policy", locals())

    @mcp.tool
    async def list_policy_rules(
        policy_id: str, after: str | None = None, fetch_all: bool = False
    ) -> ToolResult:
        return await dispatch("list_policy_rules", locals())

    @mcp.tool
    async def get_policy_rule(policy_id: str, rule_id: str) -> ToolResult:
        return await dispatch("get_policy_rule", locals())

    @mcp.tool
    async def create_policy_rule(policy_id: str, rule_data: dict) -> ToolResult:
        return await dispatch("create_policy_rule", locals())

    @mcp.tool
    async def update_policy_rule(
        policy_id: str, rule_id: str, rule_data: dict
    ) -> ToolResult:
        return await dispatch("update_policy_rule", locals())

    @mcp.tool
    async def delete_policy_rule(policy_id: str, rule_id: str) -> ToolResult:
        return await dispatch("delete_policy_rule", locals())

    @mcp.tool
    async def activate_policy_rule(policy_id: str, rule_id: str) -> ToolResult:
        return await dispatch("activate_policy_rule", locals())

    @mcp.tool
    async def deactivate_policy_rule(policy_id: str, rule_id: str) -> ToolResult:
        return await dispatch("deactivate_policy_rule", locals())

    return (
        list_policies,
        get_policy,
        create_policy,
        update_policy,
        delete_policy,
        activate_policy,
        deactivate_policy,
        list_policy_rules,
        get_policy_rule,
        create_policy_rule,
        update_policy_rule,
        delete_policy_rule,
        activate_policy_rule,
        deactivate_policy_rule,
    )
