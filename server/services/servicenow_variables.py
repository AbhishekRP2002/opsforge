"""Catalog form-variable records; qualifiers are stored opaque text."""

from . import servicenow_store as store


def _failure(message):
    return store.failure(message, variable_id=None, details=None)


def create_catalog_item_variable(db, arguments, step, clock):
    data = {
        "cat_item": arguments["catalog_item_id"],
        "name": arguments["name"],
        "type": arguments["type"],
        "question_text": arguments["label"],
        "mandatory": str(arguments["mandatory"]).lower(),
    }
    for field in ("help_text", "default_value", "description", "max_length"):
        if arguments[field]:
            data[field] = arguments[field]
    for field in ("order", "min", "max"):
        if arguments[field] is not None:
            data[field] = arguments[field]
    for source, target in (
        ("reference_table", "reference"),
        ("reference_qualifier", "reference_qual"),
    ):
        if arguments[source]:
            data[target] = arguments[source]
    if error := store.reference_error(
        db, data, {"cat_item": "sc_cat_item"}, required=("cat_item",)
    ):
        return _failure(error)
    row = store.insert(db, "item_option_new", data, step, clock)
    return {
        "success": True,
        "message": "Catalog item variable created successfully",
        "variable_id": row["sys_id"],
        "details": row,
    }, False


def update_catalog_item_variable(db, arguments, step, clock):
    data = store.fields(arguments, ("variable_id",))
    for source, target in (
        ("label", "question_text"),
        ("reference_qualifier", "reference_qual"),
    ):
        if source in data:
            data[target] = data.pop(source)
    if "mandatory" in data:
        data["mandatory"] = str(data["mandatory"]).lower()
    if not data:
        return _failure("No update parameters provided")
    row = store.get(db, "item_option_new", arguments["variable_id"])
    if row is None:
        return _failure("simulation_profile: catalog variable not found")
    row = store.update(db, "item_option_new", row, data, step, clock)
    return {
        "success": True,
        "message": "Catalog item variable updated successfully",
        "variable_id": row["sys_id"],
        "details": row,
    }, False


def list_catalog_item_variables(db, arguments, step, clock):
    rows = [
        row
        for row in store.all_rows(db, "item_option_new")
        if row.get("cat_item") == arguments["catalog_item_id"]
    ]
    rows.sort(key=lambda row: int(row.get("order", 0)))
    args = arguments | {"limit": arguments["limit"] or 1000}
    rows, _, error = store.page(rows, args)
    if not arguments["include_details"]:
        rows = [
            {
                key: row.get(key, "")
                for key in (
                    "sys_id",
                    "name",
                    "type",
                    "question_text",
                    "order",
                    "mandatory",
                )
            }
            for row in rows
        ]
    return {
        "success": not error,
        "message": error or f"Retrieved {len(rows)} variables for catalog item",
        "variables": rows,
        "count": len(rows),
    }, False


HANDLERS = {
    "create_catalog_item_variable": create_catalog_item_variable,
    "update_catalog_item_variable": update_catalog_item_variable,
    "list_catalog_item_variables": list_catalog_item_variables,
}
