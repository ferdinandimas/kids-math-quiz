#!/usr/bin/env python3
"""Validate the KidQuest runtime asset manifests and exported images.

Usage (from the repository root):
    python scripts/validate_kidquest_assets.py [--profile golden|buildings|complete] [--static-dir PATH]
        [--content-dir PATH] [--source-metadata PATH] [--structural-only]

Checks (pipeline sections 11, 13, 14.3, 18.4, 18.6 and Stage I gate):
  * every theme in content/kidquest/themes.json has a manifest whose entries follow
    content/kidquest/assets.schema.json and the runtime path rule in themes.json `runtime_assets`;
  * naming (`{asset_id}--{variant}@2x.webp`, snake case, zero-padded masks);
  * every asset the profile requires is present in all three themes;
  * each file exists, is a real WebP, has the declared dimensions (pixel size = 2 x CSS size),
    the declared alpha, stays inside its byte budget, and matches its checksum;
  * footprint, anchor, overhang, entrances and collision are identical across themes and agree with
    the logical content (buildings.json, layouts, roads.json);
  * pixel checks: transparent corners where alpha is required, fully opaque terrain, road edge
    profiles that meet at the edge midpoint with the same width and colour for every connecting pair
    of the 16 masks, shore masks whose land/water edges match the mask, identical road silhouettes
    and aligned anchored props across themes;
  * shared overlays (SVG) exist, are safe and match their checksums; source records exist and no
    asset claims approval without a recorded review;
  * byte totals per theme against the pipeline 18.6 budgets.

Profiles: `golden` (default) is the unchanged KQ-006 golden non-building set. `buildings` is the
KQ-029 six-building set in each theme. `complete` requires all 56 logical assets per theme.

Pixel checks decode WebP with Pillow when it is installed, otherwise with the `dwebp` command
(libwebp). With neither, the run fails unless --structural-only is passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTENT = REPO_ROOT / "content" / "kidquest"
DEFAULT_STATIC = REPO_ROOT / "static" / "images" / "kidquest"
DEFAULT_SOURCE_METADATA = REPO_ROOT / "design" / "kidquest" / "source-metadata.json"
RUNTIME_PREFIX = "static/images/kidquest/"

CELL_PX = 128               # one cell at @2x
KB = 1024
# Pipeline 18.6 budgets, measured after compression.
BUDGETS = {
    "critical_first_world": 650 * KB,
    "theme_pack": int(2.5 * KB * KB),
    "tile": 32 * KB,                    # every terrain, shore and road mask
    "building_2x2": 180 * KB,
    "non_selected_thumbnails": 180 * KB,
}
TILE_CATEGORIES = {"terrain", "shore", "road"}

# KQ-006 golden non-building set (plan 7A M3A; pipeline Stage G). Keys are themes.json
# `runtime_assets.directories` groups; "all" = every asset roads.json derives for that group.
GOLDEN = {
    "terrain": ["ground_buildable--base", "water--base"],
    "shore_masks": "all",
    "road_masks": "all",
    "fixed_features": ["quest_board--base"],
    "icons": ["wood--icon"],
    "theme_selector": ["theme_thumbnail--base"],
}
REQUIRED_OVERLAYS = ("overlay_focus", "overlay_selection", "overlay_valid", "overlay_invalid", "overlay_connectivity")
# Logical geometry that a theme variant must never change.
GEOMETRY_KEYS = ("category", "pixel_size", "css_cell_size", "footprint", "anchor", "overhang", "collision_ref",
                 "entrances", "layer", "alpha_required")

NAME_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*--[a-z0-9]+(?:_[a-z0-9]+)*@2x\.webp$")
SVG_NAME_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*--[a-z0-9]+(?:_[a-z0-9]+)*\.svg$")
MASK_VARIANT_RE = re.compile(r"^mask_(\d+)$")
SIDES = ("N", "E", "S", "W")
BITS = {"N": 1, "E": 2, "S": 4, "W": 8}
OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}

# Pixel tolerances (8-bit channels). Alpha is exported losslessly, so alpha comparisons are exact.
EDGE_BAND = 8               # an unconnected road side must be empty this far in from the edge
SEAM_COLOUR_TOLERANCE = 14  # mean RGB difference across one seam, or between two tiles' same edge
SHORE_TOLERANCE = 16        # mean RGB difference between a shore edge and the ground/water tile
ANCHOR_TOLERANCE_PX = 6     # anchored prop: alpha centroid vs anchor x, contact row vs anchor y
DRIFT_TOLERANCE_PX = 3      # anchored prop: contact row / centroid difference between themes
MASS_RATIO = (0.67, 1.5)    # anchored prop: opaque area vs the default theme
BUILDING_EXPORT_PROFILE = "webp_lossless_exact_method_6"
BUILDING_SOURCE_DIRS = {"perkampungan": "perkampungan", "kingdom": "kingdom", "city": "city"}


@dataclass
class Report:
    problems: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    decoder: str = "none"

    def add(self, message: str) -> None:
        self.problems.append(message)

    @property
    def ok(self) -> bool:
        return not self.problems


# --------------------------------------------------------------------------- JSON Schema subset

def schema_errors(value, schema: dict, where: str) -> list[str]:
    """The subset of JSON Schema that assets.schema.json uses (draft 2020-12 keywords)."""
    errors: list[str] = []
    types = schema.get("type")
    if types is not None:
        allowed = types if isinstance(types, list) else [types]
        checks = {"object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
                  "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
                  "null": lambda v: v is None,
                  "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
                  "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)}
        if not any(checks[t](value) for t in allowed):
            return [f"{where}: expected {' or '.join(allowed)}, got {json.dumps(value)}"]
    if value is None:
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: {json.dumps(value)} is not one of {schema['enum']}")
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{where}: {value!r} does not match {schema['pattern']}")
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: must not be empty")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{where}: {value} is below the minimum {schema['minimum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{where}: {value} must be greater than {schema['exclusiveMinimum']}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{where}: needs at least {schema['minItems']} item(s)")
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            errors.append(f"{where}: items must be unique")
        if "items" in schema:
            for i, item in enumerate(value):
                errors += schema_errors(item, schema["items"], f"{where}[{i}]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{where}: missing required field '{key}'")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{where}: unknown field '{key}' (assets.schema.json allows {sorted(props)})")
        for key, sub in props.items():
            if key in value:
                errors += schema_errors(value[key], sub, f"{where}.{key}")
    return errors


# --------------------------------------------------------------------------- WebP container

@dataclass
class WebPInfo:
    width: int
    height: int
    has_alpha: bool
    codec: str


def parse_webp(data: bytes) -> WebPInfo:
    """Read dimensions and the alpha flag from a WebP RIFF container (no decoding)."""
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP file (missing RIFF/WEBP header)")
    riff_size = struct.unpack("<I", data[4:8])[0]
    if riff_size + 8 != len(data):
        raise ValueError(f"RIFF size {riff_size + 8} does not match the file size {len(data)} (truncated or padded)")
    chunk = data[12:16]
    body = data[20:]
    if chunk == b"VP8X":
        flags = body[0]
        width = 1 + int.from_bytes(body[4:7], "little")
        height = 1 + int.from_bytes(body[7:10], "little")
        has_alpha = bool(flags & 0x10)
        pos = 12
        while pos + 8 <= len(data):         # the alpha flag is only a hint: look for ALPH or VP8L
            name, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
            if name == b"VP8L":
                has_alpha = has_alpha and bool((int.from_bytes(data[pos + 9:pos + 13], "little") >> 28) & 1)
            pos += 8 + size + (size & 1)
        return WebPInfo(width, height, has_alpha, "VP8X")
    if chunk == b"VP8L":
        if body[0] != 0x2F:
            raise ValueError("VP8L signature byte missing")
        bits = int.from_bytes(body[1:5], "little")
        return WebPInfo((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1, bool((bits >> 28) & 1), "VP8L")
    if chunk == b"VP8 ":
        if body[3:6] != b"\x9d\x01\x2a":
            raise ValueError("VP8 key-frame start code missing")
        width, height = struct.unpack("<HH", body[6:10])
        return WebPInfo(width & 0x3FFF, height & 0x3FFF, False, "VP8")
    raise ValueError(f"unknown WebP chunk {chunk!r}")


# --------------------------------------------------------------------------- pixel decoding

class Pixels:
    """Decoded RGBA image with helpers. ``data`` is width*height*4 bytes."""

    def __init__(self, width: int, height: int, data: bytes):
        self.w, self.h, self.data = width, height, data

    def px(self, x: int, y: int) -> tuple[int, int, int, int]:
        i = (y * self.w + x) * 4
        return tuple(self.data[i:i + 4])

    def alpha(self, x: int, y: int) -> int:
        return self.data[(y * self.w + x) * 4 + 3]

    def edge(self, side: str, inset: int = 0) -> list[tuple[int, int, int, int]]:
        """Pixels along one edge, ``inset`` px in from it, ordered west->east or north->south."""
        if side == "N":
            return [self.px(x, inset) for x in range(self.w)]
        if side == "S":
            return [self.px(x, self.h - 1 - inset) for x in range(self.w)]
        if side == "W":
            return [self.px(inset, y) for y in range(self.h)]
        return [self.px(self.w - 1 - inset, y) for y in range(self.h)]

    def region_mean_diff(self, other: "Pixels", box: tuple[int, int, int, int]) -> float:
        x0, y0, x1, y1 = box
        total, n = 0, 0
        for y in range(y0, y1):
            for x in range(x0, x1):
                a, b = self.px(x, y), other.px(x, y)
                total += abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
                n += 3
        return total / max(n, 1)


_DECODE_CACHE: dict[str, Pixels] = {}


def pixel_decoder() -> str | None:
    """'pillow', 'dwebp:<path>', or None."""
    try:
        from PIL import Image, features  # noqa: F401
        if features.check("webp"):
            return "pillow"
    except ImportError:
        pass
    dwebp = shutil.which("dwebp")
    return f"dwebp:{dwebp}" if dwebp else None


def decode(data: bytes, decoder: str) -> Pixels:
    key = hashlib.sha256(data).hexdigest()
    if key in _DECODE_CACHE:
        return _DECODE_CACHE[key]
    if decoder == "pillow":
        import io

        from PIL import Image
        with Image.open(io.BytesIO(data)) as img:
            rgba = img.convert("RGBA")
            pixels = Pixels(rgba.width, rgba.height, rgba.tobytes())
    else:
        import tempfile
        exe = decoder.split(":", 1)[1]
        with tempfile.NamedTemporaryFile(suffix=".webp") as tmp:
            tmp.write(data)
            tmp.flush()
            out = subprocess.run([exe, "-quiet", "-pam", tmp.name, "-o", "-"], capture_output=True, check=False)
        if out.returncode != 0:
            raise ValueError(f"dwebp could not decode it: {out.stderr.decode(errors='replace').strip()}")
        header, _, raw = out.stdout.partition(b"ENDHDR\n")
        fields = dict(line.split(" ", 1) for line in header.decode().splitlines()[1:] if " " in line)
        pixels = Pixels(int(fields["WIDTH"]), int(fields["HEIGHT"]), raw)
    _DECODE_CACHE[key] = pixels
    return pixels


# --------------------------------------------------------------------------- content helpers

def load_json(path: Path, report: Report, what: str):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        report.add(f"{what}: file not found at {path}")
    except json.JSONDecodeError as exc:
        report.add(f"{what}: invalid JSON in {path}: {exc}")
    return None


def group_of(themes: dict, roads: dict, buildings: dict) -> dict[str, str]:
    """Logical asset ID -> runtime_assets.directories group."""
    out = {}
    for group, ids in themes["required_assets"].items():
        for asset_id in ids:
            out[asset_id] = group
    for m in roads["road_masks"]:
        out[m["asset_id"]] = "road_masks"
    for m in roads["shore_masks"]:
        out[m["asset_id"]] = "shore_masks"
    for b in buildings["buildings"]:
        out[b["visual_asset_key"]] = "buildings"
    return out


def required_ids(profile: str, themes: dict, roads: dict, buildings: dict, theme: dict) -> list[str]:
    if profile == "complete":
        return list(theme["assets"])
    if profile == "buildings":
        return [building["visual_asset_key"] for building in buildings["buildings"]]
    ids = []
    for group, listed in GOLDEN.items():
        ids += [m["asset_id"] for m in roads[group]] if listed == "all" else listed
    return ids


def expected_path(themes: dict, group: str, theme_id: str, asset_id: str) -> str:
    rule = themes["runtime_assets"]
    return rule["path_template"].format(theme_id=theme_id, directory=rule["directories"][group], asset_id=asset_id).lstrip("/")


def shore_masks_used(layout: dict) -> list[int]:
    water = {(c["x"], c["y"]) for c in layout["water"]}
    used = set()
    for (x, y) in water:
        mask = 0
        for side, (dx, dy) in (("N", (0, -1)), ("E", (1, 0)), ("S", (0, 1)), ("W", (-1, 0))):
            nx, ny = x + dx, y + dy
            if 0 <= nx < layout["width"] and 0 <= ny < layout["height"] and (nx, ny) not in water:
                mask |= BITS[side]
        used.add(mask)
    return sorted(used)


def mask_number(asset_id: str) -> int | None:
    match = MASK_VARIANT_RE.match(asset_id.split("--", 1)[1]) if "--" in asset_id else None
    return int(match.group(1)) if match else None


# --------------------------------------------------------------------------- checks

def check_entry(entry: dict, ctx: dict, report: Report) -> None:
    theme_id, where = ctx["theme_id"], f"{ctx['theme_id']}/{entry.get('asset_id', '?')}"
    for err in schema_errors(entry, ctx["schema"], where):
        report.add(f"{err} -> fix the manifest entry in themes/{theme_id}/manifest.json")
    asset_id = entry.get("asset_id", "")
    group = ctx["groups"].get(asset_id)
    if asset_id not in ctx["catalog"]:
        report.add(f"{where}: '{asset_id}' is not a logical asset of theme {theme_id} in content/kidquest/themes.json "
                   f"-> use the logical ID (snake case, zero-padded masks such as road_basic--mask_05)")
    variant = asset_id.split("--", 1)[1] if "--" in asset_id else ""
    mask_match = re.match(r"^mask_(\d+)$", variant)
    if mask_match and len(mask_match.group(1)) != 2:
        report.add(f"{where}: mask variant '{variant}' must be zero-padded to two digits (mask_{int(mask_match.group(1)):02d})")
    path = entry.get("runtime_path", "")
    name = path.rsplit("/", 1)[-1]
    if not NAME_RE.match(name):
        report.add(f"{where}: file name '{name}' must be '{{asset_id}}--{{variant}}@2x.webp' in lowercase snake case")
    if group:
        want = expected_path(ctx["themes"], group, theme_id, asset_id)
        if path != want:
            report.add(f"{where}: runtime_path '{path}' does not follow themes.json runtime_assets; expected '{want}'")
    if theme_id not in entry.get("required_in_themes", []) or set(entry.get("required_in_themes", [])) != set(ctx["theme_ids"]):
        report.add(f"{where}: required_in_themes must list every theme {ctx['theme_ids']} (theme parity)")
    if entry.get("content_version") != ctx["themes"]["content_version"]:
        report.add(f"{where}: content_version {entry.get('content_version')} != themes.json content_version {ctx['themes']['content_version']}")
    px, css = entry.get("pixel_size") or {}, entry.get("css_cell_size") or {}
    if px and css and (px.get("width") != 2 * css.get("width") or px.get("height") != 2 * css.get("height")):
        report.add(f"{where}: pixel_size {px} must be exactly 2x css_cell_size {css} (@2x export)")
    check_logical_geometry(entry, group, ctx, report, where)
    if entry.get("category") == "building" and entry.get("asset_id") in ctx["selected_ids"]:
        check_building_extraction(entry, ctx, report, where)
    if entry.get("category") in TILE_CATEGORIES and entry.get("max_bytes", 0) > BUDGETS["tile"]:
        report.add(f"{where}: max_bytes {entry['max_bytes']} is above the pipeline 18.6 tile/road budget {BUDGETS['tile']}")
    if entry.get("category") == "building" and entry.get("max_bytes", 0) > BUDGETS["building_2x2"]:
        report.add(f"{where}: max_bytes {entry['max_bytes']} is above the pipeline 18.6 building budget {BUDGETS['building_2x2']}")
    source = entry.get("source") or {}
    record = ctx["records"].get(source.get("record_id"))
    if record is None:
        report.add(f"{where}: source.record_id '{source.get('record_id')}' has no record in design/kidquest/source-metadata.json "
                   f"-> add the source/licence record (unowned sources fail the Stage I gate)")
    elif source.get("review_status") == "approved":
        reviews = {**ctx["review_defaults"], **(record.get("reviews") or {})}
        if reviews.get("art") != "approved" or reviews.get("cultural") != "approved":
            report.add(f"{where}: review_status 'approved' but source-metadata records art={reviews.get('art')}, "
                       f"cultural={reviews.get('cultural')} -> record the reviews first or keep 'in_review'")


def check_logical_geometry(entry: dict, group: str | None, ctx: dict, report: Report, where: str) -> None:
    category = entry.get("category")
    fp = entry.get("footprint")
    if category in TILE_CATEGORIES:
        if fp != {"width": 1, "height": 1}:
            report.add(f"{where}: a {category} tile covers exactly one cell; footprint must be {{width: 1, height: 1}}, got {fp}")
        if entry.get("pixel_size") != {"width": CELL_PX, "height": CELL_PX}:
            report.add(f"{where}: a {category} tile must be {CELL_PX}x{CELL_PX} px (one @2x cell), got {entry.get('pixel_size')}")
    asset_id = entry.get("asset_id", "")
    logical = ctx["logical"].get(asset_id)
    if logical:
        for key in ("footprint", "anchor", "entrances"):
            if logical.get(key) is not None and entry.get(key) != logical[key]:
                report.add(f"{where}: {key} {entry.get(key)} differs from the logical content {logical[key]} "
                           f"({logical['source']}); a visual variant must not redefine geometry")
    if fp and entry.get("anchor") and entry.get("pixel_size") and not entry.get("extraction"):
        oh = entry.get("overhang") or {}
        width = (fp["width"] + oh.get("left", 0) + oh.get("right", 0)) * CELL_PX
        height = (fp["height"] + oh.get("top", 0)) * CELL_PX
        if entry["pixel_size"] != {"width": round(width), "height": round(height)}:
            report.add(f"{where}: canvas {entry['pixel_size']} must equal footprint + overhang = {round(width)}x{round(height)} px")
        anchor = entry["anchor"]
        if abs(anchor.get("x", -1) - fp["width"] / 2) > 1e-9 or abs(anchor.get("y", -1) - fp["height"]) > 1e-9:
            report.add(f"{where}: anchor {anchor} must be the bottom-centre of the footprint ({fp['width'] / 2}, {fp['height']})")
    ref = entry.get("collision_ref")
    if ref and ref.startswith("layouts/"):
        file_part, _, obj = ref.partition("#")
        layout = ctx["layouts"].get(file_part)
        if layout is None:
            report.add(f"{where}: collision_ref '{ref}' points to a missing layout file content/kidquest/{file_part}")
        elif obj != "water" and obj not in {o["id"] for o in layout["fixed_objects"]}:
            report.add(f"{where}: collision_ref '{ref}' names no fixed object in {file_part}")


def check_building_extraction(entry: dict, ctx: dict, report: Report, where: str) -> None:
    """Validate KQ-029 pixel-space metadata against the frozen contract and content labels."""
    extraction = entry.get("extraction")
    if not isinstance(extraction, dict):
        report.add(f"{where}: missing extraction metadata -> run design/kidquest/tools/extract_building_sprites.py")
        return
    logical_id = entry.get("asset_id", "").removesuffix("--base")
    slot = ctx["building_slots"].get(logical_id)
    building = ctx["building_by_id"].get(logical_id)
    if slot is None or building is None:
        report.add(f"{where}: no frozen building slot for {logical_id!r}")
        return
    theme_id = ctx["theme_id"]
    source_dir = BUILDING_SOURCE_DIRS[theme_id]
    source_rel = f"design/kidquest/sprite-maps/{source_dir}/buildings_v1.png"
    expected = {
        "logical_id": logical_id,
        "theme_id": theme_id,
        "contract_id": ctx["building_contract"]["contract_id"],
        "source_map": source_rel,
        "source_provenance": f"design/kidquest/sprite-maps/{source_dir}/PROVENANCE.md",
        "slot": slot["slot"],
        "slot_rect": slot["rect"],
        "footprint_rect": slot["footprint_rect"],
        "anchor": slot["anchor"],
        "entrances": slot["entrances"],
        "collision_ref": f"buildings.json#{logical_id}",
        "shadow_bounds": building["shadow_bounds"],
        "accessible_label": ctx["theme"]["labels"][logical_id],
    }
    for key, value in expected.items():
        if extraction.get(key) != value:
            report.add(f"{where}: extraction.{key} {extraction.get(key)!r} differs from frozen value {value!r}")
    source_path = REPO_ROOT / source_rel
    if source_path.is_file():
        source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if extraction.get("source_map_sha256") != source_sha:
            report.add(f"{where}: extraction.source_map_sha256 is stale; expected {source_sha}")
    else:
        report.add(f"{where}: source map is missing at {source_rel}")
    if entry.get("pixel_size") != {"width": 512, "height": 512}:
        report.add(f"{where}: extracted building canvas must be 512x512 px, got {entry.get('pixel_size')}")
    if entry.get("export_profile") != BUILDING_EXPORT_PROFILE:
        report.add(f"{where}: export_profile must be {BUILDING_EXPORT_PROFILE!r}")
    expected_label_key = f"themes.{theme_id}.labels.{logical_id}"
    if entry.get("accessible_label_key") != expected_label_key:
        report.add(f"{where}: accessible_label_key must be {expected_label_key!r}")


def check_file(entry: dict, ctx: dict, report: Report, decoder: str | None):
    where = f"{ctx['theme_id']}/{entry.get('asset_id', '?')}"
    path_text = entry.get("runtime_path", "")
    if not path_text.startswith(RUNTIME_PREFIX):
        return None
    path = ctx["static_dir"] / path_text[len(RUNTIME_PREFIX):]
    if not path.is_file():
        report.add(f"{where}: missing file {path_text} -> export it (design/kidquest/tools/generate_golden_assets.py) or fix runtime_path")
        return None
    data = path.read_bytes()
    ctx["bytes"][ctx["theme_id"]][entry["asset_id"]] = len(data)
    if entry.get("max_bytes") and len(data) > entry["max_bytes"]:
        report.add(f"{where}: {len(data)} bytes exceeds max_bytes {entry['max_bytes']} -> recompress (lower quality) or simplify the art")
    if entry.get("category") in TILE_CATEGORIES and len(data) > BUDGETS["tile"]:
        report.add(f"{where}: {len(data)} bytes exceeds the pipeline 18.6 tile/road target {BUDGETS['tile']}")
    checksum = "sha256:" + hashlib.sha256(data).hexdigest()
    if (entry.get("source") or {}).get("checksum") != checksum:
        report.add(f"{where}: checksum is stale: manifest says {(entry.get('source') or {}).get('checksum')}, file is {checksum} "
                   f"-> re-run the generator so manifest and export agree")
    try:
        info = parse_webp(data)
    except ValueError as exc:
        report.add(f"{where}: {path_text} is not a valid WebP: {exc}")
        return None
    size = entry.get("pixel_size") or {}
    if (info.width, info.height) != (size.get("width"), size.get("height")):
        report.add(f"{where}: dimensions are {info.width}x{info.height} px but the manifest declares "
                   f"{size.get('width')}x{size.get('height')} -> re-export at the template size")
    if entry.get("alpha_required") and not info.has_alpha:
        report.add(f"{where}: alpha_required is true but the WebP has no alpha channel (opaque background) -> export with transparency")
    if decoder is None:
        return None
    try:
        pixels = decode(data, decoder)
    except Exception as exc:  # noqa: BLE001 - any decoder failure is a broken asset
        report.add(f"{where}: could not decode {path_text}: {exc}")
        return None
    if entry.get("alpha_required"):
        corners = [pixels.alpha(0, 0), pixels.alpha(pixels.w - 1, 0), pixels.alpha(0, pixels.h - 1), pixels.alpha(pixels.w - 1, pixels.h - 1)]
        if any(corners):
            report.add(f"{where}: corner alpha {corners} -> the background must be transparent (unexpected opaque background)")
        if max(pixels.data[3::4]) < 255:
            report.add(f"{where}: no fully opaque pixel -> the asset is empty or faded")
        extraction = entry.get("extraction") or {}
        if entry.get("category") == "building" and extraction.get("anchor"):
            points = [extraction["anchor"], *(extraction.get("entrances") or [])]
            for point in points:
                x, y = point["x"], point["y"]
                nearby = [pixels.alpha(px, py) for py in range(max(0, y - 2), min(pixels.h, y + 3))
                          for px in range(max(0, x - 2), min(pixels.w, x + 3))]
                if not any(nearby):
                    report.add(f"{where}: no visible pixel at extracted anchor/entrance ({x}, {y})")
    else:
        if min(pixels.data[3::4]) < 255:
            report.add(f"{where}: terrain must be fully opaque but has transparent pixels -> export without alpha")
    return pixels


def run_spans(alpha: list[int], threshold: int = 128) -> list[tuple[int, int]]:
    spans, start = [], None
    for i, a in enumerate(alpha + [0]):
        if a >= threshold and start is None:
            start = i
        elif a < threshold and start is not None:
            spans.append((start, i))
            start = None
    return spans


def mean_rgb(pixels: list[tuple[int, int, int, int]]) -> tuple[float, float, float]:
    solid = [p for p in pixels if p[3] == 255] or pixels
    n = len(solid)
    return tuple(sum(p[c] for p in solid) / n for c in range(3))


def rgb_gap(a, b) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / 3


def check_roads(theme_id: str, tiles: dict[str, Pixels], report: Report, stats: dict, reference: dict) -> None:
    """Pipeline 13: every connected edge meets at the midpoint with one width/colour; open edges stay empty."""
    masks = {mask_number(a): p for a, p in tiles.items() if a.startswith("road_basic--") and mask_number(a) is not None}
    if len(masks) != 16:
        return
    edges: dict[tuple[int, str], dict] = {}
    for mask, px in masks.items():
        name = f"{theme_id}/road_basic--mask_{mask:02d}"
        for side in SIDES:
            line = px.edge(side)
            alpha = [p[3] for p in line]
            if mask & BITS[side]:
                spans = run_spans(alpha)
                if len(spans) != 1:
                    report.add(f"{name}: {side} edge is connected in mask {mask:02d} but has {len(spans)} road runs "
                               f"-> the road must reach the {side} edge as one band")
                    continue
                a, b = spans[0]
                centre, size = (a + b - 1) / 2, len(line)
                if abs(centre - (size - 1) / 2) > 1:
                    report.add(f"{name}: {side} edge road band is centred at {centre:.1f}, not the edge midpoint {(size - 1) / 2:.1f}")
                if any(x < 250 for x in alpha[a + 1:b - 1]):
                    report.add(f"{name}: {side} edge road band has a transparent gap -> no gaps at a connected edge")
                ref = reference.setdefault("alpha", (alpha, name, side))
                if alpha != ref[0] and alpha != list(reversed(ref[0])):
                    report.add(f"{name}: {side} edge profile (run {a}..{b - 1}, {b - a} px) differs from {ref[1]} {ref[2]} edge "
                               f"-> every connected edge must use the same width and border")
                edges[(mask, side)] = {"alpha": alpha, "rgb": mean_rgb(line[a:b])}
            else:
                band = [px.edge(side, inset) for inset in range(EDGE_BAND)]
                if any(p[3] for row in band for p in row):
                    report.add(f"{name}: {side} side is not connected in mask {mask:02d} but road pixels reach within "
                               f"{EDGE_BAND} px of that edge -> end the road deliberately inside the tile")
    # same edge across masks: colour/border identical to the straight tile's edge
    straight = {"N": 5, "S": 5, "E": 10, "W": 10}
    for (mask, side), info in edges.items():
        ref = edges.get((straight[side], side))
        if ref and rgb_gap(info["rgb"], ref["rgb"]) > SEAM_COLOUR_TOLERANCE:
            report.add(f"{theme_id}/road_basic--mask_{mask:02d}: {side} edge colour differs from mask {straight[side]:02d} "
                       f"by {rgb_gap(info['rgb'], ref['rgb']):.1f} -> seams must match in colour and border")
    # every connecting pair: A's side meets B's opposite side
    pairs = 0
    for (ma, side), a in edges.items():
        if side not in ("E", "S"):
            continue
        for (mb, other), b in edges.items():
            if other != OPPOSITE[side]:
                continue
            pairs += 1
            if a["alpha"] != b["alpha"]:
                report.add(f"{theme_id}: road mask {ma:02d} {side} edge and mask {mb:02d} {other} edge do not line up -> gap or double-width seam")
            elif rgb_gap(a["rgb"], b["rgb"]) > SEAM_COLOUR_TOLERANCE:
                report.add(f"{theme_id}: road mask {ma:02d} {side} edge and mask {mb:02d} {other} edge differ in colour by "
                           f"{rgb_gap(a['rgb'], b['rgb']):.1f} -> visible seam")
    stats["road_pairs"] = stats.get("road_pairs", 0) + pairs


def check_shores(theme_id: str, tiles: dict[str, Pixels], report: Report, stats: dict) -> None:
    ground, water = tiles.get("ground_buildable--base"), tiles.get("water--base")
    if ground is None or water is None:
        return
    size = ground.w
    lo, hi = size * 5 // 16, size * 11 // 16      # middle of the edge, clear of the corners
    depth = size // 16
    boxes = {"N": (lo, 0, hi, depth), "S": (lo, size - depth, hi, size), "W": (0, lo, depth, hi), "E": (size - depth, lo, size, hi)}
    for asset_id, px in tiles.items():
        mask = mask_number(asset_id)
        if not asset_id.startswith("shore--") or mask is None or (px.w, px.h) != (size, size):
            continue
        stats["shore_tiles"] = stats.get("shore_tiles", 0) + 1
        for side in SIDES:
            land = bool(mask & BITS[side])
            to_ground = px.region_mean_diff(ground, boxes[side])
            to_water = px.region_mean_diff(water, boxes[side])
            if land and (to_ground > SHORE_TOLERANCE or to_ground >= to_water):
                report.add(f"{theme_id}/{asset_id}: {side} edge should show land (mask {mask:02d} has land on {side}) but differs "
                           f"from ground_buildable by {to_ground:.1f} -> shore art does not match its mask")
            if not land and (to_water > SHORE_TOLERANCE or to_water >= to_ground):
                report.add(f"{theme_id}/{asset_id}: {side} edge should be open water (mask {mask:02d}) but differs from water by "
                           f"{to_water:.1f} -> shore art does not match its mask")


def anchored_metrics(px: Pixels) -> dict:
    total = sx = 0
    bottom = -1
    for y in range(px.h):
        row_alpha = px.data[y * px.w * 4 + 3:(y + 1) * px.w * 4:4]
        count = sum(1 for a in row_alpha if a >= 128)
        if count:
            bottom = y
            total += count
            sx += sum(x for x, a in enumerate(row_alpha) if a >= 128)
    return {"area": total, "centroid_x": sx / total if total else 0, "bottom": bottom}


def check_cross_theme_pixels(per_theme: dict, entries: dict, theme_ids: list[str], report: Report, stats: dict) -> None:
    base = theme_ids[0]
    for asset_id, entry in entries.items():
        if base not in per_theme or asset_id not in per_theme[base]:
            continue
        ref = per_theme[base][asset_id]
        if entry.get("category") == "road":
            for theme in theme_ids[1:]:
                other = per_theme.get(theme, {}).get(asset_id)
                if other is None or (other.w, other.h) != (ref.w, ref.h):
                    continue
                diff = sum(1 for a, b in zip(ref.data[3::4], other.data[3::4]) if abs(a - b) > 8)
                if diff > 0.005 * ref.w * ref.h:
                    report.add(f"{theme}/{asset_id}: road silhouette differs from {base} in {diff} px -> theme-switch drift; "
                               f"roads are theme-neutral logical state")
        if entry.get("anchor") and entry.get("footprint"):
            stats["anchored"] = stats.get("anchored", 0) + 1
            metrics = {}
            for theme in theme_ids:
                px = per_theme.get(theme, {}).get(asset_id)
                if px is None:
                    continue
                m = metrics[theme] = anchored_metrics(px)
                ax = entry["anchor"]["x"] * CELL_PX
                floor = (entry["footprint"]["height"] + (entry.get("overhang") or {}).get("top", 0)) * CELL_PX
                if abs(m["centroid_x"] - (ax - 0.5)) > ANCHOR_TOLERANCE_PX:
                    report.add(f"{theme}/{asset_id}: silhouette centre x={m['centroid_x']:.1f} px is off the anchor x={ax - 0.5:.1f} -> re-centre on the bottom-centre anchor")
                if not floor - CELL_PX / 4 <= m["bottom"] < floor:
                    report.add(f"{theme}/{asset_id}: lowest opaque row {m['bottom']} must sit in the bottom quarter of the footprint "
                               f"(rows {floor - CELL_PX // 4}..{floor - 1}) so the object stands on its anchor")
            if base in metrics:
                r = metrics[base]
                for theme, m in metrics.items():
                    if theme == base:
                        continue
                    if abs(m["bottom"] - r["bottom"]) > DRIFT_TOLERANCE_PX or abs(m["centroid_x"] - r["centroid_x"]) > 2 * DRIFT_TOLERANCE_PX:
                        report.add(f"{theme}/{asset_id}: contact row {m['bottom']} / centre {m['centroid_x']:.1f} drift from {base} "
                                   f"({r['bottom']} / {r['centroid_x']:.1f}) -> theme-switch drift")
                    ratio = m["area"] / max(r["area"], 1)
                    if not MASS_RATIO[0] <= ratio <= MASS_RATIO[1]:
                        report.add(f"{theme}/{asset_id}: silhouette area is {ratio:.2f}x the {base} variant -> keep approximate silhouette mass")


def check_shared(static_dir: Path, records: dict, report: Report) -> int:
    manifest_path = static_dir / "shared" / "manifest.json"
    manifest = load_json(manifest_path, report, "shared overlays manifest")
    if manifest is None:
        return 0
    seen = set()
    for entry in manifest.get("assets", []):
        asset_id = entry.get("asset_id", "?")
        where = f"shared/{asset_id}"
        seen.add(asset_id.split("--", 1)[0])
        path_text = entry.get("runtime_path", "")
        name = path_text.rsplit("/", 1)[-1]
        if not SVG_NAME_RE.match(name) or name != f"{asset_id}.svg":
            report.add(f"{where}: shared overlay file name '{name}' must be '{asset_id}.svg' (lowercase snake case)")
        if not path_text.startswith(RUNTIME_PREFIX + "shared/"):
            report.add(f"{where}: shared overlays live under {RUNTIME_PREFIX}shared/, not '{path_text}'")
            continue
        path = static_dir / path_text[len(RUNTIME_PREFIX):]
        if not path.is_file():
            report.add(f"{where}: missing file {path_text}")
            continue
        data = path.read_bytes()
        if len(data) > entry.get("max_bytes", 4096):
            report.add(f"{where}: {len(data)} bytes exceeds max_bytes {entry.get('max_bytes', 4096)}")
        if (entry.get("source") or {}).get("checksum") != "sha256:" + hashlib.sha256(data).hexdigest():
            report.add(f"{where}: checksum is stale -> re-run the generator")
        if (entry.get("source") or {}).get("record_id") not in records:
            report.add(f"{where}: source.record_id has no record in design/kidquest/source-metadata.json")
        if not entry.get("non_color_cue"):
            report.add(f"{where}: describe the non-colour cue (overlays never rely on colour alone)")
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            report.add(f"{where}: not well-formed SVG: {exc}")
            continue
        if root.tag != "{http://www.w3.org/2000/svg}svg" or root.get("viewBox") != "0 0 128 128":
            report.add(f"{where}: root must be <svg viewBox=\"0 0 128 128\"> (one cell)")
        for el in root.iter():
            tag = el.tag.rsplit("}", 1)[-1]
            if tag in ("script", "foreignObject", "text", "image"):
                report.add(f"{where}: <{tag}> is not allowed (no scripts, no baked text, no embedded images)")
            for key, value in el.attrib.items():
                if key.endswith("href") and not value.startswith("#"):
                    report.add(f"{where}: external reference {value!r} is not allowed")
                if key.startswith("on"):
                    report.add(f"{where}: event handler attribute {key!r} is not allowed")
    for required in REQUIRED_OVERLAYS:
        if required not in seen:
            report.add(f"shared: required overlay '{required}--*' is missing -> add it to static/images/kidquest/shared/")
    return len(manifest.get("assets", []))


def validate(static_dir: Path = DEFAULT_STATIC, content_dir: Path = DEFAULT_CONTENT,
             source_metadata: Path = DEFAULT_SOURCE_METADATA, profile: str = "golden",
             pixel_checks: bool = True) -> Report:
    report = Report()
    static_dir, content_dir = Path(static_dir), Path(content_dir)
    themes = load_json(content_dir / "themes.json", report, "themes.json")
    roads = load_json(content_dir / "roads.json", report, "roads.json")
    buildings = load_json(content_dir / "buildings.json", report, "buildings.json")
    schema = load_json(content_dir / "assets.schema.json", report, "assets.schema.json")
    building_contract = load_json(content_dir / "building_sprite_map.v1.json", report, "building sprite-map contract")
    metadata = load_json(Path(source_metadata), report, "source metadata")
    if None in (themes, roads, buildings, schema, building_contract, metadata):
        return report
    layouts = {f"layouts/{p.name}": json.loads(p.read_text()) for p in sorted((content_dir / "layouts").glob("*.json"))}
    records = {r["record_id"]: r for r in metadata.get("records", [])}
    logical = {b["visual_asset_key"]: {"footprint": b["footprint"], "anchor": b["anchor"],
                                       "entrances": [entrance["side"] for entrance in b["entrances"]],
                                       "source": f"buildings.json#{b['id']}"} for b in buildings["buildings"]}
    logical["quest_board--base"] = {"footprint": {"width": 1, "height": 1}, "anchor": {"x": 0.5, "y": 1}, "entrances": None,
                                    "source": "layouts fixed_objects quest_board (1x1)"}
    decoder = pixel_decoder() if pixel_checks else None
    report.decoder = decoder or ("skipped (--structural-only)" if not pixel_checks else "none")
    if pixel_checks and decoder is None:
        report.add("pixel checks need a WebP decoder: install Pillow (pip install Pillow) or libwebp's dwebp "
                   "(brew install webp / apt-get install webp), or pass --structural-only for a structural run")

    theme_ids = [t["id"] for t in themes["themes"]]
    groups = group_of(themes, roads, buildings)
    building_by_id = {building["id"]: building for building in buildings["buildings"]}
    building_slots = {slot["logical_id"]: slot for slot in building_contract["slots"]}
    ctx_base = {"themes": themes, "schema": schema, "groups": groups, "records": records, "logical": logical,
                "layouts": layouts, "theme_ids": theme_ids, "static_dir": static_dir,
                "building_contract": building_contract, "building_by_id": building_by_id, "building_slots": building_slots,
                "review_defaults": (metadata.get("defaults") or {}).get("reviews") or {}, "bytes": {t: {} for t in theme_ids}}
    per_theme_pixels: dict[str, dict[str, Pixels]] = {}
    manifests: dict[str, dict[str, dict]] = {}
    all_manifest_entries: dict[str, dict[str, dict]] = {}
    stats: dict = {}
    road_reference: dict = {}
    for theme in themes["themes"]:
        theme_id = theme["id"]
        manifest = load_json(static_dir / "themes" / theme_id / "manifest.json", report, f"{theme_id} manifest")
        if manifest is None:
            continue
        if manifest.get("theme_id") != theme_id:
            report.add(f"{theme_id}: manifest theme_id is {manifest.get('theme_id')!r}; the directory is the theme")
        if manifest.get("content_version") != themes["content_version"]:
            report.add(f"{theme_id}: manifest content_version {manifest.get('content_version')} != themes.json {themes['content_version']}")
        ctx = {**ctx_base, "theme_id": theme_id, "theme": theme, "catalog": set(theme["assets"])}
        entries: dict[str, dict] = {}
        for entry in manifest.get("assets", []):
            asset_id = entry.get("asset_id", "?")
            if asset_id in entries:
                report.add(f"{theme_id}/{asset_id}: duplicate manifest entry -> one entry per logical asset")
            entries[asset_id] = entry
        all_manifest_entries[theme_id] = entries
        selected_ids = set(required_ids(profile, themes, roads, buildings, theme))
        ctx["selected_ids"] = selected_ids
        manifests[theme_id] = {asset_id: entry for asset_id, entry in entries.items() if asset_id in selected_ids}
        for asset_id in selected_ids:
            if asset_id not in entries:
                group = groups.get(asset_id, "?")
                hint = expected_path(themes, group, theme_id, asset_id) if group != "?" else "?"
                report.add(f"{theme_id}: missing required {profile} asset '{asset_id}' -> add a manifest entry and export {hint}")
        pixels = {}
        for asset_id, entry in entries.items():
            check_entry(entry, ctx, report)
            if asset_id not in selected_ids:
                continue
            decoded = check_file(entry, ctx, report, decoder)
            if decoded is not None:
                pixels[asset_id] = decoded
        per_theme_pixels[theme_id] = pixels
        if decoder and profile != "buildings":
            check_roads(theme_id, pixels, report, stats, road_reference)
            check_shores(theme_id, pixels, report, stats)

    # parity: same assets and same logical geometry in every theme
    all_ids = sorted({a for entries in manifests.values() for a in entries})
    for asset_id in all_ids:
        present = [t for t in theme_ids if asset_id in manifests.get(t, {})]
        if len(present) != len(theme_ids):
            missing = [t for t in theme_ids if t not in present]
            report.add(f"{asset_id}: present in {present} but missing in {missing} -> every theme supplies every logical asset")
            continue
        base = manifests[theme_ids[0]][asset_id]
        for theme_id in theme_ids[1:]:
            other = manifests[theme_id][asset_id]
            for key in GEOMETRY_KEYS:
                if other.get(key) != base.get(key):
                    report.add(f"{theme_id}/{asset_id}: {key} {other.get(key)} differs from {theme_ids[0]} {base.get(key)} "
                               f"-> theme variants share footprint, anchor, overhang, entrances and collision")
    if decoder and profile != "buildings" and theme_ids[0] in manifests:
        check_cross_theme_pixels(per_theme_pixels, manifests[theme_ids[0]], theme_ids, report, stats)
    overlays = check_shared(static_dir, records, report)

    # budgets (pipeline 18.6)
    thumbs = {t: ctx_base["bytes"][t].get("theme_thumbnail--base", 0) for t in theme_ids}
    for theme_id in theme_ids:
        sizes = ctx_base["bytes"][theme_id]
        total = sum(sizes.values())
        if profile == "golden" and total > BUDGETS["critical_first_world"]:
            report.add(f"{theme_id}: {total} bytes of {profile} assets exceeds the {BUDGETS['critical_first_world'] // KB} KB critical first-world budget")
        if total > BUDGETS["theme_pack"]:
            report.add(f"{theme_id}: {total} bytes exceeds the 2.5 MB complete theme pack budget")
        others = sum(v for t, v in thumbs.items() if t != theme_id)
        if others > BUDGETS["non_selected_thumbnails"]:
            report.add(f"{theme_id}: the non-selected theme thumbnails total {others} bytes, above the "
                       f"{BUDGETS['non_selected_thumbnails'] // KB} KB budget")
        catalog = len(next(t for t in themes["themes"] if t["id"] == theme_id)["assets"])
        if profile == "buildings":
            golden_ids = required_ids("golden", themes, roads, buildings, next(t for t in themes["themes"] if t["id"] == theme_id))
            critical_ids = set(golden_ids) | {"starter_house--base"}
            critical_total = 0
            for asset_id in critical_ids:
                entry = all_manifest_entries.get(theme_id, {}).get(asset_id)
                if entry:
                    path_text = entry["runtime_path"]
                    path = static_dir / path_text[len(RUNTIME_PREFIX):]
                    critical_total += path.stat().st_size if path.is_file() else 0
            if critical_total > BUDGETS["critical_first_world"]:
                report.add(f"{theme_id}: {critical_total} bytes for golden + starter house exceeds the "
                           f"{BUDGETS['critical_first_world'] // KB} KB critical first-world budget")
            report.summary.append(
                f"{theme_id}: 6 building assets on disk, {total:,} bytes ({total / KB:.1f} KB); "
                f"critical golden + starter house {critical_total:,} bytes ({critical_total / KB:.1f} KB) "
                f"of {BUDGETS['critical_first_world'] // KB} KB; pack budget 2.5 MB; "
                f"largest {max(sizes.items(), key=lambda kv: kv[1])[0] if sizes else '-'}"
            )
        else:
            report.summary.append(f"{theme_id}: {len(sizes)} {profile} assets on disk, {total:,} bytes ({total / KB:.1f} KB) "
                                  f"of the {BUDGETS['critical_first_world'] // KB} KB critical / 2.5 MB pack budgets; "
                                  f"largest {max(sizes.items(), key=lambda kv: kv[1])[0] if sizes else '-'}; "
                                  f"{catalog - len(manifests.get(theme_id, {}))} of {catalog} catalog assets not in this profile")
    report.summary.append(f"shared overlays: {overlays}")
    if decoder and profile != "buildings":
        report.summary.append(f"road seams checked: {stats.get('road_pairs', 0)} connecting edge pairs; shore tiles checked: "
                              f"{stats.get('shore_tiles', 0)}; anchored props checked across themes: {stats.get('anchored', 0)}")
    for name, layout in layouts.items():
        used = shore_masks_used(layout)
        report.summary.append(f"{name} uses shore masks {', '.join(f'{m:02d}' for m in used)}")
        if profile == "buildings":
            continue
        for theme_id in theme_ids:
            for m in used:
                if f"shore--mask_{m:02d}" not in manifests.get(theme_id, {}):
                    report.add(f"{theme_id}: shore--mask_{m:02d} is used by {name} but missing (AC-14)")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--static-dir", default=str(DEFAULT_STATIC), help="runtime image root (default: static/images/kidquest)")
    parser.add_argument("--content-dir", default=str(DEFAULT_CONTENT), help="content directory (default: content/kidquest)")
    parser.add_argument("--source-metadata", default=str(DEFAULT_SOURCE_METADATA), help="source/licence records")
    parser.add_argument("--profile", choices=("golden", "buildings", "complete"), default="golden",
                        help="golden = KQ-006 set; buildings = KQ-029 six per theme; complete = all 56 assets per theme")
    parser.add_argument("--structural-only", action="store_true", help="skip pixel checks (no WebP decoder available)")
    args = parser.parse_args(argv)
    report = validate(Path(args.static_dir), Path(args.content_dir), Path(args.source_metadata), args.profile,
                      pixel_checks=not args.structural_only)
    if not report.ok:
        print(f"KidQuest assets INVALID ({len(report.problems)} problem(s), profile {args.profile}, decoder {report.decoder}):", file=sys.stderr)
        for problem in report.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"KidQuest assets OK (profile {args.profile}, decoder {report.decoder}): {args.static_dir}")
    for line in report.summary:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
