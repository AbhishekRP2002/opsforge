import json
import sqlite3

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment
from itops_env.server.mcp_servers import tools
from pydantic import ValidationError

from .test_servicenow_incidents import call
from .test_servicenow_incidents import env as snow_fixture

env = snow_fixture


@pytest.mark.parametrize(
    "tool,args",
    [
        ("add_change_task", {"change_id": "", "short_description": "Orphan"}),
        ("create_scrum_task", {"story": "", "short_description": "Orphan"}),
        ("create_story_dependency", {"dependent_story": "", "prerequisite_story": ""}),
        (
            "create_catalog_item_variable",
            {"catalog_item_id": "", "name": "x", "type": "6", "label": "x"},
        ),
        ("create_category", {"knowledge_base": "", "title": "Orphan"}),
        (
            "create_article",
            {
                "knowledge_base": "",
                "category": "",
                "title": "x",
                "short_description": "x",
                "text": "x",
            },
        ),
        ("create_changeset", {"name": "Orphan", "application": ""}),
    ],
)
def test_required_empty_parent_references_do_not_mutate(env, tool, args):
    assert env.episode is not None
    connection = env.episode.db.connection
    before = connection.execute("SELECT * FROM servicenow_records").fetchall()
    result, error = call(env, tool, **args)
    assert not error and result["success"] is False
    assert "simulation_profile" in result["message"]
    assert connection.execute("SELECT * FROM servicenow_records").fetchall() == before


