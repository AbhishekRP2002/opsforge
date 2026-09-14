"""Relational brands and simulated custom/email domains; no DNS or host I/O."""

import hashlib
import json
from pathlib import PurePosixPath

from . import okta_store as store


def guard(db, arguments, scope, references=(), validate=True):
    if denied := store.guard(
        db,
        scope,
        arguments,
        tuple(key for key, _ in references) if validate else (),
        id_listed=True,
    ):
        return denied
    for key, table in references:
        if store.get(db, table, arguments[key]) is None:
            return store.error(f"{key} not found")
    return None


def fields(arguments, aliases):
    return {
        alias: arguments[key]
        for key, alias in aliases.items()
        if arguments.get(key) is not None
    }


def artifact(db, path):
    parsed = PurePosixPath(path)
    if (
        not path.startswith(("/tmp/", "/var/tmp/", "artifacts/"))
        or ".." in path
        or "%" in path
        or "\\" in path
        or str(parsed) != path
    ):
        return None, "Only normalized episode artifact paths are allowed"
    item = db.artifact(path)
    if item is None:
        return None, "Episode artifact not found"
    return item, None


def _expand_brand(db, brand, expand):
    embedded = {}
    for value in expand or []:
        if value == "themes":
            embedded[value] = [
                x for x in store.rows(db, "okta_themes") if x["brandId"] == brand["id"]
            ]
        elif value == "domains":
            embedded[value] = [
                x
                for x in store.rows(db, "okta_domains")
                if x.get("brandId") == brand["id"]
            ]
        elif value == "emailDomain":
            embedded[value] = store.get(
                db, "okta_email_domains", brand.get("emailDomainId", "")
            )
        else:
            return None, "Unsupported brand expansion"
    return (brand | {"_embedded": embedded} if embedded else brand), None


def list_brands(db, arguments, step, clock):
    if denied := guard(db, arguments, "okta.brands.read"):
        return denied
    if set(arguments.get("expand") or []) - {"themes", "domains", "emailDomain"}:
        return store.error("Unsupported brand expansion")
    items = []
    for brand in store.rows(db, "okta_brands"):
        result, error = _expand_brand(db, brand, arguments.get("expand"))
        if error:
            return store.error(error)
        if (arguments.get("q") or "").casefold() in brand["name"].casefold():
            items.append(result)
    return store.page(items, arguments, "brands", 1, 200)


def get_brand(db, arguments, step, clock):
    if denied := guard(
        db, arguments, "okta.brands.read", (("brand_id", "okta_brands"),)
    ):
        return denied
    result, error = _expand_brand(
        db, store.get(db, "okta_brands", arguments["brand_id"]), arguments.get("expand")
    )
    return store.error(error) if error else (result, False)


def create_brand(db, arguments, step, clock):
    from .okta_pages import initialize_brand
    from .okta_templates import initialize_brand as initialize_email

    if denied := guard(db, arguments, "okta.brands.manage"):
        return denied
    name = arguments["name"]
    if not name.strip() or name == "DRAPP_DOMAIN_BRAND":
        return store.error("Brand name is empty or reserved")
    if any(item["name"] == name for item in store.rows(db, "okta_brands")):
        return store.error("Brand name already exists")
    brand, _ = store.create(
        db, "okta_brands", "bnd", {"name": name, "isDefault": False}
    )
    initialize_brand(db, brand["id"])
    initialize_email(db, brand["id"])
    theme = {
        "id": store._next_id(db, "okta_themes", "thm"),
        "brandId": brand["id"],
        "primaryColorHex": "#1662dd",
        "secondaryColorHex": "#ffffff",
    }
    db.connection.execute(
        "INSERT INTO okta_themes VALUES (?,?,?)",
        (theme["id"], brand["id"], json.dumps(theme)),
    )
    return brand, False


def replace_brand(db, arguments, step, clock):
    if denied := guard(
        db, arguments, "okta.brands.manage", (("brand_id", "okta_brands"),)
    ):
        return denied
    if not arguments["name"].strip() or arguments["name"] == "DRAPP_DOMAIN_BRAND":
        return store.error("Brand name is empty or reserved")
    if any(
        item["name"] == arguments["name"] and item["id"] != arguments["brand_id"]
        for item in store.rows(db, "okta_brands")
    ):
        return store.error("Brand name already exists")
    if arguments.get("email_domain_id") and not store.get(
        db, "okta_email_domains", arguments["email_domain_id"]
    ):
        return store.error("Email domain not found")
    default_app = arguments.get("default_app") or {}
    for key in ("appInstanceId", "app_instance_id"):
        if default_app.get(key) is not None and not isinstance(default_app[key], str):
            return store.error("Default application ID must be a string")
    app_id = default_app.get("appInstanceId", default_app.get("app_instance_id"))
    if app_id and not store.get(db, "okta_applications", app_id):
        return store.error("Default application not found")
    if (
        arguments.get("custom_privacy_policy_url")
        and arguments.get("agree_to_custom_privacy_policy") is not True
    ):
        return store.error("Custom privacy policy requires agreement")
    old = store.get(db, "okta_brands", arguments["brand_id"])
    assert old is not None
    data = fields(
        arguments,
        {
            "name": "name",
            "agree_to_custom_privacy_policy": "agreeToCustomPrivacyPolicy",
            "custom_privacy_policy_url": "customPrivacyPolicyUrl",
            "remove_powered_by_okta": "removePoweredByOkta",
            "locale": "locale",
            "email_domain_id": "emailDomainId",
            "default_app": "defaultApp",
        },
    )
    return store.save(
        db, "okta_brands", data | {"id": old["id"], "isDefault": old["isDefault"]}
    )


