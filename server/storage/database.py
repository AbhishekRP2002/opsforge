"""One owned private SQLite database per episode."""

import json
import sqlite3
import tempfile
from importlib.resources import files
from pathlib import Path

from ..core.scenarios import Scenario


class Database:
    def __init__(self) -> None:
        self._temp: tempfile.TemporaryDirectory[str] | None = None
        self._connection: sqlite3.Connection | None = None
        self._directory: Path | None = None

    @property
    def is_open(self) -> bool:
        return self._connection is not None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not open")
        return self._connection

    @property
    def directory(self) -> Path:
        if self._directory is None:
            raise RuntimeError("Database has not been allocated")
        return self._directory

    @classmethod
    def create(cls, scenario: Scenario, episode_id: str, seed: int) -> "Database":
        db = cls()
        db._temp = tempfile.TemporaryDirectory(prefix="opsforge-episode-")
        db._directory = Path(db._temp.name)
        try:
            db._connection = sqlite3.connect(
                db.directory / "episode.sqlite3", check_same_thread=False
            )
            db.connection.row_factory = sqlite3.Row
            db.connection.execute("PRAGMA foreign_keys = ON")
            db.connection.executescript(
                files("itops_env.server.storage")
                .joinpath("migrations", "001_initial.sql")
                .read_text()
            )
            db.connection.executescript(
                files("itops_env.server.storage")
                .joinpath("migrations", "002_okta_identity.sql")
                .read_text()
            )
            with db.connection:
                db.connection.executescript(
                    files("itops_env.server.storage")
                    .joinpath("migrations", "007_jira.sql")
                    .read_text()
                )
                from ..services.jira_store import seed as seed_jira

                seed_jira(db, scenario)
                db.connection.executescript(
                    files("itops_env.server.storage")
                    .joinpath("migrations", "006_darwinbox.sql")
                    .read_text()
                )
                db.connection.executescript(
                    files("itops_env.server.storage")
                    .joinpath("migrations", "005_erpnext.sql")
                    .read_text()
                )
                db.connection.executescript(
                    files("itops_env.server.storage")
                    .joinpath("migrations", "004_servicenow.sql")
                    .read_text()
                )
                db.connection.executescript(
                    files("itops_env.server.storage")
                    .joinpath("migrations", "003_okta_extended.sql")
                    .read_text()
                )
                for app in scenario.okta_applications:
                    db.connection.execute(
                        "INSERT INTO okta_applications VALUES (?, ?)",
                        (app["id"], json.dumps(app)),
                    )
                for event in scenario.okta_log_events:
                    db.connection.execute(
                        "INSERT INTO okta_log_events VALUES (?, ?)",
                        (event["id"], json.dumps(event)),
                    )
                for artifact in scenario.initial_artifacts:
                    db.connection.execute(
                        "INSERT INTO episode_artifacts VALUES (?,?,?,0,0)",
                        (artifact.path, artifact.content.encode(), artifact.media_type),
                    )
                for row in scenario.okta_users:
                    db.connection.execute(
                        "INSERT INTO okta_users VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            row.id,
                            row.login,
                            row.email,
                            row.first_name,
                            row.last_name,
                            row.status,
                            json.dumps(row.profile),
                        ),
                    )
                for row in scenario.okta_groups:
                    db.connection.execute(
                        "INSERT INTO okta_groups VALUES (?, ?)",
                        (row.id, json.dumps(row.profile)),
                    )
                for row in scenario.okta_memberships:
                    db.connection.execute(
                        "INSERT INTO okta_group_memberships VALUES (?, ?)",
                        (row.group_id, row.user_id),
                    )
                for row in scenario.okta_group_apps:
                    db.connection.execute(
                        "INSERT OR IGNORE INTO okta_applications VALUES (?, ?)",
                        (row.app_id, json.dumps(row.app)),
                    )
                    db.connection.execute(
                        "INSERT INTO okta_group_apps VALUES (?, ?, ?)",
                        (row.group_id, row.app_id, json.dumps(row.app)),
                    )
                db.connection.executemany(
                    "INSERT INTO okta_scopes VALUES (?)",
                    [(scope,) for scope in scenario.okta_scopes],
                )
                for row in scenario.servicenow_users:
                    db.connection.execute(
                        "INSERT INTO servicenow_users VALUES (?, ?, ?, ?, ?)",
                        (row.sys_id, row.user_name, row.email, row.name, row.active),
                    )
                    if row.profile:
                        db.connection.execute(
                            "INSERT INTO servicenow_profiles VALUES ('sys_user',?,?)",
                            (row.sys_id, json.dumps(row.profile)),
                        )
                for record in scenario.darwinbox_records:
                    from ..services.darwinbox_seed import business_key

                    db.connection.execute(
                        "INSERT INTO darwinbox_records VALUES (?,?,?)",
                        (
                            record.kind,
                            business_key(record.kind, record.id, record.data),
                            json.dumps(record.data, allow_nan=False),
                        ),
                    )
                for record in scenario.erpnext_records:
                    db.connection.execute(
                        "INSERT INTO erpnext_ids(doctype,name) VALUES (?,?)",
                        (record.doctype, record.name),
                    )
                    document = record.data | {
                        "doctype": record.doctype,
                        "name": record.name,
                        "docstatus": record.docstatus,
                        "creation": scenario.erpnext_epoch,
                        "modified": scenario.erpnext_epoch,
                    }
                    db.connection.execute(
                        "INSERT INTO erpnext_documents VALUES (?,?,?)",
                        (
                            record.doctype,
                            record.name,
                            json.dumps(document, allow_nan=False),
                        ),
                    )
                for row in scenario.servicenow_records:
                    db.connection.execute(
                        "INSERT INTO servicenow_allocated_ids VALUES (?,?)",
                        (row.table, row.sys_id),
                    )
                    db.connection.execute(
                        "INSERT INTO servicenow_records VALUES (?,?,?)",
                        (
                            row.table,
                            row.sys_id,
                            json.dumps(row.data | {"sys_id": row.sys_id}),
                        ),
                    )
                for row in scenario.servicenow_groups:
                    db.connection.execute(
                        "INSERT INTO servicenow_groups VALUES (?, ?, ?)",
                        tuple(row.model_dump().values()),
                    )
                for row in scenario.events:
                    db.connection.execute(
                        "INSERT INTO events (at, sequence, kind, group_id) VALUES (?, ?, ?, ?)",
                        tuple(row.model_dump().values()),
                    )
                for key, value in {
                    "episode_id": episode_id,
                    "seed": seed,
                    "scenario": scenario.model_dump(),
                    "clock": 0,
                    "step_count": 0,
                    "phase": "active",
                }.items():
                    db.connection.execute(
                        "INSERT INTO metadata VALUES (?, ?)", (key, json.dumps(value))
                    )
            return db
        except BaseException:
            db.close()
            raise

    def record(
        self,
        step: int,
        clock: int,
        kind: str,
        provider: str,
        record_id: str,
        group_id: str | None = None,
    ):
        self.connection.execute(
            "INSERT INTO journal (step, clock, kind, provider, record_id, group_id) VALUES (?, ?, ?, ?, ?, ?)",
            (step, clock, kind, provider, record_id, group_id),
        )

    def snapshot(self, destination: Path) -> None:
        with sqlite3.connect(destination) as backup:
            self.connection.backup(backup)

    def artifact(self, path: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM episode_artifacts WHERE path = ?", (path,)
        ).fetchone()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None
