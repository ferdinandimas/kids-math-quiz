"""KQ-025 frozen building sprite-map contract, renderer, and validator."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "validate_building_sprite_map.py"
CONTRACT_PATH = REPO_ROOT / "content" / "kidquest" / "building_sprite_map.v1.json"
SCHEMA_PATH = REPO_ROOT / "content" / "kidquest" / "building_sprite_map.schema.json"
BUILDINGS_PATH = REPO_ROOT / "content" / "kidquest" / "buildings.json"
GRAYBOX_PATH = REPO_ROOT / "design" / "kidquest" / "templates" / "building_sprite_map_graybox_v1.png"
THEME_PATHS = {
    "perkampungan": REPO_ROOT / "design" / "kidquest" / "sprite-maps" / "perkampungan" / "buildings_v1.png",
    "kingdom": REPO_ROOT / "design" / "kidquest" / "sprite-maps" / "kingdom" / "buildings_v1.png",
    "city": REPO_ROOT / "design" / "kidquest" / "sprite-maps" / "city" / "buildings_v1.png",
}
TASK_PACKET = REPO_ROOT / "docs" / "tasks" / "KQ-025-building-sprite-map-contract.md"
THEME_TASK_PACKETS = (
    REPO_ROOT / "docs" / "tasks" / "KQ-026-kingdom-building-sprite-map.md",
    REPO_ROOT / "docs" / "tasks" / "KQ-027-city-building-sprite-map.md",
    REPO_ROOT / "docs" / "tasks" / "KQ-028-kampung-building-sprite-map.md",
)

_spec = importlib.util.spec_from_file_location("validate_building_sprite_map", SCRIPT)
validator = importlib.util.module_from_spec(_spec)
sys.modules["validate_building_sprite_map"] = validator
_spec.loader.exec_module(validator)


@pytest.fixture(scope="module")
def contract():
    return json.loads(CONTRACT_PATH.read_text())


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


@pytest.fixture(scope="module")
def buildings():
    return json.loads(BUILDINGS_PATH.read_text())


@pytest.fixture(scope="module")
def graybox_image():
    return validator.decode_png_rgba(GRAYBOX_PATH.read_bytes())


def assert_problem(report, fragment: str) -> None:
    assert not report.ok, "expected validation failure"
    text = "\n".join(report.problems)
    assert fragment in text, text


def save_mutation(tmp_path: Path, image, mutate, name: str = "mutated.png") -> Path:
    rgba = bytearray(image.rgba)
    mutate(rgba, image.width, image.height)
    path = tmp_path / name
    path.write_bytes(validator.encode_png_rgba(image.width, image.height, bytes(rgba)))
    return path


def set_pixel(rgba: bytearray, width: int, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    offset = (y * width + x) * 4
    rgba[offset:offset + 4] = bytes(color)


def test_committed_contract_matches_schema_and_buildings(contract, schema, buildings):
    assert validator.validate_contract(contract, schema, buildings) == []
    assert [slot["logical_id"] for slot in contract["slots"]] == [building["id"] for building in buildings["buildings"]]
    assert [slot["footprint"] for slot in contract["slots"]] == [building["footprint"] for building in buildings["buildings"]]


@pytest.mark.parametrize(
    ("mutation", "fragment"),
    [
        (lambda item: item["canvas"].update(width=1535), "contract.canvas.width"),
        (lambda item: item["slots"][0]["anchor"].update(x=255), "contract.slots[0].anchor.x"),
        (lambda item: item["slots"][0].pop("rect"), "missing required field 'rect'"),
        (lambda item: item.update(unfrozen=True), "unknown field 'unfrozen'"),
        (lambda item: item["outline"].update(minimum=3), "contract.outline.minimum"),
    ],
)
def test_schema_rejects_each_invalid_mutation(contract, schema, buildings, mutation, fragment):
    invalid = copy.deepcopy(contract)
    mutation(invalid)
    assert fragment in "\n".join(validator.validate_contract(invalid, schema, buildings))


def test_semantic_validation_rejects_slot_order_and_footprint_drift(contract, schema, buildings):
    wrong_order = copy.deepcopy(contract)
    wrong_order["slots"][0], wrong_order["slots"][1] = wrong_order["slots"][1], wrong_order["slots"][0]
    assert "does not exactly match frozen v1 layout" in "\n".join(validator.validate_contract(wrong_order, schema, buildings))

    wrong_footprint = copy.deepcopy(contract)
    wrong_footprint["slots"][5]["footprint_rect"]["y1"] = 335
    assert "does not exactly match frozen v1 layout" in "\n".join(validator.validate_contract(wrong_footprint, schema, buildings))


def test_semantic_validation_cross_checks_buildings_json(contract, schema, buildings):
    invalid_buildings = copy.deepcopy(buildings)
    invalid_buildings["buildings"][4]["footprint"] = {"width": 2, "height": 1}
    errors = "\n".join(validator.validate_contract(contract, schema, invalid_buildings))
    assert "footprint disagrees with buildings.json" in errors


def test_frozen_slots_tile_canvas_and_share_scale_anchor_padding(contract):
    rects = [slot["rect"] for slot in contract["slots"]]
    assert rects == [
        {"x": 0, "y": 0, "width": 512, "height": 512},
        {"x": 512, "y": 0, "width": 512, "height": 512},
        {"x": 1024, "y": 0, "width": 512, "height": 512},
        {"x": 0, "y": 512, "width": 512, "height": 512},
        {"x": 512, "y": 512, "width": 512, "height": 512},
        {"x": 1024, "y": 512, "width": 512, "height": 512},
    ]
    assert contract["geometry"]["world_cell_px_at_2x"] == 128
    assert contract["geometry"]["safe_padding_px"] == 32
    assert all(slot["anchor"] == {"x": 256, "y": 464} for slot in contract["slots"])
    assert [entry["side"] for entry in contract["slots"][4]["entrances"]] == ["N", "S"]
    assert all([entry["side"] for entry in slot["entrances"]] == ["S"]
               for slot in contract["slots"] if slot["logical_id"] != "bridge")


def test_theme_task_packets_embed_the_identical_frozen_slot_table():
    def table_rows(path: Path) -> list[str]:
        rows = [line for line in path.read_text().splitlines()
                if any(line.startswith(f"| {slot} |") for slot in range(1, 7))]
        return rows[:6]

    frozen = table_rows(TASK_PACKET)
    assert len(frozen) == 6
    assert all(table_rows(path) == frozen for path in THEME_TASK_PACKETS)


def test_responsive_proof_math_keeps_anchor_at_footprint_bottom_center(contract):
    for cell_px in (38, 48, 64):
        scale = cell_px / contract["geometry"]["world_cell_px_at_2x"]
        for slot in contract["slots"]:
            footprint = slot["footprint_rect"]
            center_x = (footprint["x1"] + footprint["x2"]) / 2 * scale
            bottom_y = footprint["y2"] * scale
            assert (center_x, bottom_y) == (slot["anchor"]["x"] * scale, slot["anchor"]["y"] * scale)


def test_graybox_is_byte_deterministic_and_decodes_to_contract_render(contract, graybox_image):
    expected_pixels = validator.render_graybox_rgba(contract)
    expected_png = validator.render_graybox_png(contract)
    assert GRAYBOX_PATH.read_bytes() == expected_png
    assert graybox_image.rgba == expected_pixels


def test_graybox_slices_and_reassembles_pixel_perfectly(graybox_image):
    stride = graybox_image.width * 4
    slices = []
    for row in range(2):
        for column in range(3):
            sprite = bytearray()
            for y in range(row * 512, (row + 1) * 512):
                start = y * stride + column * 512 * 4
                sprite.extend(graybox_image.rgba[start:start + 512 * 4])
            slices.append(bytes(sprite))
    reassembled = bytearray(len(graybox_image.rgba))
    for index, sprite in enumerate(slices):
        row, column = divmod(index, 3)
        for local_y in range(512):
            source = local_y * 512 * 4
            target = ((row * 512 + local_y) * graybox_image.width + column * 512) * 4
            reassembled[target:target + 512 * 4] = sprite[source:source + 512 * 4]
    assert bytes(reassembled) == graybox_image.rgba


def test_validator_accepts_committed_graybox_and_theme_profile():
    reference = validator.validate_sprite_map(GRAYBOX_PATH)
    assert reference.ok, reference.problems
    themed = validator.validate_sprite_map(THEME_PATHS["perkampungan"], "perkampungan")
    assert themed.ok, themed.problems


def test_validator_accepts_all_committed_theme_width_ratios():
    for theme, path in THEME_PATHS.items():
        report = validator.validate_sprite_map(path, theme)
        assert report.ok, report.problems
        ratios = [line for line in report.summary if line.startswith("slot ")]
        assert len(ratios) == 6
        assert all("opaque width" in line and "limit" in line for line in ratios)


def test_validator_rejects_synthetic_oversized_sprite(tmp_path, graybox_image):
    def widen_first_slot(rgba, width, _height):
        for x in range(32, 481):
            set_pixel(rgba, width, x, 100, (20, 52, 62, 255))

    path = save_mutation(tmp_path, graybox_image, widen_first_slot, "oversized.png")
    report = validator.validate_sprite_map(path, "city")
    assert_problem(report, "opaque width 449 px / footprint width 256 px")
    assert_problem(report, "exceeds 1.35x")


def test_validator_rejects_wrong_size(tmp_path, graybox_image):
    cropped = bytearray()
    for y in range(graybox_image.height):
        start = y * graybox_image.width * 4
        cropped.extend(graybox_image.rgba[start:start + 1535 * 4])
    path = tmp_path / "wrong-size.png"
    path.write_bytes(validator.encode_png_rgba(1535, 1024, bytes(cropped)))
    assert_problem(validator.validate_sprite_map(path), "expected 1536 x 1024")


def test_validator_rejects_content_in_padding(tmp_path, graybox_image):
    path = save_mutation(tmp_path, graybox_image, lambda rgba, width, _height: set_pixel(rgba, width, 0, 0, (10, 20, 30, 255)))
    assert_problem(validator.validate_sprite_map(path), "content outside the safe area/in slot padding")


def test_validator_rejects_content_outside_slot_safe_bounds(tmp_path, graybox_image):
    path = save_mutation(tmp_path, graybox_image, lambda rgba, width, _height: set_pixel(rgba, width, 511, 200, (10, 20, 30, 255)))
    assert_problem(validator.validate_sprite_map(path), "slot 1 (starter_house)")


def test_validator_rejects_opaque_background(tmp_path, graybox_image):
    def opaque_background(rgba, width, height):
        for y in range(8):
            for x in range(width):
                set_pixel(rgba, width, x, y, (20, 20, 20, 255))

    path = save_mutation(tmp_path, graybox_image, opaque_background)
    assert_problem(validator.validate_sprite_map(path), "content outside the safe area/in slot padding")


def test_validator_rejects_shifted_anchor_overlay(tmp_path, graybox_image, contract):
    anchor_color = bytes(contract["graybox_palette_rgba"]["anchor"])

    def shift_anchor(rgba, width, _height):
        for y in range(455, 474):
            for x in range(247, 266):
                offset = (y * width + x) * 4
                if rgba[offset:offset + 4] == anchor_color:
                    rgba[offset:offset + 4] = bytes(contract["graybox_palette_rgba"]["footprint_outline"])
                    rgba[offset + 8:offset + 12] = anchor_color

    path = save_mutation(tmp_path, graybox_image, shift_anchor)
    assert_problem(validator.validate_sprite_map(path), "graybox footprint/anchor/entrance overlays differ")


def test_validator_rejects_matte_halo_rgb(tmp_path, graybox_image):
    path = save_mutation(tmp_path, graybox_image, lambda rgba, width, _height: set_pixel(rgba, width, 10, 10, (255, 255, 255, 0)))
    assert_problem(validator.validate_sprite_map(path), "matte RGB color")


def test_validator_rejects_isolated_semi_transparent_background(tmp_path, graybox_image):
    path = save_mutation(tmp_path, graybox_image, lambda rgba, width, _height: set_pixel(rgba, width, 50, 50, (80, 80, 80, 100)))
    assert_problem(validator.validate_sprite_map(path), "semi-transparent component is not connected to opaque artwork")


def test_cli_check_and_exit_codes(tmp_path, graybox_image):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    checked = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True, env=env, check=False)
    assert checked.returncode == 0, checked.stderr
    assert "deterministic bytes match" in checked.stdout

    bad = save_mutation(tmp_path, graybox_image, lambda rgba, width, _height: set_pixel(rgba, width, 0, 0, (0, 0, 0, 255)))
    rejected = subprocess.run([sys.executable, str(SCRIPT), str(bad)], capture_output=True, text=True, env=env, check=False)
    assert rejected.returncode == 1
    assert "outside the safe area" in rejected.stderr
