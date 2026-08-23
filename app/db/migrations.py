"""Versioned, idempotent SQLite schema migrations."""

from collections.abc import Callable
import sqlite3


Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def _create_initial_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
          session_id TEXT PRIMARY KEY,
          child TEXT,
          day TEXT,
          served_count INTEGER NOT NULL DEFAULT 0,
          answered_count INTEGER NOT NULL DEFAULT 0,
          correct_count INTEGER NOT NULL DEFAULT 0,
          earned INTEGER NOT NULL DEFAULT 0,
          current_qid TEXT,
          created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS child_daily (
          child TEXT NOT NULL,
          day TEXT NOT NULL,
          served_count INTEGER NOT NULL DEFAULT 0,
          answered_count INTEGER NOT NULL DEFAULT 0,
          correct_count INTEGER NOT NULL DEFAULT 0,
          earned INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (child, day)
        )
        """
    )


def _add_answered_count(conn: sqlite3.Connection) -> None:
    for table in ("sessions", "child_daily"):
        if not _has_column(conn, table, "answered_count"):
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN answered_count INTEGER NOT NULL DEFAULT 0"
            )


MIGRATIONS: tuple[Migration, ...] = (
    (1, "create quiz session and daily statistics tables", _create_initial_schema),
    (2, "add answered counters to legacy tables", _add_answered_count),
)


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Apply every pending migration and return its version numbers."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          description TEXT NOT NULL,
          applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    pending = [migration for migration in MIGRATIONS if migration[0] not in applied]

    if not pending:
        return []

    with conn:
        for version, description, operation in pending:
            operation(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, description) VALUES (?, ?)",
                (version, description),
            )

    return [version for version, _, _ in pending]
