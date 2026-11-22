"""Load and validate the versioned KidQuest content catalog in `content/kidquest/`.

`validate_content(raw)` checks the raw JSON and returns every problem as an actionable message.
`load_catalog()` raises ContentError listing all problems, or returns a typed Catalog.
Image files are not checked here; that belongs to the asset validator (KQ-006).
"""

import json
import re
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

from app.config import ConfigError
from app.domain.kidquest.geometry import (
    FIXED_OBJECT_KINDS,
    SIDES,
    Layout,
    PlacedBuilding,
    Rect,
    disconnected_buildings,
    edge_cells,
    reachable_from_quest_board,
)
from app.domain.kidquest.roads import MASK_COUNT, MASK_SHAPES, road_asset_id, shore_asset_id, sides_for
from app.domain.kidquest.state import QuestStatus
from app.domain.kidquest.theme import DEFAULT_THEME_ID, THEME_IDS

CONTENT_DIR = Path(__file__).resolve().parents[3] / "content" / "kidquest"
LAYOUT_ID = "pulau_tunas_v1"
CONTENT_FILES = {
    "quests": "quests.json",
    "buildings": "buildings.json",
    "themes": "themes.json",
    "roads": "roads.json",
    "assets_schema": "assets.schema.json",
    "layout": f"layouts/{LAYOUT_ID}.json",
    "ui_strings": "ui_strings.json",
}

SUPPORTED_SCHEMA_VERSION = 1
SKILLS = ("SUB_BASIC", "ADD_BASIC", "COUNT_GROUPS", "PATTERN_BASIC")
RESOURCES = ("wood", "stone")
SUPPORTED_CHALLENGE_TYPES = ("numeric",)
OPERATIONS = {"subtract": lambda a, b: a - b, "add": lambda a, b: a + b}
CONTENT_STATUSES = ("playable", "planned")
FEATURES = ("economy",)
INTERACTION_TYPES = ("world_home", "practice", "inspect")
ECONOMIC_ROLES = ("infrastructure", "productive", "community")
LABEL_PLACEHOLDERS = {"name", "x", "y"}
CHILD_FACING_LANGUAGE = "id"  # Indonesian (PRD 10.1).
# Placeholders the KidQuest page may fill in ui_strings.json (static/js/kidquest.js `t()`).
UI_PLACEHOLDERS = {
    "amount", "available", "cost", "h", "item", "label", "name", "required", "resource", "step", "text", "title",
    "total", "w", "what", "x", "y",
}
UI_PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]*)\}")
# Child-facing KidQuest copy never shows money (PRD 8.4, decision C13).
UI_FORBIDDEN_TEXT = re.compile(r"\bRp\b|rupiah", re.IGNORECASE)
# Must match the partial unique index on kidquest_buildings in Migration 8.
CORE_BUILDING_TYPES = ("starter_house", "garden", "bakery", "park", "bridge", "market_stall")
COORDINATE_CONVENTION = {
    "origin": "north_west",
    "x_axis": "east",
    "y_axis": "south",
    "position": "footprint_top_left",
}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
QUEST_ID_PATTERN = re.compile(r"^Q\d{3}$")


