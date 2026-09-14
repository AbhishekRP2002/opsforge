"""Finite agile memberships and lifecycle against actual SQLite."""

import pytest
from itops_env.server.core.scenarios import Scenario

from .test_jira_core import database, fixture_data
from .test_jira_relations import call, ok, workflow_fixtures


def agile_fixtures():
    return workflow_fixtures() | {
        "jira_boards": [
            {
                "id": "1",
                "name": "Delivery",
                "type": "scrum",
                "project_keys": ["OPS", "DEV"],
            },
            {"id": "2", "name": "Support", "type": "kanban", "project_keys": ["OPS"]},
        ],
        "jira_sprints": [
            {
                "id": "10",
                "board_id": "1",
                "name": "First",
                "state": "future",
                "start_date": "2026-01-02T00:00:00Z",
                "end_date": "2026-01-16T00:00:00Z",
            }
        ],
        "jira_sprint_issues": [{"issue_id": 1, "sprint_id": "10"}],
    }


def test_nonempty_board_sprint_queries_and_paging():
    assert "jira_boards" in Scenario.model_fields
    with database(**agile_fixtures()) as db:
        assert ok(
            db,
            "jira_get_agile_boards",
            board_name="lIv",
            project_key="OPS",
            board_type="scrum",
        ) == [{"id": "1", "name": "Delivery", "type": "scrum"}]
        assert ok(db, "jira_get_agile_boards", start_at=1, limit=1)[0]["id"] == "2"
        assert (
            ok(
                db,
                "jira_get_board_issues",
                board_id="1",
                jql="project=OPS",
                start_at=1,
                limit=1,
            )["issues"][0]["key"]
            == "OPS-2"
        )
        assert (
            ok(db, "jira_get_sprints_from_board", board_id="1", state="future")[0][
                "name"
            ]
            == "First"
        )
        assert (
            ok(db, "jira_get_sprint_issues", sprint_id="10")["issues"][0]["key"]
            == "OPS-1"
        )
        assert (
            ok(db, "jira_search", jql='sprint="First"', fields="sprint")["issues"][0][
                "sprint"
            ]["id"]
            == "10"
        )
        for tool, args in [
            ("jira_get_agile_boards", {"board_type": "bad"}),
            ("jira_get_agile_boards", {"project_key": "BAD"}),
            ("jira_get_board_issues", {"board_id": "99", "jql": "project=OPS"}),
            ("jira_get_board_issues", {"board_id": "1", "jql": "status!=Done"}),
            ("jira_get_sprints_from_board", {"board_id": "2"}),
            ("jira_get_sprints_from_board", {"board_id": "1", "state": "bad"}),
            ("jira_get_sprint_issues", {"sprint_id": "99"}),
            ("jira_get_sprint_issues", {"sprint_id": "10 OR project=OPS"}),
            ("jira_search", {"jql": "sprint=999"}),
        ]:
            assert call(db, tool, **args)[1]


def test_create_update_sprint_dates_lifecycle_and_literal_error():
    assert "jira_boards" in Scenario.model_fields
    with database(**agile_fixtures()) as db:
        sprint = ok(
            db,
            "jira_create_sprint",
            board_id="1",
            name="Next",
            start_date="2026-02-01T00:00:00Z",
            end_date="2026-02-14T00:00:00Z",
            goal="Ship",
        )
        assert sprint["name"] == "Next" and sprint["state"] == "future"
        assert ok(db, "jira_update_sprint", sprint_id=sprint["id"]) == sprint
        assert (
            ok(db, "jira_update_sprint", sprint_id=sprint["id"], state="active")[
                "state"
            ]
            == "active"
        )
        assert (
            ok(db, "jira_update_sprint", sprint_id=sprint["id"], state="closed")[
                "state"
            ]
            == "closed"
        )
        for args in (
            {"sprint_id": sprint["id"], "state": "future"},
            {"sprint_id": "99", "name": "bad"},
            {"sprint_id": "10", "state": "bad"},
            {"sprint_id": "10", "end_date": "2025-01-01"},
        ):
            value, error = call(db, "jira_update_sprint", **args)
            assert error is False
            assert value == {
                "error": f"Failed to update sprint {args['sprint_id']}. Check logs for details."
            }
        for args in (
            {"board_id": "2"},
            {"start_date": "2025-01-01T00:00:00Z"},
            {"end_date": "2026-01-01T00:00:00Z"},
            {"start_date": "bad"},
        ):
            assert call(
                db,
                "jira_create_sprint",
                **(
                    {
                        "board_id": "1",
                        "name": "Bad",
                        "start_date": "2026-02-01T00:00:00Z",
                        "end_date": "2026-02-14T00:00:00Z",
                    }
                    | args
                ),
            )[1]


