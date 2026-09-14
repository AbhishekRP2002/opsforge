"""Finite ERPNext documents with transactional identities and validated operations."""

import json
import math
import operator as comparison_operator
import re
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..storage.database import Database


class BusinessError(ValueError):
    """Deliberate simulator rejection; infrastructure exceptions remain fatal."""


class PartialBusinessError(BusinessError):
    """Source-defined field commit followed by a modeled assignment failure."""


REQUIRED = {
    "Company": ("company_name", "abbr", "default_currency", "country"),
    "User": ("full_name", "user_type"),
    "File": ("file_name", "attached_to_doctype", "attached_to_name"),
    "Project": ("project_name",),
    "Task": ("subject", "project"),
    "Employee": ("employee_name",),
    "Timesheet": ("employee",),
    "ToDo": ("owner", "reference_type", "reference_name", "status"),
    "Customer": ("customer_name",),
    "Item": ("item_code", "item_name"),
    "Warehouse": ("warehouse_name",),
    "Bin": ("item_code", "warehouse"),
    "Sales Order": ("customer",),
    "Sales Invoice": ("customer",),
    "Quotation": ("quotation_to", "party_name"),
    "Stock Entry": ("stock_entry_type",),
    "Account": ("account_name", "root_type"),
    "Journal Entry": ("voucher_type",),
    "Payment Entry": ("payment_type",),
    "Attendance": ("employee", "attendance_date", "status"),
    "Leave Type": ("leave_type_name",),
    "Leave Allocation": ("employee", "leave_type", "from_date", "to_date"),
    "Leave Application": ("employee", "leave_type", "from_date", "to_date"),
    "Salary Slip": ("employee",),
    "Payroll Entry": ("company",),
    "Expense Claim": ("employee",),
    "Supplier Group": ("supplier_group_name",),
    "Supplier": ("supplier_name", "supplier_group"),
    "Purchase Order": ("supplier",),
    "Purchase Invoice": ("supplier",),
    "Purchase Receipt": ("supplier",),
    "Supplier Quotation": ("supplier",),
    "Delivery Note": ("customer",),
    "Shipment": ("carrier",),
    "BOM": ("item",),
    "Work Order": ("production_item", "bom_no"),
    "Job Card": ("work_order", "operation"),
    "Lead": ("lead_name",),
    "Opportunity": ("opportunity_from", "party_name"),
    "Contact": ("first_name",),
    "Campaign": ("campaign_name",),
    "Asset Category": ("asset_category_name",),
    "Asset": ("asset_name", "asset_category", "company", "purchase_date"),
    "Asset Movement": ("purpose", "company"),
    "Asset Maintenance": ("asset_name",),
    "Item Price": ("item_code",),
    "Issue": ("subject",),
}
TEXT_FIELDS = {
    "title",
    "source",
    "raised_by",
    "company_name",
    "abbr",
    "default_currency",
    "country",
    "domain",
    "full_name",
    "user_type",
    "file_name",
    "attached_to_doctype",
    "attached_to_name",
    "attached_to_field",
    "project_name",
    "subject",
    "project",
    "employee",
    "employee_name",
    "status",
    "priority",
    "description",
    "company",
    "owner",
    "reference_type",
    "reference_name",
    "customer_name",
    "customer",
    "item_code",
    "item_name",
    "warehouse",
    "warehouse_name",
    "stock_entry_type",
    "quotation_to",
    "party_name",
    "customer_group",
    "territory",
    "item_group",
    "stock_uom",
    "email_id",
    "currency",
    "selling_price_list",
    "customer_type",
    "account_name",
    "root_type",
    "voucher_type",
    "payment_type",
    "party_type",
    "party",
    "leave_type",
    "leave_type_name",
    "reason",
    "department",
    "designation",
    "approval_status",
    "supplier",
    "supplier_name",
    "supplier_group",
    "supplier_group_name",
    "supplier_type",
    "carrier",
    "item",
    "production_item",
    "bom_no",
    "work_order",
    "operation",
    "lead_name",
    "lead_owner",
    "opportunity_from",
    "opportunity_owner",
    "first_name",
    "last_name",
    "campaign_name",
    "campaign_type",
    "asset_category",
    "asset_category_name",
    "asset_name",
    "purpose",
    "custodian",
    "location",
    "maintenance_status",
    "maintenance_team",
}
INTERNAL = {"name", "doctype", "docstatus", "creation", "modified", "_assign"}
REFERENCES = {
    "Project": {"company": "Company"},
    "Task": {"project": "Project"},
    "Timesheet": {"employee": "Employee", "project": "Project"},
    "Warehouse": {"company": "Company"},
    "Bin": {"item_code": "Item", "warehouse": "Warehouse"},
    "Sales Order": {
        "customer": "Customer",
        "company": "Company",
        "set_warehouse": "Warehouse",
    },
    "Sales Invoice": {
        "customer": "Customer",
        "company": "Company",
        "set_warehouse": "Warehouse",
    },
    "Quotation": {"company": "Company"},
    "Stock Entry": {"from_warehouse": "Warehouse", "to_warehouse": "Warehouse"},
    "Account": {"parent_account": "Account", "company": "Company"},
    "Attendance": {"employee": "Employee"},
    "Leave Allocation": {"employee": "Employee", "leave_type": "Leave Type"},
    "Leave Application": {"employee": "Employee", "leave_type": "Leave Type"},
    "Salary Slip": {"employee": "Employee"},
    "Payroll Entry": {"company": "Company"},
    "Expense Claim": {"employee": "Employee"},
    "Supplier": {"supplier_group": "Supplier Group"},
    "Purchase Order": {"supplier": "Supplier", "company": "Company"},
    "Purchase Invoice": {"supplier": "Supplier", "company": "Company"},
    "Purchase Receipt": {"supplier": "Supplier", "company": "Company"},
    "Supplier Quotation": {"supplier": "Supplier", "company": "Company"},
    "Delivery Note": {
        "customer": "Customer",
        "company": "Company",
        "set_warehouse": "Warehouse",
    },
    "BOM": {"item": "Item"},
    "Work Order": {
        "production_item": "Item",
        "bom_no": "BOM",
        "wip_warehouse": "Warehouse",
        "fg_warehouse": "Warehouse",
    },
    "Job Card": {"work_order": "Work Order"},
    "Lead": {"lead_owner": "User"},
    "Opportunity": {"opportunity_owner": "User"},
    "Asset": {
        "asset_category": "Asset Category",
        "company": "Company",
        "custodian": "Employee",
        "item_code": "Item",
    },
    "Asset Movement": {"company": "Company"},
    "Asset Maintenance": {"asset_name": "Asset", "asset_category": "Asset Category"},
    "Item Price": {"item_code": "Item"},
    "Issue": {"customer": "Customer"},
}
SUBMITTABLE = {
    "Sales Order",
    "Sales Invoice",
    "Quotation",
    "Stock Entry",
    "Timesheet",
    "Journal Entry",
    "Payment Entry",
    "Attendance",
    "Leave Allocation",
    "Leave Application",
    "Salary Slip",
    "Payroll Entry",
    "Expense Claim",
}
LINE_DOCUMENTS = {"Sales Order", "Sales Invoice", "Quotation", "Stock Entry"}
SUBMITTABLE |= {
    "Purchase Order",
    "Purchase Invoice",
    "Purchase Receipt",
    "Supplier Quotation",
    "Delivery Note",
    "BOM",
    "Work Order",
    "Asset",
    "Asset Movement",
}
LINE_DOCUMENTS |= {
    "Purchase Order",
    "Purchase Invoice",
    "Purchase Receipt",
    "Supplier Quotation",
    "Delivery Note",
    "BOM",
}


