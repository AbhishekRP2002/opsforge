"""Real SQLite relationship behavior, independent literal expectations."""

import importlib
import importlib.util
import json

import pytest
from itops_env.server.core.scenarios import Scenario

from .test_jira_core import database, fixture_data
from .test_jira_core import issue_fixture as core_issue_fixture


def issue_fixture(identity=1, key="OPS-1", **updates):
    return core_issue_fixture(identity, key, **updates)


def call(db, tool, **args):
    clock = args.pop("clock", 20)
    modules = ["jira_core", "jira_relations", "jira_workflow", "jira_agile"]
    handlers = {}
    for module in modules:
        if importlib.util.find_spec("itops_env.server.services." + module):
            handlers.update(
                importlib.import_module("itops_env.server.services." + module).HANDLERS
            )
    assert tool in handlers, f"Missing relationship behavior: {tool}"
    with db.connection:
        return handlers[tool](db, args, 1, clock)


def ok(db, tool, **args):
    value, error = call(db, tool, **args)
    assert not error, value
    return value


def test_watcher_identity_idempotency_and_removal():
    with database(jira_issues=[issue_fixture()]) as db:
        for _ in range(2):
            assert ok(db, "jira_add_watcher", issue_key="OPS-1", user_identifier="u1")[
                "success"
            ]
        watchers = ok(db, "jira_get_issue_watchers", issue_key="OPS-1")
        assert watchers["watcher_count"] == 1
        assert watchers["is_watching"] is True
        assert watchers["watchers"][0]["display_name"] == "Ada"
        assert call(db, "jira_add_watcher", issue_key="OPS-1", user_identifier="ada")[1]
        assert call(db, "jira_remove_watcher", issue_key="OPS-1", username="ada")[1]
        assert ok(db, "jira_remove_watcher", issue_key="OPS-1", account_id="u1")[
            "success"
        ]
        assert (
            ok(db, "jira_get_issue_watchers", issue_key="OPS-1")["watcher_count"] == 0
        )
        assert call(db, "jira_get_issue_watchers", issue_key="OPS-9")[1]
    with database(jira_edition="server", jira_issues=[issue_fixture()]) as db:
        ok(db, "jira_add_watcher", issue_key="OPS-1", user_identifier="ada")
        assert call(db, "jira_add_watcher", issue_key="OPS-1", user_identifier="u1")[1]
        ok(db, "jira_remove_watcher", issue_key="OPS-1", username="ada")


def test_comment_visibility_and_nonmutation():
    with database(jira_issues=[issue_fixture()]) as db:
        added = ok(
            db,
            "jira_add_comment",
            issue_key="OPS-1",
            body="First",
            visibility='{"type":"group","value":"staff"}',
        )
        edited = ok(
            db,
            "jira_edit_comment",
            issue_key="OPS-1",
            comment_id=added["id"],
            body="Revised",
        )
        assert edited["body"] == "Revised"
        assert call(
            db,
            "jira_edit_comment",
            issue_key="OPS-9",
            comment_id=added["id"],
            body="wrong",
        )[1]
        for invalid in (
            "[]",
            '{"type":[],"value":"staff"}',
            '{"type":"role","value":{}}',
        ):
            assert call(
                db,
                "jira_add_comment",
                issue_key="OPS-1",
                body="bad",
                visibility=invalid,
            )[1]
        comments = ok(db, "jira_get_issue", issue_key="OPS-1", include="comments")[
            "comments"
        ]
        assert len(comments) == 1
        assert comments[0]["body"] == "Revised"
        assert comments[0]["visibility"] == {"type": "group", "value": "staff"}
        assert (
            ok(
                db,
                "jira_get_issue",
                issue_key="OPS-1",
                include="comment",
                comment_limit=0,
            )["comments"]
            == []
        )


