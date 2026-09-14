"""Deterministic application lifecycle and finite OIN catalog."""

from . import okta_store as store
from .okta_identity import _matches


def _guard(db, arguments, manage=False, listed=False, ids=()):
    return store.guard(
        db, "okta.apps.manage" if manage else "okta.apps.read", arguments, ids, listed
    )


def list_applications(db, arguments, step, clock):
    if denied := _guard(db, arguments, listed=True):
        return denied
    if arguments.get("expand"):
        return store.error("Application expansions are unsupported in this simulation")
    items = store.rows(db, "okta_applications")
    try:
        _matches({}, arguments.get("filter"), "application")
        items = [
            item
            for item in items
            if _matches(item, arguments.get("filter"), "application")
        ]
    except ValueError as exc:
        return store.error(str(exc))
    if query := arguments.get("q"):
        items = [
            item
            for item in items
            if query.casefold() in item.get("label", "").casefold()
        ]
    return store.page(items, arguments, "applications")


def get_application(db, arguments, step, clock):
    if denied := _guard(db, arguments, ids=("app_id",)):
        return denied
    if arguments.get("expand"):
        return store.error("Application expansions are unsupported in this simulation")
    app = store.get(db, "okta_applications", arguments["app_id"])
    return (app, False) if app else store.error("Application not found")


def _config(data):
    if not isinstance(data.get("label"), str) or not data["label"].strip():
        return "Application label is required"
    if not isinstance(data.get("signOnMode"), str) or not data["signOnMode"]:
        return "Application signOnMode is required"
    if "settings" in data and not isinstance(data["settings"], dict):
        return "Application settings must be an object"
    return None


def create_application(db, arguments, step, clock):
    if denied := _guard(db, arguments, manage=True):
        return denied
    data = arguments["app_config"]
    if invalid := _config(data):
        return store.error(invalid)
    return store.create(
        db,
        "okta_applications",
        "0oa",
        data | {"status": "ACTIVE" if arguments.get("activate", True) else "INACTIVE"},
    )


def update_application(db, arguments, step, clock):
    if denied := _guard(db, arguments, manage=True, ids=("app_id",)):
        return denied
    app = store.get(db, "okta_applications", arguments["app_id"])
    if app is None:
        return store.error("Application not found")
    data = arguments["app_config"]
    if invalid := _config(data):
        return store.error(invalid)
    return store.save(
        db, "okta_applications", data | {"id": app["id"], "status": app["status"]}
    )


def delete_application(db, arguments, step, clock):
    if denied := _guard(db, arguments, manage=True, listed=True, ids=("app_id",)):
        return denied
    return [
        {
            "confirmation_required": True,
            "app_id": arguments["app_id"],
            "tool_to_use": "confirm_delete_application",
            "message": "Call confirm_delete_application with confirmation='DELETE'.",
        }
    ], False


def confirm_delete_application(db, arguments, step, clock):
    if denied := _guard(db, arguments, manage=True, listed=True, ids=("app_id",)):
        return denied
    if arguments["confirmation"] != "DELETE":
        return store.error(
            "Deletion cancelled. Confirmation 'DELETE' was not provided correctly.",
            True,
        )
    identifier = arguments["app_id"]
    app = store.get(db, "okta_applications", identifier)
    if app is None:
        return store.error("Application not found", True)
    if app["status"] != "INACTIVE":
        return store.error("Deactivate application before deleting", True)
    db.connection.execute("DELETE FROM okta_group_apps WHERE app_id=?", (identifier,))
    store.remove(db, "okta_applications", identifier)
    return [{"message": f"Application {identifier} deleted successfully"}], False


def _lifecycle(db, arguments, status):
    if denied := _guard(db, arguments, manage=True, listed=True, ids=("app_id",)):
        return denied
    app = store.get(db, "okta_applications", arguments["app_id"])
    if app is None:
        return store.error("Application not found", True)
    store.save(db, "okta_applications", app | {"status": status})
    verb = "activated" if status == "ACTIVE" else "deactivated"
    return [{"message": f"Application {app['id']} {verb} successfully"}], False


def activate_application(db, arguments, step, clock):
    return _lifecycle(db, arguments, "ACTIVE")


def deactivate_application(db, arguments, step, clock):
    return _lifecycle(db, arguments, "INACTIVE")


def list_catalog_apps(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    items = store.rows(db, "okta_catalog_apps")
    if query := arguments.get("q"):
        items = [
            item
            for item in items
            if query.casefold() in (item["name"] + " " + item["displayName"]).casefold()
        ]
    offset = 0
    if cursor := arguments.get("after"):
        names = [item["name"] for item in items]
        if cursor not in names:
            return store.error("Invalid catalog cursor")
        offset = names.index(cursor) + 1
    limit = arguments.get("limit") or 20
    if limit < 1:
        return store.error("Catalog limit must be positive")
    fetch_all = arguments.get("fetch_all", False)
    selected = items[offset:] if fetch_all else items[offset : offset + min(limit, 20)]
    more = not fetch_all and len(selected) == min(limit, 20)
    result = {
        "items": selected,
        "total_fetched": len(selected),
        "has_more": more,
        "next_cursor": selected[-1]["name"] if more else None,
        "fetch_all_used": fetch_all,
    }
    if fetch_all:
        result["pagination_info"] = {
            "pages_fetched": max(1, (len(selected) + 19) // 20),
            "total_items": len(selected),
            "stopped_early": False,
            "stop_reason": None,
        }
    return result, False


def get_catalog_app(db, arguments, step, clock):
    if denied := _guard(db, arguments, ids=("app_name",)):
        return denied
    app = store.get(db, "okta_catalog_apps", arguments["app_name"])
    return (app, False) if app else store.error("Catalog app not found")


def install_oin_app(db, arguments, step, clock):
    if denied := _guard(db, arguments, manage=True, ids=("name",)):
        return denied
    catalog = store.get(db, "okta_catalog_apps", arguments["name"])
    if not catalog:
        return store.error("Catalog app not found")
    if arguments["sign_on_mode"] not in catalog["signOnModes"]:
        return store.error("Catalog app does not support this signOnMode")
    config = {
        "name": arguments["name"],
        "label": arguments["label"],
        "signOnMode": arguments["sign_on_mode"],
        "features": catalog["features"],
    }
    if arguments.get("settings") is not None:
        config["settings"] = arguments["settings"]
    return create_application(
        db,
        {"app_config": config, "activate": arguments.get("activate", True)},
        step,
        clock,
    )


HANDLERS = {
    "list_applications": list_applications,
    "get_application": get_application,
    "create_application": create_application,
    "update_application": update_application,
    "delete_application": delete_application,
    "confirm_delete_application": confirm_delete_application,
    "activate_application": activate_application,
    "deactivate_application": deactivate_application,
    "list_catalog_apps": list_catalog_apps,
    "get_catalog_app": get_catalog_app,
    "install_oin_app": install_oin_app,
}
