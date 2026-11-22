"""Supported KidQuest visual themes. Themes change presentation only, never logical state."""

# Must match the CHECK constraint on kidquest_worlds.theme_id in Migration 8.
THEME_IDS = ("perkampungan", "kingdom", "city")
DEFAULT_THEME_ID = "perkampungan"


def is_supported_theme(theme_id: str) -> bool:
    return theme_id in THEME_IDS
