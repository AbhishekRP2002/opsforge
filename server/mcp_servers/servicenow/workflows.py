"""Servicenow workflows tool declarations."""

from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_workflows(
        *,
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
        active: Annotated[
            bool | None, Field(description="Filter by active status")
        ] = None,
        name: Annotated[
            str | None, Field(description="Filter by name (contains)")
        ] = None,
        query: Annotated[
            str | None, Field(description="Additional query string")
        ] = None,
    ) -> ToolResult:
        "List workflows from ServiceNow"
        return await dispatch(
            "list_workflows",
            {
                "limit": limit,
                "offset": offset,
                "active": active,
                "name": name,
                "query": query,
            },
        )

    @mcp.tool
    async def get_workflow_details(
        *,
        workflow_id: Annotated[str, Field(description="Workflow ID or sys_id")],
        include_versions: Annotated[
            bool | None, Field(description="Include workflow versions")
        ] = False,
    ) -> ToolResult:
        "Get detailed information about a specific workflow"
        return await dispatch(
            "get_workflow_details",
            {"workflow_id": workflow_id, "include_versions": include_versions},
        )

    @mcp.tool
    async def list_workflow_versions(
        *,
        workflow_id: Annotated[str, Field(description="Workflow ID or sys_id")],
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
    ) -> ToolResult:
        "List workflow versions from ServiceNow"
        return await dispatch(
            "list_workflow_versions",
            {"workflow_id": workflow_id, "limit": limit, "offset": offset},
        )

    @mcp.tool
    async def get_workflow_activities(
        *,
        workflow_id: Annotated[str, Field(description="Workflow ID or sys_id")],
        version: Annotated[
            str | None, Field(description="Specific version to get activities for")
        ] = None,
    ) -> ToolResult:
        "Get activities for a specific workflow"
        return await dispatch(
            "get_workflow_activities", {"workflow_id": workflow_id, "version": version}
        )

    @mcp.tool
    async def create_workflow(
        *,
        name: Annotated[str, Field(description="Name of the workflow")],
        description: Annotated[
            str | None, Field(description="Description of the workflow")
        ] = None,
        table: Annotated[
            str | None, Field(description="Table the workflow applies to")
        ] = None,
        active: Annotated[
            bool | None, Field(description="Whether the workflow is active")
        ] = True,
        attributes: Annotated[
            dict[str, Any] | None,
            Field(description="Additional attributes for the workflow"),
        ] = None,
    ) -> ToolResult:
        "Create a new workflow in ServiceNow"
        return await dispatch(
            "create_workflow",
            {
                "name": name,
                "description": description,
                "table": table,
                "active": active,
                "attributes": attributes,
            },
        )

    @mcp.tool
    async def update_workflow(
        *,
        workflow_id: Annotated[str, Field(description="Workflow ID or sys_id")],
        name: Annotated[str | None, Field(description="Name of the workflow")] = None,
        description: Annotated[
            str | None, Field(description="Description of the workflow")
        ] = None,
        table: Annotated[
            str | None, Field(description="Table the workflow applies to")
        ] = None,
        active: Annotated[
            bool | None, Field(description="Whether the workflow is active")
        ] = None,
        attributes: Annotated[
            dict[str, Any] | None,
            Field(description="Additional attributes for the workflow"),
        ] = None,
    ) -> ToolResult:
        "Update an existing workflow in ServiceNow"
        return await dispatch(
            "update_workflow",
            {
                "workflow_id": workflow_id,
                "name": name,
                "description": description,
                "table": table,
                "active": active,
                "attributes": attributes,
            },
        )

    @mcp.tool
    async def activate_workflow(
        *,
        workflow_id: Annotated[str, Field(description="Workflow ID or sys_id")],
    ) -> ToolResult:
        "Activate a workflow in ServiceNow"
        return await dispatch("activate_workflow", {"workflow_id": workflow_id})

    @mcp.tool
    async def deactivate_workflow(
        *,
        workflow_id: Annotated[str, Field(description="Workflow ID or sys_id")],
    ) -> ToolResult:
        "Deactivate a workflow in ServiceNow"
        return await dispatch("deactivate_workflow", {"workflow_id": workflow_id})

    @mcp.tool
    async def add_workflow_activity(
        *,
        workflow_version_id: Annotated[str, Field(description="Workflow version ID")],
        name: Annotated[str, Field(description="Name of the activity")],
        description: Annotated[
            str | None, Field(description="Description of the activity")
        ] = None,
        activity_type: Annotated[
            str,
            Field(
                description="Type of activity (e.g., 'approval', 'task', 'notification')"
            ),
        ],
        attributes: Annotated[
            dict[str, Any] | None,
            Field(description="Additional attributes for the activity"),
        ] = None,
    ) -> ToolResult:
        "Add a new activity to a workflow in ServiceNow"
        return await dispatch(
            "add_workflow_activity",
            {
                "workflow_version_id": workflow_version_id,
                "name": name,
                "description": description,
                "activity_type": activity_type,
                "attributes": attributes,
            },
        )

    @mcp.tool
    async def update_workflow_activity(
        *,
        activity_id: Annotated[str, Field(description="Activity ID or sys_id")],
        name: Annotated[str | None, Field(description="Name of the activity")] = None,
        description: Annotated[
            str | None, Field(description="Description of the activity")
        ] = None,
        attributes: Annotated[
            dict[str, Any] | None,
            Field(description="Additional attributes for the activity"),
        ] = None,
    ) -> ToolResult:
        "Update an existing activity in a workflow"
        return await dispatch(
            "update_workflow_activity",
            {
                "activity_id": activity_id,
                "name": name,
                "description": description,
                "attributes": attributes,
            },
        )

    @mcp.tool
    async def delete_workflow_activity(
        *,
        activity_id: Annotated[str, Field(description="Activity ID or sys_id")],
    ) -> ToolResult:
        "Delete an activity from a workflow"
        return await dispatch("delete_workflow_activity", {"activity_id": activity_id})

    @mcp.tool
    async def reorder_workflow_activities(
        *,
        workflow_id: Annotated[str, Field(description="Workflow ID or sys_id")],
        activity_ids: Annotated[
            list[str], Field(description="List of activity IDs in the desired order")
        ],
    ) -> ToolResult:
        "Reorder activities in a workflow"
        return await dispatch(
            "reorder_workflow_activities",
            {"workflow_id": workflow_id, "activity_ids": activity_ids},
        )

    return (
        list_workflows,
        get_workflow_details,
        list_workflow_versions,
        get_workflow_activities,
        create_workflow,
        update_workflow,
        activate_workflow,
        deactivate_workflow,
        add_workflow_activity,
        update_workflow_activity,
        delete_workflow_activity,
        reorder_workflow_activities,
    )
