"""Runtime configuration parsing and the production admin-secret check."""

import os
import subprocess
import sys

import pytest

from app import config
from app.config import ConfigError, env_flag, env_int, is_production, validate_startup_config
from tests.conftest import REPO_ROOT
from app.services.parent_auth_service import MIN_ITERATIONS, hash_parent_pin


VALID_PIN_HASH = hash_parent_pin("2468", iterations=MIN_ITERATIONS, salt=b"0123456789abcdef")


@pytest.mark.parametrize("marker", config.PRODUCTION_MARKERS)
def test_any_railway_marker_means_production(marker):
    assert is_production({marker: "production"}) is True


def test_no_or_blank_markers_mean_local():
    assert is_production({}) is False
    assert is_production({"RAILWAY_ENVIRONMENT": "  "}) is False


@pytest.mark.parametrize("raw, expected", [("1", True), ("TRUE", True), (" yes ", True), ("on", True),
                                           ("0", False), ("false", False), ("No", False), ("off", False)])
def test_env_flag_parses_booleans(raw, expected):
    assert env_flag("FLAG", default=not expected, environ={"FLAG": raw}) is expected


def test_env_flag_uses_the_default_when_unset_or_blank():
    assert env_flag("FLAG", default=True, environ={}) is True
    assert env_flag("FLAG", default=False, environ={"FLAG": ""}) is False


def test_env_flag_rejects_other_values():
    with pytest.raises(ConfigError, match="FLAG must be true or false"):
        env_flag("FLAG", default=False, environ={"FLAG": "maybe"})


def test_env_int_parses_positive_integers():
    assert env_int("N", 5, environ={}) == 5
    assert env_int("N", 5, environ={"N": " 250 "}) == 250
    for bad in ("0", "-1", "1.5", "lots"):
        with pytest.raises(ConfigError, match="N must be a positive whole number"):
            env_int("N", 5, environ={"N": bad})


def test_local_defaults():
    assert config.APP_TIMEZONE == "Asia/Jakarta"
    assert config.SESSION_COOKIE_SECURE is False
    assert config.SESSION_COOKIE_MAX_AGE == 365 * 24 * 60 * 60
    assert config.SESSION_COOKIE_PATH == "/"
    assert config.SQLITE_BUSY_TIMEOUT_MS == 5000
    assert config.ADMIN_CLEAR_PASSWORD == "masukaja"  # Still the local default.
    assert config.KIDQUEST_PARENT_DASHBOARD_ENABLED is False
    assert config.KIDQUEST_ADULT_SESSION_MAX_AGE == 900


def test_local_startup_accepts_the_legacy_default_password():
    validate_startup_config({})
    validate_startup_config({"ADMIN_CLEAR_PASSWORD": "masukaja"})


@pytest.mark.parametrize("password", [None, "", "   ", "masukaja", " masukaja "])
def test_production_startup_rejects_unset_or_default_password(password):
    environ = {"RAILWAY_ENVIRONMENT": "production"}
    if password is not None:
        environ["ADMIN_CLEAR_PASSWORD"] = password

    with pytest.raises(ConfigError) as error:
        validate_startup_config(environ)

    message = str(error.value)
    assert "ADMIN_CLEAR_PASSWORD" in message and "Railway service variables" in message


def test_production_startup_accepts_a_real_secret():
    validate_startup_config({"RAILWAY_ENVIRONMENT_NAME": "production", "ADMIN_CLEAR_PASSWORD": "a-strong-secret"})


def test_local_dashboard_with_missing_or_weak_secrets_stays_unavailable(monkeypatch):
    monkeypatch.setattr(config, "KIDQUEST_PARENT_DASHBOARD_ENABLED", True)
    monkeypatch.setattr(config, "PARENT_PIN_HASH", VALID_PIN_HASH)
    monkeypatch.setattr(config, "SESSION_SIGNING_KEY", "short")

    validate_startup_config({})
    assert config.adult_dashboard_ready() is False


def test_malformed_parent_hash_fails_fast_when_dashboard_enabled(monkeypatch):
    monkeypatch.setattr(config, "KIDQUEST_PARENT_DASHBOARD_ENABLED", True)
    monkeypatch.setattr(config, "PARENT_PIN_HASH", "not-a-hash")

    with pytest.raises(ConfigError, match="PARENT_PIN_HASH"):
        validate_startup_config({})


@pytest.mark.parametrize("missing", ["PARENT_PIN_HASH", "SESSION_SIGNING_KEY"])
def test_production_dashboard_requires_both_strong_secrets(missing):
    environ = {
        "RAILWAY_ENVIRONMENT": "production",
        "ADMIN_CLEAR_PASSWORD": "a-strong-secret",
        "KIDQUEST_PARENT_DASHBOARD_ENABLED": "true",
        "PARENT_PIN_HASH": VALID_PIN_HASH,
        "SESSION_SIGNING_KEY": "s" * 32,
    }
    environ.pop(missing)

    with pytest.raises(ConfigError, match="KIDQUEST_PARENT_DASHBOARD_ENABLED"):
        validate_startup_config(environ)


@pytest.mark.parametrize(
    "extra_env, expected",
    [
        ({}, "False"),
        ({"RAILWAY_ENVIRONMENT": "production"}, "True"),
        ({"RAILWAY_ENVIRONMENT": "production", "SESSION_COOKIE_SECURE": "false"}, "False"),
        ({"SESSION_COOKIE_SECURE": "true"}, "True"),
    ],
)
def test_session_cookie_secure_defaults_on_in_production(tmp_path, extra_env, expected):
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in config.PRODUCTION_MARKERS and key != "SESSION_COOKIE_SECURE"
    }
    env.update(extra_env, PYTHONPATH=str(REPO_ROOT))

    result = subprocess.run(
        [sys.executable, "-c", "import app.config as c; print(c.SESSION_COOKIE_SECURE)"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == expected
