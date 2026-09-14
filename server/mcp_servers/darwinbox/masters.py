"""Darwinbox masters tool declarations."""

from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_position_master(
        *,
        status: Annotated[float, Field(description="Position status code")],
        need_to_hire: Annotated[
            float, Field(description="Flag for positions that need hiring (0 or 1)")
        ],
        employee_nos: Annotated[
            list[str], Field(description="List of employee numbers to filter positions")
        ],
    ) -> ToolResult:
        "Retrieve organizational position data including current positions, vacancies, and hiring needs."
        return await dispatch(
            "get_position_master",
            {
                "status": status,
                "need_to_hire": need_to_hire,
                "employee_nos": employee_nos,
            },
        )

    @mcp.tool
    async def get_forms_data(
        *,
        form_id: Annotated[str, Field(description="Form identifier")],
        type: Annotated[str, Field(description="Type of form")],
        form_type: Annotated[str, Field(description="Form type category")],
        from_: Annotated[str, Field(description="Start date", alias="from")],
        to: Annotated[str, Field(description="End date")],
    ) -> ToolResult:
        "Retrieve form data and submissions within a specified date range."
        return await dispatch(
            "get_forms_data",
            {
                "form_id": form_id,
                "type": type,
                "form_type": form_type,
                "from": from_,
                "to": to,
            },
        )

    @mcp.tool
    async def get_holiday_list(
        *,
        list: Annotated[dict[str, Any], Field(description="Holiday list parameters")],
    ) -> ToolResult:
        "Get list of holidays."
        return await dispatch("get_holiday_list", {"list": list})

    return (
        get_position_master,
        get_forms_data,
        get_holiday_list,
    )
