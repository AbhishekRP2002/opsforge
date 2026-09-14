"""Darwinbox core tool declarations."""

from typing import Annotated, Any, NotRequired

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import ConfigDict, Field, with_config
from pydantic.experimental.missing_sentinel import MISSING
from typing_extensions import TypedDict


@with_config(ConfigDict(extra="allow"))
class DeactivateEmployeeEmployeesItem(TypedDict):
    employee_id: NotRequired[str]
    deactivate_type: NotRequired[str]
    deactivate_reason: NotRequired[str]
    date_of_resignation: NotRequired[str]
    date_of_exit: NotRequired[str]


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_employee_details(
        *,
        employee_ids: Annotated[
            list[str],
            Field(
                description="Array of employee IDs to fetch details for specific employees (use array with single ID for one employee)"
            ),
        ]
        | MISSING = MISSING,
        last_modified: Annotated[
            str,
            Field(
                description="ISO date string (DD-MM-YYYY HH:mm:ss) to fetch employees modified after this timestamp"
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Retrieve comprehensive employee information with flexible filtering options. Can fetch all employees, specific employees by IDs, or employees modified after a certain date."
        return await dispatch(
            "get_employee_details",
            {
                key: value
                for key, value in {
                    "employee_ids": employee_ids,
                    "last_modified": last_modified,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def update_employee(
        *,
        employee_data: Annotated[
            dict[str, Any],
            Field(description="Employee data object containing fields to update"),
        ],
    ) -> ToolResult:
        "Update employee information including personal details, work information, and other employee-related data."
        return await dispatch("update_employee", {"employee_data": employee_data})

    @mcp.tool
    async def get_employee_history(
        *,
        from_: Annotated[
            str, Field(description="Start date in DD-MM-YYYY format", alias="from")
        ],
        to: Annotated[str, Field(description="End date in DD-MM-YYYY format")],
        filter_on_effective_date: Annotated[
            float, Field(description="Filter flag for effective date (0 or 1)")
        ],
    ) -> ToolResult:
        "Retrieve historical changes and updates made to employee records within a specified date range."
        return await dispatch(
            "get_employee_history",
            {
                "from": from_,
                "to": to,
                "filter_on_effective_date": filter_on_effective_date,
            },
        )

    @mcp.tool
    async def download_personal_docs(
        *,
        employee_no: Annotated[
            str, Field(description="Employee number whose documents to download")
        ],
        for_: Annotated[
            str,
            Field(
                description="Document type to download (e.g., profile_pic, id_proof)",
                alias="for",
            ),
        ],
    ) -> ToolResult:
        "Download employee personal documents such as profile pictures, ID proofs, or other uploaded documents."
        return await dispatch(
            "download_personal_docs", {"employee_no": employee_no, "for": for_}
        )

    @mcp.tool
    async def get_separation_details(
        *,
        separation_status: Annotated[str, Field(description="Status of separation")],
        employee_ids: Annotated[list[str], Field(description="List of employee IDs")],
    ) -> ToolResult:
        "Get details about employee separations."
        return await dispatch(
            "get_separation_details",
            {"separation_status": separation_status, "employee_ids": employee_ids},
        )

    @mcp.tool
    async def add_employee(
        *,
        employees: Annotated[dict[str, Any], Field(description="Employee data to add")],
    ) -> ToolResult:
        "Add new employees to the system."
        return await dispatch("add_employee", {"employees": employees})

    @mcp.tool
    async def deactivate_employee(
        *,
        employees: Annotated[
            list[DeactivateEmployeeEmployeesItem],
            Field(description="List of employees to deactivate"),
        ],
    ) -> ToolResult:
        "Deactivate employees in the system."
        return await dispatch("deactivate_employee", {"employees": employees})

    @mcp.tool
    async def upload_profile_attachments(
        *,
        employee_no: Annotated[str, Field(description="Employee number")],
        section: Annotated[str, Field(description="Profile section")],
        section_attribute: Annotated[str, Field(description="Section attribute")],
        attachment: Annotated[str, Field(description="Attachment data")],
    ) -> ToolResult:
        "Upload attachments to employee profiles."
        return await dispatch(
            "upload_profile_attachments",
            {
                "employee_no": employee_no,
                "section": section,
                "section_attribute": section_attribute,
                "attachment": attachment,
            },
        )

    return (
        get_employee_details,
        update_employee,
        get_employee_history,
        download_personal_docs,
        get_separation_details,
        add_employee,
        deactivate_employee,
        upload_profile_attachments,
    )