class ContentError(ConfigError):
    """KidQuest content is invalid; `problems` lists every reason."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(
            f"KidQuest content in {CONTENT_DIR} is invalid ({len(problems)} problem(s)):\n- " + "\n- ".join(problems)
        )


# --- Typed catalog ------------------------------------------------------------------------------


@dataclass(frozen=True)
class Building:
    id: str
    name: str
    quest_id: str
    width: int
    height: int
    entrances: tuple[str, ...]
    cost: dict[str, int]
    placement_zone: str | None
    visual_asset_key: str
    raw: dict


@dataclass(frozen=True)
class Quest:
    id: str
    version: int
    content_status: str
    title: str
    skill_ids: tuple[str, ...]
    prerequisites: tuple[str, ...]
    initial_status: QuestStatus
    building_id: str
    raw: dict

    @property
    def playable(self) -> bool:
        return self.content_status == "playable"


@dataclass(frozen=True)
class Catalog:
    content_version: dict[str, int]
    layout: Layout
    buildings: dict[str, Building]
    quests: dict[str, Quest]
    themes: dict[str, dict]
    roads: dict
    raw: dict

    @property
    def quest_order(self) -> list[str]:
        return list(self.quests)

    @property
    def ui_strings(self) -> dict[str, dict[str, str]]:
        """Child-facing page copy (`ui_strings.json` `strings`), grouped; read by static/js/kidquest.js."""
        return self.raw["ui_strings"]["strings"]

    @property
    def manifest_version(self) -> int:
        return self.raw["themes"]["manifest_version"]

    def asset_paths(self, theme_id: str) -> dict[str, str]:
        """Logical asset ID -> runtime path in one theme, from `themes.json runtime_assets` alone.

        Every theme resolves with the same rule, so callers never branch on the theme.
        """
        runtime = self.raw["themes"]["runtime_assets"]
        groups = theme_asset_groups(self.raw)
        return {
            asset: runtime["path_template"].format(
                theme_id=theme_id, directory=runtime["directories"][groups[asset]], asset_id=asset
            )
            for asset in self.themes[theme_id]["assets"]
        }

    def counts(self) -> dict[str, int]:
        return {
            "quests": len(self.quests),
            "playable_quests": sum(quest.playable for quest in self.quests.values()),
            "buildings": len(self.buildings),
            "themes": len(self.themes),
            "assets_per_theme": len(next(iter(self.themes.values()))["assets"]),
            "road_masks": len(self.roads["road_masks"]),
            "shore_masks": len(self.roads["shore_masks"]),
            "water_cells": len(self.layout.water),
            "fixed_objects": len(self.layout.fixed_objects),
            "zones": len(self.layout.zones),
        }


# --- Loading ------------------------------------------------------------------------------------


def load_raw(content_dir: Path = CONTENT_DIR) -> tuple[dict[str, Any], list[str]]:
    """Read every content file; missing or malformed files become problems, not exceptions."""
    raw, problems = {}, []
    for key, name in CONTENT_FILES.items():
        path = content_dir / name
        try:
            raw[key] = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            problems.append(f"{name}: file is missing (expected at {path})")
        except json.JSONDecodeError as exc:
            problems.append(f"{name}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
    return raw, problems


def load_catalog(content_dir: Path = CONTENT_DIR) -> Catalog:
    raw, problems = load_raw(content_dir)
    if not problems:
        problems = validate_content(raw)
    if problems:
        raise ContentError(problems)
    return build_catalog(raw)


def build_layout(raw_layout: dict) -> Layout:
    zones = raw_layout["zones"]
    return Layout(
        layout_id=raw_layout["layout_id"],
        width=raw_layout["width"],
        height=raw_layout["height"],
        water=frozenset((cell["x"], cell["y"]) for cell in raw_layout["water"]),
        fixed_objects={(obj["x"], obj["y"]): obj["kind"] for obj in raw_layout["fixed_objects"]},
        zones={name: Rect(z["x"], z["y"], z["width"], z["height"]) for name, z in zones.items()},
        zone_unlocked_by={name: z["unlocked_by_quest"] for name, z in zones.items() if z.get("unlocked_by_quest")},
    )


def _building(raw_building: dict) -> Building:
    return Building(
        id=raw_building["id"],
        name=raw_building["name"],
        quest_id=raw_building["quest_id"],
        width=raw_building["footprint"]["width"],
        height=raw_building["footprint"]["height"],
        entrances=tuple(entrance["side"] for entrance in raw_building["entrances"]),
        cost={item["resource"]: item["amount"] for item in raw_building["cost"]},
        placement_zone=raw_building["placement_zone"],
        visual_asset_key=raw_building["visual_asset_key"],
        raw=raw_building,
    )


def _quest(raw_quest: dict) -> Quest:
    return Quest(
        id=raw_quest["id"],
        version=raw_quest["version"],
        content_status=raw_quest["content_status"],
        title=raw_quest["title"],
        skill_ids=tuple(raw_quest["skill_ids"]),
        prerequisites=tuple(raw_quest["prerequisites"]),
        initial_status=QuestStatus(raw_quest["initial_status"]),
        building_id=raw_quest["building_id"],
        raw=raw_quest,
    )


def build_catalog(raw: dict) -> Catalog:
    return Catalog(
        content_version={key: raw[key].get("content_version", 0) for key in CONTENT_FILES if key != "assets_schema"},
        layout=build_layout(raw["layout"]),
        buildings={item["id"]: _building(item) for item in raw["buildings"]["buildings"]},
        quests={item["id"]: _quest(item) for item in raw["quests"]["quests"]},
        themes={item["id"]: item for item in raw["themes"]["themes"]},
        roads=raw["roads"],
        raw=raw,
    )


# --- Validation ---------------------------------------------------------------------------------


class _Problems(list):
    def check(self, condition: bool, message: str) -> bool:
        if not condition:
            self.append(message)
        return condition


def _is_int(value, minimum=None) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and (minimum is None or value >= minimum)


def _is_text(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _items(problems: _Problems, data: Any, key: str, where: str) -> list[dict]:
    value = data.get(key) if isinstance(data, dict) else None
    if not problems.check(isinstance(value, list) and all(isinstance(item, dict) for item in value),
                          f"{where}: '{key}' must be a list of objects"):
        return []
    return value


def _require_keys(problems: _Problems, item: dict, keys: tuple[str, ...], where: str) -> bool:
    missing = [key for key in keys if key not in item]
    return problems.check(not missing, f"{where}: missing required field(s) {', '.join(missing)}")


def _check_versions(problems: _Problems, raw: dict) -> None:
    for key, name in CONTENT_FILES.items():
        data = raw.get(key)
        if not problems.check(isinstance(data, dict), f"{name}: top level must be a JSON object"):
            continue
        problems.check(
            data.get("schema_version") == SUPPORTED_SCHEMA_VERSION,
            f"{name}: schema_version must be {SUPPORTED_SCHEMA_VERSION}, got {data.get('schema_version')!r}",
        )
        if key != "assets_schema":
            problems.check(_is_int(data.get("content_version"), 1),
                           f"{name}: content_version must be a whole number of at least 1")


def validate_content(raw: dict) -> list[str]:
    """Every problem in the raw catalog, each naming the file, item, and fix."""
    problems = _Problems()
    _check_versions(problems, raw)
    if problems:
        return list(problems)

    layout_ok = _check_layout(problems, raw["layout"])
    buildings = _check_buildings(problems, raw)
    quests = _check_quests(problems, raw, buildings)
    _check_roads(problems, raw, quests)
    _check_themes(problems, raw, buildings)
    _check_ui_strings(problems, raw["ui_strings"])
    if layout_ok and not problems:
        _check_layout_against_catalog(problems, raw)
    return list(problems)


def _check_layout(problems: _Problems, layout: dict) -> bool:
    where = CONTENT_FILES["layout"]
    if not _require_keys(problems, layout, ("layout_id", "width", "height", "coordinates", "water", "fixed_objects", "zones"), where):
        return False
    start = len(problems)
    problems.check(layout["layout_id"] == LAYOUT_ID, f"{where}: layout_id must be '{LAYOUT_ID}', got {layout['layout_id']!r}")
    width, height = layout["width"], layout["height"]
    if not problems.check(_is_int(width, 1) and _is_int(height, 1), f"{where}: width and height must be positive whole numbers"):
        return False
    problems.check(
        {key: layout["coordinates"].get(key) for key in COORDINATE_CONVENTION} == COORDINATE_CONVENTION,
        f"{where}: coordinates must declare {COORDINATE_CONVENTION} (the convention the code implements)",
    )
    bounds = Rect(0, 0, width, height)

    def cell_ok(cell, label) -> bool:
        ok = isinstance(cell, dict) and _is_int(cell.get("x")) and _is_int(cell.get("y"))
        return problems.check(ok and bounds.contains((cell["x"], cell["y"])),
                              f"{where}: {label} {cell!r} must have whole-number x, y inside the {width}x{height} grid")

    water = []
    for index, cell in enumerate(layout["water"]):
        if cell_ok(cell, f"water[{index}]"):
            water.append((cell["x"], cell["y"]))
    problems.check(len(water) == len(set(water)), f"{where}: water lists a cell more than once")

    seen_ids, fixed = set(), {}
    for index, obj in enumerate(layout["fixed_objects"]):
        label = f"fixed_objects[{index}]"
        if not _require_keys(problems, obj, ("id", "kind", "x", "y"), f"{where}: {label}") or not cell_ok(obj, label):
            continue
        cell = (obj["x"], obj["y"])
        problems.check(obj["id"] not in seen_ids, f"{where}: {label} id {obj['id']!r} is not unique")
        seen_ids.add(obj["id"])
        problems.check(obj["kind"] in FIXED_OBJECT_KINDS,
                       f"{where}: {label} kind {obj['kind']!r} is unknown; use one of {', '.join(FIXED_OBJECT_KINDS)}")
        problems.check(cell not in water, f"{where}: {label} ({obj['id']}) at {cell} is on water")
        problems.check(cell not in fixed, f"{where}: {label} ({obj['id']}) at {cell} overlaps another fixed object")
        fixed[cell] = obj["kind"]
    problems.check(list(fixed.values()).count("quest_board") == 1, f"{where}: exactly one fixed object must be the quest_board")

    zones = layout["zones"]
    for name in ("tutorial_zone", "bridge_zone"):
        problems.check(name in zones, f"{where}: zones.{name} is required")
    for name, zone in zones.items():
        ok = isinstance(zone, dict) and all(_is_int(zone.get(k), 0) for k in ("x", "y")) and all(
            _is_int(zone.get(k), 1) for k in ("width", "height"))
        if problems.check(ok, f"{where}: zones.{name} needs whole-number x, y and positive width, height"):
            problems.check(bounds.contains_rect(Rect(zone["x"], zone["y"], zone["width"], zone["height"])),
                           f"{where}: zones.{name} extends outside the {width}x{height} grid")
    return len(problems) == start


def _check_buildings(problems: _Problems, raw: dict) -> dict[str, dict]:
    where = CONTENT_FILES["buildings"]
    layout = raw["layout"]
    zones = layout.get("zones", {}) if isinstance(layout, dict) else {}
    buildings = {}
    for index, item in enumerate(_items(problems, raw["buildings"], "buildings", where)):
        label = f"{where} buildings[{index}]"
        keys = ("id", "name", "quest_id", "core", "max_instances", "footprint", "collision_cells", "allowed_rotations",
                "entrances", "anchor", "shadow_bounds", "cost", "interaction_type", "economic_role", "placement_zone",
                "visual_asset_key", "accessible_label_template")
        if not _require_keys(problems, item, keys, label):
            continue
        bid = item["id"]
        label = f"{where} buildings[{index}] ({bid})"
        problems.check(isinstance(bid, str) and bool(ID_PATTERN.match(bid)), f"{label}: id must be lowercase snake_case")
        problems.check(bid not in buildings, f"{label}: id is not unique")
        buildings[bid] = item
        problems.check(_is_text(item["name"]), f"{label}: name must be non-empty child-facing text")
        problems.check(item["core"] is True and item["max_instances"] == 1,
                       f"{label}: core buildings must have core=true and max_instances=1")
        problems.check(item["interaction_type"] in INTERACTION_TYPES,
                       f"{label}: interaction_type must be one of {', '.join(INTERACTION_TYPES)}")
        problems.check(item["economic_role"] in ECONOMIC_ROLES,
                       f"{label}: economic_role must be one of {', '.join(ECONOMIC_ROLES)}")

        footprint = item["footprint"]
        if not problems.check(isinstance(footprint, dict) and _is_int(footprint.get("width"), 1)
                              and _is_int(footprint.get("height"), 1),
                              f"{label}: footprint needs positive whole-number width and height"):
            continue
        w, h = footprint["width"], footprint["height"]
        expected_cells = {(x, y) for y in range(h) for x in range(w)}
        cells = {(c.get("x"), c.get("y")) for c in item["collision_cells"] if isinstance(c, dict)}
        problems.check(cells == expected_cells and len(item["collision_cells"]) == len(expected_cells),
                       f"{label}: collision_cells must list each of the {w}x{h} footprint cells exactly once")
        problems.check(item["allowed_rotations"] == [0], f"{label}: allowed_rotations must be [0] (rotation is fixed in the MVP)")
        sides = [e.get("side") for e in item["entrances"] if isinstance(e, dict)]
        problems.check(bool(sides) and all(s in SIDES for s in sides) and len(sides) == len(set(sides)),
                       f"{label}: entrances must be a non-empty list of distinct sides from {', '.join(SIDES)}")
        problems.check(item["anchor"] == {"x": w / 2, "y": h},
                       f"{label}: anchor must be the footprint's bottom-centre {{'x': {w / 2}, 'y': {h}}}")
        shadow = item["shadow_bounds"]
        problems.check(isinstance(shadow, dict) and _is_int(shadow.get("width"), w) and _is_int(shadow.get("height"), h),
                       f"{label}: shadow_bounds must cover at least the {w}x{h} footprint")
        _check_cost(problems, item["cost"], f"{label}: cost")
        problems.check(isinstance(item["visual_asset_key"], str) and item["visual_asset_key"] == f"{bid}--base",
                       f"{label}: visual_asset_key must be '{bid}--base'")
        template = item["accessible_label_template"]
        placeholders = set(re.findall(r"{(\w+)}", template)) if isinstance(template, str) else set()
        problems.check(_is_text(template) and placeholders <= LABEL_PLACEHOLDERS,
                       f"{label}: accessible_label_template must be non-empty and use only {{name}}, {{x}}, {{y}}")

        zone_name = item["placement_zone"]
        if zone_name is not None and problems.check(zone_name in zones,
                                                    f"{label}: placement_zone {zone_name!r} is not a zone in the layout"):
            zone = zones[zone_name]
            if zone_name == "bridge_zone":
                problems.check((zone.get("width"), zone.get("height")) == (w, h),
                               f"{label}: bridge_zone must be exactly the bridge footprint ({w} wide x {h} tall)")
                short_ends = {"N", "S"} if h > w else {"E", "W"}
                problems.check(set(sides) == short_ends, f"{label}: a bridge needs entrances at both short ends {sorted(short_ends)}")

    problems.check(set(buildings) == set(CORE_BUILDING_TYPES),
                   f"{where}: the catalog must define exactly the core buildings {', '.join(CORE_BUILDING_TYPES)}; "
                   f"got {', '.join(sorted(buildings)) or 'none'}")
    return buildings


def _check_cost(problems: _Problems, cost: Any, label: str) -> None:
    if not problems.check(isinstance(cost, list) and cost, f"{label} must be a non-empty list"):
        return
    resources = []
    for item in cost:
        ok = isinstance(item, dict) and item.get("resource") in RESOURCES and _is_int(item.get("amount"), 1)
        problems.check(ok, f"{label} entry {item!r} needs a resource from {', '.join(RESOURCES)} and a positive amount")
        if isinstance(item, dict):
            resources.append(item.get("resource"))
    problems.check(len(resources) == len(set(resources)), f"{label} lists a resource more than once")


def _check_quests(problems: _Problems, raw: dict, buildings: dict[str, dict]) -> dict[str, dict]:
    where = CONTENT_FILES["quests"]
    quests: dict[str, dict] = {}
    for index, item in enumerate(_items(problems, raw["quests"], "quests", where)):
        label = f"{where} quests[{index}]"
        keys = ("id", "version", "content_status", "title", "skill_ids", "prerequisites", "requires_features",
                "initial_status", "building_id", "story", "challenge", "reward_preview", "reward", "reward_message",
                "completion", "unlocks")
        if not _require_keys(problems, item, keys, label):
            continue
        qid = item["id"]
        label = f"{where} quests[{index}] ({qid})"
        problems.check(isinstance(qid, str) and bool(QUEST_ID_PATTERN.match(qid)), f"{label}: id must look like Q001")
        problems.check(qid not in quests, f"{label}: id is not unique")
        quests[qid] = item
        problems.check(_is_int(item["version"], 1), f"{label}: version must be a whole number of at least 1")
        problems.check(item["content_status"] in CONTENT_STATUSES,
                       f"{label}: content_status must be one of {', '.join(CONTENT_STATUSES)}")
        problems.check(_is_text(item["title"]), f"{label}: title must be non-empty child-facing text")
        problems.check(isinstance(item["skill_ids"], list) and item["skill_ids"] and all(s in SKILLS for s in item["skill_ids"]),
                       f"{label}: skill_ids must be a non-empty list from {', '.join(SKILLS)}")
        problems.check(all(f in FEATURES for f in item["requires_features"]),
                       f"{label}: requires_features may only contain {', '.join(FEATURES)}")
        problems.check(item["initial_status"] in (QuestStatus.LOCKED.value, QuestStatus.AVAILABLE.value),
                       f"{label}: initial_status must be AVAILABLE or LOCKED")
        bid = item["building_id"]
        if problems.check(bid in buildings, f"{label}: building_id {bid!r} is not in buildings.json"):
            problems.check(buildings[bid]["quest_id"] == qid,
                           f"{label}: building {bid} names quest {buildings[bid]['quest_id']!r}; both files must agree")
        problems.check(item["completion"] == {"type": "place_building", "building_id": bid},
                       f"{label}: completion must be {{'type': 'place_building', 'building_id': '{bid}'}}")
        for text_key in ("story", "reward_preview", "reward_message"):
            if item[text_key] is not None:
                problems.check(_is_text(item[text_key]), f"{label}: {text_key} must be non-empty text or null")
        if item["content_status"] == "playable":
            _check_playable_quest(problems, item, buildings, label)
        elif item["challenge"] is not None:
            _check_challenge(problems, item, label)

    building_quests = [q["building_id"] for q in quests.values()]
    problems.check(len(building_quests) == len(set(building_quests)), f"{where}: each building may belong to only one quest")
    for bid, building in buildings.items():
        problems.check(building["quest_id"] in quests, f"{CONTENT_FILES['buildings']} ({bid}): quest_id {building['quest_id']!r} is not in quests.json")
    _check_prerequisites(problems, quests, where)
    return quests


def _check_playable_quest(problems: _Problems, quest: dict, buildings: dict[str, dict], label: str) -> None:
    for key in ("story", "challenge", "reward_preview", "reward", "reward_message"):
        problems.check(quest[key] is not None, f"{label}: a playable quest needs {key}")
    if quest["challenge"] is None or quest["reward"] is None:
        return
    answer = _check_challenge(problems, quest, label)
    reward = quest["reward"]
    resources = reward.get("resources") if isinstance(reward, dict) else None
    blueprints = reward.get("blueprints") if isinstance(reward, dict) else None
    _check_cost(problems, resources, f"{label}: reward.resources")
    problems.check(isinstance(blueprints, list) and quest["building_id"] in blueprints and all(b in buildings for b in blueprints),
                   f"{label}: reward.blueprints must include '{quest['building_id']}' and name only known buildings")
    building = buildings.get(quest["building_id"])
    if building and isinstance(resources, list):
        reward_amounts = {item.get("resource"): item.get("amount") for item in resources if isinstance(item, dict)}
        cost_amounts = {item.get("resource"): item.get("amount") for item in building["cost"] if isinstance(item, dict)}
        problems.check(reward_amounts == cost_amounts,
                       f"{label}: reward resources {reward_amounts} must equal the {quest['building_id']} placement cost {cost_amounts}")
    if answer is not None:
        # The reward amount equals the answer for Q001, so pre-answer text must not reveal it.
        for key in ("story", "reward_preview"):
            text = quest[key] or ""
            problems.check(not re.search(rf"(?<!\d){answer}(?!\d)", text),
                           f"{label}: {key} must not contain the answer {answer} (it would reveal the reward amount)")


def _check_challenge(problems: _Problems, quest: dict, label: str) -> int | None:
    challenge = quest["challenge"]
    keys = ("id", "type", "skill_id", "prompt", "visual_context", "operation", "answer", "hints")
    if not problems.check(isinstance(challenge, dict), f"{label}: challenge must be an object") or not _require_keys(
            problems, challenge, keys, f"{label}: challenge"):
        return None
    problems.check(challenge["type"] in SUPPORTED_CHALLENGE_TYPES,
                   f"{label}: challenge.type {challenge['type']!r} is not supported yet; use one of {', '.join(SUPPORTED_CHALLENGE_TYPES)}")
    problems.check(challenge["skill_id"] in quest["skill_ids"],
                   f"{label}: challenge.skill_id {challenge['skill_id']!r} must be one of the quest's skill_ids")
    problems.check(_is_text(challenge["prompt"]), f"{label}: challenge.prompt must be non-empty text")
    hints = challenge["hints"]
    problems.check(isinstance(hints, list) and hints and all(_is_text(h) for h in hints),
                   f"{label}: challenge.hints must be a non-empty list of non-empty texts")
    context = challenge["visual_context"]
    answer = challenge["answer"]
    ok = (isinstance(context, dict) and context.get("item") in RESOURCES and _is_int(context.get("required"), 0)
          and _is_int(context.get("available"), 0) and challenge["operation"] in OPERATIONS and _is_int(answer))
    if not problems.check(ok, f"{label}: challenge needs visual_context {{item, required, available}}, an operation "
                              f"({', '.join(OPERATIONS)}), and a whole-number answer"):
        return None
    expected = OPERATIONS[challenge["operation"]](context["required"], context["available"])
    problems.check(answer == expected,
                   f"{label}: challenge.answer {answer} disagrees with the visual operands "
                   f"({context['required']} {challenge['operation']} {context['available']} = {expected})")
    prompt = challenge["prompt"] if isinstance(challenge["prompt"], str) else ""
    for operand in ("required", "available"):
        problems.check(str(context[operand]) in prompt, f"{label}: challenge.prompt must show the {operand} amount {context[operand]}")
    problems.check(not re.search(rf"(?<!\d){answer}(?!\d)", prompt), f"{label}: challenge.prompt must not contain the answer {answer}")
    if isinstance(hints, list):
        for number, hint in enumerate(hints, start=1):
            if isinstance(hint, str):
                problems.check(not re.search(rf"(?<!\d){answer}(?!\d)", hint),
                               f"{label}: challenge.hints[{number - 1}] must not state the answer {answer}")
    return answer


def _check_prerequisites(problems: _Problems, quests: dict[str, dict], where: str) -> None:
    for qid, quest in quests.items():
        for prerequisite in quest.get("prerequisites", []):
            problems.check(prerequisite in quests, f"{where} ({qid}): prerequisite {prerequisite!r} is not a quest")
    roots = [qid for qid, quest in quests.items() if not quest.get("prerequisites")]
    problems.check(len(roots) == 1, f"{where}: exactly one quest must have no prerequisites (the start); got {roots}")
    for qid in roots:
        problems.check(quests[qid].get("initial_status") == "AVAILABLE", f"{where} ({qid}): the starting quest must begin AVAILABLE")
    for qid, quest in quests.items():
        if quest.get("prerequisites"):
            problems.check(quest.get("initial_status") == "LOCKED", f"{where} ({qid}): a quest with prerequisites must begin LOCKED")

    # Acyclic, reachable, and the exact linear teaching ladder in file order.
    ordered = list(quests)
    for position, qid in enumerate(ordered):
        expected = [] if position == 0 else [ordered[position - 1]]
        problems.check(quests[qid].get("prerequisites") == expected,
                       f"{where} ({qid}): core quests form one linear ladder in file order; prerequisites must be {expected}")
    visiting, done = set(), set()

    def visit(qid: str, path: list[str]) -> None:
        if qid in done or qid not in quests:
            return
        if qid in visiting:
            problems.append(f"{where}: prerequisite cycle {' -> '.join(path + [qid])}")
            return
        visiting.add(qid)
        for prerequisite in quests[qid].get("prerequisites", []):
            visit(prerequisite, path + [qid])
        visiting.discard(qid)
        done.add(qid)

    for qid in quests:
        visit(qid, [])


def _check_roads(problems: _Problems, raw: dict, quests: dict[str, dict]) -> None:
    where = CONTENT_FILES["roads"]
    roads = raw["roads"]
    if not _require_keys(problems, roads, ("road_type", "bit_order", "bits", "max_segments_per_world", "unlocked_by_quest",
                                           "road_masks", "shore_masks"), where):
        return
    problems.check(roads["road_type"] == "basic_road", f"{where}: road_type must be 'basic_road'")
    problems.check(roads["bit_order"] == "NESW" and roads["bits"] == {"N": 1, "E": 2, "S": 4, "W": 8},
                   f"{where}: bits must be N=1, E=2, S=4, W=8 in NESW order")
    problems.check(_is_int(roads["max_segments_per_world"], 1), f"{where}: max_segments_per_world must be positive")
    unlocking = roads["unlocked_by_quest"]
    if problems.check(unlocking in quests, f"{where}: unlocked_by_quest {unlocking!r} is not a quest"):
        problems.check("road_editing" in quests[unlocking].get("unlocks", []),
                       f"{where}: quest {unlocking} must list 'road_editing' in its unlocks")
    for key, asset_for, sides_key in (("road_masks", road_asset_id, "connections"), ("shore_masks", shore_asset_id, "land_sides")):
        entries = _items(problems, roads, key, where)
        masks = [entry.get("mask") for entry in entries]
        problems.check(sorted(m for m in masks if _is_int(m)) == list(range(MASK_COUNT)) and len(masks) == MASK_COUNT,
                       f"{where}: {key} must contain each mask 0-15 exactly once")
        for entry in entries:
            mask = entry.get("mask")
            if not _is_int(mask) or not 0 <= mask < MASK_COUNT:
                continue
            problems.check(entry.get(sides_key) == sides_for(mask),
                           f"{where}: {key} mask {mask:02d} must list {sides_key} {sides_for(mask)}")
            problems.check(entry.get("asset_id") == asset_for(mask), f"{where}: {key} mask {mask:02d} asset_id must be '{asset_for(mask)}'")
            if key == "road_masks":
                problems.check(entry.get("shape") == MASK_SHAPES[mask], f"{where}: road mask {mask:02d} shape must be '{MASK_SHAPES[mask]}'")
    for qid, quest in quests.items():
        for unlock in quest.get("unlocks", []):
            if unlock == "road_editing":
                problems.check(unlocking == qid, f"{CONTENT_FILES['quests']} ({qid}): unlocks road_editing but roads.json says {unlocking}")
            else:
                zone = raw["layout"].get("zones", {}).get(unlock)
                problems.check(isinstance(zone, dict) and zone.get("unlocked_by_quest") == qid,
                               f"{CONTENT_FILES['quests']} ({qid}): unlocks {unlock!r}, which must be a layout zone with unlocked_by_quest '{qid}'")
    for name, zone in raw["layout"].get("zones", {}).items():
        quest_id = zone.get("unlocked_by_quest") if isinstance(zone, dict) else None
        if quest_id is not None:
            problems.check(quest_id in quests and name in quests[quest_id].get("unlocks", []),
                           f"{CONTENT_FILES['layout']}: zones.{name} is unlocked by {quest_id!r}, which must be a quest listing '{name}' in unlocks")


def theme_asset_groups(raw: dict) -> dict[str, str]:
    """Every logical asset each theme must supply, mapped to its group (`terrain`, `road_masks`, ...)."""
    groups = {asset: group for group, assets in raw["themes"].get("required_assets", {}).items() for asset in assets}
    for key in ("road_masks", "shore_masks"):
        groups.update({entry["asset_id"]: key for entry in raw["roads"].get(key, [])})
    groups.update({item["visual_asset_key"]: "buildings" for item in raw["buildings"].get("buildings", [])})
    return groups


def required_theme_assets(raw: dict) -> set[str]:
    return set(theme_asset_groups(raw))


def _check_themes(problems: _Problems, raw: dict, buildings: dict[str, dict]) -> None:
    where = CONTENT_FILES["themes"]
    themes_raw = raw["themes"]
    if not _require_keys(problems, themes_raw, ("manifest_version", "default_theme_id", "required_assets", "themes"), where):
        return
    problems.check(_is_int(themes_raw["manifest_version"], 1), f"{where}: manifest_version must be at least 1")
    problems.check(themes_raw["default_theme_id"] == DEFAULT_THEME_ID, f"{where}: default_theme_id must be '{DEFAULT_THEME_ID}'")
    themes = _items(problems, themes_raw, "themes", where)
    ids = [theme.get("id") for theme in themes]
    problems.check(ids == list(THEME_IDS), f"{where}: themes must be exactly {list(THEME_IDS)} in that order; got {ids}")

    pattern_text = raw["assets_schema"].get("properties", {}).get("asset_id", {}).get("pattern")
    pattern = re.compile(pattern_text) if isinstance(pattern_text, str) else None
    problems.check(pattern is not None, f"{CONTENT_FILES['assets_schema']}: properties.asset_id.pattern is required")
    required = required_theme_assets(raw)
    for asset in sorted(required):
        if pattern:
            problems.check(bool(pattern.match(asset)), f"{where}: required asset {asset!r} does not match the asset_id pattern {pattern_text}")
    for layout_asset in ("ground_buildable--base", "water--base", *(f"{kind}--base" for kind in FIXED_OBJECT_KINDS)):
        problems.check(layout_asset in required, f"{where}: required_assets must include layout asset {layout_asset!r}")

    problems.check(themes_raw.get("child_facing_language") == CHILD_FACING_LANGUAGE,
                   f"{where}: child_facing_language must be '{CHILD_FACING_LANGUAGE}' (Indonesian is the default, PRD 10.1)")
    _check_runtime_assets(problems, raw)

    labels_needed = set(buildings) | {"quest_board"}
    for theme in themes:
        tid = theme.get("id")
        label = f"{where} theme {tid!r}"
        if not _require_keys(problems, theme, ("id", "name", "labels", "art_reference_names", "assets"), label):
            continue
        problems.check(_is_text(theme["name"]), f"{label}: name must be non-empty child-facing text")
        # `labels` is child-facing text; `art_reference_names` (PRD 11.7) is for artists only.
        for field in ("labels", "art_reference_names"):
            values = theme[field] if isinstance(theme[field], dict) else {}
            missing = sorted(labels_needed - {key for key, value in values.items() if _is_text(value)})
            problems.check(not missing, f"{label}: {field} missing or empty for {', '.join(missing)}")
            unknown = sorted(set(values) - labels_needed)
            problems.check(not unknown, f"{label}: {field} has unknown keys {', '.join(unknown)}; use only {', '.join(sorted(labels_needed))}")
        assets = theme["assets"] if isinstance(theme["assets"], list) else []
        problems.check(len(assets) == len(set(assets)), f"{label}: assets lists an ID more than once")
        missing, extra = sorted(required - set(assets)), sorted(set(assets) - required)
        problems.check(not missing, f"{label}: missing required logical assets {', '.join(missing)}")
        problems.check(not extra, f"{label}: lists assets that are not required logical assets {', '.join(extra)}")


def _check_runtime_assets(problems: _Problems, raw: dict) -> None:
    """`runtime_assets` turns (theme, logical asset) into a runtime path with one data-driven rule."""
    where = f"{CONTENT_FILES['themes']} runtime_assets"
    runtime = raw["themes"].get("runtime_assets")
    if not problems.check(isinstance(runtime, dict) and {"path_template", "directories"} <= set(runtime),
                          f"{where}: must be an object with path_template and directories"):
        return
    template, directories = runtime["path_template"], runtime["directories"]
    problems.check(isinstance(template, str) and all(f"{{{name}}}" in template for name in ("theme_id", "directory", "asset_id")),
                   f"{where}: path_template must contain {{theme_id}}, {{directory}}, and {{asset_id}}")
    directories = directories if isinstance(directories, dict) else {}
    groups = set(theme_asset_groups(raw).values())
    missing = sorted(group for group in groups if not (isinstance(directories.get(group), str) and ID_PATTERN.match(directories[group])))
    problems.check(not missing, f"{where}: directories needs a lowercase snake_case directory for {', '.join(missing)}")
    problems.check(set(directories) <= groups, f"{where}: directories lists unknown groups {', '.join(sorted(set(directories) - groups))}")
    runtime_pattern = raw["assets_schema"].get("properties", {}).get("runtime_path", {}).get("pattern")
    if isinstance(template, str) and isinstance(runtime_pattern, str) and not missing:
        sample = template.format(theme_id=DEFAULT_THEME_ID, directory=directories["buildings"], asset_id="starter_house--base")
        problems.check(bool(re.match(runtime_pattern, sample.lstrip("/"))),
                       f"{where}: path_template gives {sample!r}, which does not match the manifest runtime_path pattern {runtime_pattern}")


def _check_ui_strings(problems: _Problems, ui: dict) -> None:
    """`ui_strings.json`: groups of non-empty Indonesian strings with known placeholders and no money."""
    where = CONTENT_FILES["ui_strings"]
    problems.check(ui.get("child_facing_language") == CHILD_FACING_LANGUAGE,
                   f"{where}: child_facing_language must be '{CHILD_FACING_LANGUAGE}' (Indonesian is the default, PRD 10.1)")
    groups = ui.get("strings")
    if not problems.check(isinstance(groups, dict) and groups, f"{where}: 'strings' must be a non-empty object of groups"):
        return
    for group, entries in groups.items():
        if not problems.check(ID_PATTERN.match(group) is not None and isinstance(entries, dict) and entries,
                              f"{where}: strings.{group} must be a snake_case group holding a non-empty object"):
            continue
        for key, text in entries.items():
            label = f"{where}: strings.{group}.{key}"
            problems.check(ID_PATTERN.match(key) is not None, f"{label}: key must be lowercase snake_case")
            if not problems.check(_is_text(text), f"{label}: must be non-empty child-facing text"):
                continue
            unknown = sorted(set(UI_PLACEHOLDER_PATTERN.findall(text)) - UI_PLACEHOLDERS)
            problems.check(not unknown, f"{label}: unknown placeholder(s) {', '.join(unknown)}; use only {', '.join(sorted(UI_PLACEHOLDERS))}")
            problems.check(UI_PLACEHOLDER_PATTERN.sub("", text).count("{") == 0 and "}" not in UI_PLACEHOLDER_PATTERN.sub("", text),
                           f"{label}: has an unbalanced brace")
            problems.check(not UI_FORBIDDEN_TEXT.search(text), f"{label}: must not mention money (Rp/rupiah)")


def _check_layout_against_catalog(problems: _Problems, raw: dict) -> None:
    where = CONTENT_FILES["layout"]
    layout = build_layout(raw["layout"])
    buildings = {item["id"]: _building(item) for item in raw["buildings"]["buildings"]}
    quest_order = [quest["id"] for quest in raw["quests"]["quests"]]

    for name, quest_id in layout.zone_unlocked_by.items():
        problems.check(quest_id in quest_order, f"{where}: zones.{name}.unlocked_by_quest {quest_id!r} is not a quest")

    tutorial = layout.zones["tutorial_zone"]
    problems.check(not (tutorial.cells() & layout.water), f"{where}: tutorial_zone must not contain water")
    problems.check(tutorial.area * 2 <= layout.width * layout.height,
                   f"{where}: tutorial_zone covers {tutorial.area} cells; keep it to at most half the map so Q001 is a guided choice")
    starter = next((b for b in buildings.values() if b.placement_zone == "tutorial_zone"), None)
    if not problems.check(starter is not None, f"{CONTENT_FILES['buildings']}: one building must use placement_zone 'tutorial_zone'"):
        return
    starter_spots = tutorial_placements(layout, starter)
    problems.check(bool(starter_spots), f"{where}: tutorial_zone has no valid {starter.width}x{starter.height} {starter.id} "
                                        f"placement with a usable entrance; move obstacles or enlarge the zone")

    bridge = next((b for b in buildings.values() if b.placement_zone == "bridge_zone"), None)
    if not problems.check(bridge is not None, f"{CONTENT_FILES['buildings']}: one building must use placement_zone 'bridge_zone'"):
        return
    zone = layout.zones["bridge_zone"]
    problems.check(zone.cells() <= layout.water, f"{where}: every bridge_zone cell must be water (the bridge crosses water)")
    for side in bridge.entrances:
        for cell in edge_cells(zone, side):
            problems.check(layout.is_buildable(cell), f"{where}: the bridge's {side} end {cell} must be open land for a road")
    lateral = ("E", "W") if bridge.height > bridge.width else ("N", "S")
    for side in lateral:
        for cell in edge_cells(zone, side):
            problems.check(not layout.in_bounds(cell) or layout.is_water(cell),
                           f"{where}: cell {cell} beside bridge_zone must be water so the bridge visibly crosses it")

    board = layout.quest_board
    problems.check(not any(layout.zones[name].contains(board) for name in layout.zones),
                   f"{where}: the quest_board at {board} must not sit inside a placement zone")
    for name, quest_id in layout.zone_unlocked_by.items():
        area = layout.zones[name]
        problems.check(not (area.cells() & layout.water), f"{where}: zones.{name} must be land")
        without_bridge = reachable_from_quest_board(layout, [])
        with_bridge = reachable_from_quest_board(layout, [PlacedBuilding(bridge.id, zone, bridge.entrances, is_bridge=True)])
        problems.check(not (area.cells() & without_bridge),
                       f"{where}: zones.{name} is reachable without the bridge; it must open only when {quest_id} places it")
        problems.check(area.cells() <= with_bridge | set(layout.fixed_objects),
                       f"{where}: zones.{name} must be reachable across the bridge")

    for spot in starter_spots:
        if find_core_arrangement(layout, buildings, quest_order, {starter.id: spot}) is None:
            problems.append(
                f"{where}: placing {starter.id} at ({spot.x}, {spot.y}) leaves no way to place and connect every other "
                f"core building; enlarge the main area or narrow tutorial_zone"
            )


def tutorial_placements(layout: Layout, starter: Building) -> list[Rect]:
    """Every starter-house position in the tutorial zone with an entrance a road can reach."""
    zone = layout.zones["tutorial_zone"]
    spots = []
    for y, x in product(range(zone.y, zone.y + zone.height), range(zone.x, zone.x + zone.width)):
        rect = Rect(x, y, starter.width, starter.height)
        if layout.placement_problems(rect, zone="tutorial_zone"):
            continue
        if any(layout.is_buildable(cell) for side in starter.entrances for cell in edge_cells(rect, side)):
            spots.append(rect)
    return spots


def find_core_arrangement(
    layout: Layout, buildings: dict[str, Building], quest_order: list[str], fixed: dict[str, Rect]
) -> dict[str, Rect] | None:
    """Find positions for every core building so each one can be road-connected to the quest board.

    Buildings whose quest comes before a zone's unlocking quest may not use that zone; zone-bound
    buildings (tutorial, bridge) stay inside their zone. Returns None when no arrangement exists.
    """
    quest_index = {qid: index for index, qid in enumerate(quest_order)}
    # Fixed and zone-bound buildings (including the bridge) first: after that, each added building
    # can only remove reachable cells, so a partial arrangement that disconnects a building is final.
    order = sorted(
        buildings.values(),
        key=lambda b: (b.id not in fixed, b.placement_zone is None, quest_index.get(b.quest_id, len(quest_order))),
    )

    def candidates(building: Building) -> list[Rect]:
        if building.id in fixed:
            return [fixed[building.id]]
        locked = [layout.zones[name] for name, qid in layout.zone_unlocked_by.items()
                  if quest_index.get(building.quest_id, 0) < quest_index.get(qid, 0)]
        is_bridge = building.placement_zone == "bridge_zone"
        spots = []
        for y, x in product(range(layout.height), range(layout.width)):
            rect = Rect(x, y, building.width, building.height)
            if layout.placement_problems(rect, zone=building.placement_zone, on_water=is_bridge):
                continue
            if any(rect.cells() & zone.cells() for zone in locked):
                continue
            if not any(layout.is_buildable(cell) for side in building.entrances for cell in edge_cells(rect, side)):
                continue
            spots.append(rect)
        return spots

    options = [(building, candidates(building)) for building in order]

    def search(index: int, placed: list[PlacedBuilding]) -> list[PlacedBuilding] | None:
        if index == len(options):
            return placed
        building, spots = options[index]
        is_bridge = building.placement_zone == "bridge_zone"
        taken = {cell for p in placed for cell in p.rect.cells()}
        for rect in spots:
            if rect.cells() & taken:
                continue
            candidate = placed + [PlacedBuilding(building.id, rect, building.entrances, is_bridge)]
            if disconnected_buildings(layout, candidate):
                continue
            result = search(index + 1, candidate)
            if result is not None:
                return result
        return None

    found = search(0, [])
    return {p.building_id: p.rect for p in found} if found is not None else None
