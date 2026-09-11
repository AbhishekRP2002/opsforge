"""Validated, named public development scenarios; no arbitrary server paths."""

import re
from importlib.resources import files
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OktaUser(FixtureModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_\-@.+]+$")
    login: str
    email: str
    first_name: str
    last_name: str
    status: Literal["ACTIVE", "SUSPENDED", "DEPROVISIONED"]


class ServiceNowUser(FixtureModel):
    sys_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    user_name: str
    email: str
    name: str
    active: bool


class ServiceNowGroup(FixtureModel):
    sys_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    name: str
    available: bool = True


class ScheduledEvent(FixtureModel):
    at: int = Field(ge=0)
    sequence: int = Field(ge=0)
    kind: Literal["group_available", "group_unavailable"]
    group_id: str


class Scenario(FixtureModel):
    name: str
    version: str
    policy_version: str
    instruction: str = Field(min_length=1)
    policy: str = Field(min_length=1)
    target_okta_id: str
    target_user_id: str
    target_group_id: str
    identity_links: dict[str, str]
    okta_users: list[OktaUser]
    servicenow_users: list[ServiceNowUser]
    servicenow_groups: list[ServiceNowGroup]
    events: list[ScheduledEvent] = Field(default_factory=list)
    costs: dict[str, int]
    horizon: int = Field(gt=0)
    step_budget: int = Field(ge=4)

    @model_validator(mode="after")
    def validate_world(self) -> Self:
        for rows, fields in [
            (self.okta_users, ("id", "login", "email")),
            (self.servicenow_users, ("sys_id", "user_name", "email")),
            (self.servicenow_groups, ("sys_id", "name")),
        ]:
            for field in fields:
                values = [getattr(row, field) for row in rows]
                if any(not value for value in values) or len(values) != len(
                    set(values)
                ):
                    raise ValueError(f"Nonempty unique {field} values required")
        okta = {row.id: row for row in self.okta_users}
        users = {row.sys_id: row for row in self.servicenow_users}
        groups = {row.sys_id: row for row in self.servicenow_groups}
        if any(".." in row.id for row in self.okta_users):
            raise ValueError("Invalid Okta ID")
        if (
            self.target_okta_id not in okta
            or self.target_user_id not in users
            or self.target_group_id not in groups
        ):
            raise ValueError("Target references must exist")
        if self.identity_links.get(self.target_okta_id) != self.target_user_id:
            raise ValueError("Target identity link required")
        for source, destination in self.identity_links.items():
            if (
                source not in okta
                or destination not in users
                or okta[source].email != users[destination].email
            ):
                raise ValueError("Identity links must connect existing matching emails")
        if (
            okta[self.target_okta_id].status != "ACTIVE"
            or not users[self.target_user_id].active
        ):
            raise ValueError("Target must be active")
        required = {
            "okta.get_user",
            "servicenow.get_user",
            "servicenow.add_group_members",
            "benchmark.workflow_submit",
            "invalid",
        }
        if set(self.costs) != required or any(
            value < 0 for value in self.costs.values()
        ):
            raise ValueError("All selected tool costs must be nonnegative")
        if self.costs["benchmark.workflow_submit"] != 0 or any(
            self.costs[key] == 0 for key in required - {"benchmark.workflow_submit"}
        ):
            raise ValueError("Submit costs zero; other calls have positive duration")
        ordering = [(event.at, event.sequence) for event in self.events]
        if ordering != sorted(ordering) or len(
            {event.sequence for event in self.events}
        ) != len(self.events):
            raise ValueError("Events require chronological order and unique sequence")
        if any(
            event.group_id not in groups or event.at > self.horizon
            for event in self.events
        ):
            raise ValueError("Event references and horizon must be valid")
        read_time = self.costs["okta.get_user"] + self.costs["servicenow.get_user"]
        add_time = self.costs["servicenow.add_group_members"]
        # Find a reachable completion time, respecting equal-time event order.
        candidates = {read_time + add_time} | {
            max(read_time + add_time, event.at) for event in self.events
        }
        possible = False
        for completion in sorted(candidates):
            available = groups[self.target_group_id].available
            for event in self.events:
                if event.at <= completion and event.group_id == self.target_group_id:
                    available = event.kind == "group_available"
            wait_needed = completion > read_time + add_time
            if (
                available
                and completion <= self.horizon
                and self.step_budget >= 4 + int(wait_needed)
            ):
                possible = True
        if not possible:
            raise ValueError("Scenario cannot be completed within horizon and budget")
        return self


def load_scenario(name: str = "identity-group-v1") -> Scenario:
    if name != "identity-group-v1" or not re.fullmatch(r"[a-z0-9-]+", name):
        raise ValueError("Unknown packaged scenario")
    return Scenario.model_validate_json(
        files("itops_env.resources").joinpath("development", name + ".json").read_text()
    )
