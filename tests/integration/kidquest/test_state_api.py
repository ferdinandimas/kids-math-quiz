"""GET /api/kidquest/state: idempotent world creation, contract, asset resolution, and child isolation."""

from fastapi.routing import APIRoute

from tests.integration.kidquest.conftest import (
    KIDQUEST_ROUTES,
    STATE_URL,
    THEMES_URL,
    legacy_snapshot,
    seed_progress,
    snapshot,
    table_rows,
)

TOP_LEVEL_KEYS = ["ok", "world", "theme", "buildings", "paths", "inventory", "quests", "active_challenge", "daily_attempts",
                  "next_action"]


def asset_ids(value) -> set[str]:
    """Every `asset_id` anywhere in a payload."""
    if isinstance(value, dict):
        found = {value["asset_id"]} if "asset_id" in value else set()
        if "ground_asset_id" in value:
            found.add(value["ground_asset_id"])
        return found.union(*(asset_ids(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(asset_ids(item) for item in value))
    return set()


def test_first_read_creates_exactly_one_starter_world(kid_client):
    client = kid_client("alleia")

    response = client.get(STATE_URL)

    assert response.status_code == 200
    state = response.json()
    assert list(state) == TOP_LEVEL_KEYS and state["ok"] is True
    assert {k: v for k, v in state["world"].items() if k != "terrain"} == {
        "layout_version": "pulau_tunas_v1", "width": 8, "height": 8, "version": 1,
        "theme_id": "perkampungan", "theme_manifest_version": 1,
    }
    assert state["buildings"] == [] and state["paths"] == []
    assert state["inventory"] == {"resources": {"wood": 0, "stone": 0}, "blueprints": []}
    assert [(q["id"], q["status"], q["building_id"], q["playable"]) for q in state["quests"]] == [
        ("Q001", "AVAILABLE", "starter_house", True), ("Q002", "LOCKED", "garden", False), ("Q003", "LOCKED", "bakery", False),
        ("Q004", "LOCKED", "park", False), ("Q005", "LOCKED", "bridge", False), ("Q006", "LOCKED", "market_stall", False),
    ]
    assert state["quests"][0]["title"] == "Rumah Pertama"
    assert state["active_challenge"] is None
    assert state["next_action"] == {"type": "start_quest", "quest_id": "Q001"}
    assert state["daily_attempts"] == {"day": "2026-11-21", "used": 0, "limit": 20, "remaining": 20,
                                       "resets_at": "2026-11-22T00:00:00+07:00"}
    assert len(table_rows("kidquest_worlds")) == 1
    assert len(table_rows("kidquest_child_quests")) == 6


def test_later_reads_do_not_duplicate_or_change_the_world(kid_client, clock):
    client = kid_client("alleia")
    first = client.get(STATE_URL)
    before = snapshot("alleia")

    clock.advance(days=1)
    again = [client.get(STATE_URL) for _ in range(3)] + [client.get(THEMES_URL)]

    assert all(response.status_code == 200 for response in again)
    unchanged = [{k: v for k, v in r.json().items() if k != "daily_attempts"} for r in [first, *again[:3]]]
    assert all(view == unchanged[0] for view in unchanged)
    assert again[0].json()["daily_attempts"]["day"] == "2026-11-22"  # Only the Jakarta day moved on.
    assert snapshot("alleia") == before
    assert len(table_rows("kidquest_worlds")) == 1


def test_terrain_is_the_logical_layout(kid_client):
    terrain = kid_client("alleia").get(STATE_URL).json()["world"]["terrain"]

    assert terrain["ground_asset_id"] == "ground_buildable--base"
    assert len(terrain["water"]) == 12
    assert {"x": 5, "y": 4, "shore_mask": 1, "asset_id": "shore--mask_01"} in terrain["water"]  # Bridge end: land to the north.
    assert {"x": 3, "y": 4, "shore_mask": 9, "asset_id": "shore--mask_09"} in terrain["water"]  # Land to the north and west.
    assert [(o["id"], o["kind"], o["x"], o["y"], o["asset_id"]) for o in terrain["fixed_objects"]] == [
        ("tree_north_west", "blocked_tree", 0, 0, "blocked_tree--base"),
        ("tree_north_east", "blocked_tree", 7, 0, "blocked_tree--base"),
        ("quest_board", "quest_board", 4, 3, "quest_board--base"),
        ("rock_south_west", "blocked_rock", 0, 7, "blocked_rock--base"),
        ("tree_south_east", "blocked_tree", 7, 7, "blocked_tree--base"),
    ]
    assert terrain["zones"] == [
        {"id": "tutorial_zone", "x": 1, "y": 1, "width": 4, "height": 2, "unlocked_by_quest": None},
        {"id": "bridge_zone", "x": 5, "y": 4, "width": 1, "height": 2, "unlocked_by_quest": None},
        {"id": "expansion_zone", "x": 4, "y": 6, "width": 4, "height": 2, "unlocked_by_quest": "Q005"},
    ]


def test_state_reports_existing_progress_with_logical_ids(kid_client):
    client = kid_client("alleia")
    client.get(STATE_URL)
    seed_progress("alleia")

    state = client.get(STATE_URL).json()

    assert [{k: b[k] for k in ("type", "x", "y", "rotation", "width", "height", "entrances", "asset_id")} for b in state["buildings"]] == [
        {"type": "starter_house", "x": 1, "y": 1, "rotation": 0, "width": 2, "height": 2, "entrances": ["S"], "asset_id": "starter_house--base"}
    ]
    # Masks are derived from neighbours: an east end cap, a straight, and a west end cap.
    assert [(p["x"], p["y"], p["path_type"], p["mask"], p["asset_id"]) for p in state["paths"]] == [
        (1, 3, "basic_road", 2, "road_basic--mask_02"),
        (2, 3, "basic_road", 10, "road_basic--mask_10"),
        (3, 3, "basic_road", 8, "road_basic--mask_08"),
    ]
    assert state["inventory"] == {"resources": {"wood": 3, "stone": 1}, "blueprints": ["starter_house"]}
    assert state["quests"][0]["status"] == "COMPLETED" and state["quests"][1]["status"] == "IN_PROGRESS"
    assert state["active_challenge"] == {"id": "ch_alleia_2", "quest_id": "Q002", "attempt_count": 1}


def test_every_entity_asset_resolves_in_the_selected_theme(kid_client):
    client = kid_client("alleia")
    client.get(STATE_URL)
    seed_progress("alleia")

    state = client.get(STATE_URL).json()
    theme = state["theme"]

    assert theme["id"] == "perkampungan" and theme["name"] == "Kampung Ceria" and theme["manifest_version"] == 1
    assert len(theme["assets"]) == 56
    used = asset_ids({k: v for k, v in state.items() if k != "theme"})
    assert used and used <= set(theme["assets"])
    assert all(path == f"/static/images/kidquest/themes/perkampungan/{path.split('/')[-2]}/{asset}@2x.webp"
               for asset, path in theme["assets"].items())
    assert theme["labels"]["starter_house"] == "Rumah Kampung"


def test_art_reference_names_are_never_sent_to_a_child(kid_client):
    client = kid_client("alleia")
    payloads = [client.get(STATE_URL).text, client.get(THEMES_URL).text]

    for text in payloads:
        assert "art_reference" not in text
        for english in ("Keeper's Cottage", "Herald Board", "Colorful Townhouse", "Civic Kiosk", "City Park"):
            assert english not in text


# --- Child isolation (AC-07) ---------------------------------------------------------------------


def test_each_session_reads_only_its_own_childs_world(kid_client):
    alleia, altha = kid_client("alleia"), kid_client("althafandra")
    alleia.get(STATE_URL)
    seed_progress("alleia")

    altha_state = altha.get(STATE_URL).json()

    assert altha_state["buildings"] == [] and altha_state["inventory"]["resources"] == {"wood": 0, "stone": 0}
    assert alleia.get(STATE_URL).json()["inventory"]["resources"] == {"wood": 3, "stone": 1}
    assert [row["child"] for row in table_rows("kidquest_worlds")] == ["alleia", "althafandra"]


def test_a_child_id_in_the_request_is_ignored(kid_client):
    alleia = kid_client("alleia")
    alleia.get(STATE_URL)
    seed_progress("alleia")

    for response in (
        alleia.get(STATE_URL, params={"child": "althafandra"}),
        alleia.get(STATE_URL, headers={"X-Child": "althafandra", "Child": "althafandra"}),
        alleia.get(THEMES_URL, params={"child": "althafandra"}),
    ):
        assert response.status_code == 200
    state = alleia.get(STATE_URL, params={"child": "althafandra"}).json()

    assert state["inventory"]["resources"] == {"wood": 3, "stone": 1}  # Still alleia's world.
    assert [row["child"] for row in table_rows("kidquest_worlds")] == ["alleia"]  # No world created for the other child.


def test_no_kidquest_route_takes_a_child_parameter(kq_app):
    routes = [route for route in kq_app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/kidquest")]

    assert {(route.path, tuple(sorted(route.methods))) for route in routes} == {r for r in KIDQUEST_ROUTES if r[0].startswith("/api/")}
    path_params = {param.name for route in routes for param in route.dependant.path_params}
    query_params = {param.name for route in routes for param in route.dependant.query_params}
    assert path_params == {"quest_id", "challenge_id"} and query_params == set()


def test_reading_state_never_touches_legacy_tables(kid_client, clock):
    client = kid_client("alleia")
    clock.advance(days=1)  # A legacy request would now run the daily session reset.
    before = legacy_snapshot()

    client.get(STATE_URL)
    client.get(THEMES_URL)

    assert legacy_snapshot() == before