def delete_brand(db, arguments, step, clock):
    if denied := store.guard(
        db, "okta.brands.manage", arguments, ("brand_id",), id_listed=True
    ):
        return denied
    return {
        "confirmation_required": True,
        "message": f"Deletion of brand {arguments['brand_id']} requires explicit confirmation.",
    }, False


def list_brand_domains(db, arguments, step, clock):
    if denied := guard(
        db, arguments, "okta.brands.read", (("brand_id", "okta_brands"),)
    ):
        return denied
    domains = [
        item
        for item in store.rows(db, "okta_domains")
        if item.get("brandId") == arguments["brand_id"]
    ]
    return {"domains": domains, "total_fetched": len(domains)}, False


def list_custom_domains(db, arguments, step, clock):
    if denied := guard(db, arguments, "okta.domains.read"):
        return denied
    items = store.rows(db, "okta_domains")
    return {"domains": items, "total_fetched": len(items)}, False


def create_custom_domain(db, arguments, step, clock):
    if denied := guard(db, arguments, "okta.domains.manage"):
        return denied
    source = arguments["certificate_source_type"].upper().strip()
    if source not in {"MANUAL", "OKTA_MANAGED"}:
        return store.error("certificate_source_type must be MANUAL or OKTA_MANAGED")
    name = arguments["domain"]
    if not name.strip() or any(
        item["domain"].casefold() == name.casefold()
        for item in store.rows(db, "okta_domains")
    ):
        return store.error("Domain is empty or already exists")
    return store.create(
        db,
        "okta_domains",
        "dom",
        {
            "domain": name,
            "certificateSourceType": source,
            "validationStatus": "NOT_STARTED",
            "dnsRecords": [],
        },
    )


def get_custom_domain(db, arguments, step, clock):
    if denied := guard(
        db, arguments, "okta.domains.read", (("domain_id", "okta_domains"),)
    ):
        return denied
    return store.get(db, "okta_domains", arguments["domain_id"]), False


def replace_custom_domain(db, arguments, step, clock):
    if denied := guard(
        db,
        arguments,
        "okta.domains.manage",
        (("domain_id", "okta_domains"), ("brand_id", "okta_brands")),
    ):
        return denied
    brand = store.get(db, "okta_brands", arguments["brand_id"])
    assert brand is not None
    if brand["isDefault"]:
        return store.error("Default brand cannot be associated with a custom domain")
    domain = store.get(db, "okta_domains", arguments["domain_id"])
    assert domain is not None
    db.connection.execute(
        "UPDATE okta_domains SET brand_id=? WHERE id=?",
        (arguments["brand_id"], domain["id"]),
    )
    return store.save(db, "okta_domains", domain | {"brandId": arguments["brand_id"]})


def delete_custom_domain(db, arguments, step, clock):
    if denied := store.guard(
        db, "okta.domains.manage", arguments, ("domain_id",), id_listed=True
    ):
        return denied
    if arguments["domain_id"].lower() == "default":
        return store.error("The default Okta org domain cannot be deleted.")
    return {
        "success": False,
        "message": f"Deletion of custom domain {arguments['domain_id']!r} was cancelled.",
    }, False


def upsert_custom_domain_certificate(db, arguments, step, clock):
    if denied := guard(
        db, arguments, "okta.domains.manage", (("domain_id", "okta_domains"),)
    ):
        return denied
    key, invalid = artifact(db, arguments["private_key_file_path"])
    if invalid:
        return store.error(invalid)
    assert key is not None
    if (
        not arguments["certificate"]
        or not arguments["certificate_chain"]
        or not key["content"]
    ):
        return store.error(
            "Certificate, chain and private key must be nonempty inert data"
        )
    db.connection.execute(
        "INSERT INTO okta_domain_certificates VALUES (?,?,?,?) ON CONFLICT(domain_id) DO UPDATE SET certificate=excluded.certificate,chain=excluded.chain,private_key=excluded.private_key",
        (
            arguments["domain_id"],
            arguments["certificate"],
            arguments["certificate_chain"],
            key["content"],
        ),
    )
    domain = store.get(db, "okta_domains", arguments["domain_id"])
    assert domain is not None
    store.save(
        db,
        "okta_domains",
        domain
        | {
            "certificateSourceType": "MANUAL",
            "publicCertificate": {
                "sha256": hashlib.sha256(arguments["certificate"].encode()).hexdigest()
            },
        },
    )
    return {
        "success": True,
        "message": f"Certificate for domain {arguments['domain_id']!r} successfully upserted.",
    }, False


