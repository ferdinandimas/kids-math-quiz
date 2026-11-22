# KidQuest building sprite maps

This directory is the source-art handoff area for KQ-026–KQ-028. KQ-025 supplies only the frozen
contract, deterministic graybox, checklist, and empty theme placeholders; it does not supply
production theme maps.

Expected theme outputs:

```text
design/kidquest/sprite-maps/
  perkampungan/buildings_v1.png
  kingdom/buildings_v1.png
  city/buildings_v1.png
```

The authoritative machine-readable layout is
[`content/kidquest/building_sprite_map.v1.json`](../../../content/kidquest/building_sprite_map.v1.json).
Do not infer geometry from this guide or from a generated image when the contract has a number.

## Frozen v1 geometry

- Canvas: 1536 × 1024 PNG, 8-bit RGBA, sRGB, fully transparent background.
- Grid: 3 columns × 2 rows of 512 × 512 slots, no gutters, labels, guides, or grid lines in a theme map.
- Slot order: `starter_house`, `garden`, `bakery`, `park`, `bridge`, `market_stall`.
- Scale: 128 source pixels per logical cell. Never enlarge a small footprint to fill its slot.
- Every slot anchor: local (256, 464). Safe bounds: local x 32–480 and y 32–480. Shadow limit: y 480.
- Camera: viewer south, looking north and down; south face parallel to the canvas; verticals remain
  vertical; no perspective convergence.
- Light: one upper-left/north-west key; cast shadows fall lower-right.
- Outline: choose one weight from 4–8 source pixels at `@2x`, then apply it consistently to all six
  buildings in a theme map.
- Adopted overhangs: 2×2 top 1.0 cell (128 px), 1×2 top 0.25 cell (32 px), 1×1 top 0.75 cell
  (96 px). These are the KQ-006 follow-up values, adopted without adjustment.

The graybox is
[`design/kidquest/templates/building_sprite_map_graybox_v1.png`](../templates/building_sprite_map_graybox_v1.png).
Its guides are reference-only and must not appear in a production theme map.

## Validation

From the repository root:

```bash
# Prove the committed graybox is the byte-exact deterministic render and validate its overlays.
PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py --check

# Regenerate the reference deterministically from the contract.
PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py \
  --render-graybox design/kidquest/templates/building_sprite_map_graybox_v1.png

# Strictly validate the graybox/reference overlay profile.
PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py \
  design/kidquest/templates/building_sprite_map_graybox_v1.png

# Validate a production theme map (theme artwork is not compared to graybox pixels).
PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py \
  design/kidquest/sprite-maps/kingdom/buildings_v1.png --theme kingdom
```

The validator uses only the Python standard library. It checks the contract and schema, cross-checks
slot IDs/footprints/entrances with `buildings.json`, decodes 8-bit RGBA PNG, requires sRGB, checks
canvas and safe bounds, requires visible content at footprints/anchors/entrances, rejects colored
fully-transparent pixels (matte halos), and rejects isolated semi-transparent background components.

## Acceptance checklist for every theme

Apply these checks to all six buildings and review at 38, 48, and 64 CSS pixels per world cell:

- Friendly children's-product silhouette; category and entrance remain clear at 38 px.
- Theme materials may change, but scale, footprint, anchor, entrance, camera, light, and shadow limit do not.
- No text, brands, advertising, currency symbols, coins, banknotes, prices, cash registers, payment
  terminals, automatic-payment cues, or gambling cues.
- No matte halo or semi-transparent background. Alpha-zero pixels have RGB (0, 0, 0); partial alpha
  is limited to antialiasing and connected ground shadows.
- Human Indonesian cultural review is recorded. Automated validation is not cultural approval.

