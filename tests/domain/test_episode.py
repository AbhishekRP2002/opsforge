"""Episode accounting, provider effects, and resource lifecycle."""

import json
import sqlite3

import pytest
from itops_env import ItopsAction
from itops_env.server.itops_environment import ItopsEnvironment

USER = "1" * 32
GROUP = "a" * 32
OTHER_GROUP = "b" * 32


def call(env, provider, tool, **arguments):
    return env.step(ItopsAction(provider=provider, tool_name=tool, arguments=arguments))


def body(observation):
    return json.loads(observation.content[0]["text"])


@pytest.fixture
def env():
    instance = ItopsEnvironment()
    instance.reset(seed=42)
    yield instance
    instance.close()


def test_provider_collision_and_selector_precedence(env):
    okta = body(call(env, "okta", "get_user", user_id="alex.chen@example.test"))
    snow = body(call(env, "servicenow", "get_user", email="alex.chen@example.test"))
    assert okta[0]["id"] == "00u-target"
    assert okta[0]["status"] == "ACTIVE"
    assert snow["success"] is True
    assert snow["user"]["sys_id"] == USER
    assert (
        body(
            call(
                env,
                "servicenow",
                "get_user",
                user_id="missing",
                email="alex.chen@example.test",
            )
        )["success"]
        is False
    )
    assert (
        body(
            call(
                env,
                "servicenow",
                "get_user",
                user_id="",
                email="alex.chen@example.test",
            )
        )["success"]
        is True
    )


@pytest.mark.parametrize(
    "provider,tool,args",
    [
        ("unknown", "get_user", {}),
        ("okta", "unknown", {}),
        ("okta", "get_user", {"user_id": 123}),
        ("okta", "get_user", {"user_id": "../users"}),
        ("servicenow", "add_group_members", {"group_id": GROUP, "members": [1]}),
        ("benchmark", "workflow_wait", {"seconds": True}),
    ],
)
def test_bad_calls_consume_step(env, provider, tool, args):
    result = env.step(ItopsAction(provider=provider, tool_name=tool, arguments=args))
    assert result.is_error
    assert result.reward == 0
    assert env.state.step_count == 1


def test_partial_failure_continues_and_literal_prefix_fails(env):
    result = call(
        env,
        "servicenow",
        "add_group_members",
        group_id=GROUP,
        members=["alex.chen", "missing", "sys_id:" + USER, "sam.lee"],
    )
    assert body(result)["success"] is False
    assert body(result)["group_name"] is None
    assert (
        env.episode.db.connection.execute(
            "select count(*) from servicenow_memberships"
        ).fetchone()[0]
        == 2
    )
    assert (
        body(
            call(env, "servicenow", "add_group_members", group_id="missing", members=[])
        )["success"]
        is True
    )


def test_redelivery_conflict_and_terminal_freeze(env):
    action = ItopsAction(
        provider="servicenow",
        tool_name="add_group_members",
        arguments={"group_id": GROUP, "members": ["alex.chen"]},
        invocation_id="delivery-1",
    )
    first = env.step(action)
    assert env.step(action) == first
    assert env.state.step_count == 1
    conflict = env.step(
        action.model_copy(
            update={"arguments": {"group_id": OTHER_GROUP, "members": ["alex.chen"]}}
        )
    )
    assert conflict.is_error
    assert env.state.step_count == 2
    result = env.episode.finalize()
    assert result.terminal_reason == "abandoned"
    before = env.state
    assert env.step(action).reward == 0
    assert call(env, "okta", "get_user", user_id="00u-target").done
    assert env.state == before
    assert env.episode.result() == result


def test_reset_isolation_backup_cleanup_and_independent_instances(env, tmp_path):
    other = ItopsEnvironment()
    assert other.episode is None
    other.reset()
    assert other.episode is not None
    call(env, "servicenow", "add_group_members", group_id=GROUP, members=["alex.chen"])
    assert (
        other.episode.db.connection.execute(
            "select count(*) from servicenow_memberships"
        ).fetchone()[0]
        == 0
    )
    old_dir = env.episode.db.directory
    backup = tmp_path / "backup.sqlite3"
    env.episode.snapshot(backup)
    with sqlite3.connect(backup) as db:
        assert (
            db.execute("select count(*) from servicenow_memberships").fetchone()[0] == 1
        )
        assert db.execute("pragma integrity_check").fetchone()[0] == "ok"
    env.reset()
    assert not old_dir.exists()
    assert env.state.step_count == 0
    assert (
        env.episode.db.connection.execute(
            "select count(*) from servicenow_memberships"
        ).fetchone()[0]
        == 0
    )
    current = env.episode.db.directory
    env.close()
    env.close()
    assert not current.exists()
    other.close()


