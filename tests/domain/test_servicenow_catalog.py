import pytest
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment

from .test_servicenow_incidents import call

ITEM = "cccccccccccccccccccccccccccccccc"


def test_move_requires_target_but_optional_category_can_be_cleared(env):
    before = call(env, "get_catalog_item", item_id=ITEM)[0]
    result, error = call(
        env, "move_catalog_items", item_ids=[ITEM], target_category_id=""
    )
    assert not error and result["success"] is False
    assert call(env, "get_catalog_item", item_id=ITEM)[0] == before
    assert call(env, "update_catalog_item", item_id=ITEM, category="")[0]["success"]
    assert call(env, "get_catalog_item", item_id=ITEM)[0]["data"]["category"] == ""


@pytest.fixture
def env():
    raw = load_scenario().model_dump() | {
        "step_budget": 500,
        "horizon": 2000,
        "servicenow_records": [
            {
                "table": "sc_cat_item",
                "sys_id": ITEM,
                "data": {
                    "name": "Laptop",
                    "short_description": "Short",
                    "active": "true",
                },
            }
        ],
    }
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    yield world
    world.close()


def test_catalog_categories_items_and_partial_move_roundtrip(env):
    created, error = call(env, "create_catalog_category", title="Hardware", order=0)
    assert not error and created["data"]["order"] == "0"
    key = created["data"]["sys_id"]
    assert (
        call(env, "update_catalog_category", category_id=key, title="Devices")[0][
            "data"
        ]["title"]
        == "Devices"
    )
    assert call(env, "list_catalog_categories", query="Devices")[0]["total"] == 1
    moved = call(
        env, "move_catalog_items", item_ids=[ITEM, "absent"], target_category_id=key
    )[0]
    assert (
        moved["success"]
        and moved["data"]["moved_items_count"] == 1
        and len(moved["data"]["failed_items"]) == 1
    )
    assert call(env, "get_catalog_item", item_id=ITEM)[0]["data"]["category"] == key
    assert (
        call(env, "update_catalog_item", item_id=ITEM, active=False, price="0")[0][
            "data"
        ]["active"]
        == "false"
    )
    assert call(env, "list_catalog_items", active=False)[0]["total"] == 1
    assert call(env, "list_catalog_items")[0]["total"] == 0


def test_catalog_variables_mapping_projection_and_zero_updates(env):
    created, error = call(
        env,
        "create_catalog_item_variable",
        catalog_item_id=ITEM,
        name="Location",
        type="custom",
        label="Where",
        min=0,
        order=0,
    )
    assert not error and created["details"]["question_text"] == "Where"
    key = created["variable_id"]
    assert (
        call(
            env,
            "update_catalog_item_variable",
            variable_id=key,
            label="",
            mandatory=True,
        )[0]["details"]["question_text"]
        == ""
    )
    listed = call(
        env, "list_catalog_item_variables", catalog_item_id=ITEM, include_details=False
    )[0]
    assert listed["count"] == 1
    assert set(listed["variables"][0]) == {
        "sys_id",
        "name",
        "type",
        "question_text",
        "order",
        "mandatory",
    }
    assert (
        call(env, "get_catalog_item", item_id=ITEM)[0]["data"]["variables"][0]["label"]
        == ""
    )


def test_optimization_exact_quality_name_and_seeded_synthetic_ranges(env):
    result, error = call(
        env,
        "get_optimization_recommendations",
        recommendation_types=[
            "poor_description",
            "description_quality",
            "low_usage",
            "high_abandonment",
            "slow_fulfillment",
        ],
    )
    assert not error and result["success"]
    recs = {row["type"]: row for row in result["recommendations"]}
    assert set(recs) == {
        "description_quality",
        "low_usage",
        "high_abandonment",
        "slow_fulfillment",
    }
    assert recs["description_quality"]["items"][0]["description_quality"] == 30
    assert 1 <= recs["low_usage"]["items"][0]["order_count"] <= 5
    assert 40 <= recs["high_abandonment"]["items"][0]["abandonment_rate"] <= 80
    assert 5 <= recs["slow_fulfillment"]["items"][0]["avg_fulfillment_time"] <= 10
    call(env, "update_catalog_item", item_id=ITEM, active=False)
    inactive = call(
        env, "get_optimization_recommendations", recommendation_types=["inactive_items"]
    )[0]
    assert inactive["recommendations"][0]["items"][0]["sys_id"] == ITEM


def test_optimization_replay_reset_and_isolation_use_local_rng(env):
    from itops_env import ItopsAction

    action = ItopsAction(
        provider="servicenow",
        tool_name="get_optimization_recommendations",
        arguments={
            "recommendation_types": [
                "low_usage",
                "high_abandonment",
                "slow_fulfillment",
            ]
        },
        invocation_id="synthetic",
    )
    first = env.step(action)
    assert env.step(action).content == first.content
    assert env.state.step_count == 1
    env.reset()
    assert env.step(action).content == first.content
    other = ItopsEnvironment(scenario=env.episode.scenario)
    other.reset()
    try:
        assert other.step(action).content == first.content
    finally:
        other.close()
    call(env, "update_catalog_item", item_id=ITEM, active=False)
    assert call(
        env,
        "get_optimization_recommendations",
        recommendation_types=["low_usage", "high_abandonment", "slow_fulfillment"],
    )[0] == {"success": True, "recommendations": []}


@pytest.mark.parametrize(
    "tool,args",
    [
        ("create_catalog_category", {"title": "Bad", "parent": "absent"}),
        ("update_catalog_category", {"category_id": "absent"}),
        ("list_catalog_categories", {"limit": -1}),
        ("list_catalog_items", {"limit": -1}),
        ("get_catalog_item", {"item_id": "absent"}),
        ("update_catalog_item", {"item_id": "absent"}),
        ("move_catalog_items", {"item_ids": [ITEM], "target_category_id": "absent"}),
        (
            "create_catalog_item_variable",
            {
                "catalog_item_id": "absent",
                "name": "Bad",
                "type": "custom",
                "label": "Bad",
            },
        ),
        ("update_catalog_item_variable", {"variable_id": "absent"}),
        ("list_catalog_item_variables", {"catalog_item_id": ITEM, "limit": -1}),
        (
            "get_optimization_recommendations",
            {"recommendation_types": ["inactive_items"], "category_id": "absent"},
        ),
    ],
)
def test_catalog_business_failures(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and value["success"] is False
