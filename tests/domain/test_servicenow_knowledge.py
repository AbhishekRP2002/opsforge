import pytest

from .test_servicenow_incidents import call
from .test_servicenow_incidents import env as snow_fixture

env = snow_fixture


def test_knowledge_category_article_mapping_and_publish_round_trip(env):
    kb, error = call(env, "create_knowledge_base", title="Docs")
    assert not error and kb["success"]
    kid = kb["kb_id"]
    assert (
        call(env, "list_knowledge_bases", query="Docs")[0]["knowledge_bases"][0]["id"]
        == kid
    )
    category = call(env, "create_category", title="Guide", knowledge_base=kid)[0]
    cid = category["category_id"]
    listed = call(env, "list_categories", knowledge_base=kid)[0]
    assert listed["count"] == 1 and listed["categories"][0]["title"] == "Guide"
    article = call(
        env,
        "create_article",
        title="Title wins",
        short_description="Ignored",
        text="<b>Opaque</b>",
        knowledge_base=kid,
        category=cid,
    )[0]
    aid = article["article_id"]
    assert article["article_title"] == "Title wins"
    assert (
        call(
            env,
            "update_article",
            article_id=aid,
            title="First",
            short_description="Second",
        )[0]["article_title"]
        == "Second"
    )
    assert (
        call(env, "publish_article", article_id=aid, workflow_state="custom")[0][
            "workflow_state"
        ]
        == "custom"
    )
    found = call(env, "get_article", article_id=aid)[0]["article"]
    assert found["title"] == "Second" and found["text"] == "<b>Opaque</b>"
    listed = call(
        env,
        "list_articles",
        knowledge_base=kid,
        category=cid,
        query="Opaque",
        workflow_state="custom",
    )[0]
    assert listed["count"] == 1 and listed["articles"][0]["id"] == aid


@pytest.mark.parametrize(
    "tool,args",
    [
        ("create_knowledge_base", {"title": "Bad", "owner": "absent"}),
        ("list_knowledge_bases", {"limit": -1}),
        ("create_category", {"title": "Bad", "knowledge_base": "absent"}),
        ("list_categories", {"limit": -1}),
        (
            "create_article",
            {
                "title": "Bad",
                "short_description": "Bad",
                "text": "Bad",
                "knowledge_base": "absent",
                "category": "absent",
            },
        ),
        ("update_article", {"article_id": "absent"}),
        ("publish_article", {"article_id": "absent"}),
        ("get_article", {"article_id": "absent"}),
        ("list_articles", {"limit": -1}),
    ],
)
def test_knowledge_business_failures(env, tool, args):
    value, error = call(env, tool, **args)
    assert not error and value["success"] is False
