import pytest

from .test_servicenow_incidents import call
from .test_servicenow_incidents import env as snow_fixture

env = snow_fixture


def test_membership_ids_are_monotonic_after_first_record_removed(env):
    group = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert call(
        env, "add_group_members", group_id=group, members=["alex.chen", "sam.lee"]
    )[0]["success"]
    assert call(env, "remove_group_members", group_id=group, members=["alex.chen"])[0][
        "success"
    ]
    assert call(env, "add_group_members", group_id=group, members=["alex.chen"])[0][
        "success"
    ]
    rows = env.episode.db.connection.execute(
        "SELECT sys_id FROM servicenow_memberships ORDER BY sys_id"
    ).fetchall()
    assert [row[0] for row in rows] == [
        "00000000000000000000000000000002",
        "00000000000000000000000000000003",
    ]


def test_users_groups_round_trip_and_secondary_partial_members(env):
    user, error = call(
        env,
        "create_user",
        user_name="new",
        first_name="New",
        last_name="Person",
        email="new@example.test",
        title="Engineer",
        roles=["unknown"],
    )
    assert not error and user["success"]
    uid = user["user_id"]
    assert call(env, "update_user", user_id=uid, title="Lead", active=False)[0][
        "success"
    ]
    found = call(env, "get_user", user_id=uid)[0]["user"]
    assert found["title"] == "Lead" and found["active"] == "false"
    assert found["name"] == "New Person" and "profile_json" not in found
    assert call(env, "list_users", active=False, query="new")[0]["count"] == 1
    group, error = call(
        env, "create_group", name="New group", members=["new", "missing"]
    )
    assert not error and group["success"]
    gid = group["group_id"]
    assert call(env, "update_group", group_id=gid, description="Updated", active=False)[
        0
    ]["success"]
    listed = call(env, "list_groups", query="Updated", active=False)[0]
    assert listed["groups"][0]["sys_id"] == gid
    removed = call(
        env, "remove_group_members", group_id=gid, members=["new", "missing"]
    )[0]
    assert removed["success"] is False and "missing" in removed["message"]
    assert (
        env.episode.db.connection.execute(
            "SELECT count(*) FROM servicenow_memberships WHERE group_id=?", (gid,)
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    "tool,args",
    [
        (
            "create_user",
            {
                "user_name": "alex.chen",
                "first_name": "X",
                "last_name": "Y",
                "email": "x@example.test",
            },
        ),
        ("update_user", {"user_id": "missing"}),
        ("get_user", {"user_id": "missing"}),
        ("list_users", {"limit": -1}),
        ("create_group", {"name": "Bad", "manager": "missing"}),
        ("update_group", {"group_id": "missing"}),
        ("list_groups", {"limit": -1}),
        ("add_group_members", {"group_id": "missing", "members": ["alex.chen"]}),
        ("remove_group_members", {"group_id": "missing", "members": ["alex.chen"]}),
    ],
)
def test_user_group_failures_are_business_results(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and value["success"] is False
