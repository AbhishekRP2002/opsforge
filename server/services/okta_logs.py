"""Read-only log projections from persisted fixture events and episode journal."""

import json
import re
from datetime import datetime, timedelta

from . import okta_store as store
from .okta_identity import _page
from .okta_templates import timestamp

LOGIN_TYPES = {
    "user.session.start",
    "user.authentication.auth_via_mfa",
    "user.authentication.sso",
    "user.authentication.auth_via_IDP",
    "user.authentication.auth_via_social",
    "user.authentication.auth_via_radius",
    "policy.evaluate_sign_on",
    "app.generic.unauth_app_access_attempt",
}
OUTCOMES = {"SUCCESS", "FAILURE", "DENY", "ALLOW", "CHALLENGE", "UNKNOWN"}


def _events(db):
    events = store.rows(db, "okta_log_events")
    for row in db.connection.execute(
        "SELECT * FROM journal WHERE provider='okta' ORDER BY sequence"
    ):
        events.append(
            {
                "uuid": f"journal-{row['sequence']}",
                "published": timestamp(row["clock"]),
                "eventType": f"opsforge.{row['kind']}",
                "actor": {"id": row["record_id"]},
                # Invocation journal entries precede validation/execution and do
                # not prove success; only completed identity records do.
                "outcome": {
                    "result": "UNKNOWN" if row["kind"] == "action" else "SUCCESS"
                },
                "displayMessage": f"Simulated Okta {row['kind']}",
            }
        )
    return sorted(
        events,
        key=lambda item: (item["published"], item.get("uuid", item.get("id", ""))),
    )


def _parse_time(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return result


def _select(db, arguments):
    try:
        since = _parse_time(arguments["since"]) if arguments.get("since") else None
        until = _parse_time(arguments["until"]) if arguments.get("until") else None
    except ValueError as exc:
        return None, f"Invalid timestamp: {exc}"
    if since and until and since > until:
        return None, "since must not be after until"
    conditions = []
    expression = arguments.get("filter") or ""
    for clause in expression.split(" and ") if expression else []:
        match = re.fullmatch(
            r"""(outcome\.result|actor\.id|eventType)\s+eq\s+["']([^"']+)["']""", clause
        )
        if not match:
            return (
                None,
                "Unsupported log filter; use equality on outcome.result, actor.id or eventType joined with and",
            )
        field, value = match.groups()
        if field == "outcome.result" and value.upper() not in OUTCOMES:
            return (
                None,
                "Invalid outcome.result; use SUCCESS, FAILURE, DENY, ALLOW, CHALLENGE or UNKNOWN",
            )
        if (
            field == "eventType"
            and re.search(
                r"mfa|factor|verify|challenge|step.?up|authentication",
                value,
                re.IGNORECASE,
            )
            and not re.search(
                r"""outcome\.result\s+eq\s+["']CHALLENGE["']""",
                expression,
                re.IGNORECASE,
            )
        ):
            return None, 'Incorrect MFA filter; use outcome.result eq "CHALLENGE"'
        conditions.append((field, value))
    items = []
    for item in _events(db):
        published = _parse_time(item["published"])
        if since and published < since or until and published > until:
            continue
        if (
            arguments.get("q")
            and arguments["q"].casefold() not in json.dumps(item).casefold()
        ):
            continue
        values = {
            "eventType": item["eventType"],
            "outcome.result": item["outcome"]["result"],
            "actor.id": item["actor"]["id"],
        }
        if all(values[key] == value for key, value in conditions):
            items.append(item)
    return items, None


def get_logs(db, arguments, step, clock):
    if denied := store.guard(db, "okta.logs.read", arguments):
        return denied
    items, invalid = _select(db, arguments)
    if invalid:
        return store.error(invalid)
    assert items is not None
    result, invalid = _page(
        items,
        kind="logs",
        query=(
            arguments.get("filter"),
            arguments.get("since"),
            arguments.get("until"),
            arguments.get("q"),
        ),
        after=arguments.get("after"),
        limit=arguments.get("limit"),
        fetch_all=arguments.get("fetch_all", False),
        minimum=20,
        maximum=100,
        max_pages=50,
        fetch_all_size=100,
    )
    if invalid:
        return store.error(invalid)
    assert result is not None
    expression = arguments.get("filter") or ""
    for outcome, other in (("FAILURE", "DENY"), ("DENY", "FAILURE")):
        if f'"{outcome}"' in expression and f'"{other}"' not in expression:
            result["reminder"] = (
                f"{outcome} results fetched. Also query {other}; authentication failures and policy denials are separate outcomes."
            )
    return result, False


def get_login_failures(db, arguments, step, clock):
    if denied := store.guard(db, "okta.logs.read", arguments):
        return denied
    until = arguments.get("until") or timestamp(clock)
    since = arguments.get("since") or (
        datetime.fromisoformat(timestamp(clock)) - timedelta(hours=24)
    ).isoformat().replace("+00:00", "Z")
    items, invalid = _select(db, arguments | {"since": since, "until": until})
    if invalid:
        return store.error(invalid)
    assert items is not None
    if arguments.get("user_id"):
        items = [item for item in items if item["actor"]["id"] == arguments["user_id"]]
    result: dict = {"time_window": {"since": since, "until": until}}
    parts = []
    warnings = []
    for outcome, key in (("FAILURE", "failures"), ("DENY", "denials")):
        matching = [item for item in items if item["outcome"]["result"] == outcome]
        selected = matching[:5000]
        stopped = len(matching) > 5000
        login = [item for item in selected if item["eventType"] in LOGIN_TYPES]
        other = [item for item in selected if item["eventType"] not in LOGIN_TYPES]
        result[key] = {
            "login_events": login,
            "other_events": other,
            "total": len(selected),
            "pagination": {
                "pages_fetched": max(1, (len(selected) + 99) // 100),
                "stopped_early": stopped,
                "total_fetched": len(selected),
            },
        }
        if selected:
            parts.append(
                f"{len(login)} login {outcome} event(s), {len(other)} other {outcome} event(s)"
            )
        if stopped:
            warnings.append(
                f"{outcome} query hit the page limit; narrow the time window."
            )
    result["summary"] = (
        "Found: " + "; ".join(parts) + "."
        if parts
        else "No login failures or policy denials found in this time window."
    )
    if warnings:
        result["warnings"] = warnings
    if arguments.get("user_id"):
        result["scoped_to_user"] = arguments["user_id"]
    return result, False


HANDLERS = {"get_logs": get_logs, "get_login_failures": get_login_failures}
