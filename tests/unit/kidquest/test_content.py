"""The KidQuest catalog matches the PRD, and invalid content fails with actionable messages."""

import copy
import json
import subprocess
import sys

import pytest

from app.domain.kidquest.content import (
    CONTENT_DIR,
    ContentError,
    load_catalog,
    load_raw,
    required_theme_assets,
    validate_content,
)
from tests.conftest import REPO_ROOT

_RAW, _LOAD_PROBLEMS = load_raw()


@pytest.fixture
def raw():
    assert _LOAD_PROBLEMS == []
    return copy.deepcopy(_RAW)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def quest(raw, qid):
    return next(q for q in raw["quests"]["quests"] if q["id"] == qid)


def building(raw, bid):
    return next(b for b in raw["buildings"]["buildings"] if b["id"] == bid)


def theme(raw, tid):
    return next(t for t in raw["themes"]["themes"] if t["id"] == tid)


# --- The shipped catalog --------------------------------------------------------------------


def test_shipped_content_is_valid(raw):
    assert validate_content(raw) == []


def test_catalog_counts(catalog):
    assert catalog.counts() == {
        "quests": 6,
        "playable_quests": 1,
        "buildings": 6,
        "themes": 3,
        "assets_per_theme": 56,
        "road_masks": 16,
        "shore_masks": 16,
        "water_cells": 12,
        "fixed_objects": 5,
        "zones": 3,
    }


def test_q001_matches_prd_8_1(raw):
    q001 = quest(raw, "Q001")
    challenge = q001["challenge"]

    assert (q001["id"], q001["version"], q001["title"]) == ("Q001", 1, "Rumah Pertama")
    assert q001["skill_ids"] == ["SUB_BASIC"] and challenge["skill_id"] == "SUB_BASIC"
    assert challenge["type"] == "numeric"
    assert challenge["visual_context"] == {"item": "wood", "required": 10, "available": 6}
    assert (challenge["operation"], challenge["answer"]) == ("subtract", 4)
    assert challenge["prompt"] == "Kita butuh 10 kayu. Sudah ada 6. Berapa lagi?"  # PRD section 12.1.
    assert q001["reward"] == {"resources": [{"resource": "wood", "amount": 4}], "blueprints": ["starter_house"]}
    assert q001["completion"] == {"type": "place_building", "building_id": "starter_house"}
    assert (q001["prerequisites"], q001["initial_status"], q001["content_status"]) == ([], "AVAILABLE", "playable")


def test_q001_reward_preview_hides_the_amount_and_the_result_states_it(raw):
    q001 = quest(raw, "Q001")

    assert q001["reward_preview"] == "Hadiah: kayu yang kurang + Cetak biru Rumah"
    assert "4" not in q001["reward_preview"] and "4" not in q001["story"]
    assert "4 kayu" in q001["reward_message"]


@pytest.mark.parametrize(
    "qid, title, building_id, skills, prerequisite, cost",
    [
        ("Q001", "Rumah Pertama", "starter_house", ["SUB_BASIC"], [], {"wood": 4}),
        ("Q002", "Kebun Tunas", "garden", ["COUNT_GROUPS"], ["Q001"], {"wood": 2}),
        ("Q003", "Toko Roti", "bakery", ["ADD_BASIC", "SUB_BASIC"], ["Q002"], {"wood": 3, "stone": 1}),
        ("Q004", "Taman Warna", "park", ["PATTERN_BASIC"], ["Q003"], {"wood": 2, "stone": 2}),
        ("Q005", "Jembatan Kecil", "bridge", ["SUB_BASIC"], ["Q004"], {"wood": 3, "stone": 2}),
        ("Q006", "Pasar Ceria", "market_stall", ["ADD_BASIC"], ["Q005"], {"wood": 2, "stone": 1}),
    ],
)
def test_core_quests_and_costs_match_prd_9_9(raw, qid, title, building_id, skills, prerequisite, cost):
    q = quest(raw, qid)
    b = building(raw, building_id)

    assert (q["title"], q["building_id"], q["skill_ids"], q["prerequisites"]) == (title, building_id, skills, prerequisite)
    assert {item["resource"]: item["amount"] for item in b["cost"]} == cost
    assert b["quest_id"] == qid


