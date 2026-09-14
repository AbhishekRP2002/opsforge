"""Explicit source Kanban columns and transitions over shared documents."""

import json
import re
from datetime import date

from . import erpnext_store as store

COLUMNS = {
    "Task": [
        ("open", "Open", "#60a5fa"),
        ("working", "Working", "#f59e0b"),
        ("pending-review", "Pending Review", "#a78bfa"),
        ("overdue", "Overdue", "#ef4444"),
        ("completed", "Completed", "#22c55e"),
        ("cancelled", "Cancelled", "#78716c"),
    ],
    "Opportunity": [
        ("open", "Open", "#60a5fa"),
        ("replied", "Replied", "#f59e0b"),
        ("quotation", "Quotation", "#a78bfa"),
        ("converted", "Converted", "#22c55e"),
        ("closed", "Closed", "#64748b"),
        ("lost", "Lost", "#ef4444"),
    ],
    "Issue": [
        ("open", "Open", "#60a5fa"),
        ("replied", "Replied", "#f59e0b"),
        ("on-hold", "On Hold", "#a78bfa"),
        ("resolved", "Resolved", "#22c55e"),
        ("closed", "Closed", "#64748b"),
    ],
}
TRANSITIONS = {
    "Task": [
        ("open", "working", "Start work"),
        ("open", "pending-review", None),
        ("open", "completed", None),
        ("open", "cancelled", None),
        ("working", "open", None),
        ("working", "pending-review", "Request review"),
        ("working", "completed", None),
        ("working", "cancelled", None),
        ("pending-review", "working", "Resume work"),
        ("pending-review", "completed", "Approve"),
        ("pending-review", "open", None),
        ("pending-review", "cancelled", None),
        ("completed", "working", "Reopen"),
        ("completed", "open", None),
        ("cancelled", "open", "Reopen"),
    ],
    "Opportunity": [
        ("open", "replied", "Reply"),
        ("open", "quotation", "Send quotation"),
        ("open", "converted", "Convert"),
        ("open", "closed", "Close"),
        ("open", "lost", "Mark lost"),
        ("replied", "open", "Reopen"),
        ("replied", "quotation", "Send quotation"),
        ("replied", "converted", "Convert"),
        ("replied", "closed", "Close"),
        ("replied", "lost", "Mark lost"),
        ("quotation", "open", "Reopen"),
        ("quotation", "replied", "Resume conversation"),
        ("quotation", "converted", "Convert"),
        ("quotation", "closed", "Close"),
        ("quotation", "lost", "Mark lost"),
        ("converted", "open", "Reopen"),
        ("converted", "closed", "Close"),
        ("closed", "open", "Reopen"),
        ("closed", "replied", "Resume"),
        ("lost", "open", "Reopen"),
        ("lost", "replied", "Resume"),
    ],
    "Issue": [
        ("open", "replied", "Reply"),
        ("open", "on-hold", "Put on hold"),
        ("open", "resolved", "Resolve"),
        ("open", "closed", "Close"),
        ("replied", "open", "Reopen"),
        ("replied", "on-hold", "Put on hold"),
        ("replied", "resolved", "Resolve"),
        ("replied", "closed", "Close"),
        ("on-hold", "open", "Resume"),
        ("on-hold", "replied", "Reply"),
        ("on-hold", "resolved", "Resolve"),
        ("on-hold", "closed", "Close"),
        ("resolved", "open", "Reopen"),
        ("resolved", "replied", "Reply"),
        ("resolved", "closed", "Close"),
        ("closed", "open", "Reopen"),
        ("closed", "replied", "Reply"),
    ],
}


def column(kind, doc):
    return next(
        (
            key
            for key, status, _ in COLUMNS[kind]
            if status == doc.get("status", "Open")
        ),
        "open",
    )


