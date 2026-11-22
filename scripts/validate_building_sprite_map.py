#!/usr/bin/env python3
"""Render and validate the frozen KidQuest building sprite-map contract.

Usage from the repository root:
    PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py IMAGE.png [--theme THEME_ID]
    PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py --check
    PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py --render-graybox IMAGE.png

The PNG codec is intentionally standard-library-only. It accepts the contract's required
non-interlaced, 8-bit RGBA/sRGB PNG and does not require Pillow or an external decoder.
"""

from __future__ import annotations

import argparse
import binascii
import json
import struct
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = REPO_ROOT / "content" / "kidquest" / "building_sprite_map.v1.json"
DEFAULT_SCHEMA = REPO_ROOT / "content" / "kidquest" / "building_sprite_map.schema.json"
DEFAULT_BUILDINGS = REPO_ROOT / "content" / "kidquest" / "buildings.json"
DEFAULT_GRAYBOX = REPO_ROOT / "design" / "kidquest" / "templates" / "building_sprite_map_graybox_v1.png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
OPAQUE_ALPHA_THRESHOLD = 16
WIDTH_RATIO_LIMITS = {(2, 2): 1.35, (1, 2): 1.60, (1, 1): 1.60}

THEMES = ("perkampungan", "kingdom", "city")
SLOT_IDS = ("starter_house", "garden", "bakery", "park", "bridge", "market_stall")

EXPECTED_SLOTS = (
    {"slot": 1, "row": 1, "column": 1, "rect": {"x": 0, "y": 0, "width": 512, "height": 512},
     "logical_id": "starter_house", "footprint": {"width": 2, "height": 2},
     "footprint_rect": {"x1": 128, "y1": 208, "x2": 384, "y2": 464},
     "anchor": {"x": 256, "y": 464}, "entrances": [{"side": "S", "x": 256, "y": 464}]},
    {"slot": 2, "row": 1, "column": 2, "rect": {"x": 512, "y": 0, "width": 512, "height": 512},
     "logical_id": "garden", "footprint": {"width": 2, "height": 2},
     "footprint_rect": {"x1": 128, "y1": 208, "x2": 384, "y2": 464},
     "anchor": {"x": 256, "y": 464}, "entrances": [{"side": "S", "x": 256, "y": 464}]},
    {"slot": 3, "row": 1, "column": 3, "rect": {"x": 1024, "y": 0, "width": 512, "height": 512},
     "logical_id": "bakery", "footprint": {"width": 2, "height": 2},
     "footprint_rect": {"x1": 128, "y1": 208, "x2": 384, "y2": 464},
     "anchor": {"x": 256, "y": 464}, "entrances": [{"side": "S", "x": 256, "y": 464}]},
    {"slot": 4, "row": 2, "column": 1, "rect": {"x": 0, "y": 512, "width": 512, "height": 512},
     "logical_id": "park", "footprint": {"width": 2, "height": 2},
     "footprint_rect": {"x1": 128, "y1": 208, "x2": 384, "y2": 464},
     "anchor": {"x": 256, "y": 464}, "entrances": [{"side": "S", "x": 256, "y": 464}]},
    {"slot": 5, "row": 2, "column": 2, "rect": {"x": 512, "y": 512, "width": 512, "height": 512},
     "logical_id": "bridge", "footprint": {"width": 1, "height": 2}, "long_axis": "north_south",
     "footprint_rect": {"x1": 192, "y1": 208, "x2": 320, "y2": 464},
     "anchor": {"x": 256, "y": 464},
     "entrances": [{"side": "N", "x": 256, "y": 208}, {"side": "S", "x": 256, "y": 464}]},
    {"slot": 6, "row": 2, "column": 3, "rect": {"x": 1024, "y": 512, "width": 512, "height": 512},
     "logical_id": "market_stall", "footprint": {"width": 1, "height": 1},
     "footprint_rect": {"x1": 192, "y1": 336, "x2": 320, "y2": 464},
     "anchor": {"x": 256, "y": 464}, "entrances": [{"side": "S", "x": 256, "y": 464}]},
)


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def add(self, message: str) -> None:
        self.problems.append(message)


