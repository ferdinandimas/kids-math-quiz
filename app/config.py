import os

APP_TITLE = "Kids Math Quiz"
DAILY_LIMIT = 400
REWARD_PER_CORRECT = 50
KNOWLEDGE_REWARD_PER_CORRECT = 100
COOKIE_NAME = "math_sess"

DEFAULT_DB_PATH = "math_app.sqlite3"
DB_PATH = os.getenv("DB_PATH", DEFAULT_DB_PATH)
LEGACY_ADMIN_CLEAR_PASSWORD = "masukaja"
ADMIN_CLEAR_PASSWORD = os.getenv("ADMIN_CLEAR_PASSWORD", LEGACY_ADMIN_CLEAR_PASSWORD)

CHILDREN = ["althafandra", "alleia"]


# Railway injects these into every deployed service; any of them means production.
PRODUCTION_MARKERS = ("RAILWAY_ENVIRONMENT", "RAILWAY_ENVIRONMENT_NAME", "RAILWAY_ENVIRONMENT_ID")


class ConfigError(RuntimeError):
    """Configuration that must stop the application from starting."""


def is_production(environ=os.environ) -> bool:
    return any((environ.get(name) or "").strip() for name in PRODUCTION_MARKERS)


def env_flag(name: str, default: bool, environ=os.environ) -> bool:
    raw = (environ.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false, got {environ.get(name)!r}.")


def env_int(name: str, default: int, environ=os.environ) -> int:
    raw = (environ.get(name) or "").strip()
    if not raw:
        return default
    if not raw.isdigit() or int(raw) <= 0:
        raise ConfigError(f"{name} must be a positive whole number, got {environ.get(name)!r}.")
    return int(raw)


# Every day boundary uses this zone, never the container's local time.
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Jakarta")

SESSION_COOKIE_SECURE = env_flag("SESSION_COOKIE_SECURE", default=is_production())
SESSION_COOKIE_MAX_AGE = env_int("SESSION_COOKIE_MAX_AGE", 365 * 24 * 60 * 60)
SESSION_COOKIE_PATH = "/"

SQLITE_BUSY_TIMEOUT_MS = env_int("SQLITE_BUSY_TIMEOUT_MS", 5000)


def env_profiles(name: str, environ=os.environ) -> tuple[str, ...]:
    """Comma-separated child IDs; every one must be a configured child."""
    profiles: list[str] = []
    for part in (environ.get(name) or "").split(","):
        child = part.strip().lower()
        if child and child not in profiles:
            profiles.append(child)
    unknown = [child for child in profiles if child not in CHILDREN]
    if unknown:
        raise ConfigError(f"{name} lists unknown child ID(s) {', '.join(unknown)}; use only {', '.join(CHILDREN)}.")
    return tuple(profiles)


# KidQuest rollout. Parsed here, enforced by the KidQuest routes (KQ-007).
KIDQUEST_ENABLED = env_flag("KIDQUEST_ENABLED", default=False)
KIDQUEST_PROFILE_ALLOWLIST = env_profiles("KIDQUEST_PROFILE_ALLOWLIST")
KIDQUEST_DAILY_ATTEMPT_LIMIT = env_int("KIDQUEST_DAILY_ATTEMPT_LIMIT", 20)
KIDQUEST_PARENT_DASHBOARD_ENABLED = env_flag("KIDQUEST_PARENT_DASHBOARD_ENABLED", default=False)
PARENT_PIN_HASH = (os.getenv("PARENT_PIN_HASH") or "").strip()
SESSION_SIGNING_KEY = (os.getenv("SESSION_SIGNING_KEY") or "").strip()
KIDQUEST_ADULT_SESSION_MAX_AGE = env_int("KIDQUEST_ADULT_SESSION_MAX_AGE", 15 * 60)
MIN_SESSION_SIGNING_KEY_BYTES = 32


def get_db_path() -> str:
    """Resolve DB_PATH when a connection opens, so tests can point at a temporary database."""
    return os.getenv("DB_PATH", DEFAULT_DB_PATH)


def validate_startup_config(environ=os.environ) -> None:
    """Refuse to serve production traffic with the legacy admin password.

    Called by create_app() only, so migrations and the Docker build never need the secret.
    """
    production = is_production(environ)
    if production:
        password = (environ.get("ADMIN_CLEAR_PASSWORD") or "").strip()
        if not password or password == LEGACY_ADMIN_CLEAR_PASSWORD:
            raise ConfigError(
                "ADMIN_CLEAR_PASSWORD is unset or still the legacy default. Production (a RAILWAY_ENVIRONMENT* "
                "variable is set) requires a strong secret: set ADMIN_CLEAR_PASSWORD in the Railway service "
                "variables and redeploy."
            )

    dashboard_enabled = env_flag(
        "KIDQUEST_PARENT_DASHBOARD_ENABLED", KIDQUEST_PARENT_DASHBOARD_ENABLED, environ=environ
    )
    if not dashboard_enabled:
        return

    # Imported lazily to keep configuration parsing independent of the service layer.
    from app.services.parent_auth_service import is_valid_pin_hash

    pin_hash = (environ.get("PARENT_PIN_HASH") if "PARENT_PIN_HASH" in environ else PARENT_PIN_HASH) or ""
    signing_key = (environ.get("SESSION_SIGNING_KEY") if "SESSION_SIGNING_KEY" in environ else SESSION_SIGNING_KEY) or ""
    pin_hash, signing_key = pin_hash.strip(), signing_key.strip()
    if pin_hash and not is_valid_pin_hash(pin_hash):
        raise ConfigError(
            "PARENT_PIN_HASH is malformed or below the supported PBKDF2 strength. "
            "Generate it with PYTHONPATH=. .venv/bin/python scripts/hash_parent_pin.py."
        )
    if production and (not pin_hash or len(signing_key.encode("utf-8")) < MIN_SESSION_SIGNING_KEY_BYTES):
        raise ConfigError(
            "KIDQUEST_PARENT_DASHBOARD_ENABLED=true requires PARENT_PIN_HASH and a "
            f"SESSION_SIGNING_KEY of at least {MIN_SESSION_SIGNING_KEY_BYTES} bytes in production. "
            "Set both Railway service variables and redeploy."
        )


def adult_dashboard_ready() -> bool:
    """Whether the adult router may be registered for this process."""
    if not KIDQUEST_PARENT_DASHBOARD_ENABLED:
        return False
    from app.services.parent_auth_service import is_valid_pin_hash

    return (
        is_valid_pin_hash(PARENT_PIN_HASH)
        and len(SESSION_SIGNING_KEY.encode("utf-8")) >= MIN_SESSION_SIGNING_KEY_BYTES
    )
