"""Servicenow users tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def create_user(
        *,
        user_name: Annotated[str, Field(description="Username for the user")],
        first_name: Annotated[str, Field(description="First name of the user")],
        last_name: Annotated[str, Field(description="Last name of the user")],
        email: Annotated[str, Field(description="Email address of the user")],
        title: Annotated[str | None, Field(description="Job title of the user")] = None,
        department: Annotated[
            str | None, Field(description="Department the user belongs to")
        ] = None,
        manager: Annotated[
            str | None, Field(description="Manager of the user (sys_id or username)")
        ] = None,
        roles: Annotated[
            list[str] | None, Field(description="Roles to assign to the user")
        ] = None,
        phone: Annotated[
            str | None, Field(description="Phone number of the user")
        ] = None,
        mobile_phone: Annotated[
            str | None, Field(description="Mobile phone number of the user")
        ] = None,
        location: Annotated[
            str | None, Field(description="Location of the user")
        ] = None,
        password: Annotated[
            str | None, Field(description="Password for the user account")
        ] = None,
        active: Annotated[
            bool | None, Field(description="Whether the user account is active")
        ] = True,
    ) -> ToolResult:
        "Create a new user in ServiceNow"
        return await dispatch(
            "create_user",
            {
                "user_name": user_name,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "title": title,
                "department": department,
                "manager": manager,
                "roles": roles,
                "phone": phone,
                "mobile_phone": mobile_phone,
                "location": location,
                "password": password,
                "active": active,
            },
        )

    @mcp.tool
    async def update_user(
        *,
        user_id: Annotated[str, Field(description="User ID or sys_id to update")],
        user_name: Annotated[
            str | None, Field(description="Username for the user")
        ] = None,
        first_name: Annotated[
            str | None, Field(description="First name of the user")
        ] = None,
        last_name: Annotated[
            str | None, Field(description="Last name of the user")
        ] = None,
        email: Annotated[
            str | None, Field(description="Email address of the user")
        ] = None,
        title: Annotated[str | None, Field(description="Job title of the user")] = None,
        department: Annotated[
            str | None, Field(description="Department the user belongs to")
        ] = None,
        manager: Annotated[
            str | None, Field(description="Manager of the user (sys_id or username)")
        ] = None,
        roles: Annotated[
            list[str] | None, Field(description="Roles to assign to the user")
        ] = None,
        phone: Annotated[
            str | None, Field(description="Phone number of the user")
        ] = None,
        mobile_phone: Annotated[
            str | None, Field(description="Mobile phone number of the user")
        ] = None,
        location: Annotated[
            str | None, Field(description="Location of the user")
        ] = None,
        password: Annotated[
            str | None, Field(description="Password for the user account")
        ] = None,
        active: Annotated[
            bool | None, Field(description="Whether the user account is active")
        ] = None,
    ) -> ToolResult:
        "Update an existing user in ServiceNow"
        return await dispatch(
            "update_user",
            {
                "user_id": user_id,
                "user_name": user_name,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "title": title,
                "department": department,
                "manager": manager,
                "roles": roles,
                "phone": phone,
                "mobile_phone": mobile_phone,
                "location": location,
                "password": password,
                "active": active,
            },
        )

    @mcp.tool
    async def list_users(
        *,
        limit: Annotated[
            int, Field(description="Maximum number of users to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        active: Annotated[
            bool | None, Field(description="Filter by active status")
        ] = None,
        department: Annotated[
            str | None, Field(description="Filter by department")
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description="Case-insensitive search term that matches against name, username, or email fields. Uses ServiceNow's LIKE operator for partial matching."
            ),
        ] = None,
    ) -> ToolResult:
        "List users in ServiceNow"
        return await dispatch(
            "list_users",
            {
                "limit": limit,
                "offset": offset,
                "active": active,
                "department": department,
                "query": query,
            },
        )

    @mcp.tool
    async def create_group(
        *,
        name: Annotated[str, Field(description="Name of the group")],
        description: Annotated[
            str | None, Field(description="Description of the group")
        ] = None,
        manager: Annotated[
            str | None, Field(description="Manager of the group (sys_id or username)")
        ] = None,
        parent: Annotated[
            str | None, Field(description="Parent group (sys_id or name)")
        ] = None,
        type: Annotated[str | None, Field(description="Type of the group")] = None,
        email: Annotated[
            str | None, Field(description="Email address for the group")
        ] = None,
        members: Annotated[
            list[str] | None,
            Field(description="List of user sys_ids or usernames to add as members"),
        ] = None,
        active: Annotated[
            bool | None, Field(description="Whether the group is active")
        ] = True,
    ) -> ToolResult:
        "Create a new group in ServiceNow"
        return await dispatch(
            "create_group",
            {
                "name": name,
                "description": description,
                "manager": manager,
                "parent": parent,
                "type": type,
                "email": email,
                "members": members,
                "active": active,
            },
        )

    @mcp.tool
    async def update_group(
        *,
        group_id: Annotated[str, Field(description="Group ID or sys_id to update")],
        name: Annotated[str | None, Field(description="Name of the group")] = None,
        description: Annotated[
            str | None, Field(description="Description of the group")
        ] = None,
        manager: Annotated[
            str | None, Field(description="Manager of the group (sys_id or username)")
        ] = None,
        parent: Annotated[
            str | None, Field(description="Parent group (sys_id or name)")
        ] = None,
        type: Annotated[str | None, Field(description="Type of the group")] = None,
        email: Annotated[
            str | None, Field(description="Email address for the group")
        ] = None,
        active: Annotated[
            bool | None, Field(description="Whether the group is active")
        ] = None,
    ) -> ToolResult:
        "Update an existing group in ServiceNow"
        return await dispatch(
            "update_group",
            {
                "group_id": group_id,
                "name": name,
                "description": description,
                "manager": manager,
                "parent": parent,
                "type": type,
                "email": email,
                "active": active,
            },
        )

    @mcp.tool
    async def remove_group_members(
        *,
        group_id: Annotated[str, Field(description="Group ID or sys_id")],
        members: Annotated[
            list[str],
            Field(description="List of user sys_ids or usernames to remove as members"),
        ],
    ) -> ToolResult:
        "Remove members from an existing group in ServiceNow"
        return await dispatch(
            "remove_group_members", {"group_id": group_id, "members": members}
        )

    @mcp.tool
    async def list_groups(
        *,
        limit: Annotated[
            int, Field(description="Maximum number of groups to return")
        ] = 10,
        offset: Annotated[int, Field(description="Offset for pagination")] = 0,
        active: Annotated[
            bool | None, Field(description="Filter by active status")
        ] = None,
        query: Annotated[
            str | None,
            Field(
                description="Case-insensitive search term that matches against group name or description fields. Uses ServiceNow's LIKE operator for partial matching."
            ),
        ] = None,
        type: Annotated[str | None, Field(description="Filter by group type")] = None,
    ) -> ToolResult:
        "List groups from ServiceNow with optional filtering"
        return await dispatch(
            "list_groups",
            {
                "limit": limit,
                "offset": offset,
                "active": active,
                "query": query,
                "type": type,
            },
        )

    return (
        create_user,
        update_user,
        list_users,
        create_group,
        update_group,
        remove_group_members,
        list_groups,
    )
