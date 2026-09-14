"""Separate persisted hosted-page defaults, customized content and previews."""

import json

from . import okta_store as store
from .okta_customization import fields, guard


def initialize_brand(db, brand_id):
    for kind in ("error", "sign-in"):
        for slot in ("default", "customized", "preview"):
            data = (
                {"pageContent": f"<html><body>Default {kind} page</body></html>"}
                if slot == "default"
                else {}
            )
            db.connection.execute(
                "INSERT INTO okta_pages VALUES (?,?,?,?)",
                (brand_id, kind, slot, json.dumps(data)),
            )
    db.connection.execute(
        "INSERT INTO okta_pages VALUES (?, 'sign-out', 'customized', ?)",
        (brand_id, '{"type":"OKTA_DEFAULT"}'),
    )


def _guard(db, arguments, manage=False):
    return guard(
        db,
        arguments,
        "okta.brands.manage" if manage else "okta.brands.read",
        (("brand_id", "okta_brands"),),
    )


def _read(db, brand_id, kind, slot):
    row = db.connection.execute(
        "SELECT data_json FROM okta_pages WHERE brand_id=? AND kind=? AND slot=?",
        (brand_id, kind, slot),
    ).fetchone()
    if row is None:
        raise RuntimeError("Brand has no initialized page slot")
    return json.loads(row[0])


def _get(db, arguments, kind, slot):
    if denied := _guard(db, arguments):
        return denied
    return _read(db, arguments["brand_id"], kind, slot), False


def _replace(db, arguments, kind, slot):
    if denied := _guard(db, arguments, True):
        return denied
    data = fields(
        arguments,
        {
            "page_content": "pageContent",
            "widget_version": "widgetVersion",
            "widget_customizations": "widgetCustomizations",
        },
    )
    if not data.get("widgetCustomizations"):
        data.pop("widgetCustomizations", None)
    csp = fields(
        arguments,
        {"csp_mode": "mode", "csp_report_uri": "reportUri", "csp_src_list": "srcList"},
    )
    if csp:
        if csp.get("mode") not in (None, "enforced", "report_only", "disabled"):
            return store.error("Invalid CSP mode")
        data["contentSecurityPolicySetting"] = csp
    db.connection.execute(
        "UPDATE okta_pages SET data_json=? WHERE brand_id=? AND kind=? AND slot=?",
        (json.dumps(data), arguments["brand_id"], kind, slot),
    )
    return data, False


def _resources(db, arguments, kind):
    if denied := _guard(db, arguments):
        return denied
    embedded = {}
    for slot in arguments.get("expand") or []:
        if slot not in {
            "default",
            "customized",
            "preview",
            "customizedUrl",
            "previewUrl",
        }:
            return store.error("Unsupported page resource expansion")
        embedded[slot] = (
            {"href": f"episode-page:{arguments['brand_id']}/{kind}/{slot[:-3]}"}
            if slot.endswith("Url")
            else _read(db, arguments["brand_id"], kind, slot)
        )
    result = {
        "_links": {
            slot: {"href": f"episode-page:{arguments['brand_id']}/{kind}/{slot}"}
            for slot in ("default", "customized", "preview")
        }
    }
    if embedded:
        result["_embedded"] = embedded
    return result, False


def _delete(db, arguments, label):
    if denied := store.guard(
        db, "okta.brands.manage", arguments, ("brand_id",), id_listed=True
    ):
        return denied
    return {"success": False, "message": f"Delete {label} page cancelled."}, False


def get_error_page_resources(db, arguments, step, clock):
    return _resources(db, arguments, "error")


def get_customized_error_page(db, arguments, step, clock):
    return _get(db, arguments, "error", "customized")


def replace_customized_error_page(db, arguments, step, clock):
    return _replace(db, arguments, "error", "customized")


def delete_customized_error_page(db, arguments, step, clock):
    return _delete(db, arguments, "customized error")


def get_default_error_page(db, arguments, step, clock):
    return _get(db, arguments, "error", "default")


def get_preview_error_page(db, arguments, step, clock):
    return _get(db, arguments, "error", "preview")


def replace_preview_error_page(db, arguments, step, clock):
    return _replace(db, arguments, "error", "preview")


def delete_preview_error_page(db, arguments, step, clock):
    return _delete(db, arguments, "preview error")


def get_sign_in_page_resources(db, arguments, step, clock):
    return _resources(db, arguments, "sign-in")


def get_customized_sign_in_page(db, arguments, step, clock):
    return _get(db, arguments, "sign-in", "customized")


def replace_customized_sign_in_page(db, arguments, step, clock):
    return _replace(db, arguments, "sign-in", "customized")


def delete_customized_sign_in_page(db, arguments, step, clock):
    return _delete(db, arguments, "customized sign-in")


def get_default_sign_in_page(db, arguments, step, clock):
    return _get(db, arguments, "sign-in", "default")


def get_preview_sign_in_page(db, arguments, step, clock):
    return _get(db, arguments, "sign-in", "preview")


def replace_preview_sign_in_page(db, arguments, step, clock):
    return _replace(db, arguments, "sign-in", "preview")


def delete_preview_sign_in_page(db, arguments, step, clock):
    return _delete(db, arguments, "preview sign-in")


def list_sign_in_widget_versions(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    versions = [
        row[0]
        for row in db.connection.execute(
            "SELECT version FROM okta_widget_versions ORDER BY version"
        )
    ]
    return {"versions": versions, "total_fetched": len(versions)}, False


def get_sign_out_page_settings(db, arguments, step, clock):
    return _get(db, arguments, "sign-out", "customized")


def replace_sign_out_page_settings(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    kind = arguments["type"].upper()
    if kind not in {"OKTA_DEFAULT", "EXTERNALLY_HOSTED"}:
        return store.error("Invalid sign-out type")
    if kind == "EXTERNALLY_HOSTED" and not arguments.get("url"):
        return store.error(
            "The url parameter is required when type is EXTERNALLY_HOSTED"
        )
    data = {"type": kind} | fields(arguments, {"url": "url"})
    db.connection.execute(
        "UPDATE okta_pages SET data_json=? WHERE brand_id=? AND kind='sign-out' AND slot='customized'",
        (json.dumps(data), arguments["brand_id"]),
    )
    return data, False


HANDLERS = {
    "get_error_page_resources": get_error_page_resources,
    "get_customized_error_page": get_customized_error_page,
    "replace_customized_error_page": replace_customized_error_page,
    "delete_customized_error_page": delete_customized_error_page,
    "get_default_error_page": get_default_error_page,
    "get_preview_error_page": get_preview_error_page,
    "replace_preview_error_page": replace_preview_error_page,
    "delete_preview_error_page": delete_preview_error_page,
    "get_sign_in_page_resources": get_sign_in_page_resources,
    "get_customized_sign_in_page": get_customized_sign_in_page,
    "replace_customized_sign_in_page": replace_customized_sign_in_page,
    "delete_customized_sign_in_page": delete_customized_sign_in_page,
    "get_default_sign_in_page": get_default_sign_in_page,
    "get_preview_sign_in_page": get_preview_sign_in_page,
    "replace_preview_sign_in_page": replace_preview_sign_in_page,
    "delete_preview_sign_in_page": delete_preview_sign_in_page,
    "list_sign_in_widget_versions": list_sign_in_widget_versions,
    "get_sign_out_page_settings": get_sign_out_page_settings,
    "replace_sign_out_page_settings": replace_sign_out_page_settings,
}
