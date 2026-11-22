"""KQ-006 asset validator: the committed golden set passes, and each failure class is caught.

Every negative test works on a copy of static/images/kidquest (and the source metadata) in a temp
directory; committed assets are never modified. Pixel checks need a WebP decoder (Pillow or libwebp's
`dwebp`); tests that need one skip with a reason when neither is installed, and tests that must
craft new images skip without Pillow.
"""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "validate_kidquest_assets.py"
STATIC = REPO_ROOT / "static" / "images" / "kidquest"
CONTENT = REPO_ROOT / "content" / "kidquest"
METADATA = REPO_ROOT / "design" / "kidquest" / "source-metadata.json"
EXTRACTOR = REPO_ROOT / "design" / "kidquest" / "tools" / "extract_building_sprites.py"

_spec = importlib.util.spec_from_file_location("validate_kidquest_assets", SCRIPT)
validator = importlib.util.module_from_spec(_spec)
sys.modules["validate_kidquest_assets"] = validator
_spec.loader.exec_module(validator)

THEMES = ("perkampungan", "kingdom", "city")
needs_decoder = pytest.mark.skipif(validator.pixel_decoder() is None,
                                   reason="pixel checks need Pillow or dwebp (libwebp) to decode WebP")


class AssetCopy:
    def __init__(self, root: Path):
        self.static = root / "static"
        self.metadata = root / "source-metadata.json"
        shutil.copytree(STATIC, self.static)
        shutil.copyfile(METADATA, self.metadata)

    def manifest_path(self, theme: str) -> Path:
        return self.static / "themes" / theme / "manifest.json"

    def manifest(self, theme: str) -> dict:
        return json.loads(self.manifest_path(theme).read_text())

    def save(self, theme: str, manifest: dict) -> None:
        self.manifest_path(theme).write_text(json.dumps(manifest, indent=2))

    def entry(self, manifest: dict, asset_id: str) -> dict:
        return next(e for e in manifest["assets"] if e["asset_id"] == asset_id)

    def edit(self, theme: str, asset_id: str, **changes) -> None:
        manifest = self.manifest(theme)
        self.entry(manifest, asset_id).update(changes)
        self.save(theme, manifest)

    def file(self, theme: str, asset_id: str) -> Path:
        rel = self.entry(self.manifest(theme), asset_id)["runtime_path"]
        return self.static / rel[len("static/images/kidquest/"):]

    def replace_file(self, theme: str, asset_id: str, data: bytes, resign: bool = True) -> None:
        """Swap the file's bytes; by default update the checksum so only the intended check fails."""
        self.file(theme, asset_id).write_bytes(data)
        if resign:
            manifest = self.manifest(theme)
            self.entry(manifest, asset_id)["source"]["checksum"] = "sha256:" + hashlib.sha256(data).hexdigest()
            self.save(theme, manifest)

    def validate(self, pixel_checks: bool = True, profile: str = "golden"):
        return validator.validate(self.static, CONTENT, self.metadata, profile, pixel_checks=pixel_checks)


@pytest.fixture
def assets(tmp_path):
    return AssetCopy(tmp_path)


def problems_text(report) -> str:
    return "\n".join(report.problems)


def assert_problem(report, *fragments):
    text = problems_text(report)
    assert not report.ok, "expected the validator to fail"
    for fragment in fragments:
        assert fragment in text, f"expected {fragment!r} in:\n{text}"


# --------------------------------------------------------------------------- the committed set

def test_committed_golden_set_passes_structural_checks():
    report = validator.validate(STATIC, CONTENT, METADATA, "golden", pixel_checks=False)
    assert report.ok, problems_text(report)
    assert any("37 golden assets" in line for line in report.summary)


@needs_decoder
def test_committed_golden_set_passes_pixel_checks():
    report = validator.validate(STATIC, CONTENT, METADATA, "golden", pixel_checks=True)
    assert report.ok, problems_text(report)
    summary = "\n".join(report.summary)
    assert "384 connecting edge pairs" in summary          # 3 themes x 2 axes x 8 x 8 masks
    assert "shore tiles checked: 48" in summary
    assert "uses shore masks 01, 04, 08, 09, 10" in summary


