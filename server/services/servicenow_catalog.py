"""Catalog item/category operations and source partial move results."""

from . import servicenow_store as store

ITEM_FIELDS = (
    "sys_id",
    "name",
    "short_description",
    "category",
    "price",
    "picture",
    "active",
    "order",
)
CATEGORY_FIELDS = (
    "sys_id",
    "title",
    "description",
    "parent",
    "icon",
    "active",
    "order",
)


def _format(row, keys):
    return {key: row.get(key, "") for key in keys}


def _data(arguments, exclude):
    data = store.fields(arguments, exclude)
    if "active" in data:
        data["active"] = str(data["active"]).lower()
    if "order" in data:
        data["order"] = str(data["order"])
    return data


def _list(db, table, arguments, filters, search, keys, plural, label):
    args = arguments | {"active": True if arguments["active"] else None}
    rows, _, error = store.page(
        store.all_rows(db, table), args, filters, search_fields=search
    )
    return {
        "success": not error,
        "message": error or f"Retrieved {len(rows)} catalog {label}",
        plural: [_format(row, keys) for row in rows],
        "total": len(rows),
        "limit": arguments["limit"],
        "offset": arguments["offset"],
    }, False


def list_catalog_items(db, arguments, step, clock):
    return _list(
        db,
        "sc_cat_item",
        arguments,
        ("active", "category"),
        ("short_description", "name"),
        ITEM_FIELDS,
        "items",
        "items",
    )


def list_catalog_categories(db, arguments, step, clock):
    return _list(
        db,
        "sc_category",
        arguments,
        ("active",),
        ("title", "description"),
        CATEGORY_FIELDS,
        "categories",
        "categories",
    )


def get_catalog_item(db, arguments, step, clock):
    row = store.get(db, "sc_cat_item", arguments["item_id"])
    if row is None:
        return store.failure(
            f"Catalog item not found: {arguments['item_id']}", data=None
        )
    variables = [
        item
        for item in store.all_rows(db, "item_option_new")
        if item.get("cat_item") == row["sys_id"]
    ]
    variables.sort(key=lambda item: int(item.get("order", 0)))
    formatted = [
        _format(
            item,
            (
                "sys_id",
                "name",
                "type",
                "mandatory",
                "default_value",
                "help_text",
                "order",
            ),
        )
        | {"label": item.get("question_text", "")}
        for item in variables
    ]
    data = _format(
        row, ITEM_FIELDS + ("description", "delivery_time", "availability")
    ) | {"variables": formatted}
    return {
        "success": True,
        "message": f"Retrieved catalog item: {row.get('name', '')}",
        "data": data,
    }, False


def create_catalog_category(db, arguments, step, clock):
    data = _data(arguments, ())
    if error := store.reference_error(db, data, {"parent": "sc_category"}):
        return store.failure(error, data=None)
    row = store.insert(db, "sc_category", data, step, clock)
    return {
        "success": True,
        "message": f"Created catalog category: {arguments['title']}",
        "data": _format(row, CATEGORY_FIELDS),
    }, False


def update_catalog_category(db, arguments, step, clock):
    key = arguments["category_id"]
    row = store.get(db, "sc_category", key)
    if row is None:
        return store.failure(
            "simulation_profile: catalog category not found", data=None
        )
    data = _data(arguments, ("category_id",))
    if error := store.reference_error(db, data, {"parent": "sc_category"}):
        return store.failure(error, data=None)
    row = store.update(db, "sc_category", row, data, step, clock)
    return {
        "success": True,
        "message": f"Updated catalog category: {key}",
        "data": _format(row, CATEGORY_FIELDS),
    }, False


def update_catalog_item(db, arguments, step, clock):
    row = store.get(db, "sc_cat_item", arguments["item_id"])
    if row is None:
        return store.failure("simulation_profile: catalog item not found", data=None)
    data = _data(arguments, ("item_id",))
    if error := store.reference_error(db, data, {"category": "sc_category"}):
        return store.failure(error, data=None)
    return {
        "success": True,
        "message": "Catalog item updated successfully",
        "data": store.update(db, "sc_cat_item", row, data, step, clock),
    }, False


def move_catalog_items(db, arguments, step, clock):
    target = arguments["target_category_id"]
    failed, count = [], 0
    for key in arguments["item_ids"]:
        row = store.get(db, "sc_cat_item", key)
        error = store.reference_error(
            db,
            {"category": target},
            {"category": "sc_category"},
            required=("category",),
        )
        if row is None or error:
            failed.append(
                {
                    "item_id": key,
                    "error": error or "simulation_profile: catalog item not found",
                }
            )
            continue
        store.update(db, "sc_cat_item", row, {"category": target}, step, clock)
        count += 1
    if count == len(arguments["item_ids"]):
        return {
            "success": True,
            "message": f"Successfully moved {count} catalog items to category {target}",
            "data": {"moved_items_count": count},
        }, False
    if count:
        return {
            "success": True,
            "message": f"Partially moved catalog items. {count} succeeded, {len(failed)} failed.",
            "data": {"moved_items_count": count, "failed_items": failed},
        }, False
    return store.failure(
        "Failed to move any catalog items", data={"failed_items": failed}
    )


HANDLERS = {
    "list_catalog_items": list_catalog_items,
    "get_catalog_item": get_catalog_item,
    "list_catalog_categories": list_catalog_categories,
    "create_catalog_category": create_catalog_category,
    "update_catalog_category": update_catalog_category,
    "update_catalog_item": update_catalog_item,
    "move_catalog_items": move_catalog_items,
}