@dataclass(frozen=True)
class PNGImage:
    width: int
    height: int
    rgba: bytes
    srgb_intent: int | None

    def alpha(self, x: int, y: int) -> int:
        return self.rgba[(y * self.width + x) * 4 + 3]


@dataclass(frozen=True)
class OpaqueWidthMetric:
    slot: int
    logical_id: str
    opaque_width: int
    footprint_width: int
    ratio: float
    limit: float


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_type_ok(value, expected: str) -> bool:
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }
    return checks[expected](value)


def schema_errors(value, schema: dict, where: str = "contract", root: dict | None = None) -> list[str]:
    """Validate the draft-2020-12 subset used by the committed contract schema."""
    root = schema if root is None else root
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            return [f"{where}: unsupported non-local schema reference {ref!r}"]
        target = root
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return schema_errors(value, target, where, root)

    errors: list[str] = []
    expected = schema.get("type")
    if expected is not None:
        allowed = expected if isinstance(expected, list) else [expected]
        if not any(_json_type_ok(value, item) for item in allowed):
            return [f"{where}: expected {' or '.join(allowed)}, got {json.dumps(value)}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{where}: expected frozen value {json.dumps(schema['const'])}, got {json.dumps(value)}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {json.dumps(value)} is not one of {schema['enum']}")

    if isinstance(value, str) and not isinstance(value, bool):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: string is shorter than {schema['minLength']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < schema.get("minimum", value):
            errors.append(f"{where}: {value} is below minimum {schema['minimum']}")
        if value > schema.get("maximum", value):
            errors.append(f"{where}: {value} is above maximum {schema['maximum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{where}: needs at most {schema['maxItems']} items")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            errors.append(f"{where}: items must be unique")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(schema_errors(item, schema["items"], f"{where}[{index}]", root))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required field {key!r}")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{where}: unknown field {key!r}")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(schema_errors(value[key], child_schema, f"{where}.{key}", root))
    return errors


