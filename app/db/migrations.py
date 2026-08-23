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


def _create_served_questions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS served_questions (
          child TEXT NOT NULL,
          day TEXT NOT NULL,
          quiz_type TEXT NOT NULL,
          question_id TEXT NOT NULL,
          served_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (child, day, quiz_type, question_id)
        )
        """
    )


def _add_current_quiz_type(conn: sqlite3.Connection) -> None:
    if not _has_column(conn, "sessions", "current_quiz_type"):
        conn.execute("ALTER TABLE sessions ADD COLUMN current_quiz_type TEXT")


def _create_daily_question_banks(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_question_banks (
          child TEXT NOT NULL,
          day TEXT NOT NULL,
          quiz_type TEXT NOT NULL,
          bank_json TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (child, day, quiz_type)
        )
        """
    )


def _add_per_type_current_questions(conn: sqlite3.Connection) -> None:
    """Keep one unfinished question for each quiz tab."""
    for column in ("current_math_qid", "current_knowledge_qid"):
        if not _has_column(conn, "sessions", column):
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {column} TEXT")


def _create_profile_current_questions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS session_current_questions (
          session_id TEXT NOT NULL,
          child TEXT NOT NULL,
          quiz_type TEXT NOT NULL,
          question_id TEXT NOT NULL,
          PRIMARY KEY (session_id, child, quiz_type)
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO session_current_questions(session_id, child, quiz_type, question_id)
        SELECT session_id, child, current_quiz_type, current_qid
        FROM sessions
        WHERE child IS NOT NULL AND current_qid IS NOT NULL AND current_quiz_type IS NOT NULL
        """
    )


MIGRATIONS: tuple[Migration, ...] = (
    (1, "create quiz session and daily statistics tables", _create_initial_schema),
    (2, "add answered counters to legacy tables", _add_answered_count),
    (3, "track served questions to prevent daily duplicates", _create_served_questions),
    (4, "store the current quiz type with the active question", _add_current_quiz_type),
    (5, "persist generated daily question banks", _create_daily_question_banks),
    (6, "persist one unfinished question per quiz type", _add_per_type_current_questions),
    (7, "persist unfinished questions per child profile", _create_profile_current_questions),
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
