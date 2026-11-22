"""Application clock.

Every day boundary (sessions, daily banks, statistics, quotas, and later KidQuest) uses
APP_TIMEZONE, never the process or container timezone. Code reads time only through this
module; tests install a frozen clock with set_clock().
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import APP_TIMEZONE, ConfigError


def load_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(f"APP_TIMEZONE={name!r} is not a valid IANA timezone, for example 'Asia/Jakarta'.") from exc


class Clock:
    """The system time, expressed in the application timezone."""

    def __init__(self, timezone: str = APP_TIMEZONE):
        self.timezone = load_timezone(timezone)

    def now(self) -> datetime:
        return datetime.now(self.timezone)


_clock = Clock()


def get_clock() -> Clock:
    return _clock


def set_clock(clock: Clock) -> Clock:
    """Install a clock and return the previous one."""
    global _clock
    previous, _clock = _clock, clock
    return previous


def now() -> datetime:
    """Timezone-aware current time in APP_TIMEZONE."""
    return _clock.now()


def today() -> date:
    return now().date()


def today_str() -> str:
    return today().isoformat()


def now_str() -> str:
    """Local wall time without an offset, the legacy `created_at`/`generated_at` format."""
    return now().replace(tzinfo=None).isoformat(timespec="seconds")