def number(
    value, field, minimum: float = 0, maximum: float | None = None
) -> int | float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or abs(value) > 1e308
        or not math.isfinite(value)
        or value < minimum
        or maximum is not None
        and value > maximum
    ):
        raise BusinessError(f"{field} must be a finite number in the supported range")
    return value


def validate_finite_numbers(value, field="result"):
    if isinstance(value, float) and not math.isfinite(value):
        raise BusinessError(f"{field} must contain only finite numbers")
    if isinstance(value, dict):
        for key, item in value.items():
            validate_finite_numbers(item, f"{field}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_finite_numbers(item, f"{field}[{index}]")


def references(db, kind, data):
    validate_references(kind, data, lambda target, name: get(db, target, name))


def validate_references(kind, data, lookup):
    if kind == "ToDo":
        owner = text(data["owner"], "owner")
        user = lookup("User", owner)
        if "@" not in owner or user.get("enabled") != 1:
            raise BusinessError(
                "ToDo owner is disabled or is not a User email identity"
            )
        lookup(
            doctype(data["reference_type"]),
            text(data["reference_name"], "reference_name"),
        )
    for field, target in REFERENCES.get(kind, {}).items():
        if field in data:
            if data[field] == "" and field not in REQUIRED[kind]:
                continue
            linked = lookup(target, data[field])
            if field == "customer":
                data["customer_name"] = linked["customer_name"]
    if kind == "Payment Entry" and "party" in data:
        target = text(data.get("party_type"), "party_type")
        if target not in {"Customer", "Supplier", "Employee"}:
            raise BusinessError("Unsupported party_type")
        lookup(target, data["party"])
    if kind == "Journal Entry":
        accounts = data.get("accounts")
        if not isinstance(accounts, list) or not accounts:
            raise BusinessError("accounts must be a non-empty array")
        debit = credit = 0
        for account in accounts:
            if not isinstance(account, dict):
                raise BusinessError("Account line must be an object")
            lookup("Account", account.get("account"))
            debit += number(account.get("debit_in_account_currency", 0), "debit")
            credit += number(account.get("credit_in_account_currency", 0), "credit")
        number(debit, "total_debit")
        number(credit, "total_credit")
        if not math.isclose(debit, credit, abs_tol=1e-8):
            raise BusinessError("Journal Entry must balance total debit and credit")
        data.update(total_debit=debit, total_credit=credit)
    if kind == "Expense Claim":
        expenses = data.get("expenses")
        if not isinstance(expenses, list) or not expenses:
            raise BusinessError("expenses must be a non-empty array")
        total = 0
        for expense in expenses:
            if not isinstance(expense, dict):
                raise BusinessError("Expense must be an object")
            text(expense.get("expense_type"), "expense_type")
            total += number(expense.get("amount"), "amount")
        data["total_claimed_amount"] = number(total, "total_claimed_amount")
    if kind == "Leave Application":
        data["total_leave_days"] = (
            datetime.fromisoformat(data["to_date"])
            - datetime.fromisoformat(data["from_date"])
        ).days + 1
    if kind == "Quotation":
        target = text(data.get("quotation_to"), "quotation_to")
        if target not in {"Customer", "Lead"}:
            raise BusinessError("quotation_to must be Customer or Lead")
        lookup(target, data.get("party_name"))
    if kind == "Opportunity":
        target = text(data.get("opportunity_from"), "opportunity_from")
        if target not in {"Customer", "Lead"}:
            raise BusinessError("Unsupported opportunity_from")
        lookup(target, data.get("party_name"))
    if kind == "Work Order":
        quantity = number(data.get("qty"), "qty")
        if quantity == 0:
            raise BusinessError("Work Order qty must be positive")
        bom = lookup("BOM", data["bom_no"])
        if bom["item"] != data["production_item"]:
            raise BusinessError("BOM item must match production_item")
        data["required_items"] = [
            {
                "item_code": item["item_code"],
                "required_qty": number(
                    item["qty"] * quantity / bom.get("quantity", 1), "required_qty"
                ),
            }
            for item in bom["items"]
        ]
    if kind == "Asset Movement":
        assets = data.get("assets")
        if not isinstance(assets, list) or not assets:
            raise BusinessError("assets must contain linked assets")
        for asset in assets:
            if not isinstance(asset, dict):
                raise BusinessError("Asset movement row must be an object")
            lookup("Asset", asset.get("asset"))
    if kind in LINE_DOCUMENTS:
        items = data.get("items")
        if not isinstance(items, list) or not items:
            raise BusinessError("items must be a non-empty array")
        total = 0
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise BusinessError("Each item must be an object")
            for field in TEXT_FIELDS.intersection(item):
                if not isinstance(item[field], str):
                    raise BusinessError(f"Item {field} must be a string")
            linked_item = lookup("Item", item.get("item_code"))
            item["item_name"] = linked_item["item_name"]
            qty = number(item.get("qty"), "qty", minimum=0)
            if qty == 0:
                raise BusinessError("qty must be positive")
            rate_key = "basic_rate" if kind == "Stock Entry" else "rate"
            rate = number(
                item.get(
                    rate_key, 0 if kind in {"Stock Entry", "Delivery Note"} else None
                ),
                rate_key,
            )
            for field in ("warehouse", "s_warehouse", "t_warehouse"):
                if field in item:
                    lookup("Warehouse", item[field])
            item["amount"] = qty * rate
            number(item["amount"], "amount")
            item["idx"] = index + 1
            if item.get("against_sales_order"):
                order = lookup("Sales Order", item["against_sales_order"])
                if order.get("customer") != data.get("customer") or not any(
                    line["item_code"] == item["item_code"] for line in order["items"]
                ):
                    raise BusinessError("Delivery line does not match Sales Order")
            total += item["amount"]
        number(total, "total")
        data["grand_total" if kind != "Stock Entry" else "total_amount"] = total
        data["total_qty"] = number(sum(item["qty"] for item in items), "total_qty")
        if kind == "Sales Invoice":
            paid = number(
                data.get(
                    "paid_amount",
                    total
                    - number(
                        data.get("outstanding_amount", total), "outstanding_amount"
                    ),
                ),
                "paid_amount",
                maximum=total,
            )
            outstanding = number(total - paid, "outstanding_amount")
            if (
                "paid_amount" in data
                and "outstanding_amount" in data
                and not math.isclose(
                    data["outstanding_amount"], outstanding, abs_tol=1e-8
                )
            ):
                raise BusinessError(
                    "Invoice balance must equal grand_total minus paid_amount"
                )
            data.update(paid_amount=paid, outstanding_amount=outstanding)
        if kind == "BOM":
            data["total_cost"] = total


def resolve(db, kind, identifier, label, partial=True):
    identifier = text(identifier, "identifier")
    rows = all_docs(db, kind)
    if any(row["name"] == identifier for row in rows):
        return identifier
    matches = [row for row in rows if row.get(label) == identifier]
    if not matches and partial:
        matches = [
            row for row in rows if identifier.lower() in str(row.get(label, "")).lower()
        ]
    if len(matches) != 1:
        raise BusinessError(f"{kind} identifier is missing or ambiguous: {identifier}")
    return matches[0]["name"]


def handler(
    function: Callable[["Database", dict, int, int], object],
) -> Callable[["Database", dict, int, int], tuple[object, bool]]:
    @wraps(function)
    def execute(db, arguments, step, clock):
        db.connection.execute("SAVEPOINT erpnext_business")
        try:
            value = function(db, arguments, step, clock)
            validate_finite_numbers(value)
        except BusinessError as error:
            if not isinstance(error, PartialBusinessError):
                db.connection.execute("ROLLBACK TO erpnext_business")
            db.connection.execute("RELEASE erpnext_business")
            return {"error": str(error)}, True
        db.connection.execute("RELEASE erpnext_business")
        return value, False

    return execute


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise BusinessError(f"{field} must be a non-empty string")
    return value.strip()


def doctype(value):
    value = text(value, "doctype")
    if value not in REQUIRED:
        raise BusinessError(f"Unsupported DocType: {value}")
    return value


def now(db, clock):
    scenario = json.loads(
        db.connection.execute(
            "SELECT value FROM metadata WHERE key='scenario'"
        ).fetchone()[0]
    )
    epoch = datetime.fromisoformat(
        scenario.get("erpnext_epoch", "2026-01-01T00:00:00+00:00")
    )
    return (epoch.astimezone(UTC) + timedelta(seconds=clock)).isoformat()


def get(db, kind, name):
    kind, name = doctype(kind), text(name, "name")
    row = db.connection.execute(
        "SELECT data FROM erpnext_documents WHERE doctype=? AND name=?", (kind, name)
    ).fetchone()
    if row is None:
        raise BusinessError(f"{kind} {name} does not exist")
    return json.loads(row[0])


def all_docs(db, kind):
    kind = doctype(kind)
    return [
        json.loads(row[0])
        for row in db.connection.execute(
            "SELECT data FROM erpnext_documents WHERE doctype=? ORDER BY name", (kind,)
        )
    ]


def validate(kind, data):
    validate_finite_numbers(data, kind)
    for field in REQUIRED[kind]:
        text(data.get(field), field)
    if kind == "Bin":
        for field in ("actual_qty", "reserved_qty", "valuation_rate"):
            data.setdefault(field, 0)
        data.setdefault(
            "projected_qty",
            number(data["actual_qty"], "actual_qty")
            - number(data["reserved_qty"], "reserved_qty"),
        )
        data.setdefault(
            "stock_value",
            number(data["actual_qty"], "actual_qty")
            * number(data["valuation_rate"], "valuation_rate"),
        )
        number(data["projected_qty"], "projected_qty", minimum=-1e308)
    for field in TEXT_FIELDS.intersection(data):
        if not isinstance(data[field], str):
            raise BusinessError(f"{field} must be a string")
    for field in (
        "disabled",
        "is_stock_item",
        "selling",
        "buying",
        "is_group",
        "is_active",
        "is_default",
        "is_fixed_asset",
        "is_milestone",
    ):
        if field in data and (
            not isinstance(data[field], (bool, int)) or data[field] not in (0, 1)
        ):
            raise BusinessError(f"{field} must be a boolean or 0/1")
    for field in ("expected_time", "actual_time"):
        if field in data:
            number(data[field], field)
    for field in data:
        if field in {"resolution_by", "resolution_date"}:
            if data[field] is None or data[field] == "":
                continue
            value = text(data[field], field)
            if not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[T ])", value):
                raise BusinessError(f"{field} must be an ISO date or timestamp")
            try:
                datetime.fromisoformat(value)
            except ValueError as error:
                raise BusinessError(f"Invalid {field}") from error
            data[field] = value
        elif field.endswith("_date") or field in {
            "expected_closing",
            "planned_start_date",
            "planned_end_date",
        }:
            value = text(data[field], field)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise BusinessError(f"{field} must be YYYY-MM-DD")
            try:
                datetime.fromisoformat(value)
            except ValueError as error:
                raise BusinessError(f"Invalid {field}") from error
            data[field] = value
    if "enabled" in data and (
        type(data["enabled"]) is not int or data["enabled"] not in (0, 1)
    ):
        raise BusinessError("enabled must be 0 or 1")
    for field in ("progress", "percent_complete"):
        if field in data:
            number(data[field], field, maximum=100)
    for field in ("estimated_costing", "total_hours"):
        if field in data:
            number(data[field], field)
    for field in (
        "standard_rate",
        "actual_qty",
        "reserved_qty",
        "valuation_rate",
        "stock_value",
        "outstanding_amount",
    ):
        if field in data:
            number(data[field], field)
    for field in (
        "paid_amount",
        "gross_pay",
        "net_pay",
        "total_leaves_allocated",
        "new_leaves_allocated",
    ):
        if field in data:
            number(data[field], field)
    for field in (
        "gross_purchase_amount",
        "current_value",
        "shipment_amount",
        "quantity",
        "for_quantity",
        "total_completed_qty",
        "opportunity_amount",
        "probability",
    ):
        if field in data:
            number(data[field], field)
    if "price_list_rate" in data:
        number(data["price_list_rate"], "price_list_rate")
    if kind == "BOM" and data.get("quantity", 1) == 0:
        raise BusinessError("BOM quantity must be positive")
    if kind == "Asset":
        number(data.get("gross_purchase_amount"), "gross_purchase_amount")
    if kind == "Account" and data["root_type"] not in {
        "Asset",
        "Liability",
        "Income",
        "Expense",
        "Equity",
    }:
        raise BusinessError("Unsupported root_type")
    for start, end in (
        ("expected_start_date", "expected_end_date"),
        ("exp_start_date", "exp_end_date"),
        ("start_date", "end_date"),
        ("from_date", "to_date"),
        ("posting_date", "posting_date"),
        ("attendance_date", "attendance_date"),
    ):
        for field in (start, end):
            if field in data:
                value = text(data[field], field)
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise BusinessError(f"{field} must be YYYY-MM-DD")
                try:
                    datetime.fromisoformat(value)
                except ValueError as error:
                    raise BusinessError(f"Invalid {field}") from error
        if data.get(start) and data.get(end) and data[start] > data[end]:
            raise BusinessError(f"{start} must not follow {end}")