@pytest.mark.parametrize(
    "building_id, size, entrances",
    [
        ("starter_house", (2, 2), ["S"]),
        ("garden", (2, 2), ["S"]),
        ("bakery", (2, 2), ["S"]),
        ("park", (2, 2), ["S"]),
        ("bridge", (1, 2), ["N", "S"]),  # 1 wide x 2 tall: long axis north-south.
        ("market_stall", (1, 1), ["S"]),
    ],
)
def test_footprints_match_prd_11_7_and_the_sprite_map_contract(raw, building_id, size, entrances):
    b = building(raw, building_id)

    assert (b["footprint"]["width"], b["footprint"]["height"]) == size
    assert [e["side"] for e in b["entrances"]] == entrances
    assert b["allowed_rotations"] == [0]
    assert b["anchor"] == {"x": size[0] / 2, "y": size[1]}
    assert b["visual_asset_key"] == f"{building_id}--base"


def test_themes_match_prd_11_3(raw):
    themes = raw["themes"]

    assert [t["id"] for t in themes["themes"]] == ["perkampungan", "kingdom", "city"]
    assert themes["default_theme_id"] == "perkampungan"
    assert {t["id"]: t["name"] for t in themes["themes"]} == {
        "perkampungan": "Kampung Ceria",
        "kingdom": "Kerajaan Ceria",
        "city": "Kota Ceria",
    }


LABEL_KEYS = ["starter_house", "garden", "bakery", "park", "bridge", "market_stall", "quest_board"]


@pytest.mark.parametrize(
    "theme_id, labels",
    [
        ("kingdom", ["Pondok Penjaga", "Kebun Herbal Kerajaan", "Dapur Roti Istana", "Taman Kerajaan", "Jembatan Batu Cerita",
                     "Kios Pasar Kerajaan", "Papan Berita Kerajaan"]),
        ("city", ["Rumah Warna-Warni", "Kebun Komunitas", "Toko Roti Kota", "Taman Kota", "Jembatan Pejalan Kaki", "Kios Kota",
                  "Kios Info Kota"]),
        ("perkampungan", ["Rumah Kampung", "Kebun Tunas", "Warung Roti", "Lapangan Kampung", "Jembatan Kayu-Bambu", "Kios Pasar",
                          "Papan Pengumuman"]),
    ],
)
def test_child_facing_theme_labels_are_indonesian(raw, theme_id, labels):
    """PRD 10.1: Indonesian is the default child-facing language in every theme."""
    assert raw["themes"]["child_facing_language"] == "id"
    assert [theme(raw, theme_id)["labels"][key] for key in LABEL_KEYS] == labels


@pytest.mark.parametrize(
    "theme_id, names",
    [
        ("kingdom", ["Keeper's Cottage", "Royal Herb Garden", "Castle Bakehouse", "Royal Garden", "Stone Story Bridge", "Royal Bazaar Stall", "Herald Board"]),
        ("city", ["Colorful Townhouse", "Community Garden", "City Bakery", "City Park", "Pedestrian City Bridge", "City Kiosk", "Civic Kiosk"]),
        ("perkampungan", ["Rumah Kampung", "Kebun Tunas", "Warung Roti", "Lapangan Kampung", "Jembatan Kayu-Bambu", "Kios Pasar", "Papan Pengumuman"]),
    ],
)
def test_prd_11_7_names_are_art_references_only(raw, theme_id, names):
    assert [theme(raw, theme_id)["art_reference_names"][key] for key in LABEL_KEYS] == names
    english = {"Keeper's Cottage", "Herald Board", "City Kiosk", "Civic Kiosk", "Royal Garden", "City Park"}
    child_facing = [t["name"] for t in raw["themes"]["themes"]] + [label for t in raw["themes"]["themes"] for label in t["labels"].values()]
    assert not english & set(child_facing)


