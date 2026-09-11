---
title: OpsForge IT Operations Environment
emoji: 📠
colorFrom: pink
colorTo: gray
sdk: docker
pinned: false
app_port: 8000
base_path: /health
tags:
  - openenv
---

# OpsForge

An ITSM and ITAM reinforcement-learning environment built on OpenEnv. This checkpoint implements one public identity-to-group simulation with Okta and ServiceNow tools, deterministic grading and persistent environment traces.

With Python 3.11 and [uv](https://docs.astral.sh/uv/), start the server:

```sh
uv sync --locked --extra dev
export OPSFORGE_CONTROLLER_TOKEN="$(openssl rand -hex 32)"
uv run server
```

In another terminal, set the same controller token and run the scripted workflow:

```sh
uv run python -m itops_env.runner replay --url http://127.0.0.1:8000
```

Use `connect` instead of `replay` to keep an episode open for an external MCP agent. Give the agent the printed MCP configuration, which contains a separate episode capability. Keep the controller token and final grading report with the controller. See the [runner](runner.py) and [typed MCP tools](server/mcp_servers/) for the implemented interface.

Traces persist in `.opsforge/traces`, configurable with `OPSFORGE_TRACE_DIR`. The controller can retrieve them through `/control/trace/{trace_id}` using the IDs in the runner report. Container retention requires mounting the trace directory.

Run `uv run pytest -q` for the local suite and `uv run openenv validate . --verbose` for the OpenEnv packaging check. Dependencies and the generated package layout are defined in [pyproject.toml](pyproject.toml).

Rubric integration, a model-driving harness, model-output tracing and broader ITAM/ITSM scenarios are subsequent milestones. The current runner executes a scripted policy or maintains ownership for an external agent.

Internal guides are maintained locally under `docs/internal`; designs and review evidence under `docs/superpowers`. These directories are excluded from this public repository by its ignore rules.
