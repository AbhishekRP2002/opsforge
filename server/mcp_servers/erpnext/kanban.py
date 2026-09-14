"""Erpnext kanban tool declarations."""

from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field
from pydantic.experimental.missing_sentinel import MISSING


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def erpnext_kanban_get_board(
        *,
        doctype: Annotated[
            Literal["Task", "Opportunity", "Issue"],
            Field(description="Kanban-enabled ERPNext DocType"),
        ],
        limit: Annotated[float, Field(description="Page size (default 50)")]
        | MISSING = MISSING,
        offset: Annotated[float, Field(description="Pagination offset (default 0)")]
        | MISSING = MISSING,
        project: Annotated[str, Field(description="Optional Task project filter")]
        | MISSING = MISSING,
        priority: Annotated[
            Literal["Low", "Medium", "High", "Urgent"],
            Field(description="Optional Task priority filter"),
        ]
        | MISSING = MISSING,
        status: Annotated[
            Literal["Open", "Replied", "Quotation", "Converted", "Closed", "Lost"],
            Field(description="Optional Opportunity status filter"),
        ]
        | MISSING = MISSING,
        opportunity_owner: Annotated[
            str, Field(description="Optional Opportunity owner filter")
        ]
        | MISSING = MISSING,
        party_name: Annotated[
            str, Field(description="Optional Opportunity party filter")
        ]
        | MISSING = MISSING,
        customer: Annotated[str, Field(description="Optional Issue customer filter")]
        | MISSING = MISSING,
        raised_by: Annotated[
            str, Field(description="Optional Issue reporter email filter")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Get a normalized kanban board for a supported ERPNext DocType. Supports Task, Opportunity, and Issue, with pagination and MCP App metadata."
        return await dispatch(
            "erpnext_kanban_get_board",
            {
                key: value
                for key, value in {
                    "doctype": doctype,
                    "limit": limit,
                    "offset": offset,
                    "project": project,
                    "priority": priority,
                    "status": status,
                    "opportunity_owner": opportunity_owner,
                    "party_name": party_name,
                    "customer": customer,
                    "raised_by": raised_by,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_kanban_move_card(
        *,
        doctype: Annotated[
            Literal["Task", "Opportunity", "Issue"],
            Field(description="Kanban-enabled ERPNext DocType"),
        ],
        card_id: Annotated[str, Field(description="Card/document identifier")],
        from_column: Annotated[str, Field(description="Source column identifier")],
        to_column: Annotated[str, Field(description="Destination column identifier")],
    ) -> ToolResult:
        "Move a kanban card for a supported ERPNext DocType. Returns structured success or business error details for MCP App reconciliation."
        return await dispatch(
            "erpnext_kanban_move_card",
            {
                "doctype": doctype,
                "card_id": card_id,
                "from_column": from_column,
                "to_column": to_column,
            },
        )

    return (
        erpnext_kanban_get_board,
        erpnext_kanban_move_card,
    )
