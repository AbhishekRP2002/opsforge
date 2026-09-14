import pytest

from .test_erpnext_operations import call, create
from .test_erpnext_operations import env as erpnext_fixture

env = erpnext_fixture


@pytest.mark.parametrize(
    "kind,destination,status",
    [
        ("Task", "working", "Working"),
        ("Opportunity", "quotation", "Quotation"),
        ("Issue", "resolved", "Resolved"),
    ],
)
def test_kanban_transition_and_stale_rejection(env, kind, destination, status):
    if kind == "Task":
        project = create(env, "Project", project_name="Launch")
        doc = create(
            env,
            "Task",
            project=project["name"],
            subject="Prepare",
            priority="High",
            exp_end_date="2025-12-31",
        )
    elif kind == "Opportunity":
        lead = create(env, "Lead", lead_name="Prospect")
        doc = create(
            env,
            kind,
            opportunity_from="Lead",
            party_name=lead["name"],
            opportunity_amount=5,
        )
    else:
        doc = create(env, kind, subject="Problem", raised_by="alice@example.test")
    board, error = call(env, "kanban_get_board", doctype=kind, limit=1)
    assert not error and board["cards"][0]["columnId"] == "open"
    assert board["pagination"] == {
        "limit": 1,
        "offset": 0,
        "loadedCount": 1,
        "hasMore": False,
    }
    moved, error = call(
        env,
        "kanban_move_card",
        doctype=kind,
        card_id=doc["name"],
        from_column="open",
        to_column=destination,
    )
    assert (
        not error
        and moved["ok"] is True
        and moved["serverCard"]["columnId"] == destination
    )
    assert (
        call(env, "doc_get", doctype=kind, name=doc["name"])[0]["data"]["status"]
        == status
    )
    stale, error = call(
        env,
        "kanban_move_card",
        doctype=kind,
        card_id=doc["name"],
        from_column="open",
        to_column=destination,
    )
    assert not error and stale["ok"] is False and stale["fromColumn"] == destination
    assert call(env, "kanban_get_board", doctype=kind, limit=-1)[1]


def test_task_overdue_column_is_system_managed(env):
    project = create(env, "Project", project_name="Launch")
    task = create(env, "Task", project=project["name"], subject="Prepare")
    result, error = call(
        env,
        "kanban_move_card",
        doctype="Task",
        card_id=task["name"],
        from_column="open",
        to_column="overdue",
    )
    assert (
        not error
        and result["ok"] is False
        and result["errorMessage"] == "Overdue is system-managed"
    )
