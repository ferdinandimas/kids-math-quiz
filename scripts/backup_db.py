#!/usr/bin/env python3
"""Back up the SQLite database with the online backup API, then check the copy.

Usage (from the repository root, or /app in the container):
    PYTHONPATH=. python scripts/backup_db.py [--source PATH] [--output PATH]

The source defaults to DB_PATH. The output defaults to
<db dir>/backups/<db name>-YYYYMMDD-HHMMSS.sqlite3. Existing files are never overwritten,
and backups are never deleted automatically (see docs/Database_Operations.md).
"""

import argparse
import sys
from pathlib import Path

from app import clock
from app.config import get_db_path
from app.db.backup import BackupError, copy_database, default_backup_path, describe, integrity_problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", help="database to back up (default: DB_PATH)")
    parser.add_argument("--output", help="backup file to create (default: timestamped file in <db dir>/backups)")
    args = parser.parse_args(argv)

    source = Path(args.source or get_db_path())
    output = Path(args.output) if args.output else default_backup_path(source, clock.now())
    try:
        copy_database(source, output)
    except BackupError as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1

    problems = integrity_problems(output)
    if problems:
        print(f"Backup written to {output} but FAILED integrity checks:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    info = describe(output)
    print(f"Backup written: {output}")
    print("integrity_check: ok")
    print(f"schema version: {info['schema_version']}")
    print("rows: " + ", ".join(f"{table}={count}" for table, count in info["tables"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
