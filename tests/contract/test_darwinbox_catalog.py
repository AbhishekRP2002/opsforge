import ast
import json
from copy import deepcopy
from pathlib import Path

from itops_env.server.mcp_servers import tools
from jsonschema import Draft202012Validator

from .schema_contracts import contract_shape, parameter_descriptions

NAMES = {
    "get_employee_details",
    "update_employee",
    "get_employee_history",
    "download_personal_docs",
    "get_position_master",
    "get_forms_data",
    "get_separation_details",
    "add_employee",
    "deactivate_employee",
    "upload_profile_attachments",
    "get_monthly_attendance",
    "record_attendance_punches",
    "get_daily_attendance",
    "get_attendance_roster",
    "record_backdated_attendance",
    "approve_leave",
    "get_leave_action_history",
    "get_holiday_list",
    "apply_leave",
    "get_leave_balance",
    "get_job_listings",
    "get_job_detail",
    "get_bulk_candidates",
}


def test_exact_source_schemas_two_repairs_and_complete_execution_catalog():
    definitions = tools.tool_definitions("darwinbox")
    source = json.loads(
        (Path(__file__).parents[1] / "fixtures")
        .joinpath("darwinbox-source-schemas.json")
        .read_text()
    )
    assert set(definitions) == NAMES
    assert list(tools.REGISTRARS)[:5] == [
        "okta",
        "servicenow",
        "benchmark",
        "erpnext",
        "darwinbox",
    ]
    for entry in source["tools"]:
        expected = deepcopy(entry["raw_input_schema"])
        if entry["name"] == "get_employee_details":
            del expected["oneOf"]
        elif entry["name"] == "update_employee":
            del expected["properties"]["employee_data"]["required"]
        elif entry["name"] == "apply_leave":
            # Upstream defaults on required TypedDict keys are documentation only.
            # Field defaults would weaken requiredness and populate omitted keys.
            item = expected["properties"]["data"]["items"]
            for field, default in {
                "is_half_day": "No",
                "is_paid_or_unpaid": "paid",
                "revoke_leave": "No",
                "is_firsthalf_secondhalf": "1",
            }.items():
                assert item["properties"][field].pop("default") == default
        actual = definitions[entry["name"]]
        assert contract_shape(actual.parameters) == contract_shape(expected), entry[
            "name"
        ]
        assert actual.parameters["additionalProperties"] is False
        assert parameter_descriptions(actual.parameters) == parameter_descriptions(
            expected
        ), entry["name"]
        assert actual.description == entry["description"]
        Draft202012Validator.check_schema(actual.parameters)
    tools.validate_registry()
    assert (
        tools.argument_error(
            "darwinbox",
            "get_employee_details",
            {"employee_ids": [], "last_modified": "ignored"},
        )
        is None
    )
    assert tools.argument_error("darwinbox", "update_employee", {}) is not None
    assert (
        tools.argument_error(
            "darwinbox", "apply_leave", {"data": [{"employee_no": "E1"}]}
        )
        is not None
    )


def test_fixture_coverage_records_have_runnable_success_failure_nodes():
    coverage = json.loads(
        (Path(__file__).parents[1] / "fixtures")
        .joinpath("darwinbox-coverage.json")
        .read_text()
    )
    assert {row["tool"] for row in coverage["tools"]} == NAMES
    for row in coverage["tools"]:
        assert row["implemented"] is True and row["limitations"]
        assert row["revision"] == "9c586d53c8ae1c5449a1a55ea1b57ae011152970"
        assert row["source_path"] == "src/index.ts"
        for key in ("success_test", "failure_test"):
            file, node = row[key].split("::", 1)
            names = {
                part.name
                for part in ast.walk(ast.parse(Path(file).read_text()))
                if isinstance(part, ast.FunctionDef)
            }
            assert node.split("[", 1)[0] in names