def test_committed_building_set_passes_structural_checks():
    report = validator.validate(STATIC, CONTENT, METADATA, "buildings", pixel_checks=False)
    assert report.ok, problems_text(report)
    assert sum("6 building assets" in line for line in report.summary) == 3
    assert all("critical golden + starter house" in line for line in report.summary[:3])


@needs_decoder
def test_committed_building_set_passes_pixel_checks():
    report = validator.validate(STATIC, CONTENT, METADATA, "buildings", pixel_checks=True)
    assert report.ok, problems_text(report)


def test_building_extraction_is_byte_identical():
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    checked = subprocess.run([sys.executable, str(EXTRACTOR), "--check"], cwd=REPO_ROOT, env=env,
                             capture_output=True, text=True, check=False)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "byte-identical check passed" in checked.stdout


def test_golden_profile_matches_content_and_complete_profile_reports_the_rest():
    complete = validator.validate(STATIC, CONTENT, METADATA, "complete", pixel_checks=False)
    text = problems_text(complete)
    # KQ-029 now supplies buildings; props/fences/plants/stone remain KQ-023 work.
    assert "missing required complete asset 'starter_house--base'" not in text
    assert "missing required complete asset 'stone--icon'" in text
    assert "missing required complete asset 'road_basic" not in text
    assert "missing required complete asset 'shore--" not in text


def test_every_committed_runtime_file_is_in_a_manifest():
    listed = set()
    for theme in THEMES:
        manifest = json.loads((STATIC / "themes" / theme / "manifest.json").read_text())
        listed |= {e["runtime_path"] for e in manifest["assets"]}
    shared = json.loads((STATIC / "shared" / "manifest.json").read_text())
    listed |= {e["runtime_path"] for e in shared["assets"]}
    on_disk = {str(p.relative_to(REPO_ROOT)) for p in STATIC.rglob("*") if p.suffix in (".webp", ".svg", ".png")}
    assert on_disk == listed
    buildings = {path for path in on_disk if "/buildings/" in path}
    assert len(buildings) == 18, "KQ-029 owns exactly six building sprites in each of three themes"


def test_cli_exit_codes(assets):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    ok = subprocess.run([sys.executable, str(SCRIPT), "--structural-only"], capture_output=True, text=True, env=env, check=False)
    assert ok.returncode == 0, ok.stderr
    assert "KidQuest assets OK" in ok.stdout
    assets.file("city", "wood--icon").unlink()
    bad = subprocess.run([sys.executable, str(SCRIPT), "--structural-only", "--static-dir", str(assets.static),
                          "--source-metadata", str(assets.metadata)], capture_output=True, text=True, env=env, check=False)
    assert bad.returncode == 1
    assert "city/wood--icon: missing file" in bad.stderr


# --------------------------------------------------------------------------- existence, parity, naming

def test_missing_file(assets):
    assets.file("kingdom", "road_basic--mask_07").unlink()
    assert_problem(assets.validate(pixel_checks=False), "kingdom/road_basic--mask_07: missing file")


def test_asset_missing_from_one_theme(assets):
    manifest = assets.manifest("city")
    manifest["assets"] = [e for e in manifest["assets"] if e["asset_id"] != "shore--mask_09"]
    assets.save("city", manifest)
    report = assets.validate(pixel_checks=False)
    assert_problem(report, "city: missing required golden asset 'shore--mask_09'",
                   "shore--mask_09: present in ['perkampungan', 'kingdom'] but missing in ['city']",
                   "shore--mask_09 is used by layouts/pulau_tunas_v1.json but missing (AC-14)")


def test_missing_theme_manifest(assets):
    assets.manifest_path("kingdom").unlink()
    assert_problem(assets.validate(pixel_checks=False), "kingdom manifest: file not found")


