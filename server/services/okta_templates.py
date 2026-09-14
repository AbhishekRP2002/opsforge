"""Brand email customizations, bounded preview substitution and simulated outbox."""

import json
import re
from datetime import UTC, datetime, timedelta

from . import okta_store as store
from .okta_customization import guard


def timestamp(clock):
    return (
        (datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=clock))
        .isoformat()
        .replace("+00:00", "Z")
    )


def initialize_brand(db, brand_id):
    for template in db.connection.execute(
        "SELECT name FROM okta_email_template_defaults"
    ):
        db.connection.execute(
            "INSERT INTO okta_email_templates VALUES (?,?,?)",
            (brand_id, template[0], '{"recipients":"ALL_USERS"}'),
        )


def _guard(db, arguments, manage=False):
    if denied := guard(
        db,
        arguments,
        "okta.templates.manage" if manage else "okta.templates.read",
        (("brand_id", "okta_brands"),),
    ):
        return denied
    if (
        "template_name" in arguments
        and db.connection.execute(
            "SELECT 1 FROM okta_email_templates WHERE brand_id=? AND name=?",
            (arguments["brand_id"], arguments["template_name"]),
        ).fetchone()
        is None
    ):
        return store.error("Email template not found")
    if "customization_id" in arguments:
        if denied := store.guard(
            db,
            "okta.templates.manage" if manage else "okta.templates.read",
            arguments,
            ("customization_id",),
            id_listed=True,
        ):
            return denied
        item = store.get(db, "okta_email_customizations", arguments["customization_id"])
        if (
            not item
            or item["brandId"] != arguments["brand_id"]
            or item["templateName"] != arguments["template_name"]
        ):
            return store.error("Email customization not found for this template")
    return None


def _items(db, arguments):
    return [
        item
        for item in store.rows(db, "okta_email_customizations")
        if item["brandId"] == arguments["brand_id"]
        and item["templateName"] == arguments["template_name"]
    ]


def _settings(db, arguments):
    return json.loads(
        db.connection.execute(
            "SELECT settings_json FROM okta_email_templates WHERE brand_id=? AND name=?",
            (arguments["brand_id"], arguments["template_name"]),
        ).fetchone()[0]
    )


def _template(db, arguments):
    result = {"name": arguments["template_name"]}
    embedded = {}
    for key in arguments.get("expand") or []:
        if key == "settings":
            embedded[key] = _settings(db, arguments)
        elif key == "customizationCount":
            embedded[key] = len(_items(db, arguments))
        else:
            return store.error("Unsupported email template expansion")
    if embedded:
        result["_embedded"] = embedded
    return result, False