def test_runtime_asset_paths_follow_one_rule_for_every_theme(catalog):
    for theme_id in ("perkampungan", "kingdom", "city"):
        paths = catalog.asset_paths(theme_id)
        assert len(paths) == 56
        assert paths["starter_house--base"] == f"/static/images/kidquest/themes/{theme_id}/buildings/starter_house--base@2x.webp"
        assert paths["road_basic--mask_05"] == f"/static/images/kidquest/themes/{theme_id}/roads/road_basic--mask_05@2x.webp"
        assert paths["shore--mask_15"] == f"/static/images/kidquest/themes/{theme_id}/terrain/shore--mask_15@2x.webp"
        assert paths["quest_board--base"] == f"/static/images/kidquest/themes/{theme_id}/props/quest_board--base@2x.webp"


def test_validator_cli_reports_counts():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "validate_kidquest_content.py")],
        env={"PYTHONPATH": str(REPO_ROOT), "PATH": ""},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "KidQuest content OK" in result.stdout and "assets_per_theme: 56" in result.stdout


# --- Invalid content -------------------------------------------------------------------------


def _set(path_fn, value):
    def mutate(raw):
        target, key = path_fn(raw)
        target[key] = value
    return mutate


INVALID_CASES = {
    "schema version": (lambda r: r["roads"].__setitem__("schema_version", 2), "roads.json: schema_version must be 1, got 2"),
    "duplicate quest id": (lambda r: quest(r, "Q002").__setitem__("id", "Q001"), "(Q001): id is not unique"),
    "unknown skill": (lambda r: quest(r, "Q001").__setitem__("skill_ids", ["DIVIDE_HARD"]), "skill_ids must be a non-empty list from"),
    "unknown resource": (lambda r: building(r, "bakery")["cost"].__setitem__(1, {"resource": "marble", "amount": 1}),
                         "needs a resource from wood, stone"),
    "missing prerequisite": (lambda r: quest(r, "Q003").__setitem__("prerequisites", ["Q009"]), "prerequisite 'Q009' is not a quest"),
    "prerequisite cycle": (lambda r: quest(r, "Q001").update(prerequisites=["Q006"], initial_status="LOCKED"), "prerequisite cycle"),
    "answer disagrees": (lambda r: quest(r, "Q001")["challenge"].__setitem__("answer", 5), "disagrees with the visual operands (10 subtract 6 = 4)"),
    "prompt leaks answer": (lambda r: quest(r, "Q001")["challenge"].__setitem__("prompt", "10 kayu, ada 6, kurang 4?"),
                            "challenge.prompt must not contain the answer 4"),
    "preview leaks reward": (lambda r: quest(r, "Q001").__setitem__("reward_preview", "Hadiah: 4 kayu"),
                             "reward_preview must not contain the answer 4"),
    "hint leaks answer": (lambda r: quest(r, "Q001")["challenge"]["hints"].append("Jawabannya 4."), "hints[2] must not state the answer 4"),
    "reward differs from cost": (lambda r: building(r, "starter_house")["cost"].__setitem__(0, {"resource": "wood", "amount": 5}),
                                 "must equal the starter_house placement cost"),
    "empty title": (lambda r: quest(r, "Q004").__setitem__("title", " "), "(Q004): title must be non-empty"),
    "unsupported challenge": (lambda r: quest(r, "Q001")["challenge"].__setitem__("type", "multiple_choice"),
                              "challenge.type 'multiple_choice' is not supported yet"),
    "building quest mismatch": (lambda r: building(r, "garden").__setitem__("quest_id", "Q003"), "building garden names quest 'Q003'"),
    "missing building": (lambda r: r["buildings"]["buildings"].pop(), "must define exactly the core buildings"),
    "incomplete collision": (lambda r: building(r, "park")["collision_cells"].pop(), "collision_cells must list each of the 2x2"),
    "anchor not bottom centre": (lambda r: building(r, "garden").__setitem__("anchor", {"x": 0, "y": 0}), "anchor must be the footprint's bottom-centre"),
    "bridge side entrances": (lambda r: building(r, "bridge").__setitem__("entrances", [{"side": "E"}, {"side": "W"}]),
                              "a bridge needs entrances at both short ends ['N', 'S']"),
    "rotation": (lambda r: building(r, "bakery").__setitem__("allowed_rotations", [0, 90]), "allowed_rotations must be [0]"),
    "label placeholder": (lambda r: building(r, "park").__setitem__("accessible_label_template", "{name} {colour}"), "use only {name}, {x}, {y}"),
    "theme missing asset": (lambda r: theme(r, "kingdom")["assets"].remove("road_basic--mask_07"),
                            "theme 'kingdom': missing required logical assets road_basic--mask_07"),
    "theme extra asset": (lambda r: theme(r, "city")["assets"].append("castle_moat--base"), "theme 'city': lists assets that are not required"),
    "theme ids": (lambda r: r["themes"]["themes"].append({**copy.deepcopy(theme(r, "city")), "id": "space"}), "themes must be exactly"),
    "theme label missing": (lambda r: theme(r, "perkampungan")["labels"].pop("quest_board"), "labels missing or empty for quest_board"),
    "theme label empty": (lambda r: theme(r, "kingdom")["labels"].__setitem__("starter_house", "  "),
                          "theme 'kingdom': labels missing or empty for starter_house"),
    "theme label not text": (lambda r: theme(r, "city")["labels"].__setitem__("garden", None), "theme 'city': labels missing or empty for garden"),
    "theme label unknown key": (lambda r: theme(r, "city")["labels"].__setitem__("castle", "Istana"), "labels has unknown keys castle"),
    "theme name empty": (lambda r: theme(r, "city").__setitem__("name", ""), "theme 'city': name must be non-empty child-facing text"),
    "art reference missing": (lambda r: theme(r, "kingdom")["art_reference_names"].pop("bridge"),
                              "theme 'kingdom': art_reference_names missing or empty for bridge"),
    "art reference field missing": (lambda r: theme(r, "city").pop("art_reference_names"), "missing required field(s) art_reference_names"),
    "child-facing language": (lambda r: r["themes"].__setitem__("child_facing_language", "en"), "child_facing_language must be 'id'"),
    "runtime directory missing": (lambda r: r["themes"]["runtime_assets"]["directories"].pop("road_masks"),
                                  "runtime_assets: directories needs a lowercase snake_case directory for road_masks"),
    "runtime template": (lambda r: r["themes"]["runtime_assets"].__setitem__("path_template", "/static/{asset_id}.webp"),
                         "path_template must contain {theme_id}, {directory}, and {asset_id}"),
    "runtime path pattern": (lambda r: r["themes"]["runtime_assets"].__setitem__("path_template", "/img/{theme_id}/{directory}/{asset_id}.gif"),
                             "does not match the manifest runtime_path pattern"),
    "road mask missing": (lambda r: r["roads"]["road_masks"].pop(9), "road_masks must contain each mask 0-15 exactly once"),
    "road mask connections": (lambda r: r["roads"]["road_masks"][5].__setitem__("connections", ["E", "W"]),
                              "road_masks mask 05 must list connections ['N', 'S']"),
    "road mask shape": (lambda r: r["roads"]["road_masks"][3].__setitem__("shape", "corner_south_west"), "road mask 03 shape must be 'corner_north_east'"),
    "shore asset": (lambda r: r["roads"]["shore_masks"][15].__setitem__("asset_id", "shore--mask_f"), "shore_masks mask 15 asset_id must be 'shore--mask_15'"),
    "coordinate convention": (lambda r: r["layout"]["coordinates"].__setitem__("origin", "south_west"), "coordinates must declare"),
    "fixed object off map": (lambda r: r["layout"]["fixed_objects"][0].update(x=8), "inside the 8x8 grid"),
    "two quest boards": (lambda r: r["layout"]["fixed_objects"].append({"id": "board2", "kind": "quest_board", "x": 1, "y": 3}),
                         "exactly one fixed object must be the quest_board"),
    "obstacle on water": (lambda r: r["layout"]["fixed_objects"].append({"id": "rock2", "kind": "blocked_rock", "x": 4, "y": 4}), "is on water"),
    "tutorial zone water": (lambda r: r["layout"]["water"].append({"x": 2, "y": 2}), "tutorial_zone must not contain water"),
    "tutorial zone too small": (lambda r: r["layout"]["zones"]["tutorial_zone"].update(width=1), "tutorial_zone has no valid 2x2 starter_house placement"),
    "tutorial zone whole map": (lambda r: (r["layout"].__setitem__("water", []),
                                           r["layout"]["zones"]["tutorial_zone"].update(x=0, y=0, width=8, height=8)),
                                "keep it to at most half the map"),
    "bridge zone size": (lambda r: r["layout"]["zones"]["bridge_zone"].update(width=2), "bridge_zone must be exactly the bridge footprint (1 wide x 2 tall)"),
    "bridge zone on land": (lambda r: r["layout"]["zones"]["bridge_zone"].update(x=1, y=4), "every bridge_zone cell must be water"),
    "expansion reachable by land": (lambda r: r["layout"]["water"].__delitem__(slice(10, 12)), "zones.expansion_zone is reachable without the bridge"),
    "zone unlock mismatch": (lambda r: r["layout"]["zones"]["expansion_zone"].update(unlocked_by_quest="Q004"), "must be a quest listing 'expansion_zone'"),
    "road unlock mismatch": (lambda r: r["roads"].__setitem__("unlocked_by_quest", "Q004"), "quest Q004 must list 'road_editing'"),
    "core catalog does not fit": (
        lambda r: r["layout"]["fixed_objects"].extend(
            {"id": f"rock_{x}_{y}", "kind": "blocked_rock", "x": x, "y": y}
            for x, y in [(5, 1), (6, 1), (5, 2), (6, 2), (0, 4), (1, 4), (0, 5), (1, 5), (2, 5)]
        ),
        "placing starter_house at (1, 1) leaves no way to place and connect every other core building",
    ),
}


