---
id: KQ-028
title: Generate the Kampung building sprite map
status: IN_REVIEW
owner: codex-core
depends_on: [KQ-025]
milestone: Asset
updated: 2026-11-22
---

# KQ-028 — Generate the Kampung building sprite map

## Outcome

One transparent, internally consistent Kampung (theme ID `perkampungan`) sprite map contains all six production buildings in the exact KQ-025 slots.

## Source references

- [KQ-025 building sprite-map contract](KQ-025-building-sprite-map-contract.md)
- [PRD §11.3 theme system and §11.7 building catalog](../KidQuest_Build_Your_World_PRD_v1.4.md)
- [Visual pipeline §10 theme art bibles and §12.3 building brief](../KidQuest_Visual_Design_Asset_Pipeline.md)

## Fixed sprite-map layout (copy of KQ-025 contract v1 — do not change)

All three theme maps use exactly this layout. If this copy and KQ-025 ever differ, KQ-025 wins and this packet must be corrected before generation.

- One PNG, **1536 × 1024 px**, RGBA, sRGB, fully transparent background, saved as `design/kidquest/sprite-maps/perkampungan/buildings_v1.png`.
- **3 columns × 2 rows** of equal **512 × 512 px** slots; no gutters, labels, grid lines, or guides in the image.
- **128 px per world cell** in every slot. Buildings keep true world scale: never enlarge a 1×1 or 1×2 building to fill its slot.
- **Anchor** (bottom-center of footprint) at slot-local **(256, 464)** in every slot.
- **Safe padding** 32 px per slot edge: nothing visible outside slot-local x 32–480, y 32–480. Shadows end at y = 480.
- Three-quarter front view from the south, no perspective convergence; single key light from the upper left (north-west).
- If the tool cannot output 1536 × 1024, generate at exactly 3072 × 2048 and downscale by exactly 50%; never crop, pad, or stretch.

| Slot | Row / column | Slot rectangle (x, y, w, h) | Logical ID | Footprint | Footprint ground rectangle, slot-local | Entrance / connection, slot-local |
|---:|---|---|---|---|---|---|
| 1 | 1 / 1 | 0, 0, 512, 512 | `starter_house` | 2×2 | 128, 208 – 384, 464 | South (256, 464) |
| 2 | 1 / 2 | 512, 0, 512, 512 | `garden` | 2×2 | 128, 208 – 384, 464 | South (256, 464) |
| 3 | 1 / 3 | 1024, 0, 512, 512 | `bakery` | 2×2 | 128, 208 – 384, 464 | South (256, 464) |
| 4 | 2 / 1 | 0, 512, 512, 512 | `park` | 2×2 | 128, 208 – 384, 464 | South (256, 464) |
| 5 | 2 / 2 | 512, 512, 512, 512 | `bridge` | 1×2, long axis north–south | 192, 208 – 320, 464 | North (256, 208) and South (256, 464) |
| 6 | 2 / 3 | 1024, 512, 512, 512 | `market_stall` | 1×1 | 192, 336 – 320, 464 | South (256, 464) |

## Theme direction

Use the approved Kampung/Perkampungan style bible consistently across the full map: warm Indonesian neighborhood forms, coherent local wood/bamboo/tile/material language, shared palette, one light direction, one camera, consistent outlines and shadows, and culturally respectful details without poverty, exoticism, or unsafe construction stereotypes.

## Required building checks

| Slot | Logical ID | Variant | Mandatory visual communication |
|---:|---|---|---|
| 1 | `starter_house` (2×2) | Rumah Kampung | Safe home, clear south door, first achievement; no income/supply cue |
| 2 | `garden` (2×2) | Kebun Tunas | Countable planting groups and accessible boundary; no text or guaranteed-income cue |
| 3 | `bakery` (2×2) | Warung Roti | Bread/oven purpose and clear south door; no brand, price, or unsafe heat emphasis |
| 4 | `park` (2×2) | Lapangan Kampung | Open, pattern-friendly community space; no supply, income, or stat-bonus cue |
| 5 | `bridge` (1×2, N–S) | Jembatan Kayu-Bambu | Two unobstructed short-end connections and safe crossing profile; no toll/unsafe cue |
| 6 | `market_stall` (1×1) | Kios Pasar | Countable displayed items; no currency, advertising, trading, or automatic-payment cue |

