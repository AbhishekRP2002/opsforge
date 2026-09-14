"""Darwinbox attendance tool declarations."""

from typing import Annotated, Any, NotRequired

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import ConfigDict, Field, with_config
from typing_extensions import TypedDict


@with_config(ConfigDict(extra="allow"))
class RecordAttendancePunchesAttendanceValueItem(TypedDict):
    id: NotRequired[str]
    timestamp: NotRequired[
        Annotated[str, Field(description="YYYY-MM-DD HH:mm:ss format")]
    ]
    machineid: NotRequired[str]
    status: NotRequired[str]


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_monthly_attendance(
        *,
        emp_number_list: Annotated[
            list[str],
            Field(description="List of employee numbers to fetch attendance for"),
        ],
        from_date: Annotated[str, Field(description="Start date in YYYY-MM-DD format")],
        to_date: Annotated[str, Field(description="End date in YYYY-MM-DD format")],
        month: Annotated[str, Field(description="Month in YYYY-MM format")],
    ) -> ToolResult:
        "Retrieve detailed monthly attendance records for specified employees, including check-in/out times and attendance status."
        return await dispatch(
            "get_monthly_attendance",
            {
                "emp_number_list": emp_number_list,
                "from_date": from_date,
                "to_date": to_date,
                "month": month,
            },
        )

    @mcp.tool
    async def record_attendance_punches(
        *,
        attendance: Annotated[
            dict[str, list[RecordAttendancePunchesAttendanceValueItem]],
            Field(description="Map of employee IDs to their attendance punch records"),
        ],
    ) -> ToolResult:
        "Record employee attendance punches with timestamp and location details. Supports both check-in and check-out records."
        return await dispatch("record_attendance_punches", {"attendance": attendance})

    @mcp.tool
    async def get_daily_attendance(
        *,
        emp_number_list: Annotated[
            list[str], Field(description="List of employee numbers")
        ],
        from_date: Annotated[str, Field(description="Start date")],
        to_date: Annotated[str, Field(description="End date")],
    ) -> ToolResult:
        "Get daily attendance records for employees."
        return await dispatch(
            "get_daily_attendance",
            {
                "emp_number_list": emp_number_list,
                "from_date": from_date,
                "to_date": to_date,
            },
        )

    @mcp.tool
    async def get_attendance_roster(
        *,
        emp_number_list: Annotated[
            list[str], Field(description="List of employee numbers")
        ],
        from_date: Annotated[str, Field(description="Start date")],
        to_date: Annotated[str, Field(description="End date")],
    ) -> ToolResult:
        "Get attendance roster information."
        return await dispatch(
            "get_attendance_roster",
            {
                "emp_number_list": emp_number_list,
                "from_date": from_date,
                "to_date": to_date,
            },
        )

    @mcp.tool
    async def record_backdated_attendance(
        *,
        attendance: Annotated[
            dict[str, Any], Field(description="Backdated attendance data")
        ],
    ) -> ToolResult:
        "Record backdated attendance entries."
        return await dispatch("record_backdated_attendance", {"attendance": attendance})

    return (
        get_monthly_attendance,
        record_attendance_punches,
        get_daily_attendance,
        get_attendance_roster,
        record_backdated_attendance,
    )
