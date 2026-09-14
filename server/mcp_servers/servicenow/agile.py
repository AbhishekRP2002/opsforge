"""Servicenow agile tool declarations."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from pydantic import Field


def register_tools(mcp: FastMCP, dispatch):
    @mcp.tool
    async def create_story(
        *,
        short_description: Annotated[
            str, Field(description="Short description of the story")
        ],
        acceptance_criteria: Annotated[
            str, Field(description="Acceptance criteria for the story")
        ],
        description: Annotated[
            str | None, Field(description="Detailed description of the story")
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="State of story (-6 is Draft,-7 is Ready for Testing,-8 is Testing,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled)"
            ),
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the story")
        ] = None,
        story_points: Annotated[
            int | None, Field(description="Points value for the story")
        ] = 10,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the story")
        ] = None,
        epic: Annotated[
            str | None,
            Field(
                description="Epic that the story belongs to. It requires the System ID of the epic."
            ),
        ] = None,
        project: Annotated[
            str | None,
            Field(
                description="Project that the story belongs to. It requires the System ID of the project."
            ),
        ] = None,
        work_notes: Annotated[
            str | None,
            Field(
                description="Work notes to add to the story. Used for adding notes and comments to a story"
            ),
        ] = None,
    ) -> ToolResult:
        "Create a new story in ServiceNow"
        return await dispatch(
            "create_story",
            {
                "short_description": short_description,
                "acceptance_criteria": acceptance_criteria,
                "description": description,
                "state": state,
                "assignment_group": assignment_group,
                "story_points": story_points,
                "assigned_to": assigned_to,
                "epic": epic,
                "project": project,
                "work_notes": work_notes,
            },
        )

    @mcp.tool
    async def update_story(
        *,
        story_id: Annotated[
            str,
            Field(
                description="Story IDNumber or sys_id. You will need to fetch the story to get the sys_id if you only have the story number"
            ),
        ],
        short_description: Annotated[
            str | None, Field(description="Short description of the story")
        ] = None,
        acceptance_criteria: Annotated[
            str | None, Field(description="Acceptance criteria for the story")
        ] = None,
        description: Annotated[
            str | None, Field(description="Detailed description of the story")
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="State of story (-6 is Draft,-7 is Ready for Testing,-8 is Testing,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled)"
            ),
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the story")
        ] = None,
        story_points: Annotated[
            int | None, Field(description="Points value for the story")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the story")
        ] = None,
        epic: Annotated[
            str | None,
            Field(
                description="Epic that the story belongs to. It requires the System ID of the epic."
            ),
        ] = None,
        project: Annotated[
            str | None,
            Field(
                description="Project that the story belongs to. It requires the System ID of the project."
            ),
        ] = None,
        work_notes: Annotated[
            str | None,
            Field(
                description="Work notes to add to the story. Used for adding notes and comments to a story"
            ),
        ] = None,
    ) -> ToolResult:
        "Update an existing story in ServiceNow"
        return await dispatch(
            "update_story",
            {
                "story_id": story_id,
                "short_description": short_description,
                "acceptance_criteria": acceptance_criteria,
                "description": description,
                "state": state,
                "assignment_group": assignment_group,
                "story_points": story_points,
                "assigned_to": assigned_to,
                "epic": epic,
                "project": project,
                "work_notes": work_notes,
            },
        )

    @mcp.tool
    async def list_stories(
        *,
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
        state: Annotated[str | None, Field(description="Filter by state")] = None,
        assignment_group: Annotated[
            str | None, Field(description="Filter by assignment group")
        ] = None,
        timeframe: Annotated[
            str | None,
            Field(description="Filter by timeframe (upcoming, in-progress, completed)"),
        ] = None,
        query: Annotated[
            str | None, Field(description="Additional query string")
        ] = None,
    ) -> ToolResult:
        "List stories from ServiceNow"
        return await dispatch(
            "list_stories",
            {
                "limit": limit,
                "offset": offset,
                "state": state,
                "assignment_group": assignment_group,
                "timeframe": timeframe,
                "query": query,
            },
        )

    @mcp.tool
    async def list_story_dependencies(
        *,
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
        query: Annotated[
            str | None, Field(description="Additional query string")
        ] = None,
        dependent_story: Annotated[
            str | None, Field(description="Sys_id of the dependent story is required")
        ] = None,
        prerequisite_story: Annotated[
            str | None,
            Field(description="Sys_id that this story depends on is required"),
        ] = None,
    ) -> ToolResult:
        "List story dependencies from ServiceNow"
        return await dispatch(
            "list_story_dependencies",
            {
                "limit": limit,
                "offset": offset,
                "query": query,
                "dependent_story": dependent_story,
                "prerequisite_story": prerequisite_story,
            },
        )

    @mcp.tool
    async def create_story_dependency(
        *,
        dependent_story: Annotated[
            str, Field(description="Sys_id of the dependent story is required")
        ],
        prerequisite_story: Annotated[
            str, Field(description="Sys_id that this story depends on is required")
        ],
    ) -> ToolResult:
        "Create a dependency between two stories in ServiceNow"
        return await dispatch(
            "create_story_dependency",
            {
                "dependent_story": dependent_story,
                "prerequisite_story": prerequisite_story,
            },
        )

    @mcp.tool
    async def delete_story_dependency(
        *,
        dependency_id: Annotated[
            str, Field(description="Sys_id of the dependency is required")
        ],
    ) -> ToolResult:
        "Delete a story dependency in ServiceNow"
        return await dispatch(
            "delete_story_dependency", {"dependency_id": dependency_id}
        )

    @mcp.tool
    async def create_epic(
        *,
        short_description: Annotated[
            str, Field(description="Short description of the epic")
        ],
        description: Annotated[
            str | None, Field(description="Detailed description of the epic")
        ] = None,
        priority: Annotated[
            str | None,
            Field(
                description="Priority of epic (1 is Critical, 2 is High, 3 is Moderate, 4 is Low, 5 is Planning)"
            ),
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="State of story (-6 is Draft,1 is Ready,2 is Work in progress, 3 is Complete, 4 is Cancelled)"
            ),
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the epic")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the epic")
        ] = None,
        work_notes: Annotated[
            str | None,
            Field(
                description="Work notes to add to the epic. Used for adding notes and comments to an epic"
            ),
        ] = None,
    ) -> ToolResult:
        "Create a new epic in ServiceNow"
        return await dispatch(
            "create_epic",
            {
                "short_description": short_description,
                "description": description,
                "priority": priority,
                "state": state,
                "assignment_group": assignment_group,
                "assigned_to": assigned_to,
                "work_notes": work_notes,
            },
        )

    @mcp.tool
    async def update_epic(
        *,
        epic_id: Annotated[str, Field(description="Epic ID or sys_id")],
        short_description: Annotated[
            str | None, Field(description="Short description of the epic")
        ] = None,
        description: Annotated[
            str | None, Field(description="Detailed description of the epic")
        ] = None,
        priority: Annotated[
            str | None,
            Field(
                description="Priority of epic (1 is Critical, 2 is High, 3 is Moderate, 4 is Low, 5 is Planning)"
            ),
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="State of story (-6 is Draft,1 is Ready,2 is Work in progress, 3 is Complete, 4 is Cancelled)"
            ),
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the epic")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the epic")
        ] = None,
        work_notes: Annotated[
            str | None,
            Field(
                description="Work notes to add to the epic. Used for adding notes and comments to an epic"
            ),
        ] = None,
    ) -> ToolResult:
        "Update an existing epic in ServiceNow"
        return await dispatch(
            "update_epic",
            {
                "epic_id": epic_id,
                "short_description": short_description,
                "description": description,
                "priority": priority,
                "state": state,
                "assignment_group": assignment_group,
                "assigned_to": assigned_to,
                "work_notes": work_notes,
            },
        )

    @mcp.tool
    async def list_epics(
        *,
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
        priority: Annotated[str | None, Field(description="Filter by priority")] = None,
        assignment_group: Annotated[
            str | None, Field(description="Filter by assignment group")
        ] = None,
        timeframe: Annotated[
            str | None,
            Field(description="Filter by timeframe (upcoming, in-progress, completed)"),
        ] = None,
        query: Annotated[
            str | None, Field(description="Additional query string")
        ] = None,
    ) -> ToolResult:
        "List epics from ServiceNow"
        return await dispatch(
            "list_epics",
            {
                "limit": limit,
                "offset": offset,
                "priority": priority,
                "assignment_group": assignment_group,
                "timeframe": timeframe,
                "query": query,
            },
        )

    @mcp.tool
    async def create_scrum_task(
        *,
        story: Annotated[
            str,
            Field(
                description="Short description of the story. It requires the System ID of the story."
            ),
        ],
        short_description: Annotated[
            str, Field(description="Short description of the scrum task")
        ],
        priority: Annotated[
            str | None,
            Field(
                description="Priority of scrum task (1 is Critical, 2 is High, 3 is Moderate, 4 is Low)"
            ),
        ] = None,
        planned_hours: Annotated[
            int | None, Field(description="Planned hours for the scrum task")
        ] = None,
        remaining_hours: Annotated[
            int | None, Field(description="Remaining hours for the scrum task")
        ] = None,
        hours: Annotated[
            int | None, Field(description="Actual Hours for the scrum task")
        ] = None,
        description: Annotated[
            str | None, Field(description="Detailed description of the scrum task")
        ] = None,
        type: Annotated[
            str | None,
            Field(
                description="Type of scrum task (1 is Analysis, 2 is Coding, 3 is Documentation, 4 is Testing)"
            ),
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="State of scrum task (-6 is Draft,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled)"
            ),
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the scrum task")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the scrum task")
        ] = None,
        work_notes: Annotated[
            str | None, Field(description="Work notes to add to the scrum task")
        ] = None,
    ) -> ToolResult:
        "Create a new scrum task in ServiceNow"
        return await dispatch(
            "create_scrum_task",
            {
                "story": story,
                "short_description": short_description,
                "priority": priority,
                "planned_hours": planned_hours,
                "remaining_hours": remaining_hours,
                "hours": hours,
                "description": description,
                "type": type,
                "state": state,
                "assignment_group": assignment_group,
                "assigned_to": assigned_to,
                "work_notes": work_notes,
            },
        )

    @mcp.tool
    async def update_scrum_task(
        *,
        scrum_task_id: Annotated[str, Field(description="Scrum Task ID or sys_id")],
        short_description: Annotated[
            str | None, Field(description="Short description of the scrum task")
        ] = None,
        priority: Annotated[
            str | None,
            Field(
                description="Priority of scrum task (1 is Critical, 2 is High, 3 is Moderate, 4 is Low)"
            ),
        ] = None,
        planned_hours: Annotated[
            int | None, Field(description="Planned hours for the scrum task")
        ] = None,
        remaining_hours: Annotated[
            int | None, Field(description="Remaining hours for the scrum task")
        ] = None,
        hours: Annotated[
            int | None, Field(description="Actual Hours for the scrum task")
        ] = None,
        description: Annotated[
            str | None, Field(description="Detailed description of the scrum task")
        ] = None,
        type: Annotated[
            str | None,
            Field(
                description="Type of scrum task (1 is Analysis, 2 is Coding, 3 is Documentation, 4 is Testing)"
            ),
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="State of scrum task (-6 is Draft,1 is Ready, 2 is Work in progress, 3 is Complete, 4 is Cancelled)"
            ),
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the scrum task")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the scrum task")
        ] = None,
        work_notes: Annotated[
            str | None, Field(description="Work notes to add to the scrum task")
        ] = None,
    ) -> ToolResult:
        "Update an existing scrum task in ServiceNow"
        return await dispatch(
            "update_scrum_task",
            {
                "scrum_task_id": scrum_task_id,
                "short_description": short_description,
                "priority": priority,
                "planned_hours": planned_hours,
                "remaining_hours": remaining_hours,
                "hours": hours,
                "description": description,
                "type": type,
                "state": state,
                "assignment_group": assignment_group,
                "assigned_to": assigned_to,
                "work_notes": work_notes,
            },
        )

    @mcp.tool
    async def list_scrum_tasks(
        *,
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
        state: Annotated[str | None, Field(description="Filter by state")] = None,
        assignment_group: Annotated[
            str | None, Field(description="Filter by assignment group")
        ] = None,
        timeframe: Annotated[
            str | None,
            Field(description="Filter by timeframe (upcoming, in-progress, completed)"),
        ] = None,
        query: Annotated[
            str | None, Field(description="Additional query string")
        ] = None,
    ) -> ToolResult:
        "List scrum tasks from ServiceNow"
        return await dispatch(
            "list_scrum_tasks",
            {
                "limit": limit,
                "offset": offset,
                "state": state,
                "assignment_group": assignment_group,
                "timeframe": timeframe,
                "query": query,
            },
        )

    @mcp.tool
    async def create_project(
        *,
        short_description: Annotated[
            str, Field(description="Project name of the project")
        ],
        description: Annotated[
            str | None, Field(description="Detailed description of the project")
        ] = None,
        status: Annotated[
            str | None, Field(description="Status of the project (green, yellow, red)")
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="State of project (-5 is Pending,1 is Open, 2 is Work in progress, 3 is Closed Complete, 4 is Closed Incomplete, 5 is Closed Skipped)"
            ),
        ] = None,
        project_manager: Annotated[
            str | None, Field(description="Project manager for the project")
        ] = None,
        percentage_complete: Annotated[
            int | None, Field(description="Percentage complete for the project")
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the project")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the project")
        ] = None,
        start_date: Annotated[
            str | None, Field(description="Start date for the project")
        ] = None,
        end_date: Annotated[
            str | None, Field(description="End date for the project")
        ] = None,
    ) -> ToolResult:
        "Create a new project in ServiceNow"
        return await dispatch(
            "create_project",
            {
                "short_description": short_description,
                "description": description,
                "status": status,
                "state": state,
                "project_manager": project_manager,
                "percentage_complete": percentage_complete,
                "assignment_group": assignment_group,
                "assigned_to": assigned_to,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    @mcp.tool
    async def update_project(
        *,
        project_id: Annotated[str, Field(description="Project ID or sys_id")],
        short_description: Annotated[
            str | None, Field(description="Project name of the project")
        ] = None,
        description: Annotated[
            str | None, Field(description="Detailed description of the project")
        ] = None,
        status: Annotated[
            str | None, Field(description="Status of the project (green, yellow, red)")
        ] = None,
        state: Annotated[
            str | None,
            Field(
                description="State of project (-5 is Pending,1 is Open, 2 is Work in progress, 3 is Closed Complete, 4 is Closed Incomplete, 5 is Closed Skipped)"
            ),
        ] = None,
        project_manager: Annotated[
            str | None, Field(description="Project manager for the project")
        ] = None,
        percentage_complete: Annotated[
            int | None, Field(description="Percentage complete for the project")
        ] = None,
        assignment_group: Annotated[
            str | None, Field(description="Group assigned to the project")
        ] = None,
        assigned_to: Annotated[
            str | None, Field(description="User assigned to the project")
        ] = None,
        start_date: Annotated[
            str | None, Field(description="Start date for the project")
        ] = None,
        end_date: Annotated[
            str | None, Field(description="End date for the project")
        ] = None,
    ) -> ToolResult:
        "Update an existing project in ServiceNow"
        return await dispatch(
            "update_project",
            {
                "project_id": project_id,
                "short_description": short_description,
                "description": description,
                "status": status,
                "state": state,
                "project_manager": project_manager,
                "percentage_complete": percentage_complete,
                "assignment_group": assignment_group,
                "assigned_to": assigned_to,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    @mcp.tool
    async def list_projects(
        *,
        limit: Annotated[
            int | None, Field(description="Maximum number of records to return")
        ] = 10,
        offset: Annotated[int | None, Field(description="Offset to start from")] = 0,
        state: Annotated[str | None, Field(description="Filter by state")] = None,
        assignment_group: Annotated[
            str | None, Field(description="Filter by assignment group")
        ] = None,
        timeframe: Annotated[
            str | None,
            Field(description="Filter by timeframe (upcoming, in-progress, completed)"),
        ] = None,
        query: Annotated[
            str | None, Field(description="Additional query string")
        ] = None,
    ) -> ToolResult:
        "List projects from ServiceNow"
        return await dispatch(
            "list_projects",
            {
                "limit": limit,
                "offset": offset,
                "state": state,
                "assignment_group": assignment_group,
                "timeframe": timeframe,
                "query": query,
            },
        )

    return (
        create_story,
        update_story,
        list_stories,
        list_story_dependencies,
        create_story_dependency,
        delete_story_dependency,
        create_epic,
        update_epic,
        list_epics,
        create_scrum_task,
        update_scrum_task,
        list_scrum_tasks,
        create_project,
        update_project,
        list_projects,
    )
