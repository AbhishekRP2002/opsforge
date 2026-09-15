"""Jira tools grouped by source service family."""

from . import activity, agile, core, forms, insights, metadata, service_desk, workflow


def register_tools(mcp, dispatch):
    return (
        *core.register_tools(mcp, dispatch),
        *activity.register_tools(mcp, dispatch),
        *metadata.register_tools(mcp, dispatch),
        *workflow.register_tools(mcp, dispatch),
        *agile.register_tools(mcp, dispatch),
        *service_desk.register_tools(mcp, dispatch),
        *forms.register_tools(mcp, dispatch),
        *insights.register_tools(mcp, dispatch),
    )
