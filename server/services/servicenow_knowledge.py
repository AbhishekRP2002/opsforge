"""Knowledge bases, categories and opaque article bodies."""

from . import servicenow_store as store


def _display(db, table, key, field):
    row = store.get(db, table, key) if key else None
    return row.get(field, "") if row else ""


def create_knowledge_base(db, arguments, step, clock):
    data = {"title": arguments["title"]}
    for source, target in {
        "description": "description",
        "owner": "owner",
        "managers": "kb_managers",
        "publish_workflow": "workflow_publish",
        "retire_workflow": "workflow_retire",
    }.items():
        if arguments[source]:
            data[target] = arguments[source]
    if error := store.reference_error(db, data, {"owner": "sys_user"}):
        return store.failure(error, kb_id=None, kb_name=None)
    row = store.insert(db, "kb_knowledge_base", data, step, clock)
    return {
        "success": True,
        "message": "Knowledge base created successfully",
        "kb_id": row["sys_id"],
        "kb_name": row["title"],
    }, False


def _list_result(rows, arguments, plural, label, error=None):
    return {
        "success": not error,
        "message": error or f"Found {len(rows)} {label}",
        plural: rows,
        "count": len(rows),
        "limit": arguments["limit"],
        "offset": arguments["offset"],
    }, False


def list_knowledge_bases(db, arguments, step, clock):
    rows, _, error = store.page(
        store.all_rows(db, "kb_knowledge_base"),
        arguments,
        ("active",),
        search_fields=("title", "description"),
    )
    items = [
        {
            "id": row["sys_id"],
            "title": row.get("title", ""),
            "description": row.get("description", ""),
            "owner": "",
            "managers": "",
            "active": str(row.get("active")).lower() == "true",
            "created": row.get("sys_created_on", ""),
            "updated": row.get("sys_updated_on", ""),
        }
        for row in rows
    ]
    return _list_result(items, arguments, "knowledge_bases", "knowledge bases", error)


def create_category(db, arguments, step, clock):
    data = {
        "label": arguments["title"],
        "kb_knowledge_base": arguments["knowledge_base"],
        "active": str(arguments["active"]).lower(),
    }
    for source, target in {
        "description": "description",
        "parent_category": "parent",
        "parent_table": "parent_table",
    }.items():
        if arguments[source]:
            data[target] = arguments[source]
    if error := store.reference_error(
        db,
        data,
        {"kb_knowledge_base": "kb_knowledge_base", "parent": "kb_category"},
        required=("kb_knowledge_base",),
    ):
        return store.failure(error, category_id=None, category_name=None)
    row = store.insert(db, "kb_category", data, step, clock)
    return {
        "success": True,
        "message": "Category created successfully",
        "category_id": row["sys_id"],
        "category_name": row["label"],
    }, False


def list_categories(db, arguments, step, clock):
    filters = arguments | {
        "kb_knowledge_base": arguments["knowledge_base"],
        "parent": arguments["parent_category"],
    }
    rows, _, error = store.page(
        store.all_rows(db, "kb_category"),
        filters,
        ("kb_knowledge_base", "parent", "active"),
        search_fields=("label", "description"),
    )
    items = [
        {
            "id": row["sys_id"],
            "title": row.get("label", ""),
            "description": row.get("description", ""),
            "knowledge_base": _display(
                db, "kb_knowledge_base", row.get("kb_knowledge_base"), "title"
            ),
            "parent_category": _display(db, "kb_category", row.get("parent"), "label"),
            "active": str(row.get("active")).lower() == "true",
            "created": row.get("sys_created_on", ""),
            "updated": row.get("sys_updated_on", ""),
        }
        for row in rows
    ]
    return _list_result(items, arguments, "categories", "categories", error)


def _article_failure(message):
    return store.failure(
        message, article_id=None, article_title=None, workflow_state=None
    )


