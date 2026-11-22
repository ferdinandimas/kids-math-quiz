---
id: KQ-025
title: Define the shared building sprite-map contract
status: IN_REVIEW
owner: codex-core
depends_on: [KQ-006]
milestone: Asset
updated: 2026-11-22
---

# KQ-025 — Define the shared building sprite-map contract

## Outcome

Kingdom, City, and Kampung (`perkampungan`) generation use one immutable sprite-map layout and visual-geometry contract. Each theme task generates all six buildings in one image, in the same slot order and at the same slot resolution, so every building in every theme slices and anchors identically without per-theme or per-building adjustment.

## Source references

- [PRD §11.4 world projection, grid, and render layers](../KidQuest_Build_Your_World_PRD_v1.4.md)
- [PRD §11.7 building catalog](../KidQuest_Build_Your_World_PRD_v1.4.md)
- [Visual pipeline §11 geometry templates, §12.3 building brief, §14 manifest contract](../KidQuest_Visual_Design_Asset_Pipeline.md)
- [Implementation plan §7A M3A](../KidQuest_Implementation_Plan.md)

## Fixed sprite-map layout (contract v1)

These values are frozen by this packet. KQ-026, KQ-027, and KQ-028 copy them verbatim. Once KQ-026, KQ-027, or KQ-028 begins, any change requires a new contract version and regeneration and reapproval of every affected theme map.

### Canvas

- One PNG per theme, **1536 × 1024 px**, RGBA, sRGB, fully transparent background.
- A **3 columns × 2 rows** grid of equal **512 × 512 px** slots, with no gutters, labels, grid lines, or guides in the image.
- Every slot has the same resolution regardless of building footprint, so extraction is a fixed grid cut.
- If a generation tool cannot output 1536 × 1024 directly, generate at exactly 3072 × 2048 and downscale by exactly 50%. Never crop, pad, stretch, or non-uniformly scale the map.

### Scale and anchor (identical in every slot and every theme)

