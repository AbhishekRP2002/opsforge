import json

import pytest
from itops_env import ItopsAction
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment


@pytest.fixture
def env():
    raw = load_scenario().model_dump()
    raw.update(step_budget=500, horizon=2000)
    raw["initial_artifacts"] = [
        {
            "path": "/tmp/okta-fixture.key",
            "content": "INERT SIMULATED PRIVATE KEY",
            "media_type": "application/x-pem-file",
        },
        {
            "path": "/tmp/okta-fixture.svg",
            "content": '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>',
            "media_type": "image/svg+xml",
        },
    ]
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    yield world
    world.close()


def call(env, tool, **arguments):
    result = env.step(ItopsAction(provider="okta", tool_name=tool, arguments=arguments))
    return json.loads(result.content[0]["text"]), result.is_error


def test_application_replacement_lifecycle_and_confirmation(env):
    app, error = call(
        env,
        "create_application",
        app_config={
            "label": "Portal",
            "signOnMode": "BOOKMARK",
            "settings": {"url": "https://example.test"},
        },
    )
    assert not error and app["status"] == "ACTIVE"
    identifier = app["id"]
    assert call(
        env, "confirm_delete_application", app_id=identifier, confirmation="DELETE"
    )[1]
    requested, error = call(env, "delete_application", app_id=identifier)
    assert not error and requested[0]["confirmation_required"] is True
    replaced, error = call(
        env,
        "update_application",
        app_id=identifier,
        app_config={"label": "Replacement", "signOnMode": "BOOKMARK"},
    )
    assert not error and "settings" not in replaced
    assert call(env, "get_application", app_id=identifier)[0]["label"] == "Replacement"
    assert call(env, "list_applications", q="Replacement")[0]["total_fetched"] == 1
    assert not call(env, "deactivate_application", app_id=identifier)[1]
    assert call(env, "get_application", app_id=identifier)[0]["status"] == "INACTIVE"
    assert not call(env, "activate_application", app_id=identifier)[1]
    assert call(env, "get_application", app_id=identifier)[0]["status"] == "ACTIVE"
    assert not call(env, "deactivate_application", app_id=identifier)[1]
    assert call(
        env, "confirm_delete_application", app_id=identifier, confirmation="delete"
    )[1]
    assert not call(
        env, "confirm_delete_application", app_id=identifier, confirmation="DELETE"
    )[1]
    assert call(env, "get_application", app_id=identifier)[1]


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("get_application", {"app_id": "missing"}),
        (
            "update_application",
            {"app_id": "missing", "app_config": {"label": "Missing"}},
        ),
        ("activate_application", {"app_id": "missing"}),
        ("deactivate_application", {"app_id": "missing"}),
        ("delete_application", {"app_id": "../invalid"}),
        ("confirm_delete_application", {"app_id": "missing", "confirmation": "DELETE"}),
        ("create_application", {"app_config": {}}),
        ("list_applications", {"filter": "unsupported"}),
        ("list_catalog_apps", {"after": "missing"}),
        ("get_catalog_app", {"app_name": "missing"}),
        (
            "install_oin_app",
            {"name": "missing", "label": "Missing", "sign_on_mode": "BOOKMARK"},
        ),
    ],
)
def test_application_failures(env, name, arguments):
    assert call(env, name, **arguments)[1]


def test_catalog_install_uses_shared_application_state(env):
    catalog, error = call(env, "list_catalog_apps", q="bookmark")
    assert not error and catalog["items"][0]["name"] == "bookmark"
    definition, error = call(env, "get_catalog_app", app_name="bookmark")
    assert not error and definition["signOnModes"] == ["BOOKMARK"]
    app, error = call(
        env,
        "install_oin_app",
        name="bookmark",
        label="Installed",
        sign_on_mode="BOOKMARK",
        activate=False,
    )
    assert not error and app["status"] == "INACTIVE"
    assert call(env, "get_application", app_id=app["id"])[0]["name"] == "bookmark"


def test_group_application_reads_follow_application_replacement():
    raw = load_scenario().model_dump()
    raw.update(step_budget=100, horizon=500)
    raw["okta_groups"] = [{"id": "g", "profile": {"name": "Staff"}}]
    raw["okta_group_apps"] = [
        {
            "group_id": "g",
            "app_id": "a",
            "app": {
                "id": "a",
                "label": "Old",
                "signOnMode": "BOOKMARK",
                "status": "ACTIVE",
            },
        }
    ]
    world = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    world.reset()
    try:
        assert not call(
            world,
            "update_application",
            app_id="a",
            app_config={"label": "New", "signOnMode": "BOOKMARK"},
        )[1]
        assert (
            call(world, "list_group_apps", group_id="g")[0]["items"][0]["label"]
            == "New"
        )
    finally:
        world.close()