## Scope and deliverables

1. Generate all six buildings together from the frozen contract, Kampung style bible, graybox map, and approved prompt template.
2. Preserve the fixed layout above: transparent background, slot order, 512 × 512 slot resolution, safe padding, 128 px-per-cell scale, camera, lighting, and anchor (256, 464).
3. Iterate by editing the complete source map or a controlled masked region; do not replace a rejected cell with an unrelated standalone generation.
4. Store the production map, generation prompt/settings/reference provenance, revision history, cultural-review evidence, and captures.
5. Complete every building row above even if only one building requires revision.

## Acceptance criteria

- [x] The map is exactly 1536 × 1024 with the six buildings in the slot order above, and contract validation finds no slot, size, padding, alpha, or bounds violation.
- [x] Each building's ground contact and entrance line up with its footprint rectangle and anchor in the graybox overlay; small buildings keep world scale.
- [x] All six buildings visibly belong to one respectful Kampung art system.
- [x] Every building-specific check passes at minimum supported display size.
- [x] No labels, currency, numerical amounts, status badges, grid guides, or background are baked into the map.
- [ ] Cultural review finds no poverty, exoticism, unsafe-material, or regional-tokenism problem.
- [ ] The map is approved for KQ-029 extraction without manual geometry repair.

## Verification

- Run KQ-025 contract validation and capture the complete map at native and minimum display sizes.
- Review the six cells individually and as one sheet against the Kampung style bible.
- Record prompt, references, model/tool, generation date, revisions, cultural reviewer, and decision.

## Building and cultural review matrix

Self-review by `codex-core` on 2026-11-22. Art/cultural approval remains with the independent lead and product owner.

| Slot / building | Required cues at native and 38/48/64 px | Prohibited cues | Geometry / style | Decision and known weakness |
|---|---|---|---|---|
| 1 `starter_house` / Rumah Kampung | Pass — unmistakable safe home; centered open south door and welcoming steps; first-achievement presence | Pass — no shop, money, production, damage, or danger cue | Pass — 2×2 scale, coherent woven/timber/clay language, shared camera/light | Self-review pass. Roof is the widest silhouette in the set but stays inside safe padding and reads cleanly at 38 px. |
| 2 `garden` / Kebun Tunas | Pass — three clearly countable planting rows/groups; low accessible bamboo boundary; centered south opening | Pass — no text, sale/payout cue, or hazardous tool | Pass — 2×2 soil area centered on footprint; shared palette/outline | Self-review pass. Bamboo posts extend about 30 px beyond nominal footprint sides as decorative overhang. |
| 3 `bakery` / Warung Roti | Pass — four large bread loaves, enclosed oven and chimney, centered south door; purpose survives 38 px | Pass — no brand, price, advertising, open flame, or factory cue | Pass — 2×2 scale, same house construction and lighting | Self-review pass. Oven is visually prominent but reads as enclosed and safe. |
| 4 `park` / Lapangan Kampung | Pass — open central space, two benches, circular stepping pattern, four planted corners, south opening | Pass — no vendor, supply, income, production, or status-bonus cue | Pass — 2×2 earth area centered on footprint; open, pattern-friendly silhouette | Self-review pass. Corner foliage/bamboo posts extend about 30 px beyond nominal footprint sides. |
| 5 `bridge` / Jembatan Kayu-Bambu | Pass — narrow north–south timber deck; both short ends open; sturdy paired bamboo rails | Pass — no toll, vehicle, damage, water, or unsafe gap cue | Pass — visibly 1×2 and much narrower than 2×2 sprites; shared camera/light | Self-review pass. Rounded north rail posts reach about 10 px above the preferred 32 px overhang profile, but remain in safe padding. |
| 6 `market_stall` / Kios Pasar | Pass — three countable produce baskets; compact open-front stall; clear 1×1 hierarchy at 38 px | Pass — no seller, currency, price, advertising, brand, checkout, automatic payment, or gambling cue | Pass — visibly smallest sprite; shared timber/bamboo/clay language | Self-review pass. Canopy and two footings overhang the 1×1 collision footprint, while the stall remains clearly smaller than every 2×2 building. |
| Cultural screen | Pass for self-review — cared-for contemporary shared space; generic timber/bamboo/clay construction | Pass for self-review — no poverty/decay, exoticism, costume, sacred/regional roof, textile, religious/political/ethnic symbol | Matches the draft Kampung bible and existing generated golden assets | **Human cultural approval pending.** This row is not cultural sign-off. |

