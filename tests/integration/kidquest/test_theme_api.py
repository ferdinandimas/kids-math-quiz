"""GET /api/kidquest/themes and PATCH /api/kidquest/theme: metadata, persistence, invariance (AC-13), errors."""

import pytest

from app import clock as app_clock
from app.domain.kidquest.content import load_catalog
from tests.integration.kidquest.conftest import (
    STATE_URL,
    THEMES_URL,
    all_kidquest_counts,
    change_theme,
    error_code,
    legacy_snapshot,
    seed_progress,
    snapshot,
    table_rows,
    without_theme_columns,
)


def logical_view(state: dict) -> dict:
    """A state payload without the fields a theme change may alter."""
    world = {k: v for k, v in state["world"].items() if k not in ("theme_id", "version")}
    rest = {k: v for k, v in state.items() if k not in ("ok", "world", "theme", "theme_id", "world_version")}
    return {"world": world, **rest}


def test_a_new_world_starts_in_kampung_and_offers_three_free_themes(kid_client):
    response = kid_client("alleia").get(THEMES_URL)

    assert response.status_code == 200
    body = response.json()
    assert {k: body[k] for k in ("ok", "manifest_version", "default_theme_id", "current_theme_id", "world_version")} == {
        "ok": True, "manifest_version": 1, "default_theme_id": "perkampungan", "current_theme_id": "perkampungan", "world_version": 1,
    }
    assert [(t["id"], t["name"], t["manifest_version"], t["asset_count"]) for t in body["themes"]] == [
        ("perkampungan", "Kampung Ceria", 1, 56), ("kingdom", "Kerajaan Ceria", 1, 56), ("city", "Kota Ceria", 1, 56),
    ]
    assert body["themes"][1]["thumbnail"] == "/static/images/kidquest/themes/kingdom/icons/theme_thumbnail--base@2x.webp"
    assert body["themes"][2]["labels"]["starter_house"] == "Rumah Warna-Warni"
    assert all("price" not in theme and "cost" not in theme for theme in body["themes"])
    assert all("assets" in theme for theme in body["themes"])
    catalog = load_catalog()
    assert all(set(theme["assets"]) == set(catalog.themes[theme["id"]]["assets"]) for theme in body["themes"])
    current = next(theme for theme in body["themes"] if theme["id"] == body["current_theme_id"])
    assert current["assets"] == kid_client("alleia").get(STATE_URL).json()["theme"]["assets"]
    assert len(response.content) < 32 * 1024


@pytest.mark.parametrize("theme_id", ["kingdom", "city"])
def test_switching_theme_persists_after_refresh(kid_client, theme_id):
    client = kid_client("alleia")
    client.get(STATE_URL)

    response = change_theme(client, theme_id, 1, "switch-key-1")

    assert response.status_code == 200
    body = response.json()
    assert (body["ok"], body["theme_id"], body["world_version"]) == (True, theme_id, 2)
    assert body["world"]["theme_id"] == theme_id and body["theme"]["id"] == theme_id
    refreshed = kid_client("alleia").get(STATE_URL).json()  # A new browser session for the same child.
    assert (refreshed["world"]["theme_id"], refreshed["world"]["version"]) == (theme_id, 2)
    assert client.get(THEMES_URL).json()["current_theme_id"] == theme_id


def test_theme_response_returns_the_unchanged_world(kid_client):
    client = kid_client("alleia")
    client.get(STATE_URL)
    seed_progress("alleia")
    before = client.get(STATE_URL).json()

    body = change_theme(client, "city", 1, "switch-key-1").json()

    assert logical_view(body) == logical_view(before)
    assert body["theme"]["labels"]["starter_house"] == "Rumah Warna-Warni"
    assert all("/themes/city/" in path for path in body["theme"]["assets"].values())


# --- AC-13 theme invariance, AC-07 isolation --------------------------------------------------


