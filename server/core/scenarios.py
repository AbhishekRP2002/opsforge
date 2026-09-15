"""Validated, named public development scenarios; no arbitrary server paths."""

import re
from datetime import datetime
from importlib.resources import files
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..mcp_servers.tools import business_tool_names


class FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OktaUser(FixtureModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_\-@.+]+$")
    login: str
    email: str
    first_name: str
    last_name: str
    status: Literal["STAGED", "ACTIVE", "SUSPENDED", "DEPROVISIONED"]
    profile: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_profile_extras(self) -> Self:
        canonical = {"login", "email", "firstName", "lastName"}
        if canonical.intersection(self.profile):
            raise ValueError("Okta profile extras cannot contain canonical keys")
        return self


class OktaGroup(FixtureModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_\-@.+]+$")
    profile: dict[str, object]


class OktaMembership(FixtureModel):
    group_id: str
    user_id: str


class OktaGroupApp(FixtureModel):
    group_id: str
    app_id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_\-@.+]+$")
    app: dict[str, object]

    @model_validator(mode="after")
    def validate_app_identity(self) -> Self:
        if self.app.get("id") != self.app_id:
            raise ValueError("Okta group app object id must match app_id")
        return self


class ServiceNowUser(FixtureModel):
    sys_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    user_name: str
    email: str
    name: str
    active: bool
    profile: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        if {
            "sys_id",
            "user_name",
            "email",
            "name",
            "active",
            "profile",
            "profile_json",
        }.intersection(self.profile):
            raise ValueError("ServiceNow profile cannot shadow canonical fields")
        return self


class InitialArtifact(FixtureModel):
    path: str
    content: str
    media_type: str

    @model_validator(mode="after")
    def validate_virtual_file(self) -> Self:
        parsed = PurePosixPath(self.path)
        if (
            not self.path.startswith(("/tmp/", "/var/tmp/", "artifacts/"))
            or str(parsed) != self.path
            or ".." in parsed.parts
            or "%" in self.path
            or "\\" in self.path
            or len(self.content.encode()) > 1_048_576
            or not self.media_type.strip()
        ):
            raise ValueError("Invalid episode artifact fixture")
        return self


class ServiceNowGroup(FixtureModel):
    sys_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    name: str
    available: bool = True


class ServiceNowRecord(FixtureModel):
    table: Literal[
        "incident",
        "sc_cat_item",
        "sc_category",
        "item_option_new",
        "change_request",
        "change_task",
        "sysapproval_approver",
        "wf_workflow",
        "wf_workflow_version",
        "wf_activity",
        "sys_update_set",
        "sys_update_xml",
        "sys_script_include",
        "kb_knowledge_base",
        "kb_category",
        "kb_knowledge",
        "rm_story",
        "rm_epic",
        "rm_scrum_task",
        "pm_project",
        "m2m_story_dependencies",
        "sys_scope",
        "sys_user_role",
        "sys_user_has_role",
        "cmn_department",
        "cmn_location",
        "sc_req_item",
    ]
    sys_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    data: dict[str, object]

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if "sys_id" in self.data:
            raise ValueError("Record data cannot shadow sys_id")
        if self.table in {"wf_workflow", "wf_workflow_version", "wf_activity"}:
            for field in ("name", "table", "description", "activity_type"):
                if field in self.data and not isinstance(self.data[field], str):
                    raise ValueError(f"Workflow fixture {field} must be text")
            for field in ("order", "version"):
                if field in self.data:
                    value = self.data[field]
                    if isinstance(value, bool) or not isinstance(value, (int, str)):
                        raise ValueError(
                            f"Workflow fixture {field} must be an integer or integer string"
                        )
                    try:
                        int(value)
                    except ValueError as error:
                        raise ValueError(
                            f"Workflow fixture {field} must be an integer or integer string"
                        ) from error
            for field in ("active", "published"):
                if field in self.data and not (
                    isinstance(self.data[field], bool)
                    or self.data[field] in ("true", "false")
                ):
                    raise ValueError(
                        f"Workflow fixture {field} must be a boolean or boolean string"
                    )
        for field in ("script", "payload"):
            value = self.data.get(field)
            if value is not None and (
                not isinstance(value, str) or len(value.encode()) > 1_048_576
            ):
                raise ValueError("Opaque fixture payload must be text of at most 1 MiB")
        return self


