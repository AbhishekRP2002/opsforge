"""Darwinbox tool declarations grouped by service family."""

from . import (
    attendance,
    core,
    masters,
    recruitment,
    timeoff,
)


def register_tools(mcp, dispatch):
    return (
        *core.register_tools(mcp, dispatch),
        *attendance.register_tools(mcp, dispatch),
        *masters.register_tools(mcp, dispatch),
        *recruitment.register_tools(mcp, dispatch),
        *timeoff.register_tools(mcp, dispatch),
    )
