"""Issue-owned ProForma form fixtures and answer updates."""

import json
from datetime import date, datetime

from . import jira_store as s


def form(db, issue, identifier):
    form_id = s.text(identifier, "form_id")
    row = db.connection.execute(
        "SELECT data FROM jira_forms WHERE issue_id=? AND id=?", (issue["id"], form_id)
    ).fetchone()
    if row is None:
        raise s.BusinessError(f"Form {form_id} not found on {issue['key']}")
    return {"id": form_id, **json.loads(row[0])}


def summary(record):
    return {key: record[key] for key in ("id", "name", "status") if key in record}


@s.handler()
def get_issue_proforma_forms(db, args, step, clock):
    issue = s.issue(db, args.get("issue_key"))
    return [
        summary({"id": row["id"], **json.loads(row["data"])})
        for row in db.connection.execute(
            "SELECT * FROM jira_forms WHERE issue_id=? ORDER BY id", (issue["id"],)
        )
    ]


@s.handler()
def get_proforma_form_details(db, args, step, clock):
    issue = s.issue(db, args.get("issue_key"))
    return form(db, issue, args.get("form_id"))


def normalized_answer(answer, questions):
    answer = s.obj(answer, "answer")
    question_id = s.text(answer.get("questionId"), "questionId")
    if question_id not in questions:
        raise s.BusinessError(f"Unknown form question {question_id}")
    kind = s.text(answer.get("type"), "answer type").upper()
    if kind != str(questions[question_id].get("type", kind)).upper():
        raise s.BusinessError(f"Answer type does not match question {question_id}")
    value = answer.get("value")
    if kind == "NUMBER" and (
        isinstance(value, bool) or not isinstance(value, (int, float))
    ):
        raise s.BusinessError("NUMBER answer requires a number")
    if kind in ("TEXT", "SELECT") and not isinstance(value, str):
        raise s.BusinessError(f"{kind} answer requires text")
    if kind in ("DATE", "DATETIME"):
        try:
            value = (
                date.fromisoformat(s.text(value, "date answer")).isoformat()
                if kind == "DATE"
                else datetime.fromisoformat(
                    s.text(value, "datetime answer")
                ).isoformat()
            )
        except ValueError as error:
            raise s.BusinessError(f"Invalid {kind} answer") from error
    return {"questionId": question_id, "type": kind, "value": value}


@s.handler(write=True)
def update_proforma_form_answers(db, args, step, clock):
    issue = s.issue(db, args.get("issue_key"))
    record = form(db, issue, args.get("form_id"))
    questions = {
        s.text(item.get("id"), "question id"): item
        for item in s.array(
            record.get("design", {}).get("questions", []), "form questions"
        )
    }
    supplied = s.array(args.get("answers"), "answers")
    normalized = [normalized_answer(answer, questions) for answer in supplied]
    merged = {answer["questionId"]: answer for answer in record.get("answers", [])}
    merged.update({answer["questionId"]: answer for answer in normalized})
    record["answers"] = list(merged.values())
    db.connection.execute(
        "UPDATE jira_forms SET data=? WHERE issue_id=? AND id=?",
        (
            json.dumps({key: value for key, value in record.items() if key != "id"}),
            issue["id"],
            record["id"],
        ),
    )
    return {"success": True, "issueKey": issue["key"], "form": record}


def validate_fixtures(world):
    issues = {issue["id"] for issue in world.jira_issues}
    seen = set()
    for item in world.jira_forms:
        key = (item.get("issue_id"), s.text(item.get("id"), "form id"))
        if key in seen or key[0] not in issues:
            raise s.BusinessError("Invalid form fixture")
        questions = set()
        for question in s.array(
            s.obj(item.get("design", {}), "form design").get("questions", []),
            "form questions",
        ):
            identity = s.text(s.obj(question, "question").get("id"), "question id")
            if identity in questions:
                raise s.BusinessError("Duplicate form question")
            s.text(question.get("type"), "question type")
            questions.add(identity)
        seen.add(key)


def seed(db, world):
    for item in world.jira_forms:
        data = {
            key: value for key, value in item.items() if key not in ("id", "issue_id")
        }
        db.connection.execute(
            "INSERT INTO jira_forms VALUES (?,?,?)",
            (item["id"], item["issue_id"], json.dumps(data)),
        )


HANDLERS = {
    "jira_get_issue_proforma_forms": get_issue_proforma_forms,
    "jira_get_proforma_form_details": get_proforma_form_details,
    "jira_update_proforma_form_answers": update_proforma_form_answers,
}
