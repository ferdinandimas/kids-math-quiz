---
id: KQ-029
title: Extract, manifest, and validate all building sprites
status: IN_REVIEW
owner: codex-core
depends_on: [KQ-026, KQ-027, KQ-028]
milestone: Asset
updated: 2026-11-22
---

# KQ-029 — Extract, manifest, and validate all building sprites

## Outcome

The three approved theme maps become deterministic runtime sprites and manifests, with every building aligned across themes and ready for gameplay integration.

## Scope

1. Validate source maps against the frozen KQ-025 contract without visually repairing theme artwork in this task.
2. Slice all 18 building/theme sprites with one fixed grid cut: six 512 × 512 slots per 1536 × 1024 map, in the KQ-025 slot order (1 `starter_house`, 2 `garden`, 3 `bakery`, 4 `park`, 5 `bridge`, 6 `market_stall`). Output to `static/images/kidquest/themes/{theme_id}/buildings/{asset_id}--base@2x.webp`. Every sprite keeps its 512 × 512 canvas and anchor (256, 464) so the renderer places all buildings in all themes with one rule.
3. Optimize exports without changing alpha edges, dimensions, color, anchor, or visual quality.
4. Create runtime manifests for logical ID, theme, source map/version, rectangle, footprint, anchor, entrance, collision reference, shadow bounds, and accessible label.
5. Build gallery comparisons and overlay matching logical buildings across all three themes.
6. Validate normal, selected, placement-valid, placement-invalid, locked/dimmed-context, and productive status-badge compositions without baking status into sprites.

## Required cross-theme checks

| Logical ID | Required validation |
|---|---|
| `starter_house` | Identical 2×2 footprint, south entrance, safe-home silhouette, no productive state |
| `garden` | Identical 2×2 footprint; planting groups readable; shared productive badges do not obscure groups |
| `bakery` | Identical 2×2 footprint and road-facing entrance; shared productive badges remain readable |
| `park` | Identical 2×2 footprint; pattern cues work without color alone; no productive state |
| `bridge` | Identical 1×2 footprint, water mask, draw order, and both road endpoints |
| `market_stall` | Identical 1×1 footprint; displayed groups readable; shared productive badges remain readable |

## Deliverables

- Reproducible extraction/optimization command or script.
- Eighteen runtime building sprites and versioned manifests.
- Three source-map records and prompt/provenance links.
- Cross-theme overlay gallery, state-composition gallery, and QA report.

## Acceptance criteria

- [x] Re-running extraction creates byte-identical or documented deterministically equivalent outputs.
- [x] Exactly six logical buildings × three themes are exported with no missing or duplicate mapping; slot N maps to the same logical ID in every theme.
- [x] All 18 sprites are 512 × 512 with anchor (256, 464) recorded identically in the manifest.
- [x] Matching buildings show no anchor, entrance, footprint, collision, endpoint, or hit-area drift between themes.
- [x] Transparent edges, shadows, color space, dimensions, filenames, and budgets pass automated validation.
- [x] Each building passes its row above and retains the prohibited-cue rules from all theme tasks.
- [x] Runtime can switch themes by changing asset references only; world state and geometry are unchanged.

## Verification

- Run contract, manifest, image-budget, alpha, naming, and completeness validators.
- Re-run extraction and compare outputs.
- Capture the full 6-building × 3-theme overlay and UI-state matrix at target densities.
- Smoke-test theme switching in the world renderer or approved gallery harness.

## Out of scope

- Regenerating rejected art, gameplay implementation, roads, terrain, props, animation, and post-MVP buildings. A visual rejection returns to KQ-026, KQ-027, or KQ-028.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Final sprite extraction and cross-theme QA task created. |
| 2026-11-22 | codex-core | IN_PROGRESS | Claimed under the lead exception: KQ-026, KQ-027, and KQ-028 remain `IN_REVIEW` after lead contract/art review, with product-owner art/cultural review deferred; KQ-029 may proceed but cannot be `DONE` before KQ-006, KQ-025, and KQ-026–KQ-028 are `DONE`. |
| 2026-11-22 | codex-core | IN_REVIEW | Extracted 18 fixed-slot sprites with lossless/exact libwebp, extended all three manifests and source records, added the `buildings` validation profile plus negative tests, and captured/inspected cross-theme and six-state galleries. All source contracts pass; decode round trips have max RGBA difference 0 and exact alpha; `--check` is byte-identical; asset tests 45 passed/3 skipped; final full suite 1,021 passed/3 skipped. QA and retained upstream weaknesses: `docs/evidence/kq-029/QA_REPORT.md`. Product-owner art/cultural review and dependency completion remain pending, so status is `IN_REVIEW`, never `DONE`. |

## Completion handoff

- **Summary:** Deterministically extracted all six KQ-025 slots from each theme map without modifying source art. Runtime geometry and asset references are theme-neutral; the API catalog already exposed all building IDs.
- **Source maps/versions:** `perkampungan/buildings_v1.png` SHA-256 `a09ff1a…7632`; `kingdom/buildings_v1.png` `c34df76…ea75`; `city/buildings_v1.png` `0338271…2534`; contract `building_sprite_map.v1`.
- **Runtime sprites/manifests:** 18 lossless/exact 512×512 WebPs under `static/images/kidquest/themes/*/buildings/`; three extended `manifest.json` files; three KQ-029 source records in `design/kidquest/source-metadata.json`. Every pixel anchor is `(256,464)` and every source-slot decode comparison is exact.
- **Validation/gallery evidence:** `docs/evidence/kq-029/QA_REPORT.md`; `design/kidquest/gallery/kq029.html`; four inspected captures in `design/kidquest/gallery/screenshots/`. `scripts/validate_kidquest_assets.py --profile buildings` and unchanged `--profile golden` both pass; final suite 1,021 passed, 3 skipped.
- **Rejected upstream items:** None rejected during extraction. Kampung garden/park post overhang, bridge rail-post height, and market canopy/footing overhang are retained and documented; Kingdom finials/flat bridge and City pipe-like rails/compressed stall details also remain upstream review notes.
- **Commit/artifact revision:** No commit created, per assignment. Determinism check passed byte-for-byte with `webp_lossless_exact_method_6`.
- **Follow-ups:** Lead/product owner reviews the captures and QA report; human Indonesian cultural review remains pending. KQ-029 cannot become `DONE` before KQ-006, KQ-025, and KQ-026–KQ-028 are `DONE`.

