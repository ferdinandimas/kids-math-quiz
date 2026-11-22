"""Fixtures and helpers for the KidQuest HTTP API tests (KQ-007 onward)."""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import create_app
from tests.support import DEFAULT_DAY, LEGACY_TABLES, execute, query, select_child

STATE_URL = "/api/kidquest/state"
THEMES_URL = "/api/kidquest/themes"
THEME_URL = "/api/kidquest/theme"
# Every KidQuest route and method; the only path parameters are content/entity IDs, never a child.
PAGE_URL = "/kidquest"
KIDQUEST_ROUTES = {
    (PAGE_URL, ("GET",)),
    ("/api/kidquest/state", ("GET",)),
    ("/api/kidquest/themes", ("GET",)),
    ("/api/kidquest/theme", ("PATCH",)),
    ("/api/kidquest/quests/{quest_id}/start", ("POST",)),
    ("/api/kidquest/quests/{quest_id}/challenge", ("POST",)),
    ("/api/kidquest/challenges/{challenge_id}/answers", ("POST",)),
    ("/api/kidquest/buildings/preview", ("GET",)),
    ("/api/kidquest/buildings", ("POST",)),
}
BUILDINGS_URL = "/api/kidquest/buildings"
PREVIEW_URL = "/api/kidquest/buildings/preview"
# pulau_tunas_v1: the 2x2 house fits the tutorial zone (x 1-4, y 1-2) only at these top-left cells.
VALID_HOUSE_ORIGINS = [(1, 1), (2, 1), (3, 1)]

# Logical player state. kidquest_idempotency is bookkeeping and is checked separately.
LOGICAL_TABLES = (
    "kidquest_worlds",
    "kidquest_buildings",
    "kidquest_paths",
    "kidquest_child_quests",
    "kidquest_challenges",
    "kidquest_attempts",
    "kidquest_resource_balances",
    "kidquest_resource_ledger",
    "kidquest_blueprints",
    "kidquest_daily_usage",
)
# The only world columns a theme change may write (PRD 14.3, AC-13).
THEME_COLUMNS = ("theme_id", "version", "updated_at")


@pytest.fixture
def kidquest_on(monkeypatch):
    monkeypatch.setattr(config, "KIDQUEST_ENABLED", True)
    monkeypatch.setattr(config, "KIDQUEST_PROFILE_ALLOWLIST", ("alleia", "althafandra"))


@pytest.fixture
def kq_app(db_path, clock, seeded_random, kidquest_on):
    return create_app()


@pytest.fixture
def kid_client(kq_app):
    """A browser for one child: the child is selected the legacy way, through GET /home/{child}."""

    def make(child: str | None = None) -> TestClient:
        client = TestClient(kq_app)
        if child:
            select_child(client, child)
        return client

    return make


def change_theme(client: TestClient, theme_id: str, world_version: int, key: str, manifest_version: int = 1):
    return client.patch(
        THEME_URL,
        json={"theme_id": theme_id, "world_version": world_version, "manifest_version": manifest_version},
        headers={"Idempotency-Key": key},
    )


def start_quest(client: TestClient, key: str, quest_id: str = "Q001"):
    return client.post(f"/api/kidquest/quests/{quest_id}/start", headers={"Idempotency-Key": key})


def open_challenge(client: TestClient, key: str, quest_id: str = "Q001"):
    return client.post(f"/api/kidquest/quests/{quest_id}/challenge", headers={"Idempotency-Key": key})


def answer(client: TestClient, challenge_id: str, value: str, key: str, hint_count: int = 0):
    return client.post(
        f"/api/kidquest/challenges/{challenge_id}/answers",
        json={"answer": value, "hint_count": hint_count},
        headers={"Idempotency-Key": key},
    )


def active_challenge_id(client: TestClient) -> str:
    """Start Q001 and return its challenge ID."""
    response = open_challenge(client, f"open-{id(client)}")
    assert response.status_code == 200, response.text
    return response.json()["challenge"]["id"]


def place(client: TestClient, x: int, y: int, world_version: int, key: str, building_type: str = "starter_house", **extra):
    return client.post(
        BUILDINGS_URL,
        json={"building_type": building_type, "x": x, "y": y, "rotation": 0, "world_version": world_version, **extra},
        headers={"Idempotency-Key": key},
    )


def world_version(client: TestClient) -> int:
    return client.get(STATE_URL).json()["world"]["version"]


def seed_ready_to_build(child: str, wood: int = 4) -> None:
    """Q001 answered: READY_TO_BUILD, the reward wood, and the blueprint (as KQ-008 writes them). World must exist."""
    now = "2026-11-21T09:30:00"
    execute("UPDATE kidquest_child_quests SET status = 'READY_TO_BUILD' WHERE child = ? AND quest_id = 'Q001'", (child,))
    execute("INSERT INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at) "
            "VALUES (?, 'wood', 4, 'quest_reward', 'Q001', ?)", (child, now))
    execute("INSERT INTO kidquest_resource_balances VALUES (?, 'wood', ?, ?)", (child, wood, now))
    execute("INSERT INTO kidquest_blueprints VALUES (?, 'starter_house', 'quest_reward', 'Q001', 1, ?)", (child, now))


