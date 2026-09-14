import json

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment


def call(env, name, arguments, invocation_id=None):
    action = {"provider": "okta", "tool_name": name, "arguments": arguments}
    if invocation_id is not None:
        action["invocation_id"] = invocation_id
    result = env.step(ItopsAction(**action))
    return json.loads(result.content[0]["text"]), result.is_error


def test_user_profile_lifecycle_and_business_idempotency():
    env = ItopsEnvironment()
    env.reset()
    try:
        created, error = call(
            env,
            "create_user",
            {
                "profile": {
                    "login": "new@example.test",
                    "email": "new@example.test",
                    "firstName": "New",
                    "lastName": "User",
                    "department": "IT",
                },
                "activate": False,
            },
        )
        assert not error and created[0]["status"] == "STAGED"
        user_id = created[0]["id"]
        updated, error = call(
            env,
            "update_user",
            {"user_id": user_id, "profile": {"firstName": "Newest", "title": "SRE"}},
        )
        assert not error
        assert updated[0]["profile"] == {
            "login": "new@example.test",
            "email": "new@example.test",
            "firstName": "Newest",
            "lastName": "User",
            "department": "IT",
            "title": "SRE",
        }
        assert call(env, "deactivate_user", {"user_id": user_id})[0] == [
            {"message": f"User {user_id} deactivated successfully."}
        ]
        assert (
            call(env, "get_user", {"user_id": user_id})[0][0]["status"]
            == "DEPROVISIONED"
        )
        assert not call(env, "delete_deactivated_user", {"user_id": user_id})[1]
        assert call(env, "get_user", {"user_id": user_id})[1]
    finally:
        env.close()


def test_groups_replacement_confirmation_membership_and_lists():
    env = ItopsEnvironment()
    env.reset()
    try:
        active, _ = call(
            env,
            "create_user",
            {
                "profile": {
                    "login": "member@example.test",
                    "email": "member@example.test",
                }
            },
        )
        assert active[0]["status"] == "ACTIVE"
        user_id = active[0]["id"]
        group, _ = call(
            env, "create_group", {"profile": {"name": "IT", "description": "old"}}
        )
        group_id = group[0]["id"]
        replaced, _ = call(
            env, "update_group", {"group_id": group_id, "profile": {"name": "Platform"}}
        )
        assert replaced[0]["profile"] == {"name": "Platform"}

        first, first_error = call(
            env, "add_user_to_group", {"group_id": group_id, "user_id": user_id}
        )
        second, second_error = call(
            env, "add_user_to_group", {"group_id": group_id, "user_id": user_id}
        )
        assert not first_error and not second_error
        assert "added" in first[0]["message"] and "already" in second[0]["message"]
        assert (
            call(env, "list_group_users", {"group_id": group_id})[0]["total_fetched"]
            == 1
        )
        assert (
            call(env, "list_user_groups", {"user_id": user_id})[0][0]["id"] == group_id
        )

        requested, _ = call(env, "delete_group", {"group_id": group_id})
        assert requested[0]["confirmation_required"] is True
        assert (
            call(env, "get_group", {"group_id": group_id})[0][0]["profile"]["name"]
            == "Platform"
        )
        assert call(
            env,
            "confirm_delete_group",
            {"group_id": group_id, "confirmation": "delete"},
        )[1]
        assert not call(
            env,
            "confirm_delete_group",
            {"group_id": group_id, "confirmation": "DELETE"},
        )[1]
        assert call(env, "get_group", {"group_id": group_id})[1]
    finally:
        env.close()


