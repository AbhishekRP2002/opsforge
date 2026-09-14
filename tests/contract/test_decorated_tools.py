"""Callable declarations own inputs and share executable registry validation."""

import asyncio
import inspect

import pytest
from fastmcp import FastMCP
from fastmcp.tools import Tool, ToolResult
from fastmcp.tools.function_tool import FunctionTool
from itops_env.server.interfaces.control import EpisodeBinding
from itops_env.server.mcp_servers import providers, tools
from pydantic import Field


def test_provider_tools_are_typed_fastmcp_functions():
    factory = getattr(providers, "create_provider_server", None)
    assert callable(factory), "Expose the servers built from @mcp.tool functions"

    async def check():
        binding = EpisodeBinding()
        for provider, expected in {
            "okta": {"get_user": {"user_id"}},
            "servicenow": {
                "get_user": {"user_id", "user_name", "email"},
                "add_group_members": {"group_id", "members"},
            },
            "benchmark": {
                "workflow_wait": {"seconds"},
                "workflow_submit": {"disposition", "user_id", "group_id", "summary"},
            },
        }.items():
            server = providers.create_provider_server(binding, provider)
            for name, arguments in expected.items():
                tool = await server.get_tool(name)
                assert isinstance(tool, FunctionTool)
                assert set(tool.parameters["properties"]) == arguments
                assert tool.parameters["additionalProperties"] is False
                assert tool.description

    asyncio.run(check())


def test_callable_normalization_owns_nested_caller_values_and_defaults(monkeypatch):
    default = Field(default=[])

    async def nested(attributes: dict, defaults: list = default) -> ToolResult:
        return ToolResult(content=[])

    declared = Tool.from_function(nested)
    monkeypatch.setattr(
        tools, "tool_definitions", lambda provider: {"nested": declared}
    )
    raw = {"attributes": {"nested": ["original"]}}
    normalized = tools.normalized_arguments("fixture", "nested", raw)
    assert normalized == {"attributes": {"nested": ["original"]}, "defaults": []}
    normalized["attributes"]["nested"].append("mutated")
    normalized["defaults"].append("mutated")
    assert raw == {"attributes": {"nested": ["original"]}}
    assert declared.parameters["properties"]["defaults"]["default"] == []


def test_callable_declarations_share_registry_checks(monkeypatch):
    async def declared() -> ToolResult:
        return ToolResult(content=[])

    def register(mcp: FastMCP, dispatch):
        mcp.tool(declared)
        return (declared,)

    monkeypatch.setitem(tools.REGISTRARS, "fixture", register)
    monkeypatch.setitem(
        tools.HANDLER_RESOLVERS,
        "fixture",
        lambda: {"declared": lambda db, args, step, clock: ({}, False)},
    )
    tools.validate_registry()
    monkeypatch.setitem(
        tools.REGISTRARS, "fixture", lambda mcp, dispatch: (declared, declared)
    )
    with pytest.raises(ValueError, match="duplicate tool"):
        tools.validate_registry()
    monkeypatch.setitem(tools.REGISTRARS, "fixture", register)
    monkeypatch.setitem(tools.HANDLER_RESOLVERS, "fixture", dict)
    with pytest.raises(ValueError, match="handler mismatch"):
        tools.validate_registry()


@pytest.mark.parametrize(
    "provider,count",
    [
        ("servicenow", 82),
        ("erpnext", 127),
        ("darwinbox", 23),
        ("okta", 112),
        ("benchmark", 2),
    ],
)
def test_registered_contracts_have_typed_async_callables(provider, count):
    definitions = tools.tool_definitions(provider)
    assert len(definitions) == count
    for name, declaration in definitions.items():
        function = getattr(declaration, "fn", None)
        assert inspect.iscoroutinefunction(function), name
        signature = inspect.signature(function)
        assert all(
            parameter.annotation is not inspect.Parameter.empty
            for parameter in signature.parameters.values()
        ), name
        if provider in {"servicenow", "erpnext", "darwinbox"}:
            assert declaration.description


@pytest.mark.parametrize(
    "provider,name,arguments",
    [
        (
            "servicenow",
            "create_incident",
            {"short_description": "Native", "extra": "ignored"},
        ),
        ("erpnext", "erpnext_account_list", {"extra": "ignored"}),
        ("darwinbox", "get_employee_details", {"extra": "ignored"}),
    ],
)
def test_undeclared_top_level_arguments_are_rejected(provider, name, arguments):
    assert tools.argument_error(provider, name, arguments) is not None


@pytest.mark.parametrize(
    "missing", ["is_half_day", "is_paid_or_unpaid", "revoke_leave"]
)
def test_nested_source_default_does_not_make_leave_required_key_optional(missing):
    entry = {
        "employee_no": "E1",
        "leave_name": "Annual",
        "message": "Rest",
        "from_date": "04-01-2026",
        "to_date": "04-01-2026",
        "is_half_day": "No",
        "is_paid_or_unpaid": "paid",
        "revoke_leave": "No",
    }
    assert tools.argument_error("darwinbox", "apply_leave", {"data": [entry]}) is None
    del entry[missing]
    assert (
        tools.argument_error("darwinbox", "apply_leave", {"data": [entry]}) is not None
    )
