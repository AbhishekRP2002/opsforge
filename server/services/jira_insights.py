"""Issue updates, artifacts, history metrics, and relationship insights."""

import base64
import json
from copy import deepcopy
from datetime import UTC, datetime, time, timedelta
from urllib.parse import quote

from . import jira_relations as activity
from . import jira_store as s
from .results import ServiceContent


def issue_by_identity(db, value):
    value = s.text(value, "issue identity")
    if value.isdigit():
        row = db.connection.execute(
            "SELECT key FROM jira_issues WHERE id=?", (int(value),)
        ).fetchone()
        if row is None:
            raise s.BusinessError(f"Issue {value} not found")
        value = row[0]
    return s.issue(db, value)


@s.handler()
def batch_get_changelogs(db, args, step, clock):
    if s.config(db)["jira_edition"] != "cloud":
        raise s.BusinessError("Batch changelogs are available only on Jira Cloud")
    identities = [
        value.strip()
        for value in s.text(args.get("issue_ids_or_keys"), "issue_ids_or_keys").split(
            ","
        )
        if value.strip()
    ]
    if not identities or len(identities) > 100:
        raise s.BusinessError("Supply between 1 and 100 issue identities")
    fields = {
        value.strip().casefold()
        for value in (args.get("fields") or "").split(",")
        if value.strip()
    }
    limit = args.get("limit", -1)
    if type(limit) is not int or limit == 0 or limit < -1:
        raise s.BusinessError("limit must be -1 or a positive integer")
    result = {}
    for identity in identities:
        record = issue_by_identity(db, identity)
        changes = activity_history(db, record)
        if fields:
            changes = [
                change
                | {
                    "items": [
                        item
                        for item in change["items"]
                        if item["field"].casefold() in fields
                    ]
                }
                for change in changes
            ]
            changes = [change for change in changes if change["items"]]
        result[record["key"]] = changes if limit == -1 else changes[:limit]
    return result


def activity_history(db, record):
    from .jira_workflow import changelogs

    return changelogs(db, record)


def parse_paths(value):
    if value is None or value == "":
        return []
    if isinstance(value, str) and value.lstrip().startswith("["):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as error:
            raise s.BusinessError("Invalid attachments JSON") from error
    elif isinstance(value, str):
        value = [part.strip() for part in value.split(",") if part.strip()]
    paths = [s.text(path, "attachment path") for path in s.array(value, "attachments")]
    if len(paths) != len(set(paths)):
        raise s.BusinessError("Duplicate attachment paths")
    return paths


def attach_existing(db, record, path):
    artifact = db.artifact(path)
    if artifact is None:
        raise s.BusinessError(f"Episode artifact {path} not found")
    owner = db.connection.execute(
        "SELECT issue_id FROM jira_attachments WHERE path=?", (path,)
    ).fetchone()
    if owner is not None and owner[0] != record["id"]:
        raise s.BusinessError(f"Artifact {path} belongs to another issue")
    if owner is None:
        filename = path.rsplit("/", 1)[-1]
        cursor = db.connection.execute(
            "INSERT INTO jira_attachments(issue_id,path,filename,media_type) VALUES (?,?,?,?)",
            (record["id"], path, filename, artifact["media_type"]),
        )
        return str(cursor.lastrowid)
    return str(
        db.connection.execute(
            "SELECT id FROM jira_attachments WHERE path=?", (path,)
        ).fetchone()[0]
    )


def update_fields(db, record, changes):
    changes = s.obj(changes, "fields")
    protected = {
        "id",
        "key",
        "project",
        "project_key",
        "created",
        "updated",
        "status",
        "issue_type",
    }
    if protected.intersection(changes):
        raise s.BusinessError(
            "Issue identity and workflow fields require dedicated operations"
        )
    data = dict(record["data"])
    parent = changes.pop("parent", ...) if "parent" in changes else ...
    if parent is not ...:
        if s.config(db)["jira_edition"] != "cloud":
            raise s.BusinessError("Parent update is available only on Jira Cloud")
        if parent is None:
            record["parent_id"] = None
        else:
            key = parent.get("key") if isinstance(parent, dict) else parent
            target = s.issue(db, key)
            if target["id"] == record["id"]:
                raise s.BusinessError("Issue cannot be its own parent")
            record["parent_id"] = target["id"]
    if "assignee" in changes:
        changes["assignee"] = s.assignee(db, changes["assignee"], data["project_key"])
    data.update(changes)
    s.validate_fields(data, s.project(db, data["project_key"]))
    record["data"] = data


