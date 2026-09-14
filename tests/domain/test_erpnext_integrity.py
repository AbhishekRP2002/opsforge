import json

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment

from .test_erpnext_operations import call, create
from .test_erpnext_operations import env as erpnext_fixture

env = erpnext_fixture


def test_typed_fixture_epoch_reference_validation_and_usage():
    data = load_scenario().model_dump()
    data.update(
        erpnext_epoch="2026-03-15T00:00:00+00:00",
        erpnext_records=[
            {
                "doctype": "Customer",
                "name": "CUST-1",
                "data": {"customer_name": "Acme"},
            },
            {
                "doctype": "Item",
                "name": "WIDGET",
                "data": {"item_code": "WIDGET", "item_name": "Widget"},
            },
            {
                "doctype": "Sales Order",
                "name": "SO-1",
                "data": {
                    "customer": "CUST-1",
                    "items": [{"item_code": "WIDGET", "qty": 2, "rate": 3}],
                    "transaction_date": "2026-03-01",
                },
                "docstatus": 1,
            },
        ],
    )
    world = ItopsEnvironment(scenario=Scenario.model_validate(data))
    world.reset()
    try:
        assert call(world, "kpi_revenue")[0]["value"] == 6
        assert (
            call(world, "doc_get", doctype="Sales Order", name="SO-1")[0]["data"][
                "grand_total"
            ]
            == 6
        )
    finally:
        world.close()
    data["erpnext_records"][2]["data"]["customer"] = "missing"
    with pytest.raises(ValueError, match="reference|exist"):
        Scenario.model_validate(data)
    data["erpnext_records"] = []
    data["erpnext_epoch"] = "2026-01-01"
    with pytest.raises(ValueError, match="UTC|timezone"):
        Scenario.model_validate(data)


def test_modelled_assignment_failure_preserves_field_update():
    data = load_scenario().model_dump()
    data.update(erpnext_assignment_failures=["alice@example.test"])
    world = ItopsEnvironment(scenario=Scenario.model_validate(data))
    world.reset()
    try:
        create(
            world,
            "User",
            name="alice@example.test",
            full_name="Alice",
            enabled=1,
            user_type="System User",
        )
        project = create(world, "Project", project_name="Launch")
        task = create(world, "Task", subject="Before", project=project["name"])
        value, error = call(
            world,
            "task_update",
            name=task["name"],
            description="Committed",
            assign_to="alice@example.test",
        )
        assert error and "updated, but assignment failed" in value["error"]
        assert (
            call(world, "task_get", name=task["name"])[0]["data"]["description"]
            == "Committed"
        )
        assert call(world, "doc_list", doctype="ToDo")[0]["count"] == 0
    finally:
        world.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("transaction_date", []),
        ("customer", {}),
        ("status", []),
        ("due_date", {}),
        ("item_code", []),
        ("is_stock_item", []),
        ("expected_time", []),
        ("disabled", {}),
        ("selling", []),
        ("currency", {}),
    ],
)
def test_nested_wrong_type_is_deliberate_business_error(env, field, value):
    customer = create(env, "Customer", customer_name="Acme")
    value, error = call(
        env,
        "doc_update",
        doctype="Customer",
        name=customer["name"],
        data={field: value},
    )
    assert error and value["error"]
    assert call(env, "customer_get", name=customer["name"])[0]["data"] == customer


def test_numeric_order_and_filter_validation_in_empty_world(env):
    call(env, "item_create", item_code="TWO", item_name="Two", standard_rate=2)
    call(env, "item_create", item_code="TEN", item_name="Ten", standard_rate=10)
    value, error = call(
        env,
        "doc_list",
        doctype="Item",
        fields=["standard_rate"],
        order_by="standard_rate desc",
    )
    assert not error and value["data"] == [{"standard_rate": 10}, {"standard_rate": 2}]
    assert call(env, "doc_list", doctype="Company", filters=[["name", "like", 4]])[1]


def test_leave_usage_submit_cancel_and_private_projection(env):
    employee = create(env, "Employee", employee_name="Alice")
    leave = create(env, "Leave Type", leave_type_name="Annual")
    allocation = create(
        env,
        "Leave Allocation",
        employee=employee["name"],
        leave_type=leave["name"],
        from_date="2026-01-01",
        to_date="2026-12-31",
        total_leaves_allocated=10,
    )
    assert not call(
        env, "doc_submit", doctype="Leave Allocation", name=allocation["name"]
    )[1]
    application = create(
        env,
        "Leave Application",
        employee=employee["name"],
        leave_type=leave["name"],
        from_date="2026-02-01",
        to_date="2026-02-03",
        status="Approved",
    )
    assert not call(
        env, "doc_submit", doctype="Leave Application", name=application["name"]
    )[1]
    persisted = call(
        env, "doc_get", doctype="Leave Allocation", name=allocation["name"]
    )[0]["data"]
    assert persisted["used_leaves"] == 3
    assert persisted["remaining_leaves"] == 7
    assert (
        call(env, "doc_get", doctype="Leave Application", name=application["name"])[0][
            "data"
        ]["status"]
        == "Approved"
    )
    balance = call(env, "leave_balance", employee=employee["name"])[0]
    assert "used_leaves" not in balance["data"][0]
    assert not call(
        env, "doc_cancel", doctype="Leave Application", name=application["name"]
    )[1]
    assert (
        call(env, "doc_get", doctype="Leave Allocation", name=allocation["name"])[0][
            "data"
        ]["remaining_leaves"]
        == 10
    )


