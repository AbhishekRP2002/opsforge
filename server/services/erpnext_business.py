"""Purchasing, delivery, manufacturing, CRM and asset adapters."""

from . import erpnext_store as store
from .erpnext_accounting_hr import listing
from .erpnext_commerce import create_master, list_master, mutation
from .erpnext_projects import get_document


def resolved_listing(
    kind, fields, exact=(), resolve_fields=None, date_field="posting_date", end=None
):
    @store.handler
    def listed(db, args, step, clock):
        filters = [
            [field, "=", args[field]] for field in exact if args.get(field) is not None
        ]
        for field, (target, label) in (resolve_fields or {}).items():
            if args.get(field):
                filters.append(
                    [field, "=", store.resolve(db, target, args[field], label)]
                )
        if args.get("date_from"):
            filters.append([date_field, ">=", args["date_from"]])
        if args.get("date_to"):
            filters.append([end or date_field, "<=", args["date_to"]])
        if kind == "Opportunity" and args.get("party_name"):
            target = store.text(args.get("opportunity_from"), "opportunity_from")
            if target not in {"Customer", "Lead"}:
                raise store.BusinessError("Unsupported opportunity_from")
            filters.append(
                [
                    "party_name",
                    "=",
                    store.resolve(
                        db,
                        target,
                        args["party_name"],
                        "customer_name" if target == "Customer" else "lead_name",
                    ),
                ]
            )
        docs = store.select(
            db, kind, fields=fields.split(), filters=filters, limit=args.get("limit")
        )
        return {"doctype": kind, "count": len(docs), "data": docs}

    return listed


@store.handler
def supplier_create(db, args, step, clock):
    return mutation(
        store.create(db, "Supplier", {"supplier_type": "Company"} | args, clock),
        "created",
    )


@store.handler
def purchase_order_create(db, args, step, clock):
    supplier = store.resolve(
        db, "Supplier", args["supplier"], "supplier_name", partial=False
    )
    data = {"supplier": supplier, "items": []}
    for item in args["items"]:
        line = {field: item.get(field) for field in ("item_code", "qty", "rate")}
        if "schedule_date" in args:
            line["schedule_date"] = args["schedule_date"]
        data["items"].append(line)
    if "schedule_date" in args:
        data["schedule_date"] = args["schedule_date"]
    return mutation(store.create(db, "Purchase Order", data, clock), "created")


@store.handler
def delivery_create(db, args, step, clock):
    data = {
        "customer": args["customer"],
        "items": [
            {
                key: item[key]
                for key in ("item_code", "qty", "against_sales_order")
                if key in item
            }
            for item in args["items"]
        ],
    }
    if "posting_date" in args:
        data["posting_date"] = args["posting_date"]
    return mutation(store.create(db, "Delivery Note", data, clock), "created")


