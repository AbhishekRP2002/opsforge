"""Source-shaped analytics recomputed from episode documents and simulated UTC."""

import math
from datetime import date

from . import erpnext_store as store

COLORS = [
    "#60a5fa",
    "#4ade80",
    "#fbbf24",
    "#818cf8",
    "#c084fc",
    "#fb923c",
    "#34d399",
    "#f472b6",
    "#a78bfa",
    "#f97316",
    "#22d3ee",
    "#e879f9",
]


def rounded(value, digits=0):
    scaled = value * 10**digits + 0.5
    store.validate_finite_numbers(scaled, "rounded aggregate")
    return math.floor(scaled) / 10**digits


def amount(row, field):
    return store.number(row.get(field, 0), field)


def rows(db, kind, state=None):
    docs = store.all_docs(db, kind)
    if state == "submitted":
        docs = [doc for doc in docs if doc["docstatus"] == 1]
    elif state == "active":
        docs = [doc for doc in docs if doc["docstatus"] != 2]
    return docs


def children(db, kind, state):
    return [
        dict(
            item, parent=doc["name"], customer_name=doc.get("customer_name", "Unknown")
        )
        for doc in rows(db, kind, state)
        for item in doc["items"]
    ]


def grouped(docs, field, value):
    totals = {}
    for doc in docs:
        key = doc.get(field, "Unknown")
        if not isinstance(key, str):
            raise store.BusinessError(f"{field} must be a string for analytics")
        totals[key] = totals.get(key, 0) + amount(doc, value)
    return totals


def top(totals, limit):
    return sorted(totals, key=lambda key: totals[key], reverse=True)[:limit]


def chart(title, kind, labels, datasets, **extras):
    return {
        "title": title,
        "type": kind,
        "labels": labels,
        "datasets": datasets,
        **extras,
    }


def dataset(label, values, **extras):
    return {"label": label, "values": values, **extras}


