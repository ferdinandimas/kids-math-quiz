---
id: KQ-026
title: Generate the Kingdom building sprite map
status: IN_REVIEW
owner: codex-core
depends_on: [KQ-025]
milestone: Asset
updated: 2026-11-22
---

# KQ-026 — Generate the Kingdom building sprite map

## Outcome

One transparent, internally consistent Kingdom sprite map contains all six production buildings in the exact KQ-025 slots.

## Source references

- [KQ-025 building sprite-map contract](KQ-025-building-sprite-map-contract.md)
- [PRD §11.3 theme system and §11.7 building catalog](../KidQuest_Build_Your_World_PRD_v1.4.md)
- [Visual pipeline §10 theme art bibles and §12.3 building brief](../KidQuest_Visual_Design_Asset_Pipeline.md)

## Fixed sprite-map layout (copy of KQ-025 contract v1 — do not change)

All three theme maps use exactly this layout. If this copy and KQ-025 ever differ, KQ-025 wins and this packet must be corrected before generation.

- One PNG, **1536 × 1024 px**, RGBA, sRGB, fully transparent background, saved as `design/kidquest/sprite-maps/kingdom/buildings_v1.png`.
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

Use the approved Kingdom style bible consistently across the full map: friendly storybook architecture, coherent stone/wood/material language, shared palette, one light direction, one camera, consistent outlines and shadows, and no frightening military or class-status cues.

## Required building checks

| Slot | Logical ID | Variant | Mandatory visual communication |
|---:|---|---|---|
| 1 | `starter_house` (2×2) | Keeper's Cottage | Safe home, clear south door, first achievement; no income/supply cue |
| 2 | `garden` (2×2) | Royal Herb Garden | Countable planting groups and accessible boundary; no text or guaranteed-income cue |
| 3 | `bakery` (2×2) | Castle Bakehouse | Bread/oven purpose and clear south door; no brand, price, or unsafe heat emphasis |
| 4 | `park` (2×2) | Royal Garden | Open, pattern-friendly community space; no supply, income, or stat-bonus cue |
| 5 | `bridge` (1×2, N–S) | Stone Story Bridge | Two unobstructed short-end connections and safe crossing profile; no toll cue |
| 6 | `market_stall` (1×1) | Royal Bazaar Stall | Countable displayed items; no currency, advertising, trading, or automatic-payment cue |

## Scope and deliverables

1. Generate all six buildings together from the frozen contract, Kingdom style bible, graybox map, and approved prompt template.
2. Preserve the fixed layout above: transparent background, slot order, 512 × 512 slot resolution, safe padding, 128 px-per-cell scale, camera, lighting, and anchor (256, 464).
3. Iterate by editing the complete source map or a controlled masked region; do not replace a rejected cell with an unrelated standalone generation.
4. Store the production map, generation prompt/settings/reference provenance, revision history, and review captures.
5. Complete every building row above even if only one building requires revision.

## Acceptance criteria

- [x] The map is exactly 1536 × 1024 with the six buildings in the slot order above, and contract validation finds no slot, size, padding, alpha, or bounds violation.
- [x] Each building's ground contact and entrance line up with its footprint rectangle and anchor in the graybox overlay; small buildings keep world scale.
- [x] All six buildings visibly belong to one Kingdom art system.
- [x] Every building-specific check passes at minimum supported display size.
- [x] No labels, currency, numerical amounts, status badges, grid guides, or background are baked into the map.
- [ ] The map is approved for KQ-029 extraction without manual geometry repair.

## Verification

- Run KQ-025 contract validation and capture the complete map at native and minimum display sizes.
- Review the six cells individually and as one sheet against the Kingdom style bible.
- Record prompt, references, model/tool, generation date, revisions, and reviewer decision.

## Out of scope

- City/Kampung maps, slicing runtime sprites, manifest generation, roads, terrain, and gameplay code.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Theme-wide sprite-map generation task created. |
| 2026-11-21 | planning | NOT_STARTED | Embedded KQ-025 contract v1 layout (slot order, 512×512 slots, anchor, scale) in the packet. |
| 2026-11-22 | codex-core | IN_PROGRESS | Claimed under the lead exception allowing KQ-026 to begin while KQ-025 and KQ-006 remain `IN_REVIEW`; generating and validating the complete Kingdom map. |
| 2026-11-22 | codex-core | IN_REVIEW | Generated and iterated the complete six-slot map with the built-in image tool, performed only permitted background cleanup and whole-building translations, passed the Kingdom contract validator, and reviewed 28 native/38/48/64 captures. Independent art and cultural reviews remain pending. |

