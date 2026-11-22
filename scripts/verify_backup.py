#!/usr/bin/env python3
"""Verify a SQLite backup: integrity, schema version, and a test restore.

Usage (from the repository root, or /app in the container):
    PYTHONPATH=. python scripts/verify_backup.py BACKUP [--restore-to PATH] [--compare-with DB]

Without --restore-to, the backup is restored into a temporary directory that is removed
afterwards. --restore-to keeps the restored copy and refuses to overwrite an existing file.
--compare-with checks that the backup matches another database exactly (schema and rows).
"""

import argparse
import sys
import tempfile
from pathlib import Path

from app.db.backup import BackupError, copy_database, database_digest, describe, integrity_problems


def fail(message: str) -> int:
    print(f"Verification FAILED: {message}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("backup", help="backup file to verify")
    parser.add_argument("--restore-to", help="keep the restored copy at this new path")
    parser.add_argument("--compare-with", help="database that the backup must match exactly")
    args = parser.parse_args(argv)
    backup = Path(args.backup)

    if not backup.is_file():
        return fail(f"backup not found: {backup}")
    problems = integrity_problems(backup)
    if problems:
        return fail("; ".join(problems))
    info = describe(backup)
    if info["schema_version"] is None:
        return fail("no schema_migrations table; this is not an application database")
    backup_digest = database_digest(backup)

    with tempfile.TemporaryDirectory(prefix="kids-quiz-restore-") as scratch:
        target = Path(args.restore_to) if args.restore_to else Path(scratch) / "restored.sqlite3"
        try:
            copy_database(backup, target)
        except BackupError as exc:
            return fail(str(exc))
        restored_problems = integrity_problems(target)
        if restored_problems:
            return fail("restored copy: " + "; ".join(restored_problems))
        if database_digest(target) != backup_digest:
            return fail("restored copy differs from the backup")

    if args.compare_with and database_digest(Path(args.compare_with)) != backup_digest:
        return fail(f"backup differs from {args.compare_with}")

    print(f"Backup verified: {backup}")
    print("integrity_check: ok")
    print(f"schema version: {info['schema_version']}")
    print("rows: " + ", ".join(f"{table}={count}" for table, count in info["tables"].items()))
    print(f"restore test: ok ({args.restore_to or 'temporary copy removed'})")
    if args.compare_with:
        print(f"matches: {args.compare_with}")
    print(f"digest: {backup_digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
