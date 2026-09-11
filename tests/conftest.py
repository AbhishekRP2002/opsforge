"""Keep persistent diagnostic artifacts isolated between tests."""

import pytest


@pytest.fixture(autouse=True)
def trace_directory(tmp_path, monkeypatch):
    directory = tmp_path / "traces"
    monkeypatch.setenv("OPSFORGE_TRACE_DIR", str(directory))
    return directory
