---
id: KQ-006
title: Build asset system, graybox, and golden set
status: IN_REVIEW
owner: ui-ux-designer
depends_on: [KQ-004, KQ-005]
milestone: M3A
updated: 2026-11-22
---

# KQ-006 — Build asset system, graybox, and golden set

## Outcome

The team can create interchangeable Kingdom, City, and Perkampungan assets with validated geometry, naming, exports, and runtime manifests.

## Source references

- [Visual design and asset pipeline](../KidQuest_Visual_Design_Asset_Pipeline.md)
- [PRD — theme invariance and asset catalog](../KidQuest_Build_Your_World_PRD_v1.4.md)

## Scope

1. Implement the canonical asset naming, folder, metadata, pivot, footprint, scale, and export rules.
2. Build a manifest/schema validator and visual gallery harness.
3. Produce graybox assets for layout and collision testing.
4. Produce the golden-set reference assets in all three themes: representative terrain including every shore mask used by `pulau_tunas_v1`, quest board, all 16 road masks, `wood` icon, theme selector thumbnail, and shared overlays. Use a non-production graybox building study (128 px per cell, bottom-center anchor) only to prove the geometry that KQ-025 freezes; no production building is made here.
5. Run silhouette, readability, cultural, accessibility, and theme-switch alignment reviews.

## Deliverables

- Asset source/export structure and versioned manifests.
- Automated asset validator and gallery.
- Approved graybox and golden-set reference assets for three themes.
- Review evidence and correction log.

## Acceptance criteria

- [x] Every exported asset maps to one stable logical ID and theme variant. *(validator: path template, naming, catalog membership)*
- [x] All theme variants share footprint, anchor, and interaction geometry. *(validator: manifest parity + pixel anchor/contact checks; "approved" awaits lead review)*
- [x] All 16 road masks exist and connect without visible geometry breaks in each theme. *(validator: 384 edge pairs; 3×3 proofs)*
- [x] The gallery exposes missing assets, bounds, pivots, scale, and theme-switch drift.
- [ ] Golden reference assets pass the visual definition of done in the pipeline document. **Open:** automated geometry/budget parts pass; art review, cultural review and child comprehension have not happened (cannot be done honestly by this agent).
- [x] Building sprite-map production is delegated to KQ-025–KQ-029; this task does not claim any production building complete.

## Verification

- Run manifest/schema validation.
- Capture the required gallery and theme-switch comparison matrix and link it in the log.

## Out of scope

- Production building sprite maps (KQ-025–KQ-029), the complete remaining asset catalog, and gameplay implementation.

## Execution log

| Timestamp | Agent | Status | Evidence / notes |
|---|---|---|---|
| 2026-11-21 | planning | NOT_STARTED | Task packet created. |
| 2026-11-21 | lead | NOT_STARTED | **Approved dependency exception:** KQ-006 may start while KQ-005 is `IN_REVIEW`, because KQ-005's only open item is real household usability testing, which does not change asset geometry, naming, manifests or validation. KQ-004 is `DONE`. Condition: any household-test finding that changes geometry or component states must be reflected here before KQ-006 is marked `DONE`. |
| 2026-11-22 | ui-ux-designer | IN_PROGRESS | Claimed after lead approval of KQ-005 (lead review passed 216/216; KQ-005 stays IN_REVIEW for household testing). Scope per lead checklist: validator + one test file, golden non-building set ×3 themes (procedural Pillow, reproducible), shared SVG overlays, graybox building study outside `buildings/`, 3×3 road proofs, dev gallery, art bibles, budgets. `content/` stays read-only. |
| 2026-11-22 | ui-ux-designer | IN_REVIEW | Golden non-building set generated in all three themes (37 assets/theme: ground, water, 16 shore masks, 16 road masks, quest board, wood icon, thumbnail) + 6 shared SVG overlays + manifests + `design/kidquest/source-metadata.json`. `scripts/validate_kidquest_assets.py` OK (decoder dwebp): 384 road edge pairs, 48 shore tiles, quest-board anchor/drift across themes, budgets. Bytes: perkampungan 60,776 · kingdom 81,324 · city 60,264 (≤ 650 KB critical, largest tile 3.6 KB ≤ 32 KB). `tests/unit/kidquest/test_asset_validation.py`: 38 passed + 3 skipped (need Pillow) in `.venv`; 41 passed with Pillow; 31 passed + 10 skipped with no decoder. Coordinator decision applied: Pillow only in new `requirements-assets.txt` (pinned), never runtime; generator byte-reproducible in that venv (`--check`). Reading of @2x: 128 px per cell = 2 × 64 CSS px; `css_cell_size` = CSS px at 64 px cells. Evidence: `design/kidquest/proofs/`, `design/kidquest/gallery/screenshots/` (25 captures), `design/kidquest/templates/`. Art and cultural review **pending**; nothing is production-approved. Full suite: other lanes' in-flight work (Migration 9, `app/security`, KQ-010 browser test) currently fails 14–19 tests unrelated to KQ-006 files. |
| 2026-11-22 | lead | IN_REVIEW | **Lead review passed; stays `IN_REVIEW`.** Independently ran `validate_kidquest_assets.py` (OK, golden profile, dwebp decoder: 37 assets per theme, 384 road seams, 48 shore tiles, budgets far below limits) and its tests (38 passed, 3 skipped for missing Pillow); confirmed no `static/images/kidquest/themes/*/buildings`, `content/kidquest/` untouched by the designer, and viewed the 38/48/64 px golden proofs and island proofs (readable, themes share geometry, proofs labelled pending art/cultural review). `DONE` is blocked only by the open criterion: human art, cultural (Kampung) and child-comprehension review. **Lead exception:** KQ-025 (sprite-map contract, geometry only) may start while KQ-006 is `IN_REVIEW`, because the open item is a human art review that does not change footprint/anchor/scale geometry; KQ-025 must not be marked `DONE` before KQ-006 is. |

