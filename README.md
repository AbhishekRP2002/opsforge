---
title: OpsForge IT Operations Environment
emoji: 📠
colorFrom: pink
colorTo: gray
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---

# OpsForge

An ITSM and ITAM reinforcement-learning environment being built on the generated OpenEnv scaffold.

The current implementation is the generator's echo example. It verifies packaging, server startup, typed client calls, and episode reset. Provider MCP servers, SQLite simulation, business scenarios, and terminal business grading are planned.

## Run locally

Use Python 3.11 and [uv](https://docs.astral.sh/uv/). From this repository root:

```sh
uv sync --locked --extra dev
uv run server
```

The server listens on port 8000 with one active OpenEnv session. To use a different port:

```sh
uv run python -m itops_env.server.app --port 8001
```

## Connect to the server

Run this from the project environment with the server running:

```python
import asyncio

from itops_env import ItopsAction, ItopsEnv


async def main():
    async with ItopsEnv(base_url="http://127.0.0.1:8000") as env:
        await env.reset()
        result = await env.step(ItopsAction(message="OpsForge"))
        print(result.observation.echoed_message)
        print(result.reward)
        print(await env.state())


asyncio.run(main())
```

For synchronous use, open the client with `ItopsEnv(base_url=...).sync()`.

The generated example returns the message and its length, awards `length × 0.1`, and never terminates automatically. This is the echo demonstration's behavior; the future ITSM/ITAM benchmark will require explicit submission and trusted outcome grading.

## Development checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run openenv validate . --verbose
uv build
```

The three tests exercise async and sync typed clients over WebSockets, reset, a fresh session after reconnecting, and OpenEnv's inherited async lifecycle methods. The WebSocket tests start a local server on an ephemeral port. OpenEnv's local validator checks packaging; it does not establish native MCP compatibility or provider fidelity.

OpenEnv is pinned to 0.4.2 in the project and lockfile. The CLI installed separately with `uv tool install` has its own environment.

## Docker

With Docker running:

```sh
docker build -t opsforge:scaffold -f server/Dockerfile .
docker run --rm -p 8000:8000 opsforge:scaffold
```

The Dockerfile retains OpenEnv's generated base-image workflow. Its default base uses the upstream `latest` tag; release reproducibility will require a pinned image digest. The build context excludes local environments, internal plans, credentials, and private evaluation/state files.

## Structure

```text
opsforge/
├── __init__.py
├── models.py
├── client.py
├── pyproject.toml
├── openenv.yaml
├── uv.lock
├── server/
│   ├── app.py
│   ├── itops_environment.py
│   ├── Dockerfile
│   └── requirements.txt
└── tests/
    └── test_scaffold.py
```

The generated setuptools mapping exposes this repository root as the Python module `itops_env`. Future episode, storage, provider service, and MCP modules will be added beneath `server/` as they are implemented. The public models and client stay in their generated locations.

Hugging Face publication, Verifiers and Harbor integration, and real-provider conformance are later milestones.
