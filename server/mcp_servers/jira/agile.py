"""Jira board, sprint, and backlog declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from .core import DEFAULT_FIELDS, PROJECT


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def jira_get_agile_boards(
        *,
        board_name: str | None = None,
        project_key: Annotated[str | None, Field(pattern=PROJECT)] = None,
        board_type: str | None = None,
        start_at: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> ToolResult:
        "List Jira agile boards."
        return await dispatch(
            "jira_get_agile_boards",
            {
                "board_name": board_name,
                "project_key": project_key,
                "board_type": board_type,
                "start_at": start_at,
                "limit": limit,
            },
        )

    @mcp.tool
    async def jira_get_board_issues(
        *,
        board_id: str,
        jql: str,
        fields: str = DEFAULT_FIELDS,
        start_at: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
        expand: str = "version",
    ) -> ToolResult:
        "Search issues within a Jira board's projects."
        return await dispatch(
            "jira_get_board_issues",
            {
                "board_id": board_id,
                "jql": jql,
                "fields": fields,
                "start_at": start_at,
                "limit": limit,
                "expand": expand,
            },
        )

    @mcp.tool
    async def jira_get_sprints_from_board(
        *,
        board_id: str,
        state: str | None = None,
        start_at: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> ToolResult:
        "List sprints from a Jira scrum board."
        return await dispatch(
            "jira_get_sprints_from_board",
            {
                "board_id": board_id,
                "state": state,
                "start_at": start_at,
                "limit": limit,
            },
        )

    @mcp.tool
    async def jira_get_sprint_issues(
        *,
        sprint_id: str,
        fields: str = DEFAULT_FIELDS,
        start_at: Annotated[int, Field(ge=0)] = 0,
        limit: Annotated[int, Field(ge=1, le=50)] = 10,
    ) -> ToolResult:
        "List issues assigned to a sprint."
        return await dispatch(
            "jira_get_sprint_issues",
            {
                "sprint_id": sprint_id,
                "fields": fields,
                "start_at": start_at,
                "limit": limit,
            },
        )

    @mcp.tool
    async def jira_create_sprint(
        *,
        board_id: str,
        name: str,
        start_date: str,
        end_date: str,
        goal: str | None = None,
    ) -> ToolResult:
        "Create a future sprint on a scrum board."
        return await dispatch(
            "jira_create_sprint",
            {
                "board_id": board_id,
                "name": name,
                "start_date": start_date,
                "end_date": end_date,
                "goal": goal,
            },
        )

    @mcp.tool
    async def jira_update_sprint(
        *,
        sprint_id: str,
        name: str | None = None,
        state: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        goal: str | None = None,
    ) -> ToolResult:
        "Update sprint fields or advance its lifecycle."
        return await dispatch(
            "jira_update_sprint",
            {
                "sprint_id": sprint_id,
                "name": name,
                "state": state,
                "start_date": start_date,
                "end_date": end_date,
                "goal": goal,
            },
        )

    @mcp.tool
    async def jira_add_issues_to_sprint(
        *, sprint_id: str, issue_keys: str
    ) -> ToolResult:
        "Assign comma-separated issues to a sprint."
        return await dispatch(
            "jira_add_issues_to_sprint",
            {"sprint_id": sprint_id, "issue_keys": issue_keys},
        )

    @mcp.tool
    async def jira_move_issues_to_backlog(*, issue_keys: str) -> ToolResult:
        "Move comma-separated issues out of their sprints."
        return await dispatch("jira_move_issues_to_backlog", {"issue_keys": issue_keys})

    return (
        jira_get_agile_boards,
        jira_get_board_issues,
        jira_get_sprints_from_board,
        jira_get_sprint_issues,
        jira_create_sprint,
        jira_update_sprint,
        jira_add_issues_to_sprint,
        jira_move_issues_to_backlog,
    )
