"""Erpnext analytics tool declarations."""

from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field
from pydantic.experimental.missing_sentinel import MISSING


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def erpnext_stock_chart(
        *,
        warehouse: Annotated[str, Field(description="Filter by warehouse name")]
        | MISSING = MISSING,
        item_group: Annotated[str, Field(description="Filter by item group")]
        | MISSING = MISSING,
        limit: Annotated[float, Field(description="Max items to show (default 20)")]
        | MISSING = MISSING,
        type: Annotated[
            Literal["bar", "horizontal-bar"],
            Field(
                description="Chart type (default: horizontal-bar for many items, bar for few)"
            ),
        ]
        | MISSING = MISSING,
        min_qty: Annotated[
            float,
            Field(
                description="Only show items with qty >= this value (filters out zeros)"
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Get stock levels as a bar chart. Shows actual_qty per item (optionally filtered by warehouse). Groups items and returns chart-ready data. Use type='horizontal-bar' for readability with many items."
        return await dispatch(
            "erpnext_stock_chart",
            {
                key: value
                for key, value in {
                    "warehouse": warehouse,
                    "item_group": item_group,
                    "limit": limit,
                    "type": type,
                    "min_qty": min_qty,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_sales_chart(
        *,
        group_by: Annotated[
            Literal["customer", "item", "status"],
            Field(description="Dimension to group by (default: customer)"),
        ]
        | MISSING = MISSING,
        limit: Annotated[float, Field(description="Top N results (default 10)")]
        | MISSING = MISSING,
        include_drafts: Annotated[
            bool, Field(description="Include Draft invoices (default false)")
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Analyze sales revenue as a chart. group_by='customer' → bar chart of top customers by revenue. group_by='item' → bar chart of top items sold. group_by='status' → donut chart of invoice status breakdown. Reads from Sales Invoice (submitted only by default)."
        return await dispatch(
            "erpnext_sales_chart",
            {
                key: value
                for key, value in {
                    "group_by": group_by,
                    "limit": limit,
                    "include_drafts": include_drafts,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_revenue_trend(
        *,
        months: Annotated[
            float, Field(description="How many months back to include (default 6)")
        ]
        | MISSING = MISSING,
        type: Annotated[
            Literal["line", "area", "stacked-area"],
            Field(description="Chart type (default: line)"),
        ]
        | MISSING = MISSING,
        group_by: Annotated[
            Literal["total", "customer"],
            Field(description="Group by total or per customer (default: total)"),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Sales revenue trend over time. Returns a line chart (or area if type='area') with monthly revenue from Sales Orders. Add group_by='customer' for multi-line per customer. Use type='stacked-area' to stack customers."
        return await dispatch(
            "erpnext_revenue_trend",
            {
                key: value
                for key, value in {
                    "months": months,
                    "type": type,
                    "group_by": group_by,
                }.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_order_breakdown(
        *,
        type: Annotated[
            Literal["stacked-bar", "pie", "donut"],
            Field(description="Chart type (default: stacked-bar)"),
        ]
        | MISSING = MISSING,
        limit: Annotated[float, Field(description="Top N customers (default 8)")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Breakdown of Sales Orders by customer (stacked-bar by status) or as a pie chart of totals. type='stacked-bar' → orders stacked by status per customer. type='pie' → total order value per customer as pie. type='donut' → same as pie but with donut hole."
        return await dispatch(
            "erpnext_order_breakdown",
            {
                key: value
                for key, value in {"type": type, "limit": limit}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_revenue_vs_orders(
        *,
        limit: Annotated[float, Field(description="Top N customers (default 8)")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Composed chart (bar + line) showing revenue (bars, left axis) vs order count (line, right axis) per customer. Demonstrates dual-axis composed chart."
        return await dispatch(
            "erpnext_revenue_vs_orders",
            {
                key: value
                for key, value in {"limit": limit}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_stock_treemap(
        *,
        group_by: Annotated[
            Literal["item", "warehouse"],
            Field(description="Group by item or warehouse (default: item)"),
        ]
        | MISSING = MISSING,
        limit: Annotated[float, Field(description="Top N entries (default 15)")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Stock value as a treemap. Each rectangle represents an item, sized by stock value. Use group_by='warehouse' to group by warehouse instead."
        return await dispatch(
            "erpnext_stock_treemap",
            {
                key: value
                for key, value in {"group_by": group_by, "limit": limit}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_product_radar(
        *,
        items: Annotated[
            list[str],
            Field(
                max_length=8,
                description="2-8 item codes to compare. Leave empty for auto-select top items.",
            ),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Radar chart comparing items across multiple dimensions: stock level, stock value, order frequency, and revenue. Pass 2-8 item codes to compare, or none to auto-select top items."
        return await dispatch(
            "erpnext_product_radar",
            {
                key: value
                for key, value in {"items": items}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_price_vs_qty(
        *,
        limit: Annotated[float, Field(description="Max items to show (default 30)")]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Scatter chart: item selling price (X) vs total qty ordered (Y). Each point is an item. Colored by item group if available."
        return await dispatch(
            "erpnext_price_vs_qty",
            {
                key: value
                for key, value in {"limit": limit}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_kpi_revenue() -> ToolResult:
        "KPI card: total Sales Order revenue for the current month, with delta % vs previous month and sparkline of last 6 months."
        return await dispatch("erpnext_kpi_revenue", {})

    @mcp.tool
    async def erpnext_kpi_outstanding() -> ToolResult:
        "KPI card: total outstanding receivables from submitted Sales Invoices with outstanding_amount > 0. Shows count of open invoices."
        return await dispatch("erpnext_kpi_outstanding", {})

    @mcp.tool
    async def erpnext_kpi_orders() -> ToolResult:
        "KPI card: count and total value of Sales Orders created this month, with delta % vs last month."
        return await dispatch("erpnext_kpi_orders", {})

    @mcp.tool
    async def erpnext_kpi_gross_margin() -> ToolResult:
        "KPI card: estimated gross margin % based on Sales Order revenue vs valuation rate from stock (Bin). Margin = (revenue - cost) / revenue * 100."
        return await dispatch("erpnext_kpi_gross_margin", {})

    @mcp.tool
    async def erpnext_kpi_overdue() -> ToolResult:
        "KPI card: count and total value of overdue Sales Invoices (due_date < today, outstanding_amount > 0, submitted)."
        return await dispatch("erpnext_kpi_overdue", {})

    @mcp.tool
    async def erpnext_sales_funnel(
        *,
        period: Annotated[
            Literal["this_month", "this_quarter", "this_year", "all"],
            Field(description="Time period (default: all)"),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Sales funnel from Lead → Opportunity → Quotation → Sales Order. Shows count and value at each stage with conversion rates between stages."
        return await dispatch(
            "erpnext_sales_funnel",
            {
                key: value
                for key, value in {"period": period}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_ar_aging(
        *,
        limit: Annotated[float, Field(description="Top N customers (default 10)")]
        | MISSING = MISSING,
        type: Annotated[
            Literal["stacked-bar", "horizontal-bar", "treemap"],
            Field(description="Chart type (default: stacked-bar)"),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Accounts Receivable Aging — stacked bar showing outstanding invoices by customer, grouped into aging buckets (0-30, 31-60, 61-90, 90+ days). Shows who owes you money and for how long."
        return await dispatch(
            "erpnext_ar_aging",
            {
                key: value
                for key, value in {"limit": limit, "type": type}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_gross_profit(
        *,
        limit: Annotated[float, Field(description="Top N entries (default 10)")]
        | MISSING = MISSING,
        group_by: Annotated[
            Literal["item", "customer"],
            Field(description="Group by item or customer (default: item)"),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Gross profit analysis — composed chart showing revenue (bars) vs margin % (line) by item or customer. Uses Sales Invoice Item for revenue and Bin valuation_rate for cost estimation."
        return await dispatch(
            "erpnext_gross_profit",
            {
                key: value
                for key, value in {"limit": limit, "group_by": group_by}.items()
                if value is not MISSING
            },
        )

    @mcp.tool
    async def erpnext_profit_loss(
        *,
        months: Annotated[float, Field(description="How many months back (default 6)")]
        | MISSING = MISSING,
        type: Annotated[
            Literal["bar", "stacked-bar", "composed"],
            Field(description="Chart type (default: composed)"),
        ]
        | MISSING = MISSING,
    ) -> ToolResult:
        "Profit & Loss overview — bar chart comparing total income vs total expenses per month from Sales Orders (income) and Purchase Orders (expenses). Shows net profit line. Use type='composed' for bar+line."
        return await dispatch(
            "erpnext_profit_loss",
            {
                key: value
                for key, value in {"months": months, "type": type}.items()
                if value is not MISSING
            },
        )

    return (
        erpnext_stock_chart,
        erpnext_sales_chart,
        erpnext_revenue_trend,
        erpnext_order_breakdown,
        erpnext_revenue_vs_orders,
        erpnext_stock_treemap,
        erpnext_product_radar,
        erpnext_price_vs_qty,
        erpnext_kpi_revenue,
        erpnext_kpi_outstanding,
        erpnext_kpi_orders,
        erpnext_kpi_gross_margin,
        erpnext_kpi_overdue,
        erpnext_sales_funnel,
        erpnext_ar_aging,
        erpnext_gross_profit,
        erpnext_profit_loss,
    )
