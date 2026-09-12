"""Invoke the installed module CLI against a real simulation server."""

import json
import os
import subprocess
import sys
from pathlib import Path

from test_mcp_episode import TOKEN
from test_mcp_episode import live_server as server_fixture

live_server = server_fixture


def failed_step(messages, tools, sampling):
    raise RuntimeError("provider fixture unavailable")


def invoke(url, output, callback="test_harness_runtime:scripted_step", *extra):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "itops_env.harness",
            "--url",
            url,
            "--model-step",
            callback,
            "--output-dir",
            str(output),
            *extra,
        ],
        env=os.environ
        | {
            "OPSFORGE_CONTROLLER_TOKEN": TOKEN,
            "PYTHONPATH": str(Path(__file__).parent),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_cli_collects_and_refuses_to_mix_existing_results(live_server, tmp_path):
    url, app = live_server
    output = tmp_path / "rollouts"
    result = invoke(
        url, output, "test_harness_runtime:scripted_step", "--episodes", "2"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout.splitlines()[-1])
    assert summary["num_collected"] == 2 and summary["num_failed"] == 0
    records = (output / "results.jsonl").read_bytes()
    assert [json.loads(line)["reward"] for line in records.splitlines()] == [1, 1]
    assert (
        json.loads((output / "metadata.json").read_text())["model_step"]
        == "test_harness_runtime:scripted_step"
    )
    again = invoke(url, output)
    assert again.returncode != 0 and "already exists" in again.stderr
    assert (output / "results.jsonl").read_bytes() == records
    assert app.state.binding.env is None


def test_cli_reports_failed_collection_as_nonzero_exit(live_server, tmp_path):
    url, app = live_server
    output = tmp_path / "failures"
    result = invoke(url, output, "test_harness_cli:failed_step")
    assert result.returncode == 1, result.stdout + result.stderr
    summary = json.loads(result.stdout.splitlines()[-1])
    assert summary["num_failed"] == 1 and summary["num_collected"] == 0
    assert "provider fixture unavailable" in result.stdout
    assert not (output / "results.jsonl").exists()
    assert app.state.binding.env is None