def persist(db, kind, data):
    validate_finite_numbers(data, kind)
    db.connection.execute(
        "INSERT INTO erpnext_documents VALUES (?,?,?) ON CONFLICT(doctype,name) DO UPDATE SET data=excluded.data",
        (kind, data["name"], json.dumps(data, allow_nan=False)),
    )
    return data


def create(db, kind, data, clock, *, file=False):
    kind = doctype(kind)
    if not isinstance(data, dict):
        raise BusinessError("data must be an object")
    if kind == "File" and not file:
        raise BusinessError("File creation requires erpnext_file_upload")
    prompt_name = (
        data.get("name")
        if kind == "User"
        else data.get("item_code")
        if kind == "Item"
        else None
    )
    forbidden = INTERNAL.intersection(data) - (
        {"name"} if kind == "User" and prompt_name else set()
    )
    if forbidden:
        raise BusinessError(
            "Cannot supply internal fields: " + ", ".join(sorted(forbidden))
        )
    result = deepcopy(data)
    validate(kind, result)
    references(db, kind, result)
    if prompt_name:
        text(prompt_name, "name")
        if kind == "User" and "@" not in prompt_name:
            raise BusinessError("User name must be an email")
        if db.connection.execute(
            "SELECT 1 FROM erpnext_ids WHERE name=?", (prompt_name,)
        ).fetchone():
            raise BusinessError("Document name is already allocated")
    cursor = db.connection.execute(
        "INSERT INTO erpnext_ids(doctype) VALUES (?)", (kind,)
    )
    name = prompt_name or f"ERP-{cursor.lastrowid:06d}"
    while (
        not prompt_name
        and db.connection.execute(
            "SELECT 1 FROM erpnext_ids WHERE name=?", (name,)
        ).fetchone()
    ):
        cursor = db.connection.execute(
            "INSERT INTO erpnext_ids(doctype) VALUES (?)", (kind,)
        )
        name = f"ERP-{cursor.lastrowid:06d}"
    db.connection.execute(
        "UPDATE erpnext_ids SET name=? WHERE sequence=?", (name, cursor.lastrowid)
    )
    result.update(
        name=name,
        doctype=kind,
        docstatus=0,
        creation=now(db, clock),
        modified=now(db, clock),
    )
    if kind in {"Customer", "Item", "Supplier"}:
        result.setdefault("disabled", 0)
    if kind == "Item":
        result.setdefault("is_stock_item", 1)
    if kind in SUBMITTABLE:
        result.setdefault("status", "Draft")
    if kind in {"Sales Order", "Quotation"}:
        result.setdefault("transaction_date", now(db, clock)[:10])
    if kind in {"Sales Invoice", "Stock Entry"}:
        result.setdefault("posting_date", now(db, clock)[:10])
    return persist(db, kind, result)