## Out of scope

- Kingdom/City maps, slicing runtime sprites, manifest generation, roads, terrain, and gameplay code.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Theme-wide sprite-map generation task created. |
| 2026-11-21 | planning | NOT_STARTED | Embedded KQ-025 contract v1 layout (slot order, 512×512 slots, anchor, scale) in the packet. |
| 2026-11-22 | codex-core | IN_PROGRESS | Claimed KQ-028; beginning contract, style-reference, and generation review. |
| 2026-11-22 | codex-core | IN_PROGRESS | Generated three complete-map revisions with the built-in image tool. Selected revision 2 for its strongest scale hierarchy and silhouettes; rejected revision 3 because its top row exceeded the lower safe bound. |
| 2026-11-22 | codex-core | IN_PROGRESS | Deterministically removed generated low-alpha glow, normalized transparent RGB/sRGB metadata, and translated whole sprites vertically to the frozen anchors; no art was redrawn, rescaled, or spliced. Official validator passed. |
| 2026-11-22 | codex-core | IN_REVIEW | Inspected full-map and all six per-building captures at native, 38, 48, and 64 px per cell. Building self-review passed with documented overhang weaknesses; independent art and human cultural review remain pending. |
| 2026-11-22 | lead | IN_REVIEW | **Lead review passed; stays `IN_REVIEW`.** Independently ran the sprite-map validator for Kampung (OK; SHA-256 starts a09ff1ab), confirmed generation provenance (built-in image tool, whole map in one call, deterministic post-processing only), re-ran the full suite (1014 passed, 3 skipped) and the golden asset validator (OK), and viewed the full map and the 38 px proof. Stilt houses with woven walls, bamboo fences and clay-tile roofs; all six buildings recognisable and child-friendly; no poverty or sacred/regional motifs seen by the lead, but cultural review is still a human step. Weaknesses to handle in KQ-029: garden/park posts overhang the footprint by ~30 px, bridge rail posts exceed the overhang profile by ~10 px, market canopy overhangs its 1x1 footprint. Independent product-owner and cultural review still pending; not `DONE`, and KQ-029 must verify geometry again on extraction. |

## Completion handoff

- **Summary:** Generated one cohesive six-building Kampung Ceria sprite map and moved KQ-028 to `IN_REVIEW`. The production map is transparent RGBA/sRGB, preserves the frozen slot order and relative 2×2/1×2/1×1 scale hierarchy, and passes the KQ-025 validator.
- **Sprite-map source/output:** `design/kidquest/sprite-maps/perkampungan/buildings_v1.png`; raw complete-map generations under `revisions/`; exact native and 38/48/64 proofs under `review/`.
- **Generation provenance:** `design/kidquest/sprite-maps/perkampungan/PROVENANCE.md` records tool/version availability, prompts, references, job IDs, all revisions, deterministic post-processing, rights status, review state, SHA-256, and known weaknesses.
- **Building/cultural review matrix:** All six rows pass `codex-core` self-review at every proof size. Human Indonesian cultural approval and independent lead art review are pending; no cultural approval is claimed.
- **Contract validation:** `PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py design/kidquest/sprite-maps/perkampungan/buildings_v1.png --theme perkampungan` → OK: 1536×1024 RGBA/sRGB; six slots; padding, alpha, footprint, anchor, and entrances valid.
- **Commit/artifact revision:** No commit made per assignment. Final SHA-256 `a09ff1abe2be78af3f909944c0bc25fb2638c059a2f2b792d01bf008a0927632`.
- **Follow-ups:** Lead independently reviews art quality and geometry; product owner/human reviewer performs cultural review. Keep `IN_REVIEW` until those reviews and KQ-025/KQ-006 dependency state allow progression. KQ-029 may consume only after approval.

