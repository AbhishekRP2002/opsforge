import json
from pathlib import Path

import pytest

from .test_okta_applications import call
from .test_okta_applications import env as env_fixture

env = env_fixture
CONTRACTS = json.loads(
    (Path(__file__).parents[1] / "fixtures").joinpath("okta_contracts.json").read_text()
)


@pytest.fixture
def prepared(env):
    setup = [
        (
            "create_application",
            {
                "app_config": {"label": "Fixture", "signOnMode": "BOOKMARK"},
                "activate": False,
            },
        ),
        (
            "create_policy",
            {"policy_data": {"name": "Fixture", "type": "ACCESS_POLICY"}},
        ),
        (
            "create_policy_rule",
            {
                "policy_id": "00p000001",
                "rule_data": {"name": "Fixture", "type": "ACCESS_POLICY"},
            },
        ),
        ("create_brand", {"name": "Fixture"}),
        (
            "create_custom_domain",
            {"domain": "login.example.test", "certificate_source_type": "MANUAL"},
        ),
        ("replace_custom_domain", {"domain_id": "dom000001", "brand_id": "bnd000001"}),
        (
            "create_email_domain",
            {
                "brand_id": "bnd000001",
                "domain": "mail.example.test",
                "display_name": "Fixture",
                "user_name": "fixture",
            },
        ),
        (
            "create_email_customization",
            {
                "brand_id": "bnd000001",
                "template_name": "UserActivation",
                "language": "en",
                "subject": "Fixture",
                "body": "Open ${activationLink}",
            },
        ),
        (
            "create_device_assurance_policy",
            {"policy_data": {"name": "Fixture", "platform": "MACOS"}},
        ),
    ]
    for tool, arguments in setup:
        value, error = call(env, tool, **arguments)
        assert not error, (tool, value)
    return env


