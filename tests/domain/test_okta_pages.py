import pytest

from .test_okta_applications import call
from .test_okta_applications import env as env_fixture

env = env_fixture


@pytest.mark.parametrize(
    "kind,resource,default,get_custom,get_preview,replace_custom,replace_preview,delete_custom,delete_preview",
    [
        (
            "error",
            "get_error_page_resources",
            "get_default_error_page",
            "get_customized_error_page",
            "get_preview_error_page",
            "replace_customized_error_page",
            "replace_preview_error_page",
            "delete_customized_error_page",
            "delete_preview_error_page",
        ),
        (
            "sign-in",
            "get_sign_in_page_resources",
            "get_default_sign_in_page",
            "get_customized_sign_in_page",
            "get_preview_sign_in_page",
            "replace_customized_sign_in_page",
            "replace_preview_sign_in_page",
            "delete_customized_sign_in_page",
            "delete_preview_sign_in_page",
        ),
    ],
)
def test_page_slots_are_distinct_replace_and_cancel_delete(
    env,
    kind,
    resource,
    default,
    get_custom,
    get_preview,
    replace_custom,
    replace_preview,
    delete_custom,
    delete_preview,
):
    brand, _ = call(env, "create_brand", name="Pages")
    bid = brand["id"]
    assert call(env, replace_custom, brand_id="missing", page_content="orphan")[1]
    assert (
        call(env, default, brand_id=bid)[0]["pageContent"]
        == f"<html><body>Default {kind} page</body></html>"
    )
    assert call(
        env,
        replace_custom,
        brand_id=bid,
        page_content="<h1>Live</h1>",
        csp_mode="enforced",
    )[0]["contentSecurityPolicySetting"] == {"mode": "enforced"}
    assert (
        call(env, replace_preview, brand_id=bid, page_content="<h1>Preview</h1>")[0][
            "pageContent"
        ]
        == "<h1>Preview</h1>"
    )
    assert call(env, get_custom, brand_id=bid)[0]["pageContent"] == "<h1>Live</h1>"
    assert call(env, get_preview, brand_id=bid)[0]["pageContent"] == "<h1>Preview</h1>"
    root, error = call(env, resource, brand_id=bid, expand=["customized", "preview"])
    assert (
        not error and root["_embedded"]["customized"]["pageContent"] == "<h1>Live</h1>"
    )
    for delete in (delete_custom, delete_preview):
        assert call(env, delete, brand_id=bid)[0]["success"] is False
    assert call(env, get_custom, brand_id=bid)[0]["pageContent"] == "<h1>Live</h1>"
    assert call(env, get_preview, brand_id=bid)[0]["pageContent"] == "<h1>Preview</h1>"
    assert not call(env, replace_custom, brand_id=bid, page_content="Reset")[1]
    assert "contentSecurityPolicySetting" not in call(env, get_custom, brand_id=bid)[0]


def test_signout_and_widget_versions(env):
    brand, _ = call(env, "create_brand", name="Widget")
    bid = brand["id"]
    versions, error = call(env, "list_sign_in_widget_versions", brand_id=bid)
    assert not error and "7" in versions["versions"]
    assert call(
        env, "replace_sign_out_page_settings", brand_id=bid, type="EXTERNALLY_HOSTED"
    )[1]
    assert not call(
        env,
        "replace_sign_out_page_settings",
        brand_id=bid,
        type="EXTERNALLY_HOSTED",
        url="https://example.test/out",
    )[1]
    assert call(env, "get_sign_out_page_settings", brand_id=bid)[0] == {
        "type": "EXTERNALLY_HOSTED",
        "url": "https://example.test/out",
    }
