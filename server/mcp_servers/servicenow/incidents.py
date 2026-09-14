"""Servicenow incidents tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def create_incident(
        *,
        short_description: Annotated[
            str, Field(description="Short description of the incident")
        ],
        description: Annotated[
            str | None, Field(description="Detailed description of the incident")
        ] = None,
        caller_id: Annotated[
            str | None, Field(description="User who reported the incident")
        ] = None,
        category: Annotated[
            str | None, Field(description="Category of the incident")
        ] = None,
        subcategory: Annotated[
            str | None, Field(description="Subcategory of the incident")
        ] = None,
        priority: Annotated[
            str | None, Field(description="Priority of the incident")
        ] = None,
        impact: Annotated[
            str | None, Field(description="Impact of the incident")
        ] = None,
        urgency: Annotated[
            str | None, Field(description="Urgency of the incident")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the incident")
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the incident")
        ] = None,
    ) -> ToolResult:
        "Create a new incident in ServiceNow"
        return await dispatch(
            "create_incident",
            {
                "short_description": short_description,
                "description": description,
                "caller_id": caller_id,
                "category": category,
                "subcategory": subcategory,
                "priority": priority,
                "impact": impact,
                "urgency": urgency,
                "assigned_to": assigned_to,
                "assignment_group": assignment_group,
            },
        )

    @mcp.tool
    async def update_incident(
        *,
        incident_id: Annotated[str, Field(description="Incident ID or sys_id")],
        short_description: Annotated[
            str | None, Field(description="Short description of the incident")
        ] = None,
        description: Annotated[
            str | None, Field(description="Detailed description of the incident")
        ] = None,
        state: Annotated[str | None, Field(description="State of the incident")] = None,
        category: Annotated[
            str | None, Field(description="Category of the incident")
        ] = None,
        subcategory: Annotated[
            str | None, Field(description="Subcategory of the incident")
        ] = None,
        priority: Annotated[
            str | None, Field(description="Priority of the incident")
        ] = None,
        impact: Annotated[
            str | None, Field(description="Impact of the incident")
        ] = None,
        urgency: Annotated[
            str | None, Field(description="Urgency of the incident")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the incident")
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the incident")
        ] = None,
        work_notes: Annotated[
            str | None, Field(description="Work notes to add to the incident")
        ] = None,
        close_notes: Annotated[
            str | None, Field(description="Close notes to add to the incident")
        ] = None,
        close_code: Annotated[
            str | None, Field(description="Close code for the incident")
        ] = None,
    ) -> ToolResult:
        "Update an existing incident in ServiceNow"
        return await dispatch(
            "update_incident",
            {
                "incident_id": incident_id,
                "short_description": short_description,
                "description": description,
                "state": state,
                "category": category,
                "subcategory": subcategory,
                "priority": priority,
                "impact": impact,
                "urgency": urgency,
                "assigned_to": assigned_to,
                "assignment_group": assignment_group,
                "work_notes": work_notes,
                "close_notes": close_notes,
                "close_code": close_code,
            },
        )

    @mcp.tool
    async def add_comment(
        *,
        incident_id: Annotated[str, Field(description="Incident ID or sys_id")],
        comment: Annotated[str, Field(description="Comment to add to the incident")],
        is_work_note: Annotated[
            bool, Field(description="Whether the comment is a work note")
        ] = False,
    ) -> ToolResult:
        "Add a comment to an incident in ServiceNow"
        return await dispatch(
            "add_comment",
            {
                "incident_id": incident_id,
                "comment": comment,
                "is_work_note": is_work_note,
            },
        )

    @mcp.tool
    async def resolve_incident(
        *,
        incident_id: Annotated[str, Field(description="Incident ID or sys_id")],
        resolution_code: Annotated[
            str, Field(description="Resolution code for the incident")
        ],
        resolution_notes: Annotated[
            str, Field(description="Resolution notes for the incident")
        ],
    ) -> ToolResult:
        "Resolve an incident in ServiceNow"
        return await dispatch(
            "resolve_incident",
            {
                "incident_id": incident_id,
                "resolution_code": resolution_code,
                "resolution_notes": resolution_notes,
            },
        )

    @mcp.tool
    async def list_incidents(
        *,
        limit: Annotated[
            int, Field(description="Maximum number of incidents to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        state: Annotated[
            str | None, Field(description="Filter by incident state")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="Filter by assigned user")
        ] = None,
        category: Annotated[str | None, Field(description="Filter by category")] = None,
        query: Annotated[
            str | None, Field(description="Search query for incidents")
        ] = None,
    ) -> ToolResult:
        "List incidents from ServiceNow"
        return await dispatch(
            "list_incidents",
            {
                "limit": limit,
                "offset": offset,
                "state": state,
                "assigned_to": assigned_to,
                "category": category,
                "query": query,
            },
        )

    @mcp.tool
    async def get_incident_by_number(
        *,
        incident_number: Annotated[
            str, Field(description="The number of the incident to fetch")
        ],
    ) -> ToolResult:
        "Incident details from ServiceNow"
        return await dispatch(
            "get_incident_by_number", {"incident_number": incident_number}
        )

    return (
        create_incident,
        update_incident,
        add_comment,
        resolve_incident,
        list_incidents,
        get_incident_by_number,
    )