def test_naming_must_be_lowercase_snake_case_at_the_template_path(assets):
    old = assets.file("perkampungan", "wood--icon")
    new = old.with_name("Wood--Icon@2x.webp")
    old.rename(new)
    assets.edit("perkampungan", "wood--icon", runtime_path="static/images/kidquest/themes/perkampungan/icons/Wood--Icon@2x.webp")
    assert_problem(assets.validate(pixel_checks=False), "must be '{asset_id}--{variant}@2x.webp' in lowercase snake case",
                   "does not follow themes.json runtime_assets; expected 'static/images/kidquest/themes/perkampungan/icons/wood--icon@2x.webp'")


def test_wrong_directory(assets):
    target = assets.static / "themes" / "kingdom" / "props" / "wood--icon@2x.webp"
    assets.file("kingdom", "wood--icon").rename(target)
    assets.edit("kingdom", "wood--icon", runtime_path="static/images/kidquest/themes/kingdom/props/wood--icon@2x.webp")
    assert_problem(assets.validate(pixel_checks=False), "kingdom/wood--icon: runtime_path", "expected 'static/images/kidquest/themes/kingdom/icons/wood--icon@2x.webp'")


def test_building_profile_rejects_missing_sprite(assets):
    assets.file("kingdom", "garden--base").unlink()
    assert_problem(assets.validate(pixel_checks=False, profile="buildings"), "kingdom/garden--base: missing file")


def test_building_profile_rejects_misnamed_sprite(assets):
    old = assets.file("city", "market_stall--base")
    new = old.with_name("market-stall--base@2x.webp")
    old.rename(new)
    assets.edit("city", "market_stall--base",
                runtime_path="static/images/kidquest/themes/city/buildings/market-stall--base@2x.webp")
    assert_problem(assets.validate(pixel_checks=False, profile="buildings"),
                   "file name 'market-stall--base@2x.webp' must be", "does not follow themes.json runtime_assets")


def test_building_profile_rejects_mis_sized_sprite(assets):
    board = assets.file("perkampungan", "quest_board--base").read_bytes()
    assets.replace_file("perkampungan", "bridge--base", board)
    assert_problem(assets.validate(pixel_checks=False, profile="buildings"),
                   "perkampungan/bridge--base: dimensions are 128x192 px but the manifest declares 512x512")


def test_building_profile_rejects_anchor_drift(assets):
    manifest = assets.manifest("kingdom")
    assets.entry(manifest, "bakery--base")["extraction"]["anchor"] = {"x": 255, "y": 464}
    assets.save("kingdom", manifest)
    assert_problem(assets.validate(pixel_checks=False, profile="buildings"),
                   "kingdom/bakery--base: extraction.anchor", "differs from frozen value {'x': 256, 'y': 464}")


def test_masks_must_be_zero_padded(assets):
    for theme in THEMES:
        manifest = assets.manifest(theme)
        assets.entry(manifest, "road_basic--mask_05")["asset_id"] = "road_basic--mask_5"
        assets.save(theme, manifest)
    assert_problem(assets.validate(pixel_checks=False), "mask variant 'mask_5' must be zero-padded to two digits (mask_05)",
                   "'road_basic--mask_5' is not a logical asset", "missing required golden asset 'road_basic--mask_05'")


def test_required_in_themes_must_list_every_theme(assets):
    assets.edit("city", "water--base", required_in_themes=["city"])
    assert_problem(assets.validate(pixel_checks=False), "city/water--base: required_in_themes must list every theme")


# --------------------------------------------------------------------------- schema, source and review

def test_schema_rejects_unknown_fields_and_bad_enums(assets):
    manifest = assets.manifest("kingdom")
    entry = assets.entry(manifest, "water--base")
    entry["theme"] = "kingdom"
    entry["source"]["review_status"] = "pending_art_review"
    assets.save("kingdom", manifest)
    assert_problem(assets.validate(pixel_checks=False), "unknown field 'theme'",
                   "kingdom/water--base.source.review_status: \"pending_art_review\" is not one of")


def test_unowned_source_record(assets):
    manifest = assets.manifest("city")
    assets.entry(manifest, "quest_board--base")["source"]["record_id"] = "somewhere/else"
    assets.save("city", manifest)
    assert_problem(assets.validate(pixel_checks=False), "city/quest_board--base: source.record_id 'somewhere/else' has no record")


