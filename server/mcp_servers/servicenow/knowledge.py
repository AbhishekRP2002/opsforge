"""Servicenow knowledge tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def create_knowledge_base(
        *,
        title: Annotated[str, Field(description="Title of the knowledge base")],
        description: Annotated[
            str | None, Field(description="Description of the knowledge base")
        ] = None,
        owner: Annotated[
            str | None, Field(description="The specified admin user or group")
        ] = None,
        managers: Annotated[
            str | None, Field(description="Users who can manage this knowledge base")
        ] = None,
        publish_workflow: Annotated[
            str | None, Field(description="Publication workflow")
        ] = "Knowledge - Instant Publish",
        retire_workflow: Annotated[
            str | None, Field(description="Retirement workflow")
        ] = "Knowledge - Instant Retire",
    ) -> ToolResult:
        "Create a new knowledge base in ServiceNow"
        return await dispatch(
            "create_knowledge_base",
            {
                "title": title,
                "description": description,
                "owner": owner,
                "managers": managers,
                "publish_workflow": publish_workflow,
                "retire_workflow": retire_workflow,
            },
        )

    @mcp.tool
    async def list_knowledge_bases(
        *,
        limit: Annotated[
            int, Field(description="Maximum number of knowledge bases to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        active: Annotated[
            bool | None, Field(description="Filter by active status")
        ] = None,
        query: Annotated[
            str | None, Field(description="Search query for knowledge bases")
        ] = None,
    ) -> ToolResult:
        "List knowledge bases from ServiceNow"
        return await dispatch(
            "list_knowledge_bases",
            {"limit": limit, "offset": offset, "active": active, "query": query},
        )

    @mcp.tool
    async def create_category(
        *,
        title: Annotated[str, Field(description="Title of the category")],
        description: Annotated[
            str | None, Field(description="Description of the category")
        ] = None,
        knowledge_base: Annotated[
            str, Field(description="The knowledge base to create the category in")
        ],
        parent_category: Annotated[
            str | None,
            Field(
                description="Parent category (if creating a subcategory). Sys_id refering to the parent category or sys_id of the parent table."
            ),
        ] = None,
        parent_table: Annotated[
            str | None,
            Field(
                description="Parent table (if creating a subcategory). Sys_id refering to the table where the parent category is defined."
            ),
        ] = None,
        active: Annotated[
            bool, Field(description="Whether the category is active")
        ] = True,
    ) -> ToolResult:
        "Create a new category in a knowledge base"
        return await dispatch(
            "create_category",
            {
                "title": title,
                "description": description,
                "knowledge_base": knowledge_base,
                "parent_category": parent_category,
                "parent_table": parent_table,
                "active": active,
            },
        )

    @mcp.tool
    async def create_article(
        *,
        title: Annotated[str, Field(description="Title of the article")],
        text: Annotated[
            str,
            Field(
                description="The main body text for the article. Field supports html formatting and wiki markup based on the article_type. HTML is the default."
            ),
        ],
        short_description: Annotated[
            str, Field(description="Short description of the article")
        ],
        knowledge_base: Annotated[
            str, Field(description="The knowledge base to create the article in")
        ],
        category: Annotated[str, Field(description="Category for the article")],
        keywords: Annotated[
            str | None, Field(description="Keywords for search")
        ] = None,
        article_type: Annotated[
            str | None,
            Field(
                description="The type of article. Options are 'text' or 'wiki'. text lets the text field support html formatting. wiki lets the text field support wiki markup."
            ),
        ] = "html",
    ) -> ToolResult:
        "Create a new knowledge article"
        return await dispatch(
            "create_article",
            {
                "title": title,
                "text": text,
                "short_description": short_description,
                "knowledge_base": knowledge_base,
                "category": category,
                "keywords": keywords,
                "article_type": article_type,
            },
        )

    @mcp.tool
    async def update_article(
        *,
        article_id: Annotated[str, Field(description="ID of the article to update")],
        title: Annotated[
            str | None, Field(description="Updated title of the article")
        ] = None,
        text: Annotated[
            str | None,
            Field(
                description="Updated main body text for the article. Field supports html formatting and wiki markup based on the article_type. HTML is the default."
            ),
        ] = None,
        short_description: Annotated[
            str | None, Field(description="Updated short description")
        ] = None,
        category: Annotated[
            str | None, Field(description="Updated category for the article")
        ] = None,
        keywords: Annotated[
            str | None, Field(description="Updated keywords for search")
        ] = None,
    ) -> ToolResult:
        "Update an existing knowledge article"
        return await dispatch(
            "update_article",
            {
                "article_id": article_id,
                "title": title,
                "text": text,
                "short_description": short_description,
                "category": category,
                "keywords": keywords,
            },
        )

    @mcp.tool
    async def publish_article(
        *,
        article_id: Annotated[str, Field(description="ID of the article to publish")],
        workflow_state: Annotated[
            str | None, Field(description="The workflow state to set")
        ] = "published",
        workflow_version: Annotated[
            str | None, Field(description="The workflow version to use")
        ] = None,
    ) -> ToolResult:
        "Publish a knowledge article"
        return await dispatch(
            "publish_article",
            {
                "article_id": article_id,
                "workflow_state": workflow_state,
                "workflow_version": workflow_version,
            },
        )

    @mcp.tool
    async def list_articles(
        *,
        limit: Annotated[
            int, Field(description="Maximum number of articles to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        knowledge_base: Annotated[
            str | None, Field(description="Filter by knowledge base")
        ] = None,
        category: Annotated[str | None, Field(description="Filter by category")] = None,
        query: Annotated[
            str | None, Field(description="Search query for articles")
        ] = None,
        workflow_state: Annotated[
            str | None, Field(description="Filter by workflow state")
        ] = None,
    ) -> ToolResult:
        "List knowledge articles"
        return await dispatch(
            "list_articles",
            {
                "limit": limit,
                "offset": offset,
                "knowledge_base": knowledge_base,
                "category": category,
                "query": query,
                "workflow_state": workflow_state,
            },
        )

    @mcp.tool
    async def get_article(
        *,
        article_id: Annotated[str, Field(description="ID of the article to get")],
    ) -> ToolResult:
        "Get a specific knowledge article by ID"
        return await dispatch("get_article", {"article_id": article_id})

    @mcp.tool
    async def list_categories(
        *,
        knowledge_base: Annotated[
            str | None, Field(description="Filter by knowledge base ID")
        ] = None,
        parent_category: Annotated[
            str | None, Field(description="Filter by parent category ID")
        ] = None,
        limit: Annotated[
            int, Field(description="Maximum number of categories to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        active: Annotated[
            bool | None, Field(description="Filter by active status")
        ] = None,
        query: Annotated[
            str | None, Field(description="Search query for categories")
        ] = None,
    ) -> ToolResult:
        "List categories in a knowledge base"
        return await dispatch(
            "list_categories",
            {
                "knowledge_base": knowledge_base,
                "parent_category": parent_category,
                "limit": limit,
                "offset": offset,
                "active": active,
                "query": query,
            },
        )

    return (
        create_knowledge_base,
        list_knowledge_bases,
        create_category,
        create_article,
        update_article,
        publish_article,
        list_articles,
        get_article,
        list_categories,
    )