def update(db, kind, name, data, clock):
    current = get(db, kind, name)
    if kind in SUBMITTABLE and current["docstatus"] != 0:
        raise BusinessError("Only Draft documents can be updated")
    if kind == "File":
        raise BusinessError(
            "Generic File updates are unsupported; use attachment tools"
        )
    if not isinstance(data, dict) or not data:
        raise BusinessError("data must contain changed fields")
    if INTERNAL.intersection(data):
        raise BusinessError("Cannot update internal identity or lifecycle fields")
    if kind == "Item" and "item_code" in data and data["item_code"] != name:
        raise BusinessError("Cannot update Item identity")
    result = current | deepcopy(data)
    if kind == "Sales Invoice":
        if "outstanding_amount" in data and "paid_amount" not in data:
            result.pop("paid_amount", None)
        elif "outstanding_amount" not in data:
            result.pop("outstanding_amount", None)
    validate(kind, result)
    references(db, kind, result)
    result["modified"] = now(db, clock)
    return persist(db, kind, result)


def limited(value, default=20, maximum=500):
    value = default if value is None else value
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not 1 <= value <= maximum
        or int(value) != value
    ):
        raise BusinessError(f"limit must be an integer between 1 and {maximum}")
    return int(value)


def select(
    db,
    kind,
    *,
    fields=None,
    filters=None,
    limit=None,
    order_by="modified desc",
    all_rows=False,
):
    rows = all_docs(db, kind)
    limit = limited(limit)
    fields = ["name", "modified"] if fields is None else fields
    if (
        not isinstance(fields, list)
        or not fields
        or any(
            not isinstance(field, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*|\*", field)
            for field in fields
        )
    ):
        raise BusinessError("Unsupported field selection")
    if not isinstance(order_by, str) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]* (asc|desc)", order_by
    ):
        raise BusinessError("Unsupported order_by; use one field asc or desc")
    if filters is not None and not isinstance(filters, list):
        raise BusinessError("filters must be an array")
    for condition in filters or []:
        if not isinstance(condition, list) or len(condition) != 3:
            raise BusinessError("Supported filters are [field, operator, value]")
        field, operator, value = condition
        if (
            not isinstance(field, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field)
            or not isinstance(operator, str)
            or operator not in {"=", "!=", "in", "not in", ">", ">=", "<", "<=", "like"}
        ):
            raise BusinessError("Unsupported filter syntax")
        if operator in {"in", "not in"}:
            if not isinstance(value, list) or any(
                not isinstance(item, (str, int, float)) or isinstance(item, bool)
                for item in value
            ):
                raise BusinessError("in/not in requires an array of strings or numbers")
        elif value is not None and not isinstance(value, (str, int, float, bool)):
            raise BusinessError("Filter value must be scalar")
        if operator == "like" and not isinstance(value, str):
            raise BusinessError("like requires string value")

        def matches(row, field=field, operator=operator, value=value):
            actual = row.get(field)
            if operator == "=":
                return actual == value
            if operator == "!=":
                return actual != value
            if operator == "in":
                return actual in value
            if operator == "not in":
                return actual not in value
            if operator == "like":
                if not isinstance(value, str):
                    raise BusinessError("like requires string value")
                pattern = "".join(
                    ".*" if char == "%" else "." if char == "_" else re.escape(char)
                    for char in value
                )
                return (
                    isinstance(actual, str)
                    and re.fullmatch(pattern, actual, re.IGNORECASE) is not None
                )
            if actual is None:
                return False
            if not (
                isinstance(actual, str)
                and isinstance(value, str)
                or type(actual) in (int, float)
                and type(value) in (int, float)
            ):
                raise BusinessError("Incompatible ordered filter values")
            if not isinstance(value, (str, int, float)):
                raise BusinessError("Ordered filter value must be a string or number")
            comparison = comparison_operator.gt(actual, value) - comparison_operator.lt(
                actual, value
            )
            return {
                ">": comparison > 0,
                ">=": comparison >= 0,
                "<": comparison < 0,
                "<=": comparison <= 0,
            }[operator]

        rows = [row for row in rows if matches(row)]
    field, direction = order_by.split()
    if any(
        row.get(field) is not None and not isinstance(row[field], (str, int, float))
        for row in rows
    ):
        raise BusinessError("Ordering requires scalar fields")
    rows.sort(
        key=lambda row: (
            row.get(field) is not None,
            isinstance(row.get(field), str),
            row.get(field) if row.get(field) is not None else "",
        ),
        reverse=direction == "desc",
    )
    return [
        {field: row.get(field) for field in fields} if fields != ["*"] else row
        for row in rows[: None if all_rows else limit]
    ]
