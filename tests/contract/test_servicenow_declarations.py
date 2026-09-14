"""Independent source contracts retain all ServiceNow constraints and evidence."""

import ast
import json
from pathlib import Path

from itops_env.server.mcp_servers import tools

from .schema_contracts import contract_shape, parameter_descriptions


def test_servicenow_discovery_preserves_source_constraints_and_execution_coverage():
    fixtures = Path(__file__).parents[1] / "fixtures"
    metadata = json.loads((fixtures / "servicenow-source-schemas.json").read_text())
    coverage = json.loads((fixtures / "servicenow-coverage.json").read_text())
    definitions = tools.tool_definitions("servicenow")
    assert (
        set(definitions)
        == {row["name"] for row in metadata["tools"]}
        == {row["name"] for row in coverage["tools"]}
    )
    assert len(definitions) == 82
    for entry in metadata["tools"]:
        if entry["name"] not in {"get_user", "add_group_members"}:
            actual = definitions[entry["name"]]
            assert contract_shape(actual.parameters) == contract_shape(
                entry["input_schema"]
            ), entry["name"]
            assert actual.parameters["additionalProperties"] is False
            assert parameter_descriptions(actual.parameters) == parameter_descriptions(
                entry["input_schema"]
            ), entry["name"]
            assert actual.description == entry["description"]
    for row in coverage["tools"]:
        assert (
            row["success_test"]
            and row["failure_test"]
            and row["limitations"]
            and row["status"] == "implemented"
        )
        for field in ("success_test", "failure_test"):
            path, test = row[field].split("::", 1)
            nodes = ast.walk(ast.parse(Path(path).read_text()))
            assert test.split("[", 1)[0] in {
                node.name for node in nodes if isinstance(node, ast.FunctionDef)
            }
