import pytest

from .test_erpnext_operations import call, create
from .test_erpnext_operations import env as erpnext_fixture

env = erpnext_fixture


@pytest.fixture
def records(env):
    company = create(
        env,
        "Company",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    employee = create(env, "Employee", employee_name="Alice")
    customer = create(env, "Customer", customer_name="Customer")
    group = create(env, "Supplier Group", supplier_group_name="Parts")
    supplier, error = call(
        env, "supplier_create", supplier_name="Supplier", supplier_group=group["name"]
    )
    assert not error and supplier["data"]["supplier_type"] == "Company"
    supplier = supplier["data"]
    call(env, "item_create", item_code="WIDGET", item_name="Widget")
    warehouse = create(env, "Warehouse", warehouse_name="Stores")
    order, error = call(
        env,
        "purchase_order_create",
        supplier="Supplier",
        items=[{"item_code": "WIDGET", "qty": 2, "rate": 3}],
    )
    assert not error and order["data"]["grand_total"] == 6
    invoice = create(
        env,
        "Purchase Invoice",
        supplier=supplier["name"],
        items=[{"item_code": "WIDGET", "qty": 2, "rate": 3}],
    )
    receipt = create(
        env,
        "Purchase Receipt",
        supplier=supplier["name"],
        items=[
            {"item_code": "WIDGET", "qty": 2, "rate": 3, "warehouse": warehouse["name"]}
        ],
    )
    quotation = create(
        env,
        "Supplier Quotation",
        supplier=supplier["name"],
        items=[{"item_code": "WIDGET", "qty": 2, "rate": 3}],
    )
    delivery, error = call(
        env,
        "delivery_note_create",
        customer=customer["name"],
        items=[{"item_code": "WIDGET", "qty": 1}],
    )
    assert not error and delivery["data"]["total_qty"] == 1
    shipment = create(
        env, "Shipment", carrier="Local", pickup_date="2026-01-02", shipment_amount=1
    )
    bom = create(
        env,
        "BOM",
        item="WIDGET",
        quantity=1,
        items=[{"item_code": "WIDGET", "qty": 1, "rate": 2}],
    )
    work, error = call(
        env, "work_order_create", production_item="WIDGET", bom_no=bom["name"], qty=2
    )
    assert not error and work["data"]["required_items"][0]["required_qty"] == 2
    job = create(
        env,
        "Job Card",
        work_order=work["data"]["name"],
        operation="Assemble",
        for_quantity=2,
    )
    lead, error = call(env, "lead_create", lead_name="Prospect")
    assert not error
    opportunity = create(
        env,
        "Opportunity",
        opportunity_from="Lead",
        party_name=lead["data"]["name"],
        opportunity_amount=5,
    )
    contact = create(env, "Contact", first_name="Alice")
    campaign = create(
        env,
        "Campaign",
        campaign_name="Launch",
        start_date="2026-01-01",
        end_date="2026-01-31",
    )
    category = create(env, "Asset Category", asset_category_name="Computers")
    asset, error = call(
        env,
        "asset_create",
        asset_name="Laptop",
        asset_category=category["name"],
        company=company["name"],
        purchase_date="2026-01-01",
        gross_purchase_amount=100,
        custodian=employee["name"],
    )
    assert not error and asset["data"]["gross_purchase_amount"] == 100
    movement = create(
        env,
        "Asset Movement",
        purpose="Transfer",
        company=company["name"],
        assets=[{"asset": asset["data"]["name"]}],
    )
    maintenance = create(
        env,
        "Asset Maintenance",
        asset_name=asset["data"]["name"],
        maintenance_status="Planned",
    )
    return {
        "supplier": supplier,
        "purchase_order": order["data"],
        "purchase_invoice": invoice,
        "purchase_receipt": receipt,
        "supplier_quotation": quotation,
        "delivery_note": delivery["data"],
        "shipment": shipment,
        "bom": bom,
        "work_order": work["data"],
        "job_card": job,
        "lead": lead["data"],
        "opportunity": opportunity,
        "contact": contact,
        "campaign": campaign,
        "asset": asset["data"],
        "asset_movement": movement,
        "asset_maintenance": maintenance,
        "asset_category": category,
    }


@pytest.mark.parametrize(
    "stem",
    [
        "supplier",
        "purchase_order",
        "purchase_invoice",
        "purchase_receipt",
        "delivery_note",
        "shipment",
        "bom",
        "work_order",
        "job_card",
        "lead",
        "opportunity",
        "contact",
        "asset",
        "asset_movement",
        "asset_maintenance",
    ],
)
def test_business_get_reads_generic_and_specialized_documents(env, records, stem):
    value, error = call(env, stem + "_get", name=records[stem]["name"])
    assert not error and value["data"] == records[stem]
    assert call(env, stem + "_get", name="missing")[1]


@pytest.mark.parametrize(
    "stem",
    [
        "supplier",
        "purchase_order",
        "purchase_invoice",
        "purchase_receipt",
        "supplier_quotation",
        "delivery_note",
        "shipment",
        "bom",
        "work_order",
        "job_card",
        "lead",
        "opportunity",
        "contact",
        "campaign",
        "asset",
        "asset_movement",
        "asset_maintenance",
        "asset_category",
    ],
)
def test_business_lists_read_real_records(env, records, stem):
    value, error = call(env, stem + "_list")
    assert (
        not error
        and value["count"] == 1
        and value["data"][0]["name"] == records[stem]["name"]
    )
    assert call(env, stem + "_list", limit=-1)[1]


@pytest.mark.parametrize(
    "tool,args",
    [
        ("supplier_create", {"supplier_name": "A", "supplier_group": "missing"}),
        ("purchase_order_create", {"supplier": "missing", "items": []}),
        ("delivery_note_create", {"customer": "missing", "items": []}),
        (
            "work_order_create",
            {"production_item": "missing", "bom_no": "missing", "qty": 1},
        ),
        ("lead_create", {"lead_name": ""}),
        (
            "asset_create",
            {
                "asset_name": "A",
                "asset_category": "missing",
                "company": "missing",
                "purchase_date": "2026-01-01",
                "gross_purchase_amount": 1,
            },
        ),
    ],
)
def test_business_create_failures(env, tool, args):
    value, error = call(env, tool, **args)
    assert error and value["error"] != "Unknown provider or tool"


def test_receipt_delivery_reversals_and_asset_ids_are_enforced(env, records):
    receipt = records["purchase_receipt"]
    assert (
        call(env, "doc_submit", doctype="Purchase Receipt", name=receipt["name"])[1]
        is False
    )
    balance = call(env, "stock_balance")[0]["data"][0]
    assert balance["actual_qty"] == 2
    delivery = records["delivery_note"]
    assert (
        call(
            env,
            "doc_update",
            doctype="Delivery Note",
            name=delivery["name"],
            data={
                "items": [
                    {"item_code": "WIDGET", "qty": 1, "warehouse": balance["warehouse"]}
                ]
            },
        )[1]
        is False
    )
    assert (
        call(env, "doc_submit", doctype="Delivery Note", name=delivery["name"])[1]
        is False
    )
    assert call(env, "stock_balance")[0]["data"][0]["actual_qty"] == 1
    assert (
        call(env, "doc_cancel", doctype="Delivery Note", name=delivery["name"])[1]
        is False
    )
    assert call(env, "stock_balance")[0]["data"][0]["actual_qty"] == 2
    asset = records["asset"]
    assert call(
        env,
        "doc_update",
        doctype="Asset",
        name=asset["name"],
        data={"custodian": "Alice"},
    )[1]
    assert call(env, "asset_list", custodian="Alice")[0]["count"] == 1