def test_sqlite_failure_rolls_back_step_and_freezes_infrastructure_error(env):
    db = env.episode.db.connection
    db.execute(
        "CREATE TRIGGER fail_insert BEFORE INSERT ON servicenow_memberships BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        call(
            env,
            "servicenow",
            "add_group_members",
            group_id=GROUP,
            members=["alex.chen"],
        )
    assert db.execute("select count(*) from servicenow_memberships").fetchone()[0] == 0
    assert db.execute("select count(*) from journal").fetchone()[0] == 0
    assert env.state.step_count == 0
    assert env.state.phase == "terminal"
    result = env.episode.result()
    assert result.status == "infrastructure_error"
    assert result.reward == 0
    assert env.episode.finalize() == result


def test_invalid_seed_preserves_explicit_failure(env):
    for seed in [-1, True, "42"]:
        with pytest.raises((ValueError, TypeError)):
            env.reset(seed=seed)


def test_scenario_validation_and_named_loader():
    from itops_env.server.core.scenarios import Scenario, load_scenario

    scenario = load_scenario("identity-group-v1")
    for override in [
        {"step_budget": 3},
        {"horizon": 1},
        {"target_user_id": "missing"},
        {
            "events": [
                {
                    "at": 10000,
                    "sequence": 0,
                    "kind": "group_available",
                    "group_id": GROUP,
                }
            ]
        },
        {"costs": {"okta.get_user": -1}},
    ]:
        with pytest.raises(ValueError):
            Scenario.model_validate(scenario.model_dump() | override)
    with pytest.raises(ValueError):
        load_scenario("../../secrets")


def test_delayed_availability_wait_replay_and_horizon():
    from itops_env.server.core.scenarios import Scenario, load_scenario

    data = load_scenario("identity-group-v1").model_dump()
    data["servicenow_groups"][0]["available"] = False
    data["events"] = [
        {"at": 10, "sequence": 1, "kind": "group_available", "group_id": GROUP}
    ]
    scenario = Scenario.model_validate(data)
    traces = []
    for _ in range(2):
        env = ItopsEnvironment(scenario=scenario)
        env.reset(seed=7)
        assert env.episode is not None
        trace = [
            body(
                call(
                    env,
                    "servicenow",
                    "add_group_members",
                    group_id=GROUP,
                    members=["alex.chen"],
                )
            )
        ]
        assert trace[0]["success"] is False
        call(env, "benchmark", "workflow_wait", seconds=10)
        trace.append(
            body(
                call(
                    env,
                    "servicenow",
                    "add_group_members",
                    group_id=GROUP,
                    members=["alex.chen"],
                )
            )
        )
        assert trace[1]["success"] is True
        before = env.episode.db.connection.execute(
            "select count(*) from servicenow_memberships"
        ).fetchone()[0]
        assert call(env, "benchmark", "workflow_wait", seconds=1000).done
        assert env.state.simulated_clock == scenario.horizon
        result = env.episode.result()
        assert result is not None
        assert result.terminal_reason == "horizon"
        assert (
            env.episode.db.connection.execute(
                "select count(*) from servicenow_memberships"
            ).fetchone()[0]
            == before
        )
        traces.append(trace)
        env.close()
    assert traces[0] == traces[1]


def test_step_budget_and_horizon_crossing_do_not_infer_success():
    from itops_env.server.core.scenarios import Scenario, load_scenario

    data = load_scenario().model_dump()
    data["step_budget"] = 4
    instance = ItopsEnvironment(scenario=Scenario.model_validate(data))
    instance.reset()
    try:
        assert instance.episode is not None
        observation = None
        for _ in range(4):
            observation = call(instance, "unknown", "unknown")
        assert observation is not None
        assert observation.done
        assert instance.state.remaining_budget == 0
        result = instance.episode.result()
        assert result is not None
        assert result.terminal_reason == "step_budget"
        assert result.reward == 0
    finally:
        instance.close()
    data["horizon"] = 6
    data["costs"]["servicenow.add_group_members"] = 4
    instance = ItopsEnvironment(scenario=Scenario.model_validate(data))
    instance.reset()
    try:
        assert instance.episode is not None
        call(instance, "benchmark", "workflow_wait", seconds=5)
        assert call(
            instance,
            "servicenow",
            "add_group_members",
            group_id=GROUP,
            members=["alex.chen"],
        ).done
        assert instance.state.simulated_clock == 6
        assert (
            instance.episode.db.connection.execute(
                "select count(*) from servicenow_memberships"
            ).fetchone()[0]
            == 0
        )
    finally:
        instance.close()


