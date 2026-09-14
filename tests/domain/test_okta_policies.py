from .test_okta_applications import call
from .test_okta_applications import env as env_fixture

env = env_fixture


def test_policy_rule_parent_replacement_lifecycle_and_deletion(env):
    policy, error = call(
        env,
        "create_policy",
        policy_data={"name": "Access", "type": "ACCESS_POLICY", "description": "old"},
    )
    assert not error and policy["status"] == "ACTIVE"
    pid = policy["id"]
    rule, error = call(
        env,
        "create_policy_rule",
        policy_id=pid,
        rule_data={
            "name": "Allow",
            "type": "ACCESS_POLICY",
            "actions": {"access": "ALLOW"},
        },
    )
    assert not error and rule["actions"] == {"access": "ALLOW"}
    rid = rule["id"]
    assert call(env, "list_policy_rules", policy_id=pid)[0]["total_fetched"] == 1
    assert call(env, "list_policies", type="ACCESS_POLICY")[0]["total_fetched"] == 1
    assert not call(
        env,
        "update_policy",
        policy_id=pid,
        policy_data={"name": "Renamed", "type": "ACCESS_POLICY"},
    )[1]
    assert "description" not in call(env, "get_policy", policy_id=pid)[0]
    assert not call(
        env,
        "update_policy_rule",
        policy_id=pid,
        rule_id=rid,
        rule_data={
            "name": "Deny",
            "type": "ACCESS_POLICY",
            "actions": {"access": "DENY"},
        },
    )[1]
    assert call(env, "get_policy_rule", policy_id=pid, rule_id=rid)[0]["actions"] == {
        "access": "DENY"
    }
    for tool, state in [
        ("deactivate_policy", "INACTIVE"),
        ("activate_policy", "ACTIVE"),
    ]:
        assert call(env, tool, policy_id=pid)[0]["success"] is True
        assert call(env, "get_policy", policy_id=pid)[0]["status"] == state
    for tool, state in [
        ("deactivate_policy_rule", "INACTIVE"),
        ("activate_policy_rule", "ACTIVE"),
    ]:
        assert call(env, tool, policy_id=pid, rule_id=rid)[0]["success"] is True
        assert (
            call(env, "get_policy_rule", policy_id=pid, rule_id=rid)[0]["status"]
            == state
        )
    other, error = call(
        env, "create_policy", policy_data={"name": "Other", "type": "ACCESS_POLICY"}
    )
    assert not error
    assert call(env, "get_policy_rule", policy_id=other["id"], rule_id=rid)[1]
    assert call(env, "delete_policy_rule", policy_id=other["id"], rule_id=rid)[1]
    assert (
        call(env, "delete_policy_rule", policy_id=pid, rule_id=rid)[0]["success"]
        is True
    )
    assert call(env, "get_policy_rule", policy_id=pid, rule_id=rid)[1]
    assert call(env, "delete_policy", policy_id=pid)[0]["success"] is True
    assert call(env, "get_policy", policy_id=pid)[1]


def test_missing_policy_never_creates_rule(env):
    value, error = call(
        env,
        "create_policy_rule",
        policy_id="missing",
        rule_data={"name": "Orphan", "type": "ACCESS_POLICY"},
    )
    assert error and "not found" in value["error"]