@s.handler(write=True)
def update_issue(db, args, step, clock):
    from .jira_core import projection
    from .jira_workflow import transition_record

    record = s.issue(db, args.get("issue_key"))
    performed, failed = [], []

    def attempt(name, function):
        before = deepcopy(record)
        db.connection.execute("SAVEPOINT jira_update_operation")
        try:
            function()
        except s.BusinessError as error:
            db.connection.execute("ROLLBACK TO jira_update_operation")
            record.clear()
            record.update(before)
            failed.append({"operation": name, "error": str(error)})
        else:
            performed.append(name)
        finally:
            db.connection.execute("RELEASE jira_update_operation")

    for field in ("fields", "additional_fields"):
        if args.get(field):
            attempt(
                field,
                lambda field=field: update_fields(
                    db, record, s.json_object(args[field], field)
                ),
            )
    if args.get("components") is not None:
        attempt(
            "components",
            lambda: update_fields(
                db,
                record,
                {
                    "components": [
                        value.strip()
                        for value in s.text(args["components"], "components").split(",")
                        if value.strip()
                    ]
                },
            ),
        )
    for path in parse_paths(args.get("attachments")):
        attempt("attachment", lambda path=path: attach_existing(db, record, path))
    if args.get("comment") is not None:
        attempt(
            "comment",
            lambda: activity.add_comment_record(
                db,
                record,
                args["comment"],
                clock,
                visibility_value=activity.visibility(args.get("comment_visibility")),
            ),
        )
    if args.get("worklog") is not None:
        attempt(
            "worklog",
            lambda: activity.add_worklog_record(
                db,
                record,
                {"time_spent": args["worklog"], "started": args.get("worklog_started")},
                clock,
            ),
        )
    if args.get("transition") is not None:
        attempt(
            "transition",
            lambda: transition_record(db, record, args["transition"], clock),
        )
    if any(
        name in performed
        for name in ("fields", "additional_fields", "components", "attachment")
    ):
        activity.touch(db, record, clock)
    if not performed and not failed:
        raise s.BusinessError("No update operation was supplied")
    return {
        "issue": projection(
            db, s.issue(db, record["key"]), args.get("return_fields", "*all")
        ),
        "operations_performed": performed,
        "operations_failed": failed,
    }


def attachment_rows(db, record):
    rows = []
    for row in db.connection.execute(
        "SELECT * FROM jira_attachments WHERE issue_id=? ORDER BY id", (record["id"],)
    ):
        artifact = db.artifact(row["path"])
        if artifact is None:
            raise s.BusinessError(f"Attachment bytes unavailable for {row['filename']}")
        rows.append((row, artifact))
    return rows


