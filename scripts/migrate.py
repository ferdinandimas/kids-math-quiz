#!/usr/bin/env python3
"""Apply all pending SQLite migrations for the configured database."""

from app.db.migrations import migrate
from app.db.sqlite import db_conn


def main() -> None:
    conn = db_conn()
    try:
        applied = migrate(conn)
    finally:
        conn.close()

    if applied:
        print(f"Applied SQLite migrations: {', '.join(map(str, applied))}")
    else:
        print("SQLite schema is up to date.")


if __name__ == "__main__":
    main()