def months(db, clock, count):
    count = store.limited(count, 6, maximum=120)
    today = date.fromisoformat(store.now(db, clock)[:10])
    current = today.year * 12 + today.month - 1
    dates = [
        date(index // 12, index % 12 + 1, 1)
        for index in range(current - count + 1, current + 1)
    ]
    return dates, [day.strftime("%b %y") for day in dates]


def buckets(docs, dates):
    result = [0] * len(dates)
    start = dates[0].year * 12 + dates[0].month
    for doc in docs:
        value = doc.get("transaction_date")
        if value is None:
            continue
        if not isinstance(value, str):
            raise store.BusinessError("transaction_date must be a date string")
        try:
            day = date.fromisoformat(value)
        except ValueError as error:
            raise store.BusinessError(
                "Invalid transaction_date in analytics"
            ) from error
        index = day.year * 12 + day.month - start
        if 0 <= index < len(result):
            result[index] += amount(doc, "grand_total")
    return result


def cost_map(db, highest=False):
    result = {}
    for row in rows(db, "Bin"):
        value = amount(row, "valuation_rate")
        if value > 0:
            if highest:
                result[row["item_code"]] = max(result.get(row["item_code"], 0), value)
            else:
                result.setdefault(row["item_code"], value)
    return result


@store.handler
def stock_chart(db, args, step, clock):
    limit = store.limited(args.get("limit"))
    minimum = store.number(args.get("min_qty", 0), "min_qty", minimum=-1e300)
    bins = [
        row
        for row in rows(db, "Bin")
        if amount(row, "actual_qty") > minimum
        and (not args.get("warehouse") or row["warehouse"] == args["warehouse"])
    ]
    bins.sort(key=lambda row: amount(row, "actual_qty"), reverse=True)
    if args.get("item_group"):
        allowed = {
            row["name"]
            for row in rows(db, "Item")
            if row.get("item_group") == args["item_group"]
        }
        bins = [row for row in bins[:1000] if row["item_code"] in allowed]
    else:
        bins = bins[:limit]
    totals = grouped(bins, "item_code", "actual_qty")
    labels = top(totals, limit)
    return chart(
        "Stock Levels",
        args.get("type", "horizontal-bar" if len(labels) > 6 else "bar"),
        labels,
        [dataset("Qty on Hand", [totals[key] for key in labels], color="#60a5fa")],
        subtitle=args.get("warehouse", "All Warehouses"),
        unit="units",
        generatedAt=store.now(db, clock),
    )


@store.handler
def sales_chart(db, args, step, clock):
    limit = store.limited(args.get("limit"), 10)
    group = args.get("group_by", "customer")
    if group == "status":
        totals = grouped(
            rows(db, "Sales Invoice", "active")[:500], "status", "grand_total"
        )
        labels = top(totals, len(totals))
        return chart(
            "Invoice Revenue by Status",
            "donut",
            labels,
            [dataset("Revenue", [totals[key] for key in labels])],
            currency="EUR",
            generatedAt=store.now(db, clock),
        )
    if group == "item":
        source = children(db, "Sales Invoice", "submitted")[:500]
        dimension, value, title, color = "item_code", "amount", "Items", "#c084fc"
    else:
        source = rows(
            db, "Sales Invoice", None if args.get("include_drafts") else "submitted"
        )[:500]
        dimension, value, title, color = (
            "customer",
            "grand_total",
            "Customers",
            "#4ade80",
        )
    totals = grouped(source, dimension, value)
    keys = top(totals, limit)
    label_field = "item_name" if group == "item" else "customer_name"
    labels = [
        next(
            (row.get(label_field, key) for row in source if row[dimension] == key), key
        )
        for key in keys
    ]
    return chart(
        f"Top {title} by Revenue",
        "horizontal-bar",
        labels,
        [dataset("Revenue", [totals[key] for key in keys], color=color)],
        subtitle=f"Top {len(labels)} {title.lower()}",
        currency="EUR",
        generatedAt=store.now(db, clock),
    )


@store.handler
def revenue_trend(db, args, step, clock):
    dates, labels = months(db, clock, args.get("months", 6))
    kind = args.get("type", "line")
    source = rows(db, "Sales Order", "active")
    if args.get("group_by", "total") == "customer":
        groups = {row.get("customer_name", "Unknown") for row in source}
        totals = {
            name: buckets(
                [row for row in source if row.get("customer_name", "Unknown") == name],
                dates,
            )
            for name in groups
        }
        keys = sorted(totals, key=lambda key: (-sum(totals[key]), key))[:5]
        colors = ["#60a5fa", "#4ade80", "#fbbf24", "#c084fc", "#f472b6"]
        data = [
            dataset(
                key,
                totals[key],
                color=colors[index],
                showDots=kind == "line",
                **({"stack": "revenue"} if kind == "stacked-area" else {}),
            )
            for index, key in enumerate(keys)
        ]
        title = "Revenue by Customer"
    else:
        data = [
            dataset("Revenue", buckets(source, dates), color="#60a5fa", showDots=True)
        ]
        title = "Revenue Trend"
    return chart(
        title,
        kind,
        labels,
        data,
        subtitle=f"Last {len(dates)} months",
        currency="EUR",
        yAxisLabel="Revenue",
    )


@store.handler
def order_breakdown(db, args, step, clock):
    limit = store.limited(args.get("limit"), 8)
    kind = args.get("type", "stacked-bar")
    source = rows(db, "Sales Order", "active")[:500]
    totals = grouped(source, "customer_name", "grand_total")
    labels = top(totals, limit)
    if kind in {"pie", "donut"}:
        return chart(
            "Orders by Customer",
            kind,
            labels,
            [dataset("Total", [totals[key] for key in labels])],
            currency="EUR",
        )
    statuses = {
        "Draft": "#78716c",
        "To Deliver and Bill": "#60a5fa",
        "To Bill": "#c084fc",
        "Completed": "#4ade80",
        "Cancelled": "#f87171",
    }
    data = []
    for status, color in statuses.items():
        values = [
            sum(
                amount(row, "grand_total")
                for row in source
                if row.get("customer_name", "Unknown") == label
                and row.get("status", "Draft") == status
            )
            for label in labels
        ]
        if any(value > 0 for value in values):
            data.append(
                dataset(
                    "To Deliver" if status == "To Deliver and Bill" else status,
                    values,
                    color=color,
                    stack="status",
                )
            )
    return chart(
        "Order Value by Customer & Status",
        kind,
        labels,
        data,
        currency="EUR",
        xAxisLabel="Customer",
        yAxisLabel="Order Value",
    )


@store.handler
def revenue_vs_orders(db, args, step, clock):
    source = rows(db, "Sales Order", "active")[:500]
    totals = grouped(source, "customer_name", "grand_total")
    labels = top(totals, store.limited(args.get("limit"), 8))
    counts = [
        sum(row.get("customer_name", "Unknown") == label for row in source)
        for label in labels
    ]
    return chart(
        "Revenue vs Order Count",
        "composed",
        labels,
        [
            dataset(
                "Revenue", [totals[key] for key in labels], color="#60a5fa", type="bar"
            ),
            dataset(
                "Orders",
                counts,
                color="#fbbf24",
                type="line",
                yAxisId="right",
                unit="orders",
                showDots=True,
            ),
        ],
        subtitle=f"Top {len(labels)} customers",
        showRightAxis=True,
        yAxisLabel="Revenue (€)",
        rightAxisLabel="# Orders",
        currency="EUR",
    )


@store.handler
def stock_treemap(db, args, step, clock):
    field = "warehouse" if args.get("group_by") == "warehouse" else "item_code"
    source = [row for row in rows(db, "Bin") if amount(row, "stock_value") > 0]
    totals = grouped(source, field, "stock_value")
    labels = top(totals, store.limited(args.get("limit"), 15))
    tree = [
        {
            "name": name[:18] + "…" if len(name) > 20 else name,
            "value": rounded(totals[name]),
            "color": COLORS[index % len(COLORS)],
        }
        for index, name in enumerate(labels)
    ]
    return chart(
        "Stock Value by " + ("Warehouse" if field == "warehouse" else "Item"),
        "treemap",
        [],
        [],
        treeData=tree,
        currency="EUR",
    )


@store.handler
def product_radar(db, args, step, clock):
    codes = (
        args.get("items")
        or [
            row["item_code"]
            for row in sorted(
                rows(db, "Bin"),
                key=lambda row: amount(row, "stock_value"),
                reverse=True,
            )
            if amount(row, "actual_qty") > 0
        ][:4]
    )
    if len(codes) > 8:
        raise store.BusinessError("product_radar accepts at most 8 item codes")
    if len(codes) < 2:
        return chart("Product Comparison", "radar", [], [])
    source = children(db, "Sales Order", "active")[:500]
    raw = {}
    for code in codes:
        bins = [row for row in rows(db, "Bin") if row["item_code"] == code][:100]
        ordered = [row for row in source if row["item_code"] == code]
        raw[code] = [
            sum(amount(row, "actual_qty") for row in bins),
            sum(amount(row, "stock_value") for row in bins),
            len(ordered),
            sum(amount(row, "amount") for row in ordered),
        ]
    maximum = [max(1, *(raw[code][index] for code in codes)) for index in range(4)]
    colors = ["#60a5fa", "#f472b6", "#4ade80", "#fbbf24"]
    return chart(
        "Product Comparison",
        "radar",
        ["Stock Qty", "Stock Value", "Order Lines", "Revenue"],
        [
            dataset(
                code,
                [
                    rounded(raw[code][index] / maximum[index] * 100)
                    for index in range(4)
                ],
                color=colors[number % 4],
            )
            for number, code in enumerate(codes)
        ],
        subtitle=" vs ".join(codes),
    )


@store.handler
def price_vs_qty(db, args, step, clock):
    limit = store.limited(args.get("limit"), 30)
    prices = {}
    for row in rows(db, "Item Price"):
        if row.get("selling") == 1:
            prices.setdefault(row["item_code"], amount(row, "price_list_rate"))
    qty = grouped(children(db, "Sales Order", "active"), "item_code", "qty")
    codes = [code for code in prices if code in qty][:limit]
    if codes:
        title, x_axis, y_axis = (
            "Price vs Quantity Ordered",
            "Selling Price (€)",
            "Total Qty Ordered",
        )
        points = [
            {"x": rounded(prices[code]), "y": rounded(qty[code]), "label": code}
            for code in codes
        ]
    else:
        title, x_axis, y_axis = (
            "Valuation Rate vs Stock Qty",
            "Valuation Rate (€/unit)",
            "Stock Qty",
        )
        bins = sorted(
            [
                row
                for row in rows(db, "Bin")
                if amount(row, "actual_qty") > 0 and amount(row, "valuation_rate") > 0
            ],
            key=lambda row: amount(row, "stock_value"),
            reverse=True,
        )[:limit]
        points = [
            {
                "x": rounded(amount(row, "valuation_rate")),
                "y": rounded(amount(row, "actual_qty")),
                "label": row["item_code"],
            }
            for row in bins
        ]
    return chart(
        title,
        "scatter",
        [],
        [],
        scatterData=[{"label": "Items", "color": "#818cf8", "points": points}],
        xAxisLabel=x_axis,
        yAxisLabel=y_axis,
    )


def change(current, previous):
    delta = (current - previous) / previous * 100 if previous > 0 else 0
    return {
        "delta": rounded(delta, 1),
        "deltaLabel": "vs last month",
        "trend": "up" if delta > 0 else "down" if delta < 0 else "flat",
    }


@store.handler
def kpi_revenue(db, args, step, clock):
    dates, _ = months(db, clock, 6)
    values = buckets(rows(db, "Sales Order", "active"), dates)
    return {
        "label": "Revenue MTD",
        "value": values[5],
        "currency": "EUR",
        **change(values[5], values[4]),
        "trendIsGood": True,
        "sparkline": values,
        "color": "#60a5fa",
    }


@store.handler
def kpi_orders(db, args, step, clock):
    dates, _ = months(db, clock, 2)
    source = rows(db, "Sales Order", "active")
    current = sum(row.get("transaction_date", "") >= str(dates[1]) for row in source)
    previous = sum(
        str(dates[0]) <= row.get("transaction_date", "") < str(dates[1])
        for row in source
    )
    return {
        "label": "Orders This Month",
        "value": current,
        "formattedValue": f"{current} orders",
        "unit": "orders",
        **change(current, previous),
        "trendIsGood": True,
        "color": "#4ade80",
    }


def unpaid(db):
    return [
        row
        for row in rows(db, "Sales Invoice", "submitted")
        if amount(row, "outstanding_amount") > 0
    ]


@store.handler
def kpi_outstanding(db, args, step, clock):
    source = unpaid(db)
    total = sum(amount(row, "outstanding_amount") for row in source)
    return {
        "label": "Outstanding Receivables",
        "value": total,
        "formattedValue": f"{len(source)} inv. / €{total:,.2f}",
        "currency": "EUR",
        "trend": "up" if total > 0 else "flat",
        "trendIsGood": False,
        "color": "#fbbf24",
    }


@store.handler
def kpi_overdue(db, args, step, clock):
    today = store.now(db, clock)[:10]
    source = [
        row for row in unpaid(db) if row.get("due_date") and row["due_date"] < today
    ]
    total = sum(amount(row, "outstanding_amount") for row in source)
    return {
        "label": "Overdue Invoices",
        "value": len(source),
        "formattedValue": f"{len(source)} inv. / €{total:,.2f}",
        "trend": "up" if source else "flat",
        "trendIsGood": False,
        "color": "#f87171",
    }


@store.handler
def kpi_gross_margin(db, args, step, clock):
    source = children(db, "Sales Order", "active")
    revenue = sum(amount(row, "amount") for row in source)
    costs = cost_map(db)
    cost = sum(amount(row, "qty") * costs.get(row["item_code"], 0) for row in source)
    margin = (revenue - cost) / revenue * 100 if revenue > 0 else 0
    return {
        "label": "Gross Margin",
        "value": rounded(margin, 1),
        "unit": "%",
        "trend": "up" if margin >= 30 else "flat" if margin >= 15 else "down",
        "trendIsGood": True,
        "color": "#c084fc",
    }


@store.handler
def sales_funnel(db, args, step, clock):
    period = args.get("period", "all")
    today = date.fromisoformat(store.now(db, clock)[:10])
    since = {
        "all": "",
        "this_month": f"{today:%Y-%m}-01",
        "this_quarter": f"{today.year}-{((today.month - 1) // 3) * 3 + 1:02d}-01",
        "this_year": f"{today.year}-01-01",
    }[period]
    stages = []
    previous = 0
    for kind, label, value, color in [
        ("Lead", "Leads", None, "#818cf8"),
        ("Opportunity", "Opportunities", "opportunity_amount", "#60a5fa"),
        ("Quotation", "Quotations", "grand_total", "#4ade80"),
        ("Sales Order", "Orders", "grand_total", "#fbbf24"),
    ]:
        source = rows(
            db, kind, "active" if kind in {"Quotation", "Sales Order"} else None
        )
        field = "creation" if kind == "Lead" else "transaction_date"
        source = [row for row in source if not since or row.get(field, "") >= since][
            :500
        ]
        stage = {"label": label, "count": len(source), "color": color}
        if value:
            stage.update(
                value=sum(amount(row, value) for row in source),
                conversionRate=rounded(len(source) / previous * 100) if previous else 0,
            )
        stages.append(stage)
        previous = len(source)
    return {
        "title": "Sales Funnel",
        "subtitle": {
            "all": "All Time",
            "this_month": "This Month",
            "this_quarter": "This Quarter",
            "this_year": "This Year",
        }[period],
        "stages": stages,
        "currency": "EUR",
    }


@store.handler
def ar_aging(db, args, step, clock):
    today = date.fromisoformat(store.now(db, clock)[:10])
    totals = {}
    for row in unpaid(db):
        name = row.get("customer_name", "Unknown")
        day = date.fromisoformat(
            row.get("due_date") or row.get("posting_date") or str(today)
        )
        age = max(0, (today - day).days)
        index = 0 if age <= 30 else 1 if age <= 60 else 2 if age <= 90 else 3
        totals.setdefault(name, [0, 0, 0, 0])[index] += amount(
            row, "outstanding_amount"
        )
    labels = sorted(totals, key=lambda key: sum(totals[key]), reverse=True)[
        : store.limited(args.get("limit"), 10)
    ]
    kind = args.get("type", "stacked-bar")
    if kind == "treemap":
        return chart(
            "Accounts Receivable by Customer",
            kind,
            [],
            [],
            treeData=[
                {
                    "name": name[:18] + "..." if len(name) > 20 else name,
                    "value": rounded(sum(totals[name])),
                    "color": COLORS[index % 10],
                }
                for index, name in enumerate(labels)
            ],
            currency="EUR",
        )
    descriptors = [
        ("0-30 days", "#4ade80"),
        ("31-60 days", "#fbbf24"),
        ("61-90 days", "#fb923c"),
        ("90+ days", "#f87171"),
    ]
    return chart(
        "Accounts Receivable Aging",
        kind,
        labels,
        [
            dataset(
                label,
                [totals[name][index] for name in labels],
                color=color,
                stack="aging",
            )
            for index, (label, color) in enumerate(descriptors)
        ],
        subtitle=f"Top {len(labels)} customers",
        currency="EUR",
        xAxisLabel="Customer",
        yAxisLabel="Outstanding Amount",
    )


@store.handler
def gross_profit(db, args, step, clock):
    by_customer = args.get("group_by") == "customer"
    source = children(db, "Sales Invoice", "submitted")
    costs = cost_map(db, highest=True)
    grouped_values = {}
    for row in source:
        key = (
            row["customer_name"]
            if by_customer
            else row.get("item_name", row["item_code"])
        )
        values = grouped_values.setdefault(key, [0, 0])
        values[0] += amount(row, "amount")
        values[1] += amount(row, "qty") * costs.get(row["item_code"], 0)
    labels = sorted(
        grouped_values, key=lambda key: grouped_values[key][0], reverse=True
    )[: store.limited(args.get("limit"), 10)]
    revenues = [rounded(grouped_values[name][0]) for name in labels]
    margins = [
        rounded(
            (grouped_values[name][0] - grouped_values[name][1])
            / grouped_values[name][0]
            * 100,
            2,
        )
        if grouped_values[name][0]
        else 0
        for name in labels
    ]
    return chart(
        "Gross Profit by " + ("Customer" if by_customer else "Item"),
        "composed",
        labels,
        [
            dataset("Revenue", revenues, color="#60a5fa", type="bar"),
            dataset(
                "Margin %",
                margins,
                color="#4ade80",
                type="line",
                yAxisId="right",
                showDots=True,
            ),
        ],
        subtitle=f"Top {len(labels)} {'customers' if by_customer else 'items'}",
        showRightAxis=True,
        currency="EUR",
        yAxisLabel="Revenue",
        rightAxisLabel="Margin %",
    )


@store.handler
def profit_loss(db, args, step, clock):
    dates, labels = months(db, clock, args.get("months", 6))
    kind = args.get("type", "composed")
    income = buckets(rows(db, "Sales Order", "submitted"), dates)
    expenses = buckets(rows(db, "Purchase Order", "submitted"), dates)
    data = [
        dataset(
            "Income", [rounded(value) for value in income], color="#4ade80", type="bar"
        ),
        dataset(
            "Expenses",
            [rounded(value) for value in expenses],
            color="#f87171",
            type="bar",
        ),
    ]
    extras = {}
    if kind == "composed":
        data.append(
            dataset(
                "Net Profit",
                [
                    rounded(value - expenses[index])
                    for index, value in enumerate(income)
                ],
                color="#60a5fa",
                type="line",
                yAxisId="right",
                showDots=True,
            )
        )
        extras = {"showRightAxis": True, "rightAxisLabel": "Net Profit"}
    return chart(
        "Profit & Loss",
        kind,
        labels,
        data,
        subtitle=f"Last {len(dates)} months",
        currency="EUR",
        yAxisLabel="Amount",
        **extras,
    )


HANDLERS = {
    "erpnext_stock_chart": stock_chart,
    "erpnext_sales_chart": sales_chart,
    "erpnext_revenue_trend": revenue_trend,
    "erpnext_order_breakdown": order_breakdown,
    "erpnext_revenue_vs_orders": revenue_vs_orders,
    "erpnext_stock_treemap": stock_treemap,
    "erpnext_product_radar": product_radar,
    "erpnext_price_vs_qty": price_vs_qty,
    "erpnext_kpi_revenue": kpi_revenue,
    "erpnext_kpi_orders": kpi_orders,
    "erpnext_kpi_outstanding": kpi_outstanding,
    "erpnext_kpi_overdue": kpi_overdue,
    "erpnext_kpi_gross_margin": kpi_gross_margin,
    "erpnext_sales_funnel": sales_funnel,
    "erpnext_ar_aging": ar_aging,
    "erpnext_gross_profit": gross_profit,
    "erpnext_profit_loss": profit_loss,
}
