# KQ-028 Perkampungan building sprite-map provenance

## Final artifact

- Output: `buildings_v1.png`
- Contract: `building_sprite_map.v1`
- Generation date: 2026-11-22
- Creator/operator: `codex-core`
- Tool: OpenAI built-in image generation tool (`image_gen`)
- Model/tool version: not exposed by the built-in tool
- Final selected generation: revision 2, followed only by deterministic alpha cleanup and whole-sprite vertical translations
- Final SHA-256: `a09ff1abe2be78af3f909944c0bc25fb2638c059a2f2b792d01bf008a0927632`
- Rights/license status: generated for this project through the OpenAI tool; use remains governed by the applicable OpenAI terms and repository licensing review. The inputs were repository-owned project references; no external third-party art was introduced.
- Human cultural review status: pending lead/product-owner review
- Art review status: `codex-core` self-review complete at native, 38, 48, and 64 px per world cell; independent lead review pending

## References and their roles

- `design/kidquest/templates/building_sprite_map_graybox_v1.png` — immutable geometry reference only; no guides retained.
- `static/images/kidquest/themes/perkampungan/props/quest_board--base@2x.webp` — palette, outline, material, camera, and light reference.
- `static/images/kidquest/themes/perkampungan/terrain/ground_buildable--base@2x.webp` — palette/value reference only.
- `static/images/kidquest/themes/perkampungan/roads/road_basic--mask_15@2x.webp` — palette/value reference only.
- `static/images/kidquest/themes/perkampungan/icons/theme_thumbnail--base@2x.webp` — whole-theme cohesion reference only.
- `design/kidquest/art-bibles/kampung-ceria.md` and pipeline §§10, 12.3 — cultural/material and per-building constraints.

## Generation settings

- Built-in mode: generate/edit with local reference paths
- `transparent_background`: `true` for every revision
- Requested canvas: 1536 × 1024, one complete 3 × 2 map
- Requested camera: orthographic three-quarter front, viewer south looking north/down
- Requested light: one upper-left/north-west key
- Requested outline: consistent 5–6 source px, `#26352B`
- Seed: not exposed

## Prompt revision 1 — complete map generation

Job/output ID: `exec-18f4641f-bda3-47e9-be3d-5dfd3aedeaf1`

Prompt:

> Create one complete 1536 × 1024 transparent Kampung Ceria building sprite map in a 3 × 2 grid, ordered starter house, garden, bakery, park, bridge, market stall. Use the graybox as immutable geometry and the Perkampungan golden assets only as style references. Keep 128 px per cell, anchor every slot at local (256,464), use four 2×2 footprints, a north-south 1×2 bridge, and a visibly smaller 1×1 market stall. Use a friendly orthographic three-quarter front view, one upper-left light, a consistent dark-green outline, warm timber, bamboo/weave, terracotta tile, cream, leaf green, and rounded stone. Communicate a safe Rumah Kampung; a three-group accessible Kebun Tunas; a bread-and-enclosed-oven Warung Roti; an open Lapangan Kampung; a safe open-ended Jembatan Kayu-Bambu; and a compact Kios Pasar with three produce baskets. Return only the six sprites on true transparency, with no background, terrain, guides, text, numbers, currency, advertising, brands, people, symbols, poverty, damage, hazards, water, or watermark.

Result/reason for revision: all six designs were strong and consistent, but the generated sprites filled too much of their slots, several anchors missed, and low-alpha glow/background pixels failed the contract.

## Prompt revision 2 — selected complete-map edit

Job/output ID: `exec-3025b951-46b0-4b13-8a14-af28915dd58b`

Prompt:

> Revise the entire complete map together. Preserve all six accepted designs, materials, palette, outline, camera, and lighting, but correct scale, geometry, and transparency. Match the graybox footprints: four 2×2 rectangles at local x128..384/y208..464, bridge deck x192..320/y208..464 with open north and south ends, and a clearly smaller market-stall footprint x192..320/y336..464. Put every bottom-center contact at (256,464), keep all content in x32..480/y32..480, remove low-alpha glow and detached shadows, and preserve all required/prohibited building cues. Return one complete transparent map; do not transplant standalone objects.

Result: selected for final art. It corrected the relative hierarchy and reduced all six sprites while preserving the strongest silhouettes and details. Exact anchors and background extraction were completed deterministically, without redrawing or rescaling.

## Prompt revision 3 — rejected geometry experiment

Job/output ID: `exec-ebc393be-8c08-487d-b604-6efa2b9dbea2`

Prompt:

> Preserve revision 2 and change only final placement and garden/park boundary width. Translate complete sprites toward (256,464), tighten the garden and park outer boundaries toward x128..384, preserve every prop and all style invariants, remove glow, and return the complete map.

Result/reason rejected: the generator moved the top-row building bottoms beyond y=480 and did not materially improve the garden/park proportions. Revision 2 remained the better complete-map source. The raw revision is retained for audit only.

## Deterministic post-generation edits

Implemented by `postprocess_buildings_v1.py` against `revisions/buildings_v1_r2_raw.png`:

1. Removed alpha values below 8, which were generated glow/haze rather than object edges.
2. Set RGB to `(0,0,0)` wherever alpha is zero and encoded an sRGB PNG.
3. Translated each complete sprite vertically only, preserving x, scale, and all pixels: slots 1–6 moved by `+3, +20, +3, +59, +62, +64` px respectively.
4. Removed 147 antialias/edge pixels that would otherwise exceed the frozen safe bound after anchor alignment, and 7 detached partial-alpha pixels with no opaque component.
5. Promoted generated near-opaque alpha values ≥250 to opaque so connected antialias edges validate correctly.

No building was redrawn, independently rescaled, rotated, stretched, or spliced. The final run retained 418,818 visible generated pixels and removed 71,138 low-alpha glow pixels.

## Revision files

- `revisions/buildings_v1_r1_raw.png` — initial full-map generation; SHA-256 `12a2324e77437a6067899b72b141f5ed7788fe07a31c8055cb2f344428ccab6d`
- `revisions/buildings_v1_r2_raw.png` — selected full-map generation; SHA-256 `a95ec5c7e9ad449bfe07742a6be35fb6b1cb749b6b5215e79af6c1e78f0904e1`
- `revisions/buildings_v1_r3_raw.png` — rejected placement experiment; SHA-256 `87df1c22c98c5824162509685a678cb3c85986dc34accf75d8205f74b3146c01`

## Review evidence

`make_review_captures.py` creates exact native slices plus full-map and per-building proofs at 38, 48, and 64 px per world cell under `review/`. All 28 captures were visually inspected by `codex-core` on 2026-11-22.

Known weaknesses retained for independent review:

- Garden and park bamboo posts/foliage extend roughly 30 px beyond the nominal footprint sides, while their walkable soil/earth areas remain centered on the 2×2 footprint.
- The bridge rail-post top reaches about 10 px above the preferred 32 px 1×2 overhang profile; it remains inside safe padding and reads clearly at 38 px.
- The market stall canopy and two footings overhang its 1×1 collision footprint, but its overall scale remains visibly smaller than every 2×2 building.
- Cultural accuracy has not been approved by a human reviewer; the sheet intentionally uses generic contemporary timber/bamboo/clay language and avoids region-specific sacred forms.
