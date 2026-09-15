"""Derive executable provider contracts from the same decorated tool functions."""

from collections.abc import Callable, Mapping
from copy import deepcopy
from functools import lru_cache
from typing import TYPE_CHECKING, cast

from fastmcp import FastMCP
from fastmcp.tools import Tool
from jsonschema import Draft202012Validator, validators

from . import benchmark, darwinbox, erpnext, jira, okta, servicenow

if TYPE_CHECKING:
    from ..storage.database import Database

Handler = Callable[["Database", dict, int, int], tuple[object, bool]]

REGISTRARS = {
    "okta": okta.register_tools,
    "servicenow": servicenow.register_tools,
    "benchmark": benchmark.register_tools,
    "erpnext": erpnext.register_tools,
    "darwinbox": darwinbox.register_tools,
    "jira": jira.register_tools,
}
HANDLER_RESOLVERS: dict[str, Callable[[], Mapping[str, Handler]]] = {
    "darwinbox": lambda: _darwinbox_handlers(),
    "erpnext": lambda: _erpnext_handlers(),
    "okta": lambda: _okta_handlers(),
    "servicenow": lambda: _servicenow_handlers(),
    "jira": lambda: _jira_handlers(),
}
CONTROL_TOOL_NAMES = {"benchmark": frozenset({"workflow_wait", "workflow_submit"})}
StrictValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda checker, value: type(value) is int
    ),
)


async def _unbound(name, arguments):
    raise RuntimeError("Schema-only tool definitions cannot execute an episode")


def _darwinbox_handlers() -> Mapping[str, Handler]:
    from ..services.darwinbox_attendance import HANDLERS as ATTENDANCE
    from ..services.darwinbox_core import HANDLERS as CORE
    from ..services.darwinbox_masters import HANDLERS as MASTERS
    from ..services.darwinbox_recruitment import HANDLERS as RECRUITMENT
    from ..services.darwinbox_timeoff import HANDLERS as TIMEOFF

    return CORE | ATTENDANCE | MASTERS | RECRUITMENT | TIMEOFF


def _erpnext_handlers() -> Mapping[str, Handler]:
    from ..services.erpnext_accounting_hr import HANDLERS as ACCOUNTING_HR
    from ..services.erpnext_analytics import HANDLERS as ANALYTICS
    from ..services.erpnext_business import HANDLERS as BUSINESS
    from ..services.erpnext_commerce import HANDLERS as COMMERCE
    from ..services.erpnext_kanban import HANDLERS as KANBAN
    from ..services.erpnext_operations import HANDLERS
    from ..services.erpnext_projects import HANDLERS as PROJECTS

    return (
        HANDLERS | PROJECTS | COMMERCE | ACCOUNTING_HR | BUSINESS | ANALYTICS | KANBAN
    )


def _okta_handlers() -> Mapping[str, Handler]:
    from ..services import (
        okta,
        okta_applications,
        okta_customization,
        okta_devices,
        okta_identity,
        okta_logs,
        okta_pages,
        okta_policies,
        okta_templates,
        okta_themes,
    )

    return (
        okta_applications.HANDLERS
        | okta_policies.HANDLERS
        | okta_customization.HANDLERS
        | okta_themes.HANDLERS
        | okta_pages.HANDLERS
        | okta_templates.HANDLERS
        | okta_devices.HANDLERS
        | okta_logs.HANDLERS
        | {"get_user": okta.get_user}
        | {
            name: getattr(okta_identity, name)
            for name in (
                "list_users",
                "get_user_profile_attributes",
                "create_user",
                "update_user",
                "deactivate_user",
                "delete_deactivated_user",
                "export_users_csv",
                "list_groups",
                "get_group",
                "create_group",
                "delete_group",
                "confirm_delete_group",
                "update_group",
                "list_group_users",
                "list_group_apps",
                "add_user_to_group",
                "remove_user_from_group",
                "list_user_groups",
            )
        }
    )