def error_code(response) -> str:
    body = response.json()
    assert body["ok"] is False and set(body["error"]) >= {"code", "message"}, body
    return body["error"]["code"]


def table_rows(table: str, child: str | None = None) -> list[dict]:
    where = " WHERE child = ?" if child else ""
    rows = query(f"SELECT * FROM {table}{where}", (child,) if child else ())
    return sorted(rows, key=lambda row: repr(sorted(row.items())))


def snapshot(child: str) -> dict[str, list[dict]]:
    """Every logical KidQuest row of one child."""
    return {table: table_rows(table, child) for table in LOGICAL_TABLES}


def without_theme_columns(snap: dict[str, list[dict]]) -> dict[str, list[dict]]:
    worlds = [{k: v for k, v in row.items() if k not in THEME_COLUMNS} for row in snap["kidquest_worlds"]]
    return {**snap, "kidquest_worlds": worlds}


def legacy_snapshot() -> dict[str, list[dict]]:
    return {table: table_rows(table) for table in LEGACY_TABLES}


def all_kidquest_counts() -> dict[str, int]:
    tables = (*LOGICAL_TABLES, "kidquest_idempotency")
    return {table: query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"] for table in tables}


def seed_progress(child: str) -> None:
    """Give an existing world non-trivial state in every logical table (written directly; KQ-008/009 own the flows)."""
    now = "2026-11-21T09:00:00"
    statements = [
        ("UPDATE kidquest_child_quests SET status = 'COMPLETED', progress_json = '{\"answered\": true}' WHERE child = ? AND quest_id = 'Q001'", (child,)),
        ("UPDATE kidquest_child_quests SET status = 'IN_PROGRESS' WHERE child = ? AND quest_id = 'Q002'", (child,)),
        ("INSERT INTO kidquest_challenges VALUES (?, ?, 'Q001', 1, 'Q001#challenge', 'COMPLETED', ?, ?, NULL)", (f"ch_{child}_1", child, now, now)),
        ("INSERT INTO kidquest_challenges VALUES (?, ?, 'Q002', 1, 'Q002#challenge', 'ACTIVE', ?, NULL, NULL)", (f"ch_{child}_2", child, now)),
        ("INSERT INTO kidquest_attempts(child, attempt_key, challenge_id, skill_id, content_version, is_correct, hint_count, attempted_at) "
         "VALUES (?, 'k1', ?, 'SUB_BASIC', 1, 0, 1, ?)", (child, f"ch_{child}_1", now)),
        ("INSERT INTO kidquest_attempts(child, attempt_key, challenge_id, skill_id, content_version, is_correct, hint_count, attempted_at) "
         "VALUES (?, 'k2', ?, 'SUB_BASIC', 1, 1, 1, ?)", (child, f"ch_{child}_1", now)),
        ("INSERT INTO kidquest_attempts(child, attempt_key, challenge_id, skill_id, content_version, is_correct, hint_count, attempted_at) "
         "VALUES (?, 'k3', ?, 'COUNT_GROUPS', 1, 0, 0, ?)", (child, f"ch_{child}_2", now)),
        ("INSERT INTO kidquest_daily_usage VALUES (?, ?, 3, ?)", (child, DEFAULT_DAY, now)),
        ("INSERT INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at) VALUES (?, 'wood', 4, 'quest_reward', 'Q001', ?)", (child, now)),
        ("INSERT INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at) VALUES (?, 'wood', -4, 'placement', 'starter_house', ?)", (child, now)),
        ("INSERT INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at) VALUES (?, 'wood', 3, 'test_grant', 'seed', ?)", (child, now)),
        ("INSERT INTO kidquest_resource_ledger(child, resource_type, delta, source_type, source_ref, created_at) VALUES (?, 'stone', 1, 'test_grant', 'seed', ?)", (child, now)),
        ("INSERT INTO kidquest_resource_balances VALUES (?, 'wood', 3, ?)", (child, now)),
        ("INSERT INTO kidquest_resource_balances VALUES (?, 'stone', 1, ?)", (child, now)),
        ("INSERT INTO kidquest_blueprints VALUES (?, 'starter_house', 'quest_reward', 'Q001', 1, ?)", (child, now)),
        ("INSERT INTO kidquest_buildings(child, type, x, y, rotation, placed_at, updated_at) VALUES (?, 'starter_house', 1, 1, 0, ?, ?)", (child, now, now)),
        ("INSERT INTO kidquest_paths(child, x, y, path_type, created_at) VALUES (?, 1, 3, 'basic_road', ?)", (child, now)),
        ("INSERT INTO kidquest_paths(child, x, y, path_type, created_at) VALUES (?, 2, 3, 'basic_road', ?)", (child, now)),
        ("INSERT INTO kidquest_paths(child, x, y, path_type, created_at) VALUES (?, 3, 3, 'basic_road', ?)", (child, now)),
    ]
    for sql, params in statements:
        execute(sql, params)
