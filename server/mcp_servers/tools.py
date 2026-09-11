"""Derive validation contracts from the same decorated tool functions."""

from functools import lru_cache

from fastmcp import FastMCP
from fastmcp.tools import Tool
from jsonschema import Draft202012Validator, validators

from . import benchmark, okta, servicenow

REGISTRARS = {
    "okta": okta.register_tools,
    "servicenow": servicenow.register_tools,
    "benchmark": benchmark.register_tools,
}
StrictValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda checker, value: type(value) is int
    ),
)


async def _unbound(name, arguments):
    raise RuntimeError("Schema-only tool definitions cannot execute an episode")


@lru_cache
def tool_definitions(provider: str) -> dict[str, Tool]:
    try:
        register = REGISTRARS[provider]
    except KeyError:
        raise KeyError(f"unknown provider: {provider}") from None
    functions = register(FastMCP(provider), _unbound)
    tools = [Tool.from_function(function) for function in functions]
    return {tool.name: tool for tool in tools}


def tool_schema(provider: str, name: str) -> dict:
    try:
        return tool_definitions(provider)[name].parameters
    except KeyError:
        raise KeyError(f"unknown tool for provider {provider}: {name}") from None


def argument_error(provider: str, name: str, arguments: dict) -> str | None:
    try:
        schema = tool_schema(provider, name)
    except KeyError:
        return "Unknown provider or tool"
    error = next(iter(StrictValidator(schema).iter_errors(arguments)), None)
    return f"Invalid arguments: {error.message}" if error else None
