"""Regressions for the six independently reproduced Task4 review findings."""

import json
import os
import subprocess
import sys

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment

from .test_erpnext_operations import call, create
from .test_erpnext_operations import env as erpnext_fixture

env = erpnext_fixture


@pytest.mark.parametrize("mode", ["create", "update", "fixture"])
@pytest.mark.parametrize(
    "field,value",
    [
        ("resolution_by", {"bad": "type"}),
        ("resolution_by", ["2026-01-01"]),
        ("resolution_by", "2026-02-30T12:00:00"),
        ("resolution_by", "2026-01-01garbage"),
        ("raised_by", {}),
        ("title", []),
        ("source", {}),
        ("is_milestone", []),
        ("opening_date", {}),
        ("resolution_date", []),
    ],
)
def test_kanban_interpreted_fields_rejected_before_persistence(env, mode, field, value):
    data = {"subject": "SLA issue", field: value}
    if mode == "fixture":
        config = load_scenario().model_dump()
        config["erpnext_records"] = [
            {"doctype": "Issue", "name": "ISSUE-1", "data": data}
        ]
        with pytest.raises(ValueError, match=field):
            Scenario.model_validate(config)
    elif mode == "create":
        result, error = call(env, "doc_create", doctype="Issue", data=data)
        assert error and field in result["error"]
        assert call(env, "doc_list", doctype="Issue")[0]["count"] == 0
    else:
        issue = create(env, "Issue", subject="SLA issue")
        result, error = call(
            env, "doc_update", doctype="Issue", name=issue["name"], data={field: value}
        )
        assert error and field in result["error"]
        assert (
            call(env, "doc_get", doctype="Issue", name=issue["name"])[0]["data"]
            == issue
        )


def test_issue_sla_timestamps_remain_readable_from_generic_and_fixture_records(env):
    issue = create(
        env,
        "Issue",
        subject="SLA",
        resolution_by="2025-12-31T10:00:00+00:00",
        resolution_date="2026-01-01 09:30:00",
        opening_date="2025-12-30",
        raised_by="alice@example.test",
    )
    board, error = call(env, "kanban_get_board", doctype="Issue")
    assert not error and board["cards"][0]["id"] == issue["name"]
    assert {"label": "SLA breach", "tone": "error"} in board["cards"][0]["badges"]
    assert {"label": "Resolved", "value": "Jan 1"} in board["cards"][0]["metrics"]
    config = load_scenario().model_dump()
    config["erpnext_records"] = [
        {
            "doctype": "Issue",
            "name": "ISSUE-1",
            "data": {"subject": "Fixture", "resolution_by": "2025-12-31 10:00:00"},
        }
    ]
    world = ItopsEnvironment(scenario=Scenario.model_validate(config))
    world.reset()
    try:
        assert (
            call(world, "kanban_get_board", doctype="Issue")[0]["cards"][0]["dueDate"]
            == "2025-12-31 10:00:00"
        )
    finally:
        world.close()


@pytest.mark.parametrize("mode", ["generic", "fixture"])
def test_minimal_bins_support_receipt_and_reversal_with_numeric_defaults(env, mode):
    world = env
    if mode == "fixture":
        config = load_scenario().model_dump()
        config["erpnext_records"] = [
            {
                "doctype": "Item",
                "name": "WIDGET",
                "data": {"item_code": "WIDGET", "item_name": "Widget"},
            },
            {
                "doctype": "Warehouse",
                "name": "STORES",
                "data": {"warehouse_name": "Stores"},
            },
            {
                "doctype": "Bin",
                "name": "BIN-1",
                "data": {"item_code": "WIDGET", "warehouse": "STORES"},
            },
        ]
        world = ItopsEnvironment(scenario=Scenario.model_validate(config))
        world.reset()
        warehouse, name = "STORES", "BIN-1"
    else:
        create(world, "Item", item_code="WIDGET", item_name="Widget")
        warehouse = create(world, "Warehouse", warehouse_name="Stores")["name"]
        name = create(world, "Bin", item_code="WIDGET", warehouse=warehouse)["name"]
    try:
        before = call(world, "doc_get", doctype="Bin", name=name)[0]["data"]
        assert {
            field: before[field]
            for field in (
                "actual_qty",
                "reserved_qty",
                "projected_qty",
                "valuation_rate",
                "stock_value",
            )
        } == {
            "actual_qty": 0,
            "reserved_qty": 0,
            "projected_qty": 0,
            "valuation_rate": 0,
            "stock_value": 0,
        }
        receipt = create(
            world,
            "Stock Entry",
            stock_entry_type="Material Receipt",
            to_warehouse=warehouse,
            items=[{"item_code": "WIDGET", "qty": 2, "basic_rate": 3}],
        )
        assert not call(
            world, "doc_submit", doctype="Stock Entry", name=receipt["name"]
        )[1]
        after = call(world, "doc_get", doctype="Bin", name=name)[0]["data"]
        assert (
            after["actual_qty"] == 2
            and after["reserved_qty"] == 0
            and after["projected_qty"] == 2
            and after["stock_value"] == 6
        )
        assert not call(
            world, "doc_cancel", doctype="Stock Entry", name=receipt["name"]
        )[1]
        assert (
            call(world, "doc_get", doctype="Bin", name=name)[0]["data"]["actual_qty"]
            == 0
        )
    finally:
        if world is not env:
            world.close()