def test_equal_time_events_follow_sequence():
    from itops_env.server.core.scenarios import Scenario, load_scenario

    data = load_scenario().model_dump()
    data["events"] = [
        {"at": 2, "sequence": 1, "kind": "group_unavailable", "group_id": GROUP},
        {"at": 2, "sequence": 2, "kind": "group_available", "group_id": GROUP},
    ]
    instance = ItopsEnvironment(scenario=Scenario.model_validate(data))
    instance.reset()
    try:
        assert instance.episode is not None
        call(instance, "benchmark", "workflow_wait", seconds=2)
        assert (
            body(
                call(
                    instance,
                    "servicenow",
                    "add_group_members",
                    group_id=GROUP,
                    members=["alex.chen"],
                )
            )["success"]
            is True
        )
        assert (
            instance.episode.db.connection.execute(
                "select sum(applied) from events"
            ).fetchone()[0]
            == 2
        )
    finally:
        instance.close()


def test_sqlite_failure_after_first_insert_rolls_back_entire_call(env):
    db = env.episode.db.connection
    db.execute(
        "CREATE TRIGGER fail_second BEFORE INSERT ON servicenow_memberships WHEN NEW.user_id = '22222222222222222222222222222222' BEGIN SELECT RAISE(ABORT, 'second insert failure'); END"
    )
    with pytest.raises(sqlite3.IntegrityError, match="second insert failure"):
        call(
            env,
            "servicenow",
            "add_group_members",
            group_id=GROUP,
            members=["alex.chen", "sam.lee"],
        )
    assert db.execute("select count(*) from servicenow_memberships").fetchone()[0] == 0
    assert db.execute("select count(*) from delivery").fetchone()[0] == 0
    assert db.execute("select count(*) from journal").fetchone()[0] == 0
    assert env.episode.result().status == "infrastructure_error"


def test_schema_extras_nullable_fields_and_sql_parameters(env):
    rejected = call(env, "okta", "get_user", user_id="00u-target", ignored="extra")
    assert rejected.is_error
    assert "Additional properties" in body(rejected)["error"]
    assert env.state.step_count == 1
    assert (
        env.episode.db.connection.execute(
            "SELECT count(*) FROM journal WHERE kind = 'read'"
        ).fetchone()[0]
        == 0
    )
    assert (
        body(
            call(
                env,
                "servicenow",
                "get_user",
                user_id=None,
                email="alex.chen@example.test",
            )
        )["success"]
        is True
    )
    assert (
        body(call(env, "servicenow", "get_user", user_id="' OR 1=1 --"))["success"]
        is False
    )
    assert body(call(env, "servicenow", "get_user"))["success"] is False
    assert call(env, "servicenow", "get_user", email=4).is_error


def test_concurrent_redelivery_uses_one_writer(env):
    from concurrent.futures import ThreadPoolExecutor

    action = ItopsAction(
        provider="servicenow",
        tool_name="add_group_members",
        arguments={"group_id": GROUP, "members": ["alex.chen"]},
        invocation_id="shared",
    )
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(env.step, [action] * 20))
    assert all(body(result)["success"] for result in results)
    assert env.state.step_count == 1
    assert (
        env.episode.db.connection.execute(
            "select count(*) from servicenow_memberships"
        ).fetchone()[0]
        == 1
    )


def test_reset_failure_does_not_return_old_episode_as_fresh(env):
    old = env.episode
    call(env, "servicenow", "add_group_members", group_id=GROUP, members=["alex.chen"])
    with pytest.raises(ValueError):
        env.reset(scenario="../../private")
    assert env.episode is old
    assert env.state.step_count == 1


def test_closed_and_uninitialized_lifecycle():
    instance = ItopsEnvironment()
    action = ItopsAction(
        provider="okta", tool_name="get_user", arguments={"user_id": "00u-target"}
    )
    with pytest.raises(RuntimeError, match="Reset"):
        instance.step(action)
    instance.close()
    instance.reset()
    instance.close()
    with pytest.raises(RuntimeError, match="not open"):
        instance.step(action)


def test_infrastructure_result_metrics_are_unknown_not_fabricated_zero(env):
    call(env, "servicenow", "add_group_members", group_id=GROUP, members=["alex.chen"])
    env.episode.db.connection.execute(
        "CREATE TRIGGER fail_insert BEFORE INSERT ON servicenow_memberships BEGIN SELECT RAISE(ABORT, 'injected'); END"
    )
    with pytest.raises(sqlite3.IntegrityError):
        call(
            env, "servicenow", "add_group_members", group_id=GROUP, members=["sam.lee"]
        )
    assert env.episode.result().metrics.membership_count is None
    assert env.episode.result().metrics.effect_count is None


def test_wait_requires_integer_without_float_coercion(env):
    observation = call(env, "benchmark", "workflow_wait", seconds=1.0)
    assert observation.is_error
    assert env.state.step_count == 1
    assert type(env.state.simulated_clock) is int


