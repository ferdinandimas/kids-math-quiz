"""Theme parity on logical asset IDs, and the asset manifest schema contract."""

import json
import re

import pytest

from app.domain.kidquest.content import CONTENT_DIR, load_catalog, load_raw, required_theme_assets
from app.domain.kidquest.theme import DEFAULT_THEME_ID, THEME_IDS, is_supported_theme


@pytest.fixture(scope="module")
def raw():
    return load_raw()[0]


def test_supported_themes():
    assert THEME_IDS == ("perkampungan", "kingdom", "city")
    assert DEFAULT_THEME_ID == "perkampungan"
    assert is_supported_theme("city") and not is_supported_theme("space")


def test_every_theme_provides_the_same_56_logical_assets(raw):
    required = required_theme_assets(raw)
    themes = load_catalog().themes

    assert len(required) == 56
    assert {tid: set(t["assets"]) for tid, t in themes.items()} == {tid: required for tid in THEME_IDS}


def test_themes_carry_only_presentation_fields(raw):
    for theme in raw["themes"]["themes"]:
        assert set(theme) == {"id", "name", "labels", "art_reference_names", "assets"}  # No footprint, cost, or geometry overrides.


def test_asset_ids_match_the_manifest_schema_pattern(raw):
    pattern = re.compile(raw["assets_schema"]["properties"]["asset_id"]["pattern"])

    assert all(pattern.match(asset) for asset in required_theme_assets(raw))
    assert not pattern.match("starter_house@2x.webp")


def test_asset_schema_requires_the_pipeline_manifest_fields(raw):
    schema = json.loads((CONTENT_DIR / "assets.schema.json").read_text(encoding="utf-8"))

    assert schema == raw["assets_schema"]
    assert {"asset_id", "category", "content_version", "required_in_themes", "runtime_path", "pixel_size", "layer",
            "alpha_required", "max_bytes", "source", "decorative"} <= set(schema["required"])
    assert schema["properties"]["required_in_themes"]["items"]["enum"] == list(THEME_IDS)
    assert "top-left (north-west) cell" in schema["description"]