def test_worklog_duration_estimates_and_readback():
    with database(jira_issues=[issue_fixture()]) as db:
        result = ok(
            db,
            "jira_add_worklog",
            issue_key="OPS-1",
            time_spent="1h 30m",
            original_estimate="1d",
            remaining_estimate="2h",
            comment="Repair",
        )
        assert result["worklog"]["time_spent_seconds"] == 5400
        assert result["worklog"]["original_estimate_updated"] is True
        logs = ok(db, "jira_get_worklog", issue_key="OPS-1")["worklogs"]
        assert len(logs) == 1 and logs[0]["comment"] == "Repair"
        assert logs[0]["author"] == "Ada"
        for value in ("NaN", "inf", "-2h", "0s", "junk", "9" * 5000 + "h"):
            assert call(db, "jira_add_worklog", issue_key="OPS-1", time_spent=value)[1]
        for key, value in (
            ("remaining_estimate", "NaN"),
            ("original_estimate", "-1h"),
            ("started", "bad"),
        ):
            assert call(
                db,
                "jira_add_worklog",
                issue_key="OPS-1",
                time_spent="1h",
                **{key: value},
            )[1]
        assert len(ok(db, "jira_get_worklog", issue_key="OPS-1")["worklogs"]) == 1
        tracking = ok(db, "jira_get_issue", issue_key="OPS-1", fields="timetracking")[
            "timetracking"
        ]
        assert tracking == {
            "originalEstimateSeconds": 86400,
            "remainingEstimateSeconds": 7200,
            "timeSpentSeconds": 5400,
        }
        assert call(db, "jira_get_worklog", issue_key="OPS-9")[1]


def test_request_comment_public_guards():
    assert "jira_request_issue_ids" in Scenario.model_fields
    with database(
        jira_issues=[issue_fixture()],
        jira_request_issue_ids=[1],
        jira_internal_only_projects=["OPS"],
    ) as db:
        assert call(db, "jira_add_comment", issue_key="OPS-1", body="Public")[1]
        assert call(
            db, "jira_add_comment", issue_key="OPS-1", body="Public", public=True
        )[1]
        internal = ok(
            db, "jira_add_comment", issue_key="OPS-1", body="Internal", public=False
        )
        assert internal["public"] is False
        assert call(
            db,
            "jira_add_comment",
            issue_key="OPS-1",
            body="bad",
            public=False,
            visibility='{"type":"role","value":"staff"}',
        )[1]
        ok(
            db,
            "jira_edit_comment",
            issue_key="OPS-1",
            comment_id=internal["id"],
            body="Edited",
        )
    with database(jira_issues=[issue_fixture()]) as db:
        # The source server treats false as omitted outside guarded projects.
        assert "public" not in ok(
            db, "jira_add_comment", issue_key="OPS-1", body="Ordinary", public=False
        )
        assert call(
            db, "jira_add_comment", issue_key="OPS-1", body="not request", public=True
        )[1]


def test_add_comment_accepts_exactly_one_alias_without_mutation():
    with database(jira_issues=[issue_fixture()]) as db:
        args = {"issue_key": "OPS-1", "comment": "Alias"}
        saved = dict(args)
        assert ok(db, "jira_add_comment", **args)["body"] == "Alias"
        assert args == saved
        for bad in (
            {},
            {"comment": 5},
            {"body": []},
            {"body": "valid", "comment": []},
            {"body": "Body", "comment": "Alias"},
        ):
            assert call(db, "jira_add_comment", issue_key="OPS-1", **bad)[1]
        assert call(
            db,
            "jira_edit_comment",
            issue_key="OPS-1",
            comment_id="1",
            comment="unsupported",
        )[1]


@pytest.mark.parametrize(
    "updates",
    [
        {"jira_request_issue_ids": [9]},
        {"jira_request_issue_ids": [True]},
        {"jira_internal_only_projects": ["BAD"]},
        {"jira_watchers": [{"issue_id": 1, "user_id": []}]},
        {
            "jira_comments": [
                {
                    "id": 1,
                    "issue_id": 9,
                    "body": "bad",
                    "author_id": "u1",
                    "created": "2026-01-01T00:00:00Z",
                    "updated": "2026-01-01T00:00:00Z",
                }
            ]
        },
    ],
)
def test_activity_fixture_references_rejected(updates):
    assert "jira_comments" in Scenario.model_fields
    with pytest.raises(ValueError):
        Scenario.model_validate(fixture_data(jira_issues=[issue_fixture()], **updates))