def _servicenow_handlers() -> Mapping[str, Handler]:
    from ..services import servicenow as service
    from ..services import (
        servicenow_agile,
        servicenow_catalog,
        servicenow_changes,
        servicenow_changesets,
        servicenow_incidents,
        servicenow_knowledge,
        servicenow_optimization,
        servicenow_scripts,
        servicenow_users,
        servicenow_variables,
        servicenow_workflows,
    )

    return (
        servicenow_incidents.HANDLERS
        | servicenow_users.HANDLERS
        | servicenow_scripts.HANDLERS
        | servicenow_changesets.HANDLERS
        | servicenow_workflows.HANDLERS
        | servicenow_changes.HANDLERS
        | servicenow_agile.HANDLERS
        | servicenow_knowledge.HANDLERS
        | servicenow_catalog.HANDLERS
        | servicenow_variables.HANDLERS
        | servicenow_optimization.HANDLERS
        | {
            "get_user": service.get_user,
            "add_group_members": service.add_group_members,
        }
    )


def _jira_handlers() -> Mapping[str, Handler]:
    from ..services.jira_agile import HANDLERS as AGILE
    from ..services.jira_core import HANDLERS as CORE
    from ..services.jira_forms import HANDLERS as FORMS
    from ..services.jira_insights import HANDLERS as INSIGHTS
    from ..services.jira_metadata import HANDLERS as METADATA
    from ..services.jira_relations import HANDLERS as ACTIVITY
    from ..services.jira_service_desk import HANDLERS as SERVICE_DESK
    from ..services.jira_workflow import HANDLERS as WORKFLOW

    return cast(
        Mapping[str, Handler],
        CORE | ACTIVITY | METADATA | WORKFLOW | AGILE | SERVICE_DESK | FORMS | INSIGHTS,
    )


def _registered_tools(provider: str) -> list[Tool]:
    try:
        register = REGISTRARS[provider]
    except KeyError:
        raise KeyError(f"unknown provider: {provider}") from None
    return [
        function if isinstance(function, Tool) else Tool.from_function(function)
        for function in register(FastMCP(provider), _unbound)
    ]


@lru_cache
def tool_definitions(provider: str) -> dict[str, Tool]:
    return {tool.name: tool for tool in _registered_tools(provider)}


def business_tool_names() -> set[str]:
    return {
        f"{provider}.{name}"
        for provider in REGISTRARS
        if provider in HANDLER_RESOLVERS
        for name in tool_definitions(provider)
        if name not in CONTROL_TOOL_NAMES.get(provider, frozenset())
    }


def tool_handler(provider: str, name: str) -> Handler:
    if name in CONTROL_TOOL_NAMES.get(provider, frozenset()):
        raise KeyError(f"tool has no business handler: {provider}.{name}")
    try:
        handlers = HANDLER_RESOLVERS[provider]()
    except KeyError:
        raise KeyError(f"unknown provider: {provider}") from None
    try:
        return handlers[name]
    except KeyError:
        raise KeyError(f"unknown business tool: {provider}.{name}") from None


def validate_registry() -> None:
    if not set(HANDLER_RESOLVERS).issubset(REGISTRARS) or not set(
        CONTROL_TOOL_NAMES
    ).issubset(REGISTRARS):
        raise ValueError("registry provider keys must match registered providers")
    for provider in REGISTRARS:
        registered = _registered_tools(provider)
        names = [tool.name for tool in registered]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate tool declaration for provider {provider}")
        controls = CONTROL_TOOL_NAMES.get(provider, frozenset())
        if not controls.issubset(names):
            raise ValueError(f"missing control declaration for provider {provider}")
        business_names = set(names) - controls
        handlers = HANDLER_RESOLVERS.get(provider, dict)()
        if any(not callable(handler) for handler in handlers.values()):
            raise ValueError(f"non-callable handler for provider {provider}")
        handler_names = set(handlers)
        if business_names != handler_names:
            raise ValueError(f"handler mismatch for provider {provider}")


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


def normalized_arguments(provider: str, name: str, arguments: dict) -> dict:
    tool = tool_definitions(provider)[name]
    return {
        key: deepcopy(arguments[key] if key in arguments else field["default"])
        for key, field in tool.parameters["properties"].items()
        if key in arguments or "default" in field
    }
