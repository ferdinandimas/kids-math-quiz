"""Road and shore autotile masks (N=1, E=2, S=4, W=8)."""

import pytest

from app.domain.kidquest.content import load_catalog
from app.domain.kidquest.roads import (
    MASK_SHAPES,
    mask_for,
    road_asset_id,
    road_mask,
    shore_asset_id,
    shore_mask,
    sides_for,
)


@pytest.mark.parametrize("mask", range(16))
def test_masks_round_trip(mask):
    assert mask_for(sides_for(mask)) == mask


def test_bits_and_shapes_follow_the_pipeline_table():
    assert [mask_for([side]) for side in "NESW"] == [1, 2, 4, 8]
    assert MASK_SHAPES[5] == "straight_vertical" and sides_for(5) == ["N", "S"]
    assert MASK_SHAPES[10] == "straight_horizontal" and sides_for(10) == ["E", "W"]
    assert MASK_SHAPES[15] == "four_way" and len(set(MASK_SHAPES.values())) == 16
    with pytest.raises(ValueError):
        sides_for(16)


def test_asset_ids_are_zero_padded():
    assert road_asset_id(5) == "road_basic--mask_05"
    assert shore_asset_id(12) == "shore--mask_12"


def test_road_mask_from_neighbouring_segments():
    roads = {(2, 2), (2, 1), (3, 2), (2, 3), (1, 2)}

    assert road_mask((2, 2), roads) == 15
    assert road_mask((2, 1), roads) == 4  # Only the cell to its south.
    assert road_mask((5, 5), roads) == 0


def test_shore_masks_for_pulau_tunas_v1():
    layout = load_catalog().layout

    assert shore_mask((3, 4), layout) == mask_for("NW")  # Land north and west.
    assert shore_mask((5, 4), layout) == mask_for("N")  # Bridge cell: land to the north only.
    assert shore_mask((3, 7), layout) == mask_for("EW")
    assert shore_mask((7, 5), layout) == mask_for("S")  # East edge of the map is not land.
    assert {shore_mask(cell, layout) for cell in layout.water} <= set(range(16))


def test_every_mask_has_a_road_and_shore_entry_in_content():
    roads = load_catalog().roads

    assert [entry["asset_id"] for entry in roads["road_masks"]] == [road_asset_id(m) for m in range(16)]
    assert [entry["asset_id"] for entry in roads["shore_masks"]] == [shore_asset_id(m) for m in range(16)]
    assert roads["max_segments_per_world"] == 48 and roads["unlocked_by_quest"] == "Q003"
