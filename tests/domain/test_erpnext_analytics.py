import pytest

from .test_erpnext_operations import call, create
from .test_erpnext_operations import env as erpnext_fixture

env = erpnext_fixture

KPIS = [
    "kpi_revenue",
    "kpi_outstanding",
    "kpi_orders",
    "kpi_gross_margin",
    "kpi_overdue",
]
CHARTS = [
    "stock_chart",
    "sales_chart",
    "revenue_trend",
    "order_breakdown",
    "revenue_vs_orders",
    "stock_treemap",
    "product_radar",
    "price_vs_qty",
    "sales_funnel",
    "ar_aging",
    "gross_profit",
    "profit_loss",
]


@pytest.mark.parametrize("tool", KPIS)
def test_total_kpis_empty_world_and_shared_terminal_gate(env, tool):
    value, error = call(env, tool)
    assert not error and value["value"] == 0
    assert env.episode is not None
    env.episode.finalize()
    value, error = call(env, tool)
    assert error and value["error"] == "Episode is terminal"


@pytest.mark.parametrize("tool", CHARTS)
def test_charts_empty_world_returns_source_envelope(env, tool):
    value, error = call(env, tool)
    assert not error and value["title"]
    assert "stages" in value if tool == "sales_funnel" else "datasets" in value


def order(env, customer, amount, day, status=0, kind="Sales Order", due=None):
    data = {
        "customer": customer,
        "items": [{"item_code": "WIDGET", "qty": 1, "rate": amount}],
        "transaction_date" if kind == "Sales Order" else "posting_date": day,
    }
    if due:
        data["due_date"] = due
    doc = create(env, kind, **data)
    if status:
        assert call(env, "doc_submit", doctype=kind, name=doc["name"])[1] is False
    if status == 2:
        assert call(env, "doc_cancel", doctype=kind, name=doc["name"])[1] is False
    return doc


def test_order_analytics_include_drafts_exclude_cancelled_and_compare_months(env):
    customer = create(env, "Customer", customer_name="Acme")["name"]
    call(env, "item_create", item_code="WIDGET", item_name="Widget")
    order(env, customer, 100, "2025-12-01")
    draft = order(env, customer, 200, "2026-01-01")
    order(env, customer, 300, "2026-01-01", 1)
    order(env, customer, 400, "2026-01-01", 2)
    revenue = call(env, "kpi_revenue")[0]
    assert (
        revenue["value"] == 500
        and revenue["delta"] == 400
        and revenue["sparkline"] == [0, 0, 0, 0, 100, 500]
    )
    assert call(env, "kpi_orders")[0]["value"] == 2
    assert call(env, "revenue_trend", months=2)[0]["datasets"][0]["values"] == [
        100,
        500,
    ]
    assert call(env, "order_breakdown", type="pie")[0]["datasets"][0]["values"] == [600]
    composed = call(env, "revenue_vs_orders")[0]
    assert composed["datasets"][0]["values"] == [600] and composed["datasets"][1][
        "values"
    ] == [3]
    assert call(env, "profit_loss", months=2)[0]["datasets"][0]["values"] == [0, 300]
    assert call(env, "kpi_gross_margin")[0]["value"] == 100
    assert call(env, "sales_funnel")[0]["stages"][3]["count"] == 3
    call(
        env,
        "doc_update",
        doctype="Sales Order",
        name=draft["name"],
        data={"items": [{"item_code": "WIDGET", "qty": 1, "rate": 250}]},
    )
    assert call(env, "kpi_revenue")[0]["value"] == 550


def test_invoice_predicates_and_overdue_boundary_and_aging(env):
    customer = create(env, "Customer", customer_name="Acme")["name"]
    call(env, "item_create", item_code="WIDGET", item_name="Widget")
    order(env, customer, 50, "2025-12-01", kind="Sales Invoice", due="2025-12-01")
    order(env, customer, 60, "2025-12-01", 1, "Sales Invoice", "2025-12-01")
    order(env, customer, 70, "2025-12-01", 2, "Sales Invoice", "2025-12-01")
    order(env, customer, 80, "2026-01-01", 1, "Sales Invoice", "2026-01-01")
    assert call(env, "sales_chart")[0]["datasets"][0]["values"] == [140]
    assert call(env, "sales_chart", include_drafts=True)[0]["datasets"][0][
        "values"
    ] == [260]
    assert (
        sum(call(env, "sales_chart", group_by="status")[0]["datasets"][0]["values"])
        == 190
    )
    assert call(env, "sales_chart", group_by="item", include_drafts=True)[0][
        "datasets"
    ][0]["values"] == [140]
    assert call(env, "kpi_outstanding")[0]["value"] == 140
    assert call(env, "kpi_overdue")[0]["value"] == 1
    aging = call(env, "ar_aging")[0]
    assert [dataset["values"] for dataset in aging["datasets"]] == [
        [80],
        [60],
        [0],
        [0],
    ]
    assert call(env, "gross_profit")[0]["datasets"][0]["values"] == [140]


def test_stock_and_product_analytics_recompute_from_mutable_rows(env):
    customer = create(env, "Customer", customer_name="Acme")["name"]
    call(env, "item_create", item_code="WIDGET", item_name="Widget")
    call(env, "item_create", item_code="OTHER", item_name="Other")
    warehouse = create(env, "Warehouse", warehouse_name="Stores")["name"]
    create(
        env,
        "Bin",
        item_code="WIDGET",
        warehouse=warehouse,
        actual_qty=10,
        reserved_qty=0,
        valuation_rate=2,
        stock_value=20,
    )
    create(
        env,
        "Bin",
        item_code="OTHER",
        warehouse=warehouse,
        actual_qty=5,
        reserved_qty=0,
        valuation_rate=1,
        stock_value=5,
    )
    order(env, customer, 10, "2026-01-01")
    assert call(env, "stock_chart")[0]["datasets"][0]["values"] == [10, 5]
    assert call(env, "stock_chart", min_qty=5)[0]["labels"] == ["WIDGET"]
    assert call(env, "stock_treemap")[0]["treeData"][0]["value"] == 20
    assert call(env, "product_radar", items=["WIDGET", "OTHER"])[0]["datasets"][0][
        "values"
    ] == [100, 100, 100, 100]
    assert call(env, "price_vs_qty")[0]["scatterData"][0]["points"][0]["x"] == 2
    create(env, "Item Price", item_code="WIDGET", selling=1, price_list_rate=9)
    assert call(env, "price_vs_qty")[0]["scatterData"][0]["points"] == [
        {"x": 9, "y": 1, "label": "WIDGET"}
    ]
    assert call(env, "kpi_gross_margin")[0]["value"] == 80


@pytest.mark.parametrize(
    "tool,args",
    [
        (name, {"limit": -1})
        for name in [
            "stock_chart",
            "sales_chart",
            "order_breakdown",
            "revenue_vs_orders",
            "stock_treemap",
            "price_vs_qty",
            "ar_aging",
            "gross_profit",
        ]
    ]
    + [
        ("revenue_trend", {"months": 0}),
        ("profit_loss", {"months": 0}),
        ("product_radar", {"items": ["a"] * 9}),
        ("sales_funnel", {"period": "bad"}),
    ],
)
def test_analytics_deliberate_invalid_inputs(env, tool, args):
    value, error = call(env, tool, **args)
    assert error and value["error"] != "Unknown provider or tool"
