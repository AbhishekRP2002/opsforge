"""Servicenow scripts tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_script_includes(
        *,
        limit: Annotated[
            int, Field(description="Maximum number of script includes to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        active: Annotated[
            bool | None, Field(description="Filter by active status")
        ] = None,
        client_callable: Annotated[
            bool | None, Field(description="Filter by client callable status")
        ] = None,
        query: Annotated[
            str | None, Field(description="Search query for script includes")
        ] = None,
    ) -> ToolResult:
        "List script includes from ServiceNow"
        return await dispatch(
            "list_script_includes",
            {
                "limit": limit,
                "offset": offset,
                "active": active,
                "client_callable": client_callable,
                "query": query,
            },
        )

    @mcp.tool
    async def get_script_include(
        *,
        script_include_id: Annotated[
            str, Field(description="Script include ID or name")
        ],
    ) -> ToolResult:
        "Get a specific script include from ServiceNow"
        return await dispatch(
            "get_script_include", {"script_include_id": script_include_id}
        )

    @mcp.tool
    async def create_script_include(
        *,
        name: Annotated[str, Field(description="Name of the script include")],
        script: Annotated[str, Field(description="Script content")],
        description: Annotated[
            str | None, Field(description="Description of the script include")
        ] = None,
        api_name: Annotated[
            str | None, Field(description="API name of the script include")
        ] = None,
        client_callable: Annotated[
            bool, Field(description="Whether the script include is client callable")
        ] = False,
        active: Annotated[
            bool, Field(description="Whether the script include is active")
        ] = True,
        access: Annotated[
            str, Field(description="Access level of the script include")
        ] = "package_private",
    ) -> ToolResult:
        "Create a new script include in ServiceNow"
        return await dispatch(
            "create_script_include",
            {
                "name": name,
                "script": script,
                "description": description,
                "api_name": api_name,
                "client_callable": client_callable,
                "active": active,
                "access": access,
            },
        )

    @mcp.tool
    async def update_script_include(
        *,
        script_include_id: Annotated[
            str, Field(description="Script include ID or name")
        ],
        script: Annotated[str | None, Field(description="Script content")] = None,
        description: Annotated[
            str | None, Field(description="Description of the script include")
        ] = None,
        api_name: Annotated[
            str | None, Field(description="API name of the script include")
        ] = None,
        client_callable: Annotated[
            bool | None,
            Field(description="Whether the script include is client callable"),
        ] = None,
        active: Annotated[
            bool | None, Field(description="Whether the script include is active")
        ] = None,
        access: Annotated[
            str | None, Field(description="Access level of the script include")
        ] = None,
    ) -> ToolResult:
        "Update an existing script include in ServiceNow"
        return await dispatch(
            "update_script_include",
            {
                "script_include_id": script_include_id,
                "script": script,
                "description": description,
                "api_name": api_name,
                "client_callable": client_callable,
                "active": active,
                "access": access,
            },
        )

    @mcp.tool
    async def delete_script_include(
        *,
        script_include_id: Annotated[
            str, Field(description="Script include ID or name")
        ],
    ) -> ToolResult:
        "Delete a script include in ServiceNow"
        return await dispatch(
            "delete_script_include", {"script_include_id": script_include_id}
        )

    return (
        list_script_includes,
        get_script_include,
        create_script_include,
        update_script_include,
        delete_script_include,
    )
