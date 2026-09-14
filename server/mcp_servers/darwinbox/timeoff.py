"""Darwinbox timeoff tool declarations."""

from typing import Annotated, Any, Literal, NotRequired

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import ConfigDict, Field, with_config
from pydantic.experimental.missing_sentinel import MISSING
from typing_extensions import TypedDict


@with_config(ConfigDict(extra="allow"))
class ApplyLeaveDataItem(TypedDict):
    employee_no: Annotated[str, Field(description="Employee number")]
    leave_name: Annotated[str, Field(description="Type of leave")]
    message: Annotated[str, Field(description="Leave reason/message")]
    from_date: Annotated[str, Field(description="Leave start date (DD-MM-YYYY)")]
    to_date: Annotated[str, Field(description="Leave end date (DD-MM-YYYY)")]
    is_half_day: Annotated[
        Literal["Yes", "No"], Field(description="Whether this is a half day leave")
    ]
    is_firsthalf_secondhalf: NotRequired[
        Annotated[
            Literal["1", "2"],
            Field(
                description="For half day leaves, specify 1 for first half or 2 for second half"
            ),
        ]
    ]
    is_paid_or_unpaid: Annotated[
        Literal["paid", "unpaid"],
        Field(description="Whether this is a paid or unpaid leave"),
    ]
    revoke_leave: Annotated[
        Literal["Yes", "No"], Field(description="Whether to revoke this leave")
    ]
    revoke_reason: NotRequired[
        Annotated[
            str,
            Field(
                description="Reason for revoking the leave (required if revoke_leave is Yes)"
            ),
        ]
    ]


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def approve_leave(
        *,
        leave_id: Annotated[
            str, Field(description="ID of the leave request to approve/reject")
        ],
        employee_no: Annotated[str, Field(description="Employee number")],
        action: Annotated[str, Field(description="Action to take (approve/reject)")],
        manager_message: Annotated[
            str, Field(description="Optional message from manager")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Approve or reject existing leave requests."
        return await dispatch(
            "approve_leave",
            {
                key: value
                for key, value in {
                    "leave_id": leave_id,
                    "employee_no": employee_no,
                    "action": action,
                    "manager_message": manager_message,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def get_leave_action_history(
        *,
        history: Annotated[
            dict[str, Any], Field(description="Leave action history parameters")
        ],
    ) -> ToolResult:
        "Get history of leave actions."
        return await dispatch("get_leave_action_history", {"history": history})

    @mcp.tool
    async def apply_leave(
        *,
        data: list[ApplyLeaveDataItem],
    ) -> ToolResult:
        "Apply for a new leave."
        return await dispatch("apply_leave", {"data": data})

    @mcp.tool
    async def get_leave_balance(
        *,
        ignore_rounding: Annotated[
            str,
            Field(
                description="Whether to ignore rounding in balance calculation (0 or 1)"
            ),
        ] = "0",
        employee_nos: Annotated[
            list[str],
            Field(description="List of employee numbers to fetch leave balances for"),
        ],
    ) -> ToolResult:
        "Retrieve available leave types and their balances for specified employees. Use this API before applying for leave to get the list of valid leave types."
        return await dispatch(
            "get_leave_balance",
            {"ignore_rounding": ignore_rounding, "employee_nos": employee_nos},
        )

    return (
        approve_leave,
        get_leave_action_history,
        apply_leave,
        get_leave_balance,
    )
