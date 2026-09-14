import pytest

from .test_servicenow_incidents import call
from .test_servicenow_incidents import env as snow_fixture

env = snow_fixture


def test_script_fixture_boolean_projection(env):
    from itops_env.server.services import servicenow_store as store

    assert env.episode is not None
    with env.episode.db.connection:
        store.insert(
            env.episode.db,
            "sys_script_include",
            {"name": "Fixture", "active": "false", "client_callable": "true"},
            0,
            0,
        )
    detail = call(env, "get_script_include", script_include_id="Fixture")[0][
        "script_include"
    ]
    listed = call(env, "list_script_includes", active=False)[0]["script_includes"][0]
    for row in (detail, listed):
        assert row["active"] is False and row["client_callable"] is True


def test_script_include_opaque_roundtrip_name_and_prefixed_id(env):
    value, error = call(
        env,
        "create_script_include",
        name="Opaque",
        script="throw new Error('inert')",
        access="custom",
    )
    assert not error and value["success"]
    key = value["script_include_id"]
    assert (
        call(env, "get_script_include", script_include_id="Opaque")[0][
            "script_include"
        ]["script"]
        == "throw new Error('inert')"
    )
    assert call(
        env,
        "update_script_include",
        script_include_id="sys_id:" + key,
        script="",
        active=False,
    )[0]["success"]
    assert (
        call(env, "get_script_include", script_include_id="Opaque")[0][
            "script_include"
        ]["script"]
        == ""
    )
    listed = call(env, "list_script_includes", active=False, query="Opa")[0]
    assert listed["total"] == 1 and "script" not in listed["script_includes"][0]
    assert call(env, "delete_script_include", script_include_id="Opaque")[0]["success"]
    assert (
        call(env, "get_script_include", script_include_id="Opaque")[0]["success"]
        is False
    )


@pytest.mark.parametrize(
    "tool,args",
    [
        ("create_script_include", {"name": "huge", "script": "x" * 1048577}),
        ("get_script_include", {"script_include_id": "absent"}),
        ("update_script_include", {"script_include_id": "absent"}),
        ("delete_script_include", {"script_include_id": "absent"}),
        ("list_script_includes", {"limit": -1}),
    ],
)
def test_script_include_business_failures(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and value["success"] is False


def test_changesets_opaque_files_publish_without_invented_precursor(env):
    from itops_env.server.core.scenarios import Scenario, load_scenario
    from itops_env.server.itops_environment import ItopsEnvironment

    raw = load_scenario().model_dump() | {
        "servicenow_records": [
            {
                "table": "sys_scope",
                "sys_id": "cccccccccccccccccccccccccccccccc",
                "data": {"name": "Fixture"},
            }
        ]
    }
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    try:
        created, error = call(
            world,
            "create_changeset",
            name="Update",
            application="cccccccccccccccccccccccccccccccc",
        )
        assert not error and created["success"]
        key = created["changeset"]["sys_id"]
        assert (
            call(
                world,
                "publish_changeset",
                changeset_id=key,
                publish_notes="Direct publish",
            )[0]["changeset"]["state"]
            == "published"
        )
        assert (
            call(world, "commit_changeset", changeset_id=key, commit_message="Commit")[
                0
            ]["changeset"]["state"]
            == "complete"
        )
        assert (
            call(world, "update_changeset", changeset_id=key, name="Updated")[0][
                "changeset"
            ]["name"]
            == "Updated"
        )
        file, error = call(
            world,
            "add_file_to_changeset",
            changeset_id=key,
            file_path="/etc/passwd",
            file_content="opaque",
        )
        assert not error and file["file"]["payload"] == "opaque"
        detail = call(world, "get_changeset_details", changeset_id=key)[0]
        assert (
            detail["change_count"] == 1
            and detail["changes"][0]["name"] == "/etc/passwd"
        )
        listed = call(world, "list_changesets", query="nameLIKEUpdated^ORDERBYname")[0]
        assert listed["count"] == 1
    finally:
        world.close()


@pytest.mark.parametrize(
    "tool,args",
    [
        ("create_changeset", {"name": "Bad", "application": "missing"}),
        ("update_changeset", {"changeset_id": "missing", "name": "Bad"}),
        ("get_changeset_details", {"changeset_id": "missing"}),
        ("commit_changeset", {"changeset_id": "missing"}),
        ("publish_changeset", {"changeset_id": "missing"}),
        (
            "add_file_to_changeset",
            {"changeset_id": "missing", "file_path": "x", "file_content": "x"},
        ),
        ("list_changesets", {"query": "nameINa,b"}),
    ],
)
def test_changeset_business_failures(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and value["success"] is False
