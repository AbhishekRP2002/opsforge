"""Brand-owned theme settings and atomic, inert episode media copies."""

import hashlib

from . import okta_store as store
from .okta_customization import artifact, fields, guard


def _guard(db, arguments, manage=False):
    references = (("brand_id", "okta_brands"),)
    if "theme_id" in arguments:
        references += (("theme_id", "okta_themes"),)
    if denied := guard(
        db,
        arguments,
        "okta.brands.manage" if manage else "okta.brands.read",
        references,
    ):
        return denied
    if "theme_id" in arguments:
        theme = store.get(db, "okta_themes", arguments["theme_id"])
        assert theme is not None
        if theme["brandId"] != arguments["brand_id"]:
            return store.error("Theme not found for this brand")
    return None


def list_brand_themes(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    items = [
        item
        for item in store.rows(db, "okta_themes")
        if item["brandId"] == arguments["brand_id"]
    ]
    return {"themes": items, "total_fetched": len(items)}, False


def get_brand_theme(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return store.get(db, "okta_themes", arguments["theme_id"]), False


def replace_brand_theme(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    aliases = {
        "primary_color_hex": "primaryColorHex",
        "secondary_color_hex": "secondaryColorHex",
        "primary_color_contrast_hex": "primaryColorContrastHex",
        "secondary_color_contrast_hex": "secondaryColorContrastHex",
        "sign_in_page_touch_point_variant": "signInPageTouchPointVariant",
        "end_user_dashboard_touch_point_variant": "endUserDashboardTouchPointVariant",
        "error_page_touch_point_variant": "errorPageTouchPointVariant",
        "email_template_touch_point_variant": "emailTemplateTouchPointVariant",
        "loading_page_touch_point_variant": "loadingPageTouchPointVariant",
    }
    data = fields(arguments, aliases)
    for key, allowed in {
        "signInPageTouchPointVariant": {
            "BACKGROUND_IMAGE",
            "BACKGROUND_SECONDARY_COLOR",
            "OKTA_DEFAULT",
        },
        "errorPageTouchPointVariant": {
            "BACKGROUND_IMAGE",
            "BACKGROUND_SECONDARY_COLOR",
            "OKTA_DEFAULT",
        },
        "endUserDashboardTouchPointVariant": {
            "FULL_THEME",
            "LOGO_ON_FULL_WHITE_BACKGROUND",
            "OKTA_DEFAULT",
            "WHITE_LOGO_BACKGROUND",
        },
        "emailTemplateTouchPointVariant": {"FULL_THEME", "OKTA_DEFAULT"},
        "loadingPageTouchPointVariant": {"NONE", "OKTA_DEFAULT"},
    }.items():
        if key in data:
            data[key] = data[key].upper()
            if data[key] not in allowed:
                return store.error(f"Invalid {key}")
    old = store.get(db, "okta_themes", arguments["theme_id"])
    assert old is not None
    retained = {
        key: old[key]
        for key in ("id", "brandId", "logo", "favicon", "backgroundImage")
        if key in old
    }
    return store.save(db, "okta_themes", retained | data)


def _upload(db, arguments, step, clock, field):
    if denied := _guard(db, arguments, True):
        return denied
    item, invalid = artifact(db, arguments["file_path"])
    if invalid:
        return store.error(invalid)
    assert item is not None
    if not item["media_type"].startswith("image/") or not item["content"]:
        return store.error("Theme asset must be nonempty inert image data")
    maximum = 100000 if field == "logo" else 1048576
    if len(item["content"]) >= maximum:
        return store.error("Theme asset exceeds simulated size limit")
    digest = hashlib.sha256(item["content"]).hexdigest()
    path = f"artifacts/okta/themes/{arguments['theme_id']}/{field}-{digest}"
    db.connection.execute(
        "INSERT OR IGNORE INTO episode_artifacts VALUES (?,?,?,?,?)",
        (path, item["content"], item["media_type"], step, clock),
    )
    url = f"episode-artifact:{path}"
    theme = store.get(db, "okta_themes", arguments["theme_id"])
    assert theme is not None
    store.save(db, "okta_themes", theme | {field: url})
    return {"url": url}, False


def upload_brand_theme_logo(db, arguments, step, clock):
    return _upload(db, arguments, step, clock, "logo")


def upload_brand_theme_favicon(db, arguments, step, clock):
    return _upload(db, arguments, step, clock, "favicon")


def upload_brand_theme_background_image(db, arguments, step, clock):
    return _upload(db, arguments, step, clock, "backgroundImage")


def _delete(db, arguments, field):
    if denied := store.guard(
        db, "okta.brands.manage", arguments, ("brand_id", "theme_id"), id_listed=True
    ):
        return denied
    return {
        "success": False,
        "message": f"Deletion of {field} for theme {arguments['theme_id']!r} was cancelled.",
    }, False


def delete_brand_theme_logo(db, arguments, step, clock):
    return _delete(db, arguments, "logo")


def delete_brand_theme_favicon(db, arguments, step, clock):
    return _delete(db, arguments, "favicon")


def delete_brand_theme_background_image(db, arguments, step, clock):
    return _delete(db, arguments, "background image")


HANDLERS = {
    "list_brand_themes": list_brand_themes,
    "get_brand_theme": get_brand_theme,
    "replace_brand_theme": replace_brand_theme,
    "upload_brand_theme_logo": upload_brand_theme_logo,
    "upload_brand_theme_favicon": upload_brand_theme_favicon,
    "upload_brand_theme_background_image": upload_brand_theme_background_image,
    "delete_brand_theme_logo": delete_brand_theme_logo,
    "delete_brand_theme_favicon": delete_brand_theme_favicon,
    "delete_brand_theme_background_image": delete_brand_theme_background_image,
}
