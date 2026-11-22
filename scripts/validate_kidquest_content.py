#!/usr/bin/env python3
"""Validate the KidQuest content catalog and print its counts.

Usage (from the repository root, or /app in the container):
    PYTHONPATH=. python scripts/validate_kidquest_content.py [--content-dir PATH]

Checks logical content only (IDs, references, geometry, zones, masks, theme parity on logical
asset IDs). It does not look for image files; that is the asset validator's job (KQ-006).
"""

import argparse
import sys
from pathlib import Path

from app.domain.kidquest.content import CONTENT_DIR, ContentError, load_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--content-dir", default=str(CONTENT_DIR), help="content directory (default: content/kidquest)")
    args = parser.parse_args(argv)

    try:
        catalog = load_catalog(Path(args.content_dir))
    except ContentError as exc:
        print(f"KidQuest content INVALID ({len(exc.problems)} problem(s)):", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"KidQuest content OK: {args.content_dir}")
    for name, count in catalog.counts().items():
        print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