def validate_contract(contract: dict, schema: dict, buildings: dict) -> list[str]:
    errors = schema_errors(contract, schema)
    if errors:
        return errors

    slots = contract["slots"]
    for index, (actual, expected) in enumerate(zip(slots, EXPECTED_SLOTS, strict=True), 1):
        if actual != expected:
            errors.append(f"contract.slots[{index - 1}]: slot {index} does not exactly match frozen v1 layout")

    rectangles = [slot["rect"] for slot in slots]
    covered: set[tuple[int, int]] = set()
    for slot, rect in zip(slots, rectangles, strict=True):
        if rect["width"] != 512 or rect["height"] != 512:
            errors.append(f"slot {slot['slot']}: slot size must be 512 x 512")
        cell = (rect["x"] // 512, rect["y"] // 512)
        if rect["x"] % 512 or rect["y"] % 512 or cell in covered:
            errors.append(f"slot {slot['slot']}: rectangle is not an exact non-overlapping grid tile")
        covered.add(cell)
    if covered != {(x, y) for y in range(2) for x in range(3)}:
        errors.append("slots do not tile the 1536 x 1024 canvas")

    catalog = buildings.get("buildings", [])
    ids = [building.get("id") for building in catalog]
    if ids != list(SLOT_IDS):
        errors.append(f"buildings.json order {ids} does not match frozen slot order {list(SLOT_IDS)}")
    by_id = {building.get("id"): building for building in catalog}
    for slot in slots:
        building = by_id.get(slot["logical_id"])
        if not building:
            errors.append(f"slot {slot['slot']}: logical_id is absent from buildings.json")
            continue
        if building.get("footprint") != slot["footprint"]:
            errors.append(f"slot {slot['slot']}: footprint disagrees with buildings.json")
        sides = [entry.get("side") for entry in building.get("entrances", [])]
        if sides != [entry["side"] for entry in slot["entrances"]]:
            errors.append(f"slot {slot['slot']}: entrances disagree with buildings.json")
        expected_anchor = {"x": slot["footprint"]["width"] / 2, "y": slot["footprint"]["height"]}
        if building.get("anchor") != expected_anchor:
            errors.append(f"slot {slot['slot']}: buildings.json anchor is not its footprint bottom-center")
        if building.get("visual_asset_key") != f"{slot['logical_id']}--base":
            errors.append(f"slot {slot['slot']}: visual_asset_key disagrees with logical_id")

    expected_overhangs = {
        "2x2": {"top_cells": 1.0, "top_px": 128},
        "1x2": {"top_cells": 0.25, "top_px": 32},
        "1x1": {"top_cells": 0.75, "top_px": 96},
    }
    if contract["overhang_profiles"] != expected_overhangs:
        errors.append("overhang_profiles do not match the adopted KQ-006 proposal")

    palette = contract["graybox_palette_rgba"]
    for name, rgba in palette.items():
        if not isinstance(rgba, list) or len(rgba) != 4 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in rgba):
            errors.append(f"graybox_palette_rgba.{name}: expected four 8-bit integers")

    checklist = contract["visual_checklist"]
    if set(checklist["per_building"]) != set(SLOT_IDS):
        errors.append("visual checklist must cover exactly the six logical building IDs")
    for building_id, item in checklist["per_building"].items():
        if set(item.get("theme_variants", {})) != set(THEMES):
            errors.append(f"visual checklist {building_id}: theme variants must cover all three themes")
        if not item.get("required_cues") or not item.get("prohibited_cues"):
            errors.append(f"visual checklist {building_id}: required and prohibited cues must be non-empty")
    shared = " ".join(checklist["shared"]).lower()
    for phrase in ("38", "48", "64", "currency", "indonesian cultural review"):
        if phrase not in shared:
            errors.append(f"visual checklist shared rules are missing {phrase!r}")
    return errors


def _chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def encode_png_rgba(width: int, height: int, rgba: bytes) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("RGBA byte count does not match dimensions")
    stride = width * 4
    scanlines = b"".join(b"\x00" + rgba[y * stride:(y + 1) * stride] for y in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b"IHDR", ihdr) + _chunk(b"sRGB", b"\x00") + _chunk(b"IDAT", zlib.compress(scanlines, 9)) + _chunk(b"IEND", b"")


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else b if pb <= pc else c


