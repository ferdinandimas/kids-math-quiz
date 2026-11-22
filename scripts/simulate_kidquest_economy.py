#!/usr/bin/env python3
"""Run the isolated KidQuest economy simulator with draft, non-production parameters.

Usage from the repository root:
    PYTHONPATH=. python scripts/simulate_kidquest_economy.py --format markdown
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.kidquest_economy.simulator import (
    DEFAULT_PARAMETERS_PATH,
    ParameterError,
    build_report,
    load_parameters,
    render_json,
    render_markdown,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--parameters", default=str(DEFAULT_PARAMETERS_PATH), help="draft parameter JSON")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", help="optional output path; defaults to stdout")
    args = parser.parse_args(argv)

    try:
        parameters = load_parameters(args.parameters)
        report = build_report(parameters)
    except (ParameterError, ValueError) as exc:
        print(f"Simulation configuration invalid: {exc}", file=sys.stderr)
        return 2

    rendered = render_json(report) if args.format == "json" else render_markdown(report)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Draft simulation report written: {output}", file=sys.stderr)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())

