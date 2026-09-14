import asyncio
import json
import sqlite3

import pytest
from itops_env import ItopsAction

from .test_okta_applications import call
from .test_okta_applications import env as env_fixture
from .test_okta_extended_profiles import CASES, _business_state
from .test_okta_extended_profiles import prepared as prepared_fixture

env = env_fixture
prepared = prepared_fixture


@pytest.mark.parametrize(
    "tool,payload_key,field",
    [
        ("create_policy", "policy_data", "type"),
        ("create_policy", "policy_data", "status"),
        ("update_policy", "policy_data", "type"),
        ("update_policy", "policy_data", "status"),
        ("create_policy_rule", "rule_data", "type"),
        ("create_policy_rule", "rule_data", "status"),
        ("update_policy_rule", "rule_data", "type"),
        ("update_policy_rule", "rule_data", "status"),
        ("create_device_assurance_policy", "policy_data", "platform"),
        ("replace_device_assurance_policy", "policy_data", "platform"),
    ],
)
@pytest.mark.parametrize("malformed", [[], {}, 42, False, None])
def test_nested_enum_payload_errors_are_metered_and_nonmutating(
    prepared, tool, payload_key, field, malformed
):
    arguments = CASES[tool][0]
    arguments = arguments | {payload_key: arguments[payload_key] | {field: malformed}}
    before = _business_state(prepared)
    step, clock = prepared.state.step_count, prepared.state.simulated_clock
    result = asyncio.run(
        prepared.step_async(
            ItopsAction(provider="okta", tool_name=tool, arguments=arguments)
        )
    )
    value = json.loads(result.content[0]["text"])
    assert result.is_error and value["error"]
    assert prepared.state.step_count == step + 1
    assert prepared.state.simulated_clock == clock + 1
    assert _business_state(prepared) == before


@pytest.mark.parametrize("key", ["appInstanceId", "app_instance_id"])
@pytest.mark.parametrize("malformed", [["invalid"], {"invalid": True}, 42, False])
def test_nested_brand_default_app_id_errors_are_metered_and_nonmutating(
    prepared, key, malformed
):
    before = _business_state(prepared)
    step, clock = prepared.state.step_count, prepared.state.simulated_clock
    value, error = call(
        prepared,
        "replace_brand",
        brand_id="bnd000001",
        name="Fixture",
        default_app={key: malformed},
    )
    assert error and "application" in value["error"].lower()
    assert prepared.state.step_count == step + 1
    assert prepared.state.simulated_clock == clock + 1
    assert _business_state(prepared) == before


def test_log_invocations_are_unknown_not_claimed_success(prepared):
    logs, error = call(prepared, "get_logs")
    assert not error and logs["total_fetched"] == 10
    assert {item["outcome"]["result"] for item in logs["items"]} == {"UNKNOWN"}
    assert [item["actor"]["id"] for item in logs["items"]] == [
        "create_application",
        "create_policy",
        "create_policy_rule",
        "create_brand",
        "create_custom_domain",
        "replace_custom_domain",
        "create_email_domain",
        "create_email_customization",
        "create_device_assurance_policy",
        "get_logs",
    ]
    assert call(prepared, "get_application", app_id="missing")[1]
    failed, error = call(prepared, "get_logs", filter='actor.id eq "get_application"')
    assert not error and failed["total_fetched"] == 1
    assert failed["items"][0]["outcome"]["result"] == "UNKNOWN"
    success, error = call(prepared, "get_logs", filter='outcome.result eq "SUCCESS"')
    assert not error and success["total_fetched"] == 0


GATES = [
    "delete_brand",
    "delete_custom_domain",
    "delete_email_domain",
    "delete_brand_theme_logo",
    "delete_brand_theme_favicon",
    "delete_brand_theme_background_image",
    "delete_customized_error_page",
    "delete_preview_error_page",
    "delete_customized_sign_in_page",
    "delete_preview_sign_in_page",
    "delete_email_customization",
    "delete_all_email_customizations",
]


