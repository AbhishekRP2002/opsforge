"""Erpnext commerce tool declarations."""

from typing import Annotated, Literal, NotRequired

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import ConfigDict, Field, with_config
from pydantic.experimental.missing_sentinel import MISSING
from typing_extensions import TypedDict


@with_config(ConfigDict(extra="allow"))
class ErpnextStockEntryCreateItemsItem(TypedDict):
    item_code: str
    qty: float
    s_warehouse: NotRequired[Annotated[str, Field(description="Source warehouse")]]
    t_warehouse: NotRequired[Annotated[str, Field(description="Target warehouse")]]
    basic_rate: NotRequired[
        Annotated[float, Field(description="Valuation rate (for receipts)")]
    ]


@with_config(ConfigDict(extra="allow"))
class ErpnextSalesOrderCreateItemsItem(TypedDict):
    item_code: str
    qty: float
    rate: float
    warehouse: NotRequired[
        Annotated[str, Field(description="Item warehouse (e.g. 'Stores - CI')")]
    ]


@with_config(ConfigDict(extra="allow"))
class ErpnextSalesOrderUpdateItemsItem(TypedDict):
    item_code: NotRequired[str]
    qty: NotRequired[float]
    rate: NotRequired[float]


@with_config(ConfigDict(extra="allow"))
class ErpnextSalesInvoiceCreateItemsItem(TypedDict):
    item_code: str
    qty: float
    rate: float
    warehouse: NotRequired[
        Annotated[str, Field(description="Item warehouse (e.g. 'Stores - CI')")]
    ]


