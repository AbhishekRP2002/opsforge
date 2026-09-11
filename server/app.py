# SPDX-License-Identifier: BSD-3-Clause

"""
FastAPI application for the Itops Env Environment.

This module creates an HTTP server that exposes the ItopsEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uv run uvicorn itops_env.server.app:app --reload --host 127.0.0.1 --port 8000

    # Production:
    uv run server

    # Or run directly:
    uv run python -m itops_env.server.app
"""

from itops_env.models import ItopsAction, ItopsObservation
from itops_env.server.itops_environment import ItopsEnvironment
from openenv.core.env_server.http_server import create_app

# Create the app with web interface and README integration
app = create_app(
    ItopsEnvironment,
    ItopsAction,
    ItopsObservation,
    env_name="itops_env",
    max_concurrent_envs=1,  # increase this number to allow more concurrent WebSocket sessions
)


def main(host: str = "0.0.0.0", port: int = 8000):
    """
    Entry point for direct execution via uv run or python -m.

    This function enables running the server without Docker:
        uv run --project . server
        uv run python -m itops_env.server.app --port 8001

    Args:
        host: Host address to bind to (default: "0.0.0.0")
        port: Port number to listen on (default: 8000)

    Run one worker so the process owns one active episode.
    """
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    main(port=args.port)
