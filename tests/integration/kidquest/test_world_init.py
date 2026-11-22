"""World initialization is idempotent and isolated by child; KidQuest config and startup hook."""

import os
import subprocess
import sys

import pytest

from app import config
from app.db.kidquest_repo import KidQuestRepo
from app.db.sqlite import transaction
from app.domain.kidquest.content import Catalog, ContentError, load_catalog
from app.main import create_app
from tests.conftest import REPO_ROOT

NOW = "2026-11-21T10:00:00"


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
def repo(app):  # `app` migrates the temporary database.
    return KidQuestRepo()


def test_first_initialization_creates_the_starter_world(repo, catalog):
    with transaction() as conn:
        created = repo.initialize_world_in(conn, "alleia", catalog, NOW)
        world = repo.get_world_in(conn, "alleia")
        statuses = repo.get_quest_statuses_in(conn, "alleia")

    assert created is True
    assert {k: world[k] for k in ("child", "layout_version", "theme_id", "theme_manifest_version", "width", "height", "version")} == {
        "child": "alleia", "layout_version": "pulau_tunas_v1", "theme_id": "perkampungan",
        "theme_manifest_version": 1, "width": 8, "height": 8, "version": 1,
    }
    assert statuses == {"Q001": "AVAILABLE", "Q002": "LOCKED", "Q003": "LOCKED", "Q004": "LOCKED", "Q005": "LOCKED", "Q006": "LOCKED"}


def test_initialization_is_idempotent(repo, catalog):
    with transaction() as conn:
        repo.initialize_world_in(conn, "alleia", catalog, NOW)
        conn.execute("UPDATE kidquest_worlds SET theme_id = 'city', version = 2")
        conn.execute("UPDATE kidquest_child_quests SET status = 'IN_PROGRESS' WHERE quest_id = 'Q001'")
    with transaction() as conn:
        again = repo.initialize_world_in(conn, "alleia", catalog, "2026-11-22T08:00:00")
        world = repo.get_world_in(conn, "alleia")
        quest_rows = conn.execute("SELECT COUNT(*) FROM kidquest_child_quests").fetchone()[0]

    assert again is False
    assert (world["theme_id"], world["version"], world["created_at"]) == ("city", 2, NOW)
    assert quest_rows == 6
    with transaction() as conn:
        assert repo.get_quest_statuses_in(conn, "alleia")["Q001"] == "IN_PROGRESS"


def test_worlds_are_isolated_by_child(repo, catalog):
    with transaction() as conn:
        repo.initialize_world_in(conn, "alleia", catalog, NOW)
        conn.execute("UPDATE kidquest_worlds SET theme_id = 'kingdom' WHERE child = 'alleia'")
        repo.initialize_world_in(conn, "althafandra", catalog, NOW)
        worlds = {row[0]: row[1] for row in conn.execute("SELECT child, theme_id FROM kidquest_worlds")}
        per_child = dict(conn.execute("SELECT child, COUNT(*) FROM kidquest_child_quests GROUP BY child").fetchall())

    assert worlds == {"alleia": "kingdom", "althafandra": "perkampungan"}
    assert per_child == {"alleia": 6, "althafandra": 6}


def test_unknown_children_get_no_world(repo, catalog):
    with pytest.raises(ValueError, match="Unknown child 'mallory'"):
        with transaction() as conn:
            repo.initialize_world_in(conn, "mallory", catalog, NOW)


# --- Config ---------------------------------------------------------------------------------------


def test_kidquest_config_defaults():
    assert config.KIDQUEST_ENABLED is False
    assert config.KIDQUEST_PROFILE_ALLOWLIST == ()
    assert config.KIDQUEST_DAILY_ATTEMPT_LIMIT == 20


def test_profile_allowlist_parsing():
    assert config.env_profiles("L", {"L": " Alleia, althafandra ,alleia,, "}) == ("alleia", "althafandra")
    assert config.env_profiles("L", {}) == ()
    with pytest.raises(config.ConfigError, match="L lists unknown child ID\\(s\\) mallory; use only althafandra, alleia"):
        config.env_profiles("L", {"L": "alleia,mallory"})


@pytest.mark.parametrize(
    "env, expected",
    [
        ({"KIDQUEST_ENABLED": "true", "KIDQUEST_PROFILE_ALLOWLIST": "alleia", "KIDQUEST_DAILY_ATTEMPT_LIMIT": "5"},
         "True ('alleia',) 5"),
        ({}, "False () 20"),
    ],
)
def test_kidquest_environment_variables(tmp_path, env, expected):
    base = {k: v for k, v in os.environ.items() if not k.startswith("KIDQUEST_")}
    result = subprocess.run(
        [sys.executable, "-c", "import app.config as c; print(c.KIDQUEST_ENABLED, c.KIDQUEST_PROFILE_ALLOWLIST, c.KIDQUEST_DAILY_ATTEMPT_LIMIT)"],
        cwd=tmp_path, env={**base, **env, "PYTHONPATH": str(REPO_ROOT)}, capture_output=True, text=True, check=True,
    )

    assert result.stdout.strip() == expected


# --- Startup hook ----------------------------------------------------------------------------------


def test_content_is_not_loaded_when_kidquest_is_disabled(db_path, clock, monkeypatch):
    def must_not_run():
        raise AssertionError("content loaded while KidQuest is disabled")

    monkeypatch.setattr("app.main.load_kidquest_catalog", must_not_run)

    assert create_app().state.kidquest_catalog is None


def test_valid_content_is_loaded_when_kidquest_is_enabled(db_path, clock, monkeypatch):
    monkeypatch.setattr(config, "KIDQUEST_ENABLED", True)

    assert isinstance(create_app().state.kidquest_catalog, Catalog)


def test_invalid_content_stops_startup_only_when_enabled(db_path, clock, monkeypatch, tmp_path):
    broken = lambda: load_catalog(tmp_path)  # noqa: E731  (an empty directory: every file is missing)
    monkeypatch.setattr("app.main.load_kidquest_catalog", broken)

    assert create_app().state.kidquest_catalog is None  # Disabled: legacy starts.
    monkeypatch.setattr(config, "KIDQUEST_ENABLED", True)
    with pytest.raises(ContentError, match="quests.json: file is missing"):
        create_app()