def list_email_templates(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    items = []
    for row in db.connection.execute(
        "SELECT name FROM okta_email_templates WHERE brand_id=? ORDER BY name",
        (arguments["brand_id"],),
    ):
        item, error = _template(db, arguments | {"template_name": row[0]})
        if error:
            return item, error
        items.append(item)
    return store.page(items, arguments, "email_templates")


def get_email_template(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return _template(db, arguments)


def list_email_customizations(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return store.page(_items(db, arguments), arguments, "email_customizations")


def _write(db, arguments, clock, replacing=False):
    if denied := _guard(db, arguments, True):
        return denied
    if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", arguments["language"]):
        return store.error("Invalid language tag in simulated BCP47 subset")
    if not arguments["subject"] or not arguments["body"]:
        return store.error("Subject and body must be nonempty")
    old = (
        store.get(db, "okta_email_customizations", arguments["customization_id"])
        if replacing
        else None
    )
    items = _items(db, arguments)
    if any(
        item["language"].casefold() == arguments["language"].casefold()
        and (old is None or item["id"] != old["id"])
        for item in items
    ):
        return store.error("Email customization language already exists")
    if old and old["language"].casefold() != arguments["language"].casefold():
        return store.error("Customization language cannot change")
    default = arguments.get("is_default")
    if default is None:
        default = old["isDefault"] if old else not items
    if not default and not any(
        item["isDefault"] and (old is None or item["id"] != old["id"]) for item in items
    ):
        return store.error("Template requires one default customization")
    if default:
        for item in items:
            if item["isDefault"]:
                store.save(db, "okta_email_customizations", item | {"isDefault": False})
    identifier = (
        old["id"] if old else store._next_id(db, "okta_email_customizations", "emc")
    )
    item = {
        "id": identifier,
        "brandId": arguments["brand_id"],
        "templateName": arguments["template_name"],
        "language": arguments["language"],
        "subject": arguments["subject"],
        "body": arguments["body"],
        "isDefault": default,
        "created": old["created"] if old else timestamp(clock),
        "lastUpdated": timestamp(clock),
    }
    if old:
        return store.save(db, "okta_email_customizations", item)
    db.connection.execute(
        "INSERT INTO okta_email_customizations VALUES (?,?,?,?)",
        (
            identifier,
            arguments["brand_id"],
            arguments["template_name"],
            json.dumps(item),
        ),
    )
    return item, False


def create_email_customization(db, arguments, step, clock):
    return _write(db, arguments, clock)


def get_email_customization(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return store.get(
        db, "okta_email_customizations", arguments["customization_id"]
    ), False


def replace_email_customization(db, arguments, step, clock):
    return _write(db, arguments, clock, True)


def delete_email_customization(db, arguments, step, clock):
    if denied := store.guard(
        db,
        "okta.templates.manage",
        arguments,
        ("brand_id", "customization_id"),
        id_listed=True,
    ):
        return denied
    return {"success": False, "message": "Delete email customization cancelled."}, False


def delete_all_email_customizations(db, arguments, step, clock):
    if denied := store.guard(
        db, "okta.templates.manage", arguments, ("brand_id",), id_listed=True
    ):
        return denied
    return {
        "success": False,
        "message": "Delete all email customizations cancelled.",
    }, False


def _preview(db, item):
    values = dict(
        db.connection.execute("SELECT name,value FROM okta_email_preview_values")
    )
    result = {}
    for key in ("subject", "body"):
        unknown = set(re.findall(r"\$\{([^}]+)\}", item[key])) - values.keys()
        if unknown:
            return store.error(
                "Unsupported preview variable: " + ", ".join(sorted(unknown))
            )
        result[key] = re.sub(
            r"\$\{([^}]+)\}", lambda match: values[match[1]], item[key]
        )
    return result, False


def get_email_customization_preview(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return _preview(
        db, store.get(db, "okta_email_customizations", arguments["customization_id"])
    )


def get_email_default_content(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return _default_content(db, arguments)


def _default_content(db, arguments):
    language = arguments.get("language") or "en"
    row = db.connection.execute(
        "SELECT content_json FROM okta_email_template_defaults WHERE name=?",
        (arguments["template_name"],),
    ).fetchone()
    languages = json.loads(row[0])
    if language not in languages:
        return store.error(
            "Default template language is unavailable in this simulation"
        )
    return languages[language], False


def _service_mode(db):
    row = db.connection.execute(
        "SELECT value FROM metadata WHERE key='scenario'"
    ).fetchone()
    return json.loads(row[0])["okta_auth_mode"] == "service"


def get_email_default_content_preview(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    if _service_mode(db):
        return store.error(
            "The email default content preview is not available when using an OAuth 2.0 service token. Use get_email_default_content for raw template content."
        )
    item, error = _default_content(db, arguments)
    return (item, error) if error else _preview(db, item)


def get_email_settings(db, arguments, step, clock):
    if denied := _guard(db, arguments):
        return denied
    return _settings(db, arguments), False


def replace_email_settings(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    if arguments["recipients"] not in {"ALL_USERS", "ADMINS_ONLY", "NO_USERS"}:
        return store.error("Invalid email recipients setting")
    data = {"recipients": arguments["recipients"]}
    db.connection.execute(
        "UPDATE okta_email_templates SET settings_json=? WHERE brand_id=? AND name=?",
        (json.dumps(data), arguments["brand_id"], arguments["template_name"]),
    )
    return data, False


def send_test_email(db, arguments, step, clock):
    if denied := _guard(db, arguments, True):
        return denied
    if _service_mode(db):
        return store.error(
            "send_test_email is not supported when using an OAuth 2.0 service token; a real user identity is required."
        )
    selected = next(
        (
            item
            for item in _items(db, arguments)
            if item["language"].casefold()
            == (arguments.get("language") or "en").casefold()
        ),
        None,
    )
    if selected is None:
        selected, error = _default_content(db, arguments)
        if error:
            return selected, error
    preview, error = _preview(db, selected)
    if error:
        return preview, error
    assert isinstance(preview, dict)
    db.connection.execute(
        "INSERT INTO okta_email_outbox (brand_id,template_name,language,subject,body,step,clock) VALUES (?,?,?,?,?,?,?)",
        (
            arguments["brand_id"],
            arguments["template_name"],
            arguments.get("language") or "en",
            preview["subject"],
            preview["body"],
            step,
            clock,
        ),
    )
    return {
        "success": True,
        "message": f"Test email for '{arguments['template_name']}' recorded in simulated outbox; no email delivered.",
    }, False


HANDLERS = {
    "list_email_templates": list_email_templates,
    "get_email_template": get_email_template,
    "list_email_customizations": list_email_customizations,
    "create_email_customization": create_email_customization,
    "get_email_customization": get_email_customization,
    "replace_email_customization": replace_email_customization,
    "delete_email_customization": delete_email_customization,
    "delete_all_email_customizations": delete_all_email_customizations,
    "get_email_customization_preview": get_email_customization_preview,
    "get_email_default_content": get_email_default_content,
    "get_email_default_content_preview": get_email_default_content_preview,
    "get_email_settings": get_email_settings,
    "replace_email_settings": replace_email_settings,
    "send_test_email": send_test_email,
}
