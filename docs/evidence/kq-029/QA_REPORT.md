# KQ-029 building extraction QA report

Date: 2026-11-22  
Owner: `codex-core`  
Status: `IN_REVIEW` — lead review passed for the three source maps; product-owner art and human cultural review remain pending.

## Inputs and extraction decision

All sources passed `scripts/validate_building_sprite_map.py` before extraction. No source-map pixel was repaired, redrawn, translated, rescaled, or otherwise changed in KQ-029.

| Theme | Source map | SHA-256 | Provenance |
|---|---|---|---|
| Kampung Ceria | `design/kidquest/sprite-maps/perkampungan/buildings_v1.png` | `a09ff1abe2be78af3f909944c0bc25fb2638c059a2f2b792d01bf008a0927632` | `design/kidquest/sprite-maps/perkampungan/PROVENANCE.md` |
| Kerajaan Ceria | `design/kidquest/sprite-maps/kingdom/buildings_v1.png` | `c34df76c8438370f0bab768d840ef785b127e06443ef5b47cd4307f954f2ea75` | `design/kidquest/sprite-maps/kingdom/PROVENANCE.md` |
| Kota Ceria | `design/kidquest/sprite-maps/city/buildings_v1.png` | `0338271f7583c4fccc4c8dee4b063c199062fbed38595a5e92a80e94c6982534` | `design/kidquest/sprite-maps/city/PROVENANCE.md` |

The deterministic encoder profile is libwebp `cwebp -lossless -exact -m 6 -metadata none`. Each fixed source rectangle is cropped directly by `cwebp`; `dwebp` then decodes the result and the extractor compares every RGBA byte to the source slot.

| Theme | Sprites | Building bytes | Largest sprite | Max per-channel difference | Alpha equality |
|---|---:|---:|---|---:|---|
| Kampung Ceria | 6 | 578,814 | `park--base`, 125,348 bytes | 0 | exact |
| Kerajaan Ceria | 6 | 484,650 | `bakery--base`, 100,538 bytes | 0 | exact |
| Kota Ceria | 6 | 686,358 | `garden--base`, 158,690 bytes | 0 | exact |

Every individual sprite is below the 180 KB building target. The `buildings` validator also reports the critical golden assets plus starter house at 166.8 KB (Kampung), 170.7 KB (Kingdom), and 203.6 KB (City), each below 650 KB. Each six-building set is below the 2.5 MB complete-pack budget.

## Automated contract and manifest evidence

- Exactly 18 WebPs exist: six logical IDs × three themes, all 512 × 512.
- The slot-to-logical-ID sequence is identical: `starter_house`, `garden`, `bakery`, `park`, `bridge`, `market_stall`.
- Every manifest records pixel anchor `(256, 464)`, fixed slot and footprint rectangles, pixel-space entrances, `buildings.json` collision reference, catalog shadow bounds, source map/SHA/provenance, and the existing Indonesian theme label.
- Top-level footprint, cell-space anchor, entrances, and collision fields remain compatible with `buildings.json`; pixel-space extraction geometry is additive under `extraction`.
- `scripts/validate_kidquest_assets.py --profile buildings` checks completeness, filenames, dimensions, alpha, checksum, byte budget, source record, source-map checksum, slot mapping, anchor, entrances, footprint, collision/shadow metadata, labels, and cross-theme geometry parity.
- Negative tests prove rejection of a missing, mis-sized, misnamed, and anchor-drifted building sprite.
- `content/kidquest/themes.json` already contained all six building asset IDs in every theme, so the API `assets` maps need no catalog-value change.

## Required cross-theme checks

| Logical ID | Result | Evidence |
|---|---|---|
| `starter_house` | **PASS** | All themes use the identical 2×2 footprint, south entrance `(256,464)`, collision cells, shadow bounds, and safe-home/non-productive composition. The cross-theme capture shows a clear home silhouette in all three variants; the state matrix deliberately shows no productive badge. |
| `garden` | **PASS** | Identical 2×2 geometry and south entrance across themes. Planting groups remain countable in the native and state captures. The separate productive badge occupies the upper-right transparent region and does not obscure the planting groups. |
| `bakery` | **PASS** | Identical 2×2 geometry and road-facing south entrance across themes. Bread/oven cues remain readable. Selection, valid/invalid, dimmed, and productive overlays remain separate and readable. |
| `park` | **PASS** | Identical 2×2 geometry and south entrance across themes. Benches/paths/fountain or tree arrangements provide pattern cues without relying on color alone. No productive badge is applied. |
| `bridge` | **PASS** | Identical 1×2 north–south footprint, collision reference, shadow bounds, draw layer, and endpoints `(256,208)` / `(256,464)`. Both ends are visibly open. Water remains a terrain/mask concern and is not baked into any bridge sprite. |
| `market_stall` | **PASS** | Identical 1×1 geometry and south entrance across themes. Displayed item groups remain readable. The separate upper-right productive badge does not obscure the displays. |

The prohibited cues from KQ-026–KQ-028 remain absent in the reviewed extracts: no baked labels, prices, currency, advertising, payout/status badge, grid, water, or background.

## Gallery evidence and visual inspection

Gallery: `design/kidquest/gallery/kq029.html`  
Capture command: `node design/kidquest/gallery/capture-kq029.mjs`

| Capture | Inspection result |
|---|---|
| `gallery/screenshots/1280-kq029-cross-theme.png` | PASS — all 18 sprites load; footprint, anchor, and entrance overlays align; true scale differences are visible. |
| `gallery/screenshots/1280-kq029-states.png` | PASS — normal, selected, placement-valid, placement-invalid, locked/dimmed, and productive treatments are readable; the productive badge is a DOM overlay. |
| `gallery/screenshots/360-kq029-cross-theme.png` | PASS — single-column responsive layout, labels and geometry overlays remain legible, no horizontal overflow. |
| `gallery/screenshots/360-kq029-states.png` | PASS — two-column state layout remains readable, no broken images, overflow, or JavaScript errors. |

Capture diagnostics: `broken=[]`, `overflow=false`, `jsErrors=[]`.

## Known weaknesses retained from upstream maps

These are review notes, not extraction defects. They were not repaired here.

- Kampung garden and park bamboo posts/foliage extend roughly 30 px beyond the nominal footprint sides; their walkable soil/earth remains centered.
- Kampung bridge rail-post tops extend roughly 10 px above the preferred 1×2 overhang profile while staying within safe padding.
- Kampung market canopy and two footings overhang the 1×1 collision footprint; the stall remains visibly smaller than every 2×2 building.
- Kingdom gold finials should receive final product-owner review so they cannot be mistaken for coin cues; its bridge reads as a flat stone causeway rather than a pronounced arch.
- City bridge rail cylinders can read slightly like pipes; city market produce details compress at the smallest display size.
- Human Indonesian cultural review is still pending for all themes, especially the generic Kampung timber/bamboo/clay language.

## Determinism and verification

`PYTHONPATH=. .venv/bin/python design/kidquest/tools/extract_building_sprites.py --check` regenerates sprites, manifests, source records, and gallery data in temporary storage. It passed with byte-identical output for all tracked artifacts.

The final task handoff records the full-suite and focused-test counts. The initial full-suite run produced 1,013 passed, 3 skipped, and one browser setup error because the sandbox denied a localhost bind; this was an environment permission failure, not a test assertion failure.