def card(db, kind, doc, clock):
    col = column(kind, doc)
    badges, metrics = [], []
    result = {
        "id": doc["name"],
        "title": doc.get("subject", doc["name"]),
        "columnId": col,
        "accent": next(color for key, _, color in COLUMNS[kind] if key == col),
        "badges": badges,
        "metrics": metrics,
    }
    dates = []
    if kind == "Opportunity":
        result["title"] = doc.get("title") or doc.get("party_name") or doc["name"]
        result["subtitle"] = doc.get("party_name")
        if doc.get("opportunity_from"):
            badges.append({"label": doc["opportunity_from"], "tone": "neutral"})
        if doc.get("source"):
            badges.append({"label": doc["source"], "tone": "info"})
        if "opportunity_amount" in doc:
            metrics.append(
                {
                    "label": "Amount",
                    "value": f"{doc.get('currency') or 'Amount'} {doc['opportunity_amount']}",
                }
            )
        if "probability" in doc:
            metrics.append({"label": "Probability", "value": f"{doc['probability']}%"})
        result["assignee"] = doc.get("opportunity_owner")
        due = doc.get("expected_closing")
        dates = [("Closing", due), ("Created", doc.get("transaction_date"))]
        overdue_label, terminal = "Overdue", {"converted", "closed", "lost"}
    else:
        priority = doc.get("priority")
        if priority:
            badges.append(
                {
                    "label": priority,
                    "tone": "error"
                    if priority == "Urgent"
                    else "warning"
                    if priority == "High"
                    else "neutral",
                }
            )
        assignees = json.loads(doc.get("_assign", "[]"))
        result["assignee"] = assignees[0] if assignees else None
        if kind == "Task":
            result["subtitle"] = doc.get("project")
            if "progress" in doc:
                metrics.append({"label": "Progress", "value": f"{doc['progress']}%"})
            if doc.get("is_milestone") == 1:
                badges.append({"label": "Milestone", "tone": "info"})
            due = doc.get("exp_end_date")
            dates = [("Due", due), ("Start", doc.get("exp_start_date"))]
            for field, label in (("expected_time", "Est."), ("actual_time", "Actual")):
                if doc.get(field, 0) > 0:
                    metrics.append({"label": label, "value": f"{doc[field]}h"})
            if doc.get("description"):
                description = (
                    re.sub(r"<[^>]*>", "", doc["description"])
                    .replace("&nbsp;", " ")
                    .strip()
                )
                if description:
                    result["description"] = (
                        description[:80].rstrip() + "…"
                        if len(description) > 80
                        else description
                    )
            overdue_label, terminal = "Overdue", {"completed", "cancelled"}
        else:
            result["subtitle"] = doc.get("customer") or doc.get("raised_by")
            if doc.get("raised_by"):
                metrics.append({"label": "Raised By", "value": doc["raised_by"]})
            due = doc.get("resolution_by")
            dates = [
                ("SLA", due),
                ("Opened", doc.get("opening_date")),
                ("Resolved", doc.get("resolution_date")),
            ]
            overdue_label, terminal = "SLA breach", {"resolved", "closed"}
    if due:
        result["dueDate"] = due
        if due[:10] < store.now(db, clock)[:10] and col not in terminal:
            badges.append({"label": overdue_label, "tone": "error"})
    for label, value in dates:
        if value:
            day = date.fromisoformat(value[:10])
            metrics.append(
                {"label": label, "value": day.strftime("%b ") + str(day.day)}
            )
    return {key: value for key, value in result.items() if value is not None}


@store.handler
def get_board(db, args, step, clock):
    kind = args["doctype"]
    limit = store.limited(args.get("limit"), 50)
    offset = args.get("offset", 0)
    if type(offset) not in (int, float) or offset < 0 or int(offset) != offset:
        raise store.BusinessError("offset must be a non-negative integer")
    offset = int(offset)
    exact = {
        "Task": ("project", "priority"),
        "Opportunity": ("status", "opportunity_owner", "party_name"),
        "Issue": ("status", "priority", "customer", "raised_by"),
    }[kind]
    filters = [[field, "=", args[field]] for field in exact if args.get(field)]
    docs = store.select(db, kind, fields=["*"], filters=filters, limit=500)
    cards = [card(db, kind, doc, clock) for doc in docs[offset : offset + limit]]
    columns = [
        {
            "id": key,
            "label": label,
            "color": color,
            "count": sum(item["columnId"] == key for item in cards),
        }
        for key, label, color in COLUMNS[kind]
    ]
    transitions = [
        {
            "fromColumn": start,
            "toColumn": end,
            "allowed": True,
            **({"label": label} if label else {}),
        }
        for start, end, label in TRANSITIONS[kind]
    ]
    return {
        "boardId": kind.lower() + "-board",
        "title": kind + " Board",
        "doctype": kind,
        "generatedAt": store.now(db, clock),
        "moveToolName": "erpnext_kanban_move_card",
        "refreshArguments": args | {"doctype": kind, "limit": limit, "offset": offset},
        "columns": columns,
        "cards": cards,
        "allowedTransitions": transitions,
        "capabilities": {"canMoveCards": True},
        "pagination": {
            "limit": limit,
            "offset": offset,
            "loadedCount": offset + len(cards),
            "hasMore": len(docs) > offset + limit,
        },
    }


@store.handler
def move_card(db, args, step, clock):
    kind = args["doctype"]
    doc = store.get(db, kind, args["card_id"])
    current, destination = column(kind, doc), args["to_column"]
    result = {
        "ok": False,
        "cardId": args["card_id"],
        "fromColumn": current,
        "toColumn": destination,
    }
    if current != args["from_column"]:
        return result | {
            "errorMessage": f"{kind} moved on the server from {args['from_column']} to {current}. Refresh the board and try again."
        }
    if not any(
        start == current and end == destination for start, end, _ in TRANSITIONS[kind]
    ):
        return result | {
            "errorMessage": "Overdue is system-managed"
            if kind == "Task" and destination == "overdue"
            else f"{kind} transition is not allowed"
        }
    status = next(label for key, label, _ in COLUMNS[kind] if key == destination)
    updated = store.update(db, kind, doc["name"], {"status": status}, clock)
    return result | {"ok": True, "serverCard": card(db, kind, updated, clock)}


HANDLERS = {
    "erpnext_kanban_get_board": get_board,
    "erpnext_kanban_move_card": move_card,
}
