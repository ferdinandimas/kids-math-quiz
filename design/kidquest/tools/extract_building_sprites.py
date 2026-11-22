#!/usr/bin/env python3
"""Extract the KQ-029 runtime building sprites and extend theme manifests.

Run from the repository root with the project interpreter and import path:

    PYTHONPATH=. .venv/bin/python design/kidquest/tools/extract_building_sprites.py
    PYTHONPATH=. .venv/bin/python design/kidquest/tools/extract_building_sprites.py --check

The script validates every source atlas with the frozen KQ-025 validator before
cropping.  It invokes libwebp's ``cwebp`` with ``-lossless -exact -m 6`` and no
metadata.  ``dwebp`` decodes every result and the script compares all RGBA
channels with the source slot.  The committed output is accepted only when the
maximum channel difference is zero and the alpha plane is byte-identical.

``--check`` regenerates all files in a temporary directory and compares the
sprites, manifests, and source records byte-for-byte without writing the tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from scripts.validate_building_sprite_map import decode_png_rgba, validate_sprite_map

REPO = Path(__file__).resolve().parents[3]
CONTENT = REPO / "content" / "kidquest"
STATIC = REPO / "static" / "images" / "kidquest"
METADATA = REPO / "design" / "kidquest" / "source-metadata.json"
GALLERY_DATA = REPO / "design" / "kidquest" / "gallery" / "kq029-data.js"
CONTRACT = CONTENT / "building_sprite_map.v1.json"
GENERATOR = "design/kidquest/tools/extract_building_sprites.py"
EXPORT_PROFILE = "webp_lossless_exact_method_6"
LICENSE = "generated for this project; see the source-map provenance record"
BUILDING_BUDGET = 180 * 1024
SOURCE_DIRS = {
    "perkampungan": "perkampungan",
    "kingdom": "kingdom",
    "city": "city",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crop_rgba(rgba: bytes, image_width: int, rect: dict) -> bytes:
    row_bytes = image_width * 4
    x, y, width, height = (rect[key] for key in ("x", "y", "width", "height"))
    return b"".join(
        rgba[(y + row) * row_bytes + x * 4:(y + row) * row_bytes + (x + width) * 4]
        for row in range(height)
    )


def encode_slot(source: Path, rect: dict, output: Path) -> bytes:
    command = [
        "cwebp", "-quiet", "-lossless", "-exact", "-m", "6", "-metadata", "none",
        "-crop", *(str(rect[key]) for key in ("x", "y", "width", "height")),
        str(source), "-o", str(output),
    ]
    subprocess.run(command, check=True)
    return output.read_bytes()


def decode_webp(data: bytes, work: Path) -> bytes:
    webp = work / "roundtrip.webp"
    png = work / "roundtrip.png"
    webp.write_bytes(data)
    subprocess.run(["dwebp", "-quiet", str(webp), "-o", str(png)], check=True)
    decoded = decode_png_rgba(png.read_bytes())
    if (decoded.width, decoded.height) != (512, 512):
        raise RuntimeError(f"decoded WebP is {decoded.width}x{decoded.height}, expected 512x512")
    return decoded.rgba


def extraction_metadata(theme: dict, slot: dict, source_rel: str, source_sha: str, building: dict) -> dict:
    logical_id = slot["logical_id"]
    return {
        "logical_id": logical_id,
        "theme_id": theme["id"],
        "contract_id": "building_sprite_map.v1",
        "source_map": source_rel,
        "source_map_sha256": source_sha,
        "source_provenance": f"design/kidquest/sprite-maps/{SOURCE_DIRS[theme['id']]}/PROVENANCE.md",
        "slot": slot["slot"],
        "slot_rect": slot["rect"],
        "footprint_rect": slot["footprint_rect"],
        "anchor": slot["anchor"],
        "entrances": slot["entrances"],
        "collision_ref": f"buildings.json#{logical_id}",
        "shadow_bounds": building["shadow_bounds"],
        "accessible_label": theme["labels"][logical_id],
    }


def manifest_entry(themes: dict, theme: dict, slot: dict, building: dict, data: bytes,
                   source_rel: str, source_sha: str) -> dict:
    asset_id = building["visual_asset_key"]
    runtime_path = themes["runtime_assets"]["path_template"].format(
        theme_id=theme["id"], directory=themes["runtime_assets"]["directories"]["buildings"], asset_id=asset_id
    ).lstrip("/")
    return {
        "asset_id": asset_id,
        "category": "building",
        "content_version": themes["content_version"],
        "required_in_themes": [item["id"] for item in themes["themes"]],
        "runtime_path": runtime_path,
        "fallback_path": None,
        "pixel_size": {"width": 512, "height": 512},
        "css_cell_size": {"width": 256, "height": 256},
        "footprint": building["footprint"],
        "anchor": building["anchor"],
        "collision_ref": f"buildings.json#{building['id']}",
        "entrances": [item["side"] for item in building["entrances"]],
        "layer": "buildings",
        "z_offset": 0,
        "alpha_required": True,
        "max_bytes": BUILDING_BUDGET,
        "export_profile": EXPORT_PROFILE,
        "source": {
            "record_id": f"kq029/{theme['id']}/buildings_v1",
            "creator": GENERATOR,
            "license_status": LICENSE,
            "review_status": "in_review",
            "checksum": "sha256:" + sha256(data),
        },
        "accessible_label_key": f"themes.{theme['id']}.labels.{building['id']}",
        "decorative": False,
        "extraction": extraction_metadata(theme, slot, source_rel, source_sha, building),
    }


def source_record(theme: dict, source_rel: str, source_sha: str) -> dict:
    theme_id = theme["id"]
    return {
        "record_id": f"kq029/{theme_id}/buildings_v1",
        "theme_id": theme_id,
        "group": "buildings",
        "source_map": source_rel,
        "source_map_sha256": source_sha,
        "contract_id": "building_sprite_map.v1",
        "provenance": f"design/kidquest/sprite-maps/{SOURCE_DIRS[theme_id]}/PROVENANCE.md",
        "creator": GENERATOR,
        "license_status": LICENSE,
        "reviews": {
            "geometry": "passed: scripts/validate_building_sprite_map.py",
            "art": "lead_review_passed_product_owner_pending",
            "cultural": "pending_product_owner_review",
        },
    }


def merged_manifest(theme: dict, building_entries: list[dict]) -> bytes:
    path = STATIC / "themes" / theme["id"] / "manifest.json"
    manifest = read_json(path)
    building_ids = {entry["asset_id"] for entry in building_entries}
    manifest["profile"] = "kq006_golden+kq029_buildings"
    manifest["note"] = (
        "KQ-006 golden non-building references plus KQ-029 lossless building extracts. "
        "Art and cultural review remain pending; this is not a release manifest."
    )
    manifest["assets"] = [entry for entry in manifest["assets"] if entry.get("asset_id") not in building_ids]
    manifest["assets"].extend(building_entries)
    return json_bytes(manifest)


def merged_source_metadata(records: list[dict]) -> bytes:
    metadata = read_json(METADATA)
    metadata["records"] = [record for record in metadata["records"] if not record.get("record_id", "").startswith("kq029/")]
    metadata["records"].extend(records)
    return json_bytes(metadata)


def build(check: bool) -> tuple[list[str], list[str]]:
    for tool in ("cwebp", "dwebp"):
        if shutil.which(tool) is None:
            raise RuntimeError(f"{tool} is required (install libwebp)")
    contract = read_json(CONTRACT)
    themes = read_json(CONTENT / "themes.json")
    buildings_raw = read_json(CONTENT / "buildings.json")
    buildings = {item["id"]: item for item in buildings_raw["buildings"]}
    differences: list[str] = []
    summary: list[str] = []
    records: list[dict] = []
    gallery_manifests: dict[str, list[dict]] = {}

    with tempfile.TemporaryDirectory(prefix="kq029-") as temp_name:
        work = Path(temp_name)
        for theme in themes["themes"]:
            theme_id = theme["id"]
            source_rel = f"design/kidquest/sprite-maps/{SOURCE_DIRS[theme_id]}/buildings_v1.png"
            source = REPO / source_rel
            report = validate_sprite_map(source, theme_id)
            if not report.ok:
                raise RuntimeError(f"source map {source_rel} failed KQ-025 validation:\n- " + "\n- ".join(report.problems))
            summary.extend(f"{theme_id}: {line}" for line in report.summary if line.startswith("slot "))
            source_bytes = source.read_bytes()
            source_sha = sha256(source_bytes)
            image = decode_png_rgba(source_bytes)
            entries: list[dict] = []
            theme_total = 0
            max_difference = 0
            alpha_equal = True
            for slot in contract["slots"]:
                asset_id = buildings[slot["logical_id"]]["visual_asset_key"]
                generated = work / f"{theme_id}-{asset_id}.webp"
                data = encode_slot(source, slot["rect"], generated)
                source_slot = crop_rgba(image.rgba, image.width, slot["rect"])
                decoded = decode_webp(data, work)
                difference = max(abs(a - b) for a, b in zip(source_slot, decoded, strict=True))
                same_alpha = source_slot[3::4] == decoded[3::4]
                if difference != 0 or not same_alpha:
                    raise RuntimeError(f"{theme_id}/{asset_id}: non-lossless round trip (max diff {difference}, alpha equal {same_alpha})")
                runtime_rel = themes["runtime_assets"]["path_template"].format(
                    theme_id=theme_id, directory=themes["runtime_assets"]["directories"]["buildings"], asset_id=asset_id
                ).lstrip("/")
                target = REPO / runtime_rel
                if len(data) > BUILDING_BUDGET:
                    raise RuntimeError(f"{theme_id}/{asset_id}: {len(data)} bytes exceeds {BUILDING_BUDGET}")
                if check:
                    if not target.is_file() or target.read_bytes() != data:
                        differences.append(runtime_rel)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                entries.append(manifest_entry(themes, theme, slot, buildings[slot["logical_id"]], data, source_rel, source_sha))
                theme_total += len(data)
                max_difference = max(max_difference, difference)
                alpha_equal &= same_alpha
            manifest_data = merged_manifest(theme, entries)
            manifest_path = STATIC / "themes" / theme_id / "manifest.json"
            if check:
                if not manifest_path.is_file() or manifest_path.read_bytes() != manifest_data:
                    differences.append(str(manifest_path.relative_to(REPO)))
            else:
                manifest_path.write_bytes(manifest_data)
            records.append(source_record(theme, source_rel, source_sha))
            gallery_manifests[theme_id] = entries
            summary.append(
                f"{theme_id}: 6 sprites, {theme_total:,} bytes; max channel difference {max_difference}; alpha equal {alpha_equal}"
            )

    metadata_data = merged_source_metadata(records)
    if check:
        if not METADATA.is_file() or METADATA.read_bytes() != metadata_data:
            differences.append(str(METADATA.relative_to(REPO)))
    else:
        METADATA.write_bytes(metadata_data)
    gallery = {
        "themes": [{"id": theme["id"], "name": theme["name"], "labels": theme["labels"]} for theme in themes["themes"]],
        "slots": contract["slots"],
        "manifests": gallery_manifests,
    }
    gallery_data = ("// Generated by design/kidquest/tools/extract_building_sprites.py - do not edit.\n"
                    "window.KQ029 = " + json.dumps(gallery, indent=1, ensure_ascii=False) + ";\n").encode("utf-8")
    if check:
        if not GALLERY_DATA.is_file() or GALLERY_DATA.read_bytes() != gallery_data:
            differences.append(str(GALLERY_DATA.relative_to(REPO)))
    else:
        GALLERY_DATA.write_bytes(gallery_data)
    return differences, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="regenerate in temp storage and require byte-identical committed outputs")
    args = parser.parse_args(argv)
    try:
        differences, summary = build(args.check)
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
        print(f"KQ-029 extraction FAILED: {exc}")
        return 1
    if differences:
        print("KQ-029 extraction is not byte-identical:")
        for path in differences:
            print(f"  - {path}")
        return 1
    action = "byte-identical check passed" if args.check else "wrote deterministic outputs"
    print(f"KQ-029 extraction OK ({action}; {EXPORT_PROFILE}):")
    for line in summary:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
