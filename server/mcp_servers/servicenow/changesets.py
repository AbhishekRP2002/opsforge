"""Servicenow changesets tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_changesets(
        *,
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
        state: Annotated[str | None, Field(description="Filter by state")] = None,
        application: Annotated[
            str | None, Field(description="Filter by application")
        ] = None,
        developer: Annotated[
            str | None, Field(description="Filter by developer")
        ] = None,
        timeframe: Annotated[
            str | None,
            Field(description="Filter by timeframe (recent, last_week, last_month)"),
        ] = None,
        query: Annotated[
            str | None, Field(description="Additional query string")
        ] = None,
    ) -> ToolResult:
        "List changesets from ServiceNow"
        return await dispatch(
            "list_changesets",
            {
                "limit": limit,
                "offset": offset,
                "state": state,
                "application": application,
                "developer": developer,
                "timeframe": timeframe,
                "query": query,
            },
        )

    @mcp.tool
    async def get_changeset_details(
        *,
        changeset_id: Annotated[str, Field(description="Changeset ID or sys_id")],
    ) -> ToolResult:
        "Get detailed information about a specific changeset"
        return await dispatch("get_changeset_details", {"changeset_id": changeset_id})

    @mcp.tool
    async def create_changeset(
        *,
        name: Annotated[str, Field(description="Name of the changeset")],
        description: Annotated[
            str | None, Field(description="Description of the changeset")
        ] = None,
        application: Annotated[
            str, Field(description="Application the changeset belongs to")
        ],
        developer: Annotated[
            str | None, Field(description="Developer responsible for the changeset")
        ] = None,
    ) -> ToolResult:
        "Create a new changeset in ServiceNow"
        return await dispatch(
            "create_changeset",
            {
                "name": name,
                "description": description,
                "application": application,
                "developer": developer,
            },
        )

    @mcp.tool
    async def update_changeset(
        *,
        changeset_id: Annotated[str, Field(description="Changeset ID or sys_id")],
        name: Annotated[str | None, Field(description="Name of the changeset")] = None,
        description: Annotated[
            str | None, Field(description="Description of the changeset")
        ] = None,
        state: Annotated[
            str | None, Field(description="State of the changeset")
        ] = None,
        developer: Annotated[
            str | None, Field(description="Developer responsible for the changeset")
        ] = None,
    ) -> ToolResult:
        "Update an existing changeset in ServiceNow"
        return await dispatch(
            "update_changeset",
            {
                "changeset_id": changeset_id,
                "name": name,
                "description": description,
                "state": state,
                "developer": developer,
            },
        )

    @mcp.tool
    async def commit_changeset(
        *,
        changeset_id: Annotated[str, Field(description="Changeset ID or sys_id")],
        commit_message: Annotated[
            str | None, Field(description="Commit message")
        ] = None,
    ) -> ToolResult:
        "Commit a changeset in ServiceNow"
        return await dispatch(
            "commit_changeset",
            {"changeset_id": changeset_id, "commit_message": commit_message},
        )

    @mcp.tool
    async def publish_changeset(
        *,
        changeset_id: Annotated[str, Field(description="Changeset ID or sys_id")],
        publish_notes: Annotated[
            str | None, Field(description="Notes for publishing")
        ] = None,
    ) -> ToolResult:
        "Publish a changeset in ServiceNow"
        return await dispatch(
            "publish_changeset",
            {"changeset_id": changeset_id, "publish_notes": publish_notes},
        )

    @mcp.tool
    async def add_file_to_changeset(
        *,
        changeset_id: Annotated[str, Field(description="Changeset ID or sys_id")],
        file_path: Annotated[str, Field(description="Path of the file to add")],
        file_content: Annotated[str, Field(description="Content of the file")],
    ) -> ToolResult:
        "Add a file to a changeset in ServiceNow"
        return await dispatch(
            "add_file_to_changeset",
            {
                "changeset_id": changeset_id,
                "file_path": file_path,
                "file_content": file_content,
            },
        )

    return (
        list_changesets,
        get_changeset_details,
        create_changeset,
        update_changeset,
        commit_changeset,
        publish_changeset,
        add_file_to_changeset,
    )