def workflow_fixtures():
    projects = fixture_data()["jira_projects"]
    for p in projects:
        p["issue_types"].append({"id": "2", "name": "Epic"})
        p["statuses"] = [
            {
                "id": "1",
                "name": "Open",
                "category": {"id": "2", "key": "new", "name": "To Do"},
            },
            {
                "id": "2",
                "name": "Doing",
                "category": {"id": "4", "key": "indeterminate", "name": "In Progress"},
            },
            {
                "id": "3",
                "name": "Done",
                "category": {"id": "3", "key": "done", "name": "Done"},
            },
        ]
    return {
        "jira_projects": projects,
        "jira_issues": [issue_fixture(), issue_fixture(2, "OPS-2")],
        "jira_link_types": [
            {
                "id": "1",
                "name": "Blocks",
                "inward": "is blocked by",
                "outward": "blocks",
            }
        ],
        "jira_transitions": [
            {
                "id": "11",
                "name": "Start",
                "project_key": "OPS",
                "from_status": "Open",
                "to_status": "Doing",
            },
            {
                "id": "21",
                "name": "Finish",
                "project_key": "OPS",
                "from_status": "Doing",
                "to_status": "Done",
            },
        ],
    }


def test_directed_links_remote_links_and_selected_removal():
    assert "jira_link_types" in Scenario.model_fields
    with database(**workflow_fixtures()) as db:
        assert (
            ok(db, "jira_get_link_types", name_filter="BLO")[0]["inward"]
            == "is blocked by"
        )
        assert call(db, "jira_get_link_types", name_filter=[])[1]
        ok(
            db,
            "jira_create_issue_link",
            link_type="Blocks",
            inward_issue_key="OPS-1",
            outward_issue_key="OPS-2",
            comment="Dependency",
        )
        ok(
            db,
            "jira_create_remote_issue_link",
            issue_key="OPS-1",
            url="https://example.test/doc",
            title="Runbook",
            summary="Steps",
        )
        a = ok(
            db,
            "jira_get_issue",
            issue_key="OPS-1",
            fields="issuelinks",
            include="remote_links,comments",
        )
        b = ok(db, "jira_get_issue", issue_key="OPS-2", fields="issuelinks")
        assert a["issuelinks"][0]["outward_issue"]["key"] == "OPS-2"
        assert b["issuelinks"][0]["inward_issue"]["key"] == "OPS-1"
        assert a["remote_links"][0]["object"]["title"] == "Runbook"
        assert a["comments"][0]["body"] == "Dependency"
        for tool, args in [
            (
                "jira_create_issue_link",
                {
                    "link_type": "Bad",
                    "inward_issue_key": "OPS-1",
                    "outward_issue_key": "OPS-2",
                },
            ),
            (
                "jira_create_issue_link",
                {
                    "link_type": "Blocks",
                    "inward_issue_key": "OPS-1",
                    "outward_issue_key": "OPS-9",
                },
            ),
            (
                "jira_create_remote_issue_link",
                {"issue_key": "OPS-9", "url": "x", "title": "bad"},
            ),
            (
                "jira_create_remote_issue_link",
                {"issue_key": "OPS-1", "url": "", "title": "bad"},
            ),
            ("jira_remove_issue_link", {"link_id": "999"}),
        ]:
            assert call(db, tool, **args)[1]
        ok(db, "jira_remove_issue_link", link_id=a["issuelinks"][0]["id"])
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-2", fields="issuelinks")[
                "issuelinks"
            ]
            == []
        )
        assert (
            len(
                ok(db, "jira_get_issue", issue_key="OPS-1", include="remote_links")[
                    "remote_links"
                ]
            )
            == 1
        )