def test_approval_needs_recorded_reviews(assets):
    manifest = assets.manifest("perkampungan")
    assets.entry(manifest, "quest_board--base")["source"]["review_status"] = "approved"
    assets.save("perkampungan", manifest)
    assert_problem(assets.validate(pixel_checks=False), "review_status 'approved' but source-metadata records art=pending_art_review")


# --------------------------------------------------------------------------- file checks

def test_stale_checksum(assets):
    manifest = assets.manifest("kingdom")
    assets.entry(manifest, "ground_buildable--base")["source"]["checksum"] = "sha256:" + "0" * 64
    assets.save("kingdom", manifest)
    assert_problem(assets.validate(pixel_checks=False), "kingdom/ground_buildable--base: checksum is stale")


def test_file_change_without_manifest_update_is_stale(assets):
    data = assets.file("city", "water--base").read_bytes()
    assets.replace_file("city", "ground_buildable--base", data, resign=False)
    assert_problem(assets.validate(pixel_checks=False), "city/ground_buildable--base: checksum is stale")


def test_corrupt_file(assets):
    assets.replace_file("city", "road_basic--mask_03", b"not an image at all, just text padding" * 4)
    assert_problem(assets.validate(pixel_checks=False), "city/road_basic--mask_03: static/images/kidquest/themes/city/roads/road_basic--mask_03@2x.webp is not a valid WebP")


def test_wrong_dimensions(assets):
    board = assets.file("kingdom", "quest_board--base").read_bytes()     # 128 x 192
    assets.replace_file("kingdom", "road_basic--mask_05", board)
    assert_problem(assets.validate(pixel_checks=False), "kingdom/road_basic--mask_05: dimensions are 128x192 px but the manifest declares 128x128")


def test_declared_size_must_be_exactly_2x_css(assets):
    for theme in THEMES:
        assets.edit(theme, "wood--icon", css_cell_size={"width": 64, "height": 64})
    assert_problem(assets.validate(pixel_checks=False), "pixel_size {'width': 96, 'height': 96} must be exactly 2x css_cell_size")


def test_opaque_background_where_alpha_is_required(assets):
    ground = assets.file("perkampungan", "ground_buildable--base").read_bytes()
    assets.replace_file("perkampungan", "road_basic--mask_10", ground)
    assert_problem(assets.validate(pixel_checks=False),
                   "perkampungan/road_basic--mask_10: alpha_required is true but the WebP has no alpha channel")


@needs_decoder
def test_opaque_corners_where_alpha_is_required(assets):
    ground = assets.file("perkampungan", "ground_buildable--base").read_bytes()
    assets.replace_file("perkampungan", "road_basic--mask_10", ground)
    assert_problem(assets.validate(), "perkampungan/road_basic--mask_10: corner alpha [255, 255, 255, 255]")


@needs_decoder
def test_terrain_must_be_opaque(assets):
    road = assets.file("city", "road_basic--mask_05").read_bytes()
    assets.replace_file("city", "ground_buildable--base", road)
    assert_problem(assets.validate(), "city/ground_buildable--base: terrain must be fully opaque but has transparent pixels")


def test_byte_budget_from_manifest(assets):
    assets.edit("city", "theme_thumbnail--base", max_bytes=100)
    assert_problem(assets.validate(pixel_checks=False), "city/theme_thumbnail--base:", "exceeds max_bytes 100")


def test_manifest_budget_cannot_exceed_pipeline_tile_budget(assets):
    assets.edit("kingdom", "shore--mask_15", max_bytes=64 * 1024)
    assert_problem(assets.validate(pixel_checks=False), "kingdom/shore--mask_15: max_bytes 65536 is above the pipeline 18.6 tile/road budget 32768")


def test_theme_totals_against_pipeline_budgets(assets, monkeypatch):
    monkeypatch.setitem(validator.BUDGETS, "critical_first_world", 50 * 1024)
    monkeypatch.setitem(validator.BUDGETS, "non_selected_thumbnails", 10 * 1024)
    report = assets.validate(pixel_checks=False)
    assert_problem(report, "kingdom:", "exceeds the 50 KB critical first-world budget",
                   "the non-selected theme thumbnails total")


