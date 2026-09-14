from .test_okta_applications import call
from .test_okta_applications import env as env_fixture

env = env_fixture


def test_device_policy_version_guard_status_diff_and_delete(env):
    invalid, error = call(
        env,
        "create_device_assurance_policy",
        policy_data={"name": "Laptop", "platform": "MACOS"},
        user_stated_os_version="14.2",
    )
    assert error and "version" in invalid["error"].lower()
    device, error = call(
        env,
        "create_device_assurance_policy",
        policy_data={
            "name": "Laptop",
            "platform": "MACOS",
            "secureHardwarePresent": True,
        },
        user_stated_os_version="14.2.1",
    )
    assert not error and device["osVersion"] == {"minimum": "14.2.1"}
    did = device["id"]
    read, error = call(env, "get_device_assurance_policy", device_assurance_id=did)
    assert (
        not error
        and read["securityAttributeStatus"]["screenLockType"] == "not_configured"
    )
    assert read["status"] == "UNKNOWN"
    policies, error = call(
        env, "list_device_assurance_policies", version_threshold="14.2.1"
    )
    assert not error and policies["policies"][0]["id"] == did
    changed, error = call(
        env,
        "replace_device_assurance_policy",
        device_assurance_id=did,
        policy_data={"name": "Laptop v2", "platform": "MACOS"},
        user_stated_os_version="15.0.0",
    )
    assert not error and changed["before"]["secureHardwarePresent"] is True
    assert "secureHardwarePresent" not in changed["after"]
    assert {x["attribute"] for x in changed["changes"]} == {
        "name",
        "osVersion",
        "secureHardwarePresent",
    }
    assert (
        call(env, "delete_device_assurance_policy", device_assurance_id=did)[0][
            "success"
        ]
        is True
    )
    assert call(env, "get_device_assurance_policy", device_assurance_id=did)[1]


def test_logs_use_simulated_records_time_and_reject_unsupported_filters(env):
    call(env, "get_user", user_id="00u-target")
    logs, error = call(env, "get_logs", fetch_all=True)
    assert not error and logs["total_fetched"] >= 1
    assert logs["items"][0]["published"].startswith("2026-01-01T")
    assert call(env, "get_logs", filter='outcome.result eq "INVALID"')[1]
    assert call(env, "get_logs", filter='eventType eq "user.authentication.mfa"')[1]
    assert call(env, "get_logs", filter='actor.id sw "00u"')[1]
    failures, error = call(env, "get_login_failures", user_id="00u-target")
    assert not error and failures["failures"]["total"] == 0
    assert failures["denials"]["total"] == 0
    assert failures["scoped_to_user"] == "00u-target"
