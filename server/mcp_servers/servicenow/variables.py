"""Servicenow variables tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def create_catalog_item_variable(
        *,
        catalog_item_id: Annotated[
            str, Field(description="The sys_id of the catalog item")
        ],
        name: Annotated[
            str, Field(description="The name of the variable (internal name)")
        ],
        type: Annotated[
            str,
            Field(
                description="The type of variable (e.g., string, integer, boolean, reference)"
            ),
        ],
        label: Annotated[str, Field(description="The display label for the variable")],
        mandatory: Annotated[
            bool, Field(description="Whether the variable is required")
        ] = False,
        help_text: Annotated[
            str | None, Field(description="Help text to display with the variable")
        ] = None,
        default_value: Annotated[
            str | None, Field(description="Default value for the variable")
        ] = None,
        description: Annotated[
            str | None, Field(description="Description of the variable")
        ] = None,
        order: Annotated[
            int | None, Field(description="Display order of the variable")
        ] = None,
        reference_table: Annotated[
            str | None,
            Field(description="For reference fields, the table to reference"),
        ] = None,
        reference_qualifier: Annotated[
            str | None,
            Field(
                description="For reference fields, the query to filter reference options"
            ),
        ] = None,
        max_length: Annotated[
            int | None, Field(description="Maximum length for string fields")
        ] = None,
        min: Annotated[
            int | None, Field(description="Minimum value for numeric fields")
        ] = None,
        max: Annotated[
            int | None, Field(description="Maximum value for numeric fields")
        ] = None,
    ) -> ToolResult:
        "Create a new catalog item variable"
        return await dispatch(
            "create_catalog_item_variable",
            {
                "catalog_item_id": catalog_item_id,
                "name": name,
                "type": type,
                "label": label,
                "mandatory": mandatory,
                "help_text": help_text,
                "default_value": default_value,
                "description": description,
                "order": order,
                "reference_table": reference_table,
                "reference_qualifier": reference_qualifier,
                "max_length": max_length,
                "min": min,
                "max": max,
            },
        )

    @mcp.tool
    async def list_catalog_item_variables(
        *,
        catalog_item_id: Annotated[
            str, Field(description="The sys_id of the catalog item")
        ],
        include_details: Annotated[
            bool,
            Field(
                description="Whether to include detailed information about each variable"
            ),
        ] = True,
        limit: Annotated[
            int | None, Field(description="Maximum number of variables to return")
        ] = None,
        offset: Annotated[
            int | None, Field(description="Offset for pagination")
        ] = None,
    ) -> ToolResult:
        "List catalog item variables"
        return await dispatch(
            "list_catalog_item_variables",
            {
                "catalog_item_id": catalog_item_id,
                "include_details": include_details,
                "limit": limit,
                "offset": offset,
            },
        )

    @mcp.tool
    async def update_catalog_item_variable(
        *,
        variable_id: Annotated[
            str, Field(description="The sys_id of the variable to update")
        ],
        label: Annotated[
            str | None, Field(description="The display label for the variable")
        ] = None,
        mandatory: Annotated[
            bool | None, Field(description="Whether the variable is required")
        ] = None,
        help_text: Annotated[
            str | None, Field(description="Help text to display with the variable")
        ] = None,
        default_value: Annotated[
            str | None, Field(description="Default value for the variable")
        ] = None,
        description: Annotated[
            str | None, Field(description="Description of the variable")
        ] = None,
        order: Annotated[
            int | None, Field(description="Display order of the variable")
        ] = None,
        reference_qualifier: Annotated[
            str | None,
            Field(
                description="For reference fields, the query to filter reference options"
            ),
        ] = None,
        max_length: Annotated[
            int | None, Field(description="Maximum length for string fields")
        ] = None,
        min: Annotated[
            int | None, Field(description="Minimum value for numeric fields")
        ] = None,
        max: Annotated[
            int | None, Field(description="Maximum value for numeric fields")
        ] = None,
    ) -> ToolResult:
        "Update a catalog item variable"
        return await dispatch(
            "update_catalog_item_variable",
            {
                "variable_id": variable_id,
                "label": label,
                "mandatory": mandatory,
                "help_text": help_text,
                "default_value": default_value,
                "description": description,
                "order": order,
                "reference_qualifier": reference_qualifier,
                "max_length": max_length,
                "min": min,
                "max": max,
            },
        )

    return (
        create_catalog_item_variable,
        list_catalog_item_variables,
        update_catalog_item_variable,
    )
