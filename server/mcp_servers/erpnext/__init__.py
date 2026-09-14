"""Erpnext tool declarations grouped by service family."""

from . import (
    accounting_hr,
    analytics,
    business,
    commerce,
    kanban,
    operations,
    projects,
)


def register_tools(mcp, dispatch):
    return (
        *operations.register_tools(mcp, dispatch),
        *projects.register_tools(mcp, dispatch),
        *commerce.register_tools(mcp, dispatch),
        *accounting_hr.register_tools(mcp, dispatch),
        *business.register_tools(mcp, dispatch),
        *analytics.register_tools(mcp, dispatch),
        *kanban.register_tools(mcp, dispatch),
    )
