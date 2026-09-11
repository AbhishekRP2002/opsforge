"""Events apply at action completion in explicit (time, sequence) order."""

from ..storage.database import Database


def advance(db: Database, clock: int):
    events = db.connection.execute(
        "SELECT * FROM events WHERE applied = 0 AND at <= ? ORDER BY at, sequence",
        (clock,),
    ).fetchall()
    for event in events:
        db.connection.execute(
            "UPDATE servicenow_groups SET available = ? WHERE sys_id = ?",
            (event["kind"] == "group_available", event["group_id"]),
        )
        db.connection.execute(
            "UPDATE events SET applied = 1 WHERE sequence = ?", (event["sequence"],)
        )
