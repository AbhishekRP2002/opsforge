"""Explicit generic document, attachment and setup adapters for the local tenant."""

import base64
import re
from urllib.parse import quote

from . import erpnext_store as store
from .results import ServiceContent


@store.handler
def doc_create(db, args, step, clock):
    doc = store.create(db, args["doctype"], args["data"], clock)
    return {
        "data": doc,
        "message": f"{doc['doctype']} {doc['name']} created successfully",
    }


@store.handler
def doc_update(db, args, step, clock):
    doc = store.update(db, args["doctype"], args["name"], args["data"], clock)
    return {
        "data": doc,
        "message": f"{doc['doctype']} {doc['name']} updated successfully",
    }


@store.handler
def doc_get(db, args, step, clock):
    return {"data": store.get(db, args["doctype"], args["name"])}


@store.handler
def doc_list(db, args, step, clock):
    docs = store.select(
        db,
        args["doctype"],
        **{
            field: args[field]
            for field in ("fields", "filters", "limit", "order_by")
            if field in args
        },
    )
    return {"doctype": args["doctype"], "count": len(docs), "data": docs}


@store.handler
def doc_delete(db, args, step, clock):
    doc = store.get(db, args["doctype"], args["name"])
    if doc["doctype"] == "File":
        raise store.BusinessError("Generic File deletion is unsupported")
    if doc["docstatus"] == 1:
        raise store.BusinessError(
            "Submitted documents must be cancelled before deletion"
        )
    if any(
        file["attached_to_doctype"] == doc["doctype"]
        and file["attached_to_name"] == doc["name"]
        for file in store.all_docs(db, "File")
    ):
        raise store.BusinessError("Document has attached files")

    def lookup(kind, name):
        if kind == doc["doctype"] and name == doc["name"]:
            raise store.BusinessError("Document has dependent references")
        return store.get(db, kind, name)

    for kind in store.REQUIRED:
        for dependent in store.all_docs(db, kind):
            if (kind, dependent["name"]) != (doc["doctype"], doc["name"]):
                store.validate_references(kind, dependent, lookup)
    db.connection.execute(
        "DELETE FROM erpnext_documents WHERE doctype=? AND name=?",
        (doc["doctype"], doc["name"]),
    )
    return {
        "message": f"{doc['doctype']} {doc['name']} deleted successfully",
        "deleted": True,
        "doctype": doc["doctype"],
        "name": doc["name"],
    }


@store.handler
def method_call(db, args, step, clock):
    method = store.text(args["method"], "method")
    if method != "frappe.client.get_count":
        raise store.BusinessError(f"Method is not permitted: {method}")
    data = args.get("args", {})
    if not isinstance(data, dict) or set(data) - {"doctype", "filters"}:
        raise store.BusinessError("get_count supports doctype and filters")
    if "invalidate" in args:
        # No read cache exists: checking ownership preserves the public invalidation contract.
        inv = args["invalidate"]
        store.get(db, inv["doctype"], inv["name"])
    docs = store.select(
        db, data.get("doctype"), filters=data.get("filters"), all_rows=True
    )
    return {"data": len(docs)}


def parent(db, args):
    return store.get(db, args["attached_to_doctype"], args["attached_to_name"])


@store.handler
def file_upload(db, args, step, clock):
    owner = parent(db, args)
    filename = store.text(args["file_name"], "file_name")
    if re.search(r"[\\/\x00]", filename) or filename in {".", ".."}:
        raise store.BusinessError("file_name must be a filename without a path")
    encoded = store.text(args["content_base64"], "content_base64")
    if not re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", encoded):
        raise store.BusinessError("File content must be valid base64")
    unpadded = encoded.rstrip("=")
    if len(unpadded) % 4 == 1:
        raise store.BusinessError("File content must be valid base64")
    if len(unpadded) * 6 // 8 > 1_048_576:
        raise store.BusinessError(
            "Decoded file exceeds the simulator 1048576-byte limit"
        )
    content = base64.b64decode(unpadded + "=" * (-len(unpadded) % 4), validate=True)
    data = {
        "file_name": filename,
        "file_size": len(content),
        "is_private": 1 if args.get("is_private", True) else 0,
        "attached_to_doctype": owner["doctype"],
        "attached_to_name": owner["name"],
        "owner": "Administrator",
    }
    if "attached_to_field" in args:
        field = store.text(args["attached_to_field"], "attached_to_field")
        if field in store.INTERNAL or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", field
        ):
            raise store.BusinessError("Unsupported attachment field")
        data["attached_to_field"] = field
    file = store.create(db, "File", data, clock, file=True)
    path = f"artifacts/erpnext/{file['name']}.bin"
    file["file_url"] = (
        ("/private/files/" if file["is_private"] else "/files/")
        + file["name"]
        + "/"
        + quote(filename, safe="")
    )
    file["artifact_path"] = path
    db.connection.execute(
        "INSERT INTO episode_artifacts VALUES (?,?,?,?,?)",
        (path, content, "application/octet-stream", step, clock),
    )
    store.persist(db, "File", file)
    if "attached_to_field" in data:
        store.update(
            db,
            owner["doctype"],
            owner["name"],
            {data["attached_to_field"]: file["file_url"]},
            clock,
        )
    return {
        "data": file,
        "message": f"{filename} attached to {owner['doctype']} {owner['name']}",
    }