def test_epic_parent_cycles_move_and_delete_relationships():
    assert "jira_link_types" in Scenario.model_fields
    with database(**workflow_fixtures()) as db:
        epic = ok(
            db,
            "jira_create_issue",
            project_key="OPS",
            summary="Epic",
            issue_type="Epic",
        )["issue"]
        ok(db, "jira_link_to_epic", issue_key="OPS-1", epic_key=epic["key"])
        assert call(
            db, "jira_link_to_epic", issue_key=epic["key"], epic_key=epic["key"]
        )[1]
        assert call(db, "jira_link_to_epic", issue_key="OPS-2", epic_key="OPS-1")[1]
        assert call(db, "jira_link_to_epic", issue_key="OPS-9", epic_key=epic["key"])[1]
        ok(db, "jira_add_watcher", issue_key="OPS-1", user_identifier="u1")
        ok(db, "jira_add_comment", issue_key="OPS-1", body="Keep")
        ok(db, "jira_add_worklog", issue_key="OPS-1", time_spent="60s")
        ok(
            db,
            "jira_create_issue_link",
            link_type="Blocks",
            inward_issue_key="OPS-1",
            outward_issue_key="OPS-2",
        )
        ok(
            db,
            "jira_create_remote_issue_link",
            issue_key="OPS-1",
            url="https://example.test",
            title="Keep",
        )
        ok(db, "jira_move_issue", issue_key="OPS-1", target_project_key="DEV")
        moved = ok(
            db, "jira_get_issue", issue_key="DEV-1", fields="*all", include="all"
        )
        assert moved["id"] == "1" and moved["parent"]["key"] == "OPS-3"
        assert moved["watchers"]["watcher_count"] == 1
        assert moved["comments"][0]["body"] == "Keep"
        assert moved["worklogs"][0]["time_spent_seconds"] == 60
        assert len(moved["remote_links"]) == 1
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-2", fields="issuelinks")[
                "issuelinks"
            ][0]["inward_issue"]["key"]
            == "DEV-1"
        )
        ok(db, "jira_delete_issue", issue_key="DEV-1")
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-2", fields="issuelinks")[
                "issuelinks"
            ]
            == []
        )
        assert (
            db.connection.execute("SELECT count(*) FROM jira_comments").fetchone()[0]
            == 0
        )


def test_allowed_transition_changes_status_fields_history_and_author():
    assert "jira_transitions" in Scenario.model_fields
    with database(**workflow_fixtures()) as db:
        assert ok(db, "jira_get_transitions", issue_key="OPS-1") == [
            {"id": "11", "name": "Start", "to_status": "Doing"}
        ]
        assert call(db, "jira_get_transitions", issue_key="OPS-9")[1]
        assert call(db, "jira_transition_issue", issue_key="OPS-1", transition_id="21")[
            1
        ]
        changed = ok(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="sTart",
            clock=30,
            fields='{"summary":"Working"}',
            comment="Started",
        )
        assert changed["issue"]["status"]["name"] == "Doing"
        assert changed["issue"]["summary"] == "Working"
        assert call(
            db, "jira_transition_issue", issue_key="OPS-1", transition_id="11", clock=40
        )[1]
        assert call(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="21",
            clock=40,
            fields='{"status":[]}',
        )[1]
        done = ok(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="21",
            clock=60,
            fields='{"resolution":{"name":"Fixed"}}',
        )
        assert done["issue"]["status"]["name"] == "Done"
        history = ok(db, "jira_get_issue", issue_key="OPS-1", include="changelog")[
            "changelogs"
        ]
        assert len(history) == 2 and history[0]["author"]["display_name"] == "Ada"
        visits = [
            dict(r)
            for r in db.connection.execute(
                "SELECT * FROM jira_status_history WHERE issue_id=1 ORDER BY id"
            )
        ]
        assert [json.loads(r["status"])["name"] for r in visits] == [
            "Open",
            "Doing",
            "Done",
        ]
        assert json.loads(visits[1]["status"])["category"]["key"] == "indeterminate"
        assert (
            visits[0]["exited"] == visits[1]["entered"] == "2026-01-01T00:00:30+00:00"
        )
        assert visits[1]["exited"] == "2026-01-01T00:01:00+00:00"


