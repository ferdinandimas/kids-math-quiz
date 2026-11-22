"""Connection pragmas, migrations with foreign keys, and the unit-of-work helper."""

import sqlite3
import threading
import time

import pytest

from app import config
from app.db import sqlite as app_sqlite
from app.db.migrations import migrate
from app.db.sqlite import db_conn, transaction
from tests.conftest import REPO_ROOT
from tests.support import answer_one, fetch_question, select_child


@pytest.fixture
def counter_table(db_path):
    conn = db_conn()
    with conn:
        conn.execute("CREATE TABLE counter (id INTEGER PRIMARY KEY, value INTEGER NOT NULL)")
        conn.execute("INSERT INTO counter VALUES (1, 0)")
    conn.close()


def read_counter() -> int:
    conn = db_conn()
    try:
        return conn.execute("SELECT value FROM counter WHERE id = 1").fetchone()[0]
    finally:
        conn.close()


# --- Connection factory ---------------------------------------------------------------------


def test_db_conn_enables_foreign_keys_busy_timeout_and_row_factory(db_path):
    conn = db_conn()
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"  # WAL deferred.
        assert isinstance(conn.execute("SELECT 1 AS one").fetchone(), sqlite3.Row)
    finally:
        conn.close()


def test_busy_timeout_is_configurable(db_path, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_BUSY_TIMEOUT_MS", 1234)
    conn = db_conn()
    try:
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 1234
    finally:
        conn.close()


def test_every_connection_opened_by_the_app_gets_the_pragmas(client, monkeypatch):
    """Trace every connection a full quiz flow opens; each must run both pragmas first."""
    traces: list[list[str]] = []
    real_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        statements: list[str] = []
        conn.set_trace_callback(statements.append)
        traces.append(statements)
        return conn

    monkeypatch.setattr(app_sqlite.sqlite3, "connect", traced_connect)
    select_child(client, "alleia")
    answer_one(client, "alleia")
    answer_one(client, "alleia", quiz_type="knowledge")
    client.get("/api/stats")
    client.get("/quiz/math")

    assert len(traces) > 20
    for statements in traces:
        assert statements[:2] == ["PRAGMA foreign_keys = ON", "PRAGMA busy_timeout = 5000"]


def test_application_code_opens_sqlite_only_through_the_factory():
    allowed = {REPO_ROOT / "app" / "db" / "sqlite.py", REPO_ROOT / "app" / "db" / "backup.py"}
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for folder in ("app", "scripts")
        for path in (REPO_ROOT / folder).rglob("*.py")
        if path not in allowed and "sqlite3.connect(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_migrations_pass_with_foreign_keys_enabled(db_path):
    conn = db_conn()
    try:
        assert migrate(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


# --- Unit of work -----------------------------------------------------------------------------


def test_transaction_commits_all_statements_together(counter_table):
    with transaction() as conn:
        conn.execute("UPDATE counter SET value = value + 1")
        conn.execute("INSERT INTO counter VALUES (2, 10)")
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    conn = db_conn()
    try:
        assert [tuple(row) for row in conn.execute("SELECT id, value FROM counter ORDER BY id")] == [(1, 1), (2, 10)]
    finally:
        conn.close()


def test_transaction_rolls_back_every_statement_on_an_exception(counter_table):
    with pytest.raises(RuntimeError, match="boom"):
        with transaction() as conn:
            conn.execute("UPDATE counter SET value = 99")
            conn.execute("INSERT INTO counter VALUES (2, 10)")
            raise RuntimeError("boom")

    conn = db_conn()
    try:
        assert [tuple(row) for row in conn.execute("SELECT id, value FROM counter")] == [(1, 0)]
    finally:
        conn.close()


def test_transaction_rolls_back_on_a_failing_statement(counter_table):
    with pytest.raises(sqlite3.IntegrityError):
        with transaction() as conn:
            conn.execute("UPDATE counter SET value = 5")
            conn.execute("INSERT INTO counter VALUES (1, 1)")  # Duplicate primary key.

    assert read_counter() == 0


def test_transaction_rolls_back_foreign_key_violations(db_path):
    conn = db_conn()
    with conn:
        conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL REFERENCES parent(id))")
    conn.close()

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with transaction() as tx:
            tx.execute("INSERT INTO parent VALUES (1)")
            tx.execute("INSERT INTO child VALUES (1, 404)")

    conn = db_conn()
    try:
        assert conn.execute("SELECT COUNT(*) FROM parent").fetchone()[0] == 0
    finally:
        conn.close()


def test_immediate_transaction_takes_the_write_lock_up_front(counter_table, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_BUSY_TIMEOUT_MS", 100)
    with transaction():  # No statement yet, but the write lock is already held.
        other = db_conn()
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("BEGIN IMMEDIATE")
        finally:
            other.close()


def test_deferred_transaction_does_not_lock_until_it_writes(counter_table, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_BUSY_TIMEOUT_MS", 100)
    with transaction(immediate=False):
        other = db_conn()
        try:
            other.execute("BEGIN IMMEDIATE")
            other.execute("ROLLBACK")
        finally:
            other.close()


def test_concurrent_writers_serialize_without_lost_updates(counter_table):
    """Read-modify-write in parallel: BEGIN IMMEDIATE queues writers, so no increment is lost."""
    errors = []

    def increment():
        try:
            with transaction() as conn:
                value = conn.execute("SELECT value FROM counter WHERE id = 1").fetchone()[0]
                time.sleep(0.01)  # Widen the race window.
                conn.execute("UPDATE counter SET value = ? WHERE id = 1", (value + 1,))
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=increment) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert read_counter() == 10


def test_a_second_writer_waits_for_the_first_to_commit(counter_table):
    first_has_lock = threading.Event()
    events: list[str] = []

    def first_writer():
        with transaction() as conn:
            first_has_lock.set()
            conn.execute("UPDATE counter SET value = value + 1")
            time.sleep(0.3)
            events.append("first committed")

    thread = threading.Thread(target=first_writer)
    thread.start()
    first_has_lock.wait(timeout=5)
    started = time.monotonic()
    with transaction() as conn:
        waited = time.monotonic() - started
        events.append("second began")
        assert conn.execute("SELECT value FROM counter").fetchone()[0] == 1
    thread.join(timeout=5)

    assert events == ["first committed", "second began"]
    assert waited >= 0.2


def test_busy_timeout_is_honored_when_the_lock_is_held_too_long(counter_table, monkeypatch):
    monkeypatch.setattr(config, "SQLITE_BUSY_TIMEOUT_MS", 200)
    release = threading.Event()
    locked = threading.Event()

    def holder():
        with transaction():
            locked.set()
            release.wait(timeout=5)

    thread = threading.Thread(target=holder)
    thread.start()
    locked.wait(timeout=5)
    started = time.monotonic()
    try:
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            with transaction():
                pass
        elapsed = time.monotonic() - started
    finally:
        release.set()
        thread.join(timeout=5)

    assert 0.15 <= elapsed < 2.0


def test_existing_repo_methods_still_work_alongside_the_helper(client):
    select_child(client, "alleia")
    fetch_question(client)
    with transaction() as conn:
        served = conn.execute("SELECT served_count FROM child_daily WHERE child = 'alleia'").fetchone()[0]

    assert served == 1