# --------------------------------------------------------------------------- geometry

def test_geometry_must_not_drift_between_themes(assets):
    assets.edit("kingdom", "quest_board--base", entrances=["S"])
    assert_problem(assets.validate(pixel_checks=False),
                   "kingdom/quest_board--base: entrances ['S'] differs from perkampungan ['N', 'E', 'S', 'W']")


def test_geometry_must_match_logical_content(assets):
    for theme in THEMES:
        assets.edit(theme, "quest_board--base", footprint={"width": 2, "height": 1})
    assert_problem(assets.validate(pixel_checks=False),
                   "footprint {'width': 2, 'height': 1} differs from the logical content {'width': 1, 'height': 1}")


def test_anchor_must_be_bottom_centre_and_canvas_must_fit_overhang(assets):
    for theme in THEMES:
        assets.edit(theme, "quest_board--base", anchor={"x": 0, "y": 1}, overhang={"top": 1, "left": 0, "right": 0})
    assert_problem(assets.validate(pixel_checks=False), "anchor {'x': 0, 'y': 1} must be the bottom-centre",
                   "canvas {'width': 128, 'height': 192} must equal footprint + overhang = 128x256 px")


def test_tiles_cover_exactly_one_cell(assets):
    for theme in THEMES:
        assets.edit(theme, "water--base", footprint={"width": 1, "height": 2})
    assert_problem(assets.validate(pixel_checks=False), "a terrain tile covers exactly one cell")


def test_collision_ref_must_exist(assets):
    for theme in THEMES:
        assets.edit(theme, "quest_board--base", collision_ref="layouts/pulau_tunas_v1.json#nothing_here")
    assert_problem(assets.validate(pixel_checks=False), "collision_ref 'layouts/pulau_tunas_v1.json#nothing_here' names no fixed object")


# --------------------------------------------------------------------------- road and shore pixels

@needs_decoder
def test_road_mask_with_the_wrong_shape(assets):
    corner = assets.file("kingdom", "road_basic--mask_06").read_bytes()        # E+S drawn in the N+S slot
    assets.replace_file("kingdom", "road_basic--mask_05", corner)
    assert_problem(assets.validate(),
                   "kingdom/road_basic--mask_05: N edge is connected in mask 05 but has 0 road runs",
                   "kingdom/road_basic--mask_05: E side is not connected in mask 05 but road pixels reach")


@needs_decoder
def test_road_seam_colour_must_match(assets):
    cobble = assets.file("kingdom", "road_basic--mask_10").read_bytes()        # kingdom art in the kampung pack
    assets.replace_file("perkampungan", "road_basic--mask_10", cobble)
    # every other kampung mask now disagrees with the swapped straight at the shared edge
    assert_problem(assets.validate(), "perkampungan/road_basic--mask_02: E edge colour differs from mask 10",
                   "perkampungan: road mask 10 E edge and mask 08 W edge differ in colour", "visible seam")


@needs_decoder
def test_shore_tile_must_match_its_mask(assets):
    north = assets.file("city", "shore--mask_01").read_bytes()                 # land N drawn in the land-S slot
    assets.replace_file("city", "shore--mask_04", north)
    assert_problem(assets.validate(), "city/shore--mask_04: S edge should show land",
                   "city/shore--mask_04: N edge should be open water")


@needs_decoder
def test_anchored_prop_silhouette_mass(assets):
    icon_like = assets.file("perkampungan", "road_basic--mask_00").read_bytes()  # tiny isolated pad, 128 x 128
    for theme in THEMES:
        assets.edit(theme, "quest_board--base", pixel_size={"width": 128, "height": 128}, css_cell_size={"width": 64, "height": 64},
                    overhang={"top": 0, "left": 0, "right": 0})
    assets.replace_file("city", "quest_board--base", icon_like)
    assets.replace_file("kingdom", "quest_board--base", assets.file("kingdom", "road_basic--mask_15").read_bytes())
    assets.replace_file("perkampungan", "quest_board--base", assets.file("perkampungan", "road_basic--mask_05").read_bytes())
    report = assets.validate()
    assert_problem(report, "city/quest_board--base: silhouette area is", "x the perkampungan variant",
                   "must sit in the bottom quarter of the footprint")