def test_worklog_automatically_reduces_existing_remaining_estimate():
    with database(jira_issues=[issue_fixture()]) as db:
        ok(
            db,
            "jira_add_worklog",
            issue_key="OPS-1",
            time_spent="1h",
            remaining_estimate="2h",
        )
        ok(db, "jira_add_worklog", issue_key="OPS-1", time_spent="30m", clock=30)
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-1", fields="timetracking")[
                "timetracking"
            ]["remainingEstimateSeconds"]
            == 5400
        )


def test_activity_fixture_chronology_cannot_exceed_issue_updated():
    with pytest.raises(ValueError):
        Scenario.model_validate(
            fixture_data(
                jira_issues=[issue_fixture()],
                jira_comments=[
                    {
                        "id": 1,
                        "issue_id": 1,
                        "author_id": "u1",
                        "body": "future",
                        "created": "2026-01-02T00:00:00Z",
                        "updated": "2026-01-02T00:00:00Z",
                    }
                ],
            )
        )


def test_visibility_unknown_nested_values_rejected_before_mutation():
    with database(jira_issues=[issue_fixture()]) as db:
        assert call(
            db,
            "jira_add_comment",
            issue_key="OPS-1",
            body="bad",
            visibility='{"type":"group","value":"staff","unexpected":{"x":NaN}}',
        )[1]
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-1", include="comments")["comments"]
            == []
        )


def test_status_id_fixture_resolves_allowed_transition():
    fixtures = workflow_fixtures()
    fixtures["jira_issues"][0]["data"]["status"] = "1"
    with database(**fixtures) as db:
        assert ok(db, "jira_get_transitions", issue_key="OPS-1")[0]["name"] == "Start"


def test_fixture_history_cannot_have_entry_after_issue_updated():
    fixtures = workflow_fixtures()
    first = fixtures["jira_projects"][0]["statuses"][0]
    fixtures["jira_status_history"] = [
        {
            "issue_id": 1,
            "status": first,
            "entered": "2026-01-01T00:00:00Z",
            "exited": "2026-01-02T00:00:00Z",
        },
        {"issue_id": 1, "status": first, "entered": "2026-01-02T00:00:00Z"},
    ]
    with pytest.raises(ValueError):
        Scenario.model_validate(fixture_data(**fixtures))


