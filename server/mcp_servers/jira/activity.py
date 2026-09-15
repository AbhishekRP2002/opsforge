"""Jira watcher, comment, worklog, and attachment declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import AliasChoices, Field

from .core import ISSUE


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def jira_get_issue_watchers(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)]
    ) -> ToolResult:
        "List watchers for a Jira issue."
        return await dispatch("jira_get_issue_watchers", {"issue_key": issue_key})

    @mcp.tool
    async def jira_add_watcher(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)], user_identifier: str
    ) -> ToolResult:
        "Add an edition-appropriate user as an issue watcher."
        return await dispatch(
            "jira_add_watcher",
            {"issue_key": issue_key, "user_identifier": user_identifier},
        )

    @mcp.tool
    async def jira_remove_watcher(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        username: str | None = None,
        account_id: str | None = None,
    ) -> ToolResult:
        "Remove an issue watcher by username or Cloud account ID."
        return await dispatch(
            "jira_remove_watcher",
            {"issue_key": issue_key, "username": username, "account_id": account_id},
        )

    @mcp.tool
    async def jira_get_worklog(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)]
    ) -> ToolResult:
        "List worklogs for a Jira issue."
        return await dispatch("jira_get_worklog", {"issue_key": issue_key})

    @mcp.tool
    async def jira_add_comment(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        body: Annotated[str, Field(validation_alias=AliasChoices("body", "comment"))],
        visibility: str | None = None,
        public: bool | None = None,
    ) -> ToolResult:
        "Add a regular or JSM customer-request comment."
        return await dispatch(
            "jira_add_comment",
            {
                "issue_key": issue_key,
                "body": body,
                "visibility": visibility,
                "public": public,
            },
        )

    @mcp.tool
    async def jira_edit_comment(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        comment_id: str,
        body: str,
        visibility: str | None = None,
    ) -> ToolResult:
        "Edit an existing issue comment."
        return await dispatch(
            "jira_edit_comment",
            {
                "issue_key": issue_key,
                "comment_id": comment_id,
                "body": body,
                "visibility": visibility,
            },
        )

    @mcp.tool
    async def jira_add_worklog(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        time_spent: str,
        comment: str | None = None,
        started: str | None = None,
        original_estimate: str | None = None,
        remaining_estimate: str | None = None,
    ) -> ToolResult:
        "Add time spent and optionally update estimates."
        return await dispatch(
            "jira_add_worklog",
            {
                "issue_key": issue_key,
                "time_spent": time_spent,
                "comment": comment,
                "started": started,
                "original_estimate": original_estimate,
                "remaining_estimate": remaining_estimate,
            },
        )

    @mcp.tool
    async def jira_download_attachments(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)]
    ) -> ToolResult:
        "Return issue attachments as embedded MCP resources."
        return await dispatch("jira_download_attachments", {"issue_key": issue_key})

    @mcp.tool
    async def jira_get_issue_images(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)]
    ) -> ToolResult:
        "Return issue image attachments as MCP image content."
        return await dispatch("jira_get_issue_images", {"issue_key": issue_key})

    return (
        jira_get_issue_watchers,
        jira_add_watcher,
        jira_remove_watcher,
        jira_get_worklog,
        jira_add_comment,
        jira_edit_comment,
        jira_add_worklog,
        jira_download_attachments,
        jira_get_issue_images,
    )
