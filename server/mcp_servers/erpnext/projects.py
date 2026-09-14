"""Erpnext projects tool declarations."""

from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field
from pydantic.experimental.missing_sentinel import MISSING


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def erpnext_doc_assign(
        *,
        doctype: Annotated[
            str,
            Field(
                description="ERPNext DocType name (e.g. 'Task', 'Issue', 'Opportunity')"
            ),
        ],
        name: Annotated[
            str, Field(description="Document name/ID (e.g. 'TASK-2026-00001')")
        ],
        assign_to: Annotated[
            Annotated[str, Field(min_length=1)]
            | Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1)],
            Field(description="User email or non-empty array of user emails to assign"),
        ],
        notify_user: Annotated[
            bool,
            Field(
                description="Frappe always sends its native assignment notification (v15 has no per-call suppression), so only true is accepted (default true)"
            ),
        ] = True,
        assignment_description: Annotated[
            str, Field(description="Description for the native ToDo assignment")
        ]
        | MISSING = MISSING,
        assignment_priority: Annotated[
            Literal["Low", "Medium", "High"], Field(description="Native ToDo priority")
        ]
        | MISSING = MISSING,
        assignment_date: Annotated[
            str,
            Field(
                pattern="^\\d{4}-\\d{2}-\\d{2}$",
                description="Native ToDo date YYYY-MM-DD",
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Assign any ERPNext document to one or more users through Frappe's native assignment workflow (per-assignee ToDo, _assign sync, permission sharing, native notifications). Works on any DocType (e.g. 'Task', 'Issue', 'Opportunity'). Idempotent: re-assigning an already-assigned user returns the existing ToDo without re-notifying."
        return await dispatch(
            "erpnext_doc_assign",
            {
                key: value
                for key, value in {
                    "doctype": doctype,
                    "name": name,
                    "assign_to": assign_to,
                    "notify_user": notify_user,
                    "assignment_description": assignment_description,
                    "assignment_priority": assignment_priority,
                    "assignment_date": assignment_date,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_doc_unassign(
        *,
        doctype: Annotated[
            str,
            Field(
                description="ERPNext DocType name (e.g. 'Task', 'Issue', 'Opportunity')"
            ),
        ],
        name: Annotated[
            str, Field(description="Document name/ID (e.g. 'TASK-2026-00001')")
        ],
        assign_to: Annotated[
            str,
            Field(
                min_length=1,
                description="User email whose assignment should be removed",
            ),
        ],
    ) -> ToolResult:
        "Remove one user's assignment from any ERPNext document through Frappe's native workflow (closes the user's ToDo and resyncs _assign). Works on any DocType. Pass one user per call. Idempotent: removing a user who is not assigned is a no-op on the Frappe side."
        return await dispatch(
            "erpnext_doc_unassign",
            {"doctype": doctype, "name": name, "assign_to": assign_to},
        )

    @mcp.tool
    async def erpnext_project_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        status: Annotated[
            Literal["Open", "Completed", "Cancelled"],
            Field(description="Filter by status (Open, Completed, Cancelled)"),
        ]
        | MISSING = MISSING,
        company: Annotated[str, Field(description="Filter by company")]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Projects. Filterable by status. Fields: name, project_name, status, percent_complete, expected_start_date, expected_end_date, estimated_costing."
        return await dispatch(
            "erpnext_project_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "status": status,
                    "company": company,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_project_get(
        *,
        name: Annotated[str, Field(description="Project name")],
    ) -> ToolResult:
        "Get a single Project by name. Returns full document including tasks summary."
        return await dispatch("erpnext_project_get", {"name": name})

    @mcp.tool
    async def erpnext_task_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        project: Annotated[str, Field(description="Filter by project name")]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Open, Working, Pending Review, Overdue, Completed, Cancelled)"
            ),
        ]
        | MISSING = MISSING,
        priority: Annotated[
            Literal["Low", "Medium", "High", "Urgent"],
            Field(description="Filter by priority (Low, Medium, High, Urgent)"),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Tasks. Filterable by project, status, priority. Fields: name, subject, project, status, priority, exp_start_date, exp_end_date, progress."
        return await dispatch(
            "erpnext_task_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "project": project,
                    "status": status,
                    "priority": priority,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_task_create(
        *,
        project: Annotated[str, Field(description="Project name")],
        subject: Annotated[str, Field(description="Task subject/title")],
        status: Annotated[
            Literal[
                "Open", "Working", "Pending Review", "Overdue", "Completed", "Cancelled"
            ],
            Field(description="Task status (default: Open)"),
        ]
        | MISSING = MISSING,
        priority: Annotated[
            Literal["Low", "Medium", "High", "Urgent"],
            Field(description="Task priority (default: Medium)"),
        ]
        | MISSING = MISSING,
        exp_start_date: Annotated[
            str, Field(description="Expected start date YYYY-MM-DD")
        ]
        | MISSING = MISSING,
        exp_end_date: Annotated[str, Field(description="Expected end date YYYY-MM-DD")]
        | MISSING = MISSING,
        assign_to: Annotated[
            Annotated[str, Field(min_length=1)]
            | Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1)],
            Field(description="User email or non-empty array of user emails to assign"),
        ]
        | MISSING = MISSING,
        notify_user: Annotated[
            bool,
            Field(
                description="Frappe always sends its native assignment notification (v15 has no per-call suppression), so only true is accepted (default true)"
            ),
        ] = True,
        assignment_description: Annotated[
            str, Field(description="Description for the native ToDo assignment")
        ]
        | MISSING = MISSING,
        assignment_priority: Annotated[
            Literal["Low", "Medium", "High"], Field(description="Native ToDo priority")
        ]
        | MISSING = MISSING,
        assignment_date: Annotated[
            str,
            Field(
                pattern="^\\d{4}-\\d{2}-\\d{2}$",
                description="Native ToDo date YYYY-MM-DD",
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Task in a project. Requires project and subject. Dates in YYYY-MM-DD format. Use assign_to for Frappe's native assignment workflow; native notifications are sent to assigned users."
        return await dispatch(
            "erpnext_task_create",
            {
                key: value
                for key, value in {
                    "project": project,
                    "subject": subject,
                    "status": status,
                    "priority": priority,
                    "exp_start_date": exp_start_date,
                    "exp_end_date": exp_end_date,
                    "assign_to": assign_to,
                    "notify_user": notify_user,
                    "assignment_description": assignment_description,
                    "assignment_priority": assignment_priority,
                    "assignment_date": assignment_date,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_task_get(
        *,
        name: Annotated[str, Field(description="Task name (e.g. TASK-00001)")],
    ) -> ToolResult:
        "Get a single Task by name. Returns full document including description and dependencies."
        return await dispatch("erpnext_task_get", {"name": name})

    @mcp.tool
    async def erpnext_task_update(
        *,
        name: Annotated[str, Field(description="Task name (e.g. TASK-00001)")],
        status: Annotated[
            Literal[
                "Open", "Working", "Pending Review", "Overdue", "Completed", "Cancelled"
            ],
            Field(description="New status"),
        ]
        | MISSING = MISSING,
        priority: Annotated[
            Literal["Low", "Medium", "High", "Urgent"],
            Field(description="New priority"),
        ]
        | MISSING = MISSING,
        progress: Annotated[float, Field(description="Completion percentage (0-100)")]
        | MISSING = MISSING,
        exp_end_date: Annotated[
            str, Field(description="New expected end date YYYY-MM-DD")
        ]
        | MISSING = MISSING,
        description: Annotated[str, Field(description="New task description")]
        | MISSING = MISSING,
        assign_to: Annotated[
            Annotated[str, Field(min_length=1)]
            | Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1)],
            Field(description="User email or non-empty array of user emails to assign"),
        ]
        | MISSING = MISSING,
        notify_user: Annotated[
            bool,
            Field(
                description="Frappe always sends its native assignment notification (v15 has no per-call suppression), so only true is accepted (default true)"
            ),
        ] = True,
        assignment_description: Annotated[
            str, Field(description="Description for the native ToDo assignment")
        ]
        | MISSING = MISSING,
        assignment_priority: Annotated[
            Literal["Low", "Medium", "High"], Field(description="Native ToDo priority")
        ]
        | MISSING = MISSING,
        assignment_date: Annotated[
            str,
            Field(
                pattern="^\\d{4}-\\d{2}-\\d{2}$",
                description="Native ToDo date YYYY-MM-DD",
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Update an existing Task. Pass only the fields you want to change. Commonly used to change status, progress, or dates. Use assign_to for Frappe's native assignment workflow; native notifications are sent to assigned users."
        return await dispatch(
            "erpnext_task_update",
            {
                key: value
                for key, value in {
                    "name": name,
                    "status": status,
                    "priority": priority,
                    "progress": progress,
                    "exp_end_date": exp_end_date,
                    "description": description,
                    "assign_to": assign_to,
                    "notify_user": notify_user,
                    "assignment_description": assignment_description,
                    "assignment_priority": assignment_priority,
                    "assignment_date": assignment_date,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_timesheet_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        employee: Annotated[
            str,
            Field(
                description="Filter by employee ID or name (e.g. 'HR-EMP-00001' or 'John Doe')"
            ),
        ]
        | MISSING = MISSING,
        project: Annotated[str, Field(description="Filter by project name")]
        | MISSING = MISSING,
        status: Annotated[
            str, Field(description="Filter by status (Draft, Submitted, Cancelled)")
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Timesheets. Filterable by employee, project. Fields: name, employee, start_date, end_date, status, total_hours."
        return await dispatch(
            "erpnext_timesheet_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "employee": employee,
                    "project": project,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_timesheet_get(
        *,
        name: Annotated[str, Field(description="Timesheet name")],
    ) -> ToolResult:
        "Get a single Timesheet by name. Returns full document with time log details."
        return await dispatch("erpnext_timesheet_get", {"name": name})

    @mcp.tool
    async def erpnext_project_create(
        *,
        project_name: Annotated[str, Field(description="Project name")],
        status: Annotated[
            Literal["Open", "Completed", "Cancelled"],
            Field(description="Initial status (default: Open)"),
        ]
        | MISSING = MISSING,
        expected_start_date: Annotated[
            str, Field(description="Expected start date YYYY-MM-DD")
        ]
        | MISSING = MISSING,
        expected_end_date: Annotated[
            str, Field(description="Expected end date YYYY-MM-DD")
        ]
        | MISSING = MISSING,
        estimated_costing: Annotated[float, Field(description="Budget estimate")]
        | MISSING = MISSING,
        company: Annotated[str, Field(description="Company name")] | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Project. Requires project_name. Optionally set expected_start_date and expected_end_date."
        return await dispatch(
            "erpnext_project_create",
            {
                key: value
                for key, value in {
                    "project_name": project_name,
                    "status": status,
                    "expected_start_date": expected_start_date,
                    "expected_end_date": expected_end_date,
                    "estimated_costing": estimated_costing,
                    "company": company,
                }.items()
                if value is not MISSING
            },
        )

    return (
        erpnext_doc_assign,
        erpnext_doc_unassign,
        erpnext_project_list,
        erpnext_project_get,
        erpnext_task_list,
        erpnext_task_create,
        erpnext_task_get,
        erpnext_task_update,
        erpnext_timesheet_list,
        erpnext_timesheet_get,
        erpnext_project_create,
    )
