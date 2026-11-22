# KQ-006 geometry templates

Shared by all three themes (pipeline §11.1). Numbers live in [`geometry.json`](geometry.json); the
validator (`scripts/validate_kidquest_assets.py`) enforces them on the exported files.

| File | What it fixes |
|---|---|
| `cell-128-template.png` | 128 × 128 px @2x cell, NW origin, edge midpoints, road band 34–93 (48 px surface + 6 px border), 8 px open-edge clearance, shore land strip 18 px and bank 28 px, 16 px guide grid |
| `quest-board-1x1-template.png` | 128 × 192 px canvas, 1 × 1 footprint/collision, overhang top 0.5, anchor (0.5, 1), contact line y 184, interaction-safe region |
| `graybox-buildings/` | **NON-PRODUCTION** graybox building study: 2 × 2, 1 × 2 (bridge) and 1 × 1 footprints, bottom-centre anchors, entrances, proposed overhangs |
| `geometry.json` | machine-readable values above, plus the `css_cell_size` reading |

## Readings to confirm

- **@2x:** one cell is 128 × 128 px, i.e. 2 × the 64 CSS px maximum cell (PRD §11.4, pipeline §11.1).
  `css_cell_size` in a manifest is the intended CSS px size at that maximum, so `pixel_size = 2 × css_cell_size`
  (tile 64 × 64, quest board 64 × 96, wood icon 48 × 48, thumbnail 128 × 128).
- **Overhang:** the canvas is footprint + overhang (`width = (w + left + right) × 128`, `height = (h + top) × 128`).
- **Graybox overhangs** (2 × 2 top 1.0 → 256 × 384; 1 × 2 top 0.25 → 128 × 288; 1 × 1 top 0.75 → 128 × 224)
  are a **proposal** for KQ-025, which freezes building geometry. The bridge deck surface is exactly the road
  band (x 34–93), so the bridge's road anchors match the mask connections (pipeline §13).

Regenerate with `python design/kidquest/tools/render_proofs.py` (see `design/kidquest/README.md`).
