"""Characterize migrations on empty, populated, and already-migrated databases.

Migrations 1-7 are the legacy schema; Migration 8 (KidQuest, additive) is covered in depth by
tests/integration/kidquest/test_migration.py.
"""

import os
import sqlite3
import subprocess
import sys

import pytest

from app.db import migrations
from app.db.migrations import MIGRATIONS, migrate
from app.db.repo import Repo
from tests.conftest import REPO_ROOT

EXPECTED_COLUMNS = {
    "schema_migrations": ["version", "description", "applied_at"],
    "sessions": [
        "session_id",
        "child",
        "day",
        "served_count",
        "answered_count",
        "correct_count",
        "earned",
        "current_qid",
        "created_at",
        "current_quiz_type",
        "current_math_qid",
        "current_knowledge_qid",
    ],
    "child_daily": ["child", "day", "served_count", "answered_count", "correct_count", "earned"],
    "served_questions": ["child", "day", "quiz_type", "question_id", "served_at"],
    "daily_question_banks": ["child", "day", "quiz_type", "bank_json", "created_at"],
    "session_current_questions": ["session_id", "child", "quiz_type", "question_id"],
}


@pytest.fixture
def conn(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


def columns(conn, table) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def tables(conn) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def schema(conn) -> list[tuple]:
    return [tuple(row) for row in conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name")]


def rows(conn, sql) -> list[dict]:
    return [dict(row) for row in conn.execute(sql)]


def applied_versions(conn) -> list[int]:
    return [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]


def migrate_to(conn, version, monkeypatch) -> list[int]:
    """Apply migrations up to `version` only, as an older release would have."""
    with monkeypatch.context() as patch:
        patch.setattr(migrations, "MIGRATIONS", MIGRATIONS[:version])
        return migrate(conn)


def create_pre_versioning_database(conn) -> None:
    """The original schema: no schema_migrations table and no answered counters."""
    conn.executescript(
        """
        CREATE TABLE sessions (
          session_id TEXT PRIMARY KEY,
          child TEXT,
          day TEXT,
          served_count INTEGER NOT NULL DEFAULT 0,
          correct_count INTEGER NOT NULL DEFAULT 0,
          earned INTEGER NOT NULL DEFAULT 0,
          current_qid TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE child_daily (
          child TEXT NOT NULL,
          day TEXT NOT NULL,
          served_count INTEGER NOT NULL DEFAULT 0,
          correct_count INTEGER NOT NULL DEFAULT 0,
          earned INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (child, day)
        );
        INSERT INTO sessions VALUES ('sess-a', 'alleia', '2026-11-20', 12, 9, 450, 'v1_q0007', '2026-11-20T08:00:00');
        INSERT INTO sessions VALUES ('sess-b', NULL, '2026-11-20', 0, 0, 0, NULL, '2026-11-20T09:00:00');
        INSERT INTO child_daily VALUES ('alleia', '2026-11-19', 30, 25, 1250);
        INSERT INTO child_daily VALUES ('alleia', '2026-11-20', 12, 9, 450);
        INSERT INTO child_daily VALUES ('althafandra', '2026-11-20', 40, 31, 1550);
        """
    )
    conn.commit()


def test_migrations_are_numbered_one_to_nine():
    assert [version for version, _, _ in MIGRATIONS] == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_empty_database_migrates_to_the_full_schema(conn):
    assert migrate(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    assert applied_versions(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert set(EXPECTED_COLUMNS) <= tables(conn)
    assert all(name.startswith("kidquest_") for name in tables(conn) - set(EXPECTED_COLUMNS))
    for table, expected in EXPECTED_COLUMNS.items():
        assert columns(conn, table) == expected, table


def test_migrations_are_idempotent(conn):
    migrate(conn)
    before = schema(conn)

    assert migrate(conn) == []
    assert schema(conn) == before
    assert applied_versions(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_every_migration_operation_is_safe_to_rerun(conn):
    """Losing schema_migrations re-applies all seven without error or data loss."""
    migrate(conn)
    conn.execute("INSERT INTO child_daily VALUES ('alleia', '2026-11-21', 5, 4, 3, 150)")
    conn.execute(
        "INSERT INTO sessions(session_id, child, day, created_at, current_qid, current_quiz_type) "
        "VALUES ('s1', 'alleia', '2026-11-21', 'now', 'v1_q0001', 'math')"
    )
    conn.execute("INSERT INTO session_current_questions VALUES ('s1', 'alleia', 'math', 'v1_q0001')")
    conn.commit()
    conn.execute("DROP TABLE schema_migrations")
    conn.commit()

    assert migrate(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert rows(conn, "SELECT * FROM child_daily") == [
        {"child": "alleia", "day": "2026-11-21", "served_count": 5, "answered_count": 4, "correct_count": 3, "earned": 150}
    ]
    assert len(rows(conn, "SELECT * FROM session_current_questions")) == 1


def test_pre_versioning_database_migrates_without_losing_counters(conn):
    create_pre_versioning_database(conn)

    assert migrate(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    assert rows(conn, "SELECT child, day, served_count, answered_count, correct_count, earned FROM child_daily ORDER BY child, day") == [
        {"child": "alleia", "day": "2026-11-19", "served_count": 30, "answered_count": 0, "correct_count": 25, "earned": 1250},
        {"child": "alleia", "day": "2026-11-20", "served_count": 12, "answered_count": 0, "correct_count": 9, "earned": 450},
        {"child": "althafandra", "day": "2026-11-20", "served_count": 40, "answered_count": 0, "correct_count": 31, "earned": 1550},
    ]
    session = rows(conn, "SELECT * FROM sessions WHERE session_id = 'sess-a'")[0]
    assert {key: session[key] for key in ("child", "served_count", "answered_count", "correct_count", "earned", "current_qid")} == {
        "child": "alleia",
        "served_count": 12,
        "answered_count": 0,
        "correct_count": 9,
        "earned": 450,
        "current_qid": "v1_q0007",
    }
    # Without a current_quiz_type, migration 7 has nothing to backfill.
    assert rows(conn, "SELECT * FROM session_current_questions") == []
    for table, expected in EXPECTED_COLUMNS.items():
        assert sorted(columns(conn, table)) == sorted(expected), table
    assert migrate(conn) == []


def test_version_six_database_backfills_unfinished_questions_in_migration_seven(conn, monkeypatch):
    assert migrate_to(conn, 6, monkeypatch) == [1, 2, 3, 4, 5, 6]
    conn.executescript(
        """
        INSERT INTO sessions(session_id, child, day, served_count, answered_count, correct_count, earned,
                             current_qid, created_at, current_quiz_type, current_math_qid)
        VALUES ('sess-a', 'alleia', '2026-11-21', 3, 2, 1, 50, 'v1_q0003', 'now', 'math', 'v1_q0003');
        INSERT INTO sessions(session_id, child, day, current_qid, created_at, current_quiz_type)
        VALUES ('sess-b', 'althafandra', '2026-11-21', 'knowledge_mahir_001', 'now', 'knowledge');
        INSERT INTO sessions(session_id, child, day, current_qid, created_at)
        VALUES ('sess-c', NULL, '2026-11-21', NULL, 'now');
        INSERT INTO child_daily VALUES ('alleia', '2026-11-21', 3, 2, 1, 50);
        INSERT INTO served_questions(child, day, quiz_type, question_id) VALUES ('alleia', '2026-11-21', 'math', 'v1_q0003');
        INSERT INTO daily_question_banks(child, day, quiz_type, bank_json) VALUES ('alleia', '2026-11-21', 'math', '[]');
        """
    )
    conn.commit()

    assert migrate(conn) == [7, 8, 9]

    assert rows(conn, "SELECT * FROM session_current_questions ORDER BY session_id") == [
        {"session_id": "sess-a", "child": "alleia", "quiz_type": "math", "question_id": "v1_q0003"},
        {"session_id": "sess-b", "child": "althafandra", "quiz_type": "knowledge", "question_id": "knowledge_mahir_001"},
    ]
    assert rows(conn, "SELECT served_count, answered_count, correct_count, earned FROM child_daily") == [
        {"served_count": 3, "answered_count": 2, "correct_count": 1, "earned": 50}
    ]
    assert len(rows(conn, "SELECT * FROM served_questions")) == 1
    assert len(rows(conn, "SELECT * FROM daily_question_banks")) == 1


def test_repo_init_db_migrates_the_configured_path(db_path):
    Repo().init_db()

    conn = sqlite3.connect(db_path)
    try:
        assert applied_versions(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    finally:
        conn.close()


def test_migrate_script_applies_then_reports_up_to_date(db_path, tmp_path):
    env = {**os.environ, "DB_PATH": str(db_path), "PYTHONPATH": str(REPO_ROOT)}
    command = [sys.executable, str(REPO_ROOT / "scripts" / "migrate.py")]

    first = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    second = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, check=True)

    assert first.stdout.strip() == "Applied SQLite migrations: 1, 2, 3, 4, 5, 6, 7, 8, 9"
    assert second.stdout.strip() == "SQLite schema is up to date."
    assert not (tmp_path / "math_app.sqlite3").exists()
