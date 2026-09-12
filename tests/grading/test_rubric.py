"""OpenEnv rubric follows committed episode transitions without duplicate credit."""

import sqlite3

import pytest
from itops_env import ItopsAction
from itops_env.server.itops_environment import ItopsEnvironment
from openenv.core.rubrics import TrajectoryRubric


def test_rubric_tracks_single_terminal_credit_and_reset():
    env = ItopsEnvironment()
    env.reset()
    try:
        assert isinstance(env.rubric, TrajectoryRubric)
        actions = [
            ItopsAction(
                provider="okta",
                tool_name="get_user",
                arguments={"user_id": "00u-target"},
            ),
            ItopsAction(
                provider="servicenow",
                tool_name="get_user",
                arguments={"email": "alex.chen@example.test"},
            ),
            ItopsAction(
                provider="servicenow",
                tool_name="add_group_members",
                arguments={"group_id": "a" * 32, "members": ["alex.chen"]},
            ),
            ItopsAction(
                provider="benchmark",
                tool_name="workflow_submit",
                arguments={
                    "disposition": "completed",
                    "user_id": "1" * 32,
                    "group_id": "a" * 32,
                },
            ),
        ]
        rewards = [env.step(action).reward for action in actions]
        assert rewards == [0, 0, 0, 1]
        assert env.rubric.compute_step_rewards() == rewards
        assert env.rubric.last_score == 1
        assert env.step(actions[-1]).reward == 0
        assert env.step(
            ItopsAction(
                provider="okta",
                tool_name="get_user",
                arguments={"user_id": "00u-target"},
            )
        ).done
        assert len(env.rubric.trajectory) == 4
        assert env.rubric.compute_step_rewards() == rewards
        with pytest.raises(ValueError):
            env.reset(seed=-1)
        assert env.rubric.last_score == 1
        env.reset()
        assert env.rubric.trajectory == []
        assert env.rubric.last_score is None
    finally:
        env.close()


def test_rubric_copies_inputs_and_excludes_rolled_back_steps():
    env = ItopsEnvironment()
    env.reset()
    try:
        assert env.episode is not None
        assert isinstance(env.rubric, TrajectoryRubric)
        action = ItopsAction(
            provider="okta", tool_name="get_user", arguments={"user_id": "00u-target"}
        )
        observation = env.step(action)
        action.arguments["user_id"] = "changed"
        observation.reward = 99
        assert env.rubric.trajectory[0][0].arguments["user_id"] == "00u-target"
        assert env.rubric.compute_step_rewards() == [0]
        env.episode.db.connection.execute(
            "CREATE TRIGGER fail_action BEFORE INSERT ON journal BEGIN SELECT RAISE(ABORT, 'rubric rollback'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="rubric rollback"):
            env.step(
                ItopsAction(
                    provider="okta",
                    tool_name="get_user",
                    arguments={"user_id": "00u-target"},
                )
            )
        assert len(env.rubric.trajectory) == 1
        result = env.episode.result()
        assert result is not None
        assert result.status == "infrastructure_error"
    finally:
        env.close()
