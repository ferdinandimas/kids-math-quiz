#!/usr/bin/env python3
"""Rank draft KidQuest economy alternatives without approving production values."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.kidquest_economy.sensitivity import (
    DEFAULT_SENSITIVITY_PATH,
    build_sensitivity_report,
    load_sensitivity_spec,
    render_sensitivity_csv,
    render_sensitivity_json,
    render_sensitivity_markdown,
)
from tools.kidquest_economy.simulator import DEFAULT_PARAMETERS_PATH, ParameterError, load_parameters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", default=str(DEFAULT_PARAMETERS_PATH), help="draft baseline parameter JSON")
    parser.add_argument("--sensitivity", default=str(DEFAULT_SENSITIVITY_PATH), help="sensitivity specification JSON")
    parser.add_argument("--format", choices=("json", "markdown", "csv"), default="markdown")
    parser.add_argument("--top", type=int, help="number of ranked candidates to include")
    parser.add_argument("--output", help="optional output path; defaults to stdout")
    args = parser.parse_args(argv)

    try:
        report = build_sensitivity_report(
            load_parameters(args.parameters), load_sensitivity_spec(args.sensitivity), top=args.top
        )
    except (ParameterError, ValueError) as exc:
        print(f"Sensitivity configuration invalid: {exc}", file=sys.stderr)
        return 2

    renderers = {
        "json": render_sensitivity_json,
        "markdown": render_sensitivity_markdown,
        "csv": render_sensitivity_csv,
    }
    rendered = renderers[args.format](report)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Draft sensitivity report written: {output}", file=sys.stderr)
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())