def test_safe_unicode_filename_has_retrievable_opaque_artifact_path(env):
    parent = create(env, "Customer", customer_name="Acme")
    value, error = call(
        env,
        "file_upload",
        file_name="résumé report.txt",
        content_base64="YWJj",
        attached_to_doctype="Customer",
        attached_to_name=parent["name"],
    )
    assert not error
    assert value["data"]["artifact_path"] == "artifacts/erpnext/ERP-000002.bin"


def test_file_list_missing_parent_is_a_deliberate_error(env):
    value, error = call(
        env, "file_list", attached_to_doctype="Customer", attached_to_name="missing"
    )
    assert error and "does not exist" in value["error"]


def test_generic_deletion_and_item_identity_cannot_break_links(env):
    customer = create(env, "Customer", customer_name="Acme")
    create(env, "Item", item_code="WIDGET", item_name="Widget")
    order = create(
        env,
        "Sales Order",
        customer=customer["name"],
        items=[{"item_code": "WIDGET", "qty": 1, "rate": 3}],
    )
    assert call(env, "doc_delete", doctype="Customer", name=customer["name"])[1]
    assert call(
        env, "doc_update", doctype="Item", name="WIDGET", data={"item_code": "RENAMED"}
    )[1]
    assert (
        call(env, "sales_order_get", name=order["name"])[0]["data"]["customer"]
        == customer["name"]
    )


def test_linked_labels_and_nested_item_types_remain_analytics_readable(env):
    customer = create(env, "Customer", customer_name="Acme")
    create(env, "Item", item_code="WIDGET", item_name="Widget")
    order = create(
        env,
        "Sales Order",
        customer=customer["name"],
        items=[{"item_code": "WIDGET", "qty": 1, "rate": 3}],
    )
    assert order["customer_name"] == "Acme"
    assert order["items"][0]["item_name"] == "Widget"
    assert call(env, "order_breakdown", type="pie")[0]["labels"] == ["Acme"]
    value, error = call(
        env,
        "doc_update",
        doctype="Sales Order",
        name=order["name"],
        data={"items": [{"item_code": "WIDGET", "qty": 1, "rate": 3, "item_name": {}}]},
    )
    assert error and "item_name" in value["error"]


def test_fixture_allocated_generated_names_cannot_collide(env):
    data = load_scenario().model_dump()
    data["erpnext_records"] = [
        {
            "doctype": "Customer",
            "name": "ERP-000002",
            "data": {"customer_name": "Existing"},
        }
    ]
    world = ItopsEnvironment(scenario=Scenario.model_validate(data))
    world.reset()
    try:
        fresh = create(world, "Customer", customer_name="Fresh")
        assert fresh["name"] == "ERP-000003"
        assert (
            call(world, "customer_get", name="ERP-000002")[0]["data"]["customer_name"]
            == "Existing"
        )
    finally:
        world.close()


def test_attachment_unexpected_failure_rolls_back_ids_bytes_and_accounting(
    env, monkeypatch
):
    from itops_env.server.services import erpnext_store as store

    parent = create(
        env,
        "Company",
        company_name="Acme",
        abbr="AC",
        default_currency="USD",
        country="US",
    )
    action = ItopsAction(
        provider="erpnext",
        tool_name="erpnext_file_upload",
        arguments={
            "file_name": "safe",
            "content_base64": "YWJj",
            "attached_to_doctype": "Company",
            "attached_to_name": parent["name"],
        },
        invocation_id="rollback",
    )
    before = env.state.model_dump()
    original = store.persist

    def broken(db, kind, data):
        if kind == "File" and "artifact_path" in data:
            raise RuntimeError("injected storage failure")
        return original(db, kind, data)

    monkeypatch.setattr(store, "persist", broken)
    with pytest.raises(RuntimeError, match="injected"):
        env.step(action)
    assert env.state.model_dump() == before
    assert env.episode is not None
    assert (
        env.episode.db.connection.execute(
            "SELECT count(*) FROM episode_artifacts"
        ).fetchone()[0]
        == 0
    )
    assert (
        env.episode.db.connection.execute(
            "SELECT count(*) FROM erpnext_ids"
        ).fetchone()[0]
        == 1
    )
    monkeypatch.setattr(store, "persist", original)
    uploaded = env.step(action)
    assert (
        not uploaded.is_error
        and json.loads(uploaded.content[0]["text"])["data"]["name"] == "ERP-000002"
    )
    env.reset()
    assert call(
        env,
        "file_download",
        file_id="ERP-000002",
        attached_to_doctype="Company",
        attached_to_name=parent["name"],
    )[1]
