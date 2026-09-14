import pytest

from .test_erpnext_operations import call, create
from .test_erpnext_operations import env as erpnext_fixture

env = erpnext_fixture


def test_balanced_journal_and_payment_party_resolution(env):
    debit = create(env, "Account", account_name="Cash", root_type="Asset")
    credit = create(env, "Account", account_name="Income", root_type="Income")
    journal, error = call(
        env,
        "journal_entry_create",
        voucher_type="Journal Entry",
        accounts=[
            {"account": debit["name"], "debit_in_account_currency": 12},
            {"account": credit["name"], "credit_in_account_currency": 12},
        ],
    )
    assert not error
    assert journal["data"]["total_debit"] == journal["data"]["total_credit"] == 12
    assert (
        call(env, "journal_entry_get", name=journal["data"]["name"])[0]["data"][
            "total_debit"
        ]
        == 12
    )
    assert call(env, "journal_entry_list")[0]["count"] == 1
    assert (
        call(env, "account_list", root_type="Asset")[0]["data"][0]["name"]
        == debit["name"]
    )
    customer = create(env, "Customer", customer_name="Acme")
    payment = create(
        env,
        "Payment Entry",
        payment_type="Receive",
        party_type="Customer",
        party=customer["name"],
        paid_amount=12,
    )
    assert (
        call(env, "payment_entry_get", name=payment["name"])[0]["data"]["paid_amount"]
        == 12
    )
    assert (
        call(env, "payment_entry_list", party_type="Customer", party="Acme")[0]["count"]
        == 1
    )
    for amount in (True, -1, [], {}):
        assert call(
            env,
            "journal_entry_create",
            voucher_type="Journal Entry",
            accounts=[{"account": debit["name"], "debit_in_account_currency": amount}],
        )[1]
    assert call(
        env,
        "journal_entry_create",
        voucher_type="Journal Entry",
        accounts=[{"account": debit["name"], "debit_in_account_currency": 1}],
    )[1]


def test_hr_records_leave_allocation_and_expense_total(env):
    employee = create(env, "Employee", employee_name="Alice", status="Active")
    assert (
        call(env, "employee_get", name="Alice")[0]["data"]["name"] == employee["name"]
    )
    assert call(env, "employee_list", status="Active")[0]["count"] == 1
    leave_type = create(env, "Leave Type", leave_type_name="Annual")
    allocation = create(
        env,
        "Leave Allocation",
        employee=employee["name"],
        leave_type=leave_type["name"],
        total_leaves_allocated=10,
        new_leaves_allocated=10,
        from_date="2026-01-01",
        to_date="2026-12-31",
    )
    assert (
        call(env, "doc_submit", doctype="Leave Allocation", name=allocation["name"])[1]
        is False
    )
    leave, error = call(
        env,
        "leave_application_create",
        employee="Alice",
        leave_type=leave_type["name"],
        from_date="2026-01-03",
        to_date="2026-01-04",
    )
    assert not error
    name = leave["data"]["name"]
    assert (
        call(env, "leave_application_get", name=name)[0]["data"]["total_leave_days"]
        == 2
    )
    assert call(env, "leave_application_list", employee="Alice")[0]["count"] == 1
    call(
        env,
        "doc_update",
        doctype="Leave Application",
        name=name,
        data={"status": "Approved"},
    )
    call(env, "doc_submit", doctype="Leave Application", name=name)
    balance, error = call(env, "leave_balance", employee="Alice")
    assert (
        not error
        and balance["doctype"] == "Leave Allocation"
        and balance["data"][0]["total_leaves_allocated"] == 10
    )
    expense, error = call(
        env,
        "expense_claim_create",
        employee="Alice",
        expenses=[
            {"expense_type": "Travel", "amount": 4},
            {"expense_type": "Food", "amount": 3},
        ],
    )
    assert not error and expense["data"]["total_claimed_amount"] == 7
    assert call(env, "expense_claim_list", employee="Alice")[0]["count"] == 1
    salary = create(
        env,
        "Salary Slip",
        employee=employee["name"],
        posting_date="2026-01-31",
        gross_pay=100,
        net_pay=90,
    )
    assert call(env, "salary_slip_get", name=salary["name"])[0]["data"]["net_pay"] == 90
    assert (
        call(env, "salary_slip_list", date_from="2026-01-31", date_to="2026-01-31")[0][
            "count"
        ]
        == 1
    )
    create(
        env,
        "Attendance",
        employee=employee["name"],
        attendance_date="2026-01-02",
        status="Present",
    )
    assert call(env, "attendance_list", employee="Alice")[0]["count"] == 1
    company = create(
        env,
        "Company",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    create(env, "Payroll Entry", company=company["name"], posting_date="2026-01-31")
    assert call(env, "payroll_entry_list", company=company["name"])[0]["count"] == 1


@pytest.mark.parametrize(
    "tool,args",
    [
        ("account_list", {"limit": -1}),
        ("journal_entry_create", {"voucher_type": "Journal Entry", "accounts": []}),
        ("journal_entry_get", {"name": "missing"}),
        ("journal_entry_list", {"limit": -1}),
        ("payment_entry_get", {"name": "missing"}),
        ("payment_entry_list", {"party": "missing"}),
        ("employee_get", {"name": "missing"}),
        ("employee_list", {"limit": -1}),
        ("attendance_list", {"employee": "missing"}),
        ("leave_application_get", {"name": "missing"}),
        ("leave_application_list", {"employee": "missing"}),
        (
            "leave_application_create",
            {
                "employee": "missing",
                "leave_type": "Annual",
                "from_date": "2026-01-01",
                "to_date": "2026-01-02",
            },
        ),
        ("salary_slip_get", {"name": "missing"}),
        ("salary_slip_list", {"employee": "missing"}),
        ("payroll_entry_list", {"limit": -1}),
        ("expense_claim_list", {"employee": "missing"}),
        ("expense_claim_create", {"employee": "missing", "expenses": []}),
        ("leave_balance", {"employee": "missing"}),
    ],
)
def test_accounting_hr_deliberate_errors(env, tool, args):
    value, error = call(env, tool, **args)
    assert error and value["error"] != "Unknown provider or tool"
