"""Finite accounting and HR records; no external payroll or accounting execution."""

from . import erpnext_store as store
from .erpnext_commerce import create_master, mutation
from .erpnext_projects import get_document


def listing(
    kind,
    fields,
    exact=(),
    start="posting_date",
    end="posting_date",
    order="modified desc",
    default=20,
    employee=False,
):
    @store.handler
    def listed(db, args, step, clock):
        filters = [[field, "=", args[field]] for field in exact if field in args]
        if employee and args.get("employee"):
            filters.append(
                [
                    "employee",
                    "=",
                    store.resolve(db, "Employee", args["employee"], "employee_name"),
                ]
            )
        if args.get("date_from"):
            filters.append([start, ">=", args["date_from"]])
        if args.get("date_to"):
            filters.append([end, "<=", args["date_to"]])
        docs = store.select(
            db,
            kind,
            fields=fields.split(),
            filters=filters,
            limit=args.get("limit", default),
            order_by=order,
        )
        return {"doctype": kind, "count": len(docs), "data": docs}

    return listed


@store.handler
def payment_list(db, args, step, clock):
    filters = [
        [field, "=", args[field]]
        for field in ("payment_type", "party_type")
        if args.get(field)
    ]
    if args.get("party"):
        kind = store.text(args.get("party_type"), "party_type")
        labels = {
            "Customer": "customer_name",
            "Supplier": "supplier_name",
            "Employee": "employee_name",
        }
        if kind not in labels:
            raise store.BusinessError("Unsupported party_type")
        filters.append(
            ["party", "=", store.resolve(db, kind, args["party"], labels[kind])]
        )
    if args.get("date_from"):
        filters.append(["posting_date", ">=", args["date_from"]])
    docs = store.select(
        db,
        "Payment Entry",
        fields=[
            "name",
            "payment_type",
            "party_type",
            "party",
            "posting_date",
            "paid_amount",
            "currency",
        ],
        filters=filters,
        limit=args.get("limit"),
    )
    return {"doctype": "Payment Entry", "count": len(docs), "data": docs}


@store.handler
def employee_get(db, args, step, clock):
    name = store.resolve(db, "Employee", args["name"], "employee_name", partial=False)
    return {"data": store.get(db, "Employee", name)}


def employee_create(kind):
    @store.handler
    def created(db, args, step, clock):
        data = dict(args)
        data["employee"] = store.resolve(
            db, "Employee", args["employee"], "employee_name", partial=False
        )
        if kind == "Expense Claim":
            data["expenses"] = [
                {
                    "expense_type": row.get("expense_type"),
                    "amount": row.get("amount"),
                    "description": row.get("description", ""),
                }
                for row in args["expenses"]
            ]
        return mutation(store.create(db, kind, data, clock), "created")

    return created


@store.handler
def leave_balance(db, args, step, clock):
    employee = store.resolve(db, "Employee", args["employee"], "employee_name")
    docs = store.select(
        db,
        "Leave Allocation",
        fields=[
            "name",
            "leave_type",
            "total_leaves_allocated",
            "new_leaves_allocated",
            "from_date",
            "to_date",
        ],
        filters=[["employee", "=", employee], ["docstatus", "=", 1]],
        limit=50,
        order_by="leave_type asc",
    )
    return {
        "doctype": "Leave Allocation",
        "employee": args["employee"],
        "count": len(docs),
        "data": docs,
    }


HANDLERS = {
    "erpnext_account_list": listing(
        "Account",
        "name account_name account_type root_type parent_account is_group",
        ("root_type", "is_group", "company"),
        order="name asc",
        default=50,
    ),
    "erpnext_journal_entry_list": listing(
        "Journal Entry",
        "name voucher_type posting_date total_debit total_credit remark",
        ("voucher_type",),
    ),
    "erpnext_journal_entry_get": get_document("Journal Entry"),
    "erpnext_journal_entry_create": create_master("Journal Entry"),
    "erpnext_payment_entry_list": payment_list,
    "erpnext_payment_entry_get": get_document("Payment Entry"),
    "erpnext_employee_list": listing(
        "Employee",
        "name employee_name designation department company status date_of_joining",
        ("department", "status", "company"),
    ),
    "erpnext_employee_get": employee_get,
    "erpnext_attendance_list": listing(
        "Attendance",
        "name employee employee_name attendance_date status",
        ("status",),
        "attendance_date",
        "attendance_date",
        "attendance_date desc",
        employee=True,
    ),
    "erpnext_leave_application_list": listing(
        "Leave Application",
        "name employee employee_name leave_type from_date to_date status",
        ("status", "leave_type"),
        "from_date",
        "to_date",
        employee=True,
    ),
    "erpnext_leave_application_get": get_document("Leave Application"),
    "erpnext_leave_application_create": employee_create("Leave Application"),
    "erpnext_salary_slip_list": listing(
        "Salary Slip",
        "name employee employee_name posting_date start_date end_date gross_pay net_pay status",
        ("status",),
        order="posting_date desc",
        employee=True,
    ),
    "erpnext_salary_slip_get": get_document("Salary Slip"),
    "erpnext_payroll_entry_list": listing(
        "Payroll Entry",
        "name company posting_date payroll_frequency status",
        ("company", "status"),
        order="posting_date desc",
    ),
    "erpnext_expense_claim_list": listing(
        "Expense Claim",
        "name employee employee_name posting_date total_claimed_amount status approval_status",
        ("status", "approval_status"),
        employee=True,
    ),
    "erpnext_expense_claim_create": employee_create("Expense Claim"),
    "erpnext_leave_balance": leave_balance,
}