def decode_png_rgba(data: bytes) -> PNGImage:
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file (signature mismatch)")
    offset = len(PNG_SIGNATURE)
    ihdr: bytes | None = None
    srgb_intent: int | None = None
    idat = bytearray()
    saw_iend = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("truncated PNG chunk payload")
        payload = data[offset + 8:offset + 8 + length]
        stored_crc = struct.unpack(">I", data[offset + 8 + length:end])[0]
        if binascii.crc32(kind + payload) & 0xFFFFFFFF != stored_crc:
            raise ValueError(f"PNG chunk {kind.decode(errors='replace')} has a bad CRC")
        if kind == b"IHDR":
            if ihdr is not None or offset != len(PNG_SIGNATURE):
                raise ValueError("PNG must contain one first-position IHDR chunk")
            ihdr = payload
        elif kind == b"sRGB":
            if len(payload) != 1:
                raise ValueError("invalid sRGB chunk")
            srgb_intent = payload[0]
        elif kind == b"IDAT":
            idat.extend(payload)
        elif kind == b"IEND":
            if payload:
                raise ValueError("IEND chunk must be empty")
            saw_iend = True
            offset = end
            break
        elif kind[:1].isupper():
            raise ValueError(f"unsupported critical PNG chunk {kind.decode(errors='replace')}")
        offset = end
    if not ihdr or len(ihdr) != 13 or not saw_iend or offset != len(data):
        raise ValueError("PNG is missing a valid IHDR/IEND structure")
    width, height, depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
    if (depth, color_type, compression, filtering, interlace) != (8, 6, 0, 0, 0):
        raise ValueError("PNG must be non-interlaced 8-bit RGBA with standard compression and filtering")
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise ValueError(f"invalid PNG compressed data: {exc}") from exc
    stride = width * 4
    if len(raw) != height * (stride + 1):
        raise ValueError("PNG decompressed byte count does not match its dimensions")
    result = bytearray(width * height * 4)
    previous = bytearray(stride)
    source = 0
    for y in range(height):
        filter_type = raw[source]
        source += 1
        scanline = bytearray(raw[source:source + stride])
        source += stride
        if filter_type > 4:
            raise ValueError(f"unsupported PNG filter type {filter_type}")
        for x in range(stride):
            left = scanline[x - 4] if x >= 4 else 0
            up = previous[x]
            upper_left = previous[x - 4] if x >= 4 else 0
            if filter_type == 1:
                scanline[x] = (scanline[x] + left) & 0xFF
            elif filter_type == 2:
                scanline[x] = (scanline[x] + up) & 0xFF
            elif filter_type == 3:
                scanline[x] = (scanline[x] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                scanline[x] = (scanline[x] + _paeth(left, up, upper_left)) & 0xFF
        result[y * stride:(y + 1) * stride] = scanline
        previous = scanline
    return PNGImage(width, height, bytes(result), srgb_intent)


def _set_pixel(canvas: bytearray, width: int, x: int, y: int, color: tuple[int, int, int, int]) -> None:
    offset = (y * width + x) * 4
    canvas[offset:offset + 4] = bytes(color)


def _fill_rect(canvas: bytearray, width: int, x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int, int]) -> None:
    row = bytes(color) * max(0, x2 - x1)
    for y in range(y1, y2):
        offset = (y * width + x1) * 4
        canvas[offset:offset + len(row)] = row


