"""Meaningful coverage for the extended Jira service families."""

import base64
import importlib
import json

from itops_env.server.services.results import ServiceContent

from .test_jira_core import database
from .test_jira_relations import workflow_fixtures

MODULES = (
    "jira_core",
    "jira_relations",
    "jira_workflow",
    "jira_agile",
    "jira_metadata",
    "jira_service_desk",
    "jira_forms",
    "jira_insights",
)


def call(db, tool_name, clock=3600, **arguments):
    handlers = {}
    for module in MODULES:
        handlers.update(
            importlib.import_module(f"itops_env.server.services.{module}").HANDLERS
        )
    with db.connection:
        return handlers[tool_name](db, arguments, 1, clock)


def ok(db, tool_name, **arguments):
    result, error = call(db, tool_name, **arguments)
    assert not error, result
    return result


def extended_fixtures():
    fixtures = workflow_fixtures()
    ops = fixtures["jira_projects"][0]
    ops["components"] = [{"id": "c1", "name": "Platform"}]
    ops["field_names"] = {"customfield_100": "Environment"}
    ops["fields"] = [
        {
            "id": "summary",
            "name": "Summary",
            "required": True,
            "schema": {"type": "string"},
        },
        {
            "id": "customfield_100",
            "name": "Environment",
            "required": False,
            "schema": {"type": "option"},
        },
    ]
    ops["field_options"] = {
        "customfield_100": [
            {"id": "1", "value": "Production"},
            {"id": "2", "value": "Staging"},
        ]
    }
    return fixtures | {
        "jira_versions": [
            {
                "id": 10,
                "project_key": "OPS",
                "name": "v1",
                "start_date": "2026-01-01",
                "release_date": "2026-02-01",
            }
        ],
        "jira_service_desks": [
            {"id": "4", "project_key": "OPS", "name": "Operations desk"}
        ],
        "jira_queues": [
            {
                "id": "47",
                "service_desk_id": "4",
                "name": "Open work",
                "jql": "project=OPS AND status=Open",
            }
        ],
        "jira_request_types": [
            {
                "id": "23",
                "service_desk_id": "4",
                "name": "Access",
                "issue_type": "Task",
                "fields": [{"field_id": "summary", "required": True}],
            }
        ],
        "jira_forms": [
            {
                "id": "form-1",
                "issue_id": 1,
                "name": "Review",
                "status": "open",
                "design": {
                    "questions": [
                        {"id": "q1", "type": "TEXT"},
                        {"id": "q2", "type": "DATE"},
                    ]
                },
                "answers": [],
            }
        ],
        "initial_artifacts": [
            {
                "path": "artifacts/input/evidence.png",
                "content": "image-bytes",
                "media_type": "image/png",
            }
        ],
        "jira_attachments": [
            {
                "issue_id": 1,
                "path": "artifacts/input/evidence.png",
                "filename": "evidence.png",
                "media_type": "image/png",
            }
        ],
        "jira_development_records": [
            {
                "issue_id": 1,
                "application_type": "GitHub",
                "data_type": "pullrequest",
                "data": {"id": 7, "name": "Fix OPS-1", "status": "OPEN"},
            }
        ],
    }


def test_project_metadata_and_version_lifecycle():
    with database(**extended_fixtures()) as db:
        assert (
            ok(db, "jira_search_fields", keyword="environment")[0]["id"]
            == "customfield_100"
        )
        assert ok(
            db,
            "jira_get_field_options",
            field_id="customfield_100",
            project_key="OPS",
            values_only=True,
        ) == ["Production", "Staging"]
        assert (
            ok(db, "jira_get_create_fields", project_key="OPS", issue_type_id="1")[
                "fields"
            ][0]["id"]
            == "summary"
        )
        assert (
            ok(db, "jira_get_project_components", project_key="OPS")[0]["name"]
            == "Platform"
        )
        assert (
            ok(db, "jira_get_project_issue_types", project_key="OPS")[0]["name"]
            == "Task"
        )
        assert ok(db, "jira_get_all_projects")[0]["key"] == "DEV"
        assert ok(db, "jira_search_projects", query="oper")[0]["key"] == "OPS"
        assert (
            ok(db, "jira_get_project_fields", project_key="OPS")["fields"][1]["name"]
            == "Environment"
        )
        created = ok(
            db,
            "jira_create_version",
            project_key="OPS",
            name="v2",
            start_date="2026-02-01",
            release_date="2026-03-01",
        )
        assert (
            ok(db, "jira_update_version", version_id=created["id"], released=True)[
                "released"
            ]
            is True
        )
        batch = ok(
            db,
            "jira_batch_create_versions",
            project_key="OPS",
            versions=json.dumps([{"name": "v3"}, {"name": "v1"}]),
        )
        assert len(batch["created"]) == len(batch["failed"]) == 1
        assert [
            item["name"]
            for item in ok(db, "jira_get_project_versions", project_key="OPS")
        ] == ["v1", "v2", "v3"]


