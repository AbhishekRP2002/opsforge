"""Independent source declarations and executable per-tool evidence are complete."""

import ast
import json
from pathlib import Path

from itops_env.server.mcp_servers import tools
from jsonschema import Draft202012Validator

from .schema_contracts import contract_shape, parameter_descriptions


def test_expansion_preserves_existing_provider_registration_order():
    providers = list(tools.REGISTRARS)
    assert providers[:3] == ["okta", "servicenow", "benchmark"]
    assert providers.index("erpnext") >= 3


def test_all_127_fixture_schemas_and_coverage_match_registry():
    catalog = json.loads(
        (Path(__file__).parents[1] / "fixtures")
        .joinpath("erpnext-source-schemas.json")
        .read_text()
    )
    coverage = json.loads(
        (Path(__file__).parents[1] / "fixtures")
        .joinpath("erpnext-coverage.json")
        .read_text()
    )
    declared = {entry["name"]: entry for entry in catalog["tools"]}
    actual = tools.tool_definitions("erpnext")
    assert len(declared) == len(actual) == len(coverage["tools"]) == 127
    assert (
        set(declared) == set(actual) == {entry["tool"] for entry in coverage["tools"]}
    )
    for name, entry in declared.items():
        Draft202012Validator.check_schema(entry["inputSchema"])
        assert contract_shape(actual[name].parameters) == contract_shape(
            entry["inputSchema"]
        ), name
        assert actual[name].parameters["additionalProperties"] is False
        assert parameter_descriptions(
            actual[name].parameters
        ) == parameter_descriptions(entry["inputSchema"]), name
        assert actual[name].description == entry["description"]
    for entry in coverage["tools"]:
        assert entry["implemented"] is True and entry["limitations"]
        assert entry["source_path"] == declared[entry["tool"]]["source_path"]
        assert entry["revision"] == catalog["revision"]
        for field in ("success_test", "failure_test"):
            path, test = entry[field].split("::", 1)
            tree = ast.parse(Path(path).read_text())
            assert test.split("[", 1)[0] in {
                node.name for node in tree.body if isinstance(node, ast.FunctionDef)
            }
    tools.validate_registry()