@pytest.mark.parametrize("mode", ["create", "update", "fixture"])
def test_bin_projected_quantity_must_be_numeric(env, mode):
    item = {
        "doctype": "Item",
        "name": "WIDGET",
        "data": {"item_code": "WIDGET", "item_name": "Widget"},
    }
    warehouse = {
        "doctype": "Warehouse",
        "name": "STORES",
        "data": {"warehouse_name": "Stores"},
    }
    if mode == "fixture":
        config = load_scenario().model_dump()
        config["erpnext_records"] = [
            item,
            warehouse,
            {
                "doctype": "Bin",
                "name": "BIN-1",
                "data": {
                    "item_code": "WIDGET",
                    "warehouse": "STORES",
                    "projected_qty": {},
                },
            },
        ]
        with pytest.raises(ValueError, match="projected_qty"):
            Scenario.model_validate(config)
    else:
        create(env, "Item", **item["data"])
        store = create(env, "Warehouse", warehouse_name="Stores")["name"]
        if mode == "create":
            result, error = call(
                env,
                "doc_create",
                doctype="Bin",
                data={"item_code": "WIDGET", "warehouse": store, "projected_qty": {}},
            )
        else:
            row = create(env, "Bin", item_code="WIDGET", warehouse=store)
            result, error = call(
                env,
                "doc_update",
                doctype="Bin",
                name=row["name"],
                data={"projected_qty": {}},
            )
        assert error and "projected_qty" in result["error"]


def invoice(env, **extra):
    customer = create(env, "Customer", customer_name="Acme")
    create(env, "Item", item_code="WIDGET", item_name="Widget")
    return create(
        env,
        "Sales Invoice",
        customer=customer["name"],
        items=[{"item_code": "WIDGET", "qty": 1, "rate": 10}],
        posting_date="2025-12-01",
        due_date="2025-12-01",
        **extra,
    )


def test_invoice_line_update_recomputes_receivable_before_submit(env):
    doc = invoice(env)
    value, error = call(
        env,
        "doc_update",
        doctype="Sales Invoice",
        name=doc["name"],
        data={"items": [{"item_code": "WIDGET", "qty": 1, "rate": 20}]},
    )
    assert (
        not error
        and value["data"]["grand_total"] == 20
        and value["data"]["outstanding_amount"] == 20
    )
    assert not call(env, "doc_submit", doctype="Sales Invoice", name=doc["name"])[1]
    assert call(env, "kpi_outstanding")[0]["value"] == 20
    assert call(env, "kpi_overdue")[0]["formattedValue"] == "1 inv. / €20.00"


def test_invoice_payment_adjustment_survives_total_changes(env):
    doc = invoice(env, paid_amount=3)
    assert doc["outstanding_amount"] == 7
    value, error = call(
        env,
        "doc_update",
        doctype="Sales Invoice",
        name=doc["name"],
        data={"items": [{"item_code": "WIDGET", "qty": 1, "rate": 20}]},
    )
    assert not error and value["data"]["outstanding_amount"] == 17
    value, error = call(
        env,
        "doc_update",
        doctype="Sales Invoice",
        name=doc["name"],
        data={"outstanding_amount": 12},
    )
    assert not error and value["data"]["paid_amount"] == 8
    value, error = call(
        env,
        "doc_update",
        doctype="Sales Invoice",
        name=doc["name"],
        data={"items": [{"item_code": "WIDGET", "qty": 1, "rate": 30}]},
    )
    assert not error and value["data"]["outstanding_amount"] == 22
    before = value["data"]
    value, error = call(
        env,
        "doc_update",
        doctype="Sales Invoice",
        name=doc["name"],
        data={"paid_amount": 4, "outstanding_amount": 5},
    )
    assert error and "balance" in value["error"]
    assert (
        call(env, "doc_get", doctype="Sales Invoice", name=doc["name"])[0]["data"]
        == before
    )
    assert not call(env, "doc_submit", doctype="Sales Invoice", name=doc["name"])[1]
    assert call(env, "kpi_outstanding")[0]["value"] == 22


