"""Coordinate convention, placement rules, connectivity, and the pulau_tunas_v1 zones."""

import pytest

from app.domain.kidquest.content import find_core_arrangement, load_catalog, tutorial_placements
from app.domain.kidquest.geometry import (
    Layout,
    PlacedBuilding,
    Rect,
    disconnected_buildings,
    edge_cells,
    reachable_from_quest_board,
    step,
)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture(scope="module")
def layout(catalog):
    return catalog.layout


# --- Convention ---------------------------------------------------------------------------------


def test_x_grows_east_and_y_grows_south_from_the_north_west_corner():
    assert step((3, 3), "N") == (3, 2)
    assert step((3, 3), "S") == (3, 4)
    assert step((3, 3), "E") == (4, 3)
    assert step((3, 3), "W") == (2, 3)


def test_a_footprint_position_is_its_top_left_cell():
    house = Rect(2, 1, 2, 2)

    assert house.cells() == {(2, 1), (3, 1), (2, 2), (3, 2)}
    assert house.contains((3, 2)) and not house.contains((4, 1)) and not house.contains((2, 3))


def test_edge_cells_are_just_outside_each_side():
    house = Rect(2, 1, 2, 2)

    assert edge_cells(house, "S") == [(2, 3), (3, 3)]
    assert edge_cells(house, "N") == [(2, 0), (3, 0)]
    assert edge_cells(house, "E") == [(4, 1), (4, 2)]
    assert edge_cells(house, "W") == [(1, 1), (1, 2)]
    with pytest.raises(ValueError):
        edge_cells(house, "X")


# --- pulau_tunas_v1 -------------------------------------------------------------------------------


def test_pulau_tunas_v1_terrain(layout):
    assert (layout.layout_id, layout.width, layout.height) == ("pulau_tunas_v1", 8, 8)
    assert layout.water == {(x, y) for y in (4, 5) for x in range(3, 8)} | {(3, 6), (3, 7)}
    assert layout.fixed_objects == {
        (0, 0): "blocked_tree",
        (7, 0): "blocked_tree",
        (4, 3): "quest_board",
        (0, 7): "blocked_rock",
        (7, 7): "blocked_tree",
    }
    assert layout.quest_board == (4, 3)


def test_pulau_tunas_v1_zones(layout):
    assert layout.zones == {
        "tutorial_zone": Rect(1, 1, 4, 2),
        "bridge_zone": Rect(5, 4, 1, 2),
        "expansion_zone": Rect(4, 6, 4, 2),
    }
    assert layout.zone_unlocked_by == {"expansion_zone": "Q005"}


def test_tutorial_zone_offers_three_starter_house_positions(catalog, layout):
    spots = tutorial_placements(layout, catalog.buildings["starter_house"])

    assert spots == [Rect(1, 1, 2, 2), Rect(2, 1, 2, 2), Rect(3, 1, 2, 2)]


def test_bridge_zone_crosses_water_between_two_land_ends(layout):
    zone = layout.zones["bridge_zone"]

    assert zone.cells() == {(5, 4), (5, 5)} and zone.cells() <= layout.water
    assert layout.is_buildable((5, 3)) and layout.is_buildable((5, 6))
    assert all(layout.is_water(cell) for cell in [(4, 4), (6, 4), (4, 5), (6, 5)])


def test_expansion_zone_opens_only_across_the_bridge(catalog, layout):
    bridge = PlacedBuilding("bridge", layout.zones["bridge_zone"], ("N", "S"), is_bridge=True)
    expansion = layout.zones["expansion_zone"].cells() - set(layout.fixed_objects)

    assert not expansion & reachable_from_quest_board(layout, [])
    assert expansion <= reachable_from_quest_board(layout, [bridge])


@pytest.mark.parametrize(
    "rect, kwargs, expected",
    [
        (Rect(1, 1, 2, 2), {"zone": "tutorial_zone"}, []),
        (Rect(7, 1, 2, 2), {}, ["out_of_bounds"]),
        (Rect(3, 3, 2, 2), {}, ["water", "blocked"]),  # Covers the river and the quest board.
        (Rect(0, 0, 2, 2), {}, ["blocked"]),
        (Rect(4, 1, 2, 2), {"zone": "tutorial_zone"}, ["outside_zone"]),
        (Rect(1, 1, 2, 2), {"occupied": {(2, 2)}}, ["collision"]),
        (Rect(5, 4, 1, 2), {"zone": "bridge_zone", "on_water": True}, []),
        (Rect(1, 4, 1, 2), {"on_water": True}, ["not_water"]),
    ],
)
def test_placement_problems(layout, rect, kwargs, expected):
    assert layout.placement_problems(rect, **kwargs) == expected


def test_every_tutorial_choice_leaves_room_for_the_whole_core_catalog(catalog, layout):
    for spot in tutorial_placements(layout, catalog.buildings["starter_house"]):
        arrangement = find_core_arrangement(layout, catalog.buildings, catalog.quest_order, {"starter_house": spot})

        assert arrangement is not None and arrangement["starter_house"] == spot
        assert set(arrangement) == set(catalog.buildings)
        cells = [cell for rect in arrangement.values() for cell in rect.cells()]
        assert len(cells) == len(set(cells))  # No overlaps.
        assert arrangement["bridge"] == layout.zones["bridge_zone"]
        expansion = layout.zones["expansion_zone"].cells()
        for building_id in ("starter_house", "garden", "bakery", "park"):
            assert not arrangement[building_id].cells() & expansion  # Locked until Q005.
        placed = [
            PlacedBuilding(bid, rect, catalog.buildings[bid].entrances, is_bridge=bid == "bridge")
            for bid, rect in arrangement.items()
        ]
        assert disconnected_buildings(layout, placed) == []


def test_a_building_whose_entrance_faces_water_is_disconnected(layout):
    blocked = PlacedBuilding("park", Rect(1, 2, 2, 2), ("S",))  # South edge is (1,4),(2,4): land.
    facing_water = PlacedBuilding("garden", Rect(4, 2, 2, 2), ("S",))  # South edge is river.

    assert disconnected_buildings(layout, [blocked]) == []
    assert disconnected_buildings(layout, [facing_water]) == ["garden"]


def test_roads_cross_water_only_along_the_bridge_axis():
    layout = Layout(
        layout_id="t",
        width=3,
        height=3,
        water=frozenset({(0, 1), (1, 1), (2, 1)}),
        fixed_objects={(0, 0): "quest_board"},
        zones={"bridge_zone": Rect(1, 1, 1, 1)},
    )
    bridge = PlacedBuilding("bridge", Rect(1, 1, 1, 1), ("N", "S"), is_bridge=True)

    assert (1, 2) not in reachable_from_quest_board(layout, [])
    assert {(1, 1), (1, 2), (0, 2), (2, 2)} <= reachable_from_quest_board(layout, [bridge])
