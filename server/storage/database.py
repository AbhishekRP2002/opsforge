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
            with db.connection:
                for row in scenario.okta_users:
                    db.connection.execute(
                        "INSERT INTO okta_users VALUES (?, ?, ?, ?, ?, ?)",
                        tuple(row.model_dump().values()),
                    )
                for row in scenario.servicenow_users:
                    db.connection.execute(
                        "INSERT INTO servicenow_users VALUES (?, ?, ?, ?, ?)",
                        tuple(row.model_dump().values()),
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

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._temp is not None:
            self._temp.cleanup()
            self._temp = None