@with_config(ConfigDict(extra="allow"))
class ErpnextQuotationCreateItemsItem(TypedDict):
    item_code: str
    qty: float
    rate: float


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def erpnext_item_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        item_group: Annotated[str, Field(description="Filter by item group")]
        | MISSING = MISSING,
        is_stock_item: Annotated[
            bool, Field(description="Filter by stock item flag (true=stock items only)")
        ]
        | MISSING = MISSING,
        include_disabled: Annotated[
            bool, Field(description="Include disabled items (default false)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List ERPNext Items. Returns active items by default. Fields: name, item_code, item_name, item_group, stock_uom, is_stock_item, standard_rate. Filterable by item_group, is_stock_item."
        return await dispatch(
            "erpnext_item_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "item_group": item_group,
                    "is_stock_item": is_stock_item,
                    "include_disabled": include_disabled,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_item_get(
        *,
        name: Annotated[str, Field(description="Item name or item_code")],
    ) -> ToolResult:
        "Get a single ERPNext Item by name/item_code. Returns all fields including pricing and stock details."
        return await dispatch("erpnext_item_get", {"name": name})

    @mcp.tool
    async def erpnext_item_create(
        *,
        item_code: Annotated[str, Field(description="Unique item code")],
        item_name: Annotated[str, Field(description="Human-readable item name")],
        item_group: Annotated[
            str, Field(description="Item group (default: 'All Item Groups')")
        ]
        | MISSING = MISSING,
        uom: Annotated[
            str,
            Field(
                description="Stock unit of measure, sent to ERPNext as stock_uom (for example 'Nos')"
            ),
        ]
        | MISSING = MISSING,
        is_stock_item: Annotated[
            bool, Field(description="True for physical stock items (default: true)")
        ]
        | MISSING = MISSING,
        standard_rate: Annotated[float, Field(description="Default selling rate")]
        | MISSING = MISSING,
        description: Annotated[str, Field(description="Item description")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Item (product or service). Requires item_code and item_name. Set is_stock_item=false for service/non-stocked items."
        return await dispatch(
            "erpnext_item_create",
            {
                key: value
                for key, value in {
                    "item_code": item_code,
                    "item_name": item_name,
                    "item_group": item_group,
                    "uom": uom,
                    "is_stock_item": is_stock_item,
                    "standard_rate": standard_rate,
                    "description": description,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_item_update(
        *,
        name: Annotated[str, Field(description="Item name/item_code")],
        item_name: Annotated[str, Field(description="New item name")]
        | MISSING = MISSING,
        item_group: Annotated[str, Field(description="New item group")]
        | MISSING = MISSING,
        standard_rate: Annotated[float, Field(description="New default selling rate")]
        | MISSING = MISSING,
        description: Annotated[str, Field(description="New description")]
        | MISSING = MISSING,
        disabled: Annotated[bool, Field(description="Set to true to disable the item")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Update an existing Item. Pass only the fields you want to change."
        return await dispatch(
            "erpnext_item_update",
            {
                key: value
                for key, value in {
                    "name": name,
                    "item_name": item_name,
                    "item_group": item_group,
                    "standard_rate": standard_rate,
                    "description": description,
                    "disabled": disabled,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_stock_balance(
        *,
        limit: Annotated[float, Field(description="Max results (default 50)")]
        | MISSING = MISSING,
        item_code: Annotated[
            str,
            Field(
                description="Filter by item code or name (e.g. 'ITEM-001' or 'Widget A')"
            ),
        ]
        | MISSING = MISSING,
        warehouse: Annotated[str, Field(description="Filter by warehouse")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Get stock balance by item and/or warehouse. Reads from the Bin DocType. Fields: item_code, warehouse, actual_qty, reserved_qty, projected_qty, valuation_rate, stock_value. Filterable by item_code, warehouse."
        return await dispatch(
            "erpnext_stock_balance",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "item_code": item_code,
                    "warehouse": warehouse,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_warehouse_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        company: Annotated[str, Field(description="Filter by company")]
        | MISSING = MISSING,
        warehouse_type: Annotated[str, Field(description="Filter by warehouse type")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List ERPNext Warehouses. Fields: name, warehouse_name, warehouse_type, company."
        return await dispatch(
            "erpnext_warehouse_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "company": company,
                    "warehouse_type": warehouse_type,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_stock_entry_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        item_code: Annotated[
            str, Field(description="Exact item code present in a Stock Entry line")
        ]
        | MISSING = MISSING,
        stock_entry_type: Annotated[
            str,
            Field(
                description="Filter by type (Material Issue, Material Receipt, Material Transfer, etc.)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Stock Entries (material transfers, receipts, issues). Fields: name, stock_entry_type, posting_date, from_warehouse, to_warehouse, total_amount. Filterable by item_code, stock_entry_type, date range."
        return await dispatch(
            "erpnext_stock_entry_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "item_code": item_code,
                    "stock_entry_type": stock_entry_type,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_stock_entry_get(
        *,
        name: Annotated[str, Field(description="Stock Entry name (e.g. STE-00001)")],
    ) -> ToolResult:
        "Get a single Stock Entry by name. Returns full document with item details."
        return await dispatch("erpnext_stock_entry_get", {"name": name})

    @mcp.tool
    async def erpnext_stock_entry_create(
        *,
        stock_entry_type: Annotated[
            Literal["Material Issue", "Material Receipt", "Material Transfer"],
            Field(
                description="Entry type: Material Issue, Material Receipt, Material Transfer"
            ),
        ],
        items: Annotated[
            list[ErpnextStockEntryCreateItemsItem],
            Field(
                description="Items to move: [{item_code, qty, s_warehouse?, t_warehouse?, basic_rate?}]"
            ),
        ],
        from_warehouse: Annotated[
            str,
            Field(
                description="Default source warehouse (applies to all items if not per-item)"
            ),
        ]
        | MISSING = MISSING,
        to_warehouse: Annotated[
            str,
            Field(
                description="Default target warehouse (applies to all items if not per-item)"
            ),
        ]
        | MISSING = MISSING,
        posting_date: Annotated[str, Field(description="Posting date YYYY-MM-DD")]
        | MISSING = MISSING,
        remarks: Annotated[str, Field(description="Optional remarks")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Stock Entry (material issue, receipt, or transfer). Requires stock_entry_type and items with item_code and qty. For Material Issue: set s_warehouse. For Material Receipt: set t_warehouse. For Material Transfer: set both s_warehouse and t_warehouse."
        return await dispatch(
            "erpnext_stock_entry_create",
            {
                key: value
                for key, value in {
                    "stock_entry_type": stock_entry_type,
                    "items": items,
                    "from_warehouse": from_warehouse,
                    "to_warehouse": to_warehouse,
                    "posting_date": posting_date,
                    "remarks": remarks,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_doc_submit(
        *,
        doctype: Annotated[
            str,
            Field(
                description="ERPNext DocType name (e.g. 'Sales Order', 'Purchase Invoice', 'Timesheet')"
            ),
        ],
        name: Annotated[
            str, Field(description="Document name/ID to submit (e.g. 'SO-00001')")
        ],
    ) -> ToolResult:
        "Submit any ERPNext document (changes status from Draft to Submitted). Applies to submittable DocTypes like Sales Order, Purchase Order, Sales Invoice, etc. Calls frappe.client.submit via the Frappe method API."
        return await dispatch("erpnext_doc_submit", {"doctype": doctype, "name": name})

    @mcp.tool
    async def erpnext_doc_cancel(
        *,
        doctype: Annotated[
            str,
            Field(
                description="ERPNext DocType name (e.g. 'Sales Order', 'Purchase Invoice', 'Timesheet')"
            ),
        ],
        name: Annotated[
            str, Field(description="Document name/ID to cancel (e.g. 'SO-00001')")
        ],
    ) -> ToolResult:
        "Cancel any ERPNext submitted document (changes status to Cancelled). Applies to submittable DocTypes like Sales Order, Purchase Order, Sales Invoice, etc. Calls frappe.client.cancel via the Frappe method API."
        return await dispatch("erpnext_doc_cancel", {"doctype": doctype, "name": name})

    @mcp.tool
    async def erpnext_customer_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        customer_group: Annotated[str, Field(description="Filter by customer group")]
        | MISSING = MISSING,
        territory: Annotated[str, Field(description="Filter by territory")]
        | MISSING = MISSING,
        include_disabled: Annotated[
            bool, Field(description="Include disabled customers (default false)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List ERPNext customers. Returns active customers by default. Fields: name, customer_name, customer_group, territory, email_id, disabled."
        return await dispatch(
            "erpnext_customer_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "customer_group": customer_group,
                    "territory": territory,
                    "include_disabled": include_disabled,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_customer_get(
        *,
        name: Annotated[str, Field(description="Customer name (ID)")],
    ) -> ToolResult:
        "Get a single ERPNext customer by name (ID). Returns all fields including contact details."
        return await dispatch("erpnext_customer_get", {"name": name})

    @mcp.tool
    async def erpnext_customer_create(
        *,
        customer_name: Annotated[str, Field(description="Full customer name")],
        customer_group: Annotated[
            str, Field(description="Customer group (default: 'Commercial')")
        ]
        | MISSING = MISSING,
        territory: Annotated[
            str, Field(description="Territory (default: 'All Territories')")
        ]
        | MISSING = MISSING,
        email_id: Annotated[str, Field(description="Primary email address")]
        | MISSING = MISSING,
        customer_type: Annotated[
            Literal["Company", "Individual"],
            Field(
                description="Customer type: Company or Individual (default: Company)"
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Customer. Requires customer_name. Optionally set customer_group, territory, email_id."
        return await dispatch(
            "erpnext_customer_create",
            {
                key: value
                for key, value in {
                    "customer_name": customer_name,
                    "customer_group": customer_group,
                    "territory": territory,
                    "email_id": email_id,
                    "customer_type": customer_type,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_customer_update(
        *,
        name: Annotated[str, Field(description="Customer name (ID)")],
        customer_name: Annotated[str, Field(description="New customer name")]
        | MISSING = MISSING,
        customer_group: Annotated[str, Field(description="New customer group")]
        | MISSING = MISSING,
        territory: Annotated[str, Field(description="New territory")]
        | MISSING = MISSING,
        email_id: Annotated[str, Field(description="New email address")]
        | MISSING = MISSING,
        disabled: Annotated[
            bool, Field(description="Set to true to disable the customer")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Update an existing Customer. Pass only the fields you want to change."
        return await dispatch(
            "erpnext_customer_update",
            {
                key: value
                for key, value in {
                    "name": name,
                    "customer_name": customer_name,
                    "customer_group": customer_group,
                    "territory": territory,
                    "email_id": email_id,
                    "disabled": disabled,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_sales_order_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        customer: Annotated[
            str,
            Field(
                description="Filter by customer ID or name (e.g. 'CUST-00001' or 'Acme Corp')"
            ),
        ]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, To Deliver and Bill, Completed, Cancelled, etc.)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Sales Orders. Filterable by customer, status, date range. Fields: name, customer, transaction_date, status, grand_total, currency."
        return await dispatch(
            "erpnext_sales_order_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "customer": customer,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_sales_order_get(
        *,
        name: Annotated[str, Field(description="Sales Order name (e.g. SO-00001)")],
    ) -> ToolResult:
        "Get a single Sales Order by name (e.g. SO-00001). Returns full document with line items."
        return await dispatch("erpnext_sales_order_get", {"name": name})

    @mcp.tool
    async def erpnext_sales_order_create(
        *,
        customer: Annotated[str, Field(description="Customer name (ID)")],
        items: Annotated[
            list[ErpnextSalesOrderCreateItemsItem],
            Field(description="Line items: [{item_code, qty, rate, warehouse?}]"),
        ],
        delivery_date: Annotated[
            str, Field(description="Delivery date YYYY-MM-DD (default: today + 7 days)")
        ]
        | MISSING = MISSING,
        company: Annotated[
            str,
            Field(description="Company name. Required if multiple companies exist."),
        ]
        | MISSING = MISSING,
        selling_price_list: Annotated[
            str,
            Field(
                description="Price list name (e.g. 'Standard Selling'). Required if no default is set."
            ),
        ]
        | MISSING = MISSING,
        currency: Annotated[
            str,
            Field(
                description="Transaction currency (e.g. 'EUR', 'USD'). Defaults to company currency."
            ),
        ]
        | MISSING = MISSING,
        set_warehouse: Annotated[
            str,
            Field(description="Default warehouse for all items (e.g. 'Stores - CI')."),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Sales Order. Requires customer and at least one item with item_code, qty, rate. On a fresh ERPNext instance, you may also need to set company, selling_price_list, and currency."
        return await dispatch(
            "erpnext_sales_order_create",
            {
                key: value
                for key, value in {
                    "customer": customer,
                    "items": items,
                    "delivery_date": delivery_date,
                    "company": company,
                    "selling_price_list": selling_price_list,
                    "currency": currency,
                    "set_warehouse": set_warehouse,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_sales_order_update(
        *,
        name: Annotated[str, Field(description="Sales Order name (e.g. SO-00001)")],
        delivery_date: Annotated[str, Field(description="New delivery date YYYY-MM-DD")]
        | MISSING = MISSING,
        items: Annotated[
            list[ErpnextSalesOrderUpdateItemsItem],
            Field(description="Replacement item list: [{item_code, qty, rate}]"),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Update an existing Sales Order (only in Draft status). Pass only the fields you want to change (e.g. delivery_date, items)."
        return await dispatch(
            "erpnext_sales_order_update",
            {
                key: value
                for key, value in {
                    "name": name,
                    "delivery_date": delivery_date,
                    "items": items,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_sales_order_submit(
        *,
        name: Annotated[str, Field(description="Sales Order name (e.g. SO-00001)")],
    ) -> ToolResult:
        "Submit a Draft Sales Order (changes status to 'To Deliver and Bill'). Triggers stock reservation and fulfillment workflow."
        return await dispatch("erpnext_sales_order_submit", {"name": name})

    @mcp.tool
    async def erpnext_sales_order_cancel(
        *,
        name: Annotated[str, Field(description="Sales Order name (e.g. SO-00001)")],
    ) -> ToolResult:
        "Cancel a submitted Sales Order. Reverses stock reservation. Only works on submitted (non-completed) Sales Orders."
        return await dispatch("erpnext_sales_order_cancel", {"name": name})

    @mcp.tool
    async def erpnext_sales_invoice_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        customer: Annotated[
            str,
            Field(
                description="Filter by customer ID or name (e.g. 'CUST-00001' or 'Acme Corp')"
            ),
        ]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, Unpaid, Paid, Overdue, Cancelled, etc.)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Sales Invoices. Filterable by customer, status, date range. Fields: name, customer, posting_date, due_date, status, grand_total, outstanding_amount."
        return await dispatch(
            "erpnext_sales_invoice_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "customer": customer,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_sales_invoice_get(
        *,
        name: Annotated[str, Field(description="Sales Invoice name (e.g. SINV-00001)")],
    ) -> ToolResult:
        "Get a single Sales Invoice by name (e.g. SINV-00001). Returns full document with line items."
        return await dispatch("erpnext_sales_invoice_get", {"name": name})

    @mcp.tool
    async def erpnext_sales_invoice_create(
        *,
        customer: Annotated[str, Field(description="Customer name (ID)")],
        items: Annotated[
            list[ErpnextSalesInvoiceCreateItemsItem],
            Field(description="Line items: [{item_code, qty, rate, warehouse?}]"),
        ],
        posting_date: Annotated[
            str, Field(description="Invoice date YYYY-MM-DD (default: today)")
        ]
        | MISSING = MISSING,
        due_date: Annotated[str, Field(description="Payment due date YYYY-MM-DD")]
        | MISSING = MISSING,
        company: Annotated[
            str,
            Field(description="Company name. Required if multiple companies exist."),
        ]
        | MISSING = MISSING,
        selling_price_list: Annotated[
            str,
            Field(
                description="Price list name (e.g. 'Standard Selling'). Required if no default is set."
            ),
        ]
        | MISSING = MISSING,
        currency: Annotated[
            str,
            Field(
                description="Transaction currency (e.g. 'EUR', 'USD'). Defaults to company currency."
            ),
        ]
        | MISSING = MISSING,
        set_warehouse: Annotated[
            str, Field(description="Default warehouse for all items.")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Sales Invoice. Requires customer and at least one item. On a fresh ERPNext instance, you may also need to set company, selling_price_list, and currency. To generate from a Sales Order, use erpnext_doc_update to set is_return etc."
        return await dispatch(
            "erpnext_sales_invoice_create",
            {
                key: value
                for key, value in {
                    "customer": customer,
                    "items": items,
                    "posting_date": posting_date,
                    "due_date": due_date,
                    "company": company,
                    "selling_price_list": selling_price_list,
                    "currency": currency,
                    "set_warehouse": set_warehouse,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_sales_invoice_submit(
        *,
        name: Annotated[str, Field(description="Sales Invoice name (e.g. SINV-00001)")],
    ) -> ToolResult:
        "Submit a Draft Sales Invoice (posts it to the ledger, changes status to 'Unpaid'). Once submitted, the invoice is visible to the customer and affects GL."
        return await dispatch("erpnext_sales_invoice_submit", {"name": name})

    @mcp.tool
    async def erpnext_quotation_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        quotation_to: Annotated[
            Literal["Customer", "Lead"],
            Field(
                description="Party type: Customer or Lead. Required when 'party_name' is set, so the party name/ID can be resolved against the right doctype."
            ),
        ]
        | MISSING = MISSING,
        party_name: Annotated[
            str,
            Field(
                description="Filter by party — ID or name (e.g. customer/lead name). Requires 'quotation_to'."
            ),
        ]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, Open, Replied, Ordered, Lost, Cancelled)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Quotations. Filterable by party_name, status. Fields: name, party_name, transaction_date, status, grand_total."
        return await dispatch(
            "erpnext_quotation_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "quotation_to": quotation_to,
                    "party_name": party_name,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_quotation_get(
        *,
        name: Annotated[str, Field(description="Quotation name (e.g. QTN-00001)")],
    ) -> ToolResult:
        "Get a single Quotation by name. Returns full document with line items and terms."
        return await dispatch("erpnext_quotation_get", {"name": name})

    @mcp.tool
    async def erpnext_quotation_create(
        *,
        quotation_to: Annotated[
            Literal["Customer", "Lead"],
            Field(description="Party type: Customer or Lead"),
        ],
        party_name: Annotated[str, Field(description="Customer or Lead — ID or name")],
        items: Annotated[
            list[ErpnextQuotationCreateItemsItem],
            Field(description="Line items: [{item_code, qty, rate}]"),
        ],
        transaction_date: Annotated[
            str, Field(description="Quotation date YYYY-MM-DD (default: today)")
        ]
        | MISSING = MISSING,
        valid_till: Annotated[str, Field(description="Validity date YYYY-MM-DD")]
        | MISSING = MISSING,
        company: Annotated[
            str,
            Field(description="Company name. Required if multiple companies exist."),
        ]
        | MISSING = MISSING,
        selling_price_list: Annotated[
            str, Field(description="Price list name (e.g. 'Standard Selling').")
        ]
        | MISSING = MISSING,
        currency: Annotated[
            str, Field(description="Transaction currency (e.g. 'EUR', 'USD').")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Quotation for a customer or lead. Requires quotation_to (Customer or Lead), party_name, and at least one item."
        return await dispatch(
            "erpnext_quotation_create",
            {
                key: value
                for key, value in {
                    "quotation_to": quotation_to,
                    "party_name": party_name,
                    "items": items,
                    "transaction_date": transaction_date,
                    "valid_till": valid_till,
                    "company": company,
                    "selling_price_list": selling_price_list,
                    "currency": currency,
                }.items()
                if value is not MISSING
            },
        )

    return (
        erpnext_item_list,
        erpnext_item_get,
        erpnext_item_create,
        erpnext_item_update,
        erpnext_stock_balance,
        erpnext_warehouse_list,
        erpnext_stock_entry_list,
        erpnext_stock_entry_get,
        erpnext_stock_entry_create,
        erpnext_doc_submit,
        erpnext_doc_cancel,
        erpnext_customer_list,
        erpnext_customer_get,
        erpnext_customer_create,
        erpnext_customer_update,
        erpnext_sales_order_list,
        erpnext_sales_order_get,
        erpnext_sales_order_create,
        erpnext_sales_order_update,
        erpnext_sales_order_submit,
        erpnext_sales_order_cancel,
        erpnext_sales_invoice_list,
        erpnext_sales_invoice_get,
        erpnext_sales_invoice_create,
        erpnext_sales_invoice_submit,
        erpnext_quotation_list,
        erpnext_quotation_get,
        erpnext_quotation_create,
    )
