"""Jira field, project, component, and version declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from .core import PROJECT


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def jira_search_fields(
        *,
        keyword: str = "",
        limit: Annotated[int, Field(ge=1)] = 10,
        refresh: bool = False,
    ) -> ToolResult:
        "Search the configured Jira field catalog."
        return await dispatch(
            "jira_search_fields",
            {"keyword": keyword, "limit": limit, "refresh": refresh},
        )

    @mcp.tool
    async def jira_get_field_options(
        *,
        field_id: str,
        context_id: str | None = None,
        project_key: str | None = None,
        issue_type: str | None = None,
        contains: str | None = None,
        return_limit: Annotated[int | None, Field(ge=1)] = None,
        values_only: bool = False,
    ) -> ToolResult:
        "List configured options for a Jira field."
        return await dispatch(
            "jira_get_field_options",
            {
                "field_id": field_id,
                "context_id": context_id,
                "project_key": project_key,
                "issue_type": issue_type,
                "contains": contains,
                "return_limit": return_limit,
                "values_only": values_only,
            },
        )

    @mcp.tool
    async def jira_get_project_issue_types(
        *, project_key: Annotated[str, Field(pattern=PROJECT)]
    ) -> ToolResult:
        "List issue types available in a project."
        return await dispatch(
            "jira_get_project_issue_types", {"project_key": project_key}
        )

    @mcp.tool
    async def jira_get_create_fields(
        *, project_key: Annotated[str, Field(pattern=PROJECT)], issue_type_id: str
    ) -> ToolResult:
        "List fields available when creating a project issue type."
        return await dispatch(
            "jira_get_create_fields",
            {"project_key": project_key, "issue_type_id": issue_type_id},
        )

    @mcp.tool
    async def jira_get_project_versions(
        *, project_key: Annotated[str, Field(pattern=PROJECT)]
    ) -> ToolResult:
        "List versions for a Jira project."
        return await dispatch("jira_get_project_versions", {"project_key": project_key})

    @mcp.tool
    async def jira_get_project_components(
        *, project_key: Annotated[str, Field(pattern=PROJECT)]
    ) -> ToolResult:
        "List components for a Jira project."
        return await dispatch(
            "jira_get_project_components", {"project_key": project_key}
        )

    @mcp.tool
    async def jira_get_all_projects(*, include_archived: bool = False) -> ToolResult:
        "List Jira projects visible to the configured environment."
        return await dispatch(
            "jira_get_all_projects", {"include_archived": include_archived}
        )

    @mcp.tool
    async def jira_search_projects(
        *,
        query: str,
        max_results: Annotated[int, Field(ge=1, le=50)] = 20,
        current_project_ids: str | None = None,
    ) -> ToolResult:
        "Search projects by key prefix or name."
        return await dispatch(
            "jira_search_projects",
            {
                "query": query,
                "max_results": max_results,
                "current_project_ids": current_project_ids,
            },
        )

    @mcp.tool
    async def jira_get_project_fields(
        *, project_key: Annotated[str, Field(pattern=PROJECT)]
    ) -> ToolResult:
        "List fields configured for a project."
        return await dispatch("jira_get_project_fields", {"project_key": project_key})

    @mcp.tool
    async def jira_create_version(
        *,
        project_key: Annotated[str, Field(pattern=PROJECT)],
        name: str,
        start_date: str | None = None,
        release_date: str | None = None,
        description: str | None = None,
    ) -> ToolResult:
        "Create a project version."
        return await dispatch(
            "jira_create_version",
            {
                "project_key": project_key,
                "name": name,
                "start_date": start_date,
                "release_date": release_date,
                "description": description,
            },
        )

    @mcp.tool
    async def jira_batch_create_versions(
        *,
        project_key: Annotated[str, Field(pattern=PROJECT)],
        versions: Annotated[str, Field(description="JSON array of version objects.")],
    ) -> ToolResult:
        "Create project versions with per-item outcomes."
        return await dispatch(
            "jira_batch_create_versions",
            {"project_key": project_key, "versions": versions},
        )

    @mcp.tool
    async def jira_update_version(
        *,
        version_id: str,
        name: str | None = None,
        description: str | None = None,
        start_date: str | None = None,
        release_date: str | None = None,
        archived: bool | None = None,
        released: bool | None = None,
    ) -> ToolResult:
        "Update an existing project version."
        return await dispatch(
            "jira_update_version",
            {
                "version_id": version_id,
                "name": name,
                "description": description,
                "start_date": start_date,
                "release_date": release_date,
                "archived": archived,
                "released": released,
            },
        )

    return (
        jira_search_fields,
        jira_get_field_options,
        jira_get_project_issue_types,
        jira_get_create_fields,
        jira_get_project_versions,
        jira_get_project_components,
        jira_get_all_projects,
        jira_search_projects,
        jira_get_project_fields,
        jira_create_version,
        jira_batch_create_versions,
        jira_update_version,
    )
