"""Unmounted Jira core against real episode SQLite; literal expected behavior."""

import importlib
import json
from contextlib import contextmanager

import pytest
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.storage.database import Database


def fixture_data(**updates):
    return (
        load_scenario().model_dump()
        | {
            "jira_projects": [
                {
                    "id": "10",
                    "key": "OPS",
                    "name": "Operations",
                    "issue_types": [{"id": "1", "name": "Task"}],
                    "statuses": [{"id": "1", "name": "Open"}],
                },
                {
                    "id": "20",
                    "key": "DEV",
                    "name": "Development",
                    "issue_types": [{"id": "1", "name": "Task"}],
                    "statuses": [{"id": "1", "name": "Open"}],
                },
            ],
            "jira_users": [
                {
                    "id": "u1",
                    "name": "ada",
                    "display_name": "Ada",
                    "email": "ada@example.test",
                    "active": True,
                    "project_keys": ["OPS", "DEV"],
                }
            ],
            "jira_current_user": "u1",
        }
        | updates
    )


@contextmanager
def database(**updates):
    db = Database.create(
        Scenario.model_validate(fixture_data(**updates)), "jira-test", 0
    )
    try:
        yield db
    finally:
        db.close()


def handlers():
    return importlib.import_module("itops_env.server.services.jira_core").HANDLERS


def call(db, tool, **args):
    with db.connection:
        return handlers()["jira_" + tool](db, args, 1, 7)


def ok(db, tool, **args):
    value, error = call(db, tool, **args)
    assert not error, value
    return value


def create(db, project="OPS", **updates):
    return ok(
        db,
        "create_issue",
        **(
            {"project_key": project, "summary": "Repair", "issue_type": "Task"}
            | updates
        ),
    )["issue"]


def test_fixture_storage_is_explicit_and_validates_references():
    assert "jira_projects" in Scenario.model_fields
    with database() as db:
        assert (
            db.connection.execute("SELECT count(*) FROM jira_projects").fetchone()[0]
            == 2
        )
    for updates in (
        {"jira_current_user": "missing"},
        {
            "jira_users": [
                {
                    "id": "u",
                    "name": "n",
                    "display_name": "N",
                    "email": "e",
                    "active": True,
                    "project_keys": [[]],
                }
            ]
        },
        {"jira_projects": [fixture_data()["jira_projects"][0]] * 2},
        {"jira_epoch": "2026-01-01"},
    ):
        with pytest.raises(ValueError):
            Scenario.model_validate(fixture_data(**updates))


def test_issue_identity_survives_move_and_keys_never_reuse():
    assert "jira_projects" in Scenario.model_fields
    with database() as db:
        first = create(db)
        assert first["key"] == "OPS-1"
        assert first["created"] == "2026-01-01T00:00:07+00:00"
        moved = ok(db, "move_issue", issue_key="OPS-1", target_project_key="DEV")[
            "issue"
        ]
        assert moved["id"] == first["id"] and moved["key"] == "DEV-1"
        assert call(db, "get_issue", issue_key="OPS-1")[1]
        assert ok(db, "get_issue", issue_key="DEV-1")["summary"] == "Repair"
        ok(db, "delete_issue", issue_key="DEV-1")
        assert create(db, "DEV")["key"] == "DEV-2"
        assert create(db)["key"] == "OPS-2"


def test_assignment_user_errors_and_business_envelopes():
    assert "jira_projects" in Scenario.model_fields
    with database() as db:
        create(db)
        assert (
            ok(db, "get_user_profile", user_identifier="me")["user"]["display_name"]
            == "Ada"
        )
        assert ok(db, "get_user_profile", user_identifier="missing")["success"] is False
        assert (
            ok(db, "search_assignable_users", query="ad", project_key="OPS")["count"]
            == 1
        )
        assert ok(db, "search_assignable_users", query="ad")["success"] is False
        assigned = ok(
            db, "assign_issue", issue_key="OPS-1", assignee='{"accountId":"u1"}'
        )
        assert assigned["issue"]["assignee"]["display_name"] == "Ada"
        assert call(db, "assign_issue", issue_key="OPS-1", assignee='{"accountId":[]}')[
            1
        ]
        assert (
            ok(db, "get_issue", issue_key="OPS-1")["assignee"]["display_name"] == "Ada"
        )
        assert ok(db, "assign_issue", issue_key="OPS-1")["issue"]["assignee"] == {
            "display_name": "Unassigned"
        }