@pytest.mark.parametrize(
    "table,field",
    [
        ("change_task", "change_request"),
        ("rm_scrum_task", "story"),
        ("m2m_story_dependencies", "dependent_story"),
        ("item_option_new", "cat_item"),
        ("kb_category", "kb_knowledge_base"),
        ("kb_knowledge", "kb_knowledge_base"),
        ("sys_update_set", "application"),
        ("sys_update_xml", "update_set"),
        ("wf_activity", "workflow_version"),
        ("wf_workflow_version", "workflow"),
        ("sysapproval_approver", "document_id"),
        ("sys_user_has_role", "user"),
    ],
)
@pytest.mark.parametrize("value", ["", None, [], {}])
def test_required_fixture_reference_rejects_empty_or_malformed(table, field, value):
    raw = load_scenario().model_dump()
    raw["servicenow_records"] = [
        {"table": table, "sys_id": "a" * 32, "data": {field: value}}
    ]
    with pytest.raises(ValidationError, match="fixture reference"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize(
    "query,expected",
    [
        ("ORDERBYstate^ORDERBYshort_description", [("1", "Y"), ("1", "Z"), ("2", "A")]),
        (
            "ORDERBYstate^ORDERBYDESCshort_description",
            [("1", "Z"), ("1", "Y"), ("2", "A")],
        ),
    ],
)
def test_compound_ordering_preserves_leftmost_priority(env, query, expected):
    from itops_env.server.services import servicenow_store as store

    assert env.episode is not None
    with env.episode.db.connection:
        for state, title in [("1", "Z"), ("2", "A"), ("1", "Y")]:
            store.insert(
                env.episode.db,
                "change_request",
                {"short_description": title, "state": state},
                0,
                0,
            )
    rows = call(env, "list_change_requests", query=query)[0]["change_requests"]
    assert [(row["state"], row["short_description"]) for row in rows] == expected


def test_change_timeframes_use_simulated_clock_and_reject_unsupported_query(env):
    call(
        env,
        "create_change_request",
        short_description="Future",
        type="normal",
        start_date="2026-01-02 00:00:00",
        end_date="2026-01-03 00:00:00",
    )
    call(
        env,
        "create_change_request",
        short_description="Past",
        type="normal",
        start_date="2025-12-29 00:00:00",
        end_date="2025-12-30 00:00:00",
    )
    result = call(env, "list_change_requests", timeframe="upcoming")[0]
    assert [row["short_description"] for row in result["change_requests"]] == ["Future"]
    result = call(env, "list_change_requests", timeframe="completed")[0]
    assert [row["short_description"] for row in result["change_requests"]] == ["Past"]
    result = call(env, "list_change_requests", query="start_date>2026-01-01 00:00:00")[
        0
    ]
    assert result["count"] == 1
    result = call(
        env, "list_change_requests", query="sys_created_on>javascript:arbitrary()"
    )[0]
    assert (
        result["success"] is False
        and "unsupported_simulation_query" in result["message"]
    )


def test_changeset_date_macros_are_bounded_calendar_ranges():
    raw = load_scenario().model_dump() | {
        "servicenow_records": [
            {"table": "sys_scope", "sys_id": "a" * 32, "data": {"name": "Scope"}},
            {
                "table": "sys_update_set",
                "sys_id": "cccccccccccccccccccccccccccccccc",
                "data": {
                    "name": "Recent",
                    "sys_created_on": "2025-12-30 00:00:00",
                    "application": "a" * 32,
                },
            },
            {
                "table": "sys_update_set",
                "sys_id": "dddddddddddddddddddddddddddddddd",
                "data": {
                    "name": "Old",
                    "sys_created_on": "2025-12-01 00:00:00",
                    "application": "a" * 32,
                },
            },
        ]
    }
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    try:
        assert call(world, "list_changesets", timeframe="recent")[0]["count"] == 1
        assert call(world, "list_changesets", timeframe="last_month")[0]["count"] == 2
        result = call(
            world,
            "list_changesets",
            query="sys_created_onONLast 7 days@javascript:gs.beginningOfLast7Days()@javascript:gs.endOfToday()",
        )[0]
        assert result["count"] == 1
    finally:
        world.close()


def test_unexpected_handler_exception_restores_state_and_rolls_back(env, monkeypatch):
    real = tools.HANDLER_RESOLVERS["servicenow"]

    def fail(db, arguments, step, clock):
        db.connection.execute(
            "INSERT INTO servicenow_records VALUES ('incident','x','{}')"
        )
        raise RuntimeError("unexpected persistence adapter failure")

    monkeypatch.setitem(
        tools.HANDLER_RESOLVERS,
        "servicenow",
        lambda: dict(real()) | {"create_incident": fail},
    )
    before = env.state.model_dump()
    env.episode.db.connection.execute(
        "INSERT INTO events (sequence,at,kind,group_id) VALUES (999,1,'group_unavailable','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')"
    )
    env.episode.db.connection.commit()
    with pytest.raises(RuntimeError, match="unexpected persistence"):
        call(env, "create_incident", short_description="Rollback")
    assert env.state.model_dump() == before
    assert (
        env.episode.db.connection.execute(
            "SELECT applied FROM events WHERE sequence=999"
        ).fetchone()[0]
        == 0
    )
    assert (
        env.episode.db.connection.execute(
            "SELECT available FROM servicenow_groups WHERE sys_id='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
        ).fetchone()[0]
        == 1
    )
    assert (
        env.episode.db.connection.execute(
            "SELECT count(*) FROM servicenow_records"
        ).fetchone()[0]
        == 0
    )
    assert (
        env.episode.db.connection.execute("SELECT count(*) FROM delivery").fetchone()[0]
        == 0
    )
    assert (
        env.episode.db.connection.execute("SELECT count(*) FROM journal").fetchone()[0]
        == 0
    )


def test_sqlite_failure_rolls_back_partial_membership_effects(env, monkeypatch):
    db = env.episode.db
    original = db.record

    def fail(step, clock, kind, provider, record_id, group_id=None):
        original(step, clock, kind, provider, record_id, group_id)
        if kind == "membership_added":
            raise sqlite3.OperationalError("modeled persistence failure")

    monkeypatch.setattr(db, "record", fail)
    with pytest.raises(sqlite3.OperationalError, match="persistence failure"):
        call(
            env,
            "add_group_members",
            group_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            members=["alex.chen"],
        )
    assert (
        db.connection.execute("SELECT count(*) FROM servicenow_memberships").fetchone()[
            0
        ]
        == 0
    )
    assert env.state.step_count == 0


def test_fixture_references_and_dependency_table_are_explicit():
    raw = load_scenario().model_dump()
    raw["servicenow_records"] = [
        {
            "table": "item_option_new",
            "sys_id": "cccccccccccccccccccccccccccccccc",
            "data": {"cat_item": "missing"},
        }
    ]
    with pytest.raises(ValidationError, match="reference"):
        Scenario.model_validate(raw)
    raw["servicenow_records"] = [
        {
            "table": "m2m_story_dependencies",
            "sys_id": "cccccccccccccccccccccccccccccccc",
            "data": {"dependent_story": "missing", "prerequisite_story": "missing"},
        }
    ]
    with pytest.raises(ValidationError, match="reference"):
        Scenario.model_validate(raw)


def test_nested_defaults_replay_and_reset_preserve_state(env):
    raw = {"name": "Replay", "attributes": {"nested": ["original"]}, "ignored": 1}
    action = ItopsAction(
        provider="servicenow",
        tool_name="create_workflow",
        arguments=raw,
        invocation_id="repeat",
    )
    first = env.step(action)
    assert first.is_error
    assert env.step(action).content == first.content
    assert env.state.step_count == 1
    payload = env.episode.db.connection.execute(
        "SELECT payload FROM delivery WHERE invocation_id='repeat'"
    ).fetchone()[0]
    assert json.loads(payload)["arguments"] == raw
    assert call(env, "list_workflows")[0]["count"] == 0
    valid_raw = {"name": "Replay", "attributes": {"nested": ["original"]}}
    valid = ItopsAction(
        provider="servicenow",
        tool_name="create_workflow",
        arguments=valid_raw,
        invocation_id="valid-repeat",
    )
    created = env.step(valid)
    assert not created.is_error
    assert env.step(valid).content == created.content
    assert env.state.step_count == 3 and env.state.simulated_clock == 3
    assert json.loads(created.content[0]["text"])["workflow"]["nested"] == ["original"]
    assert valid_raw == {"name": "Replay", "attributes": {"nested": ["original"]}}
    valid_payload = env.episode.db.connection.execute(
        "SELECT payload FROM delivery WHERE invocation_id='valid-repeat'"
    ).fetchone()[0]
    assert json.loads(valid_payload)["arguments"] == valid_raw
    env.reset()
    assert call(env, "list_workflows")[0]["count"] == 0


def test_script_plain_32_character_selector_is_name_not_id(env):
    result = call(env, "create_script_include", name="Name", script="inert")[0]
    key = result["script_include_id"]
    assert call(env, "get_script_include", script_include_id=key)[0]["success"] is False
    assert call(env, "get_script_include", script_include_id="sys_id:" + key)[0][
        "success"
    ]


def test_modeled_approval_failure_retains_state_change():
    raw = load_scenario().model_dump() | {
        "servicenow_denied_operations": {"sysapproval_approver.create": ["*"]}
    }
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    try:
        created = call(
            world, "create_change_request", short_description="Partial", type="normal"
        )[0]
        key = created["change_request"]["sys_id"]
        failed, error = call(world, "submit_change_for_approval", change_id=key)
        assert not error and failed["success"] is False
        assert (
            call(world, "get_change_request_details", change_id=key)[0][
                "change_request"
            ]["state"]
            == "assess"
        )
        assert world.episode is not None
        assert (
            world.episode.db.connection.execute(
                "SELECT count(*) FROM servicenow_records WHERE table_name='sysapproval_approver'"
            ).fetchone()[0]
            == 0
        )
    finally:
        world.close()


def test_extended_user_fixture_does_not_leak_internal_profile_fields():
    raw = load_scenario().model_dump()
    raw["servicenow_users"][1]["profile"] = {
        "first_name": "Sam",
        "last_name": "Lee",
        "title": "Engineer",
    }
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    try:
        target = call(world, "get_user", user_name="alex.chen")[0]["user"]
        assert set(target) == {"sys_id", "user_name", "email", "name", "active"}
        other = call(world, "get_user", user_name="sam.lee")[0]["user"]
        assert other["title"] == "Engineer" and "profile" not in other
    finally:
        world.close()


def test_approval_secondary_change_failure_keeps_approval_update():
    key = "cccccccccccccccccccccccccccccccc"
    aid = "dddddddddddddddddddddddddddddddd"
    raw = load_scenario().model_dump() | {
        "servicenow_records": [
            {"table": "change_request", "sys_id": key, "data": {"state": "assess"}},
            {
                "table": "sysapproval_approver",
                "sys_id": aid,
                "data": {"document_id": key, "state": "requested"},
            },
        ],
        "servicenow_denied_operations": {"change_request.update": [key]},
    }
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    try:
        failed, error = call(world, "approve_change", change_id=key)
        assert not error and failed["success"] is False
        assert (
            call(world, "get_change_request_details", change_id=key)[0][
                "change_request"
            ]["state"]
            == "assess"
        )
        assert world.episode is not None
        stored = world.episode.db.connection.execute(
            "SELECT data FROM servicenow_records WHERE table_name='sysapproval_approver'"
        ).fetchone()[0]
        assert json.loads(stored)["state"] == "approved"
    finally:
        world.close()


def test_deleted_seeded_record_id_is_never_reissued():
    raw = load_scenario().model_dump() | {
        "servicenow_records": [
            {
                "table": "sys_script_include",
                "sys_id": "00000000000000000000000000000001",
                "data": {"name": "Seed", "script": "inert"},
            }
        ]
    }
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    try:
        assert call(world, "delete_script_include", script_include_id="Seed")[0][
            "success"
        ]
        created = call(world, "create_script_include", name="New", script="inert")[0]
        assert created["script_include_id"] == "00000000000000000000000000000002"
    finally:
        world.close()