def test_nonempty_activity_link_and_history_fixtures_use_exact_user_ids():
    fixtures = workflow_fixtures()
    fixtures["jira_issues"][0]["data"].update(
        status="Doing", updated="2026-01-01T00:00:10+00:00"
    )
    users = fixture_data()["jira_users"]
    users.append(
        {
            "id": "u2",
            "name": "u1",
            "display_name": "Other",
            "email": "other@test",
            "active": True,
            "project_keys": ["OPS"],
        }
    )
    fixtures.update(
        jira_users=users,
        jira_request_issue_ids=[1],
        jira_internal_only_projects=["OPS"],
        jira_watchers=[{"issue_id": 1, "user_id": "u1"}],
        jira_comments=[
            {
                "id": 7,
                "issue_id": 1,
                "author_id": "u1",
                "body": "Seed comment",
                "created": "2026-01-01T00:00:05Z",
                "updated": "2026-01-01T00:00:05Z",
                "public": True,
            }
        ],
        jira_worklogs=[
            {
                "id": 8,
                "issue_id": 1,
                "author_id": "u1",
                "comment": "Seed work",
                "created": "2026-01-01T00:00:05Z",
                "updated": "2026-01-01T00:00:05Z",
                "started": "2026-01-01T00:00:00Z",
                "time_spent": "30m",
            }
        ],
        jira_issue_links=[{"id": 9, "type_id": "1", "inward_id": 1, "outward_id": 2}],
        jira_remote_links=[
            {
                "id": 10,
                "issue_id": 1,
                "object": {
                    "url": "https://example.test",
                    "title": "Seed link",
                    "icon": {"url16x16": "https://example.test/i.png", "title": "I"},
                },
            }
        ],
        jira_status_history=[
            {
                "issue_id": 1,
                "status": fixtures["jira_projects"][0]["statuses"][0],
                "entered": "2026-01-01T00:00:00Z",
                "exited": "2026-01-01T00:00:10Z",
            },
            {
                "issue_id": 1,
                "status": fixtures["jira_projects"][0]["statuses"][1],
                "entered": "2026-01-01T00:00:10Z",
                "author_id": "u1",
                "transition_id": "11",
            },
        ],
    )
    with database(**fixtures) as db:
        item = ok(db, "jira_get_issue", issue_key="OPS-1", fields="*all", include="all")
        assert item["comments"][0]["author"] == "Ada"
        assert item["worklogs"][0]["time_spent_seconds"] == 1800
        assert item["watchers"]["watchers"][0]["display_name"] == "Ada"
        assert item["changelogs"][0]["author"]["display_name"] == "Ada"
        assert item["issuelinks"][0]["id"] == "9"
        assert item["remote_links"][0]["object"]["title"] == "Seed link"
        assert call(
            db, "jira_edit_comment", issue_key="OPS-1", comment_id="7", body="forbidden"
        )[1]
        assert call(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="21",
            comment="forbidden",
        )[1]
        assert call(
            db,
            "jira_create_issue_link",
            link_type="Blocks",
            inward_issue_key="OPS-1",
            outward_issue_key="OPS-2",
            comment="forbidden",
        )[1]
        assert call(
            db,
            "jira_edit_comment",
            issue_key="OPS-2",
            comment_id="7",
            body="wrong parent",
        )[1]
        assert (
            ok(
                db, "jira_add_comment", issue_key="OPS-2", body="ordinary", public=False
            )["body"]
            == "ordinary"
        )
        assert (
            ok(
                db, "jira_add_comment", issue_key="OPS-1", body="internal", public=False
            )["author"]
            == "Ada"
        )


@pytest.mark.parametrize(
    "tool,args",
    [
        ("jira_add_watcher", {"issue_key": "OPS-1", "user_identifier": "u1"}),
        ("jira_remove_watcher", {"issue_key": "OPS-1", "account_id": "u1"}),
        ("jira_add_comment", {"issue_key": "OPS-1", "body": "no"}),
        ("jira_edit_comment", {"issue_key": "OPS-1", "comment_id": "1", "body": "no"}),
        ("jira_add_worklog", {"issue_key": "OPS-1", "time_spent": "1h"}),
        ("jira_link_to_epic", {"issue_key": "OPS-1", "epic_key": "OPS-2"}),
        (
            "jira_create_issue_link",
            {
                "link_type": "Blocks",
                "inward_issue_key": "OPS-1",
                "outward_issue_key": "OPS-2",
            },
        ),
        (
            "jira_create_remote_issue_link",
            {"issue_key": "OPS-1", "url": "https://x.test", "title": "no"},
        ),
        ("jira_remove_issue_link", {"link_id": "1"}),
        ("jira_transition_issue", {"issue_key": "OPS-1", "transition_id": "11"}),
        (
            "jira_create_sprint",
            {
                "board_id": "1",
                "name": "no",
                "start_date": "2026-01-02T00:00:00Z",
                "end_date": "2026-01-03T00:00:00Z",
            },
        ),
        ("jira_update_sprint", {"sprint_id": "10", "name": "no"}),
        ("jira_add_issues_to_sprint", {"sprint_id": "10", "issue_keys": "OPS-2"}),
        ("jira_move_issues_to_backlog", {"issue_keys": "OPS-1"}),
    ],
)
def test_all_relationship_writes_respect_read_only(tool, args):
    from .test_jira_agile import agile_fixtures

    with database(**agile_fixtures(), jira_read_only=True) as db:
        value, error = call(db, tool, **args)
        assert error and "read-only" in value["error"]


