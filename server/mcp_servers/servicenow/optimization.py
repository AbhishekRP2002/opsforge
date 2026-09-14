"""Servicenow optimization tool declarations."""

from fastmcp import FastMCP
from fastmcp.tools import ToolResult


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_optimization_recommendations(
        *,
        recommendation_types: list[str],
        category_id: str | None = None,
    ) -> ToolResult:
        "Get optimization recommendations for the service catalog."
        return await dispatch(
            "get_optimization_recommendations",
            {"recommendation_types": recommendation_types, "category_id": category_id},
        )

    return (get_optimization_recommendations,)