def test_atomic_assignment_backlog_and_move_delete_identity():
    assert "jira_boards" in Scenario.model_fields
    with database(**agile_fixtures()) as db:
        assert call(
            db, "jira_add_issues_to_sprint", sprint_id="10", issue_keys="OPS-2,OPS-9"
        )[1]
        assert [
            i["key"] for i in ok(db, "jira_get_sprint_issues", sprint_id="10")["issues"]
        ] == ["OPS-1"]
        ok(db, "jira_add_issues_to_sprint", sprint_id="10", issue_keys=" OPS-1, OPS-2 ")
        assert call(db, "jira_move_issues_to_backlog", issue_keys="OPS-1,OPS-9")[1]
        assert len(ok(db, "jira_get_sprint_issues", sprint_id="10")["issues"]) == 2
        ok(db, "jira_move_issue", issue_key="OPS-1", target_project_key="DEV")
        assert [
            i["key"] for i in ok(db, "jira_get_sprint_issues", sprint_id="10")["issues"]
        ] == ["DEV-1", "OPS-2"]
        ok(db, "jira_move_issues_to_backlog", issue_keys="OPS-2")
        assert len(ok(db, "jira_get_sprint_issues", sprint_id="10")["issues"]) == 1
        ok(db, "jira_delete_issue", issue_key="DEV-1")
        assert ok(db, "jira_get_sprint_issues", sprint_id="10")["issues"] == []
        assert call(
            db, "jira_add_issues_to_sprint", sprint_id="99", issue_keys="OPS-2"
        )[1]
        assert call(db, "jira_move_issues_to_backlog", issue_keys=",,")[1]


def test_move_rejects_ineligible_sprint_and_watcher_before_key_allocation():
    assert "jira_boards" in Scenario.model_fields
    fixtures = agile_fixtures()
    fixtures["jira_boards"][0]["project_keys"] = ["OPS"]
    with database(**fixtures) as db:
        assert call(db, "jira_move_issue", issue_key="OPS-1", target_project_key="DEV")[
            1
        ]
        assert (
            ok(
                db,
                "jira_create_issue",
                project_key="DEV",
                summary="First",
                issue_type="Task",
            )["issue"]["key"]
            == "DEV-1"
        )
    users = fixture_data()["jira_users"]
    users.append(
        {
            "id": "u2",
            "name": "bob",
            "display_name": "Bob",
            "email": "bob@test",
            "active": True,
            "project_keys": ["OPS"],
        }
    )
    with database(
        **(
            agile_fixtures()
            | {"jira_users": users, "jira_watchers": [{"issue_id": 1, "user_id": "u2"}]}
        )
    ) as db:
        assert call(db, "jira_move_issue", issue_key="OPS-1", target_project_key="DEV")[
            1
        ]


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "jira_boards",
            [{"id": "1", "name": "Bad", "type": "scrum", "project_keys": [{}]}],
        ),
        (
            "jira_sprints",
            [
                {
                    "id": "1",
                    "name": "Bad",
                    "board_id": [],
                    "state": "future",
                    "start_date": "bad",
                    "end_date": "bad",
                }
            ],
        ),
        ("jira_sprint_issues", [{"issue_id": 1, "sprint_id": {}}]),
        ("jira_sprint_issues", [{"issue_id": True, "sprint_id": "10"}]),
    ],
)
def test_nested_agile_fixture_values_are_deliberate_errors(field, value):
    assert "jira_boards" in Scenario.model_fields
    with pytest.raises(ValueError):
        Scenario.model_validate(fixture_data(**(agile_fixtures() | {field: value})))


def test_created_sprint_after_largest_fixture_id_remains_readable():
    fixtures = agile_fixtures()
    fixtures["jira_sprints"][0]["id"] = "999999999"
    fixtures["jira_sprint_issues"] = []
    with database(**fixtures) as db:
        created = ok(
            db,
            "jira_create_sprint",
            board_id="1",
            name="Next",
            start_date="2026-02-01T00:00:00Z",
            end_date="2026-02-02T00:00:00Z",
        )
        assert created["id"] == "1000000000"
        assert ok(db, "jira_update_sprint", sprint_id=created["id"])["name"] == "Next"


def test_timezone_normalization_overflow_is_deliberate_error():
    with database(**agile_fixtures()) as db:
        assert call(
            db,
            "jira_create_sprint",
            board_id="1",
            name="Impossible",
            start_date="9999-12-31T23:59:59-23:59",
            end_date="9999-12-31T23:59:59Z",
        )[1]


def test_relationship_field_selection_trims_csv_whitespace():
    with database(**agile_fixtures()) as db:
        item = ok(
            db,
            "jira_get_issue",
            issue_key="OPS-1",
            fields="summary, sprint, timetracking",
        )
        assert item["sprint"]["id"] == "10"
        assert item["timetracking"]["timeSpentSeconds"] == 0