def test_due_event_rolls_back_with_failing_provider_write():
    from itops_env.server.core.scenarios import Scenario, load_scenario

    data = load_scenario().model_dump()
    data["servicenow_groups"][0]["available"] = False
    data["events"] = [
        {"at": 1, "sequence": 1, "kind": "group_available", "group_id": GROUP}
    ]
    instance = ItopsEnvironment(scenario=Scenario.model_validate(data))
    instance.reset()
    try:
        assert instance.episode is not None
        db = instance.episode.db.connection
        db.execute(
            "CREATE TRIGGER fail_insert BEFORE INSERT ON servicenow_memberships "
            "BEGIN SELECT RAISE(ABORT, 'injected after due event'); END"
        )
        with pytest.raises(sqlite3.IntegrityError, match="injected after due event"):
            call(
                instance,
                "servicenow",
                "add_group_members",
                group_id=GROUP,
                members=["alex.chen"],
            )
        assert (
            db.execute(
                "SELECT available FROM servicenow_groups WHERE sys_id = ?", (GROUP,)
            ).fetchone()[0]
            == 0
        )
        assert (
            db.execute("SELECT applied FROM events WHERE sequence = 1").fetchone()[0]
            == 0
        )
        assert instance.state.simulated_clock == 0
        assert instance.state.step_count == 0
        result = instance.episode.result()
        assert result is not None
        assert result.status == "infrastructure_error"
    finally:
        instance.close()


@pytest.mark.parametrize("operation", ["reset", "close"])
def test_finalization_failure_revokes_owner_and_disposes_resources(
    operation, monkeypatch
):
    from itops_env.server.interfaces.control import EpisodeBinding
    from itops_env.server.storage.database import Database

    created = []
    original_create = Database.create

    def record_create(*args, **kwargs):
        database = original_create(*args, **kwargs)
        created.append(database)
        return database

    monkeypatch.setattr(Database, "create", record_create)
    binding = EpisodeBinding()
    env = ItopsEnvironment(binding=binding)
    env.reset()
    old = env.episode
    capability, generation = binding.capability, binding.generation
    assert old is not None
    assert capability is not None
    old.db.connection.execute(
        "CREATE TRIGGER fail_result BEFORE INSERT ON result BEGIN SELECT RAISE(ABORT, 'injected result persistence failure'); END"
    )
    try:
        with pytest.raises(
            sqlite3.IntegrityError, match="injected result persistence failure"
        ) as caught:
            getattr(env, operation)()
        assert env.episode is old
        result = old.result()
        assert result is not None
        assert result.status == "infrastructure_error"
        assert result.reward == 0
        assert old.state.phase == "closed"
        assert (
            "Infrastructure result could not be persisted" in caught.value.__notes__[0]
        )
        assert (
            binding.env is None
            and binding.capability is None
            and binding.generation is None
        )
        assert not binding.matches(capability)
        assert len(created) == (2 if operation == "reset" else 1)
        assert all(not db.is_open and not db.directory.exists() for db in created)
        replacement = ItopsEnvironment(binding=binding)
        try:
            replacement.reset()
            assert binding.env is replacement and binding.generation != generation
            assert binding.capability != capability
            env.close()
            assert binding.env is replacement
            assert (
                call(replacement, "okta", "get_user", user_id="00u-target").is_error
                is False
            )
        finally:
            replacement.close()
    finally:
        env.close()
        for database in created:
            database.close()


def test_reset_preserves_original_error_if_unpublished_cleanup_also_fails(monkeypatch):
    from itops_env.server.core.episode import Episode
    from itops_env.server.interfaces.control import EpisodeBinding

    binding = EpisodeBinding()
    env = ItopsEnvironment(binding=binding)
    env.reset()
    old = env.episode
    assert old is not None
    old.db.connection.execute(
        "CREATE TRIGGER fail_result BEFORE INSERT ON result BEGIN SELECT RAISE(ABORT, 'old result failure'); END"
    )
    replacement_databases = []
    initialize = Episode.initialize

    def initialize_with_result_failure(episode):
        initialize(episode)
        replacement_databases.append(episode.db)
        episode.db.connection.execute(
            "CREATE TRIGGER fail_result BEFORE INSERT ON result BEGIN SELECT RAISE(ABORT, 'replacement result failure'); END"
        )

    monkeypatch.setattr(Episode, "initialize", initialize_with_result_failure)
    with pytest.raises(sqlite3.IntegrityError, match="old result failure") as caught:
        env.reset()
    assert any(
        "Unpublished replacement cleanup failed: replacement result failure" in note
        for note in caught.value.__notes__
    )
    result = old.result()
    assert result is not None
    assert env.episode is old and result.status == "infrastructure_error"
    assert binding.env is None
    assert all(
        not db.is_open and not db.directory.exists() for db in replacement_databases
    )
    env.close()
