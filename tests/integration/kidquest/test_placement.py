"""Q001 starter-house placement and its read-only preview (PRD 8.2, 9.13, 12.3, 14.2; AC-02, AC-05, AC-06)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.api.kidquest_schemas import PlacementRequest
from app.db.kidquest_repo import KidQuestRepo
from app.services.kidquest_service import KidQuestService
from tests.integration.kidquest.conftest import (
    PREVIEW_URL,
    STATE_URL,
    VALID_HOUSE_ORIGINS,
    active_challenge_id,
    all_kidquest_counts,
    answer,
    change_theme,
    error_code,
    legacy_snapshot,
    place,
    seed_ready_to_build,
    snapshot,
    table_rows,
    world_version,
)
from tests.support import execute

THEMES = ["perkampungan", "kingdom", "city"]


@pytest.fixture
def ready(kid_client):
    """alleia's browser with Q001 answered (READY_TO_BUILD, 4 wood, blueprint); althafandra has a world too."""
    client = kid_client("alleia")
    client.get(STATE_URL)
    kid_client("althafandra").get(STATE_URL)
    seed_ready_to_build("alleia")
    return client


def everything() -> tuple:
    return snapshot("alleia"), snapshot("althafandra"), all_kidquest_counts(), legacy_snapshot()


# --- Success -----------------------------------------------------------------------------------------


def test_the_full_q001_flow_ends_with_one_house_and_a_completed_quest(kid_client):
    client = kid_client("alleia")
    challenge_id = active_challenge_id(client)
    answer(client, challenge_id, "5", "flow-answer-1")
    answer(client, challenge_id, "4", "flow-answer-2")
    version = world_version(client)
    assert client.get(PREVIEW_URL, params={"building_type": "starter_house", "x": 2, "y": 1}).json()["valid"] is True

    response = place(client, 2, 1, version, "flow-place-1")

    assert response.status_code == 200
    body = response.json()
    assert body["building"] == {"id": body["building"]["id"], "type": "starter_house", "x": 2, "y": 1, "rotation": 0,
                                "width": 2, "height": 2, "entrances": ["S"], "asset_id": "starter_house--base"}
    assert (body["spent"], body["world_version"]) == ({"wood": 4}, version + 1)
    assert body["quest"]["status"] == "COMPLETED" and body["next_action"] == {"type": "none"}
    assert body["inventory"] == {"resources": {"wood": 0, "stone": 0}, "blueprints": ["starter_house"]}

    state = client.get(STATE_URL).json()
    assert state["buildings"] == [body["building"]]
    assert state["quests"][0]["status"] == "COMPLETED" and state["quests"][1]["status"] == "LOCKED"  # No economy: Q002 stays locked.
    assert state["world"]["version"] == version + 1
    assert state["next_action"] == {"type": "none"} and state["active_challenge"] is None
    assert state["inventory"] == body["inventory"]
    ledger = sorted((r["delta"], r["source_type"], r["source_ref"]) for r in table_rows("kidquest_resource_ledger"))
    assert ledger == [(-4, "placement", f"building:{body['building']['id']}"), (4, "quest_reward", "Q001")]


@pytest.mark.parametrize("origin", VALID_HOUSE_ORIGINS)
def test_every_tutorial_position_is_accepted(ready, origin):
    response = place(ready, *origin, 1, "origin-key-1")

    assert response.status_code == 200 and (response.json()["building"]["x"], response.json()["building"]["y"]) == origin


def test_state_points_at_building_once_the_challenge_is_solved(ready):
    assert ready.get(STATE_URL).json()["next_action"] == {"type": "place_building", "quest_id": "Q001", "building_id": "starter_house"}


# --- Every failure changes nothing (AC-06) --------------------------------------------------------