# --------------------------------------------------------------------------- shared overlays

def test_required_overlay_missing(assets):
    path = assets.static / "shared" / "manifest.json"
    shared = json.loads(path.read_text())
    shared["assets"] = [e for e in shared["assets"] if not e["asset_id"].startswith("overlay_focus")]
    path.write_text(json.dumps(shared))
    assert_problem(assets.validate(pixel_checks=False), "shared: required overlay 'overlay_focus--*' is missing")


def test_overlay_must_be_safe_svg(assets):
    path = assets.static / "shared" / "manifest.json"
    shared = json.loads(path.read_text())
    entry = next(e for e in shared["assets"] if e["asset_id"] == "overlay_valid--base")
    svg = assets.static / "shared" / "overlays" / "overlay_valid--base.svg"
    data = svg.read_bytes().replace(b"</svg>", b"<script>alert(1)</script><text>OK</text></svg>")
    svg.write_bytes(data)
    entry["source"]["checksum"] = "sha256:" + hashlib.sha256(data).hexdigest()
    path.write_text(json.dumps(shared))
    assert_problem(assets.validate(pixel_checks=False), "shared/overlay_valid--base: <script> is not allowed",
                   "shared/overlay_valid--base: <text> is not allowed")


def test_overlay_missing_file_and_stale_checksum(assets):
    (assets.static / "shared" / "overlays" / "overlay_selection--base.svg").unlink()
    svg = assets.static / "shared" / "overlays" / "overlay_invalid--base.svg"
    svg.write_bytes(svg.read_bytes() + b"\n")
    assert_problem(assets.validate(pixel_checks=False), "shared/overlay_selection--base: missing file",
                   "shared/overlay_invalid--base: checksum is stale")


# --------------------------------------------------------------------------- crafted images (need Pillow)

def _encode(img, alpha=True, lossless=False):
    import io
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=88, method=4, lossless=lossless, alpha_quality=100)
    return buf.getvalue()


def test_road_band_width_must_match_every_other_mask(assets):
    image = pytest.importorskip("PIL.Image", reason="crafting a bad image needs Pillow: pip install -r requirements-assets.txt")
    road = image.open(assets.file("city", "road_basic--mask_05")).convert("RGBA")
    narrow = road.copy()
    narrow.paste((0, 0, 0, 0), (34, 0, 40, 128))     # trim 6 px off the west side of the band
    assets.replace_file("city", "road_basic--mask_05", _encode(narrow))
    assert_problem(assets.validate(), "city/road_basic--mask_05: N edge road band is centred at",
                   "city/road_basic--mask_05: N edge profile")


def test_shifted_prop_drifts_from_its_anchor(assets):
    image = pytest.importorskip("PIL.Image", reason="crafting a bad image needs Pillow: pip install -r requirements-assets.txt")
    board = image.open(assets.file("kingdom", "quest_board--base")).convert("RGBA")
    shifted = image.new("RGBA", board.size, (0, 0, 0, 0))
    shifted.paste(board.crop((0, 0, 128, 176)), (18, 0))   # 18 px east and floating 16 px up
    assets.replace_file("kingdom", "quest_board--base", _encode(shifted))
    assert_problem(assets.validate(), "kingdom/quest_board--base: silhouette centre", "off the anchor",
                   "drift from perkampungan")


def test_oversized_tile(assets):
    image = pytest.importorskip("PIL.Image", reason="crafting a bad image needs Pillow: pip install -r requirements-assets.txt")
    noise = image.frombytes("RGB", (128, 128), os.urandom(128 * 128 * 3))
    data = _encode(noise, lossless=True)
    assert len(data) > 32 * 1024
    for theme in THEMES:
        assets.edit(theme, "water--base", max_bytes=64 * 1024)
    assets.replace_file("kingdom", "water--base", data)
    assert_problem(assets.validate(), "kingdom/water--base:", "exceeds the pipeline 18.6 tile/road target 32768")
