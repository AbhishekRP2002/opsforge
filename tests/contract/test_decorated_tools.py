"""Public schemas come from the functions FastMCP actually registers."""

import asyncio

from fastmcp.tools.function_tool import FunctionTool
from itops_env.server.interfaces.control import EpisodeBinding
from itops_env.server.mcp_servers import providers


def test_provider_tools_are_typed_fastmcp_functions():
    factory = getattr(providers, "create_provider_server", None)
    assert callable(factory), "Expose the servers built from @mcp.tool functions"

    async def check():
        binding = EpisodeBinding()
        for provider, expected in {
            "okta": {"get_user": {"user_id"}},
            "servicenow": {
                "get_user": {"user_id", "user_name", "email"},
                "add_group_members": {"group_id", "members"},
            },
            "benchmark": {
                "workflow_wait": {"seconds"},
                "workflow_submit": {"disposition", "user_id", "group_id", "summary"},
            },
        }.items():
            server = factory(binding, provider)
            for name, arguments in expected.items():
                tool = await server.get_tool(name)
                assert isinstance(tool, FunctionTool)
                assert set(tool.parameters["properties"]) == arguments
                assert tool.parameters["additionalProperties"] is False
                assert tool.description

    asyncio.run(check())