@pytest.mark.parametrize(
    "setup, request_fields, status, code, rule, message",
    [
        (None, {"x": 7, "y": 1}, 422, "INVALID_PLACEMENT", "out_of_bounds", "Pilih tempat di dalam pulau."),
        (None, {"x": -1, "y": 1}, 422, "INVALID_PLACEMENT", "out_of_bounds", "Pilih tempat di dalam pulau."),
        (None, {"x": 1, "y": 7}, 422, "INVALID_PLACEMENT", "out_of_bounds", "Pilih tempat di dalam pulau."),
        (None, {"x": 3, "y": 2}, 422, "INVALID_PLACEMENT", "blocked", "Ada pohon, batu, atau papan di sini. Pilih tempat lain."),
        (None, {"x": 6, "y": 0}, 422, "INVALID_PLACEMENT", "blocked", "Ada pohon, batu, atau papan di sini. Pilih tempat lain."),
        (None, {"x": 3, "y": 4}, 422, "INVALID_PLACEMENT", "water", "Tidak bisa membangun di atas air. Pilih tanah."),
        (None, {"x": 1, "y": 3}, 422, "INVALID_PLACEMENT", "outside_zone", "Pilih area kosong di zona rumah."),
        (None, {"x": 5, "y": 1}, 422, "INVALID_PLACEMENT", "outside_zone", "Pilih area kosong di zona rumah."),
        ("garden_at_3_1", {"x": 2, "y": 1}, 422, "INVALID_PLACEMENT", "collision", "Tempat ini sudah terpakai. Pilih area kosong."),
        ("road_at_1_2", {"x": 1, "y": 1}, 422, "INVALID_PLACEMENT", "collision", "Tempat ini sudah terpakai. Pilih area kosong."),
        (None, {"x": 1, "y": 1, "rotation": 90}, 422, "INVALID_PLACEMENT", "rotation", "Bangunan ini tidak bisa diputar."),
        ("no_blueprint", {"x": 1, "y": 1}, 422, "INVALID_PLACEMENT", "missing_blueprint", "Kamu belum punya cetak biru Rumah."),
        ("three_wood", {"x": 1, "y": 1}, 422, "INSUFFICIENT_RESOURCES", "insufficient_resources",
         "Bahanmu belum cukup: butuh 4 kayu, kamu punya 3."),
        ("not_ready", {"x": 1, "y": 1}, 422, "INVALID_PLACEMENT", "quest_not_ready", "Selesaikan tantangan misinya dulu, lalu bangun Rumah."),
        (None, {"x": 1, "y": 1, "building_type": "castle"}, 422, "INVALID_PLACEMENT", "unknown_building", "Bangunan ini tidak dikenal."),
        (None, {"x": 1, "y": 1, "building_type": "garden"}, 422, "INVALID_PLACEMENT", "quest_not_ready",
         "Selesaikan tantangan misinya dulu, lalu bangun Kebun."),
        (None, {"x": 1, "y": 1, "world_version": 2}, 409, "WORLD_VERSION_CONFLICT", "world_version",
         "Duniamu baru saja berubah. Muat ulang, lalu coba lagi."),
    ],
)
def test_invalid_placements_change_nothing(ready, setup, request_fields, status, code, rule, message):
    now = "2026-11-21T09:45:00"
    if setup == "garden_at_3_1":
        execute("INSERT INTO kidquest_buildings(child, type, x, y, rotation, placed_at, updated_at) VALUES ('alleia', 'garden', 3, 1, 0, ?, ?)", (now, now))
    elif setup == "road_at_1_2":
        execute("INSERT INTO kidquest_paths(child, x, y, path_type, created_at) VALUES ('alleia', 1, 2, 'basic_road', ?)", (now,))
    elif setup == "no_blueprint":
        execute("DELETE FROM kidquest_blueprints WHERE child = 'alleia'")
    elif setup == "three_wood":
        execute("UPDATE kidquest_resource_balances SET balance = 3 WHERE child = 'alleia'")
    elif setup == "not_ready":
        execute("UPDATE kidquest_child_quests SET status = 'IN_PROGRESS' WHERE child = 'alleia' AND quest_id = 'Q001'")
    fields = {"building_type": "starter_house", "rotation": 0, "world_version": 1, **request_fields}
    before = everything()

    response = ready.post("/api/kidquest/buildings", json=fields, headers={"Idempotency-Key": "invalid-place-1"})

    assert response.status_code == status and error_code(response) == code
    error = response.json()["error"]
    assert (error["rule"], error["message"], error["rules"][0]) == (rule, message, rule)
    if code == "WORLD_VERSION_CONFLICT":
        assert error["world_version"] == 1
    assert everything() == before


def test_all_broken_rules_are_listed(ready):
    execute("UPDATE kidquest_resource_balances SET balance = 0 WHERE child = 'alleia'")

    error = place(ready, 4, 3, 1, "many-rules-1").json()["error"]

    assert error["rules"] == ["blocked", "water", "outside_zone", "insufficient_resources"]