@pytest.mark.parametrize(
    "updates",
    [
        {
            "jira_issue_links": [
                {"id": 1, "type_id": [], "inward_id": 1, "outward_id": 2}
            ]
        },
        {
            "jira_remote_links": [
                {
                    "id": 1,
                    "issue_id": 1,
                    "object": {"url": "x", "title": "x", "icon": []},
                }
            ]
        },
        {
            "jira_transitions": [
                {
                    "id": "1",
                    "name": "X",
                    "project_key": "OPS",
                    "from_status": [],
                    "to_status": "Doing",
                }
            ]
        },
        {
            "jira_worklogs": [
                {
                    "id": 1,
                    "issue_id": 1,
                    "author_id": "u1",
                    "created": "2026-01-01T00:00:00Z",
                    "updated": "2026-01-01T00:00:00Z",
                    "started": {},
                    "time_spent": "1h",
                }
            ]
        },
    ],
)
def test_nested_workflow_fixture_references_are_deliberate_errors(updates):
    with pytest.raises(ValueError):
        Scenario.model_validate(fixture_data(**(workflow_fixtures() | updates)))


def test_relationship_helpers_do_not_commit_outer_transaction():
    from itops_env.server.services import jira_relations as activity
    from itops_env.server.services import jira_store as store
    from itops_env.server.services import jira_workflow as workflow

    with database(**workflow_fixtures()) as db:
        db.connection.execute("BEGIN")
        record = store.issue(db, "OPS-1")
        activity.add_comment_record(db, record, "rolled back", 20)
        activity.add_worklog_record(db, record, {"time_spent": "1h"}, 20)
        workflow.transition_record(db, record, "11", 20)
        db.connection.rollback()
        item = ok(db, "jira_get_issue", issue_key="OPS-1", include="all")
        assert item["status"]["name"] == "Open"
        assert item["comments"] == item["worklogs"] == item["changelogs"] == []


@pytest.mark.parametrize(
    "label", ["sprint", "timetracking", "resolution", "resolutiondate"]
)
def test_custom_display_names_cannot_shadow_new_relationship_fields(label):
    fixtures = workflow_fixtures()
    fixtures["jira_projects"][0]["field_names"] = {"customfield_1": label}
    with pytest.raises(ValueError):
        Scenario.model_validate(fixture_data(**fixtures))


def test_nonfinite_new_fixture_metadata_rejected_before_sqlite_seed():
    fixtures = workflow_fixtures()
    fixtures["jira_link_types"][0]["extra"] = float("nan")
    with pytest.raises(ValueError):
        Scenario.model_validate(fixture_data(**fixtures))


def test_epic_fixture_type_id_is_resolved_before_parent_link():
    fixtures = workflow_fixtures()
    fixtures["jira_issues"][1]["data"]["issue_type"] = "2"
    with database(**fixtures) as db:
        assert (
            ok(db, "jira_link_to_epic", issue_key="OPS-1", epic_key="OPS-2")["issue"][
                "parent"
            ]["key"]
            == "OPS-2"
        )


@pytest.mark.parametrize("active,projects", [(False, ["OPS"]), (True, ["DEV"])])
@pytest.mark.parametrize("assignment", ["bob", '{"accountId":"u2"}'])
def test_transition_rejects_resolved_ineligible_assignee_without_mutation(
    active, projects, assignment
):
    users = fixture_data()["jira_users"]
    users.append(
        {
            "id": "u2",
            "name": "bob",
            "display_name": "Bob",
            "email": "bob@test",
            "active": active,
            "project_keys": projects,
        }
    )
    with database(**workflow_fixtures(), jira_users=users) as db:
        before = ok(
            db, "jira_get_issue", issue_key="OPS-1", fields="*all", include="all"
        )
        visits = [
            tuple(row)
            for row in db.connection.execute(
                "SELECT * FROM jira_status_history ORDER BY id"
            )
        ]
        value, error = call(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="11",
            fields=json.dumps({"assignee": assignment, "summary": "Must not change"}),
            comment="Must not append",
        )
        assert error and "not assignable" in value["error"]
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-1", fields="*all", include="all")
            == before
        )
        assert [
            tuple(row)
            for row in db.connection.execute(
                "SELECT * FROM jira_status_history ORDER BY id"
            )
        ] == visits


