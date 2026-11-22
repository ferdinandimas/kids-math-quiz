"""Importing the app under test must never read or create a developer's database."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.config import get_db_path
from app.db.sqlite import db_conn
from tests.conftest import IMPORT_TIME_DB, REPO_DEFAULT_DB, REPO_DEFAULT_DB_STATE, REPO_ROOT, _file_state


def test_import_time_app_used_a_temporary_database():
    assert IMPORT_TIME_DB.exists()
    assert REPO_ROOT not in IMPORT_TIME_DB.parents


def test_importing_the_app_left_the_repository_database_untouched():
    assert _file_state(REPO_DEFAULT_DB) == REPO_DEFAULT_DB_STATE
    assert _file_state(Path.cwd() / "math_app.sqlite3") == (
        REPO_DEFAULT_DB_STATE if Path.cwd() == REPO_ROOT else None
    )


def test_db_conn_resolves_db_path_at_call_time(tmp_path, monkeypatch):
    target = tmp_path / "late.sqlite3"
    monkeypatch.setenv("DB_PATH", str(target))

    conn = db_conn()
    try:
        conn.execute("CREATE TABLE probe (id INTEGER)")
        assert isinstance(conn.execute("SELECT 1 AS one").fetchone(), sqlite3.Row)
    finally:
        conn.close()

    assert get_db_path() == str(target)
    assert target.exists()


def test_app_imports_from_any_working_directory_without_creating_a_default_db(tmp_path):
    db = tmp_path / "subprocess.sqlite3"
    env = {**os.environ, "DB_PATH": str(db), "PYTHONPATH": str(REPO_ROOT)}
    code = (
        "from fastapi.testclient import TestClient; from app.main import app; c = TestClient(app); "
        "print(c.get('/static/css/base.css').status_code, c.get('/home').status_code)"
    )

    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True, check=True)

    assert result.stdout.split() == ["200", "200"]
    assert db.exists()
    assert not (tmp_path / "math_app.sqlite3").exists()
