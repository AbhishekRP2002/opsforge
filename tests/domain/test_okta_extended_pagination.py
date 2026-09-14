from .test_okta_applications import call
from .test_okta_applications import env as env_fixture

env = env_fixture


def test_application_pagination_clamps_and_scopes_cursors_to_query(env):
    for index in range(23):
        assert not call(
            env,
            "create_application",
            app_config={"label": f"Application {index:02}", "signOnMode": "BOOKMARK"},
        )[1]
    first, error = call(env, "list_applications", limit=1)
    assert not error and first["total_fetched"] == 20 and first["has_more"] is True
    second, error = call(env, "list_applications", after=first["next_cursor"], limit=20)
    assert not error and second["total_fetched"] == 3 and second["has_more"] is False
    assert {row["id"] for row in first["items"]}.isdisjoint(
        {row["id"] for row in second["items"]}
    )
    assert call(env, "list_applications", after=first["next_cursor"], q="other")[1]
    all_items, error = call(env, "list_applications", fetch_all=True)
    assert not error and all_items["total_fetched"] == 23
    assert all_items["has_more"] is False and all_items["next_cursor"] is None
    assert all_items["pagination_info"]["stopped_early"] is False


def test_brands_allow_one_item_pages_and_reject_unsupported_expand_on_empty_state(env):
    assert call(env, "list_brands", expand=["unsupported"])[1]
    for name in ("A", "B", "C"):
        assert not call(env, "create_brand", name=name)[1]
    page, error = call(env, "list_brands", limit=1)
    assert not error and page["total_fetched"] == 1 and page["has_more"] is True
    assert (
        call(env, "list_brands", after=page["next_cursor"], limit=1)[0]["items"][0][
            "name"
        ]
        == "B"
    )