def test_switching_through_every_theme_changes_only_theme_version_and_timestamp(kid_client, clock):
    alleia, altha = kid_client("alleia"), kid_client("althafandra")
    alleia.get(STATE_URL)
    altha.get(STATE_URL)
    seed_progress("alleia")
    seed_progress("althafandra")
    before, other_before, legacy_before = snapshot("alleia"), snapshot("althafandra"), legacy_snapshot()
    api_before = alleia.get(STATE_URL).json()

    version = 1
    for step, theme_id in enumerate(["kingdom", "city", "perkampungan"], start=1):
        clock.advance(minutes=5)
        response = change_theme(alleia, theme_id, version, f"tour-key-{step}")
        assert response.status_code == 200, response.text
        version += 1

        after = snapshot("alleia")
        world = after["kidquest_worlds"][0]
        assert (world["theme_id"], world["version"], world["updated_at"]) == (theme_id, version, app_clock.now_str())
        assert without_theme_columns(after) == without_theme_columns(before)  # Every other column of every table.
        refreshed = alleia.get(STATE_URL).json()
        assert refreshed["world"]["theme_id"] == theme_id
        assert logical_view(refreshed) == logical_view(api_before)

    assert snapshot("althafandra") == other_before
    assert legacy_snapshot() == legacy_before
    assert [row["key"] for row in table_rows("kidquest_idempotency", "alleia")] == ["tour-key-1", "tour-key-2", "tour-key-3"]
    assert table_rows("kidquest_idempotency", "althafandra") == []


def test_choosing_the_current_theme_changes_nothing(kid_client):
    client = kid_client("alleia")
    client.get(STATE_URL)
    before = snapshot("alleia")

    response = change_theme(client, "perkampungan", 1, "same-theme-1")

    assert response.status_code == 200
    assert (response.json()["theme_id"], response.json()["world_version"]) == ("perkampungan", 1)
    assert snapshot("alleia") == before


# --- Idempotency -------------------------------------------------------------------------------


def test_same_key_and_body_replays_the_identical_response_without_a_second_bump(kid_client, clock):
    client = kid_client("alleia")
    client.get(STATE_URL)
    first = change_theme(client, "kingdom", 1, "replay-key-1")
    after_first = snapshot("alleia")

    clock.advance(minutes=1)
    replays = [change_theme(client, "kingdom", 1, "replay-key-1") for _ in range(2)]
    # The same logical body with keys in another order is the same request.
    reordered = client.patch("/api/kidquest/theme", content=b'{"manifest_version":1,"world_version":1,"theme_id":"kingdom"}',
                             headers={"Idempotency-Key": "replay-key-1", "Content-Type": "application/json"})

    assert first.status_code == 200
    for replay in (*replays, reordered):
        assert (replay.status_code, replay.content) == (200, first.content)
    assert snapshot("alleia") == after_first
    assert after_first["kidquest_worlds"][0]["version"] == 2
    assert len(table_rows("kidquest_idempotency")) == 1


def test_a_replay_returns_the_original_response_even_after_later_changes(kid_client):
    client = kid_client("alleia")
    client.get(STATE_URL)
    first = change_theme(client, "kingdom", 1, "replay-key-1")
    change_theme(client, "city", 2, "replay-key-2")

    replay = change_theme(client, "kingdom", 1, "replay-key-1")

    assert replay.content == first.content
    assert client.get(STATE_URL).json()["world"]["theme_id"] == "city"


def test_same_key_with_a_different_body_is_a_conflict_without_mutation(kid_client):
    client = kid_client("alleia")
    client.get(STATE_URL)
    change_theme(client, "kingdom", 1, "conflict-key-1")
    before, counts = snapshot("alleia"), all_kidquest_counts()

    response = change_theme(client, "city", 2, "conflict-key-1")

    assert response.status_code == 409 and error_code(response) == "IDEMPOTENCY_CONFLICT"
    assert snapshot("alleia") == before and all_kidquest_counts() == counts


def test_keys_are_scoped_to_one_child(kid_client):
    alleia, altha = kid_client("alleia"), kid_client("althafandra")

    first = change_theme(alleia, "kingdom", 1, "shared-key-1")
    second = change_theme(altha, "city", 1, "shared-key-1")

    assert (first.status_code, second.status_code) == (200, 200)
    assert {row["child"]: row["theme_id"] for row in table_rows("kidquest_worlds")} == {"alleia": "kingdom", "althafandra": "city"}


# --- Errors --------------------------------------------------------------------------------------