HANDLERS = {
    "erpnext_supplier_create": supplier_create,
    "erpnext_supplier_get": get_document("Supplier"),
    "erpnext_supplier_list": list_master(
        "Supplier",
        "name supplier_name supplier_group supplier_type email_id disabled",
        ("supplier_group", "supplier_type"),
        True,
    ),
    "erpnext_purchase_order_create": purchase_order_create,
    "erpnext_purchase_order_get": get_document("Purchase Order"),
    "erpnext_purchase_order_list": resolved_listing(
        "Purchase Order",
        "name supplier transaction_date schedule_date status grand_total currency",
        ("status",),
        {"supplier": ("Supplier", "supplier_name")},
        "transaction_date",
    ),
    "erpnext_purchase_invoice_get": get_document("Purchase Invoice"),
    "erpnext_purchase_invoice_list": resolved_listing(
        "Purchase Invoice",
        "name supplier posting_date due_date status grand_total outstanding_amount",
        ("status",),
        {"supplier": ("Supplier", "supplier_name")},
    ),
    "erpnext_purchase_receipt_get": get_document("Purchase Receipt"),
    "erpnext_purchase_receipt_list": resolved_listing(
        "Purchase Receipt",
        "name supplier posting_date status total_qty grand_total",
        ("status",),
        {"supplier": ("Supplier", "supplier_name")},
    ),
    "erpnext_supplier_quotation_list": resolved_listing(
        "Supplier Quotation",
        "name supplier transaction_date status grand_total",
        ("status",),
        {"supplier": ("Supplier", "supplier_name")},
        "transaction_date",
    ),
    "erpnext_delivery_note_create": delivery_create,
    "erpnext_delivery_note_get": get_document("Delivery Note"),
    "erpnext_delivery_note_list": resolved_listing(
        "Delivery Note",
        "name customer posting_date status total_qty grand_total",
        ("status",),
        {"customer": ("Customer", "customer_name")},
    ),
    "erpnext_shipment_get": get_document("Shipment"),
    "erpnext_shipment_list": listing(
        "Shipment",
        "name status pickup_date delivery_date carrier shipment_amount",
        ("status", "carrier"),
        "pickup_date",
        "pickup_date",
    ),
    "erpnext_bom_get": get_document("BOM"),
    "erpnext_bom_list": resolved_listing(
        "BOM",
        "name item item_name quantity uom is_active is_default total_cost",
        ("is_active", "is_default"),
        {"item": ("Item", "item_name")},
    ),
    "erpnext_work_order_create": create_master("Work Order"),
    "erpnext_work_order_get": get_document("Work Order"),
    "erpnext_work_order_list": resolved_listing(
        "Work Order",
        "name production_item qty produced_qty status planned_start_date planned_end_date",
        ("status",),
        {"production_item": ("Item", "item_name")},
        "planned_start_date",
    ),
    "erpnext_job_card_get": get_document("Job Card"),
    "erpnext_job_card_list": listing(
        "Job Card",
        "name work_order operation status for_quantity total_completed_qty workstation",
        ("work_order", "status", "operation"),
    ),
    "erpnext_lead_create": create_master("Lead"),
    "erpnext_lead_get": get_document("Lead"),
    "erpnext_lead_list": listing(
        "Lead",
        "name lead_name company_name status lead_owner email_id mobile_no",
        ("status", "lead_owner"),
    ),
    "erpnext_opportunity_get": get_document("Opportunity"),
    "erpnext_opportunity_list": resolved_listing(
        "Opportunity",
        "name opportunity_from party_name status opportunity_amount currency probability opportunity_owner",
        ("status", "opportunity_owner"),
    ),
    "erpnext_contact_get": get_document("Contact"),
    "erpnext_contact_list": listing(
        "Contact",
        "name first_name last_name company_name email_id mobile_no status",
        ("company_name", "status"),
    ),
    "erpnext_campaign_list": listing(
        "Campaign",
        "name campaign_name campaign_type start_date end_date description",
        ("campaign_type",),
        "start_date",
        "end_date",
    ),
    "erpnext_asset_create": create_master("Asset"),
    "erpnext_asset_get": get_document("Asset"),
    "erpnext_asset_list": resolved_listing(
        "Asset",
        "name asset_name asset_category status purchase_date gross_purchase_amount current_value location custodian",
        ("status", "asset_category", "location"),
        {"custodian": ("Employee", "employee_name")},
        "purchase_date",
    ),
    "erpnext_asset_movement_get": get_document("Asset Movement"),
    "erpnext_asset_movement_list": listing(
        "Asset Movement",
        "name transaction_date purpose company",
        ("purpose",),
        "transaction_date",
        "transaction_date",
    ),
    "erpnext_asset_maintenance_get": get_document("Asset Maintenance"),
    "erpnext_asset_maintenance_list": listing(
        "Asset Maintenance",
        "name asset_name asset_category maintenance_team maintenance_status",
        ("asset_name", "maintenance_status"),
    ),
    "erpnext_asset_category_list": listing(
        "Asset Category", "name asset_category_name"
    ),
}