| Building | Theme treatments (Kingdom / City / Perkampungan) | Required visual cues | Prohibited cues |
|---|---|---|---|
| `starter_house` | Keeper's Cottage / Colorful Townhouse / Rumah Kampung | Safe home, clear south door, first-achievement landmark | Shopfront, income/payout, machinery, damage/danger |
| `garden` | Royal Herb Garden / Community Garden / Kebun Tunas | Countable planting groups, accessible boundary, south entrance | Sale signs, payout, hazardous tools, dense unreadable foliage |
| `bakery` | Castle Bakehouse / City Bakery / Warung Roti | Bread/oven purpose without text, south door, friendly preparation | Prices/brands, dangerous flame, factory machinery |
| `park` | Royal Garden / City Park / Lapangan Kampung | Open community space, pattern-friendly layout, south entrance | Vendor/shop, production/payout, blocked entrance |
| `bridge` | Stone Story Bridge / Pedestrian City Bridge / Jembatan Kayu-Bambu | Open north/south ends, 1×2 pedestrian deck, water-safe crossing | Toll/money, vehicle road, blocked ends, broken/unsafe structure |
| `market_stall` | Royal Bazaar Stall / City Kiosk / Kios Pasar | Countable display, visibly smaller 1×1 scale, south entrance | Prices/brands, child trading, automatic payment, gambling |

## Generation prompt template

Copy this template into the theme task and replace every bracketed field. Attach the graybox as the
geometry reference. The generator must return one complete map, never six independent images.

```text
Create one KidQuest building sprite map for theme [THEME_ID: perkampungan|kingdom|city].

OUTPUT
- Exactly 1536 x 1024 px, 8-bit RGBA PNG, sRGB, fully transparent background.
- Exactly six 512 x 512 slots in a 3 x 2 grid with no gutters, guides, labels, or grid lines.
- Slot order, left-to-right then top-to-bottom:
  1 starter_house, 2 garden, 3 bakery, 4 park, 5 bridge, 6 market_stall.
- Use the attached building_sprite_map_graybox_v1.png as immutable geometry.

GEOMETRY
- 128 source px per logical world cell; keep true relative scale.
- Every footprint bottom-center anchor is slot-local (256, 464).
- No alpha outside slot-local x 32..480 or y 32..480; shadows stop at y 480.
- Footprints: four 2x2 buildings, bridge 1x2 north-south, market_stall 1x1.
- Entrances: south for every building; bridge also has north at (256, 208).
- Never crop, pad, stretch, rotate, independently rescale, or move a slot.

CAMERA AND LIGHT
- Friendly three-quarter front view: viewer south looking north and down.
- South faces parallel to canvas; vertical edges vertical; no perspective convergence.
- One upper-left/north-west key light; shadows fall lower-right.
- Use one consistent outline weight in the 4..8 source-px range for all six buildings.

THEME AND CONTENT
- Art direction: [PASTE THE THEME-SPECIFIC KQ-026/027/028 BRIEF].
- Follow the per-building required/prohibited checklist in this README and the contract.
- No text, brands, advertising, money, prices, payment, payout, or gambling cues.
- Optimize silhouettes and entrances for review at 38, 48, and 64 px per cell.
- Cultural accuracy is pending human Indonesian review; do not claim approval.

ALPHA AND EDGES
- Alpha-zero background pixels use RGB 0,0,0. No matte fringe or colored transparent pixels.
- Partial alpha only for antialiased object edges and connected ground shadows.

REVISION POLICY
- Return the complete six-slot map on every revision.
- Feedback may identify a failing slot, but do not transplant, crop, patch, or rescale a single
  building from another generation. Preserve every accepted slot's locked geometry.

PROVENANCE TO RETURN WITH THE PNG
- creator: [VALUE]
- model_or_tool: [VALUE]
- model_or_tool_version: [VALUE]
- generation_date: [YYYY-MM-DD]
- prompt_revision: [VALUE]
- contract_id: building_sprite_map.v1
- source_graybox: design/kidquest/templates/building_sprite_map_graybox_v1.png
- seed_or_job_id: [VALUE]
- rights_or_license_status: [VALUE]
- human_cultural_review_status: pending
- art_review_status: pending
- post_generation_edits: [NONE OR DESCRIBE]
```

If the tool cannot produce 1536 × 1024 directly, generate exactly 3072 × 2048 and downscale exactly
50 percent. Never use any other crop, pad, stretch, or non-uniform scaling workflow.
