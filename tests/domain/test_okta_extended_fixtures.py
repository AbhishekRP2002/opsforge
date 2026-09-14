import json

import pytest
from itops_env.server.core.scenarios import Scenario, load_scenario
from itops_env.server.itops_environment import ItopsEnvironment
from pydantic import ValidationError

from .test_okta_applications import call


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "initial_artifacts",
            [{"path": "/etc/passwd", "content": "inert", "media_type": "text/plain"}],
        ),
        (
            "initial_artifacts",
            [
                {
                    "path": "/tmp/../escape",
                    "content": "inert",
                    "media_type": "text/plain",
                }
            ],
        ),
        ("okta_applications", [{"id": "../bad", "label": "Bad", "status": "ACTIVE"}]),
        ("okta_applications", [{"id": "a", "label": "Bad", "status": "INVALID"}]),
    ],
)
def test_invalid_extended_fixture_rejected_before_database_creation(field, value):
    raw = load_scenario().model_dump() | {field: value}
    with pytest.raises(ValidationError):
        Scenario.model_validate(raw)


def test_log_outcomes_are_classified_from_fixture_records():
    raw = load_scenario().model_dump()
    raw["okta_log_events"] = [
        {
            "id": "log1",
            "uuid": "log1",
            "published": "2026-01-01T00:00:00Z",
            "eventType": "user.session.start",
            "actor": {"id": "00u-target"},
            "outcome": {"result": "FAILURE"},
        },
        {
            "id": "log2",
            "uuid": "log2",
            "published": "2026-01-01T00:00:00Z",
            "eventType": "policy.evaluate_sign_on",
            "actor": {"id": "00u-target"},
            "outcome": {"result": "DENY"},
        },
        {
            "id": "log3",
            "uuid": "log3",
            "published": "2026-01-01T00:00:00Z",
            "eventType": "application.lifecycle.create",
            "actor": {"id": "00u-target"},
            "outcome": {"result": "FAILURE"},
        },
    ]
    env = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    env.reset()
    try:
        failures, error = call(env, "get_login_failures", user_id="00u-target")
        assert not error
        assert failures["failures"]["total"] == 2
        assert failures["denials"]["total"] == 1
        assert len(failures["failures"]["login_events"]) == 1
        assert len(failures["failures"]["other_events"]) == 1
        filtered, error = call(
            env,
            "get_logs",
            filter='outcome.result eq "DENY" and actor.id eq "00u-target"',
        )
        assert not error and filtered["items"][0]["uuid"] == "log2"
        assert filtered["total_fetched"] == 1
    finally:
        env.close()


def test_service_token_preview_and_send_are_nonmutating_errors():
    raw = load_scenario().model_dump() | {"okta_auth_mode": "service"}
    env = ItopsEnvironment(scenario=Scenario.model_validate(raw))
    env.reset()
    try:
        brand, _ = call(env, "create_brand", name="Service")
        args = {"brand_id": brand["id"], "template_name": "UserActivation"}
        for tool in ("get_email_default_content_preview", "send_test_email"):
            value, error = call(env, tool, **args)
            assert error and "OAuth 2.0 service token" in value["error"]
        assert env.episode is not None
        assert (
            env.episode.db.connection.execute(
                "SELECT COUNT(*) FROM okta_email_outbox"
            ).fetchone()[0]
            == 0
        )
        assert "${org.name}" in json.dumps(
            call(env, "get_email_default_content", **args)[0]
        )
    finally:
        env.close()
