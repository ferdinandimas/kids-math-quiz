"""The application clock: APP_TIMEZONE day boundaries, independent of the process TZ."""

import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app import clock
from app.clock import Clock
from app.config import ConfigError
from tests.conftest import REPO_ROOT
from tests.support import JAKARTA, FrozenClock

DIRECT_TIME_CALL = re.compile(r"\b(date\.today|datetime\.(now|utcnow|today)|time\.localtime)\(")


def test_default_clock_uses_asia_jakarta():
    now = Clock().now()

    assert Clock().timezone == ZoneInfo("Asia/Jakarta")
    assert now.utcoffset() == timedelta(hours=7)
    assert abs(now - datetime.now(timezone.utc)) < timedelta(seconds=5)


@pytest.mark.parametrize(
    "jakarta_time, day",
    [
        (datetime(2026, 11, 21, 23, 59, 59), "2026-11-21"),
        (datetime(2026, 11, 22, 0, 0, 0), "2026-11-22"),
        (datetime(2026, 11, 22, 7, 0, 0), "2026-11-22"),
    ],
)
def test_frozen_clock_rolls_over_at_jakarta_midnight(monkeypatch, jakarta_time, day):
    FrozenClock(jakarta_time.replace(tzinfo=JAKARTA)).install(monkeypatch)

    assert clock.today_str() == day
    assert clock.today().isoformat() == day


def test_now_str_is_jakarta_wall_time_without_offset(monkeypatch):
    FrozenClock(datetime(2026, 11, 21, 17, 30, 15, tzinfo=timezone.utc)).install(monkeypatch)

    assert clock.now_str() == "2026-11-22T00:30:15"
    assert clock.now().tzinfo == JAKARTA


def test_a_configured_timezone_changes_the_boundary(monkeypatch):
    FrozenClock(datetime(2026, 11, 22, 0, 0, tzinfo=JAKARTA), timezone_name="UTC").install(monkeypatch)

    assert clock.today_str() == "2026-11-21"


def test_set_clock_returns_the_previous_clock():
    replacement = Clock("UTC")
    previous = clock.set_clock(replacement)
    try:
        assert clock.get_clock() is replacement
    finally:
        assert clock.set_clock(previous) is replacement


@pytest.mark.parametrize("name", ["Mars/Olympus_Mons", "", "../etc/passwd"])
def test_invalid_timezone_is_a_configuration_error(name):
    with pytest.raises(ConfigError, match="APP_TIMEZONE"):
        Clock(name)


@pytest.mark.parametrize(
    "value, expected_returncode, expected_output",
    [("UTC", 0, "UTC"), ("Asia/Jakarta", 0, "Asia/Jakarta"), ("Not/AZone", 1, "APP_TIMEZONE='Not/AZone'")],
)
def test_app_timezone_environment_variable(tmp_path, value, expected_returncode, expected_output):
    env = {**os.environ, "APP_TIMEZONE": value, "PYTHONPATH": str(REPO_ROOT)}

    result = subprocess.run(
        [sys.executable, "-c", "from app import clock; print(clock.get_clock().timezone)"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == expected_returncode
    assert expected_output in (result.stdout + result.stderr)


def test_no_direct_system_time_calls_outside_the_clock():
    offenders = [
        f"{path.relative_to(REPO_ROOT)}:{number}"
        for folder in ("app", "scripts")
        for path in sorted((REPO_ROOT / folder).rglob("*.py"))
        if path != REPO_ROOT / "app" / "clock.py"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if DIRECT_TIME_CALL.search(line)
    ]

    assert offenders == []
