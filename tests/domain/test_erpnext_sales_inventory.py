import pytest

from .test_erpnext_operations import call, create
from .test_erpnext_operations import env as erpnext_fixture

env = erpnext_fixture


def test_sales_totals_lifecycle_reserves_and_cancel_releases_stock(env):
    customer, error = call(env, "customer_create", customer_name="Acme")
    assert not error
    customer = customer["data"]
    item, error = call(
        env,
        "item_create",
        item_code="WIDGET",
        item_name="Widget",
        uom="Nos",
        is_stock_item=True,
        standard_rate=5,
    )
    assert not error and item["data"]["stock_uom"] == "Nos"
    warehouse = create(env, "Warehouse", warehouse_name="Stores")
    entry, error = call(
        env,
        "stock_entry_create",
        stock_entry_type="Material Receipt",
        to_warehouse=warehouse["name"],
        items=[{"item_code": "WIDGET", "qty": 10, "basic_rate": 2}],
    )
    assert not error
    receipt = entry["data"]
    assert (
        call(env, "stock_entry_get", name=receipt["name"])[0]["data"]["total_amount"]
        == 20
    )
    assert call(env, "stock_entry_list", item_code="WIDGET")[0]["count"] == 1
    assert (
        call(env, "doc_submit", doctype="Stock Entry", name=receipt["name"])[0]["data"][
            "docstatus"
        ]
        == 1
    )
    assert (
        call(env, "stock_balance", item_code="Widget")[0]["data"][0]["actual_qty"] == 10
    )
    order, error = call(
        env,
        "sales_order_create",
        customer=customer["name"],
        items=[{"item_code": "WIDGET", "qty": 3, "rate": 5}],
        set_warehouse=warehouse["name"],
        currency="USD",
    )
    assert not error and order["data"]["grand_total"] == 15
    assert order["refreshRequest"]["toolName"] == "erpnext_sales_order_get"
    name = order["data"]["name"]
    assert (
        call(
            env,
            "sales_order_update",
            name=name,
            items=[{"item_code": "WIDGET", "qty": 4, "rate": 5}],
        )[0]["data"]["grand_total"]
        == 20
    )
    assert call(env, "sales_order_submit", name=name)[0]["data"]["docstatus"] == 1
    balance = call(env, "stock_balance")[0]["data"][0]
    assert balance["actual_qty"] == 10 and balance["reserved_qty"] == 4
    assert call(env, "sales_order_submit", name=name)[1]
    assert call(env, "sales_order_cancel", name=name)[0]["data"]["docstatus"] == 2
    assert call(env, "sales_order_cancel", name=name)[1]
    assert call(env, "stock_balance")[0]["data"][0]["reserved_qty"] == 0
    assert call(env, "sales_order_get", name=name)[0]["data"]["grand_total"] == 20
    assert call(env, "sales_order_list", customer="Acme")[0]["count"] == 1
    assert (
        call(env, "doc_cancel", doctype="Stock Entry", name=receipt["name"])[0]["data"][
            "docstatus"
        ]
        == 2
    )
    assert call(env, "stock_balance")[0]["data"][0]["actual_qty"] == 0
    assert call(env, "warehouse_list")[0]["data"][0]["name"] == warehouse["name"]


