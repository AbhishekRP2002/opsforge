"""Controller-private, append-only diagnostics outside disposable episode storage."""

import json
import math
import os
import re
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import uuid4

call_context: ContextVar[dict | None] = ContextVar(
    "opsforge_call_context", default=None
)
_SECRET_KEYS = {
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "accesstoken",
    "refreshtoken",
    "apikey",
    "clientsecret",
    "capability",
    "controllertoken",
}


def diagnostic(value):
    """Redact credential fields and represent invalid JSON values diagnostically."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if re.sub(r"[^a-z]", "", str(key).lower()) in _SECRET_KEYS
            else diagnostic(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [diagnostic(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return {"unsupported_type": type(value).__name__}


class TraceStore:
    def __init__(self, root: Path | None = None):
        self.root = (
            root
            if root is not None
            else Path(os.getenv("OPSFORGE_TRACE_DIR", ".opsforge/traces"))
        ).resolve()
        self.transport_id = uuid4().hex
        self._lock = RLock()

    def path(self, trace_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{32}", trace_id):
            raise ValueError("Invalid trace ID")
        return self.root / f"{trace_id}.jsonl"

    def emit(self, trace_id: str, event: str, **fields) -> None:
        record = diagnostic(
            {
                "version": 1,
                "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "provenance": "[TOOL]"
                if event.startswith(("tool.", "mcp."))
                else "[CODE]",
                "trace_id": trace_id,
                "event": event,
                **fields,
            }
        )
        line = json.dumps(record, ensure_ascii=True, allow_nan=False) + "\n"
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            descriptor = os.open(
                self.path(trace_id), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())

    def read(self, trace_id: str) -> bytes:
        with self._lock:
            return self.path(trace_id).read_bytes()


def record_failure(emit, event: str, error: BaseException, **fields) -> None:
    """Keep the original failure if writing its diagnostic also fails."""
    try:
        emit(
            event, error={"type": type(error).__name__, "message": str(error)}, **fields
        )
    except OSError as trace_error:
        error.add_note(f"Diagnostic trace could not be persisted: {trace_error}")
