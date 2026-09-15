"""Jira issue, user, and search tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

ISSUE = r"^[A-Z][A-Z0-9_]+-[1-9][0-9]*$"
PROJECT = r"^[A-Z][A-Z0-9_]+$"
DEFAULT_FIELDS = "summary,description,status,assignee,reporter,labels,versions,priority,created,updated,issuetype"


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def jira_get_user_profile(
        *,
        user_identifier: Annotated[
            str, Field(description="Email, username, account ID, user key, or 'me'.")
        ],
    ) -> ToolResult:
        "Get a Jira user profile."
        return await dispatch(
            "jira_get_user_profile", {"user_identifier": user_identifier}
        )

    @mcp.tool
    async def jira_search_assignable_users(
        *,
        query: Annotated[
            str, Field(description="Display-name, username, or email substring.")
        ],
        project_key: str | None = None,
        issue_key: str | None = None,
        limit: Annotated[int, Field(ge=1, le=1000)] = 20,
    ) -> ToolResult:
        "Search users assignable to exactly one project or issue scope."
        return await dispatch(
            "jira_search_assignable_users",
            {
                "query": query,
                "project_key": project_key,
                "issue_key": issue_key,
                "limit": limit,
            },
        )

    @mcp.tool
    async def jira_get_issue(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        fields: str = DEFAULT_FIELDS,
        expand: str | None = None,
        comment_limit: Annotated[int, Field(ge=0, le=100)] = 10,
        properties: str | None = None,
        update_history: bool = True,
        include: str | None = None,
        use_display_names: bool = False,
    ) -> ToolResult:
        "Get a Jira issue with selectable fields and related sections."
        return await dispatch(
            "jira_get_issue",
            {
                "issue_key": issue_key,
                "fields": fields,
                "expand": expand,
                "comment_limit": comment_limit,
                "properties": properties,
                "update_history": update_history,
                "include": include,
                "use_display_names": use_display_names,
            },
        )

    @mcp.tool
    async def jira_search(
        *,
        jql: Annotated[str, Field(description="Jira Query Language expression.")],
        fields: str = DEFAULT_FIELDS,
        limit: Annotated[int, Field(ge=1)] = 10,
        start_at: Annotated[int, Field(ge=0)] = 0,
        projects_filter: str | None = None,
        expand: str | None = None,
        page_token: str | None = None,
        use_display_names: bool = False,
    ) -> ToolResult:
        "Search Jira issues using the supported finite JQL profile."
        return await dispatch(
            "jira_search",
            {
                "jql": jql,
                "fields": fields,
                "limit": limit,
                "start_at": start_at,
                "projects_filter": projects_filter,
                "expand": expand,
                "page_token": page_token,
                "use_display_names": use_display_names,
            },
        )

    @mcp.tool
    async def jira_get_project_issues(
        *,
        project_key: Annotated[str, Field(pattern=PROJECT)],
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
        start_at: Annotated[int, Field(ge=0)] = 0,
    ) -> ToolResult:
        "List issues in a Jira project."
        return await dispatch(
            "jira_get_project_issues",
            {"project_key": project_key, "limit": limit, "start_at": start_at},
        )

    @mcp.tool
    async def jira_create_issue(
        *,
        project_key: Annotated[str, Field(pattern=PROJECT)],
        summary: str,
        issue_type: str,
        assignee: str | None = None,
        description: str | None = None,
        components: str | None = None,
        additional_fields: str | None = None,
    ) -> ToolResult:
        "Create a Jira issue."
        return await dispatch(
            "jira_create_issue",
            {
                "project_key": project_key,
                "summary": summary,
                "issue_type": issue_type,
                "assignee": assignee,
                "description": description,
                "components": components,
                "additional_fields": additional_fields,
            },
        )

    @mcp.tool
    async def jira_batch_create_issues(
        *,
        issues: Annotated[str, Field(description="JSON array of issue objects.")],
        validate_only: bool = False,
    ) -> ToolResult:
        "Validate or create a batch of Jira issues."
        return await dispatch(
            "jira_batch_create_issues",
            {"issues": issues, "validate_only": validate_only},
        )

    @mcp.tool
    async def jira_update_issue(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        fields: str | None = None,
        additional_fields: str | None = None,
        components: str | None = None,
        attachments: str | None = None,
        transition: str | None = None,
        comment: str | None = None,
        comment_visibility: str | None = None,
        worklog: str | None = None,
        worklog_started: str | None = None,
        return_fields: str = "*all",
    ) -> ToolResult:
        "Apply ordered Jira issue operations and report partial outcomes."
        return await dispatch(
            "jira_update_issue",
            {
                "issue_key": issue_key,
                "fields": fields,
                "additional_fields": additional_fields,
                "components": components,
                "attachments": attachments,
                "transition": transition,
                "comment": comment,
                "comment_visibility": comment_visibility,
                "worklog": worklog,
                "worklog_started": worklog_started,
                "return_fields": return_fields,
            },
        )

    @mcp.tool
    async def jira_assign_issue(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)], assignee: str | None = None
    ) -> ToolResult:
        "Assign or unassign a Jira issue."
        return await dispatch(
            "jira_assign_issue", {"issue_key": issue_key, "assignee": assignee}
        )

    @mcp.tool
    async def jira_delete_issue(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)]
    ) -> ToolResult:
        "Delete a Jira issue that has no children."
        return await dispatch("jira_delete_issue", {"issue_key": issue_key})

    @mcp.tool
    async def jira_move_issue(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        target_project_key: Annotated[str, Field(pattern=PROJECT)],
    ) -> ToolResult:
        "Move a Jira Cloud issue to another project while preserving stable identity."
        return await dispatch(
            "jira_move_issue",
            {"issue_key": issue_key, "target_project_key": target_project_key},
        )

    return (
        jira_get_user_profile,
        jira_search_assignable_users,
        jira_get_issue,
        jira_search,
        jira_get_project_issues,
        jira_create_issue,
        jira_batch_create_issues,
        jira_update_issue,
        jira_assign_issue,
        jira_delete_issue,
        jira_move_issue,
    )
