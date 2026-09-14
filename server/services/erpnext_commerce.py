"""Sales and inventory documents, totals, reservations and physical movements."""

from . import erpnext_store as store
from .erpnext_projects import get_document


def mutation(doc, verb, refresh=None):
    result = {
        "data": doc,
        "message": f"{doc['doctype']} {doc['name']} {verb} successfully",
    }
    if refresh:
        result["refreshRequest"] = {
            "toolName": refresh,
            "arguments": {"name": doc["name"]},
        }
    return result


def create_master(kind, rename=None):
    @store.handler
    def created(db, args, step, clock):
        data = dict(args)
        if rename and rename[0] in data:
            data[rename[1]] = data.pop(rename[0])
        return mutation(store.create(db, kind, data, clock), "created")

    return created


def update_master(kind):
    @store.handler
    def updated(db, args, step, clock):
        return mutation(
            store.update(
                db,
                kind,
                args["name"],
                {key: value for key, value in args.items() if key != "name"},
                clock,
            ),
            "updated",
        )

    return updated


def create_sales(kind, refresh):
    @store.handler
    def created(db, args, step, clock):
        data = dict(args)
        if kind == "Quotation":
            target = store.text(args["quotation_to"], "quotation_to")
            if target not in {"Customer", "Lead"}:
                raise store.BusinessError("Unsupported quotation party")
            data["party_name"] = store.resolve(
                db,
                target,
                args["party_name"],
                "customer_name" if target == "Customer" else "lead_name",
                partial=False,
            )
        items = args["items"]
        if not isinstance(items, list) or not items:
            raise store.BusinessError("items must be a non-empty array")
        data["items"] = []
        for item in items:
            if not isinstance(item, dict):
                raise store.BusinessError("Each item must be an object")
            line = {field: item.get(field) for field in ("item_code", "qty", "rate")}
            if kind != "Quotation" and item.get("warehouse"):
                line["warehouse"] = item["warehouse"]
            if kind == "Sales Order" and "delivery_date" in args:
                line["delivery_date"] = args["delivery_date"]
            data["items"].append(line)
        if args.get("currency"):
            data.update(price_list_currency=args["currency"], plc_conversion_rate=1)
        return mutation(store.create(db, kind, data, clock), "created", refresh)

    return created


def bin_row(db, item, warehouse, clock):
    store.get(db, "Warehouse", warehouse)
    matches = [
        row
        for row in store.all_docs(db, "Bin")
        if row["item_code"] == item and row["warehouse"] == warehouse
    ]
    if matches:
        return matches[0]
    return store.create(
        db,
        "Bin",
        {
            "item_code": item,
            "warehouse": warehouse,
            "actual_qty": 0,
            "reserved_qty": 0,
            "projected_qty": 0,
            "valuation_rate": 0,
            "stock_value": 0,
        },
        clock,
    )


def apply_stock(db, doc, direction, clock):
    kind = doc["doctype"]
    if kind not in {"Sales Order", "Stock Entry", "Purchase Receipt", "Delivery Note"}:
        return
    movements = []
    for item in doc["items"]:
        if kind == "Sales Order":
            warehouse = item.get("warehouse") or doc.get("set_warehouse")
            if warehouse:
                movements.append((item, warehouse, 0, direction * item["qty"]))
        elif kind in {"Purchase Receipt", "Delivery Note"}:
            movements.append(
                (
                    item,
                    item.get("warehouse") or doc.get("set_warehouse"),
                    direction * item["qty"] * (1 if kind == "Purchase Receipt" else -1),
                    0,
                )
            )
        else:
            entry_type = store.text(doc.get("stock_entry_type"), "stock_entry_type")
            if entry_type not in {
                "Material Receipt",
                "Material Issue",
                "Material Transfer",
            }:
                raise store.BusinessError("Unsupported stock entry type")
            if entry_type in {"Material Issue", "Material Transfer"}:
                movements.append(
                    (
                        item,
                        item.get("s_warehouse") or doc.get("from_warehouse"),
                        -direction * item["qty"],
                        0,
                    )
                )
            if entry_type in {"Material Receipt", "Material Transfer"}:
                movements.append(
                    (
                        item,
                        item.get("t_warehouse") or doc.get("to_warehouse"),
                        direction * item["qty"],
                        0,
                    )
                )
    for item, warehouse, actual, reserved in movements:
        row = bin_row(db, item["item_code"], warehouse, clock)
        if row["actual_qty"] + actual < 0 or row["reserved_qty"] + reserved < 0:
            raise store.BusinessError("Insufficient stock for this simulator movement")
        row["actual_qty"] += actual
        row["reserved_qty"] += reserved
        if actual > 0 and item.get("basic_rate") is not None:
            row["valuation_rate"] = item["basic_rate"]
        row["projected_qty"] = row["actual_qty"] - row["reserved_qty"]
        row["stock_value"] = row["actual_qty"] * row["valuation_rate"]
        store.validate("Bin", row)
        row["modified"] = store.now(db, clock)
        store.persist(db, "Bin", row)