CASES = {
    "list_applications": [{}, ["total_fetched"], 1],
    "get_application": [{"app_id": "0oa000001"}, ["label"], "Fixture"],
    "create_application": [
        {"app_config": {"label": "New", "signOnMode": "BOOKMARK"}},
        ["status"],
        "ACTIVE",
    ],
    "update_application": [
        {
            "app_id": "0oa000001",
            "app_config": {"label": "Updated", "signOnMode": "BOOKMARK"},
        },
        ["label"],
        "Updated",
    ],
    "delete_application": [{"app_id": "0oa000001"}, [0, "confirmation_required"], True],
    "confirm_delete_application": [
        {"app_id": "0oa000001", "confirmation": "DELETE"},
        [0, "message"],
        "Application 0oa000001 deleted successfully",
    ],
    "activate_application": [
        {"app_id": "0oa000001"},
        [0, "message"],
        "Application 0oa000001 activated successfully",
    ],
    "deactivate_application": [
        {"app_id": "0oa000001"},
        [0, "message"],
        "Application 0oa000001 deactivated successfully",
    ],
    "list_catalog_apps": [{}, ["items", 0, "name"], "bookmark"],
    "get_catalog_app": [{"app_name": "bookmark"}, ["name"], "bookmark"],
    "install_oin_app": [
        {"name": "bookmark", "label": "New OIN", "sign_on_mode": "BOOKMARK"},
        ["name"],
        "bookmark",
    ],
    "list_policies": [{"type": "ACCESS_POLICY"}, ["total_fetched"], 1],
    "get_policy": [{"policy_id": "00p000001"}, ["name"], "Fixture"],
    "create_policy": [
        {"policy_data": {"name": "New", "type": "ACCESS_POLICY"}},
        ["status"],
        "ACTIVE",
    ],
    "update_policy": [
        {
            "policy_id": "00p000001",
            "policy_data": {"name": "Updated", "type": "ACCESS_POLICY"},
        },
        ["name"],
        "Updated",
    ],
    "delete_policy": [{"policy_id": "00p000001"}, ["success"], True],
    "activate_policy": [{"policy_id": "00p000001"}, ["success"], True],
    "deactivate_policy": [{"policy_id": "00p000001"}, ["success"], True],
    "list_policy_rules": [{"policy_id": "00p000001"}, ["total_fetched"], 1],
    "get_policy_rule": [
        {"policy_id": "00p000001", "rule_id": "0pr000001"},
        ["name"],
        "Fixture",
    ],
    "create_policy_rule": [
        {
            "policy_id": "00p000001",
            "rule_data": {"name": "New", "type": "ACCESS_POLICY"},
        },
        ["name"],
        "New",
    ],
    "update_policy_rule": [
        {
            "policy_id": "00p000001",
            "rule_id": "0pr000001",
            "rule_data": {"name": "Updated", "type": "ACCESS_POLICY"},
        },
        ["name"],
        "Updated",
    ],
    "delete_policy_rule": [
        {"policy_id": "00p000001", "rule_id": "0pr000001"},
        ["success"],
        True,
    ],
    "activate_policy_rule": [
        {"policy_id": "00p000001", "rule_id": "0pr000001"},
        ["success"],
        True,
    ],
    "deactivate_policy_rule": [
        {"policy_id": "00p000001", "rule_id": "0pr000001"},
        ["success"],
        True,
    ],
    "list_brands": [{}, ["total_fetched"], 1],
    "get_brand": [{"brand_id": "bnd000001"}, ["name"], "Fixture"],
    "create_brand": [{"name": "New"}, ["name"], "New"],
    "replace_brand": [
        {"brand_id": "bnd000001", "name": "Updated"},
        ["name"],
        "Updated",
    ],
    "delete_brand": [{"brand_id": "bnd000001"}, ["confirmation_required"], True],
    "list_brand_domains": [{"brand_id": "bnd000001"}, ["total_fetched"], 1],
    "list_custom_domains": [{}, ["total_fetched"], 1],
    "create_custom_domain": [
        {"domain": "new.example.test", "certificate_source_type": "MANUAL"},
        ["validationStatus"],
        "NOT_STARTED",
    ],
    "get_custom_domain": [{"domain_id": "dom000001"}, ["domain"], "login.example.test"],
    "replace_custom_domain": [
        {"domain_id": "dom000001", "brand_id": "bnd000001"},
        ["brandId"],
        "bnd000001",
    ],
    "delete_custom_domain": [{"domain_id": "dom000001"}, ["success"], False],
    "upsert_custom_domain_certificate": [
        {
            "domain_id": "dom000001",
            "certificate": "inert cert",
            "certificate_chain": "inert chain",
            "private_key_file_path": "/tmp/okta-fixture.key",
        },
        ["success"],
        True,
    ],
    "verify_custom_domain": [
        {"domain_id": "dom000001"},
        ["validationStatus"],
        "VERIFIED",
    ],
    "list_email_domains": [{}, ["total_fetched"], 1],
    "create_email_domain": [
        {
            "brand_id": "bnd000001",
            "domain": "newmail.example.test",
            "display_name": "New",
            "user_name": "new",
        },
        ["displayName"],
        "New",
    ],
    "get_email_domain": [
        {"email_domain_id": "emd000001"},
        ["domain"],
        "mail.example.test",
    ],
    "replace_email_domain": [
        {
            "email_domain_id": "emd000001",
            "display_name": "Updated",
            "user_name": "updated",
        },
        ["displayName"],
        "Updated",
    ],
    "delete_email_domain": [{"email_domain_id": "emd000001"}, ["success"], False],
    "verify_email_domain": [
        {"email_domain_id": "emd000001"},
        ["validationStatus"],
        "VERIFIED",
    ],
    "list_brand_themes": [{"brand_id": "bnd000001"}, ["total_fetched"], 1],
    "get_brand_theme": [
        {"brand_id": "bnd000001", "theme_id": "thm000001"},
        ["primaryColorHex"],
        "#1662dd",
    ],
    "replace_brand_theme": [
        {
            "brand_id": "bnd000001",
            "theme_id": "thm000001",
            "primary_color_hex": "#000000",
            "secondary_color_hex": "#ffffff",
            "sign_in_page_touch_point_variant": "OKTA_DEFAULT",
            "end_user_dashboard_touch_point_variant": "FULL_THEME",
            "error_page_touch_point_variant": "OKTA_DEFAULT",
            "email_template_touch_point_variant": "FULL_THEME",
        },
        ["primaryColorHex"],
        "#000000",
    ],
    "upload_brand_theme_logo": [
        {
            "brand_id": "bnd000001",
            "theme_id": "thm000001",
            "file_path": "/tmp/okta-fixture.svg",
        },
        ["url"],
        "episode-artifact:artifacts/okta/themes/thm000001/logo-7a108193a3c54e5c07c1207c0e38b0279d9cddc0fb844fdbdcaf82629ec69eb8",
    ],
    "upload_brand_theme_favicon": [
        {
            "brand_id": "bnd000001",
            "theme_id": "thm000001",
            "file_path": "/tmp/okta-fixture.svg",
        },
        ["url"],
        "episode-artifact:artifacts/okta/themes/thm000001/favicon-7a108193a3c54e5c07c1207c0e38b0279d9cddc0fb844fdbdcaf82629ec69eb8",
    ],
    "upload_brand_theme_background_image": [
        {
            "brand_id": "bnd000001",
            "theme_id": "thm000001",
            "file_path": "/tmp/okta-fixture.svg",
        },
        ["url"],
        "episode-artifact:artifacts/okta/themes/thm000001/backgroundImage-7a108193a3c54e5c07c1207c0e38b0279d9cddc0fb844fdbdcaf82629ec69eb8",
    ],
    "delete_brand_theme_logo": [
        {"brand_id": "bnd000001", "theme_id": "thm000001"},
        ["success"],
        False,
    ],
    "delete_brand_theme_favicon": [
        {"brand_id": "bnd000001", "theme_id": "thm000001"},
        ["success"],
        False,
    ],
    "delete_brand_theme_background_image": [
        {"brand_id": "bnd000001", "theme_id": "thm000001"},
        ["success"],
        False,
    ],
    "get_error_page_resources": [
        {"brand_id": "bnd000001"},
        ["_links", "default", "href"],
        "episode-page:bnd000001/error/default",
    ],
    "get_customized_error_page": [{"brand_id": "bnd000001"}, [], {}],
    "replace_customized_error_page": [
        {"brand_id": "bnd000001", "page_content": "Written"},
        ["pageContent"],
        "Written",
    ],
    "delete_customized_error_page": [{"brand_id": "bnd000001"}, ["success"], False],
    "get_default_error_page": [
        {"brand_id": "bnd000001"},
        ["pageContent"],
        "<html><body>Default error page</body></html>",
    ],
    "get_preview_error_page": [{"brand_id": "bnd000001"}, [], {}],
    "replace_preview_error_page": [
        {"brand_id": "bnd000001", "page_content": "Written"},
        ["pageContent"],
        "Written",
    ],
    "delete_preview_error_page": [{"brand_id": "bnd000001"}, ["success"], False],
    "get_sign_in_page_resources": [
        {"brand_id": "bnd000001"},
        ["_links", "default", "href"],
        "episode-page:bnd000001/sign-in/default",
    ],
    "get_customized_sign_in_page": [{"brand_id": "bnd000001"}, [], {}],
    "replace_customized_sign_in_page": [
        {"brand_id": "bnd000001", "page_content": "Written"},
        ["pageContent"],
        "Written",
    ],
    "delete_customized_sign_in_page": [{"brand_id": "bnd000001"}, ["success"], False],
    "get_default_sign_in_page": [
        {"brand_id": "bnd000001"},
        ["pageContent"],
        "<html><body>Default sign-in page</body></html>",
    ],
    "get_preview_sign_in_page": [{"brand_id": "bnd000001"}, [], {}],
    "replace_preview_sign_in_page": [
        {"brand_id": "bnd000001", "page_content": "Written"},
        ["pageContent"],
        "Written",
    ],
    "delete_preview_sign_in_page": [{"brand_id": "bnd000001"}, ["success"], False],
    "list_sign_in_widget_versions": [
        {"brand_id": "bnd000001"},
        ["versions"],
        ["*", "7"],
    ],
    "get_sign_out_page_settings": [{"brand_id": "bnd000001"}, ["type"], "OKTA_DEFAULT"],
    "replace_sign_out_page_settings": [
        {
            "brand_id": "bnd000001",
            "type": "EXTERNALLY_HOSTED",
            "url": "https://example.test",
        },
        ["url"],
        "https://example.test",
    ],
    "list_email_templates": [
        {"brand_id": "bnd000001"},
        ["items", 0, "name"],
        "UserActivation",
    ],
    "get_email_template": [
        {"brand_id": "bnd000001", "template_name": "UserActivation"},
        ["name"],
        "UserActivation",
    ],
    "list_email_customizations": [
        {"brand_id": "bnd000001", "template_name": "UserActivation"},
        ["total_fetched"],
        1,
    ],
    "create_email_customization": [
        {
            "brand_id": "bnd000001",
            "template_name": "UserActivation",
            "language": "fr",
            "subject": "New",
            "body": "New",
        },
        ["isDefault"],
        False,
    ],
    "get_email_customization": [
        {
            "brand_id": "bnd000001",
            "template_name": "UserActivation",
            "customization_id": "emc000001",
        },
        ["subject"],
        "Fixture",
    ],
    "replace_email_customization": [
        {
            "brand_id": "bnd000001",
            "template_name": "UserActivation",
            "customization_id": "emc000001",
            "language": "en",
            "subject": "Updated",
            "body": "Updated",
        },
        ["subject"],
        "Updated",
    ],
    "delete_email_customization": [
        {
            "brand_id": "bnd000001",
            "template_name": "UserActivation",
            "customization_id": "emc000001",
        },
        ["success"],
        False,
    ],
    "delete_all_email_customizations": [
        {"brand_id": "bnd000001", "template_name": "UserActivation"},
        ["success"],
        False,
    ],
    "get_email_customization_preview": [
        {
            "brand_id": "bnd000001",
            "template_name": "UserActivation",
            "customization_id": "emc000001",
        },
        ["body"],
        "Open https://example.test/activate",
    ],
    "get_email_default_content": [
        {"brand_id": "bnd000001", "template_name": "UserActivation"},
        ["subject"],
        "Activate ${org.name} account",
    ],
    "get_email_default_content_preview": [
        {"brand_id": "bnd000001", "template_name": "UserActivation"},
        ["subject"],
        "Activate OpsForge account",
    ],
    "get_email_settings": [
        {"brand_id": "bnd000001", "template_name": "UserActivation"},
        ["recipients"],
        "ALL_USERS",
    ],
    "replace_email_settings": [
        {
            "brand_id": "bnd000001",
            "template_name": "UserActivation",
            "recipients": "NO_USERS",
        },
        ["recipients"],
        "NO_USERS",
    ],
    "send_test_email": [
        {"brand_id": "bnd000001", "template_name": "UserActivation"},
        ["success"],
        True,
    ],
    "list_device_assurance_policies": [{}, ["policies", 0, "name"], "Fixture"],
    "get_device_assurance_policy": [
        {"device_assurance_id": "dap000001"},
        ["status"],
        "UNKNOWN",
    ],
    "create_device_assurance_policy": [
        {"policy_data": {"name": "New", "platform": "IOS", "jailbreak": False}},
        ["jailbreak"],
        False,
    ],
    "replace_device_assurance_policy": [
        {
            "device_assurance_id": "dap000001",
            "policy_data": {"name": "Updated", "platform": "MACOS"},
        },
        ["after", "name"],
        "Updated",
    ],
    "delete_device_assurance_policy": [
        {"device_assurance_id": "dap000001"},
        ["success"],
        True,
    ],
    "get_logs": [{}, ["total_fetched"], 10],
    "get_login_failures": [{}, ["failures", "total"], 0],
}