- World scale: **128 px per logical world cell** (the pipeline's `@2x` export cell). A 2×2 building's ground footprint is 256 × 256 px; a 1×1 building's is 128 × 128 px.
- Buildings keep true world scale inside the equal slots: a 1×1 Market Stall is visibly smaller than a 2×2 House. Never enlarge a small building to fill its slot.
- **Anchor:** bottom-center of the footprint at slot-local **(256, 464)** for all six slots.
- **Safe padding:** 32 px on every slot edge. No pixel with alpha > 0 may fall outside slot-local x 32–480, y 32–480.
- Height and overhang may extend above and beside the footprint only inside the safe area. Ground shadow may extend at most to y = 480.

### Slot order (identical in every theme)

| Slot | Row / column | Slot rectangle on canvas (x, y, w, h) | Logical ID | Footprint | Footprint ground rectangle, slot-local (x1, y1 – x2, y2) | Entrance / connection points, slot-local |
|---:|---|---|---|---|---|---|
| 1 | 1 / 1 | 0, 0, 512, 512 | `starter_house` | 2×2 | 128, 208 – 384, 464 | South (256, 464) |
| 2 | 1 / 2 | 512, 0, 512, 512 | `garden` | 2×2 | 128, 208 – 384, 464 | South (256, 464) |
| 3 | 1 / 3 | 1024, 0, 512, 512 | `bakery` | 2×2 | 128, 208 – 384, 464 | South (256, 464) |
| 4 | 2 / 1 | 0, 512, 512, 512 | `park` | 2×2 | 128, 208 – 384, 464 | South (256, 464) |
| 5 | 2 / 2 | 512, 512, 512, 512 | `bridge` | 1×2, long axis north–south | 192, 208 – 320, 464 | North (256, 208) and South (256, 464) |
| 6 | 2 / 3 | 1024, 512, 512, 512 | `market_stall` | 1×1 | 192, 336 – 320, 464 | South (256, 464) |

The bridge's long axis is fixed north–south because rotation is fixed in the MVP; `pulau_tunas_v1` must define `bridge_zone` as a 1-wide × 2-tall zone (validated in KQ-004).

### Camera and light (identical in every theme)

- Three-quarter front view: the viewer is south of the building, looking north and down; front (south) faces are parallel to the canvas. No perspective convergence: vertical edges stay vertical and the ground footprint is drawn as a screen-space rectangle matching the square interaction cells.
- Single key light from the upper left (north-west); cast shadows fall toward the lower right and stay inside the shadow limit above.
- Outline weight, palette, and material rules are set per theme by the style guides. Outline weight must be one consistent range for all six buildings in a map; this task records that range in the contract.

### Files

- Contract: `content/kidquest/building_sprite_map.v1.json` (canvas, slots, rectangles, anchors, footprints, entrances, padding, shadow limit, color/alpha rules).
- Graybox reference map: `design/kidquest/templates/building_sprite_map_graybox_v1.png`.
- Theme source maps: `design/kidquest/sprite-maps/{theme_id}/buildings_v1.png`, where `theme_id` is `perkampungan`, `kingdom`, or `city`.

## Scope

1. Encode the fixed layout above as the machine-readable contract and a JSON Schema.
2. Create the transparent graybox reference map with each slot's footprint, anchor, entrance, safe padding, and shadow limit drawn as neutral shapes.
3. Record the outline range and the alpha/edge rules (no matte halos, no semi-transparent background) in the contract.
4. Define the per-building visual and prohibited-cue checklist used by all three theme tasks.
5. Write the generation prompt template that references the graybox map and states the slot order, scale, anchor, camera, and light rules, plus the revision policy and provenance fields.
6. Build the contract validator (canvas size, slot bounds, padding, alpha, footprint/anchor overlays) and document its command.

## Deliverables

- `content/kidquest/building_sprite_map.v1.json` and its JSON Schema.
- Graybox reference map and a human-readable guide.
- Per-building acceptance matrix and generation prompt template.
- Documented contract validation command.

## Acceptance criteria

- [x] The contract JSON matches the canvas, slot order, rectangles, anchors, footprints, and entrances in this packet exactly.
- [x] All six slot rectangles are equal size (512 × 512), exact, non-overlapping, and tile the 1536 × 1024 canvas.
- [x] Every slot uses anchor (256, 464), 128 px per world cell, and 32 px safe padding.
- [x] The bridge defines both connection points; all other buildings define the south entrance.
- [x] The graybox map passes the validator, slices into six 512 × 512 sprites, and reassembles pixel-perfectly.
- [x] KQ-026, KQ-027, and KQ-028 contain an identical copy of the fixed layout and can be executed without new layout decisions.

## Verification

- Run the contract validator against the graybox map.
- Slice and reassemble the graybox map pixel-perfectly.
- Overlay the six graybox sprites on the canonical world grid at 38 px and 64 px per cell and confirm anchors land on footprint bottom-centers.

## Out of scope

- Production theme artwork, final sprite extraction, gameplay integration, roads, terrain, props, and UI icons.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Replaced per-building generation with a shared sprite-map contract. |
| 2026-11-21 | planning | NOT_STARTED | Froze contract v1 in the packet: 1536×1024 canvas, six equal 512×512 slots, fixed slot order, anchor (256, 464), 128 px per cell. |
| 2026-11-22 | codex-core | IN_PROGRESS | Claimed under the recorded KQ-006 dependency exception; implementation and baseline verification beginning. |
| 2026-11-22 | codex-core | IN_PROGRESS | Adopted KQ-006's proposed overhang tops unchanged: 2×2 = 1.0 cell/128 px, 1×2 = 0.25 cell/32 px, 1×1 = 0.75 cell/96 px. Chose a consistent per-map outline range of 4–8 source px at `@2x` so it remains readable at the 38 px proof size. |
| 2026-11-22 | codex-core | IN_PROGRESS | Added the frozen JSON/schema, standard-library PNG renderer/validator, deterministic graybox, theme placeholders, checklist/prompt guide, and 22 focused tests. No production theme map or app/runtime file was changed. |
| 2026-11-22 | codex-core | IN_REVIEW | Verification complete: deterministic `--check` passed; official Draft 2020-12 schema validation passed; focused suite 22 passed; content/geometry/theme/asset suite 142 passed, 3 skipped; final full suite 1014 passed, 3 skipped. Baseline sandbox run was 991 passed, 3 skipped, 1 socket-permission error; unrestricted final run proves it was environmental. |
| 2026-11-22 | lead | IN_REVIEW | **Lead review passed; stays `IN_REVIEW`** (cannot be `DONE` before KQ-006). Independently ran the sprite-map validator (graybox strict check OK, `--check` deterministic bytes match, 21,333 bytes), its tests (22 passed), `validate_kidquest_content.py` (OK) and the full suite (1014 passed, 3 skipped; no stray DB file). Viewed the graybox PNG: six 512x512 slots in the frozen order, 2x2 houses, 1x2 bridge with north/south entrances, 1x1 stall, anchor (256,464) in every slot. Checked contract slots against the packet. Accepted Codex decisions: overhangs 128/32/96 px, outline 4-8 px at @2x, complete-six-slot revisions only. KQ-026-028 may be generated against this contract. |

## Completion handoff

- **Summary:** Implemented the frozen v1 building sprite-map contract, deterministic transparent graybox, standard-library validator/renderer, cross-theme visual checklist, and complete generation prompt/provenance handoff. Set to `IN_REVIEW`; KQ-006 remains `IN_REVIEW`, so this task is not eligible for `DONE` yet.
- **Contract/reference files:** `content/kidquest/building_sprite_map.v1.json`; `content/kidquest/building_sprite_map.schema.json`; `design/kidquest/templates/building_sprite_map_graybox_v1.png`; `design/kidquest/sprite-maps/README.md`; `scripts/validate_building_sprite_map.py`; `tests/unit/kidquest/test_building_sprite_map.py`.
- **Frozen contract version:** v1 (layout fixed in this packet)
- **Verification performed:** `PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py --check` passed (21,333-byte byte-exact render); direct graybox and `--theme kingdom` validation passed; `PYTHONPATH=. .venv/bin/python scripts/validate_kidquest_content.py` passed; official Draft 2020-12 schema validation passed; `.venv/bin/python -m pytest -q tests/unit/kidquest/test_building_sprite_map.py` → 22 passed; content/geometry/theme/asset regression set → 142 passed, 3 skipped; `.venv/bin/python -m pytest -q` outside the socket-restricted sandbox → 1014 passed, 3 skipped. Slice/reassembly and 38/48/64 px anchor proofs are focused tests.
- **Commit/artifact revision:** pending lead commit. Contract SHA-256 `bfef08f70c7d916e8b27a2e561d46e1348cf4d4cd603b21df7dbea5724fcd695`; schema `3e9793cbfb0fa0d3a44bd4f966d9be1260129030653d8692dd722bf9c2b9c3c5`; graybox `65eb52c5a7574592a64eb7d97e9837a3b9518b9981b2bf31d173f768d4fc4e40`.
- **Follow-ups:** Lead independently reviews and accepts. KQ-026–KQ-028 must generate complete maps from the graybox/prompt and record human Indonesian cultural review plus art review; automated validation is not cultural approval. Any future layout change requires a new contract version and regeneration/reapproval of every affected theme map.
