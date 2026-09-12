"""Collect verified episodes with a user-provided module:function model step."""

import argparse
import json
from dataclasses import asdict
from importlib import import_module
from pathlib import Path
from typing import cast
from uuid import uuid4

from openenv.core.harness import HarnessRunLimits, ModelStep
from openenv.core.harness.collect import CollectRunner, RolloutSerializer

from .runtime import ItopsMCPHarnessAdapter
from .session import ItopsSessionFactory


def load_model_step(reference: str) -> ModelStep:
    module, separator, name = reference.partition(":")
    if not separator or not module or not name:
        raise ValueError("--model-step must be module:function")
    callback = getattr(import_module(module), name)
    if not callable(callback):
        raise TypeError(f"{reference} is not callable")
    # The dynamic import is checked for callability above; the user supplies the
    # ModelStep signature documented by this plugin boundary.
    return cast(ModelStep, callback)


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-step",
        required=True,
        help="Importable module:function returning OpenEnv ModelStepResult",
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--episodes", type=positive_int, default=1)
    parser.add_argument("--max-turns", type=positive_int, default=10)
    parser.add_argument("--max-tool-calls", type=positive_int)
    parser.add_argument(
        "--output-dir", type=Path, default=Path(".opsforge/rollouts") / uuid4().hex
    )
    args = parser.parse_args()
    model_step = load_model_step(args.model_step)
    factory = ItopsSessionFactory(args.url)
    # Claim a new directory before contacting the server. Never silently mix runs.
    try:
        args.output_dir.mkdir(parents=True, mode=0o700)
    except FileExistsError as error:
        raise FileExistsError(
            f"Output directory already exists: {args.output_dir}; choose a new directory"
        ) from error
    serializer = RolloutSerializer(args.output_dir)
    limits = HarnessRunLimits(
        max_turns=args.max_turns, max_total_tool_calls=args.max_tool_calls
    )
    serializer.write_metadata(
        {
            "model_step": args.model_step,
            "task": "identity-group-v1",
            "limits": asdict(limits),
            "num_episodes": args.episodes,
            "openenv_version": "0.4.2",
        }
    )
    runner = CollectRunner(
        session_factory=factory,
        harness_adapter=ItopsMCPHarnessAdapter(),
        serializer=serializer,
        limits=limits,
    )
    result = runner.run(
        model_step=model_step,
        num_episodes=args.episodes,
        episode_id_prefix="opsforge",
        resume=False,
    )
    print(json.dumps(asdict(result) | {"output_dir": str(args.output_dir)}))
    return 1 if result.num_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
