import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from app import config
from app.config import get_db_path

def db_conn():
    """Open a connection with the settings every application connection must have."""
    timeout_ms = config.SQLITE_BUSY_TIMEOUT_MS
    conn = sqlite3.connect(get_db_path(), timeout=timeout_ms / 1000)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {int(timeout_ms)}")
    # WAL stays off until volume behavior and backup/restore are proven with it (KQ-002).
    return conn


@contextmanager
def transaction(immediate: bool = True) -> Iterator[sqlite3.Connection]:
    """Run several statements on one connection as one unit of work.

    `BEGIN IMMEDIATE` takes the write lock up front, so concurrent writers queue on the busy
    timeout instead of failing halfway. Everything commits together, or nothing does.
    """
    conn = db_conn()
    conn.isolation_level = None  # We issue BEGIN/COMMIT/ROLLBACK ourselves.
    try:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        try:
            yield conn
            conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()