@s.handler()
def download_attachments(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    rows = attachment_rows(db, record)
    blocks: list[dict] = [
        {
            "type": "text",
            "text": f"Prepared {len(rows)} attachment(s) from {record['key']}.",
        }
    ]
    blocks.extend(
        {
            "type": "resource",
            "resource": {
                "uri": "attachment:///" + quote(row["filename"], safe=""),
                "mimeType": row["media_type"],
                "blob": base64.b64encode(artifact["content"]).decode(),
            },
        }
        for row, artifact in rows
    )
    return ServiceContent.model_validate({"content": blocks})


@s.handler()
def get_issue_images(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    rows = [
        (row, artifact)
        for row, artifact in attachment_rows(db, record)
        if row["media_type"].startswith("image/")
    ]
    blocks: list[dict] = [
        {
            "type": "text",
            "text": f"Found {len(rows)} image attachment(s) on {record['key']}.",
        }
    ]
    blocks.extend(
        {
            "type": "image",
            "data": base64.b64encode(artifact["content"]).decode(),
            "mimeType": row["media_type"],
        }
        for row, artifact in rows
    )
    return ServiceContent.model_validate({"content": blocks})


def status_visits(db, record, clock):
    now = datetime.fromisoformat(s.now(db, clock)).astimezone(UTC)
    rows = []
    for row in db.connection.execute(
        "SELECT * FROM jira_status_history WHERE issue_id=? ORDER BY id",
        (record["id"],),
    ):
        start = datetime.fromisoformat(row["entered"]).astimezone(UTC)
        end = (
            datetime.fromisoformat(row["exited"]).astimezone(UTC)
            if row["exited"]
            else now
        )
        rows.append(
            {
                "status": json.loads(row["status"]),
                "entered": start,
                "exited": end,
                "duration_seconds": max(0, int((end - start).total_seconds())),
            }
        )
    return rows


@s.handler()
def get_issue_dates(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    visits = status_visits(db, record, clock)
    result = {
        "issueKey": record["key"],
        "created": record["data"]["created"],
        "updated": record["data"]["updated"],
        "resolved": record["data"].get("resolutiondate"),
    }
    if args.get("include_status_changes", True):
        result["statusChanges"] = [
            {
                "status": visit["status"]["name"],
                "entered": visit["entered"].isoformat(),
                "exited": visit["exited"].isoformat(),
                "durationSeconds": visit["duration_seconds"],
            }
            for visit in visits
        ]
    if args.get("include_status_summary", True):
        summary = {}
        for visit in visits:
            summary[visit["status"]["name"]] = (
                summary.get(visit["status"]["name"], 0) + visit["duration_seconds"]
            )
        result["statusSummary"] = summary
    return result


def working_seconds(start, end, config):
    if end <= start:
        return 0
    open_hour, close_hour = config.get("open_hour", 9), config.get("close_hour", 17)
    if (
        type(open_hour) is not int
        or type(close_hour) is not int
        or not 0 <= open_hour < close_hour <= 24
    ):
        raise s.BusinessError("Invalid Jira SLA working hours")
    total, day = 0, start.date()
    while day <= end.date():
        if day.weekday() < 5:
            left = max(start, datetime.combine(day, time(open_hour), UTC))
            right = min(end, datetime.combine(day, time(close_hour), UTC))
            total += max(0, int((right - left).total_seconds()))
        day += timedelta(days=1)
    return total


@s.handler()
def get_issue_sla(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    visits = status_visits(db, record, clock)
    created = datetime.fromisoformat(record["data"]["created"]).astimezone(UTC)
    resolved = (
        datetime.fromisoformat(record["data"]["resolutiondate"]).astimezone(UTC)
        if record["data"].get("resolutiondate")
        else datetime.fromisoformat(s.now(db, clock)).astimezone(UTC)
    )
    configured = s.config(db).get("jira_sla", {})
    working_only = (
        args.get("working_hours_only")
        if args.get("working_hours_only") is not None
        else configured.get("working_hours_only", False)
    )
    if type(working_only) is not bool:
        raise s.BusinessError("working_hours_only must be boolean")
    duration = lambda start, end: (
        working_seconds(start, end, configured)
        if working_only
        else max(0, int((end - start).total_seconds()))
    )
    requested = [
        name.strip()
        for name in (args.get("metrics") or "cycle_time,time_in_status").split(",")
        if name.strip()
    ]
    supported = {
        "cycle_time",
        "lead_time",
        "time_in_status",
        "due_date_compliance",
        "resolution_time",
        "first_response_time",
    }
    if not requested or any(name not in supported for name in requested):
        raise s.BusinessError("Unsupported SLA metric")
    metrics = {}
    if "cycle_time" in requested:
        metrics["cycle_time"] = (
            duration(created, resolved)
            if record["data"].get("resolutiondate")
            else None
        )
    if "lead_time" in requested:
        metrics["lead_time"] = duration(created, resolved)
    if "time_in_status" in requested:
        totals = {}
        for visit in visits:
            name = visit["status"]["name"]
            totals[name] = totals.get(name, 0) + duration(
                visit["entered"], visit["exited"]
            )
        metrics["time_in_status"] = totals
    if "resolution_time" in requested:
        started = next(
            (
                visit["entered"]
                for visit in visits
                if visit["status"].get("category", {}).get("key") == "indeterminate"
            ),
            None,
        )
        metrics["resolution_time"] = (
            duration(started, resolved)
            if started and record["data"].get("resolutiondate")
            else None
        )
    if "first_response_time" in requested:
        metrics["first_response_time"] = (
            duration(created, visits[1]["entered"]) if len(visits) > 1 else None
        )
    if "due_date_compliance" in requested:
        due = record["data"].get("duedate")
        metrics["due_date_compliance"] = (
            None
            if not due
            else {
                "met": resolved.date() <= datetime.fromisoformat(due).date(),
                "dueDate": due,
            }
        )
    result = {
        "issueKey": record["key"],
        "workingHoursOnly": working_only,
        "metrics": metrics,
    }
    if args.get("include_raw_dates", False):
        result["rawDates"] = {
            "created": created.isoformat(),
            "resolvedOrNow": resolved.isoformat(),
        }
    return result


def development(db, record, application_type=None, data_type=None):
    return [
        {
            "applicationType": row["application_type"],
            "dataType": row["data_type"],
            "data": json.loads(row["data"]),
        }
        for row in db.connection.execute(
            "SELECT * FROM jira_development_records WHERE issue_id=? ORDER BY id",
            (record["id"],),
        )
        if (application_type is None or row["application_type"] == application_type)
        and (data_type is None or row["data_type"] == data_type)
    ]


@s.handler()
def get_issue_development_info(db, args, step, clock):
    record = s.issue(db, args.get("issue_key"))
    return {
        "issueKey": record["key"],
        "development": development(
            db, record, args.get("application_type"), args.get("data_type")
        ),
    }


@s.handler()
def get_issues_development_info(db, args, step, clock):
    keys = [
        key.strip()
        for key in s.text(args.get("issue_keys"), "issue_keys").split(",")
        if key.strip()
    ]
    if not keys or len(keys) > 100:
        raise s.BusinessError("Supply between 1 and 100 issue keys")
    return {
        key: development(
            db, s.issue(db, key), args.get("application_type"), args.get("data_type")
        )
        for key in keys
    }


@s.handler()
def get_project_epic_hierarchy(db, args, step, clock):
    from .jira_core import projection
    from .jira_workflow import is_epic

    project = s.project(db, args.get("project_key"))
    maximum = args.get("max_epics", 200)
    if type(maximum) is not int or not 1 <= maximum <= 500:
        raise s.BusinessError("max_epics must be between 1 and 500")
    records = []
    for row in db.connection.execute(
        "SELECT * FROM jira_issues WHERE project_id=? ORDER BY id", (project["id"],)
    ):
        record = dict(row) | {"data": json.loads(row["data"])}
        if is_epic(db, record):
            children = [
                s.issue(db, child["key"])
                for child in db.connection.execute(
                    "SELECT key FROM jira_issues WHERE parent_id=? ORDER BY id",
                    (record["id"],),
                )
            ]
            records.append(
                {
                    "epic": projection(db, record, "summary,status"),
                    "children": [
                        projection(db, child, "summary,status") for child in children
                    ],
                }
            )
    return {"projectKey": project["key"], "epics": records[:maximum]}


@s.handler()
def get_cross_project_dependencies(db, args, step, clock):
    project = s.project(db, args.get("project_key"))
    maximum = args.get("max_issues", 200)
    if type(maximum) is not int or not 1 <= maximum <= 500:
        raise s.BusinessError("max_issues must be between 1 and 500")
    dependencies = []
    rows = db.connection.execute(
        "SELECT l.*,a.key inward_key,b.key outward_key,a.project_id inward_project,b.project_id outward_project FROM jira_issue_links l JOIN jira_issues a ON a.id=l.inward_id JOIN jira_issues b ON b.id=l.outward_id WHERE a.project_id=? OR b.project_id=? ORDER BY l.id",
        (project["id"], project["id"]),
    )
    types = {
        row["id"]: json.loads(row["data"])
        for row in db.connection.execute("SELECT * FROM jira_link_types")
    }
    for row in rows:
        if row["inward_project"] != row["outward_project"]:
            dependencies.append(
                {
                    "id": str(row["id"]),
                    "type": types[row["type_id"]]["name"],
                    "inwardIssue": row["inward_key"],
                    "outwardIssue": row["outward_key"],
                }
            )
    return {"projectKey": project["key"], "dependencies": dependencies[:maximum]}


def validate_fixtures(world):
    issues = {issue["id"] for issue in world.jira_issues}
    artifacts = {
        artifact.path: artifact.media_type for artifact in world.initial_artifacts
    }
    paths = set()
    for item in world.jira_attachments:
        path = s.text(item.get("path"), "attachment path")
        if (
            item.get("issue_id") not in issues
            or path not in artifacts
            or path in paths
            or item.get("media_type") != artifacts.get(path)
        ):
            raise s.BusinessError("Invalid attachment fixture")
        s.text(item.get("filename"), "attachment filename")
        s.text(item.get("media_type"), "attachment media type")
        paths.add(path)
    for item in world.jira_development_records:
        if item.get("issue_id") not in issues:
            raise s.BusinessError("Invalid development fixture issue")
        s.text(item.get("application_type"), "application_type")
        s.text(item.get("data_type"), "data_type")
        s.obj(item.get("data"), "development data")


def seed(db, world):
    for item in world.jira_attachments:
        db.connection.execute(
            "INSERT INTO jira_attachments(issue_id,path,filename,media_type) VALUES (?,?,?,?)",
            (item["issue_id"], item["path"], item["filename"], item["media_type"]),
        )
    for item in world.jira_development_records:
        db.connection.execute(
            "INSERT INTO jira_development_records(issue_id,application_type,data_type,data) VALUES (?,?,?,?)",
            (
                item["issue_id"],
                item["application_type"],
                item["data_type"],
                json.dumps(item["data"]),
            ),
        )


HANDLERS = {
    "jira_batch_get_changelogs": batch_get_changelogs,
    "jira_update_issue": update_issue,
    "jira_download_attachments": download_attachments,
    "jira_get_issue_images": get_issue_images,
    "jira_get_issue_dates": get_issue_dates,
    "jira_get_issue_sla": get_issue_sla,
    "jira_get_issue_development_info": get_issue_development_info,
    "jira_get_issues_development_info": get_issues_development_info,
    "jira_get_project_epic_hierarchy": get_project_epic_hierarchy,
    "jira_get_cross_project_dependencies": get_cross_project_dependencies,
}
