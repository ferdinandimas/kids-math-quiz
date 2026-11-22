"""Backup a populated database, verify it, and restore it exactly into a fresh location."""

import os
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from app.db.backup import (
    BackupError,
    copy_database,
    database_digest,
    default_backup_path,
    describe,
    integrity_problems,
)
from tests.conftest import REPO_ROOT
from tests.support import JAKARTA, answer_one, fetch_question, select_child


def run_script(name: str, *args: str, cwd: Path, db_path: Path | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    if db_path:
        env["DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / name), *args], cwd=cwd, env=env, capture_output=True, text=True
    )


@pytest.fixture
def populated_db(make_client, db_path):
    """A representative database: both children, both quiz types, answers, and open questions."""
    for child in ("alleia", "althafandra"):
        client = make_client()
        select_child(client, child)
        answer_one(client, child, correct=True)
        answer_one(client, child, correct=False)
        answer_one(client, child, "knowledge")
        fetch_question(client)  # Leave an unfinished question.
    return db_path


def test_backup_and_verify_scripts_restore_the_database_exactly(populated_db, tmp_path):
    backup = tmp_path / "backups" / "kids-quiz-backup.sqlite3"
    restored = tmp_path / "restored" / "kids-quiz.sqlite3"

    backed_up = run_script("backup_db.py", "--output", str(backup), cwd=tmp_path, db_path=populated_db)
    verified = run_script(
        "verify_backup.py", str(backup), "--restore-to", str(restored), "--compare-with", str(populated_db), cwd=tmp_path
    )

    assert backed_up.returncode == 0, backed_up.stderr
    assert f"Backup written: {backup}" in backed_up.stdout
    assert "integrity_check: ok" in backed_up.stdout and "schema version: 9" in backed_up.stdout
    assert verified.returncode == 0, verified.stderr
    assert "restore test: ok" in verified.stdout and f"matches: {populated_db}" in verified.stdout

    assert database_digest(restored) == database_digest(populated_db) == database_digest(backup)
    assert describe(restored) == describe(populated_db)
    assert describe(restored)["tables"]["child_daily"] == 2
    assert integrity_problems(restored) == []


def test_backup_defaults_to_db_path_and_a_timestamped_backups_folder(populated_db, tmp_path):
    result = run_script("backup_db.py", cwd=tmp_path, db_path=populated_db)

    assert result.returncode == 0, result.stderr
    backups = list((populated_db.parent / "backups").glob("kids-quiz-*.sqlite3"))
    assert len(backups) == 1
    assert database_digest(backups[0]) == database_digest(populated_db)


def test_default_backup_name_uses_the_given_time():
    path = default_backup_path(Path("/data/kids-quiz/kids-quiz.sqlite3"), datetime(2026, 11, 21, 9, 5, 7, tzinfo=JAKARTA))

    assert path == Path("/data/kids-quiz/backups/kids-quiz-20261121-090507.sqlite3")


def test_verify_without_restore_to_uses_a_temporary_copy(populated_db, tmp_path):
    backup = tmp_path / "b.sqlite3"
    copy_database(populated_db, backup)

    result = run_script("verify_backup.py", str(backup), cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "restore test: ok (temporary copy removed)" in result.stdout


def test_backup_refuses_a_missing_source_without_creating_it(tmp_path):
    missing = tmp_path / "missing.sqlite3"

    result = run_script("backup_db.py", "--output", str(tmp_path / "out.sqlite3"), cwd=tmp_path, db_path=missing)

    assert result.returncode == 1 and "Database not found" in result.stderr
    assert not missing.exists() and not (tmp_path / "out.sqlite3").exists()


def test_backup_and_restore_never_overwrite_existing_files(populated_db, tmp_path):
    existing = tmp_path / "existing.sqlite3"
    existing.write_bytes(b"keep me")

    with pytest.raises(BackupError, match="Refusing to overwrite"):
        copy_database(populated_db, existing)
    backup = tmp_path / "b.sqlite3"
    copy_database(populated_db, backup)
    result = run_script("verify_backup.py", str(backup), "--restore-to", str(existing), cwd=tmp_path)

    assert result.returncode == 1 and "Refusing to overwrite" in result.stderr
    assert existing.read_bytes() == b"keep me"


def test_verify_rejects_a_corrupted_backup(populated_db, tmp_path):
    backup = tmp_path / "b.sqlite3"
    copy_database(populated_db, backup)
    data = bytearray(backup.read_bytes())
    data[100:4096] = b"\xff" * (4096 - 100)  # Wreck the first page after the header.
    backup.write_bytes(bytes(data))

    result = run_script("verify_backup.py", str(backup), cwd=tmp_path)

    assert result.returncode == 1 and "Verification FAILED" in result.stderr


def test_verify_rejects_a_database_without_schema_migrations(tmp_path):
    other = tmp_path / "other.sqlite3"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE t (x)")
    conn.close()

    result = run_script("verify_backup.py", str(other), cwd=tmp_path)

    assert result.returncode == 1 and "not an application database" in result.stderr


def test_compare_with_detects_a_changed_database(populated_db, tmp_path):
    backup = tmp_path / "b.sqlite3"
    copy_database(populated_db, backup)
    conn = sqlite3.connect(populated_db)
    with conn:
        conn.execute("UPDATE child_daily SET earned = earned + 1")
    conn.close()

    result = run_script("verify_backup.py", str(backup), "--compare-with", str(populated_db), cwd=tmp_path)

    assert result.returncode == 1 and "backup differs" in result.stderr


def test_backup_is_consistent_while_the_app_holds_a_write_transaction(populated_db, tmp_path):
    """An open, uncommitted write is not captured; the backup is the last committed state."""
    committed = database_digest(populated_db)
    writer = sqlite3.connect(populated_db, isolation_level=None)
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("UPDATE child_daily SET earned = 999999")
    try:
        backup = tmp_path / "during-write.sqlite3"
        copy_database(populated_db, backup)
    finally:
        writer.execute("ROLLBACK")
        writer.close()

    assert database_digest(backup) == committed
    assert integrity_problems(backup) == []
