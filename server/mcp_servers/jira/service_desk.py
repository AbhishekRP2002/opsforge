"""Jira Service Management declaration family."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from .core import PROJECT


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def jira_get_service_desk_for_project(
        *, project_key: Annotated[str, Field(pattern=PROJECT)]
    ) -> ToolResult:
        "Get the service desk associated with a project."
        return await dispatch(
            "jira_get_service_desk_for_project", {"project_key": project_key}
        )

    @mcp.tool
    async def jira_get_service_desk_queues(
        *,
        service_desk_id: str,
        start_at: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=50)] = 50,
    ) -> ToolResult:
        "List queues in a service desk."
        return await dispatch(
            "jira_get_service_desk_queues",
            {"service_desk_id": service_desk_id, "start_at": start_at, "limit": limit},
        )

    @mcp.tool
    async def jira_get_queue_issues(
        *,
        service_desk_id: str,
        queue_id: str,
        start_at: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1)] = 50,
    ) -> ToolResult:
        "List issues currently matching a service-desk queue."
        return await dispatch(
            "jira_get_queue_issues",
            {
                "service_desk_id": service_desk_id,
                "queue_id": queue_id,
                "start_at": start_at,
                "limit": limit,
            },
        )

    @mcp.tool
    async def jira_get_request_types(
        *,
        service_desk_id: str,
        start_at: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=50)] = 50,
    ) -> ToolResult:
        "List request types exposed by a service desk."
        return await dispatch(
            "jira_get_request_types",
            {"service_desk_id": service_desk_id, "start_at": start_at, "limit": limit},
        )

    @mcp.tool
    async def jira_get_request_type_fields(
        *, service_desk_id: str, request_type_id: str
    ) -> ToolResult:
        "List fields required by a service-desk request type."
        return await dispatch(
            "jira_get_request_type_fields",
            {"service_desk_id": service_desk_id, "request_type_id": request_type_id},
        )

    @mcp.tool
    async def jira_create_customer_request(
        *,
        service_desk_id: str,
        request_type_id: str,
        request_field_values: Annotated[
            str, Field(description="JSON object keyed by request field ID.")
        ],
        raise_on_behalf_of: str | None = None,
        request_participants: str | None = None,
        attachments: str | None = None,
        strict_on_behalf: bool = False,
    ) -> ToolResult:
        "Create a customer request with optional participants and inline attachments."
        return await dispatch(
            "jira_create_customer_request",
            {
                "service_desk_id": service_desk_id,
                "request_type_id": request_type_id,
                "request_field_values": request_field_values,
                "raise_on_behalf_of": raise_on_behalf_of,
                "request_participants": request_participants,
                "attachments": attachments,
                "strict_on_behalf": strict_on_behalf,
            },
        )

    return (
        jira_get_service_desk_for_project,
        jira_get_service_desk_queues,
        jira_get_queue_issues,
        jira_get_request_types,
        jira_get_request_type_fields,
        jira_create_customer_request,
    )
