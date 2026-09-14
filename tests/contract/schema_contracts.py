"""Compare independent source constraints despite SDK schema presentation."""

import json


def parameter_descriptions(schema, path=(), definitions=None):
    """Collect descriptions by wire-field path, resolving SDK model references."""
    definitions = definitions or schema.get("$defs", {})
    if "$ref" in schema:
        schema = definitions[schema["$ref"].split("/")[-1]] | {
            key: value for key, value in schema.items() if key != "$ref"
        }
    descriptions = (
        {(path, schema["description"])} if path and "description" in schema else set()
    )
    for name, field in schema.get("properties", {}).items():
        descriptions |= parameter_descriptions(field, (*path, name), definitions)
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            descriptions |= parameter_descriptions(
                schema[key], (*path, key), definitions
            )
    for key in ("anyOf", "oneOf", "prefixItems"):
        for field in schema.get(key, []):
            descriptions |= parameter_descriptions(field, path, definitions)
    return descriptions


def contract_shape(schema, *, root=True, definitions=None):
    """Retain validation/default metadata, normalizing equivalent JSON schemas.

    Top-level extra rejection is the explicitly approved decorator contract.
    Titles and prose descriptions are checked separately from acceptance rules.
    """
    definitions = definitions or schema.get("$defs", {})
    if "$ref" in schema:
        schema = definitions[schema["$ref"].split("/")[-1]] | {
            key: value for key, value in schema.items() if key != "$ref"
        }
    result = {}
    for key, value in schema.items():
        if key in {"title", "description", "$defs"}:
            continue
        if key == "additionalProperties" and (root or value is True):
            continue
        if key == "required":
            if value:
                result[key] = sorted(value)
        elif key == "properties":
            result[key] = {
                name: contract_shape(field, root=False, definitions=definitions)
                for name, field in value.items()
            }
        elif key in {"anyOf", "oneOf"}:
            branches = [
                contract_shape(field, root=False, definitions=definitions)
                for field in value
            ]
            branches = [
                member
                for field in branches
                for member in (field["anyOf"] if set(field) == {"anyOf"} else [field])
            ]
            result["anyOf"] = sorted(
                branches,
                key=lambda field: json.dumps(field, sort_keys=True),
            )
        elif key == "type" and isinstance(value, list):
            branches = []
            for kind in value:
                branch = dict(schema, type=kind)
                for irrelevant in (
                    ("minItems", "maxItems", "items")
                    if kind != "array"
                    else ("minLength", "maxLength")
                ):
                    branch.pop(irrelevant, None)
                branches.append(
                    contract_shape(branch, root=False, definitions=definitions)
                )
            return {
                "anyOf": sorted(
                    branches, key=lambda field: json.dumps(field, sort_keys=True)
                )
            }
        elif isinstance(value, dict):
            result[key] = contract_shape(value, root=False, definitions=definitions)
        elif key == "prefixItems":
            result[key] = [
                contract_shape(field, root=False, definitions=definitions)
                for field in value
            ]
        else:
            result[key] = value
    if "anyOf" in result and result.get("type") == "array":
        # A source array type intersects each union branch; SDK spells it per branch.
        result["anyOf"] = [dict(branch, type="array") for branch in result["anyOf"]]
        del result["type"]
    if "prefixItems" in result and result.get("items") == {}:
        del result["items"]
    return result