def test_invoice_quotation_and_master_updates(env):
    customer = create(env, "Customer", customer_name="Acme")
    call(env, "item_create", item_code="WIDGET", item_name="Widget")
    items = [{"item_code": "WIDGET", "qty": 2, "rate": 7}]
    for stem, args in (
        (
            "sales_invoice",
            {
                "customer": customer["name"],
                "posting_date": "2026-01-01",
                "due_date": "2026-01-15",
            },
        ),
        ("quotation", {"quotation_to": "Customer", "party_name": "Acme"}),
    ):
        value, error = call(env, stem + "_create", items=items, **args)
        assert not error and value["data"]["grand_total"] == 14
        assert (
            call(env, stem + "_get", name=value["data"]["name"])[0]["data"]["items"][0][
                "amount"
            ]
            == 14
        )
        assert call(env, stem + "_list")[0]["count"] == 1
        if stem == "sales_invoice":
            call(
                env,
                "doc_update",
                doctype="Sales Invoice",
                name=value["data"]["name"],
                data={"rounded_total": None},
            )
            submitted, error = call(
                env, "sales_invoice_submit", name=value["data"]["name"]
            )
            assert (
                not error
                and submitted["warnings"]
                and submitted["data"]["outstanding_amount"] == 14
            )
    assert (
        call(env, "customer_update", name=customer["name"], disabled=True)[0]["data"][
            "disabled"
        ]
        is True
    )
    assert (
        call(env, "customer_get", name=customer["name"])[0]["data"]["customer_name"]
        == "Acme"
    )
    assert call(env, "customer_list")[0]["count"] == 0
    assert call(env, "customer_list", include_disabled=True)[0]["count"] == 1
    assert (
        call(env, "item_update", name="WIDGET", standard_rate=9)[0]["data"][
            "standard_rate"
        ]
        == 9
    )
    assert call(env, "item_get", name="WIDGET")[0]["data"]["item_name"] == "Widget"
    assert call(env, "item_list")[0]["data"][0]["standard_rate"] == 9


@pytest.mark.parametrize(
    "tool,args",
    [
        ("customer_create", {"customer_name": ""}),
        ("customer_update", {"name": "missing", "disabled": True}),
        ("customer_get", {"name": "missing"}),
        ("customer_list", {"limit": -1}),
        ("item_create", {"item_code": "", "item_name": "A"}),
        ("item_update", {"name": "missing", "standard_rate": -1}),
        ("item_get", {"name": "missing"}),
        ("item_list", {"limit": -1}),
        ("stock_entry_create", {"stock_entry_type": "Material Receipt", "items": []}),
        ("stock_entry_get", {"name": "missing"}),
        ("stock_entry_list", {"limit": -1}),
        ("stock_balance", {"item_code": "missing"}),
        ("warehouse_list", {"limit": -1}),
        ("sales_order_create", {"customer": "missing", "items": []}),
        ("sales_order_update", {"name": "missing"}),
        ("sales_order_submit", {"name": "missing"}),
        ("sales_order_cancel", {"name": "missing"}),
        ("sales_order_get", {"name": "missing"}),
        ("sales_order_list", {"customer": "missing"}),
        ("sales_invoice_create", {"customer": "missing", "items": []}),
        ("sales_invoice_submit", {"name": "missing"}),
        ("sales_invoice_get", {"name": "missing"}),
        ("sales_invoice_list", {"customer": "missing"}),
        (
            "quotation_create",
            {"quotation_to": "Customer", "party_name": "missing", "items": []},
        ),
        ("quotation_get", {"name": "missing"}),
        ("quotation_list", {"party_name": "missing"}),
        ("doc_submit", {"doctype": "Company", "name": "missing"}),
        ("doc_cancel", {"doctype": "Company", "name": "missing"}),
    ],
)
def test_sales_inventory_deliberate_errors(env, tool, args):
    value, error = call(env, tool, **args)
    assert error and value["error"] != "Unknown provider or tool"


def test_invalid_nested_numbers_links_and_insufficient_stock_are_atomic(env):
    customer = create(env, "Customer", customer_name="Acme")
    call(env, "item_create", item_code="WIDGET", item_name="Widget")
    warehouse = create(env, "Warehouse", warehouse_name="Stores")
    for qty in (True, -1, 0, [], {}):
        assert call(
            env,
            "doc_create",
            doctype="Sales Order",
            data={
                "customer": customer["name"],
                "items": [{"item_code": "WIDGET", "qty": qty, "rate": 5}],
            },
        )[1]
    assert call(
        env,
        "doc_create",
        doctype="Sales Order",
        data={"customer": [], "items": [{"item_code": "WIDGET", "qty": 1, "rate": 5}]},
    )[1]
    entry = create(
        env,
        "Stock Entry",
        stock_entry_type="Material Issue",
        from_warehouse=warehouse["name"],
        items=[{"item_code": "WIDGET", "qty": 1}],
    )
    assert call(env, "doc_submit", doctype="Stock Entry", name=entry["name"])[1]
    assert call(env, "stock_entry_get", name=entry["name"])[0]["data"]["docstatus"] == 0
    assert call(env, "stock_balance")[0]["count"] == 0
