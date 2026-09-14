from contextlib import closing

import pytest

from .test_darwinbox import call, fixture_world, leave, ok, records


def test_half_day_unpaid_reject_and_overlapping_batch_are_atomic():
    with closing(fixture_world(records())) as env:
        env.reset()
        half = leave(to_date="04-01-2026", is_half_day="Yes")
        requested = ok(env, "apply_leave", data=[half])[0]
        assert requested["is_firsthalf_secondhalf"] == "1"
        ok(
            env,
            "approve_leave",
            leave_id=requested["leave_id"],
            employee_no="E1",
            action="approve",
        )
        assert (
            ok(env, "get_leave_balance", employee_nos=["E1"], ignore_rounding="1")[0][
                "currently_availabel_balance"
            ]
            == 9.5
        )
        unpaid = leave(
            from_date="06-01-2026", to_date="07-01-2026", is_paid_or_unpaid="unpaid"
        )
        requested = ok(env, "apply_leave", data=[unpaid])[0]
        ok(
            env,
            "approve_leave",
            leave_id=requested["leave_id"],
            employee_no="E1",
            action="approve",
        )
        assert ok(env, "get_leave_balance", employee_nos=["E1"])[0]["taken"] == 0.5
        rejected = ok(
            env,
            "apply_leave",
            data=[leave(from_date="09-01-2026", to_date="10-01-2026")],
        )[0]
        ok(
            env,
            "approve_leave",
            leave_id=rejected["leave_id"],
            employee_no="E1",
            action="reject",
        )
        assert (
            ok(env, "get_leave_balance", employee_nos=["E1"])[0][
                "currently_availabel_balance"
            ]
            == 9.5
        )
        assert call(
            env,
            "apply_leave",
            data=[
                leave(from_date="11-01-2026", to_date="12-01-2026"),
                leave(from_date="12-01-2026", to_date="13-01-2026"),
            ],
        )[1]
        assert env.episode is not None
        assert (
            env.episode.db.connection.execute(
                "SELECT count(*) FROM darwinbox_records WHERE kind='leave'"
            ).fetchone()[0]
            == 3
        )
        assert call(env, "apply_leave", data=[leave(is_half_day="Yes")])[1]
        assert call(env, "apply_leave", data=[half | {"revoke_leave": "Yes"}])[1]


def test_insufficient_allocation_and_revocation_ambiguity():
    with closing(fixture_world(records())) as env:
        env.reset()
        huge = ok(env, "apply_leave", data=[leave(to_date="31-01-2026")])[0]
        assert call(
            env,
            "approve_leave",
            leave_id=huge["leave_id"],
            employee_no="E1",
            action="approve",
        )[1]
        assert (
            ok(env, "get_leave_balance", employee_nos=["E1"])[0][
                "currently_availabel_balance"
            ]
            == 10
        )
        ok(
            env,
            "approve_leave",
            leave_id=huge["leave_id"],
            employee_no="E1",
            action="reject",
        )
        ok(env, "apply_leave", data=[leave()])
        ok(
            env,
            "apply_leave",
            data=[leave(revoke_leave="Yes", revoke_reason="changed")],
        )
        ok(env, "apply_leave", data=[leave()])
        assert call(
            env, "apply_leave", data=[leave(revoke_leave="Yes", revoke_reason="again")]
        )[1]


@pytest.mark.parametrize(
    "field,value",
    [
        ("employee_no", []),
        ("leave_name", {}),
        ("from_date", []),
        ("is_half_day", {}),
        ("revoke_reason", []),
        ("is_firsthalf_secondhalf", []),
    ],
)
def test_malformed_nested_leave_never_escapes_as_infrastructure_failure(field, value):
    with closing(fixture_world(records())) as env:
        env.reset()
        entry = leave(revoke_leave="Yes") | {field: value}
        assert call(env, "apply_leave", data=[entry])[1]
        assert env.state.phase == "active"


def test_history_effective_date_defaults_to_current_mutation_day():
    with closing(fixture_world(records())) as env:
        env.reset()
        ok(
            env,
            "update_employee",
            employee_data={
                "employee_no": "E1",
                "effective_date": "10-01-2026",
                "employee_name": "Grace",
            },
        )
        ok(
            env,
            "update_employee",
            employee_data={"employee_no": "E1", "employee_name": "Ada"},
        )
        changes = ok(
            env,
            "get_employee_history",
            **{"from": "01-01-2026", "to": "01-01-2026", "filter_on_effective_date": 1},
        )
        assert len(changes) == 1 and changes[0]["after"]["employee_name"] == "Ada"


def test_fixture_freeform_employee_numbers_must_remain_json_finite():
    from pydantic import ValidationError

    source = records()
    source[0]["data"]["custom"] = {"salary": float("inf")}
    with pytest.raises(ValidationError):
        fixture_world(source)