class ERPNextRecord(FixtureModel):
    doctype: str
    name: str = Field(pattern=r"^[a-zA-Z0-9_@.+ -]+$")
    data: dict[str, object]
    docstatus: Literal[0, 1, 2] = 0

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        from ..services import erpnext_store as store

        store.doctype(self.doctype)
        if self.doctype == "File" or store.INTERNAL.intersection(self.data):
            raise ValueError(
                "ERPNext fixture cannot supply File or internal document fields"
            )
        if self.doctype == "Item" and self.data.get("item_code") != self.name:
            raise ValueError("Item fixture identity must equal item_code")
        if self.doctype == "User" and "@" not in self.name:
            raise ValueError("User fixture identity must be an email")
        store.validate(self.doctype, self.data)
        return self


class DarwinboxRecord(FixtureModel):
    kind: str
    id: str = Field(min_length=1)
    data: dict[str, object]


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
    okta_groups: list[OktaGroup] = Field(default_factory=list)
    okta_memberships: list[OktaMembership] = Field(default_factory=list)
    okta_group_apps: list[OktaGroupApp] = Field(default_factory=list)
    okta_applications: list[dict[str, object]] = Field(default_factory=list)
    okta_log_events: list[dict[str, object]] = Field(default_factory=list)
    initial_artifacts: list[InitialArtifact] = Field(default_factory=list)
    okta_auth_mode: Literal["user", "service"] = "user"
    okta_scopes: list[str] = Field(
        default_factory=lambda: [
            "okta.users.read",
            "okta.users.manage",
            "okta.groups.read",
            "okta.groups.manage",
            "okta.apps.read",
            "okta.apps.manage",
            "okta.policies.read",
            "okta.policies.manage",
            "okta.brands.read",
            "okta.brands.manage",
            "okta.domains.read",
            "okta.domains.manage",
            "okta.emailDomains.read",
            "okta.emailDomains.manage",
            "okta.templates.read",
            "okta.templates.manage",
            "okta.deviceAssurance.read",
            "okta.deviceAssurance.manage",
            "okta.logs.read",
        ]
    )
    servicenow_users: list[ServiceNowUser]
    servicenow_groups: list[ServiceNowGroup]
    servicenow_records: list[ServiceNowRecord] = Field(default_factory=list)
    servicenow_denied_operations: dict[str, list[str]] = Field(default_factory=dict)
    erpnext_records: list[ERPNextRecord] = Field(default_factory=list)
    erpnext_epoch: str = "2026-01-01T00:00:00+00:00"
    erpnext_assignment_failures: list[str] = Field(default_factory=list)
    darwinbox_records: list[DarwinboxRecord] = Field(default_factory=list)
    darwinbox_epoch: str = "2026-01-01T00:00:00+00:00"
    jira_projects: list[dict] = Field(default_factory=list)
    jira_users: list[dict] = Field(default_factory=list)
    jira_issues: list[dict] = Field(default_factory=list)
    jira_watchers: list[dict] = Field(default_factory=list)
    jira_comments: list[dict] = Field(default_factory=list)
    jira_worklogs: list[dict] = Field(default_factory=list)
    jira_request_issue_ids: list = Field(default_factory=list)
    jira_internal_only_projects: list[str] = Field(default_factory=list)
    jira_link_types: list[dict] = Field(default_factory=list)
    jira_issue_links: list[dict] = Field(default_factory=list)
    jira_remote_links: list[dict] = Field(default_factory=list)
    jira_transitions: list[dict] = Field(default_factory=list)
    jira_status_history: list[dict] = Field(default_factory=list)
    jira_boards: list[dict] = Field(default_factory=list)
    jira_sprints: list[dict] = Field(default_factory=list)
    jira_sprint_issues: list[dict] = Field(default_factory=list)
    jira_versions: list[dict] = Field(default_factory=list)
    jira_service_desks: list[dict] = Field(default_factory=list)
    jira_queues: list[dict] = Field(default_factory=list)
    jira_request_types: list[dict] = Field(default_factory=list)
    jira_requests: list[dict] = Field(default_factory=list)
    jira_forms: list[dict] = Field(default_factory=list)
    jira_attachments: list[dict] = Field(default_factory=list)
    jira_development_records: list[dict] = Field(default_factory=list)
    jira_sla: dict = Field(default_factory=dict)
    jira_current_user: str | None = None
    jira_projects_filter: list[str] = Field(default_factory=list)
    jira_epoch: str = "2026-01-01T00:00:00+00:00"
    jira_read_only: bool = False
    jira_edition: Literal["cloud", "server"] = "cloud"
    events: list[ScheduledEvent] = Field(default_factory=list)
    costs: dict[str, int]
    default_tool_cost: int = Field(default=1, gt=0)
    horizon: int = Field(gt=0)
    step_budget: int = Field(ge=4)

    @model_validator(mode="after")
    def validate_world(self) -> Self:
        from ..services import erpnext_store as store
        from ..services.darwinbox_seed import validate as validate_darwinbox

        validate_darwinbox(self.darwinbox_records, self.darwinbox_epoch)
        from ..services.jira_store import validate_fixtures

        validate_fixtures(self)

        epoch = datetime.fromisoformat(self.erpnext_epoch)
        offset = epoch.utcoffset()
        if offset is None or offset.total_seconds() != 0:
            raise ValueError("ERPNext epoch requires UTC timezone")
        erpnext_fixture_records = {
            (row.doctype, row.name): row.data for row in self.erpnext_records
        }
        if len(erpnext_fixture_records) != len(self.erpnext_records) or len(
            {row.name for row in self.erpnext_records}
        ) != len(erpnext_fixture_records):
            raise ValueError("Unique ERPNext fixture identities required")

        def lookup(kind, name):
            key = (store.doctype(kind), store.text(name, "reference"))
            if key not in erpnext_fixture_records:
                raise ValueError(f"ERPNext reference {key} does not exist")
            return erpnext_fixture_records[key]

        for row in self.erpnext_records:
            store.validate_references(row.doctype, row.data, lookup)
        if any(
            not isinstance(user, str) or "@" not in user
            for user in self.erpnext_assignment_failures
        ):
            raise ValueError("Assignment failure fixtures require email identities")
        record_ids = [(row.table, row.sys_id) for row in self.servicenow_records]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("Unique ServiceNow table record IDs required")
        allowed_denials = {"sysapproval_approver.create", "change_request.update"}
        if not self.servicenow_denied_operations.keys() <= allowed_denials:
            raise ValueError("Unsupported ServiceNow denied operation fixture")
        if any(
            not keys
            or any(
                key != "*" and not re.fullmatch(r"[0-9a-f]{32}", key) for key in keys
            )
            for keys in self.servicenow_denied_operations.values()
        ):
            raise ValueError(
                "Denied operation fixture requires IDs or explicit wildcard"
            )
        references = {
            "incident": {
                "caller_id": "sys_user",
                "assigned_to": "sys_user",
                "assignment_group": "sys_user_group",
            },
            "sc_cat_item": {"category": "sc_category"},
            "sc_category": {"parent": "sc_category"},
            "item_option_new": {"cat_item": "sc_cat_item"},
            "change_request": {
                "requested_by": "sys_user",
                "assignment_group": "sys_user_group",
            },
            "change_task": {
                "change_request": "change_request",
                "assigned_to": "sys_user",
            },
            "sysapproval_approver": {"document_id": "change_request"},
            "wf_workflow_version": {"workflow": "wf_workflow"},
            "wf_activity": {"workflow_version": "wf_workflow_version"},
            "sys_update_set": {"application": "sys_scope", "developer": "sys_user"},
            "sys_update_xml": {"update_set": "sys_update_set"},
            "kb_category": {
                "kb_knowledge_base": "kb_knowledge_base",
                "parent": "kb_category",
            },
            "kb_knowledge": {
                "kb_knowledge_base": "kb_knowledge_base",
                "kb_category": "kb_category",
                "workflow_version": "wf_workflow_version",
            },
            "rm_story": {
                "epic": "rm_epic",
                "project": "pm_project",
                "assigned_to": "sys_user",
                "assignment_group": "sys_user_group",
            },
            "rm_epic": {
                "assigned_to": "sys_user",
                "assignment_group": "sys_user_group",
            },
            "rm_scrum_task": {
                "story": "rm_story",
                "assigned_to": "sys_user",
                "assignment_group": "sys_user_group",
            },
            "pm_project": {
                "project_manager": "sys_user",
                "assigned_to": "sys_user",
                "assignment_group": "sys_user_group",
            },
            "m2m_story_dependencies": {
                "dependent_story": "rm_story",
                "prerequisite_story": "rm_story",
            },
            "sys_user_has_role": {"user": "sys_user", "role": "sys_user_role"},
        }
        identifiers = (
            set(record_ids)
            | {("sys_user", row.sys_id) for row in self.servicenow_users}
            | {("sys_user_group", row.sys_id) for row in self.servicenow_groups}
        )
        for record in self.servicenow_records:
            required = {
                "item_option_new": ("cat_item",),
                "change_task": ("change_request",),
                "sysapproval_approver": ("document_id",),
                "wf_workflow_version": ("workflow",),
                "wf_activity": ("workflow_version",),
                "sys_update_set": ("application",),
                "sys_update_xml": ("update_set",),
                "kb_category": ("kb_knowledge_base",),
                "kb_knowledge": ("kb_knowledge_base", "kb_category"),
                "rm_scrum_task": ("story",),
                "m2m_story_dependencies": ("dependent_story", "prerequisite_story"),
                "sys_user_has_role": ("user", "role"),
            }.get(record.table, ())
            for field in required:
                if not record.data.get(field):
                    raise ValueError(
                        f"Invalid ServiceNow fixture reference {record.table}.{field}: required"
                    )
            for field, table in references.get(record.table, {}).items():
                value = record.data.get(field)
                if value is not None and (
                    not isinstance(value, str)
                    or (value != "" and (table, value) not in identifiers)
                ):
                    raise ValueError(
                        f"Invalid ServiceNow fixture reference {record.table}.{field}"
                    )
        paths = [item.path for item in self.initial_artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("Unique artifact paths required")
        for records in (self.okta_applications, self.okta_log_events):
            identifiers = [row.get("id") for row in records]
            if any(
                not isinstance(identifier, str)
                or not re.fullmatch(r"[a-zA-Z0-9_\-@.+]+", identifier)
                or ".." in identifier
                for identifier in identifiers
            ) or len(identifiers) != len(set(identifiers)):
                raise ValueError("Nonempty unique valid Okta fixture IDs required")
        for app in self.okta_applications:
            if (
                not isinstance(app.get("label"), str)
                or not app["label"]
                or app.get("status") not in {"ACTIVE", "INACTIVE"}
            ):
                raise ValueError(
                    "Application fixtures require a label and valid status"
                )
        for event in self.okta_log_events:
            published = event.get("published")
            actor, outcome = event.get("actor"), event.get("outcome")
            if (
                not isinstance(published, str)
                or datetime.fromisoformat(published).tzinfo is None
                or not isinstance(event.get("uuid"), str)
                or not isinstance(event.get("eventType"), str)
                or not isinstance(actor, dict)
                or not isinstance(actor.get("id"), str)
                or not isinstance(outcome, dict)
                or outcome.get("result")
                not in {"SUCCESS", "FAILURE", "DENY", "ALLOW", "CHALLENGE", "UNKNOWN"}
            ):
                raise ValueError("Invalid Okta log fixture")
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
        group_ids = {row.id for row in self.okta_groups}
        if len(group_ids) != len(self.okta_groups):
            raise ValueError("Unique Okta group IDs required")
        if len(set(self.okta_scopes)) != len(self.okta_scopes):
            raise ValueError("Unique Okta scopes required")
        allowed_scopes = {
            "okta.users.read",
            "okta.users.manage",
            "okta.groups.read",
            "okta.groups.manage",
            "okta.apps.read",
            "okta.apps.manage",
            "okta.policies.read",
            "okta.policies.manage",
            "okta.brands.read",
            "okta.brands.manage",
            "okta.domains.read",
            "okta.domains.manage",
            "okta.emailDomains.read",
            "okta.emailDomains.manage",
            "okta.templates.read",
            "okta.templates.manage",
            "okta.deviceAssurance.read",
            "okta.deviceAssurance.manage",
            "okta.logs.read",
        }
        if not set(self.okta_scopes).issubset(allowed_scopes):
            raise ValueError("Unsupported Okta scope")
        if any(
            m.user_id not in okta or m.group_id not in group_ids
            for m in self.okta_memberships
        ):
            raise ValueError("Okta memberships require existing users and groups")
        if any(a.group_id not in group_ids for a in self.okta_group_apps):
            raise ValueError("Okta group applications require existing groups")
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
        extra = set(self.costs) - required
        if not required.issubset(self.costs) or any(
            type(value) is not int for value in self.costs.values()
        ):
            raise ValueError("Required costs must be integer values")
        if "benchmark.workflow_wait" in extra or not extra.issubset(
            business_tool_names()
        ):
            raise ValueError("Cost overrides must identify registered business tools")
        if any(
            value <= 0
            for key, value in self.costs.items()
            if key not in {"benchmark.workflow_submit"}
        ):
            raise ValueError("All non-submit tool costs must be positive")
        if self.costs["benchmark.workflow_submit"] != 0:
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