## Completion handoff

- **Summary:** Asset system and golden reference set for KQ-006. Procedurally generated (Pillow, deterministic) golden non-building art in Kampung, Kerajaan and Kota with identical logical geometry; per-theme runtime manifests that follow `assets.schema.json` and the `themes.json` path rule; shared SVG overlays; a stdlib-only validator with optional pixel decoding; a NON-PRODUCTION graybox building study; art bibles; geometry templates; 38/48/64 proofs, 3×3 road scenes, theme-switch matrix and a development gallery. Art review and cultural review are **pending**; every record says so.
- **Files changed/artifacts:**
  - `scripts/validate_kidquest_assets.py`; `tests/unit/kidquest/test_asset_validation.py`; `requirements-assets.txt` (design-time only, coordinator decision)
  - `static/images/kidquest/themes/{perkampungan,kingdom,city}/{terrain,roads,props,icons}/*.webp` + `manifest.json`; `static/images/kidquest/shared/overlays/*.svg` + `manifest.json` (no `buildings/` directory)
  - `design/kidquest/source-metadata.json`, `art-bibles/`, `templates/` (incl. `graybox-buildings/`, `geometry.json`), `proofs/`, `gallery/` (index, css, js, generated data, `capture-gallery.mjs`, `screenshots/`), `tools/` (`kq_art.py`, `generate_golden_assets.py`, `render_proofs.py`), `README.md`
- **Migrations/data impact:** None. `content/kidquest/` unchanged.
- **Verification performed:** `.venv/bin/python scripts/validate_kidquest_assets.py` → OK; `generate_golden_assets.py --check` (requirements-assets venv) → byte-identical; test file in `.venv`, Anaconda+Pillow and a decoder-less PATH; `capture-gallery.mjs` → 760 images, 0 missing, 0 JS errors, no 360 px overflow.
- **Commit/artifact revision:** Not committed (working tree, per protocol).
- **Follow-ups:**
  1. Art review and cultural review of the golden set and the three art bibles (humans; Kampung needs a cultural reviewer).
  2. Content/schema question: `review_status` enum has no `pending_art_review`/`pending_cultural_review`; manifests use `in_review` and the detail is in `source-metadata.json`. Schema has no UI layer for icons/thumbnails (they use `props`). `css_cell_size` meaning is undocumented (read as CSS px at 64 px cells). Lead/content owner to decide.
  3. A road cell next to the quest board or bridge draws an end cap, leaving grass between road and object, because `road_mask` only counts road neighbours (visible in the island proof). KQ-010/KQ-019 and the content owner should decide whether the board/bridge entrances count as visual connections.
  4. `blocked_tree`/`blocked_rock` are on `pulau_tunas_v1` but not in the golden set; KQ-010 needs graybox stand-ins until KQ-023 (proofs use neutral markers).
  5. 4-bit shore masks give square notches at convex land corners (e.g. near (3,5)/(4,6)); an 8-bit set would need a content change. Accepted for MVP unless art review objects.
  6. Graybox overhangs (2×2 top 1.0, 1×2 top 0.25, 1×1 top 0.75) are proposals for KQ-025 to freeze.
  7. CI needs `dwebp` (or Pillow) for pixel checks; otherwise run `--structural-only`.