@pytest.mark.parametrize(
    "adjustment,paid,outstanding",
    [({}, 0, 10), ({"paid_amount": 3}, 3, 7), ({"outstanding_amount": 6}, 4, 6)],
)
def test_invoice_fixture_balance_is_derived(adjustment, paid, outstanding):
    config = load_scenario().model_dump()
    config["erpnext_records"] = [
        {"doctype": "Customer", "name": "CUST", "data": {"customer_name": "Acme"}},
        {
            "doctype": "Item",
            "name": "WIDGET",
            "data": {"item_code": "WIDGET", "item_name": "Widget"},
        },
        {
            "doctype": "Sales Invoice",
            "name": "INV",
            "docstatus": 1,
            "data": {
                "customer": "CUST",
                "items": [{"item_code": "WIDGET", "qty": 1, "rate": 10}],
                **adjustment,
            },
        },
    ]
    world = ItopsEnvironment(scenario=Scenario.model_validate(config))
    world.reset()
    try:
        doc = call(world, "doc_get", doctype="Sales Invoice", name="INV")[0]["data"]
        assert doc["paid_amount"] == paid and doc["outstanding_amount"] == outstanding
        assert call(world, "kpi_outstanding")[0]["value"] == outstanding
    finally:
        world.close()
    config["erpnext_records"][2]["data"].update(paid_amount=11, outstanding_amount=0)
    with pytest.raises(ValueError, match="paid_amount|balance"):
        Scenario.model_validate(config)


@pytest.mark.parametrize("mode", ["create", "update", "fixture"])
@pytest.mark.parametrize(
    "changes",
    [
        {"owner": "missing@example.test"},
        {"reference_name": "missing"},
        {"reference_type": "Unknown"},
        {"owner": "disabled@example.test"},
    ],
)
def test_todo_generic_and_fixture_references_cannot_dangle(env, mode, changes):
    data = {
        "owner": "alice@example.test",
        "reference_type": "Task",
        "reference_name": "TASK",
        "status": "Open",
    }
    if mode == "fixture":
        config = load_scenario().model_dump()
        config["erpnext_records"] = [
            {
                "doctype": "User",
                "name": "alice@example.test",
                "data": {
                    "full_name": "Alice",
                    "user_type": "System User",
                    "enabled": 1,
                },
            },
            {
                "doctype": "User",
                "name": "disabled@example.test",
                "data": {
                    "full_name": "Disabled",
                    "user_type": "System User",
                    "enabled": 0,
                },
            },
            {
                "doctype": "Project",
                "name": "PROJECT",
                "data": {"project_name": "Launch"},
            },
            {
                "doctype": "Task",
                "name": "TASK",
                "data": {"project": "PROJECT", "subject": "Work"},
            },
            {"doctype": "ToDo", "name": "TODO", "data": data | changes},
        ]
        with pytest.raises(ValueError, match="exist|DocType|disabled"):
            Scenario.model_validate(config)
    else:
        create(
            env,
            "User",
            name="alice@example.test",
            full_name="Alice",
            user_type="System User",
            enabled=1,
        )
        create(
            env,
            "User",
            name="disabled@example.test",
            full_name="Disabled",
            user_type="System User",
            enabled=0,
        )
        project = create(env, "Project", project_name="Launch")
        task = create(env, "Task", project=project["name"], subject="Work")
        data["reference_name"] = task["name"]
        if mode == "create":
            result, error = call(env, "doc_create", doctype="ToDo", data=data | changes)
            assert error and result["error"]
            assert call(env, "doc_list", doctype="ToDo")[0]["count"] == 0
        else:
            todo = create(env, "ToDo", **data)
            result, error = call(
                env, "doc_update", doctype="ToDo", name=todo["name"], data=changes
            )
            assert error and result["error"]
            assert (
                call(env, "doc_get", doctype="ToDo", name=todo["name"])[0]["data"]
                == todo
            )


