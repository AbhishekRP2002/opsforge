import pytest

from .test_erpnext_operations import call, create
from .test_erpnext_operations import env as erpnext_fixture

env = erpnext_fixture


def test_project_task_assignment_and_timesheet_share_documents(env):
    project, error = call(
        env,
        "project_create",
        project_name="Launch",
        expected_start_date="2026-01-01",
        expected_end_date="2026-01-31",
    )
    assert not error
    project = project["data"]
    assert call(env, "project_get", name=project["name"])[0]["data"] == project
    assert (
        call(env, "project_list", date_from="2026-01-01", date_to="2026-01-31")[0][
            "count"
        ]
        == 1
    )
    user = create(
        env,
        "User",
        name="alice@example.test",
        full_name="Alice",
        enabled=1,
        user_type="System User",
    )
    task, error = call(
        env,
        "task_create",
        project=project["name"],
        subject="Prepare",
        assign_to=[user["name"], user["name"]],
    )
    assert not error
    assert task["assignment"]["assignees"] == ["alice@example.test"]
    assert task["assignment"]["notify_user"] is True
    name = task["data"]["name"]
    assert call(env, "task_get", name=name)[0]["data"]["project"] == project["name"]
    assert (
        call(env, "task_update", name=name, progress=50, status="Working")[0]["data"][
            "progress"
        ]
        == 50
    )
    assert (
        call(env, "task_list", project=project["name"], status="Working")[0]["count"]
        == 1
    )
    assigned, error = call(
        env, "doc_assign", doctype="Task", name=name, assign_to=user["name"]
    )
    assert not error and assigned["assignment"]["todos"] == task["assignment"]["todos"]
    todos = call(
        env, "doc_list", doctype="ToDo", fields=["*"], filters=[["status", "=", "Open"]]
    )[0]["data"]
    assert len(todos) == 1 and todos[0]["reference_name"] == name
    assert (
        call(env, "doc_unassign", doctype="Task", name=name, assign_to=user["name"])[0][
            "assignment"
        ]["remaining"]
        == []
    )
    assert (
        call(
            env,
            "doc_list",
            doctype="ToDo",
            fields=["*"],
            filters=[["status", "=", "Closed"]],
        )[0]["count"]
        == 1
    )
    employee = create(env, "Employee", employee_name="Alice")
    timesheet = create(
        env,
        "Timesheet",
        employee=employee["name"],
        project=project["name"],
        start_date="2026-01-01",
        end_date="2026-01-02",
        total_hours=7,
    )
    assert (
        call(env, "timesheet_get", name=timesheet["name"])[0]["data"]["total_hours"]
        == 7
    )
    assert (
        call(env, "timesheet_list", employee="Alice", project=project["name"])[0][
            "count"
        ]
        == 1
    )


@pytest.mark.parametrize(
    "tool,args",
    [
        ("project_create", {"project_name": ""}),
        ("project_list", {"limit": -1}),
        ("project_get", {"name": "missing"}),
        ("task_create", {"project": "missing", "subject": "A"}),
        ("task_get", {"name": "missing"}),
        ("task_list", {"limit": -1}),
        ("task_update", {"name": "missing", "progress": 50}),
        ("timesheet_get", {"name": "missing"}),
        ("timesheet_list", {"employee": "missing"}),
        (
            "doc_assign",
            {"doctype": "Task", "name": "missing", "assign_to": "nobody@example.test"},
        ),
        (
            "doc_unassign",
            {"doctype": "Task", "name": "missing", "assign_to": "nobody@example.test"},
        ),
    ],
)
def test_project_family_deliberate_failures(env, tool, args):
    value, error = call(env, tool, **args)
    assert error and value["error"] != "Unknown provider or tool"


def test_assignment_validation_and_partial_failure(env):
    project = create(env, "Project", project_name="Launch")
    task = create(env, "Task", subject="Prepare", project=project["name"])
    create(
        env,
        "User",
        name="disabled@example.test",
        full_name="Disabled",
        enabled=0,
        user_type="System User",
    )
    for args in (
        {"assign_to": "disabled@example.test"},
        {"assign_to": "missing@example.test"},
        {"assign_to": "disabled@example.test", "notify_user": False},
    ):
        assert call(
            env, "task_update", name=task["name"], description="Must not change", **args
        )[1]
        assert "description" not in call(env, "task_get", name=task["name"])[0]["data"]
    assert call(
        env, "doc_update", doctype="Task", name=task["name"], data={"project": []}
    )[1]
    assert call(
        env, "doc_update", doctype="Task", name=task["name"], data={"project": ""}
    )[1]
    assert call(env, "task_update", name=task["name"], progress=101)[1]
