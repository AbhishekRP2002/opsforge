"""Agile records: source-specific fields and explicit table/reference choices."""

from . import servicenow_store as store


def _create(db, table, data, refs, step, clock, entity, title, prefix=None):
    required = {
        "rm_scrum_task": ("story",),
        "m2m_story_dependencies": ("dependent_story", "prerequisite_story"),
    }.get(table, ())
    if error := store.reference_error(db, data, refs, required=required):
        return store.failure(error)
    return {
        "success": True,
        "message": f"{title} created successfully",
        entity: store.insert(db, table, data, step, clock, prefix),
    }, False


def _update(db, table, key, data, refs, step, clock, entity, title):
    row = store.get(db, table, key)
    if row is None:
        return store.failure(f"simulation_profile: {entity} not found")
    if error := store.reference_error(db, data, refs):
        return store.failure(error)
    return {
        "success": True,
        "message": f"{title} updated successfully",
        entity: store.update(db, table, row, data, step, clock),
    }, False


def _list(db, table, arguments, filters, plural, clock=0):
    rows, _, error = store.page(
        store.all_rows(db, table), arguments, filters, clock=clock
    )
    if error:
        return store.failure(error)
    return {
        "success": True,
        plural: rows,
        "count": len(rows),
        "total": len(rows),
    }, False


def create_project(db, arguments, step, clock):
    data = {"short_description": arguments["short_description"]} | store.fields(
        arguments, ("short_description",), truthy=True
    )
    return _create(
        db,
        "pm_project",
        data,
        store.ASSIGNMENT_REFS | {"project_manager": "sys_user"},
        step,
        clock,
        "project",
        "Project",
        "PRJ",
    )


def update_project(db, arguments, step, clock):
    return _update(
        db,
        "pm_project",
        arguments["project_id"],
        store.fields(arguments, ("project_id",), truthy=True),
        store.ASSIGNMENT_REFS | {"project_manager": "sys_user"},
        step,
        clock,
        "project",
        "Project",
    )


def list_projects(db, arguments, step, clock):
    return _list(
        db, "pm_project", arguments, ("state", "assignment_group"), "projects", clock
    )


def create_epic(db, arguments, step, clock):
    data = {"short_description": arguments["short_description"]} | store.fields(
        arguments, ("short_description", "state"), truthy=True
    )
    return _create(
        db, "rm_epic", data, store.ASSIGNMENT_REFS, step, clock, "epic", "Epic", "EPIC"
    )


def update_epic(db, arguments, step, clock):
    return _update(
        db,
        "rm_epic",
        arguments["epic_id"],
        store.fields(arguments, ("epic_id", "state"), truthy=True),
        store.ASSIGNMENT_REFS,
        step,
        clock,
        "epic",
        "Epic",
    )


def list_epics(db, arguments, step, clock):
    return _list(
        db, "rm_epic", arguments, ("priority", "assignment_group"), "epics", clock
    )


def create_story(db, arguments, step, clock):
    data = {
        "short_description": arguments["short_description"],
        "acceptance_criteria": arguments["acceptance_criteria"],
    } | store.fields(
        arguments, ("short_description", "acceptance_criteria"), truthy=True
    )
    return _create(
        db,
        "rm_story",
        data,
        store.ASSIGNMENT_REFS | {"epic": "rm_epic", "project": "pm_project"},
        step,
        clock,
        "story",
        "Story",
        "STRY",
    )


def update_story(db, arguments, step, clock):
    return _update(
        db,
        "rm_story",
        arguments["story_id"],
        store.fields(arguments, ("story_id",), truthy=True),
        store.ASSIGNMENT_REFS | {"epic": "rm_epic", "project": "pm_project"},
        step,
        clock,
        "story",
        "Story",
    )


def list_stories(db, arguments, step, clock):
    return _list(
        db, "rm_story", arguments, ("state", "assignment_group"), "stories", clock
    )


def create_scrum_task(db, arguments, step, clock):
    data = {
        "story": arguments["story"],
        "short_description": arguments["short_description"],
    } | store.fields(arguments, ("story", "short_description"), truthy=True)
    return _create(
        db,
        "rm_scrum_task",
        data,
        store.ASSIGNMENT_REFS | {"story": "rm_story"},
        step,
        clock,
        "scrum_task",
        "Scrum Task",
        "SCTASK",
    )


def update_scrum_task(db, arguments, step, clock):
    return _update(
        db,
        "rm_scrum_task",
        arguments["scrum_task_id"],
        store.fields(arguments, ("scrum_task_id",), truthy=True),
        store.ASSIGNMENT_REFS,
        step,
        clock,
        "scrum_task",
        "Scrum Task",
    )


def list_scrum_tasks(db, arguments, step, clock):
    return _list(
        db,
        "rm_scrum_task",
        arguments,
        ("state", "assignment_group"),
        "scrum_tasks",
        clock,
    )


def create_story_dependency(db, arguments, step, clock):
    return _create(
        db,
        "m2m_story_dependencies",
        dict(arguments),
        {"dependent_story": "rm_story", "prerequisite_story": "rm_story"},
        step,
        clock,
        "story_dependency",
        "Story dependency",
    )


def list_story_dependencies(db, arguments, step, clock):
    return _list(
        db,
        "m2m_story_dependencies",
        arguments,
        ("dependent_story", "prerequisite_story"),
        "story_dependencies",
    )


def delete_story_dependency(db, arguments, step, clock):
    key = arguments["dependency_id"]
    if store.get(db, "m2m_story_dependencies", key) is None:
        return store.failure("simulation_profile: story dependency not found")
    store.delete(db, "m2m_story_dependencies", key, step, clock)
    return {"success": True, "message": "Story dependency deleted successfully"}, False


HANDLERS = {
    "create_project": create_project,
    "update_project": update_project,
    "list_projects": list_projects,
    "create_epic": create_epic,
    "update_epic": update_epic,
    "list_epics": list_epics,
    "create_story": create_story,
    "update_story": update_story,
    "list_stories": list_stories,
    "create_scrum_task": create_scrum_task,
    "update_scrum_task": update_scrum_task,
    "list_scrum_tasks": list_scrum_tasks,
    "create_story_dependency": create_story_dependency,
    "list_story_dependencies": list_story_dependencies,
    "delete_story_dependency": delete_story_dependency,
}
