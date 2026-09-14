"""Erpnext accounting hr tool declarations."""

from typing import Annotated, Literal, NotRequired

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import ConfigDict, Field, with_config
from pydantic.experimental.missing_sentinel import MISSING
from typing_extensions import TypedDict


@with_config(ConfigDict(extra="allow"))
class ErpnextJournalEntryCreateAccountsItem(TypedDict):
    account: Annotated[str, Field(description="Account name")]
    debit_in_account_currency: NotRequired[
        Annotated[float, Field(description="Debit amount (0 if credit)")]
    ]
    credit_in_account_currency: NotRequired[
        Annotated[float, Field(description="Credit amount (0 if debit)")]
    ]


@with_config(ConfigDict(extra="allow"))
class ErpnextExpenseClaimCreateExpensesItem(TypedDict):
    expense_type: Annotated[str, Field(description="Expense type (e.g. Travel, Food)")]
    amount: Annotated[float, Field(description="Claimed amount")]
    description: NotRequired[
        Annotated[str, Field(description="Description of the expense (optional)")]
    ]


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def erpnext_account_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 50)")]
        | MISSING = MISSING,
        root_type: Annotated[
            Literal["Asset", "Liability", "Income", "Expense", "Equity"],
            Field(
                description="Filter by root type: Asset, Liability, Income, Expense, Equity"
            ),
        ]
        | MISSING = MISSING,
        is_group: Annotated[bool, Field(description="Filter by group accounts only")]
        | MISSING = MISSING,
        company: Annotated[str, Field(description="Filter by company")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Chart of Accounts. Filterable by root_type and is_group. Fields: name, account_name, account_type, root_type, parent_account, is_group. root_type values: Asset, Liability, Income, Expense, Equity."
        return await dispatch(
            "erpnext_account_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "root_type": root_type,
                    "is_group": is_group,
                    "company": company,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_journal_entry_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        voucher_type: Annotated[
            str,
            Field(
                description="Filter by voucher type (Journal Entry, Bank Entry, Cash Entry, etc.)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Journal Entries. Filterable by date range and voucher_type. Fields: name, voucher_type, posting_date, total_debit, total_credit, remark."
        return await dispatch(
            "erpnext_journal_entry_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "voucher_type": voucher_type,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_journal_entry_get(
        *,
        name: Annotated[str, Field(description="Journal Entry name (e.g. JV-00001)")],
    ) -> ToolResult:
        "Get a single Journal Entry by name (e.g. JV-00001). Returns full document with accounts."
        return await dispatch("erpnext_journal_entry_get", {"name": name})

    @mcp.tool
    async def erpnext_payment_entry_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        payment_type: Annotated[
            Literal["Receive", "Pay", "Internal Transfer"],
            Field(
                description="Filter by payment type: Receive, Pay, Internal Transfer"
            ),
        ]
        | MISSING = MISSING,
        party_type: Annotated[
            Literal["Customer", "Supplier", "Employee"],
            Field(
                description="Filter by party type (Customer, Supplier, Employee). Required when 'party' is set, so the party name/ID can be resolved against the right doctype."
            ),
        ]
        | MISSING = MISSING,
        party: Annotated[
            str,
            Field(
                description="Filter by party — ID or name (e.g. 'CUST-00001' or 'Acme Corp'). Requires 'party_type'."
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Payment Entries. Filterable by payment_type, party_type, date range. Fields: name, payment_type, party_type, party, posting_date, paid_amount, currency. payment_type values: Receive, Pay, Internal Transfer."
        return await dispatch(
            "erpnext_payment_entry_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "payment_type": payment_type,
                    "party_type": party_type,
                    "party": party,
                    "date_from": date_from,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_payment_entry_get(
        *,
        name: Annotated[str, Field(description="Payment Entry name (e.g. PE-00001)")],
    ) -> ToolResult:
        "Get a single Payment Entry by name (e.g. PE-00001). Returns full document including references."
        return await dispatch("erpnext_payment_entry_get", {"name": name})

    @mcp.tool
    async def erpnext_journal_entry_create(
        *,
        voucher_type: Annotated[
            str,
            Field(
                description="Journal entry type (Journal Entry, Bank Entry, Cash Entry, Credit Card Entry, etc.)"
            ),
        ],
        accounts: Annotated[
            list[ErpnextJournalEntryCreateAccountsItem],
            Field(
                description="Account entries: [{account, debit_in_account_currency, credit_in_account_currency}]"
            ),
        ],
        posting_date: Annotated[
            str, Field(description="Posting date YYYY-MM-DD (default: today)")
        ]
        | MISSING = MISSING,
        remark: Annotated[str, Field(description="Narration / remark")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Journal Entry. Requires voucher_type and accounts with debit/credit amounts. Total debits must equal total credits."
        return await dispatch(
            "erpnext_journal_entry_create",
            {
                key: value
                for key, value in {
                    "voucher_type": voucher_type,
                    "accounts": accounts,
                    "posting_date": posting_date,
                    "remark": remark,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_employee_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        department: Annotated[str, Field(description="Filter by department")]
        | MISSING = MISSING,
        status: Annotated[
            Literal["Active", "Inactive", "Suspended", "Left"],
            Field(description="Filter by status (Active, Inactive, Suspended, Left)"),
        ]
        | MISSING = MISSING,
        company: Annotated[str, Field(description="Filter by company")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Employees. Filterable by department, status. Fields: name, employee_name, designation, department, company, status, date_of_joining."
        return await dispatch(
            "erpnext_employee_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "department": department,
                    "status": status,
                    "company": company,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_employee_get(
        *,
        name: Annotated[
            str,
            Field(
                description="Employee name or ID (e.g. HR-EMP-00001) — a unique name resolves automatically"
            ),
        ],
    ) -> ToolResult:
        "Get a single Employee by name/ID (e.g. HR-EMP-00001). Returns all fields."
        return await dispatch("erpnext_employee_get", {"name": name})

    @mcp.tool
    async def erpnext_attendance_list(
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
        status: Annotated[
            Literal["Present", "Absent", "Half Day", "On Leave"],
            Field(description="Filter by status (Present, Absent, Half Day, On Leave)"),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Attendance records. Filterable by employee, date range. Fields: name, employee, employee_name, attendance_date, status."
        return await dispatch(
            "erpnext_attendance_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "employee": employee,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_leave_application_list(
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
        status: Annotated[
            Literal["Open", "Approved", "Rejected", "Cancelled"],
            Field(description="Filter by status (Open, Approved, Rejected, Cancelled)"),
        ]
        | MISSING = MISSING,
        leave_type: Annotated[
            str, Field(description="Filter by leave type (e.g. Sick Leave)")
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Leave Applications. Filterable by employee, status, leave_type. Fields: name, employee, employee_name, leave_type, from_date, to_date, status."
        return await dispatch(
            "erpnext_leave_application_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "employee": employee,
                    "status": status,
                    "leave_type": leave_type,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_leave_application_get(
        *,
        name: Annotated[str, Field(description="Leave Application name")],
    ) -> ToolResult:
        "Get a single Leave Application by name. Returns full document."
        return await dispatch("erpnext_leave_application_get", {"name": name})

    @mcp.tool
    async def erpnext_leave_application_create(
        *,
        employee: Annotated[
            str,
            Field(
                description="Employee name or ID (e.g. HR-EMP-00001) — a unique name resolves automatically"
            ),
        ],
        leave_type: Annotated[
            str, Field(description="Leave type (e.g. Sick Leave, Casual Leave)")
        ],
        from_date: Annotated[str, Field(description="Start date YYYY-MM-DD")],
        to_date: Annotated[str, Field(description="End date YYYY-MM-DD")],
        reason: Annotated[str, Field(description="Reason for leave (optional)")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Leave Application. Requires employee, leave_type, from_date, to_date. Dates in YYYY-MM-DD format."
        return await dispatch(
            "erpnext_leave_application_create",
            {
                key: value
                for key, value in {
                    "employee": employee,
                    "leave_type": leave_type,
                    "from_date": from_date,
                    "to_date": to_date,
                    "reason": reason,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_salary_slip_list(
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
        status: Annotated[
            Literal["Draft", "Submitted", "Cancelled"],
            Field(description="Filter by status (Draft, Submitted, Cancelled)"),
        ]
        | MISSING = MISSING,
        date_from: Annotated[
            str, Field(description="Start date filter YYYY-MM-DD (posting_date >=)")
        ]
        | MISSING = MISSING,
        date_to: Annotated[
            str, Field(description="End date filter YYYY-MM-DD (posting_date <=)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Salary Slips. Filterable by employee, status, date range. Fields: name, employee, employee_name, posting_date, start_date, end_date, gross_pay, net_pay, status."
        return await dispatch(
            "erpnext_salary_slip_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "employee": employee,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_salary_slip_get(
        *,
        name: Annotated[
            str,
            Field(description="Salary Slip ID (e.g. Salary Slip/HR-EMP-00001/00001)"),
        ],
    ) -> ToolResult:
        "Get a single Salary Slip by name/ID. Returns all fields including earnings and deductions."
        return await dispatch("erpnext_salary_slip_get", {"name": name})

    @mcp.tool
    async def erpnext_payroll_entry_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        company: Annotated[str, Field(description="Filter by company")]
        | MISSING = MISSING,
        status: Annotated[
            Literal["Draft", "Submitted", "Cancelled"],
            Field(description="Filter by status (Draft, Submitted, Cancelled)"),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Payroll Entries. Filterable by company, status. Fields: name, company, posting_date, payroll_frequency, status."
        return await dispatch(
            "erpnext_payroll_entry_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "company": company,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_expense_claim_list(
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
        status: Annotated[
            Literal["Draft", "Submitted", "Cancelled"],
            Field(description="Filter by status (Draft, Submitted, Cancelled)"),
        ]
        | MISSING = MISSING,
        approval_status: Annotated[
            Literal["Pending", "Approved", "Rejected"],
            Field(
                description="Filter by approval status (Pending, Approved, Rejected)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Expense Claims. Filterable by employee, status, approval_status. Fields: name, employee, employee_name, posting_date, total_claimed_amount, status, approval_status."
        return await dispatch(
            "erpnext_expense_claim_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "employee": employee,
                    "status": status,
                    "approval_status": approval_status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_expense_claim_create(
        *,
        employee: Annotated[
            str,
            Field(
                description="Employee name or ID (e.g. HR-EMP-00001) — a unique name resolves automatically"
            ),
        ],
        expenses: Annotated[
            list[ErpnextExpenseClaimCreateExpensesItem],
            Field(description="List of expense line items"),
        ],
        posting_date: Annotated[
            str,
            Field(description="Posting date YYYY-MM-DD (optional, defaults to today)"),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Expense Claim. Requires employee and expenses array. Each expense item maps to the Expense Claim Detail child table."
        return await dispatch(
            "erpnext_expense_claim_create",
            {
                key: value
                for key, value in {
                    "employee": employee,
                    "expenses": expenses,
                    "posting_date": posting_date,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_leave_balance(
        *,
        employee: Annotated[
            str,
            Field(
                description="Employee ID or name (e.g. 'HR-EMP-00001' or 'John Doe')"
            ),
        ],
    ) -> ToolResult:
        "Get leave balance (allocations) for an employee. Returns Leave Allocations with leave_type, total_leaves_allocated, new_leaves_allocated."
        return await dispatch("erpnext_leave_balance", {"employee": employee})

    return (
        erpnext_account_list,
        erpnext_journal_entry_list,
        erpnext_journal_entry_get,
        erpnext_payment_entry_list,
        erpnext_payment_entry_get,
        erpnext_journal_entry_create,
        erpnext_employee_list,
        erpnext_employee_get,
        erpnext_attendance_list,
        erpnext_leave_application_list,
        erpnext_leave_application_get,
        erpnext_leave_application_create,
        erpnext_salary_slip_list,
        erpnext_salary_slip_get,
        erpnext_payroll_entry_list,
        erpnext_expense_claim_list,
        erpnext_expense_claim_create,
        erpnext_leave_balance,
    )
