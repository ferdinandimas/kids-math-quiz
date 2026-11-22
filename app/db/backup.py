"""SQLite backup, integrity, and restore helpers for scripts/backup_db.py and verify_backup.py."""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from app import config


class BackupError(RuntimeError):
    """A backup or restore step failed; the message says which and why."""


def _connect_read_only(path: Path) -> sqlite3.Connection:
    """Open an existing database without ever creating or changing it."""
    if not path.is_file():
        raise BackupError(f"Database not found: {path}")
    return sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro",
        uri=True,
        timeout=config.SQLITE_BUSY_TIMEOUT_MS / 1000,
    )


def default_backup_path(db_path: Path, now: datetime) -> Path:
    """`<db dir>/backups/<db name>-YYYYMMDD-HHMMSS.sqlite3`, timestamped in APP_TIMEZONE."""
    return db_path.parent / "backups" / f"{db_path.stem}-{now:%Y%m%d-%H%M%S}.sqlite3"


def copy_database(source: Path, destination: Path) -> None:
    """Copy a live database page by page with SQLite's online backup API."""
    if destination.exists():
        raise BackupError(f"Refusing to overwrite existing file: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = _connect_read_only(source)
    try:
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
        finally:
            dst.close()
    except sqlite3.Error as exc:
        destination.unlink(missing_ok=True)
        raise BackupError(f"Backup from {source} failed: {exc}") from exc
    finally:
        src.close()


def integrity_problems(path: Path) -> list[str]:
    """Empty when `PRAGMA integrity_check` and `PRAGMA foreign_key_check` are clean."""
    try:
        conn = _connect_read_only(path)
        try:
            integrity = [row[0] for row in conn.execute("PRAGMA integrity_check")]
            foreign_keys = conn.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return [f"unreadable database: {exc}"]
    problems = [] if integrity == ["ok"] else integrity
    problems += [f"foreign key violation: {row}" for row in foreign_keys]
    return problems


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def describe(path: Path) -> dict:
    """Schema version and row count per table."""
    conn = _connect_read_only(path)
    try:
        tables = _tables(conn)
        version = None
        if "schema_migrations" in tables:
            version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
        counts = {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    finally:
        conn.close()
    return {"schema_version": version, "tables": counts}


def database_digest(path: Path) -> str:
    """SHA-256 over every table's schema and rows, so two databases can be compared exactly."""
    digest = hashlib.sha256()
    conn = _connect_read_only(path)
    try:
        for (sql,) in conn.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ):
            digest.update(sql.encode())
        for table in _tables(conn):
            digest.update(table.encode())
            for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid'):
                digest.update(repr(tuple(row)).encode())
    finally:
        conn.close()
    return digest.hexdigest()