def test_core_guards_and_explicit_transaction_rollback():
    assert "jira_projects" in Scenario.model_fields
    with database() as db:
        for changes in (
            {"additional_fields": '{"key":"DEV-9"}'},
            {"additional_fields": '{"labels":[{}]}'},
            {"project_key": "BAD"},
            {"issue_type": "Missing"},
            {"additional_fields": '{"parent":[]}'},
        ):
            args = {
                "project_key": "OPS",
                "summary": "bad",
                "issue_type": "Task",
            } | changes
            assert call(db, "create_issue", **args)[1]
        assert create(db)["key"] == "OPS-1"
        db.connection.execute("BEGIN")
        result, error = handlers()["jira_create_issue"](
            db,
            {"project_key": "OPS", "summary": "rollback", "issue_type": "Task"},
            2,
            8,
        )
        assert not error and result["issue"]["key"] == "OPS-2"
        db.connection.rollback()
        assert call(db, "get_issue", issue_key="OPS-2")[1]
        assert create(db)["key"] == "OPS-2"
    with database(jira_read_only=True) as db:
        assert call(
            db, "create_issue", project_key="OPS", summary="x", issue_type="Task"
        )[1]
    with database(jira_edition="server") as db:
        create(db)
        assert call(db, "move_issue", issue_key="OPS-1", target_project_key="DEV")[1]
        assert ok(db, "get_issue", issue_key="OPS-1")["key"] == "OPS-1"


def test_batch_preparation_partial_failure_and_validation_only():
    with database() as db:
        assert "jira_batch_create_issues" in handlers()
        valid = {"project_key": "OPS", "summary": "Batch", "issue_type": "Task"}
        assert ok(
            db, "batch_create_issues", issues=json.dumps([valid]), validate_only=True
        ) == {"message": "Issues validated successfully", "issues": []}
        assert call(
            db,
            "batch_create_issues",
            issues=json.dumps([valid, {}]),
            validate_only=True,
        )[1]
        assert call(db, "batch_create_issues", issues=json.dumps([{}, valid]))[1]
        result = ok(
            db,
            "batch_create_issues",
            issues=json.dumps([valid, {}, valid | {"assignee": "missing"}]),
        )
        assert [i["key"] for i in result["issues"]] == ["OPS-1", "OPS-2"]
        assert result["issues"][1]["assignee"] == {"display_name": "Unassigned"}
        for bad in ("{}", "not json", '[{"project_key": []}]'):
            assert call(db, "batch_create_issues", issues=bad)[1]
        assert create(db)["key"] == "OPS-3"


def test_query_quotes_projection_compound_order_and_cloud_cursor():
    with database() as db:
        assert "jira_search" in handlers()
        create(
            db,
            summary="Zulu",
            assignee="ada",
            additional_fields='{"labels":["x AND y"]}',
        )
        create(
            db,
            summary="Alpha",
            assignee="ada",
            additional_fields='{"labels":["x AND y"]}',
        )
        create(db, "DEV")
        query = 'project IN (OPS, DEV) AND labels = "x AND y" AND assignee = currentUser() ORDER BY summary ASC, key DESC'
        first = ok(db, "search", jql=query, limit=1, fields="summary", start_at=99)
        assert first["issues"] == [{"id": "2", "key": "OPS-2", "summary": "Alpha"}]
        assert first["total"] == -1 and first["start_at"] == 0
        second = ok(
            db,
            "search",
            jql=query,
            limit=1,
            fields="summary",
            page_token=first["next_page_token"],
        )
        assert second["issues"] == [{"id": "1", "key": "OPS-1", "summary": "Zulu"}]
        assert "next_page_token" not in second
        assert call(
            db, "search", jql="project=DEV", page_token=first["next_page_token"]
        )[1]
        assert ok(db, "get_project_issues", project_key="OPS")["total"] == -1
        for query in (
            'summary ~ "a"',
            "project=OPS OR project=DEV",
            "project IN ()",
            'status = "Open',
            "project=OPS; DELETE FROM jira_issues",
            "updated >= -7d",
            "project=OPS ORDER BY random()",
            "project=OPS AND",
        ):
            assert call(db, "search", jql=query)[1], query


def test_server_paging_project_allowlist_and_display_names():
    projects = fixture_data()["jira_projects"]
    projects[0]["field_names"] = {"customfield_1": "Effort"}
    with database(jira_edition="server", jira_projects=projects) as db:
        create(db, additional_fields='{"customfield_1":3}')
        create(db)
        assert "jira_search" in handlers()
        result = ok(
            db, "search", jql="project=OPS ORDER BY key", fields="key", start_at=1
        )
        assert result["issues"] == [{"id": "2", "key": "OPS-2"}]
        assert result["total"] == 2 and result["start_at"] == 1
        assert ok(
            db,
            "get_issue",
            issue_key="OPS-1",
            fields="customfield_1",
            use_display_names=True,
        )["Effort"] == {"value": 3, "field_id": "customfield_1"}
        assert call(db, "search", jql="project=OPS", page_token="bad")[1]
    with database(jira_projects_filter=["OPS"]) as db:
        create(db)
        assert call(
            db, "create_issue", project_key="DEV", summary="x", issue_type="Task"
        )[1]
        assert (
            ok(db, "search", jql="project IN (OPS,DEV)", projects_filter="DEV")[
                "issues"
            ]
            == []
        )


