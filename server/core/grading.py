"""Trusted canonical grading from rows and journal; never from summary prose."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from ..storage.database import Database
from .scenarios import Scenario


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResultMetrics(FrozenModel):
    steps: int
    simulated_clock: int
    membership_count: int | None
    effect_count: int | None


class ResultEvidence(FrozenModel):
    checks: tuple[tuple[str, bool], ...]
    memberships: tuple[tuple[str, str], ...]
    effects: tuple[tuple[int, str, str], ...]
    required_read_steps: tuple[int | None, int | None]


class EpisodeResult(FrozenModel):
    episode_id: str
    status: Literal["success", "failure", "infrastructure_error"]
    terminal_reason: str
    reward: float
    scenario_version: str
    policy_version: str
    grader_version: str = "identity-group-v1:1"
    engine_version: str = "sqlite-episode:1"
    metrics: ResultMetrics
    evidence: ResultEvidence | None


def grade(
    db: Database,
    scenario: Scenario,
    episode_id: str,
    step: int,
    clock: int,
    reason: str,
    submission: dict | None = None,
) -> EpisodeResult:
    memberships = tuple(
        (row["user_id"], row["group_id"])
        for row in db.connection.execute(
            "SELECT user_id, group_id FROM servicenow_memberships ORDER BY sys_id"
        )
    )
    effects = tuple(
        (row["step"], row["record_id"], row["group_id"])
        for row in db.connection.execute(
            "SELECT * FROM journal WHERE kind = 'membership_added' ORDER BY sequence"
        )
    )
    reads = []
    for provider, record_id in (
        ("okta", scenario.target_okta_id),
        ("servicenow", scenario.target_user_id),
    ):
        reads.append(
            db.connection.execute(
                "SELECT min(step) FROM journal WHERE kind = 'read' AND provider = ? AND record_id = ?",
                (provider, record_id),
            ).fetchone()[0]
        )
    expected = (scenario.target_user_id, scenario.target_group_id)
    submitted = submission is not None
    checks = (
        (
            "explicit_completed_submission",
            submitted and submission.get("disposition") == "completed",
        ),
        (
            "correct_references",
            submitted
            and (submission.get("user_id"), submission.get("group_id")) == expected,
        ),
        ("exact_membership", memberships == (expected,)),
        ("exact_effect", len(effects) == 1 and effects[0][1:] == expected),
        (
            "required_reads_before_effect",
            bool(effects)
            and all(read is not None and read < effects[0][0] for read in reads),
        ),
    )
    success = all(passed for _, passed in checks)
    return EpisodeResult(
        episode_id=episode_id,
        status="success" if success else "failure",
        terminal_reason=reason,
        reward=float(success),
        scenario_version=scenario.version,
        policy_version=scenario.policy_version,
        metrics=ResultMetrics(
            steps=step,
            simulated_clock=clock,
            membership_count=len(memberships),
            effect_count=len(effects),
        ),
        evidence=ResultEvidence(
            checks=checks,
            memberships=memberships,
            effects=effects,
            required_read_steps=tuple(reads),
        ),
    )