def recompute_leave_usage(db, clock):
    allocations = store.all_docs(db, "Leave Allocation")
    used = {row["name"]: 0 for row in allocations}
    for application in store.all_docs(db, "Leave Application"):
        if application["docstatus"] != 1 or application.get("status") != "Approved":
            continue
        eligible = [
            row
            for row in allocations
            if row["docstatus"] == 1
            and row["employee"] == application["employee"]
            and row["leave_type"] == application["leave_type"]
            and row["from_date"]
            <= application["from_date"]
            <= application["to_date"]
            <= row["to_date"]
        ]
        if len(eligible) != 1:
            raise store.BusinessError(
                "Approved leave requires one covering submitted allocation"
            )
        used[eligible[0]["name"]] += application["total_leave_days"]
    for allocation in allocations:
        total = allocation.get(
            "total_leaves_allocated", allocation.get("new_leaves_allocated", 0)
        )
        remaining = total - used[allocation["name"]]
        if remaining < 0:
            raise store.BusinessError("Insufficient allocated leave")
        allocation.update(
            used_leaves=used[allocation["name"]],
            remaining_leaves=remaining,
            modified=store.now(db, clock),
        )
        store.persist(db, "Leave Allocation", allocation)


def lifecycle(db, kind, name, target, clock):
    doc = store.get(db, kind, name)
    if kind not in store.SUBMITTABLE:
        raise store.BusinessError(f"{kind} is not submittable")
    if doc["docstatus"] != target - 1:
        raise store.BusinessError("Invalid document lifecycle transition")
    store.validate(kind, doc)
    store.references(db, kind, doc)
    warnings = []
    if (
        target == 1
        and any(
            field in doc and doc[field] is None
            for field in ("rounded_total", "base_rounded_total")
        )
        and not doc.get("disable_rounded_total")
    ):
        doc["disable_rounded_total"] = 1
        warnings.append(
            "disable_rounded_total auto-set — rounded totals were null (rounding not configured on this instance)"
        )
    apply_stock(db, doc, 1 if target == 1 else -1, clock)
    doc["docstatus"] = target
    doc["status"] = (
        "Cancelled"
        if target == 2
        else {
            "Sales Order": "To Deliver and Bill",
            "Sales Invoice": "Unpaid",
            "Leave Application": doc.get("status", "Open"),
        }.get(kind, "Submitted")
    )
    doc["modified"] = store.now(db, clock)
    store.persist(db, kind, doc)
    if kind in {"Leave Application", "Leave Allocation"}:
        recompute_leave_usage(db, clock)
    result = mutation(doc, "submitted" if target == 1 else "cancelled")
    if warnings:
        result["warnings"] = warnings
    return result


def transition(kind, target, refresh=None):
    @store.handler
    def changed(db, args, step, clock):
        result = lifecycle(db, kind or args["doctype"], args["name"], target, clock)
        if kind is None:
            result.update(doctype=args["doctype"], name=args["name"])
        if refresh:
            result["refreshRequest"] = {
                "toolName": refresh,
                "arguments": {"name": args["name"]},
            }
        return result

    return changed


def list_sales(kind, fields, date_field):
    @store.handler
    def listed(db, args, step, clock):
        filters = []
        if args.get("customer"):
            filters.append(
                [
                    "customer",
                    "=",
                    store.resolve(db, "Customer", args["customer"], "customer_name"),
                ]
            )
        if args.get("party_name"):
            target = store.text(args.get("quotation_to"), "quotation_to")
            if target not in {"Customer", "Lead"}:
                raise store.BusinessError("Unsupported quotation party")
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
        for field in ("status",):
            if args.get(field):
                filters.append([field, "=", args[field]])
        if args.get("date_from"):
            filters.append([date_field, ">=", args["date_from"]])
        if args.get("date_to"):
            filters.append([date_field, "<=", args["date_to"]])
        docs = store.select(
            db, kind, fields=fields.split(), filters=filters, limit=args.get("limit")
        )
        return {"doctype": kind, "count": len(docs), "data": docs}

    return listed