@store.handler
def file_list(db, args, step, clock):
    owner = parent(db, args)
    docs = store.select(
        db,
        "File",
        fields=[
            "name",
            "file_name",
            "file_url",
            "file_size",
            "is_private",
            "attached_to_field",
            "creation",
            "modified",
            "owner",
        ],
        filters=[
            ["attached_to_doctype", "=", owner["doctype"]],
            ["attached_to_name", "=", owner["name"]],
        ],
        limit=args.get("limit", 50),
        order_by="creation desc",
    )
    for doc in docs:
        doc["is_private"] = doc["is_private"] == 1
    return {"count": len(docs), "data": docs}


@store.handler
def file_download(db, args, step, clock):
    owner = parent(db, args)
    file = store.get(db, "File", args["file_id"])
    if (
        file["attached_to_doctype"] != owner["doctype"]
        or file["attached_to_name"] != owner["name"]
    ):
        raise store.BusinessError("File is not attached to the requested document")
    expected_path = f"artifacts/erpnext/{file['name']}.bin"
    if file.get("artifact_path") != expected_path or file["is_private"] not in (0, 1):
        raise store.BusinessError("Invalid attachment metadata")
    artifact = db.artifact(expected_path)
    if artifact is None or len(artifact["content"]) != file["file_size"]:
        raise store.BusinessError("Attachment bytes are unavailable or inconsistent")
    return ServiceContent.model_validate(
        {
            "content": [
                {
                    "type": "text",
                    "text": f"Prepared {file['file_name']} for download ({file['file_size']} bytes).",
                },
                {
                    "type": "resource",
                    "resource": {
                        "uri": "file:///" + quote(file["file_name"], safe=""),
                        "mimeType": artifact["media_type"],
                        "blob": base64.b64encode(artifact["content"]).decode(),
                    },
                },
            ]
        }
    )


@store.handler
def company_create(db, args, step, clock):
    doc = store.create(db, "Company", args, clock)
    return {"data": doc, "message": f"Company {doc['name']} created successfully"}


@store.handler
def company_list(db, args, step, clock):
    docs = store.select(
        db,
        "Company",
        fields=["name", "abbr", "default_currency", "country", "domain"],
        limit=args.get("limit"),
    )
    return {"doctype": "Company", "count": len(docs), "data": docs}


@store.handler
def user_list(db, args, step, clock):
    filters = [
        ["user_type", "=", "System User"],
        ["name", "not in", ["Administrator", "Guest"]],
    ]
    if not args.get("include_disabled", False):
        filters.append(["enabled", "=", 1])
    docs = store.select(
        db,
        "User",
        fields=["name", "full_name", "enabled"],
        filters=filters,
        limit=500,
        order_by="full_name asc",
    )
    if args.get("search"):
        docs = [
            doc for doc in docs if args["search"].lower() in doc["full_name"].lower()
        ]
    docs = docs[: store.limited(args.get("limit"), 50)]
    return {"doctype": "User", "count": len(docs), "data": docs}


HANDLERS = {
    "erpnext_doc_create": doc_create,
    "erpnext_doc_update": doc_update,
    "erpnext_doc_delete": doc_delete,
    "erpnext_doc_get": doc_get,
    "erpnext_doc_list": doc_list,
    "erpnext_method_call": method_call,
    "erpnext_file_upload": file_upload,
    "erpnext_file_list": file_list,
    "erpnext_file_download": file_download,
    "erpnext_company_create": company_create,
    "erpnext_company_list": company_list,
    "erpnext_user_list": user_list,
}
