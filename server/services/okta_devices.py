"""Finite platform constraints and replacement diffs for device assurance."""

import re

from . import okta_store as store
from .okta_templates import timestamp

ATTRIBUTES = {
    "MACOS": [
        "osVersion",
        "diskEncryptionType",
        "screenLockType",
        "secureHardwarePresent",
    ],
    "WINDOWS": [
        "osVersion",
        "diskEncryptionType",
        "screenLockType",
        "secureHardwarePresent",
    ],
    "IOS": ["osVersion", "jailbreak", "screenLockType"],
    "ANDROID": ["osVersion", "jailbreak", "screenLockType"],
    "CHROMEOS": ["osVersion"],
}


def _guard(db, arguments, manage=False):
    ids = ("device_assurance_id",) if "device_assurance_id" in arguments else ()
    if denied := store.guard(
        db,
        "okta.deviceAssurance.manage" if manage else "okta.deviceAssurance.read",
        arguments,
        ids,
    ):
        return denied
    if ids and not store.get(
        db, "okta_device_policies", arguments["device_assurance_id"]
    ):
        return store.error("Device assurance policy not found")
    return None


def _version(value):
    if value and not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", value):
        return "Invalid or incomplete OS version: use the exact X.Y.Z or X.Y.Z.W version; no component is inferred."
    return None


def _data(arguments):
    raw = arguments["policy_data"]
    if "osVersion" in raw or "os_version" in raw:
        return (
            None,
            "osVersion must NOT be included in policy_data. Pass user_stated_os_version separately.",
        )
    allowed = {
        "name",
        "platform",
        "diskEncryptionType",
        "screenLockType",
        "secureHardwarePresent",
        "jailbreak",
    }
    if set(raw) - allowed:
        return None, "Unsupported device policy attributes"
    if not isinstance(raw.get("name"), str) or not raw["name"].strip():
        return None, "Device policy name is required"
    if not isinstance(raw.get("platform"), str) or raw["platform"] not in ATTRIBUTES:
        return None, "Supported platform is required"
    data = {key: value for key, value in raw.items() if value is not None}
    for key in set(data) - {"name", "platform"}:
        if key not in ATTRIBUTES[data["platform"]]:
            return None, f"{key} is not supported for {data['platform']}"
        if (
            key in {"secureHardwarePresent", "jailbreak"}
            and type(data[key]) is not bool
        ):
            return None, f"{key} must be boolean"
        if key in {"screenLockType", "diskEncryptionType"} and not isinstance(
            data[key], dict
        ):
            return None, f"{key} must be an object"
    if data.get("jailbreak") is True:
        return None, "The jailbreak attribute currently only accepts false"
    if invalid := _version(arguments.get("user_stated_os_version")):
        return None, invalid
    if version := arguments.get("user_stated_os_version"):
        data["osVersion"] = {"minimum": version}
    return data, None


def _enrich(data):
    return data | {
        "status": data.get("status", "UNKNOWN"),
        "securityAttributeStatus": {
            key: "configured" if data.get(key) is not None else "not_configured"
            for key in ATTRIBUTES[data["platform"]]
        },
    }


def list_device_assurance_policies(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    if invalid := _version(arguments.get("version_threshold")):
        return store.error(invalid)
    result = {
        "policies": [_enrich(item) for item in store.rows(db, "okta_device_policies")],
        "retrieved_at": timestamp(clock),
        "note": "This list reflects simulated time; refetch before resolving policy names.",
    }
    if arguments.get("version_threshold") is not None:
        result["version_threshold"] = arguments["version_threshold"]
    return result, False


def get_device_assurance_policy(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return _enrich(
        store.get(db, "okta_device_policies", arguments["device_assurance_id"])
    ), False


def create_device_assurance_policy(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    data, invalid = _data(arguments)
    if invalid:
        return store.error(invalid)
    assert data is not None
    return store.create(db, "okta_device_policies", "dap", data)


def replace_device_assurance_policy(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    data, invalid = _data(arguments)
    if invalid:
        return store.error(invalid)
    assert data is not None
    identifier = arguments["device_assurance_id"]
    before = _enrich(store.get(db, "okta_device_policies", identifier))
    store.save(db, "okta_device_policies", data | {"id": identifier})
    after = _enrich(data | {"id": identifier})
    implications = {
        "name": "Policy display name updated.",
        "platform": "Target platform changed; the policy applies to the new platform.",
        "osVersion": "Changes the minimum OS version requirement.",
        "diskEncryptionType": "Changes disk encryption requirements.",
        "screenLockType": "Changes screen lock requirements.",
        "secureHardwarePresent": "Changes the secure hardware requirement.",
        "jailbreak": "Changes the configured jailbreak setting.",
    }
    changes = [
        {
            "attribute": key,
            "before": before.get(key),
            "after": after.get(key),
            "implication": implications.get(
                key, f"The {key} setting has been modified."
            ),
        }
        for key in sorted(
            (before.keys() | after.keys()) - {"id", "securityAttributeStatus"}
        )
        if before.get(key) != after.get(key)
    ]
    return {
        "before": before,
        "after": after,
        "changes": changes,
        "_display_required": "Present before and after as a comparison table with each changed attribute and implication.",
    }, False


def delete_device_assurance_policy(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    store.remove(db, "okta_device_policies", arguments["device_assurance_id"])
    return {
        "success": True,
        "message": f"Device assurance policy {arguments['device_assurance_id']} deleted successfully",
    }, False


HANDLERS = {
    "list_device_assurance_policies": list_device_assurance_policies,
    "get_device_assurance_policy": get_device_assurance_policy,
    "create_device_assurance_policy": create_device_assurance_policy,
    "replace_device_assurance_policy": replace_device_assurance_policy,
    "delete_device_assurance_policy": delete_device_assurance_policy,
}