def test_filter_cursor_and_scope_errors_are_explicit_and_deterministic():
    raw = load_scenario().model_dump()
    raw["okta_scopes"] = ["okta.users.read"]
    env = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    env.reset()
    try:
        page, error = call(env, "list_users", {"limit": 1})
        assert not error
        assert page["total_fetched"] == 2
        assert "clamped to 20" in page["warning"]
        filtered, error = call(env, "list_users", {"filter": 'status eq "ACTIVE"'})
        assert not error and filtered["total_fetched"] == 2
        assert call(env, "list_users", {"filter": 'profile.department sw "I"'})[1]
        assert call(env, "list_users", {"after": "not-a-valid-cursor"})[1]
        assert call(env, "create_group", {"profile": {"name": "Denied"}})[1]
    finally:
        env.close()


def test_all_identity_reads_lists_removal_apps_and_empty_export():
    raw = load_scenario().model_dump()
    raw["step_budget"] = 80
    raw["horizon"] = 1000
    raw["okta_groups"] = [{"id": "00g-fixture", "profile": {"name": "Fixture"}}]
    raw["okta_memberships"] = [{"group_id": "00g-fixture", "user_id": "00u-target"}]
    raw["okta_group_apps"] = [
        {
            "group_id": "00g-fixture",
            "app_id": "0oa-app",
            "app": {"id": "0oa-app", "label": "Portal", "status": "ACTIVE"},
        }
    ]
    raw["okta_users"] += [
        {
            "id": f"00u-page-{index:02d}",
            "login": f"page{index}@example.test",
            "email": f"page{index}@example.test",
            "first_name": "Page",
            "last_name": str(index),
            "status": "ACTIVE",
            "profile": {"department": "Paging"},
        }
        for index in range(20)
    ]
    env = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    env.reset()
    try:
        attributes, error = call(env, "get_user_profile_attributes", {})
        assert not error and attributes == {
            "login": "sam.lee@example.test",
            "email": "sam.lee@example.test",
            "firstName": "Sam",
            "lastName": "Lee",
        }
        groups, error = call(env, "list_groups", {})
        assert not error and groups["items"] == [
            {"id": "00g-fixture", "profile": {"name": "Fixture"}}
        ]
        apps, error = call(env, "list_group_apps", {"group_id": "00g-fixture"})
        assert not error and apps["items"] == [
            {"id": "0oa-app", "label": "Portal", "status": "ACTIVE"}
        ]
        users, error = call(env, "list_group_users", {"group_id": "00g-fixture"})
        assert not error and users["items"][0]["id"] == "00u-target"
        removed, error = call(
            env,
            "remove_user_from_group",
            {"group_id": "00g-fixture", "user_id": "00u-target"},
        )
        assert not error and "removed" in removed[0]["message"]
        assert call(
            env,
            "remove_user_from_group",
            {"group_id": "00g-fixture", "user_id": "00u-target"},
        )[1]

        first, error = call(env, "list_users", {"limit": 20})
        assert not error and first["has_more"] and first["next_cursor"]
        assert call(
            env,
            "list_users",
            {
                "limit": 20,
                "filter": 'status eq "ACTIVE"',
                "after": first["next_cursor"],
            },
        )[1]
        empty, error = call(
            env,
            "export_users_csv",
            {"output_path": "/tmp/empty.csv", "q": "no-such-user-value"},
        )
        assert not error and empty == {
            "output_path": "/tmp/empty.csv",
            "total_users": 0,
            "pages_fetched": 1,
        }
        assert env.episode is not None
        assert env.episode.db.artifact("empty.csv") is None

        for name, arguments in [
            ("get_group", {"group_id": "missing"}),
            ("list_group_users", {"group_id": "missing"}),
            ("list_group_apps", {"group_id": "missing"}),
            ("add_user_to_group", {"group_id": "00g-fixture", "user_id": "missing"}),
            ("list_user_groups", {"user_id": "missing"}),
        ]:
            assert call(env, name, arguments)[1], name
    finally:
        env.close()