@pytest.mark.parametrize(
    "edition,field,fallback",
    [("cloud", "accountId", "account_id"), ("server", "name", "username")],
)
@pytest.mark.parametrize("invalid", [[], {}, False, 0, None, "", ["u1"]])
@pytest.mark.parametrize("with_fallback", [False, True])
def test_transition_invalid_nested_assignee_preserves_issue_history_comments(
    edition, field, fallback, invalid, with_fallback
):
    nested = {field: invalid}
    if with_fallback:
        nested[fallback] = "u1" if edition == "cloud" else "ada"
    with database(**workflow_fixtures(), jira_edition=edition) as db:
        before = ok(
            db, "jira_get_issue", issue_key="OPS-1", fields="*all", include="all"
        )
        history = [
            tuple(row)
            for row in db.connection.execute(
                "SELECT * FROM jira_status_history ORDER BY id"
            )
        ]
        value, error = call(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="11",
            fields=json.dumps(
                {"assignee": json.dumps(nested), "summary": "Must not change"}
            ),
            comment="Must not append",
        )
        assert error and value["error"]
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-1", fields="*all", include="all")
            == before
        )
        assert [
            tuple(row)
            for row in db.connection.execute(
                "SELECT * FROM jira_status_history ORDER BY id"
            )
        ] == history


@pytest.mark.parametrize(
    "assignment", ["{", '{"accountId":}', '{"accountId":"accountid:"}']
)
def test_transition_malformed_assignee_json_or_identifier_is_not_unknown(assignment):
    with database(**workflow_fixtures()) as db:
        before = ok(
            db, "jira_get_issue", issue_key="OPS-1", fields="*all", include="all"
        )
        history = [
            tuple(row)
            for row in db.connection.execute(
                "SELECT * FROM jira_status_history ORDER BY id"
            )
        ]
        assert call(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="11",
            fields=json.dumps({"assignee": assignment}),
            comment="Must not append",
        )[1]
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-1", fields="*all", include="all")
            == before
        )
        assert [
            tuple(row)
            for row in db.connection.execute(
                "SELECT * FROM jira_status_history ORDER BY id"
            )
        ] == history


@pytest.mark.parametrize("assignment", ["u1", '{"accountId":"u1"}'])
def test_transition_ambiguous_identity_retains_source_skip(assignment):
    users = fixture_data()["jira_users"]
    users.append(
        {
            "id": "u2",
            "name": "u1",
            "display_name": "Other",
            "email": "other@test",
            "active": True,
            "project_keys": ["OPS"],
        }
    )
    with database(**workflow_fixtures(), jira_users=users) as db:
        result = ok(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="11",
            fields=json.dumps({"assignee": assignment}),
            comment="Continue",
        )
        assert result["issue"]["status"]["name"] == "Doing"
        assert result["issue"]["assignee"]["account_id"] == "u1"
        assert (
            ok(db, "jira_get_issue", issue_key="OPS-1", include="comments")["comments"][
                0
            ]["body"]
            == "Continue"
        )


def test_transition_unknown_string_assignee_still_skips_only_assignment():
    with database(**workflow_fixtures()) as db:
        result = ok(
            db,
            "jira_transition_issue",
            issue_key="OPS-1",
            transition_id="11",
            fields='{"assignee":"unknown-user","summary":"Proceed"}',
        )
        assert result["issue"]["status"]["name"] == "Doing"
        assert result["issue"]["summary"] == "Proceed"
        assert result["issue"]["assignee"]["account_id"] == "u1"
        assert (
            len(
                ok(db, "jira_get_issue", issue_key="OPS-1", include="changelog")[
                    "changelogs"
                ]
            )
            == 1
        )
