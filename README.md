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

Run `uv run pyright` for type checking, `uv run ruff check .` and `uv run ruff format --check .` for lint and formatting, `uv run pytest -q` for the local suite, and `uv run openenv validate . --verbose` for the OpenEnv packaging check. Dependencies and the generated package layout are defined in [pyproject.toml](pyproject.toml).

The editable install uses setuptools strict mode so Pyright and Pylance can resolve the mapped `itops_env` package. Select `.venv/bin/python` in your editor. After adding or renaming package files, run `uv sync --locked --extra dev --reinstall-package openenv-itops-env` to refresh the links under `build/__editable__.*`; keep that directory while using the environment.

To evaluate your own model callback, expose an importable `model_step(messages, tools, sampling)` function returning OpenEnv's `ModelStepResult`, then run:

```sh
uv run python -m itops_env.harness --model-step my_agent:model_step \
  --url http://127.0.0.1:8000 --episodes 5 --max-turns 10 --max-tool-calls 20
```

The [harness](harness/) uses OpenEnv's session, model-loop and collection interfaces. It writes verified `EpisodeRecord` JSONL under `.opsforge/rollouts` and exits nonzero if any episode fails. `ItopsSessionFactory` and `evaluate` also accept a model callback or custom OpenEnv agent adapter; see the [Python example](examples/evaluate.py). The environment's [trajectory rubric](server/rubrics.py) preserves the existing terminal reward. Model callbacks produce persistent normalized model/tool traces with IDs linking them to the environment trace; opaque external agents need their own model instrumentation.

Harness APIs are pinned to OpenEnv 0.4.2. Validation uses deterministic callbacks. Hosted model evaluation, training and broader ITAM/ITSM scenarios remain subsequent milestones.

Internal guides are maintained locally under `docs/internal`; designs and review evidence under `docs/superpowers`. These directories are excluded from this public repository by its ignore rules.