def test_valid_generic_todo_protects_its_user_and_dynamic_parent(env):
    create(
        env,
        "User",
        name="alice@example.test",
        full_name="Alice",
        user_type="System User",
        enabled=1,
    )
    issue = create(env, "Issue", subject="Investigate")
    todo = create(
        env,
        "ToDo",
        owner="alice@example.test",
        reference_type="Issue",
        reference_name=issue["name"],
        status="Open",
    )
    assert call(env, "doc_delete", doctype="Issue", name=issue["name"])[1]
    assert call(env, "doc_delete", doctype="User", name="alice@example.test")[1]
    assert not call(env, "doc_delete", doctype="ToDo", name=todo["name"])[1]
    assert not call(env, "doc_delete", doctype="Issue", name=issue["name"])[1]


@pytest.mark.parametrize("mode", ["create", "update", "fixture"])
def test_finite_line_quantity_overflow_is_atomic_business_error(env, mode):
    items = [
        {"item_code": "WIDGET", "qty": 1e308, "rate": 0},
        {"item_code": "WIDGET", "qty": 1e308, "rate": 0},
    ]
    if mode == "fixture":
        config = load_scenario().model_dump()
        config["erpnext_records"] = [
            {"doctype": "Customer", "name": "CUST", "data": {"customer_name": "Acme"}},
            {
                "doctype": "Item",
                "name": "WIDGET",
                "data": {"item_code": "WIDGET", "item_name": "Widget"},
            },
            {
                "doctype": "Sales Order",
                "name": "ORDER",
                "data": {"customer": "CUST", "items": items},
            },
        ]
        with pytest.raises(ValueError, match="total_qty|finite"):
            Scenario.model_validate(config)
    else:
        customer = create(env, "Customer", customer_name="Acme")
        create(env, "Item", item_code="WIDGET", item_name="Widget")
        order = None
        if mode == "update":
            order = create(
                env,
                "Sales Order",
                customer=customer["name"],
                items=[{"item_code": "WIDGET", "qty": 1, "rate": 1}],
            )
        assert env.episode is not None
        before = list(
            env.episode.db.connection.execute(
                "SELECT * FROM erpnext_documents ORDER BY doctype,name"
            )
        )
        ids = list(env.episode.db.connection.execute("SELECT * FROM erpnext_ids"))
        steps = env.state.step_count
        if mode == "create":
            value, error = call(
                env,
                "doc_create",
                doctype="Sales Order",
                data={"customer": customer["name"], "items": items},
            )
        else:
            assert order is not None
            value, error = call(
                env,
                "doc_update",
                doctype="Sales Order",
                name=order["name"],
                data={"items": items},
            )
        assert error and ("total_qty" in value["error"] or "finite" in value["error"])
        assert env.state.phase == "active" and env.state.step_count == steps + 1
        assert (
            list(
                env.episode.db.connection.execute(
                    "SELECT * FROM erpnext_documents ORDER BY doctype,name"
                )
            )
            == before
        )
        assert (
            list(env.episode.db.connection.execute("SELECT * FROM erpnext_ids")) == ids
        )


@pytest.mark.parametrize(
    "overflow", ["actual_qty", "reserved_qty", "stock_value", "transfer"]
)
def test_post_movement_overflow_rolls_back_all_bins_and_lifecycle(env, overflow):
    create(env, "Item", item_code="WIDGET", item_name="Widget")
    warehouse = create(env, "Warehouse", warehouse_name="Destination")["name"]
    create(
        env,
        "Bin",
        item_code="WIDGET",
        warehouse=warehouse,
        actual_qty=0 if overflow == "reserved_qty" else 1e308,
        reserved_qty=1e308 if overflow == "reserved_qty" else 0,
    )
    if overflow == "reserved_qty":
        customer = create(env, "Customer", customer_name="Acme")
        doc = create(
            env,
            "Sales Order",
            customer=customer["name"],
            items=[
                {"item_code": "WIDGET", "qty": 1e308, "rate": 0, "warehouse": warehouse}
            ],
        )
        kind = "Sales Order"
    else:
        data = {
            "stock_entry_type": "Material Receipt",
            "to_warehouse": warehouse,
            "items": [
                {
                    "item_code": "WIDGET",
                    "qty": 1 if overflow == "stock_value" else 1e308,
                    "basic_rate": 2 if overflow == "stock_value" else 0,
                }
            ],
        }
        if overflow == "transfer":
            source = create(env, "Warehouse", warehouse_name="Source")["name"]
            create(env, "Bin", item_code="WIDGET", warehouse=source, actual_qty=1e308)
            data.update(stock_entry_type="Material Transfer", from_warehouse=source)
        doc = create(env, "Stock Entry", **data)
        kind = "Stock Entry"
    assert env.episode is not None
    before = list(
        env.episode.db.connection.execute(
            "SELECT * FROM erpnext_documents ORDER BY doctype,name"
        )
    )
    value, error = call(env, "doc_submit", doctype=kind, name=doc["name"])
    assert error and "finite" in value["error"]
    assert env.state.phase == "active"
    assert (
        list(
            env.episode.db.connection.execute(
                "SELECT * FROM erpnext_documents ORDER BY doctype,name"
            )
        )
        == before
    )


