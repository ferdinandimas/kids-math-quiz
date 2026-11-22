# Graybox building study — NON-PRODUCTION

Neutral grey shapes that prove the footprint, bottom-centre anchor, entrance and overhang rules before
KQ-025 freezes the building sprite-map contract. **Not production art, never shipped, never placed
under `static/images/kidquest/themes/*/buildings/`** (KQ-029 owns those paths).

| File | Footprint | Canvas @2x | Anchor | Entrances | Stands in for |
|---|---|---|---|---|---|
| `graybox_2x2--plain.png` / `--study.png` | 2 × 2 | 256 × 384 (overhang top 1.0) | (1, 2) | S | starter_house, garden, bakery, park |
| `graybox_1x2--plain.png` / `--study.png` | 1 × 2 | 128 × 288 (overhang top 0.25) | (0.5, 2) | N + S | bridge (deck = road band x 34–93) |
| `graybox_1x1--plain.png` / `--study.png` | 1 × 1 | 128 × 224 (overhang top 0.75) | (0.5, 1) | S | market_stall |

`--plain` files are used in the island and theme-switch proofs; `--study` files are annotated
(footprint in blue, overhang zone, anchor cross in pink, entrance arrows in green, 38 px preview).
Anchors and entrances match `content/kidquest/buildings.json`. Source record: `design/kidquest/source-metadata.json` → `graybox`.