def test_source_projection_and_parent_relationship_after_move():
    with database() as db:
        first = create(db)
        assert first["status"] == {"name": "Open"}
        assert first["issue_type"] == {"name": "Task"}
        profile = ok(db, "get_user_profile", user_identifier="ada")["user"]
        assert profile == {
            "account_id": "u1",
            "name": "ada",
            "display_name": "Ada",
            "email": "ada@example.test",
            "avatar_url": None,
        }
        child = create(db, additional_fields='{"parent":"OPS-1"}')
        assert child["parent"] == {"id": "1", "key": "OPS-1"}
        ok(db, "move_issue", issue_key="OPS-1", target_project_key="DEV")
        assert ok(db, "get_issue", issue_key="OPS-2", fields="parent")["parent"] == {
            "id": "1",
            "key": "DEV-1",
        }
        assert call(db, "delete_issue", issue_key="DEV-1")[1]
        ok(db, "delete_issue", issue_key="OPS-2")
        ok(db, "delete_issue", issue_key="DEV-1")


def issue_fixture(identity=1, key="OPS-9", **updates):
    return {
        "id": identity,
        "key": key,
        "data": {
            "project_key": "OPS",
            "summary": "Seed",
            "issue_type": "Task",
            "status": "Open",
            "assignee": "u1",
            "created": "2026-01-01T00:00:00+00:00",
            "updated": "2026-01-01T00:00:00+00:00",
        },
    } | updates


def test_nonempty_issue_fixtures_validate_types_cycles_and_assignment():
    with database(jira_issues=[issue_fixture()]) as db:
        assert ok(db, "get_issue", issue_key="OPS-9")["summary"] == "Seed"
        assert create(db)["key"] == "OPS-10"
    invalid = [
        [issue_fixture(parent_id=[])],
        [issue_fixture(parent_id=2), issue_fixture(2, "OPS-10", parent_id=1)],
        [issue_fixture(data=issue_fixture()["data"] | {"assignee": []})],
        [issue_fixture(data=issue_fixture()["data"] | {"status": []})],
        [issue_fixture(data=issue_fixture()["data"] | {"parent": "DEV-8"})],
    ]
    for records in invalid:
        with pytest.raises(ValueError):
            Scenario.model_validate(fixture_data(jira_issues=records))
    users = fixture_data()["jira_users"]
    users[0]["project_keys"] = ["DEV"]
    with pytest.raises(ValueError):
        Scenario.model_validate(
            fixture_data(jira_issues=[issue_fixture()], jira_users=users)
        )


@pytest.mark.parametrize(
    "fields",
    ['{"status": []}', '{"reporter": []}', '{"sprint": []}', '{"versions": [{}]}'],
)
def test_nested_additional_fields_are_validated_before_storage(fields):
    with database() as db:
        assert call(
            db,
            "create_issue",
            project_key="OPS",
            summary="bad",
            issue_type="Task",
            additional_fields=fields,
        )[1]
        assert create(db)["key"] == "OPS-1"


def test_assignee_jql_aliases_and_invalid_current_user_without_rows():
    with database() as db:
        create(db, assignee="ada")
        assert len(ok(db, "search", jql="assignee = ada")["issues"]) == 1
        assert (
            len(ok(db, "search", jql="assignee IN (ada@example.test)")["issues"]) == 1
        )
        assert call(db, "get_project_issues", project_key="missing")[1]
        assert call(db, "move_issue", issue_key="OPS-1", target_project_key="missing")[
            1
        ]
        assert call(db, "delete_issue", issue_key="OPS-999")[1]
    with database(jira_current_user=None) as db:
        assert call(db, "search", jql="assignee = currentUser()")[1]


@pytest.mark.parametrize(
    "tool,args",
    [
        ("create_issue", {"project_key": "OPS", "summary": "x", "issue_type": "Task"}),
        ("batch_create_issues", {"issues": "[]", "validate_only": True}),
        ("assign_issue", {"issue_key": "OPS-9"}),
        ("move_issue", {"issue_key": "OPS-9", "target_project_key": "DEV"}),
        ("delete_issue", {"issue_key": "OPS-9"}),
    ],
)
def test_every_core_write_honors_read_only(tool, args):
    with database(jira_read_only=True, jira_issues=[issue_fixture()]) as db:
        assert call(db, tool, **args)[1]
        assert ok(db, "get_issue", issue_key="OPS-9")["summary"] == "Seed"


