"""Jira ProForma declaration family."""

from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field

from .core import ISSUE


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def jira_get_issue_proforma_forms(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)]
    ) -> ToolResult:
        "List ProForma forms attached to an issue."
        return await dispatch("jira_get_issue_proforma_forms", {"issue_key": issue_key})

    @mcp.tool
    async def jira_get_proforma_form_details(
        *, issue_key: Annotated[str, Field(pattern=ISSUE)], form_id: str
    ) -> ToolResult:
        "Get a ProForma form design and its current answers."
        return await dispatch(
            "jira_get_proforma_form_details",
            {"issue_key": issue_key, "form_id": form_id},
        )

    @mcp.tool
    async def jira_update_proforma_form_answers(
        *,
        issue_key: Annotated[str, Field(pattern=ISSUE)],
        form_id: str,
        answers: Annotated[
            list[dict[str, Any]], Field(description="Typed form answers.")
        ],
    ) -> ToolResult:
        "Validate and update answers on an issue-owned ProForma form."
        return await dispatch(
            "jira_update_proforma_form_answers",
            {"issue_key": issue_key, "form_id": form_id, "answers": answers},
        )

    return (
        jira_get_issue_proforma_forms,
        jira_get_proforma_form_details,
        jira_update_proforma_form_answers,
    )
