"""Policy and rule replacement, parent validation and headless lifecycle."""

import json

from . import okta_store as store

POLICY_TYPES = {
    "OKTA_SIGN_ON",
    "PASSWORD",
    "MFA_ENROLL",
    "IDP_DISCOVERY",
    "ACCESS_POLICY",
    "PROFILE_ENROLLMENT",
    "POST_AUTH_SESSION",
    "ENTITY_RISK",
    "DEVICE_SIGNAL_COLLECTION",
}


def _guard(db, arguments, manage=False):
    denied = store.guard(
        db,
        "okta.policies.manage" if manage else "okta.policies.read",
        arguments,
        tuple(key for key in ("policy_id", "rule_id") if key in arguments),
    )
    if denied:
        return denied
    if "policy_id" in arguments and not store.get(
        db, "okta_policies", arguments["policy_id"]
    ):
        return store.error("Policy not found")
    if "rule_id" in arguments:
        rule = store.get(db, "okta_policy_rules", arguments["rule_id"])
        if not rule or rule["policyId"] != arguments["policy_id"]:
            return store.error("Policy rule not found for this policy")
    return None


def _validate(data, rule=False):
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        return "Policy or rule name is required"
    allowed = POLICY_TYPES | {"SIGN_ON"} if rule else POLICY_TYPES
    if not isinstance(data.get("type"), str) or data["type"] not in allowed:
        return "Unsupported policy or rule type"
    status = data.get("status", "ACTIVE")
    if not isinstance(status, str) or status not in {"ACTIVE", "INACTIVE"}:
        return "Status must be ACTIVE or INACTIVE"
    return None


def list_policies(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    if arguments["type"] not in POLICY_TYPES:
        return store.error("Unsupported policy type")
    if arguments.get("status") not in (None, "ACTIVE", "INACTIVE"):
        return store.error("Status must be ACTIVE or INACTIVE")
    items = [
        item
        for item in store.rows(db, "okta_policies")
        if item["type"] == arguments["type"]
        and (not arguments.get("status") or item["status"] == arguments["status"])
        and (arguments.get("q") or "").casefold() in item["name"].casefold()
    ]
    return store.page(items, arguments, "policies")


def get_policy(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return store.get(db, "okta_policies", arguments["policy_id"]), False


def create_policy(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    data = arguments["policy_data"]
    if invalid := _validate(data):
        return store.error(invalid)
    return store.create(db, "okta_policies", "00p", {"status": "ACTIVE"} | data)


def update_policy(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    data = arguments["policy_data"]
    if invalid := _validate(data):
        return store.error(invalid)
    old = store.get(db, "okta_policies", arguments["policy_id"])
    assert old is not None
    if old["type"] != data["type"]:
        return store.error("Policy type cannot change")
    return store.save(
        db, "okta_policies", {"status": old["status"]} | data | {"id": old["id"]}
    )


def delete_policy(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    store.remove(db, "okta_policies", arguments["policy_id"])
    return {
        "success": True,
        "message": f"Policy {arguments['policy_id']} deleted successfully",
    }, False


def _lifecycle(db, arguments, status, rule=False):
    if denied := _guard(db, arguments, True):
        return denied
    table, key = (
        ("okta_policy_rules", "rule_id") if rule else ("okta_policies", "policy_id")
    )
    record = store.get(db, table, arguments[key])
    assert record is not None
    store.save(db, table, record | {"status": status})
    return {
        "success": True,
        "message": f"{'Rule' if rule else 'Policy'} {record['id']} {'activated' if status == 'ACTIVE' else 'deactivated'} successfully",
    }, False


def activate_policy(db, arguments, step, clock):
    return _lifecycle(db, arguments, "ACTIVE")


def deactivate_policy(db, arguments, step, clock):
    return _lifecycle(db, arguments, "INACTIVE")


def list_policy_rules(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    items = [
        item
        for item in store.rows(db, "okta_policy_rules")
        if item["policyId"] == arguments["policy_id"]
    ]
    return store.page(items, arguments, "policy_rules")


def get_policy_rule(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return store.get(db, "okta_policy_rules", arguments["rule_id"]), False


def _rule_data(db, arguments):
    data = arguments["rule_data"]
    if invalid := _validate(data, True):
        return None, invalid
    parent = store.get(db, "okta_policies", arguments["policy_id"])
    assert parent is not None
    expected = "SIGN_ON" if parent["type"] == "OKTA_SIGN_ON" else parent["type"]
    if data["type"] != expected:
        return None, "Rule type must match parent policy"
    return {"status": "ACTIVE"} | data | {"policyId": parent["id"]}, None


def create_policy_rule(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    data, invalid = _rule_data(db, arguments)
    if invalid:
        return store.error(invalid)
    assert data is not None
    identifier = store._next_id(db, "okta_policy_rules", "0pr")
    data = data | {"id": identifier}
    db.connection.execute(
        "INSERT INTO okta_policy_rules VALUES (?,?,?)",
        (identifier, arguments["policy_id"], json.dumps(data)),
    )
    return data, False


def update_policy_rule(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    data, invalid = _rule_data(db, arguments)
    if invalid:
        return store.error(invalid)
    assert data is not None
    return store.save(db, "okta_policy_rules", data | {"id": arguments["rule_id"]})


def delete_policy_rule(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    store.remove(db, "okta_policy_rules", arguments["rule_id"])
    return {
        "success": True,
        "message": f"Rule {arguments['rule_id']} deleted successfully",
    }, False


def activate_policy_rule(db, arguments, step, clock):
    return _lifecycle(db, arguments, "ACTIVE", True)


def deactivate_policy_rule(db, arguments, step, clock):
    return _lifecycle(db, arguments, "INACTIVE", True)


HANDLERS = {
    "list_policies": list_policies,
    "get_policy": get_policy,
    "create_policy": create_policy,
    "update_policy": update_policy,
    "delete_policy": delete_policy,
    "activate_policy": activate_policy,
    "deactivate_policy": deactivate_policy,
    "list_policy_rules": list_policy_rules,
    "get_policy_rule": get_policy_rule,
    "create_policy_rule": create_policy_rule,
    "update_policy_rule": update_policy_rule,
    "delete_policy_rule": delete_policy_rule,
    "activate_policy_rule": activate_policy_rule,
    "deactivate_policy_rule": deactivate_policy_rule,
}
