import json
from pathlib import Path

import pytest
from itops_env.server.mcp_servers.tools import tool_definitions, validate_registry

CONTRACTS = json.loads(
    (Path(__file__).parents[1] / "fixtures").joinpath("okta_contracts.json").read_text()
)


def _shape(value):
    return {
        key: [_shape(item) for item in content]
        if isinstance(content, list) and key == "anyOf"
        else _shape(content)
        if isinstance(content, dict)
        else content
        for key, content in value.items()
        if key not in {"title", "description", "additionalProperties"}
    }


@pytest.mark.parametrize("tool", sorted(CONTRACTS))
def test_each_okta_schema_matches_pinned_source(tool):
    expected = CONTRACTS[tool]
    actual = tool_definitions("okta")[tool].parameters
    assert _shape(actual["properties"]) == expected["properties"]
    assert actual.get("required", []) == expected["required"]


def test_exact_112_okta_tools_have_registered_handlers():
    validate_registry()
    assert len(CONTRACTS) == 112
    assert set(tool_definitions("okta")) == set(CONTRACTS)


def test_fixture_coverage_is_self_contained_and_covers_all_112_tools():
    manifest = json.loads(
        (Path(__file__).parents[1] / "fixtures")
        .joinpath("okta_extended.json")
        .read_text()
    )
    assert manifest["source"]["commit"] == "1eb0c943069fe887b607acb5360d34478f8007f8"
    assert manifest["tool_count"] == 112
    assert set(manifest["tools"]) == set(CONTRACTS)
    for name, tool in manifest["tools"].items():
        assert tool["source_file"] == CONTRACTS[name]["source_file"]
        assert tool["source_function"] == CONTRACTS[name]["source_function"]
        assert tool["status"] in {"implemented", "headless_confirmation_only"}
        assert tool["limitations"] and tool["tests"]
        assert all(
            node.startswith("tests/") and "::test_" in node for node in tool["tests"]
        )
    assert manifest["tools"]["delete_brand"]["status"] == "headless_confirmation_only"
    assert (
        manifest["tools"]["delete_custom_domain"]["status"]
        == "headless_confirmation_only"
    )
