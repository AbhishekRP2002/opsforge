"""Servicenow changes tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def create_change_request(
        *,
        short_description: Annotated[
            str, Field(description="Short description of the change request")
        ],
        description: Annotated[
            str | None, Field(description="Detailed description of the change request")
        ] = None,
        type: Annotated[
            str, Field(description="Type of change (normal, standard, emergency)")
        ],
        risk: Annotated[
            str | None, Field(description="Risk level of the change")
        ] = None,
        impact: Annotated[str | None, Field(description="Impact of the change")] = None,
        category: Annotated[
            str | None, Field(description="Category of the change")
        ] = None,
        requested_by: Annotated[
            str | None, Field(description="User who requested the change")
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the change")
        ] = None,
        start_date: Annotated[
            str | None, Field(description="Planned start date (YYYY-MM-DD HH:MM:SS)")
        ] = None,
        end_date: Annotated[
            str | None, Field(description="Planned end date (YYYY-MM-DD HH:MM:SS)")
        ] = None,
    ) -> ToolResult:
        "Create a new change request in ServiceNow"
        return await dispatch(
            "create_change_request",
            {
                "short_description": short_description,
                "description": description,
                "type": type,
                "risk": risk,
                "impact": impact,
                "category": category,
                "requested_by": requested_by,
                "assignment_group": assignment_group,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    @mcp.tool
    async def update_change_request(
        *,
        change_id: Annotated[str, Field(description="Change request ID or sys_id")],
        short_description: Annotated[
            str | None, Field(description="Short description of the change request")
        ] = None,
        description: Annotated[
            str | None, Field(description="Detailed description of the change request")
        ] = None,
        state: Annotated[
            str | None, Field(description="State of the change request")
        ] = None,
        risk: Annotated[
            str | None, Field(description="Risk level of the change")
        ] = None,
        impact: Annotated[str | None, Field(description="Impact of the change")] = None,
        category: Annotated[
            str | None, Field(description="Category of the change")
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the change")
        ] = None,
        start_date: Annotated[
            str | None, Field(description="Planned start date (YYYY-MM-DD HH:MM:SS)")
        ] = None,
        end_date: Annotated[
            str | None, Field(description="Planned end date (YYYY-MM-DD HH:MM:SS)")
        ] = None,
        work_notes: Annotated[
            str | None, Field(description="Work notes to add to the change request")
        ] = None,
    ) -> ToolResult:
        "Update an existing change request in ServiceNow"
        return await dispatch(
            "update_change_request",
            {
                "change_id": change_id,
                "short_description": short_description,
                "description": description,
                "state": state,
                "risk": risk,
                "impact": impact,
                "category": category,
                "assignment_group": assignment_group,
                "start_date": start_date,
                "end_date": end_date,
                "work_notes": work_notes,
            },
        )

    @mcp.tool
    async def list_change_requests(
        *,
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
        state: Annotated[str | None, Field(description="Filter by state")] = None,
        type: Annotated[
            str | None,
            Field(description="Filter by type (normal, standard, emergency)"),
        ] = None,
        category: Annotated[str | None, Field(description="Filter by category")] = None,
        assignment_group: Annotated[
            str | None, Field(description="Filter by assignment group")
        ] = None,
        timeframe: Annotated[
            str | None,
            Field(description="Filter by timeframe (upcoming, in-progress, completed)"),
        ] = None,
        query: Annotated[
            str | None, Field(description="Additional query string")
        ] = None,
    ) -> ToolResult:
        "List change requests from ServiceNow"
        return await dispatch(
            "list_change_requests",
            {
                "limit": limit,
                "offset": offset,
                "state": state,
                "type": type,
                "category": category,
                "assignment_group": assignment_group,
                "timeframe": timeframe,
                "query": query,
            },
        )

    @mcp.tool
    async def get_change_request_details(
        *,
        change_id: Annotated[str, Field(description="Change request ID or sys_id")],
    ) -> ToolResult:
        "Get detailed information about a specific change request"
        return await dispatch("get_change_request_details", {"change_id": change_id})

    @mcp.tool
    async def add_change_task(
        *,
        change_id: Annotated[str, Field(description="Change request ID or sys_id")],
        short_description: Annotated[
            str, Field(description="Short description of the task")
        ],
        description: Annotated[
            str | None, Field(description="Detailed description of the task")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the task")
        ] = None,
        planned_start_date: Annotated[
            str | None, Field(description="Planned start date (YYYY-MM-DD HH:MM:SS)")
        ] = None,
        planned_end_date: Annotated[
            str | None, Field(description="Planned end date (YYYY-MM-DD HH:MM:SS)")
        ] = None,
    ) -> ToolResult:
        "Add a task to a change request"
        return await dispatch(
            "add_change_task",
            {
                "change_id": change_id,
                "short_description": short_description,
                "description": description,
                "assigned_to": assigned_to,
                "planned_start_date": planned_start_date,
                "planned_end_date": planned_end_date,
            },
        )

    @mcp.tool
    async def submit_change_for_approval(
        *,
        change_id: Annotated[str, Field(description="Change request ID or sys_id")],
        approval_comments: Annotated[
            str | None, Field(description="Comments for the approval request")
        ] = None,
    ) -> ToolResult:
        "Submit a change request for approval"
        return await dispatch(
            "submit_change_for_approval",
            {"change_id": change_id, "approval_comments": approval_comments},
        )

    @mcp.tool
    async def approve_change(
        *,
        change_id: Annotated[str, Field(description="Change request ID or sys_id")],
        approver_id: Annotated[
            str | None, Field(description="ID of the approver")
        ] = None,
        approval_comments: Annotated[
            str | None, Field(description="Comments for the approval")
        ] = None,
    ) -> ToolResult:
        "Approve a change request"
        return await dispatch(
            "approve_change",
            {
                "change_id": change_id,
                "approver_id": approver_id,
                "approval_comments": approval_comments,
            },
        )

    @mcp.tool
    async def reject_change(
        *,
        change_id: Annotated[str, Field(description="Change request ID or sys_id")],
        approver_id: Annotated[
            str | None, Field(description="ID of the approver")
        ] = None,
        rejection_reason: Annotated[str, Field(description="Reason for rejection")],
    ) -> ToolResult:
        "Reject a change request"
        return await dispatch(
            "reject_change",
            {
                "change_id": change_id,
                "approver_id": approver_id,
                "rejection_reason": rejection_reason,
            },
        )

    return (
        create_change_request,
        update_change_request,
        list_change_requests,
        get_change_request_details,
        add_change_task,
        submit_change_for_approval,
        approve_change,
        reject_change,
    )