@pytest.mark.parametrize("tool", ["kpi_revenue", "kpi_gross_margin"])
def test_finite_analytics_overflow_returns_deliberate_error(env, tool):
    customer = create(env, "Customer", customer_name="Acme")
    create(env, "Item", item_code="WIDGET", item_name="Widget")
    if tool == "kpi_revenue":
        for _ in range(2):
            create(
                env,
                "Sales Order",
                customer=customer["name"],
                items=[{"item_code": "WIDGET", "qty": 1, "rate": 1e308}],
            )
    else:
        warehouse = create(env, "Warehouse", warehouse_name="Stores")["name"]
        create(
            env, "Bin", item_code="WIDGET", warehouse=warehouse, valuation_rate=1e308
        )
        create(
            env,
            "Sales Order",
            customer=customer["name"],
            items=[{"item_code": "WIDGET", "qty": 1, "rate": 1e-308}],
        )
    value, error = call(env, tool)
    assert error and "finite" in value["error"]
    assert env.state.phase == "active"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_non_json_numbers_still_reject_before_invocation_accounting(env, value):
    before = env.state.model_dump()
    with pytest.raises(ValueError, match="JSON compliant"):
        env.step(
            ItopsAction(
                provider="erpnext",
                tool_name="erpnext_doc_create",
                arguments={
                    "doctype": "Item",
                    "data": {
                        "item_code": "BAD",
                        "item_name": "Bad",
                        "standard_rate": value,
                    },
                },
            )
        )
    assert env.state.model_dump() == before


def test_tied_customer_series_and_top_five_are_stable_across_hash_seeds():
    script = """
import json
from itops_env import ItopsAction
from itops_env.server.core.scenarios import load_scenario
from itops_env.server.itops_environment import ItopsEnvironment
world = ItopsEnvironment(scenario=load_scenario().model_copy(update={"step_budget": 1000, "horizon": 5000}))
world.reset()
def call(tool, **arguments):
    result = world.step(ItopsAction(provider="erpnext", tool_name="erpnext_" + tool, arguments=arguments))
    assert not result.is_error, result.content
    return json.loads(result.content[0]["text"])
try:
    call("doc_create", doctype="Item", data={"item_code": "WIDGET", "item_name": "Widget"})
    for name in ["Foxtrot", "Echo", "Delta", "Charlie", "Bravo", "Alpha"]:
        customer = call("doc_create", doctype="Customer", data={"customer_name": name})["data"]["name"]
        call("doc_create", doctype="Sales Order", data={"customer": customer, "items": [{"item_code": "WIDGET", "qty": 1, "rate": 10}]})
    print(json.dumps(call("revenue_trend", group_by="customer")))
finally:
    world.close()
"""
    outputs = []
    for seed in ("0", "1", "42"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            env=os.environ | {"PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        chart = json.loads(result.stdout)
        assert [dataset["label"] for dataset in chart["datasets"]] == [
            "Alpha",
            "Bravo",
            "Charlie",
            "Delta",
            "Echo",
        ]
        assert [dataset["color"] for dataset in chart["datasets"]] == [
            "#60a5fa",
            "#4ade80",
            "#fbbf24",
            "#c084fc",
            "#f472b6",
        ]
        assert [dataset["values"] for dataset in chart["datasets"]] == [
            [0, 0, 0, 0, 0, 10]
        ] * 5
        outputs.append(chart)
    assert outputs[0] == outputs[1] == outputs[2]