## Building review matrix

| Slot / building | Native | 38 px/cell | 48 px/cell | 64 px/cell | Required/prohibited-cue review | Known weakness |
|---|---|---|---|---|---|---|
| 1 `starter_house` | Pass | Pass | Pass | Pass | Safe home silhouette and centered south door are clear; no shop, supply, or income cue. | Gold roof finial is an architectural ornament, but art review should confirm it cannot read as a coin cue. |
| 2 `garden` | Pass | Pass | Pass | Pass | Four countable herb beds, low accessible boundary, and open south approach remain clear; no text, tools, sale, payout, or guaranteed-income cue. | Gold corner finials are decorative; independent art review should confirm the cue remains civic rather than monetary. |
| 3 `bakery` | Pass | Pass | Pass | Pass | Three loaves, safe oven/chimney, and centered south door communicate bakehouse purpose; no brand, price, dangerous flame, or factory machinery. | Oven/chimney is a strong secondary silhouette, though the door and bread remain readable at 38 px. |
| 4 `park` | Pass | Pass | Pass | Pass | Open symmetrical community layout, bench, flower groups, fountain, and south entry remain readable; no vendor, supply, production, income, or stat-bonus cue. | Small fountain water detail simplifies at 38 px but still reads as a calm civic focal point. |
| 5 `bridge` | Pass | Pass | Pass | Pass | Narrow north–south pedestrian deck is continuous through both unobstructed short-end connections; no toll, vehicle, gate, or unsafe/broken cue. | Reads as a flat stone causeway rather than a visibly arched story bridge. |
| 6 `market_stall` | Pass | Pass | Pass | Pass | Visibly smallest 1×1 asset; bread, apples, and folded-cloth display groups remain countable; centered timber threshold reaches the anchor; no price, cash, advertising, payment, trading scene, or gambling cue. | Canopy and display simplify most at 38 px, but three groups and stall category remain distinguishable. |
| 2026-11-22 | lead | IN_REVIEW | **Lead review passed; stays `IN_REVIEW`.** Independently ran the sprite-map validator for Kingdom (OK; SHA-256 starts c34df76c), confirmed generation provenance (built-in image tool, whole map in one call, deterministic post-processing only), re-ran the full suite (1014 passed, 3 skipped) and the golden asset validator (OK), and viewed the full map and the 38 px proof. Storybook stone-and-timber look, all six buildings recognisable at 38 px, one camera/light, matches the Kingdom golden palette. Weaknesses accepted for now: outline is heavier than the golden quest board; the bridge reads as a flat causeway rather than an arch; the round gold finials should be confirmed by the art reviewer as not reading as coins. Independent product-owner and cultural review still pending; not `DONE`, and KQ-029 must verify geometry again on extraction. |

## Completion handoff

- **Summary:** Produced one internally consistent, transparent Kerajaan Ceria atlas containing all six buildings in the frozen slot order and true relative scale. Final status is `IN_REVIEW`; KQ-025 and KQ-006 remain `IN_REVIEW`, so this task is not eligible for `DONE`.
- **Sprite-map source/output:** `design/kidquest/sprite-maps/kingdom/buildings_v1.png` (1536×1024 RGBA/sRGB; SHA-256 `c34df76c8438370f0bab768d840ef785b127e06443ef5b47cd4307f954f2ea75`); five generated revision snapshots in `revisions/`; 28 review captures in `review/`.
- **Generation provenance:** `design/kidquest/sprite-maps/kingdom/PROVENANCE.md` records tool/model visibility, full base prompt, references, settings, every revision/job, permitted post-processing, checksum, and review status.
- **Building review matrix:** Completed above. All six pass native and 38/48/64 proofs; known weaknesses are recorded rather than hidden.
- **Contract validation:** `PYTHONPATH=. .venv/bin/python scripts/validate_building_sprite_map.py design/kidquest/sprite-maps/kingdom/buildings_v1.png --theme kingdom` → `Building sprite map OK: theme kingdom: 1536 x 1024 RGBA/sRGB; six slots; padding, alpha, footprint, anchor, and entrances valid`.
- **Commit/artifact revision:** No commit created, per assignment. Final artifact SHA-256 is recorded above.
- **Follow-ups:** Lead independently reviews art quality and the gold-finial/flat-bridge weaknesses; human Indonesian cultural review and product-owner approval remain pending. After approval and dependency completion, KQ-029 may extract without geometry repair.