@pytest.mark.parametrize("tool", sorted(CASES))
def test_each_extended_tool_success_profile(prepared, tool):
    arguments, path, expected = CASES[tool]
    value, error = call(prepared, tool, **arguments)
    assert not error, value
    for key in path:
        value = value[key]
    assert value == expected


@pytest.mark.parametrize("tool", sorted(CASES))
def test_each_extended_tool_succeeds_with_only_its_declared_scopes(prepared, tool):
    scopes = CONTRACTS[tool]["scopes"]
    with prepared.episode.db.connection:
        prepared.episode.db.connection.execute("DELETE FROM okta_scopes")
        prepared.episode.db.connection.executemany(
            "INSERT INTO okta_scopes VALUES (?)", [(scope,) for scope in scopes]
        )
    arguments, path, expected = CASES[tool]
    step, clock = prepared.state.step_count, prepared.state.simulated_clock
    value, error = call(prepared, tool, **arguments)
    assert not error, value
    for key in path:
        value = value[key]
    assert value == expected
    assert prepared.state.step_count == step + 1
    assert prepared.state.simulated_clock == clock + 1


def _business_state(env):
    connection = env.episode.db.connection
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'okta_%' OR name IN ('episode_artifacts','simulated_sequences')) ORDER BY name"
        )
    ]
    return {
        table: [
            tuple(row)
            for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")
        ]
        for table in tables
    }