def test_stale_world_version_is_a_refreshable_conflict(kid_client):
    client = kid_client("alleia")
    client.get(STATE_URL)
    change_theme(client, "kingdom", 1, "stale-key-1")
    before, counts = snapshot("alleia"), all_kidquest_counts()

    stale = change_theme(client, "city", 1, "stale-key-2")

    assert stale.status_code == 409 and error_code(stale) == "WORLD_VERSION_CONFLICT"
    assert stale.json()["error"]["world_version"] == 2  # Refresh target.
    assert snapshot("alleia") == before
    # The outcome is stored with its key, so a retry replays it; a new key with the fresh version works.
    assert change_theme(client, "city", 1, "stale-key-2").content == stale.content
    assert all_kidquest_counts()["kidquest_idempotency"] == counts["kidquest_idempotency"] + 1
    assert change_theme(client, "city", 2, "stale-key-3").json()["world_version"] == 3


@pytest.mark.parametrize("theme_id, manifest_version", [("space", 1), ("Kingdom", 1), ("", 1), ("kingdom", 2)])
def test_unknown_theme_or_manifest_is_rejected_without_mutation(kid_client, theme_id, manifest_version):
    client = kid_client("alleia")
    client.get(STATE_URL)
    before = snapshot("alleia")

    response = change_theme(client, theme_id, 1, "bad-theme-1", manifest_version=manifest_version)

    if theme_id == "":
        assert response.status_code == 400 and error_code(response) == "INVALID_REQUEST"
    else:
        assert response.status_code == 422 and error_code(response) == "INVALID_THEME"
        assert response.json()["error"]["manifest_version"] == 1
    assert snapshot("alleia") == before


@pytest.mark.parametrize(
    "headers",
    [{}, {"Idempotency-Key": ""}, {"Idempotency-Key": "short"}, {"Idempotency-Key": "k" * 129},
     {"Idempotency-Key": "has spaces in it"}, {"Idempotency-Key": "semi;colon-key"}],
)
def test_idempotency_key_is_required_and_limited(kid_client, headers):
    client = kid_client("alleia")
    client.get(STATE_URL)
    before, counts = snapshot("alleia"), all_kidquest_counts()

    response = client.patch("/api/kidquest/theme", json={"theme_id": "kingdom", "world_version": 1, "manifest_version": 1}, headers=headers)

    assert response.status_code == 400 and error_code(response) == "INVALID_REQUEST"
    assert response.json()["error"]["fields"] == ["Idempotency-Key"]
    assert snapshot("alleia") == before and all_kidquest_counts() == counts


def test_longest_allowed_idempotency_key_works(kid_client):
    response = change_theme(kid_client("alleia"), "kingdom", 1, "K" * 128)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "body, fields",
    [
        ({"theme_id": "kingdom", "world_version": 1, "manifest_version": 1, "child": "althafandra"}, ["child"]),
        ({"theme_id": "kingdom", "world_version": 1}, ["manifest_version"]),
        ({"theme_id": "kingdom", "world_version": "1", "manifest_version": 1}, ["world_version"]),
        ({"theme_id": "kingdom", "world_version": True, "manifest_version": 1}, ["world_version"]),
        ({"theme_id": "kingdom", "world_version": 0, "manifest_version": 1}, ["world_version"]),
        ({"theme_id": "kingdom", "world_version": 1.5, "manifest_version": 1}, ["world_version"]),
        ({"theme_id": 7, "world_version": 1, "manifest_version": 1}, ["theme_id"]),
        ({"theme_id": "k" * 33, "world_version": 1, "manifest_version": 1}, ["theme_id"]),
        (["kingdom"], ["body"]),
    ],
)
def test_malformed_bodies_are_rejected_without_mutation(kid_client, body, fields):
    client = kid_client("alleia")
    client.get(STATE_URL)
    before, counts = snapshot("alleia"), all_kidquest_counts()

    response = client.patch("/api/kidquest/theme", json=body, headers={"Idempotency-Key": "body-key-1"})

    assert response.status_code == 400 and error_code(response) == "INVALID_REQUEST"
    assert response.json()["error"]["fields"] == fields
    assert snapshot("alleia") == before and all_kidquest_counts() == counts


def test_non_json_body_is_rejected(kid_client):
    client = kid_client("alleia")

    response = client.patch("/api/kidquest/theme", content=b"theme=kingdom", headers={"Idempotency-Key": "body-key-1"})

    assert response.status_code == 400 and error_code(response) == "INVALID_REQUEST"
    assert table_rows("kidquest_worlds") == []
