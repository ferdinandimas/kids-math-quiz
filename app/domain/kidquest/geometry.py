"""Square-grid geometry for KidQuest worlds.

Convention: a cell is (x, y); (0, 0) is the north-west corner; x grows east and y grows south.
A footprint or rectangle is positioned by its top-left (north-west) cell and extends `width`
cells east and `height` cells south.
"""

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

Cell = tuple[int, int]

SIDES = ("N", "E", "S", "W")
STEP = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}

FIXED_OBJECT_KINDS = ("blocked_tree", "blocked_rock", "quest_board")


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def cells(self) -> frozenset[Cell]:
        return frozenset(
            (self.x + dx, self.y + dy) for dy in range(self.height) for dx in range(self.width)
        )

    def contains(self, cell: Cell) -> bool:
        x, y = cell
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height

    def contains_rect(self, other: "Rect") -> bool:
        return other.cells() <= self.cells()

    @property
    def area(self) -> int:
        return self.width * self.height


def step(cell: Cell, side: str) -> Cell:
    dx, dy = STEP[side]
    return cell[0] + dx, cell[1] + dy


def edge_cells(rect: Rect, side: str) -> list[Cell]:
    """Cells just outside `rect` along one side: where a road touches that entrance edge."""
    if side == "N":
        return [(rect.x + dx, rect.y - 1) for dx in range(rect.width)]
    if side == "S":
        return [(rect.x + dx, rect.y + rect.height) for dx in range(rect.width)]
    if side == "W":
        return [(rect.x - 1, rect.y + dy) for dy in range(rect.height)]
    if side == "E":
        return [(rect.x + rect.width, rect.y + dy) for dy in range(rect.height)]
    raise ValueError(f"Unknown side {side!r}; use one of {', '.join(SIDES)}")


@dataclass(frozen=True)
class Layout:
    """The logical terrain of one world layout; identical in every theme."""

    layout_id: str
    width: int
    height: int
    water: frozenset[Cell]
    fixed_objects: dict[Cell, str]  # cell -> kind
    zones: dict[str, Rect]
    zone_unlocked_by: dict[str, str] = field(default_factory=dict)  # zone -> quest ID

    @property
    def bounds(self) -> Rect:
        return Rect(0, 0, self.width, self.height)

    @property
    def quest_board(self) -> Cell:
        return next(cell for cell, kind in self.fixed_objects.items() if kind == "quest_board")

    def in_bounds(self, cell: Cell) -> bool:
        return self.bounds.contains(cell)

    def is_water(self, cell: Cell) -> bool:
        return cell in self.water

    def is_buildable(self, cell: Cell) -> bool:
        """Land with no fixed object: buildings and roads may use it."""
        return self.in_bounds(cell) and cell not in self.water and cell not in self.fixed_objects

    def placement_problems(
        self,
        rect: Rect,
        *,
        zone: str | None = None,
        on_water: bool = False,
        occupied: Iterable[Cell] = (),
    ) -> list[str]:
        """Why a footprint cannot go here (empty list when it can).

        Codes: out_of_bounds, water, not_water, blocked, outside_zone, collision.
        """
        cells = rect.cells()
        if not cells <= self.bounds.cells():
            return ["out_of_bounds"]
        problems = []
        if on_water:
            if not cells <= self.water:
                problems.append("not_water")
        elif cells & self.water:
            problems.append("water")
        if any(cell in self.fixed_objects for cell in cells):
            problems.append("blocked")
        if zone is not None and not self.zones[zone].contains_rect(rect):
            problems.append("outside_zone")
        if cells & set(occupied):
            problems.append("collision")
        return problems


@dataclass(frozen=True)
class PlacedBuilding:
    building_id: str
    rect: Rect
    entrances: tuple[str, ...]
    is_bridge: bool = False


def reachable_from_quest_board(layout: Layout, placed: Iterable[PlacedBuilding]) -> set[Cell]:
    """Cells a road could reach from the quest board without crossing buildings or obstacles.

    Roads use buildable cells not covered by a building. A placed bridge carries the road across
    its water cells, entering and leaving only through its entrance sides.
    """
    placed = list(placed)
    occupied = {cell for building in placed if not building.is_bridge for cell in building.rect.cells()}
    bridges = [building for building in placed if building.is_bridge]
    bridge_cells = {cell for bridge in bridges for cell in bridge.rect.cells()}

    def passable(cell: Cell) -> bool:
        return (layout.is_buildable(cell) and cell not in occupied) or cell in bridge_cells

    def neighbours(cell: Cell):
        for side in SIDES:
            nxt = step(cell, side)
            if not passable(nxt):
                continue
            # Water crossings happen only along a bridge's entrance axis.
            if (cell in bridge_cells or nxt in bridge_cells) and side not in _bridge_axis(bridges, cell, nxt):
                continue
            yield nxt

    start = [step(layout.quest_board, side) for side in SIDES]
    seen = {cell for cell in start if passable(cell) and cell not in bridge_cells}
    queue = deque(seen)
    while queue:
        cell = queue.popleft()
        for nxt in neighbours(cell):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return seen


def _bridge_axis(bridges: list[PlacedBuilding], cell: Cell, nxt: Cell) -> set[str]:
    sides: set[str] = set()
    for bridge in bridges:
        if cell in bridge.rect.cells() or nxt in bridge.rect.cells():
            for entrance in bridge.entrances:
                sides.add(entrance)
                sides.add({"N": "S", "S": "N", "E": "W", "W": "E"}[entrance])
    return sides


def disconnected_buildings(layout: Layout, placed: Iterable[PlacedBuilding]) -> list[str]:
    """IDs of buildings with no entrance a road from the quest board could touch."""
    placed = list(placed)
    reach = reachable_from_quest_board(layout, placed)
    return [
        building.building_id
        for building in placed
        if not any(cell in reach for side in building.entrances for cell in edge_cells(building.rect, side))
    ]
