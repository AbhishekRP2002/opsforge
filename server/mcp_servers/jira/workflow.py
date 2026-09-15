"""Jira workflow and issue-link declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from .core import ISSUE


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def jira_get_transitions(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)]
    ) -> ToolResult:
        "List transitions available from an issue's current status."
        return await dispatch("jira_get_transitions", {"issue_key": issue_key})

    @mcp.tool
    async def jira_get_link_types(*, name_filter: str | None = None) -> ToolResult:
        "List issue-link types, optionally filtered by name."
        return await dispatch("jira_get_link_types", {"name_filter": name_filter})

    @mcp.tool
    async def jira_batch_get_changelogs(
        *, issue_ids_or_keys: str, fields: str | None = None, limit: int = -1
    ) -> ToolResult:
        "Get Cloud changelogs for multiple issue IDs or keys."
        return await dispatch(
            "jira_batch_get_changelogs",
            {"issue_ids_or_keys": issue_ids_or_keys, "fields": fields, "limit": limit},
        )

    @mcp.tool
    async def jira_create_issue_link(
        *,
        link_type: str,
        inward_issue_key: Annotated[str, Field(pattern=ISSUE)],
        outward_issue_key: Annotated[str, Field(pattern=ISSUE)],
        comment: str | None = None,
        comment_visibility: str | None = None,
    ) -> ToolResult:
        "Create a directed link between two Jira issues."
        return await dispatch(
            "jira_create_issue_link",
            {
                "link_type": link_type,
                "inward_issue_key": inward_issue_key,
                "outward_issue_key": outward_issue_key,
                "comment": comment,
                "comment_visibility": comment_visibility,
            },
        )

    @mcp.tool
    async def jira_create_remote_issue_link(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        url: str,
        title: str,
        summary: str | None = None,
        relationship: str | None = None,
        icon_url: str | None = None,
    ) -> ToolResult:
        "Attach a remote URL to a Jira issue."
        return await dispatch(
            "jira_create_remote_issue_link",
            {
                "issue_key": issue_key,
                "url": url,
                "title": title,
                "summary": summary,
                "relationship": relationship,
                "icon_url": icon_url,
            },
        )

    @mcp.tool
    async def jira_remove_issue_link(*, link_id: str) -> ToolResult:
        "Remove a Jira issue link."
        return await dispatch("jira_remove_issue_link", {"link_id": link_id})

    @mcp.tool
    async def jira_transition_issue(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        transition_id: str,
        fields: str | None = None,
        comment: str | None = None,
    ) -> ToolResult:
        "Transition an issue and optionally update transition fields."
        return await dispatch(
            "jira_transition_issue",
            {
                "issue_key": issue_key,
                "transition_id": transition_id,
                "fields": fields,
                "comment": comment,
            },
        )

    @mcp.tool
    async def jira_link_to_epic(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        epic_key: Annotated[str, Field(pattern=ISSUE)],
    ) -> ToolResult:
        "Link an issue to an Epic."
        return await dispatch(
            "jira_link_to_epic", {"issue_key": issue_key, "epic_key": epic_key}
        )

    return (
        jira_get_transitions,
        jira_get_link_types,
        jira_batch_get_changelogs,
        jira_create_issue_link,
        jira_create_remote_issue_link,
        jira_remove_issue_link,
        jira_transition_issue,
        jira_link_to_epic,
    )
