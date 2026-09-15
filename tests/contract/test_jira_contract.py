"""Pinned Jira source identity versus executable FastMCP declarations."""

import json
from pathlib import Path

from itops_env.server.mcp_servers import tools
from jsonschema import Draft202012Validator

FIXTURE = Path(__file__).parents[1] / "fixtures" / "jira-source-contracts.json"


def source_contracts():
    return json.loads(FIXTURE.read_text())


def test_jira_exact_source_names_schemas_and_handlers():
    source = source_contracts()
    assert source["source"] == {
        "repository": "https://github.com/sooperset/mcp-atlassian",
        "revision": "74bdaa8f1d28783cccfe99f7b4d75e6dc947cf76",
        "provider": "atlassian_jira",
    }
    expected = {item["mounted_name"]: item for item in source["tools"]}
    definitions = tools.tool_definitions("jira")
    assert len(expected) == len(definitions) == 63
    assert set(expected) == set(definitions)
    assert set(tools.HANDLER_RESOLVERS["jira"]()) == set(expected)
    assert all(
        item["mounted_name"] == "jira_" + item["source_name"]
        for item in source["tools"]
    )
    for name, declaration in definitions.items():
        schema = declaration.parameters
        Draft202012Validator.check_schema(schema)
        assert schema["additionalProperties"] is False
        assert sorted(schema["properties"]) == expected[name]["properties"]
        assert sorted(schema.get("required", [])) == expected[name]["required"]
        assert declaration.description


def test_selected_provider_counts_exclude_confluence():
    counts = {
        provider: len(tools.tool_definitions(provider)) for provider in tools.REGISTRARS
    }
    assert counts == {
        "okta": 112,
        "servicenow": 82,
        "benchmark": 2,
        "erpnext": 127,
        "darwinbox": 23,
        "jira": 63,
    }
    assert len(tools.business_tool_names()) == 407
    assert not any("confluence" in name for name in tools.business_tool_names())
    tools.validate_registry()
