import pytest

from .test_servicenow_incidents import call
from .test_servicenow_incidents import env as snow_fixture

env = snow_fixture


def test_agile_relationships_roundtrip_and_source_ignored_zero_fields(env):
    project, error = call(
        env, "create_project", short_description="Project", percentage_complete=5
    )
    assert not error and project["success"]
    pid = project["project"]["sys_id"]
    assert (
        call(
            env,
            "update_project",
            project_id=pid,
            description="Updated",
            percentage_complete=0,
        )[0]["project"]["percentage_complete"]
        == 5
    )
    assert call(env, "list_projects", query="description=Updated")[0]["count"] == 1
    epic = call(env, "create_epic", short_description="Epic", state="ignored")[0][
        "epic"
    ]
    assert "state" not in epic
    eid = epic["sys_id"]
    assert (
        call(env, "update_epic", epic_id=eid, priority="custom", state="ignored")[0][
            "epic"
        ]["priority"]
        == "custom"
    )
    assert call(env, "list_epics", priority="custom")[0]["count"] == 1
    story = call(
        env,
        "create_story",
        short_description="Story",
        acceptance_criteria="Works",
        project=pid,
        epic=eid,
    )[0]["story"]
    sid = story["sys_id"]
    assert story["story_points"] == 10 and story["epic"] == eid
    assert (
        call(env, "update_story", story_id=sid, state="tenant-custom", story_points=0)[
            0
        ]["story"]["story_points"]
        == 10
    )
    assert call(env, "list_stories", state="tenant-custom")[0]["count"] == 1
    other = call(
        env, "create_story", short_description="Other", acceptance_criteria="Ready"
    )[0]["story"]
    dependency = call(
        env,
        "create_story_dependency",
        dependent_story=sid,
        prerequisite_story=other["sys_id"],
    )[0]["story_dependency"]
    assert (
        call(env, "list_story_dependencies", dependent_story=sid)[0][
            "story_dependencies"
        ][0]["sys_id"]
        == dependency["sys_id"]
    )
    assert call(env, "delete_story_dependency", dependency_id=dependency["sys_id"])[0][
        "success"
    ]
    assert call(env, "list_story_dependencies", dependent_story=sid)[0]["count"] == 0
    task = call(env, "create_scrum_task", story=sid, short_description="Task", hours=2)[
        0
    ]["scrum_task"]
    assert (
        call(
            env,
            "update_scrum_task",
            scrum_task_id=task["sys_id"],
            hours=0,
            state="custom",
        )[0]["scrum_task"]["hours"]
        == 2
    )
    assert call(env, "list_scrum_tasks", state="custom")[0]["count"] == 1


@pytest.mark.parametrize(
    "tool,args",
    [
        ("create_project", {"short_description": "Bad", "project_manager": "absent"}),
        ("update_project", {"project_id": "absent"}),
        ("list_projects", {"query": "stateIN1,2"}),
        ("create_epic", {"short_description": "Bad", "assigned_to": "absent"}),
        ("update_epic", {"epic_id": "absent"}),
        ("list_epics", {"query": "priorityIN1,2"}),
        (
            "create_story",
            {
                "short_description": "Bad",
                "acceptance_criteria": "Bad",
                "epic": "absent",
            },
        ),
        ("update_story", {"story_id": "absent"}),
        ("list_stories", {"query": "stateIN1,2"}),
        (
            "create_story_dependency",
            {"dependent_story": "absent", "prerequisite_story": "absent"},
        ),
        ("delete_story_dependency", {"dependency_id": "absent"}),
        ("list_story_dependencies", {"query": "sys_idIN1,2"}),
        ("create_scrum_task", {"story": "absent", "short_description": "Bad"}),
        ("update_scrum_task", {"scrum_task_id": "absent"}),
        ("list_scrum_tasks", {"query": "stateIN1,2"}),
    ],
)
def test_agile_business_failures(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and value["success"] is False