def test_malformed_batch_assignee_is_not_unknown_user_recovery():
    with database() as db:
        payload = [
            {
                "project_key": "OPS",
                "summary": "bad",
                "issue_type": "Task",
                "assignee": [],
            }
        ]
        assert call(db, "batch_create_issues", issues=json.dumps(payload))[1]
        assert create(db)["key"] == "OPS-1"


@pytest.mark.parametrize(
    "metadata",
    [
        {"field_names": {"customfield_1": "key"}},
        {"field_names": {"customfield_1": "Effort", "customfield_2": "Effort"}},
        {"issue_types": [{"id": "1", "name": "Task", "subtask": []}]},
    ],
)
def test_fixture_metadata_rejects_unsafe_interpreted_values(metadata):
    projects = fixture_data()["jira_projects"]
    projects[0].update(metadata)
    with pytest.raises(ValueError):
        Scenario.model_validate(fixture_data(jira_projects=projects))


def test_fixture_subtask_requires_parent_like_creation():
    projects = fixture_data()["jira_projects"]
    projects[0]["issue_types"][0]["subtask"] = True
    with pytest.raises(ValueError):
        Scenario.model_validate(
            fixture_data(jira_projects=projects, jira_issues=[issue_fixture()])
        )


def test_source_custom_values_and_display_field_id():
    projects = fixture_data()["jira_projects"]
    projects[0]["field_names"] = {"customfield_1": "Effort"}
    with database(jira_projects=projects) as db:
        create(
            db,
            additional_fields='{"customfield_1":[{"value":"yes"},{"name":"A","self":"https://jira.invalid/1"},{"name":"Checklist","checked":true}]}',
        )
        result = ok(
            db,
            "get_issue",
            issue_key="OPS-1",
            fields="customfield_1",
            use_display_names=True,
        )
        assert result["Effort"] == {
            "field_id": "customfield_1",
            "value": ["yes", "A", {"name": "Checklist", "checked": True}],
        }


@pytest.mark.parametrize("components", [{}, False, 0])
def test_falsey_nested_components_are_not_treated_as_missing(components):
    with database() as db:
        payload = [
            {
                "project_key": "OPS",
                "summary": "bad",
                "issue_type": "Task",
                "components": components,
            }
        ]
        assert call(db, "batch_create_issues", issues=json.dumps(payload))[1]
        assert create(db)["key"] == "OPS-1"


@pytest.mark.parametrize(
    "row",
    [issue_fixture(identity=2**80), issue_fixture(key="OPS-999999999999999999999999")],
)
def test_fixture_identity_counters_fit_sqlite_before_seed(row):
    with pytest.raises(ValueError):
        Scenario.model_validate(fixture_data(jira_issues=[row]))


def test_stored_user_id_is_not_resolved_as_a_public_alias():
    users = fixture_data()["jira_users"]
    users.append(
        {
            "id": "u2",
            "name": "u1",
            "display_name": "Other",
            "email": "other@example.test",
            "active": True,
            "project_keys": ["OPS", "DEV"],
        }
    )
    with database(jira_users=users, jira_issues=[issue_fixture()]) as db:
        issue = ok(db, "get_issue", issue_key="OPS-9")
        assert issue["assignee"]["account_id"] == "u1"
        assert issue["assignee"]["display_name"] == "Ada"
        assert ok(db, "get_user_profile", user_identifier="u1")["success"] is False
        assert (
            ok(db, "get_user_profile", user_identifier="me")["user"]["display_name"]
            == "Ada"
        )
        assert [
            row["key"]
            for row in ok(db, "search", jql="assignee=currentUser()")["issues"]
        ] == ["OPS-9"]


def test_move_rejects_retained_assignee_ineligible_in_destination():
    users = fixture_data()["jira_users"]
    users[0]["project_keys"] = ["OPS"]
    with database(jira_users=users) as db:
        original = create(db, assignee="ada")
        assert call(db, "move_issue", issue_key="OPS-1", target_project_key="DEV")[1]
        assert ok(db, "get_issue", issue_key="OPS-1", fields="*all") == original
        assert call(db, "get_issue", issue_key="DEV-1")[1]
        assert create(db, "DEV")["key"] == "DEV-1"


def test_oversized_valid_fingerprint_cursor_is_a_deliberate_error():
    with database() as db:
        create(db)
        create(db)
        args = {"jql": "project=OPS", "limit": 1}
        first = ok(db, "search", **args)
        fingerprint = first["next_page_token"].split(":")[0]
        result, error = call(
            db, "search", **args, page_token=fingerprint + ":" + "9" * 5000
        )
        assert error and result["error"]
        second = ok(db, "search", **args, page_token=first["next_page_token"])
        assert [row["key"] for row in second["issues"]] == ["OPS-2"]
