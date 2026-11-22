"""The admin-secret check stops app startup in production, but never the build or migrations."""

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app import config
from app.config import ConfigError
from app.main import create_app
from tests.conftest import REPO_ROOT

PRODUCTION = {"RAILWAY_ENVIRONMENT": "production"}
SECRET_ERROR = "ADMIN_CLEAR_PASSWORD is unset or still the legacy default"


def production_env(**extra) -> dict:
    """A production-like environment with no admin secret unless one is given."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in config.PRODUCTION_MARKERS and key not in {"ADMIN_CLEAR_PASSWORD", "DB_PATH"}
    }
    # Put this interpreter first so `python` in shell scripts has the app's dependencies.
    env["PATH"] = f"{Path(sys.executable).parent}{os.pathsep}{env.get('PATH', '')}"
    env.update(PRODUCTION, PYTHONPATH=str(REPO_ROOT), **extra)
    return env


@pytest.mark.parametrize("password", [None, "masukaja"])
def test_create_app_refuses_production_without_a_real_secret(db_path, monkeypatch, password):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    if password:
        monkeypatch.setenv("ADMIN_CLEAR_PASSWORD", password)

    with pytest.raises(ConfigError, match=SECRET_ERROR):
        create_app()
    assert not db_path.exists()  # Refused before touching the database.


def test_create_app_starts_in_production_with_a_real_secret(db_path, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ADMIN_CLEAR_PASSWORD", "a-strong-secret")

    assert create_app() is not None
    assert db_path.exists()


def test_uvicorn_import_fails_with_an_actionable_message(tmp_path):
    env = production_env(DB_PATH=str(tmp_path / "app.sqlite3"))

    result = subprocess.run(
        [sys.executable, "-c", "import app.main"], cwd=tmp_path, env=env, capture_output=True, text=True
    )

    assert result.returncode != 0
    assert SECRET_ERROR in result.stderr
    assert "Railway service variables" in result.stderr


def test_dockerfile_seed_step_runs_without_the_secret(tmp_path):
    """Mirrors `DB_PATH=/app/seed/kids-quiz.sqlite3 python scripts/migrate.py` in the Dockerfile."""
    seed = tmp_path / "seed" / "kids-quiz.sqlite3"
    seed.parent.mkdir()

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "migrate.py")],
        cwd=tmp_path,
        env=production_env(DB_PATH=str(seed)),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "Applied SQLite migrations: 1, 2, 3, 4, 5, 6, 7, 8, 9"


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_entrypoint_migrates_without_the_secret_and_app_start_is_refused(tmp_path):
    seed = tmp_path / "seed" / "kids-quiz.sqlite3"
    seed.parent.mkdir()
    db = tmp_path / "data" / "kids-quiz" / "kids-quiz.sqlite3"
    base = production_env(APP_DIR=str(REPO_ROOT), SEED_DB=str(seed))
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "migrate.py")],
        cwd=tmp_path, env={**base, "DB_PATH": str(seed)}, check=True, capture_output=True,
    )
    entrypoint = ["sh", str(REPO_ROOT / "docker-entrypoint.sh")]
    env = {**base, "DB_PATH": str(db)}

    migrated = subprocess.run(entrypoint + ["true"], cwd=tmp_path, env=env, capture_output=True, text=True)
    refused = subprocess.run(
        entrypoint + [sys.executable, "-c", "import app.main"], cwd=tmp_path, env=env, capture_output=True, text=True
    )
    started = subprocess.run(
        entrypoint + [sys.executable, "-c", "import app.main; print('started')"],
        cwd=tmp_path,
        env={**env, "ADMIN_CLEAR_PASSWORD": "a-strong-secret"},
        capture_output=True,
        text=True,
    )

    assert migrated.returncode == 0, migrated.stderr
    assert migrated.stdout.strip() == "SQLite schema is up to date."  # Copied from the migrated seed.
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 9
    finally:
        conn.close()
    assert refused.returncode != 0 and SECRET_ERROR in refused.stderr
    assert started.returncode == 0, started.stderr
    assert started.stdout.strip().splitlines()[-1] == "started"