def _hline(canvas: bytearray, width: int, x1: int, x2: int, y: int, color: tuple[int, int, int, int], dashed: bool = False) -> None:
    for x in range(x1, x2 + 1):
        if not dashed or ((x - x1) // 8) % 2 == 0:
            _set_pixel(canvas, width, x, y, color)


def _vline(canvas: bytearray, width: int, x: int, y1: int, y2: int, color: tuple[int, int, int, int]) -> None:
    for y in range(y1, y2 + 1):
        _set_pixel(canvas, width, x, y, color)


def _marker(canvas: bytearray, width: int, x: int, y: int, radius: int, color: tuple[int, int, int, int]) -> None:
    for dy in range(-radius, radius + 1):
        span = radius - abs(dy)
        for dx in range(-span, span + 1):
            _set_pixel(canvas, width, x + dx, y + dy, color)


def render_graybox_rgba(contract: dict) -> bytes:
    width, height = contract["canvas"]["width"], contract["canvas"]["height"]
    canvas = bytearray(width * height * 4)
    palette = {name: tuple(color) for name, color in contract["graybox_palette_rgba"].items()}
    bounds = contract["geometry"]["safe_bounds"]
    for slot in contract["slots"]:
        ox, oy = slot["rect"]["x"], slot["rect"]["y"]
        x1, y1, x2, y2 = (bounds[key] for key in ("x1", "y1", "x2", "y2"))
        _hline(canvas, width, ox + x1, ox + x2, oy + y1, palette["safe_padding"])
        _vline(canvas, width, ox + x1, oy + y1, oy + y2, palette["safe_padding"])
        _vline(canvas, width, ox + x2, oy + y1, oy + y2, palette["safe_padding"])
        _hline(canvas, width, ox + x1, ox + x2, oy + y2, palette["safe_padding"])
        _hline(canvas, width, ox + x1, ox + x2, oy + contract["geometry"]["shadow_limit_y"], palette["shadow_limit"], dashed=True)

        footprint = slot["footprint_rect"]
        profile = contract["overhang_profiles"][f"{slot['footprint']['width']}x{slot['footprint']['height']}"]
        mass_top = footprint["y1"] - profile["top_px"]
        _fill_rect(canvas, width, ox + footprint["x1"], oy + mass_top,
                   ox + footprint["x2"], oy + footprint["y2"], palette["mass"])
        _fill_rect(canvas, width, ox + footprint["x1"], oy + footprint["y1"],
                   ox + footprint["x2"], oy + footprint["y2"], palette["footprint"])
        _hline(canvas, width, ox + footprint["x1"], ox + footprint["x2"], oy + footprint["y1"], palette["footprint_outline"])
        _hline(canvas, width, ox + footprint["x1"], ox + footprint["x2"], oy + footprint["y2"], palette["footprint_outline"])
        _vline(canvas, width, ox + footprint["x1"], oy + footprint["y1"], oy + footprint["y2"], palette["footprint_outline"])
        _vline(canvas, width, ox + footprint["x2"], oy + footprint["y1"], oy + footprint["y2"], palette["footprint_outline"])
        for entrance in slot["entrances"]:
            _marker(canvas, width, ox + entrance["x"], oy + entrance["y"], 7, palette["entrance"])
        anchor = slot["anchor"]
        _hline(canvas, width, ox + anchor["x"] - 9, ox + anchor["x"] + 9, oy + anchor["y"], palette["anchor"])
        _vline(canvas, width, ox + anchor["x"], oy + anchor["y"] - 9, oy + anchor["y"] + 9, palette["anchor"])
    return bytes(canvas)


def render_graybox_png(contract: dict) -> bytes:
    return encode_png_rgba(contract["canvas"]["width"], contract["canvas"]["height"], render_graybox_rgba(contract))


def _window_has_alpha(image: PNGImage, x: int, y: int, radius: int = 2) -> bool:
    return any(image.alpha(px, py) > 0
               for py in range(max(0, y - radius), min(image.height, y + radius + 1))
               for px in range(max(0, x - radius), min(image.width, x + radius + 1)))


def _alpha_geometry_errors(image: PNGImage, contract: dict) -> list[str]:
    errors: list[str] = []
    rgba = image.rgba
    halo_count = sum(1 for offset in range(0, len(rgba), 4) if rgba[offset + 3] == 0 and rgba[offset:offset + 3] != b"\x00\x00\x00")
    if halo_count:
        errors.append(f"transparent pixels retain matte RGB color ({halo_count} pixel(s)); alpha-zero RGB must be 0,0,0")

    bounds = contract["geometry"]["safe_bounds"]
    for slot in contract["slots"]:
        ox, oy = slot["rect"]["x"], slot["rect"]["y"]
        outside = 0
        for local_y in range(512):
            for local_x in range(512):
                if (local_x < bounds["x1"] or local_x > bounds["x2"] or
                        local_y < bounds["y1"] or local_y > bounds["y2"]):
                    outside += image.alpha(ox + local_x, oy + local_y) > 0
        if outside:
            errors.append(f"slot {slot['slot']} ({slot['logical_id']}): {outside} pixel(s) have content outside the safe area/in slot padding")

        anchor = slot["anchor"]
        if not _window_has_alpha(image, ox + anchor["x"], oy + anchor["y"]):
            errors.append(f"slot {slot['slot']} ({slot['logical_id']}): no content at anchor ({anchor['x']}, {anchor['y']})")
        for entrance in slot["entrances"]:
            if not _window_has_alpha(image, ox + entrance["x"], oy + entrance["y"]):
                errors.append(f"slot {slot['slot']} ({slot['logical_id']}): no content at {entrance['side']} entrance ({entrance['x']}, {entrance['y']})")

        footprint = slot["footprint_rect"]
        for cell_y in range(slot["footprint"]["height"]):
            for cell_x in range(slot["footprint"]["width"]):
                cell_x1 = ox + footprint["x1"] + cell_x * 128
                cell_y1 = oy + footprint["y1"] + cell_y * 128
                count = sum(image.alpha(x, y) > 0 for y in range(cell_y1, cell_y1 + 128) for x in range(cell_x1, cell_x1 + 128))
                if count < 164:
                    errors.append(f"slot {slot['slot']} ({slot['logical_id']}): footprint cell ({cell_x}, {cell_y}) lacks a visible overlay/content")

    partial_exists = any(0 < rgba[offset + 3] < 255 for offset in range(0, len(rgba), 4))
    if partial_exists:
        visited = bytearray(image.width * image.height)
        for start in range(image.width * image.height):
            if visited[start] or rgba[start * 4 + 3] == 0:
                continue
            stack = [start]
            visited[start] = 1
            has_opaque = False
            has_partial = False
            while stack:
                index = stack.pop()
                alpha = rgba[index * 4 + 3]
                has_opaque |= alpha == 255
                has_partial |= alpha != 255
                x, y = index % image.width, index // image.width
                for neighbor in (index - 1 if x else -1, index + 1 if x + 1 < image.width else -1,
                                 index - image.width if y else -1,
                                 index + image.width if y + 1 < image.height else -1):
                    if neighbor >= 0 and not visited[neighbor] and rgba[neighbor * 4 + 3] > 0:
                        visited[neighbor] = 1
                        stack.append(neighbor)
            if has_partial and not has_opaque:
                errors.append("semi-transparent component is not connected to opaque artwork (background/halo)")
                break
    return errors


def opaque_width_metrics(image: PNGImage, contract: dict) -> list[OpaqueWidthMetric]:
    """Measure visible slot width at the lead-review alpha threshold."""
    metrics: list[OpaqueWidthMetric] = []
    for slot in contract["slots"]:
        rect = slot["rect"]
        visible_x = [
            local_x
            for local_y in range(rect["height"])
            for local_x in range(rect["width"])
            if image.alpha(rect["x"] + local_x, rect["y"] + local_y) > OPAQUE_ALPHA_THRESHOLD
        ]
        opaque_width = max(visible_x) - min(visible_x) + 1 if visible_x else 0
        footprint = slot["footprint"]
        footprint_width = slot["footprint_rect"]["x2"] - slot["footprint_rect"]["x1"]
        limit = WIDTH_RATIO_LIMITS[(footprint["width"], footprint["height"])]
        metrics.append(OpaqueWidthMetric(
            slot=slot["slot"],
            logical_id=slot["logical_id"],
            opaque_width=opaque_width,
            footprint_width=footprint_width,
            ratio=opaque_width / footprint_width,
            limit=limit,
        ))
    return metrics


def _opaque_width_errors(metrics: list[OpaqueWidthMetric]) -> list[str]:
    return [
        (f"slot {metric.slot} ({metric.logical_id}): opaque width {metric.opaque_width} px / "
         f"footprint width {metric.footprint_width} px = {metric.ratio:.3f}x exceeds {metric.limit:.2f}x")
        for metric in metrics
        if metric.ratio > metric.limit
    ]


def validate_sprite_map(path: Path, theme: str | None = None, *, contract_path: Path = DEFAULT_CONTRACT,
                        schema_path: Path = DEFAULT_SCHEMA, buildings_path: Path = DEFAULT_BUILDINGS) -> Report:
    report = Report()
    try:
        contract, schema, buildings = load_json(contract_path), load_json(schema_path), load_json(buildings_path)
    except (OSError, json.JSONDecodeError) as exc:
        report.add(f"could not load contract inputs: {exc}")
        return report
    contract_problems = validate_contract(contract, schema, buildings)
    if contract_problems:
        report.problems.extend(contract_problems)
        return report
    if theme is not None and theme not in contract["theme_ids"]:
        report.add(f"unknown theme {theme!r}; expected one of {contract['theme_ids']}")
        return report
    try:
        image = decode_png_rgba(Path(path).read_bytes())
    except (OSError, ValueError) as exc:
        report.add(f"{path}: {exc}")
        return report
    expected_size = (contract["canvas"]["width"], contract["canvas"]["height"])
    if (image.width, image.height) != expected_size:
        report.add(f"canvas is {image.width} x {image.height}; expected {expected_size[0]} x {expected_size[1]}")
        return report
    if image.srgb_intent != 0:
        report.add("PNG must declare sRGB rendering intent 0")
    report.problems.extend(_alpha_geometry_errors(image, contract))
    width_summary: list[str] = []
    if theme is not None:
        metrics = opaque_width_metrics(image, contract)
        report.problems.extend(_opaque_width_errors(metrics))
        width_summary = [
            (f"slot {metric.slot} {metric.logical_id}: opaque width {metric.opaque_width} px / "
             f"footprint width {metric.footprint_width} px = {metric.ratio:.3f}x "
             f"(limit {metric.limit:.2f}x)")
            for metric in metrics
        ]
    if theme is None:
        expected_pixels = render_graybox_rgba(contract)
        if image.rgba != expected_pixels:
            differing = sum(a != b for a, b in zip(image.rgba, expected_pixels, strict=True))
            report.add(f"graybox footprint/anchor/entrance overlays differ from the contract ({differing} channel byte(s))")
    if report.ok:
        profile = "graybox reference" if theme is None else f"theme {theme}"
        report.summary.append(
            f"{profile}: 1536 x 1024 RGBA/sRGB; six slots; padding, alpha, footprint, anchor, entrances, and opaque widths valid"
        )
    report.summary.extend(width_summary)
    return report


def _print_report(report: Report) -> int:
    if report.ok:
        for line in report.summary:
            print(f"Building sprite map OK: {line}")
        return 0
    for line in report.summary:
        print(f"Building sprite map metric: {line}")
    print(f"Building sprite map INVALID ({len(report.problems)} problem(s)):", file=sys.stderr)
    for problem in report.problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("png", nargs="?", type=Path, help="sprite-map PNG to validate")
    parser.add_argument("--theme", choices=THEMES, help="validate a production theme map; omit for strict graybox overlay validation")
    parser.add_argument("--check", action="store_true", help="prove the committed graybox is the deterministic contract render")
    parser.add_argument("--render-graybox", type=Path, metavar="PATH", help="write a deterministic graybox PNG")
    args = parser.parse_args(argv)
    selected = sum((args.png is not None, args.check, args.render_graybox is not None))
    if selected != 1:
        parser.error("choose exactly one of IMAGE.png, --check, or --render-graybox PATH")

    contract, schema, buildings = load_json(DEFAULT_CONTRACT), load_json(DEFAULT_SCHEMA), load_json(DEFAULT_BUILDINGS)
    contract_problems = validate_contract(contract, schema, buildings)
    if contract_problems:
        return _print_report(Report(problems=contract_problems))
    expected = render_graybox_png(contract)
    if args.render_graybox is not None:
        args.render_graybox.parent.mkdir(parents=True, exist_ok=True)
        args.render_graybox.write_bytes(expected)
        print(f"Wrote deterministic graybox: {args.render_graybox} ({len(expected)} bytes)")
        return 0
    if args.check:
        try:
            actual = DEFAULT_GRAYBOX.read_bytes()
        except OSError as exc:
            return _print_report(Report(problems=[f"could not read {DEFAULT_GRAYBOX}: {exc}"]))
        if actual != expected:
            return _print_report(Report(problems=[f"{DEFAULT_GRAYBOX} is not the byte-exact deterministic contract render; regenerate with --render-graybox"]))
        report = validate_sprite_map(DEFAULT_GRAYBOX)
        if report.ok:
            report.summary.append(f"deterministic bytes match committed graybox ({len(actual)} bytes)")
        return _print_report(report)
    return _print_report(validate_sprite_map(args.png, args.theme))


if __name__ == "__main__":
    raise SystemExit(main())
