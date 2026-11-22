"""Four-direction autotile masks for roads and shores (bits N=1, E=2, S=4, W=8)."""

from collections.abc import Collection

from app.domain.kidquest.geometry import SIDES, Cell, Layout, step

BITS = {"N": 1, "E": 2, "S": 4, "W": 8}
MASK_COUNT = 16

# Pipeline section 13: the shape each mask must depict.
MASK_SHAPES = {
    0: "isolated",
    1: "end_cap_north",
    2: "end_cap_east",
    3: "corner_north_east",
    4: "end_cap_south",
    5: "straight_vertical",
    6: "corner_south_east",
    7: "t_junction_east",
    8: "end_cap_west",
    9: "corner_north_west",
    10: "straight_horizontal",
    11: "t_junction_north",
    12: "corner_south_west",
    13: "t_junction_west",
    14: "t_junction_south",
    15: "four_way",
}


def mask_for(sides: Collection[str]) -> int:
    return sum(BITS[side] for side in set(sides))


def sides_for(mask: int) -> list[str]:
    if not 0 <= mask < MASK_COUNT:
        raise ValueError(f"Mask must be 0-15, got {mask}")
    return [side for side in SIDES if mask & BITS[side]]


def road_asset_id(mask: int) -> str:
    return f"road_basic--mask_{mask:02d}"


def shore_asset_id(mask: int) -> str:
    return f"shore--mask_{mask:02d}"


def road_mask(cell: Cell, road_cells: Collection[Cell]) -> int:
    """Which neighbouring cells also hold a road segment."""
    return mask_for([side for side in SIDES if step(cell, side) in road_cells])


def shore_mask(cell: Cell, layout: Layout) -> int:
    """For a water cell: the sides that border land inside the map."""
    return mask_for(
        [side for side in SIDES if layout.in_bounds(step(cell, side)) and not layout.is_water(step(cell, side))]
    )
