"""Evaluate one episode: uv run python examples/evaluate.py my_agent:model_step."""

import argparse
import json

from itops_env.harness import ItopsSessionFactory, evaluate
from itops_env.harness.__main__ import load_model_step
from openenv.core.harness import HarnessRunLimits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_step", help="Importable module:function")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    record = evaluate(
        ItopsSessionFactory(args.url),
        model_step=load_model_step(args.model_step),
        limits=HarnessRunLimits(max_turns=10, max_total_tool_calls=20),
    )
    print(json.dumps(record.to_dict(), indent=2))


if __name__ == "__main__":
    main()
