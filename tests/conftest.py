"""Test configuration for the legacy characterization suite.

`app.main` builds the application (and migrates the database) at import time, and
`app.config` reads its environment at import time. This module therefore isolates the
environment *before* anything under `app` is imported.
"""

import os
import random
import shutil
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_DEFAULT_DB = REPO_ROOT / "math_app.sqlite3"


def _file_state(path: Path):
    return (path.stat().st_size, path.stat().st_mtime_ns) if path.exists() else None


# Captured before any app import so tests can prove importing the app did not touch it.
REPO_DEFAULT_DB_STATE = _file_state(REPO_DEFAULT_DB)

_IMPORT_DB_DIR = tempfile.mkdtemp(prefix="kids-quiz-tests-")
IMPORT_TIME_DB = Path(_IMPORT_DB_DIR) / "import-time.sqlite3"
os.environ["DB_PATH"] = str(IMPORT_TIME_DB)
# Test the defaults, not a developer's local or Railway-shell overrides.
for _name in (
    "ADMIN_CLEAR_PASSWORD",
    "APP_TIMEZONE",
    "SESSION_COOKIE_SECURE",
    "SESSION_COOKIE_MAX_AGE",
    "SQLITE_BUSY_TIMEOUT_MS",
    "RAILWAY_ENVIRONMENT",
    "RAILWAY_ENVIRONMENT_NAME",
    "RAILWAY_ENVIRONMENT_ID",
    "KIDQUEST_ENABLED",
    "KIDQUEST_PROFILE_ALLOWLIST",
    "KIDQUEST_DAILY_ATTEMPT_LIMIT",
    "KIDQUEST_PARENT_DASHBOARD_ENABLED",
    "KIDQUEST_ADULT_SESSION_MAX_AGE",
    "PARENT_PIN_HASH",
    "SESSION_SIGNING_KEY",
):
    os.environ.pop(_name, None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.main  # noqa: E402,F401  (runs the import-time create_app against IMPORT_TIME_DB)
from app.main import create_app  # noqa: E402
from app.services import question_service  # noqa: E402
from tests.support import FrozenClock  # noqa: E402


def pytest_unconfigure(config):
    shutil.rmtree(_IMPORT_DB_DIR, ignore_errors=True)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """A fresh, empty SQLite file for one test; every db_conn() call resolves to it."""
    path = tmp_path / "kids-quiz.sqlite3"
    monkeypatch.setenv("DB_PATH", str(path))
    return path


@pytest.fixture
def clock(monkeypatch):
    """Frozen application clock: 2026-11-21 10:00 Asia/Jakarta."""
    frozen = FrozenClock()
    frozen.install(monkeypatch)
    return frozen


@pytest.fixture
def seeded_random(monkeypatch):
    """Deterministic adaptive question selection."""
    rng = random.Random(20261121)
    monkeypatch.setattr(question_service, "random", rng)
    return rng


@pytest.fixture
def app(db_path, clock, seeded_random):
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def make_client(app):
    """Independent browser sessions (separate cookie jars) against the same app."""
    return lambda: TestClient(app)