@pytest.mark.parametrize("case", INVALID_CASES)
def test_invalid_content_is_rejected_with_an_actionable_message(raw, case):
    mutate, expected = INVALID_CASES[case]
    mutate(raw)

    problems = validate_content(raw)

    assert any(expected in problem for problem in problems), problems


def test_load_catalog_reports_every_problem_together(tmp_path, raw):
    quest(raw, "Q001")["title"] = ""
    theme(raw, "city")["assets"].remove("wood--icon")
    for key, name in {"quests": "quests.json", "buildings": "buildings.json", "themes": "themes.json", "roads": "roads.json",
                      "assets_schema": "assets.schema.json", "layout": "layouts/pulau_tunas_v1.json",
                      "ui_strings": "ui_strings.json"}.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw[key]), encoding="utf-8")

    with pytest.raises(ContentError) as error:
        load_catalog(tmp_path)

    assert len(error.value.problems) == 2
    assert "title must be non-empty" in str(error.value) and "wood--icon" in str(error.value)


def test_missing_and_malformed_files_are_reported(tmp_path):
    (tmp_path / "quests.json").write_text("{ not json", encoding="utf-8")

    with pytest.raises(ContentError) as error:
        load_catalog(tmp_path)

    message = str(error.value)
    assert "quests.json: invalid JSON at line 1" in message
    assert "buildings.json: file is missing" in message


def test_required_theme_assets_are_the_56_logical_ids(raw):
    assets = required_theme_assets(raw)

    assert len(assets) == 56
    assert {f"road_basic--mask_{m:02d}" for m in range(16)} <= assets
    assert {f"shore--mask_{m:02d}" for m in range(16)} <= assets
    assert not any(asset.endswith((".webp", ".png")) for asset in assets)  # Logical IDs, not files.


def test_content_dir_points_at_the_repository():
    assert CONTENT_DIR == REPO_ROOT / "content" / "kidquest"