def list_master(kind, fields, exact, disabled=False, default=20):
    @store.handler
    def listed(db, args, step, clock):
        filters = [[key, "=", args[key]] for key in exact if key in args]
        if disabled and not args.get("include_disabled"):
            filters.append(["disabled", "=", 0])
        if kind == "Bin" and args.get("item_code"):
            filters.append(
                [
                    "item_code",
                    "=",
                    store.resolve(db, "Item", args["item_code"], "item_name"),
                ]
            )
        docs = store.select(
            db,
            kind,
            fields=fields.split(),
            filters=filters,
            limit=args.get("limit", default),
        )
        return {"doctype": kind, "count": len(docs), "data": docs}

    return listed


@store.handler
def stock_entry_list(db, args, step, clock):
    filters = (
        [["stock_entry_type", "=", args["stock_entry_type"]]]
        if args.get("stock_entry_type")
        else []
    )
    if args.get("date_from"):
        filters.append(["posting_date", ">=", args["date_from"]])
    if args.get("date_to"):
        filters.append(["posting_date", "<=", args["date_to"]])
    docs = store.select(db, "Stock Entry", fields=["*"], filters=filters, limit=500)
    if args.get("item_code"):
        docs = [
            doc
            for doc in docs
            if any(item["item_code"] == args["item_code"] for item in doc["items"])
        ]
    fields = [
        "name",
        "stock_entry_type",
        "posting_date",
        "from_warehouse",
        "to_warehouse",
        "total_amount",
    ]
    docs = [
        {field: doc.get(field) for field in fields}
        for doc in docs[: store.limited(args.get("limit"))]
    ]
    return {"doctype": "Stock Entry", "count": len(docs), "data": docs}


HANDLERS = {
    "erpnext_customer_create": create_master("Customer"),
    "erpnext_customer_update": update_master("Customer"),
    "erpnext_customer_get": get_document("Customer"),
    "erpnext_customer_list": list_master(
        "Customer",
        "name customer_name customer_group territory email_id disabled",
        ("customer_group", "territory"),
        True,
    ),
    "erpnext_item_create": create_master("Item", ("uom", "stock_uom")),
    "erpnext_item_update": update_master("Item"),
    "erpnext_item_get": get_document("Item"),
    "erpnext_item_list": list_master(
        "Item",
        "name item_code item_name item_group stock_uom is_stock_item standard_rate",
        ("item_group", "is_stock_item"),
        True,
    ),
    "erpnext_warehouse_list": list_master(
        "Warehouse",
        "name warehouse_name warehouse_type company",
        ("company", "warehouse_type"),
    ),
    "erpnext_stock_balance": list_master(
        "Bin",
        "name item_code warehouse actual_qty reserved_qty projected_qty valuation_rate stock_value",
        ("warehouse",),
        default=50,
    ),
    "erpnext_stock_entry_create": create_master("Stock Entry"),
    "erpnext_stock_entry_get": get_document("Stock Entry"),
    "erpnext_stock_entry_list": stock_entry_list,
    "erpnext_sales_order_create": create_sales(
        "Sales Order", "erpnext_sales_order_get"
    ),
    "erpnext_sales_order_update": update_master("Sales Order"),
    "erpnext_sales_order_get": get_document("Sales Order"),
    "erpnext_sales_order_list": list_sales(
        "Sales Order",
        "name customer transaction_date status grand_total currency",
        "transaction_date",
    ),
    "erpnext_sales_order_submit": transition(
        "Sales Order", 1, "erpnext_sales_order_get"
    ),
    "erpnext_sales_order_cancel": transition("Sales Order", 2),
    "erpnext_sales_invoice_create": create_sales(
        "Sales Invoice", "erpnext_sales_invoice_get"
    ),
    "erpnext_sales_invoice_get": get_document("Sales Invoice"),
    "erpnext_sales_invoice_list": list_sales(
        "Sales Invoice",
        "name customer posting_date due_date status grand_total outstanding_amount",
        "posting_date",
    ),
    "erpnext_sales_invoice_submit": transition(
        "Sales Invoice", 1, "erpnext_sales_invoice_get"
    ),
    "erpnext_quotation_create": create_sales("Quotation", "erpnext_quotation_get"),
    "erpnext_quotation_get": get_document("Quotation"),
    "erpnext_quotation_list": list_sales(
        "Quotation",
        "name party_name transaction_date status grand_total",
        "transaction_date",
    ),
    "erpnext_doc_submit": transition(None, 1),
    "erpnext_doc_cancel": transition(None, 2),
}