def _article_result(row, verb):
    return {
        "success": True,
        "message": f"Article {verb} successfully",
        "article_id": row["sys_id"],
        "article_title": row.get("short_description"),
        "workflow_state": row.get("workflow_state"),
    }, False


def create_article(db, arguments, step, clock):
    data = {
        "short_description": arguments["title"] or arguments["short_description"],
        "text": arguments["text"],
        "kb_knowledge_base": arguments["knowledge_base"],
        "kb_category": arguments["category"],
        "article_type": arguments["article_type"],
    }
    if arguments["keywords"]:
        data["keywords"] = arguments["keywords"]
    if error := store.reference_error(
        db,
        data,
        {"kb_knowledge_base": "kb_knowledge_base", "kb_category": "kb_category"},
        required=("kb_knowledge_base", "kb_category"),
    ):
        return _article_failure(error)
    return _article_result(
        store.insert(db, "kb_knowledge", data, step, clock, "KB"), "created"
    )


def _update_article(db, key, data, step, clock, verb):
    row = store.get(db, "kb_knowledge", key)
    if row is None:
        return _article_failure("simulation_profile: article not found")
    if error := store.reference_error(
        db,
        data,
        {"kb_category": "kb_category", "workflow_version": "wf_workflow_version"},
    ):
        return _article_failure(error)
    return _article_result(
        store.update(db, "kb_knowledge", row, data, step, clock), verb
    )


def update_article(db, arguments, step, clock):
    data = {}
    for source, target in (
        ("title", "short_description"),
        ("text", "text"),
        ("short_description", "short_description"),
        ("category", "kb_category"),
        ("keywords", "keywords"),
    ):
        if arguments[source]:
            data[target] = arguments[source]
    return _update_article(db, arguments["article_id"], data, step, clock, "updated")


def publish_article(db, arguments, step, clock):
    data = {"workflow_state": arguments["workflow_state"]}
    if arguments["workflow_version"]:
        data["workflow_version"] = arguments["workflow_version"]
    return _update_article(db, arguments["article_id"], data, step, clock, "published")


def _format_article(db, row, *, details=False):
    result = {
        "id": row["sys_id"],
        "title": row.get("short_description", ""),
        "knowledge_base": _display(
            db, "kb_knowledge_base", row.get("kb_knowledge_base"), "title"
        ),
        "category": _display(db, "kb_category", row.get("kb_category"), "label"),
        "workflow_state": row.get("workflow_state", ""),
        "created": row.get("sys_created_on", ""),
        "updated": row.get("sys_updated_on", ""),
    }
    if details:
        result.update(
            text=row.get("text", ""),
            author="",
            keywords=row.get("keywords", ""),
            article_type=row.get("article_type", ""),
            views=row.get("view_count", "0"),
        )
    return result


def list_articles(db, arguments, step, clock):
    filters = arguments | {
        "kb_knowledge_base": arguments["knowledge_base"],
        "kb_category": arguments["category"],
    }
    rows, _, error = store.page(
        store.all_rows(db, "kb_knowledge"),
        filters,
        ("kb_knowledge_base", "kb_category", "workflow_state"),
        search_fields=("short_description", "text"),
    )
    return _list_result(
        [_format_article(db, row) for row in rows],
        arguments,
        "articles",
        "articles",
        error,
    )


def get_article(db, arguments, step, clock):
    row = store.get(db, "kb_knowledge", arguments["article_id"])
    if row is None:
        return store.failure(f"Article with ID {arguments['article_id']} not found")
    return {
        "success": True,
        "message": "Article retrieved successfully",
        "article": _format_article(db, row, details=True),
    }, False


HANDLERS = {
    "create_knowledge_base": create_knowledge_base,
    "list_knowledge_bases": list_knowledge_bases,
    "create_category": create_category,
    "list_categories": list_categories,
    "create_article": create_article,
    "update_article": update_article,
    "publish_article": publish_article,
    "list_articles": list_articles,
    "get_article": get_article,
}