def test_a_second_house_is_refused_by_the_service(ready):
    assert place(ready, 1, 1, 1, "first-house-1").status_code == 200
    execute("UPDATE kidquest_resource_balances SET balance = 8 WHERE child = 'alleia' AND resource_type = 'wood'")
    before = everything()

    response = place(ready, 3, 1, 2, "second-house-1")

    assert response.status_code == 422 and response.json()["error"]["rule"] == "already_built"
    assert response.json()["error"]["message"] == "Rumah sudah dibangun. Setiap bangunan utama hanya boleh satu."
    assert everything() == before


def test_the_database_alone_stops_a_second_house(ready, kq_app, monkeypatch):
    """With every service rule switched off, the partial unique index still refuses a second core building."""
    monkeypatch.setattr("app.services.kidquest_service.placement_problems", lambda *args, **kwargs: [])
    execute("UPDATE kidquest_resource_balances SET balance = 8 WHERE child = 'alleia'")
    service = KidQuestService(kq_app.state.kidquest_catalog)

    service.place_building("alleia", PlacementRequest(building_type="starter_house", x=1, y=1, world_version=1), "db-only-1")
    execute("UPDATE kidquest_child_quests SET status = 'READY_TO_BUILD' WHERE child = 'alleia' AND quest_id = 'Q001'")
    before = everything()

    with pytest.raises(sqlite3.IntegrityError, match="kidquest_buildings.child, kidquest_buildings.type"):
        service.place_building("alleia", PlacementRequest(building_type="starter_house", x=3, y=1, world_version=2), "db-only-2")

    assert everything() == before
    assert len(table_rows("kidquest_buildings")) == 1


def test_a_failure_mid_placement_rolls_everything_back(ready, kq_app):
    before = everything()

    def broken(*args, **kwargs):
        raise RuntimeError("disk full")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(KidQuestRepo, "bump_world_version_in", broken)  # After the building, spend, and quest writes.
        failing = TestClient(kq_app, raise_server_exceptions=False, cookies=ready.cookies)
        assert place(failing, 1, 1, 1, "rollback-place-1").status_code == 500
    assert everything() == before

    assert place(ready, 1, 1, 1, "rollback-place-1").status_code == 200  # Nothing was stored; the key still works.


# --- Idempotency (AC-05) ------------------------------------------------------------------------------


def test_replaying_a_placement_returns_the_same_building_and_spends_once(ready, clock):
    first = place(ready, 2, 1, 1, "replay-place-1")

    clock.advance(minutes=2)
    replays = [place(ready, 2, 1, 1, "replay-place-1") for _ in range(3)]
    change_theme(ready, "kingdom", 2, "replay-theme-1")
    late = place(ready, 2, 1, 1, "replay-place-1")

    for replay in (*replays, late):
        assert (replay.status_code, replay.content) == (200, first.content)
    assert [row["id"] for row in table_rows("kidquest_buildings")] == [first.json()["building"]["id"]]
    assert [row["delta"] for row in table_rows("kidquest_resource_ledger", "alleia") if row["delta"] < 0] == [-4]
    assert table_rows("kidquest_resource_balances", "alleia")[0]["balance"] == 0


def test_reusing_a_placement_key_with_another_request_is_a_conflict(ready):
    place(ready, 2, 1, 1, "conflict-place-1")
    before = everything()

    response = place(ready, 3, 1, 2, "conflict-place-1")

    assert response.status_code == 409 and error_code(response) == "IDEMPOTENCY_CONFLICT"
    assert everything() == before


@pytest.mark.parametrize(
    "body, fields",
    [
        ({"building_type": "starter_house", "x": 1, "y": 1, "rotation": 0}, ["world_version"]),
        ({"building_type": "starter_house", "x": "1", "y": 1, "world_version": 1}, ["x"]),
        ({"building_type": "starter_house", "x": 1.0, "y": 1, "world_version": 1}, ["x"]),
        ({"building_type": "starter_house", "x": 1, "y": 99, "world_version": 1}, ["y"]),
        ({"building_type": "starter_house", "x": 1, "y": 1, "world_version": 1, "child": "althafandra"}, ["child"]),
        ({"x": 1, "y": 1, "world_version": 1}, ["building_type"]),
    ],
)
def test_malformed_placement_requests_are_rejected(ready, body, fields):
    before = everything()

    response = ready.post("/api/kidquest/buildings", json=body, headers={"Idempotency-Key": "bad-place-1"})

    assert response.status_code == 400 and response.json()["error"]["fields"] == fields
    assert everything() == before


