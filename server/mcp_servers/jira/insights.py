"""Jira date, SLA, development, and dependency declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from .core import ISSUE, PROJECT


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def jira_get_issue_dates(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        include_status_changes: bool = True,
        include_status_summary: bool = True,
    ) -> ToolResult:
        "Get issue timestamps and status-duration history."
        return await dispatch(
            "jira_get_issue_dates",
            {
                "issue_key": issue_key,
                "include_status_changes": include_status_changes,
                "include_status_summary": include_status_summary,
            },
        )

    @mcp.tool
    async def jira_get_issue_sla(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        metrics: str | None = None,
        working_hours_only: bool | None = None,
        include_raw_dates: bool = False,
    ) -> ToolResult:
        "Calculate deterministic SLA metrics from issue history."
        return await dispatch(
            "jira_get_issue_sla",
            {
                "issue_key": issue_key,
                "metrics": metrics,
                "working_hours_only": working_hours_only,
                "include_raw_dates": include_raw_dates,
            },
        )

    @mcp.tool
    async def jira_get_issue_development_info(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        application_type: str | None = None,
        data_type: str | None = None,
    ) -> ToolResult:
        "Get configured development records for one issue."
        return await dispatch(
            "jira_get_issue_development_info",
            {
                "issue_key": issue_key,
                "application_type": application_type,
                "data_type": data_type,
            },
        )

    @mcp.tool
    async def jira_get_issues_development_info(
        *,
        issue_keys: str,
        application_type: str | None = None,
        data_type: str | None = None,
    ) -> ToolResult:
        "Get configured development records for multiple issues."
        return await dispatch(
            "jira_get_issues_development_info",
            {
                "issue_keys": issue_keys,
                "application_type": application_type,
                "data_type": data_type,
            },
        )

    @mcp.tool
    async def jira_get_project_epic_hierarchy(
        *,
        project_key: Annotated[str, Field(pattern=PROJECT)],
        max_epics: Annotated[int, Field(ge=1, le=500)] = 200,
    ) -> ToolResult:
        "Get project Epics and their direct issue children."
        return await dispatch(
            "jira_get_project_epic_hierarchy",
            {"project_key": project_key, "max_epics": max_epics},
        )

    @mcp.tool
    async def jira_get_cross_project_dependencies(
        *,
        project_key: Annotated[str, Field(pattern=PROJECT)],
        max_issues: Annotated[int, Field(ge=1, le=500)] = 200,
    ) -> ToolResult:
        "Get linked issues whose endpoints belong to different projects."
        return await dispatch(
            "jira_get_cross_project_dependencies",
            {"project_key": project_key, "max_issues": max_issues},
        )

    return (
        jira_get_issue_dates,
        jira_get_issue_sla,
        jira_get_issue_development_info,
        jira_get_issues_development_info,
        jira_get_project_epic_hierarchy,
        jira_get_cross_project_dependencies,
    )
