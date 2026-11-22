"""Building placement rules (PRD 8.2, 9.13, 14.2): one pure function for preview and placement.

`placement_problems` reads only the catalog and a snapshot of world facts, never the database or
the theme, so the read-only preview and the placement transaction always agree, in every theme.
Coordinates follow `content/kidquest/README.md`: (x, y) is the footprint's top-left (north-west)
cell; x grows east, y grows south.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.kidquest.content import Catalog
from app.domain.kidquest.geometry import Cell, Rect
from app.domain.kidquest.state import QuestStatus

RESOURCE_NAMES = {"wood": "kayu", "stone": "batu"}

# Machine-readable rules in reporting order (the first one names the error).
RULES = (
    "unknown_building", "already_built", "quest_not_ready", "missing_blueprint", "rotation",
    "out_of_bounds", "blocked", "collision", "water", "not_water", "outside_zone", "insufficient_resources",
)
# Layout.placement_problems codes, in the order a child should hear about them.
GEOMETRY_RULES = ("out_of_bounds", "blocked", "collision", "water", "not_water", "outside_zone")

MESSAGES = {
    "unknown_building": "Bangunan ini tidak dikenal.",
    "already_built": "{name} sudah dibangun. Setiap bangunan utama hanya boleh satu.",
    "quest_not_ready": "Selesaikan tantangan misinya dulu, lalu bangun {name}.",
    "missing_blueprint": "Kamu belum punya cetak biru {name}.",
    "rotation": "Bangunan ini tidak bisa diputar.",
    "out_of_bounds": "Pilih tempat di dalam pulau.",
    "blocked": "Ada pohon, batu, atau papan di sini. Pilih tempat lain.",
    "collision": "Tempat ini sudah terpakai. Pilih area kosong.",
    "water": "Tidak bisa membangun di atas air. Pilih tanah.",
    "not_water": "Jembatan harus dibangun di atas air.",
    "outside_zone": "Pilih area kosong di zona rumah.",
    "insufficient_resources": "Bahanmu belum cukup: {shortfall}.",
}


@dataclass(frozen=True)
class WorldFacts:
    """What placement depends on, read inside the caller's transaction."""

    quest_status: str | None  # Status of the building's quest for this child.
    blueprints: frozenset[str]
    balances: Mapping[str, int]
    built_types: frozenset[str]
    occupied: frozenset[Cell]  # Cells under existing buildings and road segments.


def footprint(catalog: Catalog, building_type: str, x: int, y: int) -> Rect:
    building = catalog.buildings[building_type]
    return Rect(x, y, building.width, building.height)


def placement_problems(catalog: Catalog, building_type: str, x: int, y: int, rotation: int, facts: WorldFacts) -> list[str]:
    """Every rule this placement breaks, in RULES order. An empty list means it may be built."""
    building = catalog.buildings.get(building_type)
    if building is None:
        return ["unknown_building"]
    problems = []
    if building_type in facts.built_types:  # Core buildings exist at most once (PRD 9.13).
        problems.append("already_built")
    if facts.quest_status != QuestStatus.READY_TO_BUILD.value:
        problems.append("quest_not_ready")
    if building_type not in facts.blueprints:
        problems.append("missing_blueprint")
    if rotation not in building.raw["allowed_rotations"]:
        problems.append("rotation")
    geometry = set(catalog.layout.placement_problems(
        footprint(catalog, building_type, x, y),
        zone=building.placement_zone,
        on_water=building.placement_zone == "bridge_zone",
        occupied=facts.occupied,
    ))
    problems += [rule for rule in GEOMETRY_RULES if rule in geometry]
    if any(facts.balances.get(resource, 0) < amount for resource, amount in building.cost.items()):
        problems.append("insufficient_resources")
    return problems


def problem_message(catalog: Catalog, building_type: str, rule: str, facts: WorldFacts) -> str:
    """A short, actionable Indonesian message for one rule."""
    building = catalog.buildings.get(building_type)
    shortfall = ""
    if building is not None:
        shortfall = ", ".join(
            f"butuh {amount} {RESOURCE_NAMES.get(resource, resource)}, kamu punya {facts.balances.get(resource, 0)}"
            for resource, amount in building.cost.items()
            if facts.balances.get(resource, 0) < amount
        )
    return MESSAGES[rule].format(name=building.name if building else "", shortfall=shortfall)