def verify_custom_domain(db, arguments, step, clock):
    if denied := guard(
        db, arguments, "okta.domains.manage", (("domain_id", "okta_domains"),)
    ):
        return denied
    domain = store.get(db, "okta_domains", arguments["domain_id"])
    assert domain is not None
    if domain["validationStatus"] in {"VERIFIED", "COMPLETED"}:
        return {
            "validationStatus": domain["validationStatus"],
            "message": "Domain is already verified. No further action needed.",
        }, False
    return store.save(db, "okta_domains", domain | {"validationStatus": "VERIFIED"})


def _email_expand(db, item, expand):
    return (
        item
        | {"_embedded": {"brands": [store.get(db, "okta_brands", item["brandId"])]}}
        if expand
        else item
    )


def list_email_domains(db, arguments, step, clock):
    if denied := guard(db, arguments, "okta.emailDomains.read"):
        return denied
    items = [
        _email_expand(db, item, arguments.get("expand_brands"))
        for item in store.rows(db, "okta_email_domains")
    ]
    return {"email_domains": items, "total_fetched": len(items)}, False


def create_email_domain(db, arguments, step, clock):
    if denied := guard(
        db,
        arguments,
        "okta.emailDomains.manage",
        (("brand_id", "okta_brands"),),
        validate=False,
    ):
        return denied
    if not all(
        arguments[key].strip() for key in ("domain", "display_name", "user_name")
    ):
        return store.error("Domain and sender fields must be nonempty")
    if any(
        item["domain"].casefold() == arguments["domain"].casefold()
        for item in store.rows(db, "okta_email_domains")
    ):
        return store.error("Email domain already exists")
    item = fields(
        arguments,
        {
            "domain": "domain",
            "display_name": "displayName",
            "user_name": "userName",
            "brand_id": "brandId",
        },
    ) | {
        "validationSubdomain": arguments.get("validation_subdomain", "mail"),
        "validationStatus": "NOT_STARTED",
        "dnsValidationRecords": [],
        "id": store._next_id(db, "okta_email_domains", "emd"),
    }
    db.connection.execute(
        "INSERT INTO okta_email_domains VALUES (?,?,?)",
        (item["id"], arguments["brand_id"], json.dumps(item)),
    )
    return item, False


def get_email_domain(db, arguments, step, clock):
    if denied := guard(
        db,
        arguments,
        "okta.emailDomains.read",
        (("email_domain_id", "okta_email_domains"),),
    ):
        return denied
    return _email_expand(
        db,
        store.get(db, "okta_email_domains", arguments["email_domain_id"]),
        arguments.get("expand_brands"),
    ), False


def replace_email_domain(db, arguments, step, clock):
    if denied := guard(
        db,
        arguments,
        "okta.emailDomains.manage",
        (("email_domain_id", "okta_email_domains"),),
    ):
        return denied
    if not arguments["display_name"].strip() or not arguments["user_name"].strip():
        return store.error("Sender fields must be nonempty")
    item = store.get(db, "okta_email_domains", arguments["email_domain_id"])
    assert item is not None
    return store.save(
        db,
        "okta_email_domains",
        item
        | {
            "displayName": arguments["display_name"],
            "userName": arguments["user_name"],
        },
    )


def delete_email_domain(db, arguments, step, clock):
    if denied := store.guard(
        db, "okta.emailDomains.manage", arguments, ("email_domain_id",), id_listed=True
    ):
        return denied
    return {
        "success": False,
        "message": f"Deletion of email domain {arguments['email_domain_id']!r} was cancelled.",
    }, False


def verify_email_domain(db, arguments, step, clock):
    if denied := guard(
        db,
        arguments,
        "okta.emailDomains.manage",
        (("email_domain_id", "okta_email_domains"),),
    ):
        return denied
    item = store.get(db, "okta_email_domains", arguments["email_domain_id"])
    assert item is not None
    if item["validationStatus"] == "VERIFIED":
        return {
            "validationStatus": "VERIFIED",
            "message": "Email domain is already verified. No further action needed.",
        }, False
    return store.save(db, "okta_email_domains", item | {"validationStatus": "VERIFIED"})


HANDLERS = {
    "list_brands": list_brands,
    "get_brand": get_brand,
    "create_brand": create_brand,
    "replace_brand": replace_brand,
    "delete_brand": delete_brand,
    "list_brand_domains": list_brand_domains,
    "list_custom_domains": list_custom_domains,
    "create_custom_domain": create_custom_domain,
    "get_custom_domain": get_custom_domain,
    "replace_custom_domain": replace_custom_domain,
    "delete_custom_domain": delete_custom_domain,
    "upsert_custom_domain_certificate": upsert_custom_domain_certificate,
    "verify_custom_domain": verify_custom_domain,
    "list_email_domains": list_email_domains,
    "create_email_domain": create_email_domain,
    "get_email_domain": get_email_domain,
    "replace_email_domain": replace_email_domain,
    "delete_email_domain": delete_email_domain,
    "verify_email_domain": verify_email_domain,
}