def test_placement_requires_an_idempotency_key(ready):
    before = everything()

    response = ready.post("/api/kidquest/buildings", json={"building_type": "starter_house", "x": 1, "y": 1, "world_version": 1})

    assert response.status_code == 400 and response.json()["error"]["fields"] == ["Idempotency-Key"]
    assert everything() == before


def test_a_child_places_only_in_their_own_world(ready, kid_client):
    altha = kid_client("althafandra")
    other_before = snapshot("althafandra")

    refused = place(altha, 1, 1, 1, "altha-place-1")  # althafandra has not solved Q001.
    placed = place(ready, 1, 1, 1, "alleia-place-1")

    assert refused.status_code == 422 and refused.json()["error"]["rule"] == "quest_not_ready"
    assert placed.status_code == 200
    assert snapshot("althafandra") == other_before
    assert [row["child"] for row in table_rows("kidquest_buildings")] == ["alleia"]


# --- Preview -------------------------------------------------------------------------------------------


def test_preview_is_read_only(ready):
    before = everything()

    responses = [ready.get(PREVIEW_URL, params={"building_type": "starter_house", "x": x, "y": y}) for x, y in [(1, 1), (4, 3), (9, 9)]]

    assert [response.status_code for response in responses] == [200, 200, 200]
    valid = responses[0].json()
    assert valid == {"ok": True, "valid": True, "building_type": "starter_house", "x": 1, "y": 1, "rotation": 0,
                     "cells": [[1, 1], [2, 1], [1, 2], [2, 2]], "cost": {"wood": 4}, "problems": [], "world_version": 1}
    assert [p["rule"] for p in responses[1].json()["problems"]] == ["blocked", "water", "outside_zone"]
    assert everything() == before


@pytest.mark.parametrize(
    "params, fields",
    [
        ({"building_type": "starter_house", "x": 1, "y": 1, "child": "althafandra"}, ["child"]),
        ({"building_type": "starter_house", "x": "satu", "y": 1}, ["x"]),
        ({"building_type": "starter_house", "x": 1}, ["y"]),
        ({"x": 1, "y": 1}, ["building_type"]),
    ],
)
def test_preview_rejects_malformed_queries(ready, params, fields):
    response = ready.get(PREVIEW_URL, params=params)

    assert response.status_code == 400 and response.json()["error"]["fields"] == fields


def sweep(client) -> dict:
    """Preview every top-left cell from (-1, -1) to (8, 8)."""
    return {
        (x, y): tuple(p["rule"] for p in client.get(PREVIEW_URL, params={"building_type": "starter_house", "x": x, "y": y}).json()["problems"])
        for x in range(-1, 9) for y in range(-1, 9)
    }


def test_geometry_validation_is_identical_in_every_theme(ready):
    results = {}
    for version, theme_id in enumerate(THEMES[1:] + THEMES[:1], start=1):
        assert change_theme(ready, theme_id, version, f"sweep-theme-{version}").status_code == 200
        results[theme_id] = sweep(ready)

    assert results["perkampungan"] == results["kingdom"] == results["city"]
    assert sorted(cell for cell, rules in results["city"].items() if not rules) == VALID_HOUSE_ORIGINS


@pytest.mark.parametrize("theme_id", THEMES)
def test_a_house_placed_in_any_theme_stays_on_its_cell_through_theme_changes(ready, theme_id):
    version = 1
    if theme_id != "perkampungan":
        version = change_theme(ready, theme_id, 1, "place-theme-0").json()["world_version"]
    placed = place(ready, 3, 1, version, "place-theme-1").json()["building"]
    building_rows = table_rows("kidquest_buildings")

    version += 1
    for step, other in enumerate(t for t in THEMES + THEMES if t != theme_id):
        version = change_theme(ready, other, version, f"tour-theme-{step}").json()["world_version"]
        state = ready.get(STATE_URL).json()
        assert state["buildings"] == [placed]
        assert state["theme"]["assets"][placed["asset_id"]].endswith(f"/themes/{other}/buildings/starter_house--base@2x.webp")

    assert table_rows("kidquest_buildings") == building_rows
