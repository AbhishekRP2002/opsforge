"""Grade actual reads, final rows, and effect history rather than declarations."""

import pytest
from itops_env import ItopsAction
from itops_env.server.itops_environment import ItopsEnvironment

USER = "1" * 32
GROUP = "a" * 32


def act(env, provider, tool, **arguments):
    observation = env.step(
        ItopsAction(provider=provider, tool_name=tool, arguments=arguments)
    )
    assert observation.reward == 0
    return observation


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "unrelated",
        "noop",
        "missing_submit",
        "wrong_reference",
        "missing_okta_read",
        "missing_snow_read",
        "late_reads",
        "duplicate",
        "other_group",
    ],
)
def test_identity_group_grading(failure):
    env = ItopsEnvironment()
    env.reset()
    try:
        assert env.episode is not None
        first = None
        if failure not in {"missing_okta_read", "late_reads"}:
            act(env, "okta", "get_user", user_id="00u-target")
        if failure not in {"missing_snow_read", "late_reads"}:
            act(env, "servicenow", "get_user", email="alex.chen@example.test")
        if failure != "noop":
            members = ["sam.lee"] if failure == "unrelated" else ["alex.chen"]
            if failure == "duplicate":
                members *= 2
            act(
                env,
                "servicenow",
                "add_group_members",
                group_id="b" * 32 if failure == "other_group" else GROUP,
                members=members,
            )
        if failure == "late_reads":
            act(env, "okta", "get_user", user_id="00u-target")
            act(env, "servicenow", "get_user", user_id=USER)
        if failure == "missing_submit":
            assert env.episode.finalize().reward == 0
        else:
            submission = ItopsAction(
                provider="benchmark",
                tool_name="workflow_submit",
                arguments={
                    "disposition": "completed",
                    "user_id": "2" * 32 if failure == "wrong_reference" else USER,
                    "group_id": GROUP,
                    "summary": "I completed every requirement successfully",
                },
            )
            first = env.step(submission)
            assert first.reward == (1.0 if failure is None else 0.0)
            duplicate = env.step(submission)
            assert duplicate.reward == 0.0
            assert duplicate.done
        assert env.state.phase == "terminal"
        result = env.episode.result()
        assert result is not None
        assert result.status == ("success" if failure is None else "failure")
        assert result == env.episode.result()
        assert "evidence" not in env.state.model_dump()
        if failure != "missing_submit":
            assert first is not None
            assert "evidence" not in first.model_dump()
    finally:
        env.close()


def test_grader_allows_non_gold_trajectory_and_freezes_nested_artifact():
    from pydantic import ValidationError

    env = ItopsEnvironment()
    env.reset()
    try:
        assert env.episode is not None
        act(env, "servicenow", "get_user", user_name="alex.chen")
        act(env, "okta", "get_user", user_id="alex.chen@example.test")
        act(env, "okta", "get_user", user_id="00u-other")
        act(
            env,
            "servicenow",
            "add_group_members",
            group_id=GROUP,
            members=["alex.chen", "unknown"],
        )
        first = env.step(
            ItopsAction(
                provider="benchmark",
                tool_name="workflow_submit",
                arguments={
                    "disposition": "completed",
                    "user_id": USER,
                    "group_id": GROUP,
                },
            )
        )
        assert first.reward == 1
        result = env.episode.result()
        assert result is not None
        with pytest.raises(ValidationError):
            result.reward = 0
        with pytest.raises(ValidationError):
            result.metrics.steps = 999
        assert (
            env.episode.db.connection.execute("select artifact from result").fetchone()[
                0
            ]
            == result.model_dump_json()
        )
        assert env.episode.finalize("arbitrary-reason") == result
        second = env.step(
            ItopsAction(
                provider="benchmark",
                tool_name="workflow_submit",
                arguments={
                    "disposition": "completed",
                    "user_id": USER,
                    "group_id": GROUP,
                },
            )
        )
        assert second.reward == 0
        assert env.episode.result() == result
    finally:
        env.close()