def test_deleted_simulated_ids_are_never_reused():
    env = ItopsEnvironment()
    env.reset()
    try:
        profile = lambda login: {"profile": {"login": login, "email": login}}
        first, _ = call(env, "create_user", profile("first@example.test"))
        first_id = first[0]["id"]
        call(env, "deactivate_user", {"user_id": first_id})
        call(env, "delete_deactivated_user", {"user_id": first_id})
        second, _ = call(env, "create_user", profile("second@example.test"))
        assert second[0]["id"] != first_id

        group, _ = call(env, "create_group", {"profile": {"name": "First"}})
        group_id = group[0]["id"]
        call(
            env,
            "confirm_delete_group",
            {"group_id": group_id, "confirmation": "DELETE"},
        )
        next_group, _ = call(env, "create_group", {"profile": {"name": "Second"}})
        assert next_group[0]["id"] != group_id
    finally:
        env.close()


@pytest.mark.parametrize("canonical", ["login", "email", "firstName", "lastName"])
def test_fixture_profile_extras_cannot_override_canonical_columns(canonical):
    raw = load_scenario().model_dump()
    raw["okta_users"][0]["profile"] = {canonical: "shadowed"}
    with pytest.raises(ValueError, match="canonical"):
        Scenario.model_validate(raw)


@pytest.mark.parametrize(
    ("app_id", "app", "message"),
    [
        ("", {"id": ""}, "app_id"),
        ("0oa-one", {"id": "0oa-two"}, "match"),
        ("0oa-one", {"label": "Missing ID"}, "match"),
    ],
)
def test_group_app_fixture_requires_matching_nonempty_relational_identity(
    app_id, app, message
):
    raw = load_scenario().model_dump()
    raw["okta_groups"] = [{"id": "00g-apps", "profile": {"name": "Apps"}}]
    raw["okta_group_apps"] = [{"group_id": "00g-apps", "app_id": app_id, "app": app}]
    with pytest.raises(ValueError, match=message):
        Scenario.model_validate(raw)


def test_every_identity_tool_has_a_modeled_failure():
    raw = load_scenario().model_dump()
    raw["step_budget"] = 100
    raw["horizon"] = 1000
    raw["okta_groups"] = [{"id": "00g-known", "profile": {"name": "Known"}}]
    env = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    env.reset()
    assert env.episode is not None
    cases = [
        ("list_users", {"filter": 'profile.department sw "I"'}),
        ("get_user_profile_attributes", {}, "okta.users.read"),
        ("get_user", {"user_id": "missing"}),
        (
            "create_user",
            {
                "profile": {
                    "login": "alex.chen@example.test",
                    "email": "unique@example.test",
                }
            },
        ),
        ("update_user", {"user_id": "missing", "profile": {"firstName": "No"}}),
        ("deactivate_user", {"user_id": "missing"}),
        ("delete_deactivated_user", {"user_id": "00u-target"}),
        ("export_users_csv", {"output_path": "/tmp/../escape.csv"}),
        ("list_groups", {"filter": 'profile.name sw "K"'}),
        ("get_group", {"group_id": "missing"}),
        ("create_group", {"profile": {}}),
        ("delete_group", {"group_id": "missing"}),
        ("confirm_delete_group", {"group_id": "00g-known", "confirmation": "delete"}),
        ("update_group", {"group_id": "missing", "profile": {"name": "No"}}),
        ("list_group_users", {"group_id": "missing"}),
        ("list_group_apps", {"group_id": "missing"}),
        ("add_user_to_group", {"group_id": "00g-known", "user_id": "missing"}),
        ("remove_user_from_group", {"group_id": "00g-known", "user_id": "00u-target"}),
        ("list_user_groups", {"user_id": "missing"}),
    ]
    try:
        for case in cases:
            name, arguments, *scope = case
            if scope:
                env.episode.db.connection.execute(
                    "DELETE FROM okta_scopes WHERE scope=?", (scope[0],)
                )
            _, error = call(env, name, arguments)
            assert error, name
            if scope:
                env.episode.db.connection.execute(
                    "INSERT INTO okta_scopes VALUES (?)", (scope[0],)
                )
    finally:
        env.close()
