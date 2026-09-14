"""Darwinbox recruitment tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def get_job_listings(
        *,
        job_updated_timestamp_from: Annotated[
            str,
            Field(
                description="Fetch jobs updated after this timestamp (DD-MM-YYYY HH:mm:ss format)"
            ),
        ],
    ) -> ToolResult:
        "Retrieve a list of all open jobs updated after a specified timestamp."
        return await dispatch(
            "get_job_listings",
            {"job_updated_timestamp_from": job_updated_timestamp_from},
        )

    @mcp.tool
    async def get_job_detail(
        *,
        job_id: Annotated[
            str, Field(description="Unique identifier of the job to fetch details for")
        ],
    ) -> ToolResult:
        "Get detailed information about a specific job posting."
        return await dispatch("get_job_detail", {"job_id": job_id})

    @mcp.tool
    async def get_bulk_candidates(
        *,
        updated_from: Annotated[
            str, Field(description="Start timestamp (DD-MM-YYYY HH:mm:ss format)")
        ],
        updated_to: Annotated[
            str, Field(description="End timestamp (DD-MM-YYYY HH:mm:ss format)")
        ],
    ) -> ToolResult:
        "Retrieve candidate data for applications within a specified time range."
        return await dispatch(
            "get_bulk_candidates",
            {"updated_from": updated_from, "updated_to": updated_to},
        )

    return (
        get_job_listings,
        get_job_detail,
        get_bulk_candidates,
    )
