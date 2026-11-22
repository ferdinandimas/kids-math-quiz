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


# Migration 8: additive KidQuest state. Plain SQL only; content files are never read here.
# The theme IDs, quest statuses, and core building types are literal copies of
# app/domain/kidquest/theme.py, state.py, and content.py; tests prove they agree.
KIDQUEST_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS kidquest_worlds (
      child TEXT PRIMARY KEY,
      layout_version TEXT NOT NULL,
      theme_id TEXT NOT NULL DEFAULT 'perkampungan'
        CHECK (theme_id IN ('perkampungan', 'kingdom', 'city')),
      theme_manifest_version INTEGER NOT NULL DEFAULT 1 CHECK (theme_manifest_version >= 1),
      width INTEGER NOT NULL CHECK (width > 0),
      height INTEGER NOT NULL CHECK (height > 0),
      version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kidquest_buildings (
      id INTEGER PRIMARY KEY,
      child TEXT NOT NULL REFERENCES kidquest_worlds(child),
      type TEXT NOT NULL,
      x INTEGER NOT NULL CHECK (x >= 0),
      y INTEGER NOT NULL CHECK (y >= 0),
      rotation INTEGER NOT NULL DEFAULT 0 CHECK (rotation IN (0, 90, 180, 270)),
      placed_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_kidquest_buildings_core_type
      ON kidquest_buildings(child, type)
      WHERE type IN ('starter_house', 'garden', 'bakery', 'park', 'bridge', 'market_stall')
    """,
    """
    CREATE TABLE IF NOT EXISTS kidquest_paths (
      id INTEGER PRIMARY KEY,
      child TEXT NOT NULL REFERENCES kidquest_worlds(child),
      x INTEGER NOT NULL CHECK (x >= 0),
      y INTEGER NOT NULL CHECK (y >= 0),
      path_type TEXT NOT NULL DEFAULT 'basic_road',
      created_at TEXT NOT NULL,
      UNIQUE (child, x, y)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kidquest_child_quests (
      child TEXT NOT NULL REFERENCES kidquest_worlds(child),
      quest_id TEXT NOT NULL,
      quest_version INTEGER NOT NULL CHECK (quest_version >= 1),
      status TEXT NOT NULL
        CHECK (status IN ('LOCKED', 'AVAILABLE', 'IN_PROGRESS', 'READY_TO_BUILD', 'COMPLETED')),
      progress_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (child, quest_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_kidquest_child_quests_status ON kidquest_child_quests(child, status)",
    """
    CREATE TABLE IF NOT EXISTS kidquest_challenges (
      id TEXT PRIMARY KEY,
      child TEXT NOT NULL,
      quest_id TEXT NOT NULL,
      quest_version INTEGER NOT NULL CHECK (quest_version >= 1),
      content_ref TEXT NOT NULL,
      status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'COMPLETED', 'EXPIRED')),
      issued_at TEXT NOT NULL,
      completed_at TEXT,
      expires_at TEXT,
      FOREIGN KEY (child, quest_id) REFERENCES kidquest_child_quests(child, quest_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_kidquest_challenges_lookup
      ON kidquest_challenges(child, quest_id, status)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_kidquest_challenges_one_active
      ON kidquest_challenges(child, quest_id) WHERE status = 'ACTIVE'
    """,
    """
    CREATE TABLE IF NOT EXISTS kidquest_attempts (
      id INTEGER PRIMARY KEY,
      child TEXT NOT NULL REFERENCES kidquest_worlds(child),
      attempt_key TEXT NOT NULL,
      challenge_id TEXT NOT NULL REFERENCES kidquest_challenges(id),
      skill_id TEXT NOT NULL,
      content_version INTEGER NOT NULL CHECK (content_version >= 1),
      is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
      hint_count INTEGER NOT NULL DEFAULT 0 CHECK (hint_count >= 0),
      attempted_at TEXT NOT NULL,
      UNIQUE (child, attempt_key)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_kidquest_attempts_challenge ON kidquest_attempts(challenge_id)",
    """
    CREATE TABLE IF NOT EXISTS kidquest_resource_balances (
      child TEXT NOT NULL REFERENCES kidquest_worlds(child),
      resource_type TEXT NOT NULL,
      balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
      updated_at TEXT NOT NULL,
      PRIMARY KEY (child, resource_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kidquest_resource_ledger (
      id INTEGER PRIMARY KEY,
      child TEXT NOT NULL REFERENCES kidquest_worlds(child),
      resource_type TEXT NOT NULL,
      delta INTEGER NOT NULL CHECK (delta <> 0),
      source_type TEXT NOT NULL,
      source_ref TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE (child, resource_type, source_type, source_ref)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kidquest_blueprints (
      child TEXT NOT NULL REFERENCES kidquest_worlds(child),
      building_type TEXT NOT NULL,
      acquisition_type TEXT NOT NULL,
      source_ref TEXT NOT NULL,
      content_version INTEGER NOT NULL CHECK (content_version >= 1),
      acquired_at TEXT NOT NULL,
      PRIMARY KEY (child, building_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kidquest_idempotency (
      child TEXT NOT NULL,
      operation TEXT NOT NULL,
      key TEXT NOT NULL,
      request_hash TEXT NOT NULL,
      status TEXT NOT NULL,
      response_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (child, operation, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS kidquest_daily_usage (
      child TEXT NOT NULL REFERENCES kidquest_worlds(child),
      day TEXT NOT NULL,
      accepted_attempts INTEGER NOT NULL DEFAULT 0 CHECK (accepted_attempts >= 0),
      updated_at TEXT NOT NULL,
      PRIMARY KEY (child, day)
    )
    """,
)


def _create_kidquest_tables(conn: sqlite3.Connection) -> None:
    for statement in KIDQUEST_SCHEMA:
        conn.execute(statement)


# Migration 9: reset audit records are append-only by application policy. They deliberately have
# no FK to kidquest_worlds, so a reset can remove a world while preserving its audit evidence.
# Raw idempotency keys are never stored: only their SHA-256 digests. Adult-session revocations are
# persisted so logout remains effective across process restarts and multiple workers.
KIDQUEST_AUDIT_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS kidquest_audit_events (
      id INTEGER PRIMARY KEY,
      event_type TEXT NOT NULL,
      child TEXT NOT NULL,
      scope TEXT NOT NULL,
      idempotency_key_hash TEXT NOT NULL,
      request_hash TEXT NOT NULL,
      response_status INTEGER NOT NULL,
      response_json TEXT NOT NULL,
      details_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE (child, event_type, idempotency_key_hash)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_kidquest_audit_events_child_created ON kidquest_audit_events(child, created_at)",
    """
    CREATE TABLE IF NOT EXISTS kidquest_adult_session_revocations (
      nonce_hash TEXT PRIMARY KEY,
      expires_at INTEGER NOT NULL,
      revoked_at TEXT NOT NULL
    )
    """,
)


def _create_kidquest_audit_tables(conn: sqlite3.Connection) -> None:
    for statement in KIDQUEST_AUDIT_SCHEMA:
        conn.execute(statement)


MIGRATIONS: tuple[Migration, ...] = (
    (1, "create quiz session and daily statistics tables", _create_initial_schema),
    (2, "add answered counters to legacy tables", _add_answered_count),
    (3, "track served questions to prevent daily duplicates", _create_served_questions),
    (4, "store the current quiz type with the active question", _add_current_quiz_type),
    (5, "persist generated daily question banks", _create_daily_question_banks),
    (6, "persist one unfinished question per quiz type", _add_per_type_current_questions),
    (7, "persist unfinished questions per child profile", _create_profile_current_questions),
    (8, "add additive KidQuest world, quest, and resource tables", _create_kidquest_tables),
    (9, "add append-only KidQuest reset audit and adult-session revocations", _create_kidquest_audit_tables),
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