@pytest.mark.parametrize("tool", GATES)
def test_headless_confirmation_gates_do_not_mutate_any_business_state(prepared, tool):
    before = _business_state(prepared)
    result, error = call(prepared, tool, **CASES[tool][0])
    assert not error
    if tool == "delete_brand":
        assert result["confirmation_required"] is True
    else:
        assert result["success"] is False and "cancelled" in result["message"]
    assert _business_state(prepared) == before


@pytest.mark.parametrize(
    "tool,arguments",
    [
        (
            "create_email_domain",
            {
                "brand_id": "missing",
                "domain": "mail.test",
                "display_name": "Sender",
                "user_name": "sender",
            },
        ),
        ("replace_custom_domain", {"domain_id": "dom000001", "brand_id": "missing"}),
        (
            "replace_preview_error_page",
            {"brand_id": "missing", "page_content": "<html></html>"},
        ),
        (
            "create_email_customization",
            {
                "brand_id": "bnd000001",
                "template_name": "missing",
                "language": "en",
                "subject": "Test",
                "body": "Test",
            },
        ),
        (
            "replace_email_customization",
            {
                "brand_id": "bnd000001",
                "template_name": "missing",
                "customization_id": "emc000001",
                "language": "en",
                "subject": "Test",
                "body": "Test",
            },
        ),
    ],
)
def test_missing_parent_never_creates_or_replaces_child(prepared, tool, arguments):
    before = _business_state(prepared)
    assert call(prepared, tool, **arguments)[1]
    assert _business_state(prepared) == before


def test_media_replay_reset_and_transaction_rollback(prepared):
    db = prepared.episode.db
    action = ItopsAction(
        provider="okta",
        tool_name="upload_brand_theme_logo",
        arguments={
            "brand_id": "bnd000001",
            "theme_id": "thm000001",
            "file_path": "/tmp/okta-fixture.svg",
        },
        invocation_id="logo-once",
    )
    before_step = prepared.state.step_count
    first = prepared.step(action)
    assert not first.is_error
    snapshot = _business_state(prepared)
    assert prepared.step(action).content == first.content
    assert prepared.state.step_count == before_step + 1
    assert _business_state(prepared) == snapshot
    path = json.loads(first.content[0]["text"])["url"].removeprefix("episode-artifact:")
    assert (
        db.artifact(path)["content"] == db.artifact("/tmp/okta-fixture.svg")["content"]
    )
    db.connection.execute(
        "CREATE TRIGGER reject_theme BEFORE UPDATE ON okta_themes BEGIN SELECT RAISE(ABORT, 'theme rejected'); END"
    )
    before_step = prepared.state.step_count
    with pytest.raises(sqlite3.IntegrityError, match="theme rejected"):
        call(prepared, "upload_brand_theme_favicon", **action.arguments)
    assert _business_state(prepared) == snapshot
    assert prepared.state.step_count == before_step
    prepared.reset(episode_id="fresh-media")
    assert prepared.episode.db.artifact(path) is None
    assert prepared.episode.db.artifact("/tmp/okta-fixture.svg") is not None
    assert (
        prepared.episode.db.connection.execute(
            "SELECT COUNT(*) FROM okta_brands"
        ).fetchone()[0]
        == 0
    )


def test_policy_cascade_and_ids_do_not_reuse_deleted_records(prepared):
    assert not call(prepared, "delete_policy", policy_id="00p000001")[1]
    assert (
        prepared.episode.db.connection.execute(
            "SELECT COUNT(*) FROM okta_policy_rules"
        ).fetchone()[0]
        == 0
    )
    replacement, error = call(
        prepared,
        "create_policy",
        policy_data={"name": "Second", "type": "ACCESS_POLICY"},
    )
    assert not error and replacement["id"] == "00p000002"


@pytest.mark.parametrize(
    "tool", ["create_device_assurance_policy", "replace_device_assurance_policy"]
)
def test_android_major_only_is_rejected_by_actual_top_level_source_wrapper(
    prepared, tool
):
    arguments = {
        "policy_data": {"name": "Android", "platform": "ANDROID"},
        "user_stated_os_version": "14",
    }
    if tool.startswith("replace"):
        arguments["device_assurance_id"] = "dap000001"
    before = _business_state(prepared)
    value, error = call(prepared, tool, **arguments)
    assert error and "version" in value["error"].lower()
    assert _business_state(prepared) == before
