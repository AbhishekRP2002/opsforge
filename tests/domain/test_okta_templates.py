import pytest

from .test_okta_applications import call
from .test_okta_applications import env as env_fixture

env = env_fixture


@pytest.mark.parametrize(
    "customized,expected_subject",
    [(False, "Activate OpsForge account"), (True, "Custom OpsForge")],
)
def test_send_needs_only_manage_scope_for_default_and_customized_content(
    env, customized, expected_subject
):
    brand, error = call(env, "create_brand", name="Minimal scope")
    assert not error
    arguments = {"brand_id": brand["id"], "template_name": "UserActivation"}
    if customized:
        assert not call(
            env,
            "create_email_customization",
            **arguments,
            language="en",
            subject="Custom ${org.name}",
            body="Open ${activationLink}",
        )[1]
    db = env.episode.db
    with db.connection:
        db.connection.execute(
            "DELETE FROM okta_scopes WHERE scope != 'okta.templates.manage'"
        )
    step, clock = env.state.step_count, env.state.simulated_clock
    result, error = call(env, "send_test_email", **arguments)
    assert not error and result["success"] is True
    assert env.state.step_count == step + 1
    assert env.state.simulated_clock == clock + 1
    rows = db.connection.execute(
        "SELECT subject,body,step,clock FROM okta_email_outbox"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        (expected_subject, "Open https://example.test/activate", step + 1, clock + 1)
    ]


def test_email_customization_default_preview_settings_and_outbox(env):
    brand, _ = call(env, "create_brand", name="Mail")
    args = {"brand_id": brand["id"], "template_name": "UserActivation"}
    templates, error = call(env, "list_email_templates", brand_id=brand["id"])
    assert not error and templates["items"][0]["name"] == "UserActivation"
    assert call(env, "get_email_template", **args)[0]["name"] == "UserActivation"
    customization, error = call(
        env,
        "create_email_customization",
        **args,
        language="en",
        subject="Welcome ${org.name}",
        body="Open ${activationLink}",
    )
    assert not error and customization["isDefault"] is True
    cid = customization["id"]
    assert call(
        env,
        "create_email_customization",
        **args,
        language="EN",
        subject="Duplicate",
        body="x",
    )[1]
    assert call(env, "list_email_customizations", **args)[0]["total_fetched"] == 1
    assert (
        call(env, "get_email_customization", **args, customization_id=cid)[0]["subject"]
        == "Welcome ${org.name}"
    )
    preview, error = call(
        env, "get_email_customization_preview", **args, customization_id=cid
    )
    assert not error and preview["subject"] == "Welcome OpsForge"
    assert (
        call(env, "get_email_default_content", **args)[0]["subject"]
        == "Activate ${org.name} account"
    )
    assert (
        call(env, "get_email_default_content_preview", **args)[0]["subject"]
        == "Activate OpsForge account"
    )
    assert not call(
        env,
        "replace_email_customization",
        **args,
        customization_id=cid,
        language="en",
        subject="Updated",
        body="New ${activationLink}",
    )[1]
    assert (
        call(env, "get_email_customization_preview", **args, customization_id=cid)[0][
            "subject"
        ]
        == "Updated"
    )
    assert (
        call(env, "replace_email_settings", **args, recipients="NO_USERS")[0][
            "recipients"
        ]
        == "NO_USERS"
    )
    assert call(env, "get_email_settings", **args)[0]["recipients"] == "NO_USERS"
    sent, error = call(env, "send_test_email", **args, language="en")
    assert not error and sent["success"] is True
    row = env.episode.db.connection.execute(
        "SELECT subject, body FROM okta_email_outbox"
    ).fetchone()
    assert (
        row["subject"] == "Updated"
        and row["body"] == "New https://example.test/activate"
    )
    assert (
        call(env, "delete_email_customization", **args, customization_id=cid)[0][
            "success"
        ]
        is False
    )
    assert call(env, "delete_all_email_customizations", **args)[0]["success"] is False
    assert call(env, "list_email_customizations", **args)[0]["total_fetched"] == 1
