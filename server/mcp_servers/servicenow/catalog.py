"""Servicenow catalog tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def list_catalog_items(
        *,
        limit: Annotated[
            int, Field(description="Maximum number of catalog items to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        category: Annotated[str | None, Field(description="Filter by category")] = None,
        query: Annotated[
            str | None, Field(description="Search query for catalog items")
        ] = None,
        active: Annotated[
            bool, Field(description="Whether to only return active catalog items")
        ] = True,
    ) -> ToolResult:
        "List service catalog items."
        return await dispatch(
            "list_catalog_items",
            {
                "limit": limit,
                "offset": offset,
                "category": category,
                "query": query,
                "active": active,
            },
        )

    @mcp.tool
    async def get_catalog_item(
        *,
        item_id: Annotated[str, Field(description="Catalog item ID or sys_id")],
    ) -> ToolResult:
        "Get a specific service catalog item."
        return await dispatch("get_catalog_item", {"item_id": item_id})

    @mcp.tool
    async def list_catalog_categories(
        *,
        limit: Annotated[
            int, Field(description="Maximum number of categories to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        query: Annotated[
            str | None, Field(description="Search query for categories")
        ] = None,
        active: Annotated[
            bool, Field(description="Whether to only return active categories")
        ] = True,
    ) -> ToolResult:
        "List service catalog categories."
        return await dispatch(
            "list_catalog_categories",
            {"limit": limit, "offset": offset, "query": query, "active": active},
        )

    @mcp.tool
    async def create_catalog_category(
        *,
        title: Annotated[str, Field(description="Title of the category")],
        description: Annotated[
            str | None, Field(description="Description of the category")
        ] = None,
        parent: Annotated[
            str | None, Field(description="Parent category sys_id")
        ] = None,
        icon: Annotated[str | None, Field(description="Icon for the category")] = None,
        active: Annotated[
            bool, Field(description="Whether the category is active")
        ] = True,
        order: Annotated[int | None, Field(description="Order of the category")] = None,
    ) -> ToolResult:
        "Create a new service catalog category."
        return await dispatch(
            "create_catalog_category",
            {
                "title": title,
                "description": description,
                "parent": parent,
                "icon": icon,
                "active": active,
                "order": order,
            },
        )

    @mcp.tool
    async def update_catalog_category(
        *,
        category_id: Annotated[str, Field(description="Category ID or sys_id")],
        title: Annotated[str | None, Field(description="Title of the category")] = None,
        description: Annotated[
            str | None, Field(description="Description of the category")
        ] = None,
        parent: Annotated[
            str | None, Field(description="Parent category sys_id")
        ] = None,
        icon: Annotated[str | None, Field(description="Icon for the category")] = None,
        active: Annotated[
            bool | None, Field(description="Whether the category is active")
        ] = None,
        order: Annotated[int | None, Field(description="Order of the category")] = None,
    ) -> ToolResult:
        "Update an existing service catalog category."
        return await dispatch(
            "update_catalog_category",
            {
                "category_id": category_id,
                "title": title,
                "description": description,
                "parent": parent,
                "icon": icon,
                "active": active,
                "order": order,
            },
        )

    @mcp.tool
    async def move_catalog_items(
        *,
        item_ids: Annotated[
            list[str], Field(description="List of catalog item IDs to move")
        ],
        target_category_id: Annotated[
            str, Field(description="Target category ID to move items to")
        ],
    ) -> ToolResult:
        "Move catalog items to a different category."
        return await dispatch(
            "move_catalog_items",
            {"item_ids": item_ids, "target_category_id": target_category_id},
        )

    @mcp.tool
    async def update_catalog_item(
        *,
        item_id: str,
        name: str | None = None,
        short_description: str | None = None,
        description: str | None = None,
        category: str | None = None,
        price: str | None = None,
        active: bool | None = None,
        order: int | None = None,
    ) -> ToolResult:
        "Update a service catalog item."
        return await dispatch(
            "update_catalog_item",
            {
                "item_id": item_id,
                "name": name,
                "short_description": short_description,
                "description": description,
                "category": category,
                "price": price,
                "active": active,
                "order": order,
            },
        )

    return (
        list_catalog_items,
        get_catalog_item,
        list_catalog_categories,
        create_catalog_category,
        update_catalog_category,
        move_catalog_items,
        update_catalog_item,
    )
