"""Source-derived Okta lookup profile, backed by episode records."""

import re

from ..storage.database import Database


def get_user(db: Database, arguments: dict, step: int, clock: int) -> tuple[list, bool]:
    identifier = arguments["user_id"]
    if (
        not identifier
        or ".." in identifier
        or not re.fullmatch(r"[a-zA-Z0-9_\-@.+]+", identifier)
    ):
        return [
            {
                "error": "Invalid user_id: expected an Okta ID or login without traversal or URL-reserved characters"
            }
        ], True
    row = db.connection.execute(
        "SELECT * FROM okta_users WHERE id = ? OR login = ? ORDER BY CASE WHEN id = ? THEN 0 ELSE 1 END LIMIT 1",
        (identifier, identifier, identifier),
    ).fetchone()
    if row is None:
        return [{"error": "User not found"}], True
    db.record(step, clock, "read", "okta", row["id"])
    return [
        {
            "id": row["id"],
            "status": row["status"],
            "profile": {
                "login": row["login"],
                "email": row["email"],
                "firstName": row["first_name"],
                "lastName": row["last_name"],
            },
        }
    ], False