def test_service_request_forms_and_attachment_content():
    with database(**extended_fixtures()) as db:
        assert (
            ok(db, "jira_get_service_desk_for_project", project_key="OPS")["id"] == "4"
        )
        assert (
            ok(db, "jira_get_service_desk_queues", service_desk_id="4")["values"][0][
                "id"
            ]
            == "47"
        )
        assert (
            ok(db, "jira_get_request_types", service_desk_id="4")["values"][0]["id"]
            == "23"
        )
        assert (
            ok(
                db,
                "jira_get_request_type_fields",
                service_desk_id="4",
                request_type_id="23",
            )["requestTypeFields"][0]["required"]
            is True
        )
        assert (
            len(
                ok(db, "jira_get_queue_issues", service_desk_id="4", queue_id="47")[
                    "values"
                ]
            )
            == 2
        )
        request = ok(
            db,
            "jira_create_customer_request",
            service_desk_id="4",
            request_type_id="23",
            request_field_values='{"summary":"VPN access"}',
            attachments=json.dumps(
                [
                    {
                        "filename": "request.txt",
                        "mime_type": "text/plain",
                        "base64": base64.b64encode(b"request evidence").decode(),
                    }
                ]
            ),
        )
        assert (
            request["issueKey"] == "OPS-3" and request["attachments"][0]["size"] == 16
        )
        form = ok(
            db,
            "jira_update_proforma_form_answers",
            issue_key="OPS-1",
            form_id="form-1",
            answers=[
                {"questionId": "q1", "type": "TEXT", "value": "Approved"},
                {"questionId": "q2", "type": "DATE", "value": "2026-01-05"},
            ],
        )
        assert form["form"]["answers"][0]["value"] == "Approved"
        assert (
            ok(db, "jira_get_issue_proforma_forms", issue_key="OPS-1")[0]["id"]
            == "form-1"
        )
        assert (
            ok(
                db,
                "jira_get_proforma_form_details",
                issue_key="OPS-1",
                form_id="form-1",
            )["answers"][1]["value"]
            == "2026-01-05"
        )
        images = ok(db, "jira_get_issue_images", issue_key="OPS-1")
        assert isinstance(images, ServiceContent) and images.content[1].type == "image"
        downloads = ok(db, "jira_download_attachments", issue_key="OPS-1")
        assert (
            isinstance(downloads, ServiceContent)
            and downloads.content[1].type == "resource"
        )


def test_ordered_update_history_sla_and_insights():
    fixtures = extended_fixtures()
    fixtures["initial_artifacts"].append(
        {
            "path": "artifacts/input/note.txt",
            "content": "note",
            "media_type": "text/plain",
        }
    )
    with database(**fixtures) as db:
        updated = ok(
            db,
            "jira_update_issue",
            issue_key="OPS-1",
            fields='{"summary":"Updated","duedate":"2026-01-03"}',
            components="Platform",
            attachments='["artifacts/input/note.txt"]',
            comment="Investigating",
            worklog="30m",
            transition="Start",
            return_fields="summary,status",
        )
        assert updated["operations_failed"] == []
        assert updated["operations_performed"] == [
            "fields",
            "components",
            "attachment",
            "comment",
            "worklog",
            "transition",
        ]
        assert updated["issue"]["status"]["name"] == "Doing"
        partial = ok(
            db,
            "jira_update_issue",
            issue_key="OPS-1",
            fields='{"summary":"Partially updated"}',
            components=42,
            comment="Valid operation still applies",
        )
        assert partial["operations_performed"] == ["fields", "comment"]
        assert partial["operations_failed"] == [
            {"operation": "components", "error": "components must be a nonempty string"}
        ]
        assert partial["issue"]["summary"] == "Partially updated"
        assert (
            len(ok(db, "jira_batch_get_changelogs", issue_ids_or_keys="OPS-1")["OPS-1"])
            == 1
        )
        dates = ok(db, "jira_get_issue_dates", issue_key="OPS-1", clock=7200)
        assert dates["statusSummary"]["Open"] == 3600
        sla = ok(
            db,
            "jira_get_issue_sla",
            issue_key="OPS-1",
            metrics="lead_time,time_in_status,first_response_time",
            clock=7200,
        )
        assert sla["metrics"]["first_response_time"] == 3600
        assert (
            ok(db, "jira_get_issue_development_info", issue_key="OPS-1")["development"][
                0
            ]["data"]["id"]
            == 7
        )
        assert (
            ok(db, "jira_get_issues_development_info", issue_keys="OPS-1")["OPS-1"][0][
                "applicationType"
            ]
            == "GitHub"
        )
        epic = ok(
            db,
            "jira_create_issue",
            project_key="OPS",
            summary="Parent",
            issue_type="Epic",
        )["issue"]
        ok(db, "jira_link_to_epic", issue_key="OPS-1", epic_key=epic["key"])
        assert (
            ok(db, "jira_get_project_epic_hierarchy", project_key="OPS")["epics"][0][
                "children"
            ][0]["key"]
            == "OPS-1"
        )
        dev = ok(
            db,
            "jira_create_issue",
            project_key="DEV",
            summary="External",
            issue_type="Task",
        )["issue"]
        ok(
            db,
            "jira_create_issue_link",
            link_type="Blocks",
            inward_issue_key="OPS-1",
            outward_issue_key=dev["key"],
        )
        assert (
            ok(db, "jira_get_cross_project_dependencies", project_key="OPS")[
                "dependencies"
            ][0]["outwardIssue"]
            == "DEV-1"
        )


def test_extended_writes_honor_read_only_and_fail_without_mutation():
    with database(**extended_fixtures(), jira_read_only=True) as db:
        assert call(db, "jira_create_version", project_key="OPS", name="blocked")[1]
        assert call(
            db,
            "jira_create_customer_request",
            service_desk_id="4",
            request_type_id="23",
            request_field_values='{"summary":"blocked"}',
        )[1]
        assert call(
            db,
            "jira_update_proforma_form_answers",
            issue_key="OPS-1",
            form_id="form-1",
            answers=[],
        )[1]
        assert call(
            db, "jira_update_issue", issue_key="OPS-1", fields='{"summary":"blocked"}'
        )[1]
        assert ok(db, "jira_get_project_versions", project_key="OPS")[0]["name"] == "v1"
