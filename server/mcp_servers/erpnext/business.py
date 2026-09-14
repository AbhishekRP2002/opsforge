"""Erpnext business tool declarations."""

from typing import Annotated, Literal, NotRequired

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import ConfigDict, Field, with_config
from pydantic.experimental.missing_sentinel import MISSING
from typing_extensions import TypedDict


@with_config(ConfigDict(extra="allow"))
class ErpnextDeliveryNoteCreateItemsItem(TypedDict):
    item_code: str
    qty: float
    against_sales_order: NotRequired[
        Annotated[str, Field(description="Sales Order reference (e.g. SO-00001)")]
    ]


@with_config(ConfigDict(extra="allow"))
class ErpnextPurchaseOrderCreateItemsItem(TypedDict):
    item_code: str
    qty: float
    rate: float


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def erpnext_asset_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, Submitted, Partially Depreciated, Fully Depreciated, Scrapped, Sold)"
            ),
        ]
        | MISSING = MISSING,
        asset_category: Annotated[str, Field(description="Filter by asset category")]
        | MISSING = MISSING,
        location: Annotated[str, Field(description="Filter by location")]
        | MISSING = MISSING,
        custodian: Annotated[
            str,
            Field(
                description="Filter by custodian — employee ID or name (e.g. 'HR-EMP-00001' or 'John Doe')"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[
            str, Field(description="Purchase date start filter YYYY-MM-DD")
        ]
        | MISSING = MISSING,
        date_to: Annotated[
            str, Field(description="Purchase date end filter YYYY-MM-DD")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Fixed Assets. Filterable by status, asset_category, location, custodian. Fields: name, asset_name, asset_category, status, purchase_date, gross_purchase_amount, current_value, location, custodian."
        return await dispatch(
            "erpnext_asset_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "status": status,
                    "asset_category": asset_category,
                    "location": location,
                    "custodian": custodian,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_asset_get(
        *,
        name: Annotated[str, Field(description="Asset name (ID)")],
    ) -> ToolResult:
        "Get a single Asset by name. Returns full details including depreciation schedule and maintenance logs."
        return await dispatch("erpnext_asset_get", {"name": name})

    @mcp.tool
    async def erpnext_asset_create(
        *,
        asset_name: Annotated[str, Field(description="Name/description of the asset")],
        asset_category: Annotated[
            str, Field(description="Asset category (e.g. Computers, Vehicles)")
        ],
        company: Annotated[str, Field(description="Company owning the asset")],
        purchase_date: Annotated[str, Field(description="Purchase date YYYY-MM-DD")],
        gross_purchase_amount: Annotated[
            float, Field(description="Purchase cost (before depreciation)")
        ],
        item_code: Annotated[str, Field(description="Linked item code (optional)")]
        | MISSING = MISSING,
        location: Annotated[str, Field(description="Physical location of the asset")]
        | MISSING = MISSING,
        custodian: Annotated[
            str, Field(description="Employee responsible for the asset")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Asset record. Requires asset_name, asset_category, company, purchase_date, gross_purchase_amount. Optionally set location, custodian, item_code."
        return await dispatch(
            "erpnext_asset_create",
            {
                key: value
                for key, value in {
                    "asset_name": asset_name,
                    "asset_category": asset_category,
                    "company": company,
                    "purchase_date": purchase_date,
                    "gross_purchase_amount": gross_purchase_amount,
                    "item_code": item_code,
                    "location": location,
                    "custodian": custodian,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_asset_movement_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        purpose: Annotated[
            str, Field(description="Filter by purpose (Issue, Transfer, Receipt)")
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Transaction date from YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="Transaction date to YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Asset Movements (transfers between locations/custodians). Fields: name, transaction_date, purpose, company."
        return await dispatch(
            "erpnext_asset_movement_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "purpose": purpose,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_asset_movement_get(
        *,
        name: Annotated[str, Field(description="Asset Movement name (ID)")],
    ) -> ToolResult:
        "Get a single Asset Movement by name. Returns full details including assets moved."
        return await dispatch("erpnext_asset_movement_get", {"name": name})

    @mcp.tool
    async def erpnext_asset_maintenance_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        asset_name: Annotated[str, Field(description="Filter by asset name")]
        | MISSING = MISSING,
        maintenance_status: Annotated[
            str,
            Field(
                description="Filter by status (Planned, Overdue, Cancelled, Completed)"
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Asset Maintenance records. Filterable by asset_name, maintenance_status. Fields: name, asset_name, asset_category, maintenance_team, maintenance_status."
        return await dispatch(
            "erpnext_asset_maintenance_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "asset_name": asset_name,
                    "maintenance_status": maintenance_status,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_asset_maintenance_get(
        *,
        name: Annotated[str, Field(description="Asset Maintenance name (ID)")],
    ) -> ToolResult:
        "Get a single Asset Maintenance record by name. Returns full details including maintenance tasks."
        return await dispatch("erpnext_asset_maintenance_get", {"name": name})

    @mcp.tool
    async def erpnext_asset_category_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Asset Categories. Fields: name, asset_category_name."
        return await dispatch(
            "erpnext_asset_category_list",
            {
                key: value
                for key, value in {"limit": limit}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_lead_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Open, Replied, Opportunity, Interested, Converted, Do Not Contact)"
            ),
        ]
        | MISSING = MISSING,
        lead_owner: Annotated[
            str, Field(description="Filter by assigned sales rep (user)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List CRM Leads. Filterable by status, lead_owner. Fields: name, lead_name, company_name, status, lead_owner, email_id, mobile_no."
        return await dispatch(
            "erpnext_lead_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "status": status,
                    "lead_owner": lead_owner,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_lead_get(
        *,
        name: Annotated[str, Field(description="Lead name (ID)")],
    ) -> ToolResult:
        "Get a single CRM Lead by name. Returns all lead details including contact info."
        return await dispatch("erpnext_lead_get", {"name": name})

    @mcp.tool
    async def erpnext_lead_create(
        *,
        lead_name: Annotated[str, Field(description="Full name of the lead contact")],
        company_name: Annotated[str, Field(description="Company name")]
        | MISSING = MISSING,
        email_id: Annotated[str, Field(description="Email address")]
        | MISSING = MISSING,
        mobile_no: Annotated[str, Field(description="Mobile number")]
        | MISSING = MISSING,
        source: Annotated[
            str,
            Field(
                description="Lead source (Cold Calling, Website, Advertisement, etc.)"
            ),
        ]
        | MISSING = MISSING,
        lead_owner: Annotated[
            str, Field(description="Assigned sales rep (ERPNext user)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new CRM Lead. Requires lead_name. Optionally set company_name, email_id, mobile_no, source."
        return await dispatch(
            "erpnext_lead_create",
            {
                key: value
                for key, value in {
                    "lead_name": lead_name,
                    "company_name": company_name,
                    "email_id": email_id,
                    "mobile_no": mobile_no,
                    "source": source,
                    "lead_owner": lead_owner,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_opportunity_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Open, Quotation, Converted, Lost, Closed)"
            ),
        ]
        | MISSING = MISSING,
        opportunity_owner: Annotated[
            str, Field(description="Filter by assigned sales rep (user)")
        ]
        | MISSING = MISSING,
        opportunity_from: Annotated[
            Literal["Customer", "Lead"],
            Field(
                description="Party type: Customer or Lead. Required when 'party_name' is set, so the party name/ID can be resolved against the right doctype."
            ),
        ]
        | MISSING = MISSING,
        party_name: Annotated[
            str,
            Field(
                description="Filter by party — ID or name (e.g. customer/lead name). Requires 'opportunity_from'."
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List CRM Opportunities. Filterable by status, opportunity_owner, opportunity_from. Fields: name, opportunity_from, party_name, status, opportunity_amount, currency, probability, opportunity_owner."
        return await dispatch(
            "erpnext_opportunity_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "status": status,
                    "opportunity_owner": opportunity_owner,
                    "opportunity_from": opportunity_from,
                    "party_name": party_name,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_opportunity_get(
        *,
        name: Annotated[str, Field(description="Opportunity name (ID)")],
    ) -> ToolResult:
        "Get a single CRM Opportunity by name. Returns full details including items and competitors."
        return await dispatch("erpnext_opportunity_get", {"name": name})

    @mcp.tool
    async def erpnext_contact_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        company_name: Annotated[str, Field(description="Filter by company name")]
        | MISSING = MISSING,
        status: Annotated[
            str, Field(description="Filter by status (Passive, Open, Replied)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Contacts. Filterable by company_name, status. Fields: name, first_name, last_name, company_name, email_id, mobile_no, status."
        return await dispatch(
            "erpnext_contact_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "company_name": company_name,
                    "status": status,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_contact_get(
        *,
        name: Annotated[str, Field(description="Contact name (ID)")],
    ) -> ToolResult:
        "Get a single Contact by name. Returns all contact details."
        return await dispatch("erpnext_contact_get", {"name": name})

    @mcp.tool
    async def erpnext_campaign_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        campaign_type: Annotated[str, Field(description="Filter by campaign type")]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List CRM Campaigns. Fields: name, campaign_name, campaign_type, start_date, end_date, description."
        return await dispatch(
            "erpnext_campaign_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "campaign_type": campaign_type,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_delivery_note_list(
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
                description="Filter by status (Draft, To Bill, Completed, Cancelled, etc.)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Delivery Notes. Filterable by customer, status, date range. Fields: name, customer, posting_date, status, total_qty, grand_total."
        return await dispatch(
            "erpnext_delivery_note_list",
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
    async def erpnext_delivery_note_get(
        *,
        name: Annotated[
            str, Field(description="Delivery Note name (e.g. MAT-DN-00001)")
        ],
    ) -> ToolResult:
        "Get a single Delivery Note by name (e.g. MAT-DN-00001). Returns full document with delivered items."
        return await dispatch("erpnext_delivery_note_get", {"name": name})

    @mcp.tool
    async def erpnext_delivery_note_create(
        *,
        customer: Annotated[str, Field(description="Customer name (ID)")],
        items: Annotated[
            list[ErpnextDeliveryNoteCreateItemsItem],
            Field(description="Line items: [{item_code, qty, against_sales_order?}]"),
        ],
        posting_date: Annotated[
            str, Field(description="Posting date YYYY-MM-DD (default: today)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Delivery Note. Requires customer and at least one item with item_code, qty. Typically created against a Sales Order."
        return await dispatch(
            "erpnext_delivery_note_create",
            {
                key: value
                for key, value in {
                    "customer": customer,
                    "items": items,
                    "posting_date": posting_date,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_shipment_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, Submitted, Booked, Delivered, Cancelled, etc.)"
            ),
        ]
        | MISSING = MISSING,
        carrier: Annotated[str, Field(description="Filter by carrier name")]
        | MISSING = MISSING,
        date_from: Annotated[
            str, Field(description="Pickup date start filter YYYY-MM-DD")
        ]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="Pickup date end filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Shipments. Filterable by status, pickup_from date range. Fields: name, status, pickup_date, delivery_date, carrier, shipment_amount."
        return await dispatch(
            "erpnext_shipment_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "status": status,
                    "carrier": carrier,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_shipment_get(
        *,
        name: Annotated[str, Field(description="Shipment name (ID)")],
    ) -> ToolResult:
        "Get a single Shipment by name. Returns full shipment details including parcels."
        return await dispatch("erpnext_shipment_get", {"name": name})

    @mcp.tool
    async def erpnext_bom_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        item: Annotated[
            str,
            Field(
                description="Filter by finished goods item code or name (e.g. 'ITEM-001' or 'Widget A')"
            ),
        ]
        | MISSING = MISSING,
        is_active: Annotated[
            bool, Field(description="Filter by active status (default: all)")
        ]
        | MISSING = MISSING,
        is_default: Annotated[bool, Field(description="Filter for default BOMs only")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Bills of Materials (BOM). Filterable by item, is_active, is_default. Fields: name, item, item_name, quantity, uom, is_active, is_default, total_cost."
        return await dispatch(
            "erpnext_bom_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "item": item,
                    "is_active": is_active,
                    "is_default": is_default,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_bom_get(
        *,
        name: Annotated[str, Field(description="BOM name (e.g. BOM-ITEM-00001)")],
    ) -> ToolResult:
        "Get a single BOM by name (e.g. BOM-ITEM-00001). Returns full document with raw materials and operations."
        return await dispatch("erpnext_bom_get", {"name": name})

    @mcp.tool
    async def erpnext_work_order_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        production_item: Annotated[
            str,
            Field(
                description="Filter by item being produced — item code or name (e.g. 'ITEM-001' or 'Widget A')"
            ),
        ]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, Submitted, Not Started, In Process, Completed, Stopped, etc.)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[
            str, Field(description="Planned start date from YYYY-MM-DD")
        ]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="Planned start date to YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Work Orders. Filterable by production_item, status, date range. Fields: name, production_item, qty, produced_qty, status, planned_start_date, planned_end_date."
        return await dispatch(
            "erpnext_work_order_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "production_item": production_item,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_work_order_get(
        *,
        name: Annotated[str, Field(description="Work Order name (e.g. MFG-WO-00001)")],
    ) -> ToolResult:
        "Get a single Work Order by name (e.g. MFG-WO-00001). Returns full document with operations and materials."
        return await dispatch("erpnext_work_order_get", {"name": name})

    @mcp.tool
    async def erpnext_work_order_create(
        *,
        production_item: Annotated[
            str, Field(description="Item code of the item to produce")
        ],
        bom_no: Annotated[str, Field(description="BOM to use (e.g. BOM-ITEM-00001)")],
        qty: Annotated[float, Field(description="Quantity to produce")],
        planned_start_date: Annotated[
            str, Field(description="Planned start date YYYY-MM-DD")
        ]
        | MISSING = MISSING,
        wip_warehouse: Annotated[str, Field(description="Work-In-Progress warehouse")]
        | MISSING = MISSING,
        fg_warehouse: Annotated[
            str, Field(description="Finished Goods target warehouse")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Work Order for manufacturing. Requires production_item, bom_no, and qty. Optionally set planned_start_date and wip_warehouse."
        return await dispatch(
            "erpnext_work_order_create",
            {
                key: value
                for key, value in {
                    "production_item": production_item,
                    "bom_no": bom_no,
                    "qty": qty,
                    "planned_start_date": planned_start_date,
                    "wip_warehouse": wip_warehouse,
                    "fg_warehouse": fg_warehouse,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_job_card_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        work_order: Annotated[str, Field(description="Filter by Work Order")]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Open, Work In Progress, Completed, Cancelled)"
            ),
        ]
        | MISSING = MISSING,
        operation: Annotated[str, Field(description="Filter by operation name")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Job Cards (production operations tracking). Filterable by work_order, status, operation. Fields: name, work_order, operation, status, for_quantity, total_completed_qty, workstation."
        return await dispatch(
            "erpnext_job_card_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "work_order": work_order,
                    "status": status,
                    "operation": operation,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_job_card_get(
        *,
        name: Annotated[str, Field(description="Job Card name (ID)")],
    ) -> ToolResult:
        "Get a single Job Card by name. Returns full document with time logs and material transfers."
        return await dispatch("erpnext_job_card_get", {"name": name})

    @mcp.tool
    async def erpnext_supplier_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        supplier_group: Annotated[str, Field(description="Filter by supplier group")]
        | MISSING = MISSING,
        supplier_type: Annotated[
            str, Field(description="Filter by supplier type (Company, Individual)")
        ]
        | MISSING = MISSING,
        include_disabled: Annotated[
            bool, Field(description="Include disabled suppliers (default false)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List ERPNext suppliers. Returns active suppliers by default. Fields: name, supplier_name, supplier_group, supplier_type, email_id, disabled."
        return await dispatch(
            "erpnext_supplier_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "supplier_group": supplier_group,
                    "supplier_type": supplier_type,
                    "include_disabled": include_disabled,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_supplier_get(
        *,
        name: Annotated[str, Field(description="Supplier name (ID)")],
    ) -> ToolResult:
        "Get a single ERPNext supplier by name (ID). Returns all fields including contact details."
        return await dispatch("erpnext_supplier_get", {"name": name})

    @mcp.tool
    async def erpnext_supplier_create(
        *,
        supplier_name: Annotated[
            str, Field(description="Supplier company or person name")
        ],
        supplier_group: Annotated[
            str, Field(description="Supplier Group (e.g. 'Hardware', 'Services')")
        ],
        supplier_type: Annotated[
            str, Field(description="Company or Individual (default Company)")
        ]
        | MISSING = MISSING,
        country: Annotated[str, Field(description="Country name")] | MISSING = MISSING,
        default_currency: Annotated[
            str, Field(description="Currency code (e.g. EUR, USD)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new ERPNext Supplier. Requires supplier_name and supplier_group. Returns the created supplier document."
        return await dispatch(
            "erpnext_supplier_create",
            {
                key: value
                for key, value in {
                    "supplier_name": supplier_name,
                    "supplier_group": supplier_group,
                    "supplier_type": supplier_type,
                    "country": country,
                    "default_currency": default_currency,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_purchase_order_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        supplier: Annotated[
            str,
            Field(
                description="Filter by supplier ID or name (e.g. 'SUPP-00001' or 'Acme Supplies')"
            ),
        ]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, To Receive and Bill, To Bill, Completed, Cancelled, etc.)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Purchase Orders. Filterable by supplier, status, date range. Fields: name, supplier, transaction_date, schedule_date, status, grand_total, currency."
        return await dispatch(
            "erpnext_purchase_order_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "supplier": supplier,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_purchase_order_get(
        *,
        name: Annotated[str, Field(description="Purchase Order name (e.g. PO-00001)")],
    ) -> ToolResult:
        "Get a single Purchase Order by name (e.g. PO-00001). Returns full document with line items."
        return await dispatch("erpnext_purchase_order_get", {"name": name})

    @mcp.tool
    async def erpnext_purchase_order_create(
        *,
        supplier: Annotated[
            str,
            Field(
                description="Supplier name or ID — a unique name resolves automatically"
            ),
        ],
        items: Annotated[
            list[ErpnextPurchaseOrderCreateItemsItem],
            Field(description="Line items: [{item_code, qty, rate}]"),
        ],
        schedule_date: Annotated[
            str, Field(description="Expected delivery date YYYY-MM-DD")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Create a new Purchase Order. Requires supplier and at least one item with item_code, qty, rate. Optionally set schedule_date (YYYY-MM-DD)."
        return await dispatch(
            "erpnext_purchase_order_create",
            {
                key: value
                for key, value in {
                    "supplier": supplier,
                    "items": items,
                    "schedule_date": schedule_date,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_purchase_invoice_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        supplier: Annotated[
            str,
            Field(
                description="Filter by supplier ID or name (e.g. 'SUPP-00001' or 'Acme Supplies')"
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
        "List Purchase Invoices (bills from suppliers). Filterable by supplier, status, date range. Fields: name, supplier, posting_date, due_date, status, grand_total, outstanding_amount."
        return await dispatch(
            "erpnext_purchase_invoice_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "supplier": supplier,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_purchase_invoice_get(
        *,
        name: Annotated[
            str, Field(description="Purchase Invoice name (e.g. PINV-00001)")
        ],
    ) -> ToolResult:
        "Get a single Purchase Invoice by name (e.g. PINV-00001). Returns full document with line items."
        return await dispatch("erpnext_purchase_invoice_get", {"name": name})

    @mcp.tool
    async def erpnext_purchase_receipt_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        supplier: Annotated[
            str,
            Field(
                description="Filter by supplier ID or name (e.g. 'SUPP-00001' or 'Acme Supplies')"
            ),
        ]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, To Bill, Completed, Cancelled, etc.)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Purchase Receipts (goods received notes). Filterable by supplier, status, date range. Fields: name, supplier, posting_date, status, total_qty, grand_total."
        return await dispatch(
            "erpnext_purchase_receipt_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "supplier": supplier,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_purchase_receipt_get(
        *,
        name: Annotated[
            str, Field(description="Purchase Receipt name (e.g. MAT-PRE-00001)")
        ],
    ) -> ToolResult:
        "Get a single Purchase Receipt by name (e.g. MAT-PRE-00001). Returns full document with received items."
        return await dispatch("erpnext_purchase_receipt_get", {"name": name})

    @mcp.tool
    async def erpnext_supplier_quotation_list(
        *,
        limit: Annotated[float, Field(description="Max results (default 20)")]
        | MISSING = MISSING,
        supplier: Annotated[
            str,
            Field(
                description="Filter by supplier ID or name (e.g. 'SUPP-00001' or 'Acme Supplies')"
            ),
        ]
        | MISSING = MISSING,
        status: Annotated[
            str,
            Field(
                description="Filter by status (Draft, Submitted, Ordered, Lost, Cancelled)"
            ),
        ]
        | MISSING = MISSING,
        date_from: Annotated[str, Field(description="Start date filter YYYY-MM-DD")]
        | MISSING = MISSING,
        date_to: Annotated[str, Field(description="End date filter YYYY-MM-DD")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "List Supplier Quotations (RFQ responses from suppliers). Filterable by supplier, status. Fields: name, supplier, transaction_date, status, grand_total."
        return await dispatch(
            "erpnext_supplier_quotation_list",
            {
                key: value
                for key, value in {
                    "limit": limit,
                    "supplier": supplier,
                    "status": status,
                    "date_from": date_from,
                    "date_to": date_to,
                }.items()
                if value is not MISSING
            },
        )

    return (
        erpnext_asset_list,
        erpnext_asset_get,
        erpnext_asset_create,
        erpnext_asset_movement_list,
        erpnext_asset_movement_get,
        erpnext_asset_maintenance_list,
        erpnext_asset_maintenance_get,
        erpnext_asset_category_list,
        erpnext_lead_list,
        erpnext_lead_get,
        erpnext_lead_create,
        erpnext_opportunity_list,
        erpnext_opportunity_get,
        erpnext_contact_list,
        erpnext_contact_get,
        erpnext_campaign_list,
        erpnext_delivery_note_list,
        erpnext_delivery_note_get,
        erpnext_delivery_note_create,
        erpnext_shipment_list,
        erpnext_shipment_get,
        erpnext_bom_list,
        erpnext_bom_get,
        erpnext_work_order_list,
        erpnext_work_order_get,
        erpnext_work_order_create,
        erpnext_job_card_list,
        erpnext_job_card_get,
        erpnext_supplier_list,
        erpnext_supplier_get,
        erpnext_supplier_create,
        erpnext_purchase_order_list,
        erpnext_purchase_order_get,
        erpnext_purchase_order_create,
        erpnext_purchase_invoice_list,
        erpnext_purchase_invoice_get,
        erpnext_purchase_receipt_list,
        erpnext_purchase_receipt_get,
        erpnext_supplier_quotation_list,
    )
