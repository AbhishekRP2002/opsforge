"""Provider-specific public arguments generated from typed tools."""

from itops_env.server.mcp_servers.tools import tool_schema


def test_get_user_schemas_preserve_provider_specific_arguments():
    okta = tool_schema("okta", "get_user")
    servicenow = tool_schema("servicenow", "get_user")

    assert okta["required"] == ["user_id"]
    assert set(okta["properties"]) == {"user_id"}
    assert okta["properties"]["user_id"]["type"] == "string"

    assert "required" not in servicenow
    assert set(servicenow["properties"]) == {"user_id", "user_name", "email"}
    for property_name in ("user_id", "user_name", "email"):
        property_schema = servicenow["properties"][property_name]
        assert property_schema["anyOf"] == [{"type": "string"}, {"type": "null"}]
        assert property_schema["default"] is None


def test_add_group_members_schema_accepts_every_upstream_argument():
    schema = tool_schema("servicenow", "add_group_members")

    assert set(schema["properties"]) == {"group_id", "members"}
    assert schema["required"] == ["group_id", "members"]
    assert schema["properties"]["group_id"]["type"] == "string"
    assert schema["properties"]["members"]["type"] == "array"
    assert schema["properties"]["members"]["items"] == {"type": "string"}