@pytest.mark.parametrize("tool", sorted(CASES))
def test_each_extended_tool_missing_scope_is_nonmutating(prepared, tool):
    scope = CONTRACTS[tool]["scopes"][0]
    with prepared.episode.db.connection:
        prepared.episode.db.connection.execute(
            "DELETE FROM okta_scopes WHERE scope=?", (scope,)
        )
    before = _business_state(prepared)
    value, error = call(prepared, tool, **CASES[tool][0])
    assert error
    envelope = CONTRACTS[tool]["scope_error_envelope"]
    assert isinstance(value, list if envelope == "list" else dict)
    if isinstance(value, list):
        message = value[0]["error"]
    else:
        message = value["error"]
    assert scope in message and "missing required scope" in message
    assert _business_state(prepared) == before


@pytest.mark.parametrize(
    "tool", sorted(name for name in CASES if CONTRACTS[name]["validated_ids"])
)
def test_each_extended_id_guard_matches_source_envelope(prepared, tool):
    key = CONTRACTS[tool]["validated_ids"][0]
    before = _business_state(prepared)
    value, error = call(prepared, tool, **(CASES[tool][0] | {key: "../invalid"}))
    assert error
    assert isinstance(
        value, list if CONTRACTS[tool]["id_error_envelope"] == "list" else dict
    )
    assert _business_state(prepared) == before
