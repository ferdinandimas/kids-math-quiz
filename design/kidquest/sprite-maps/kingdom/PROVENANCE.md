# Kingdom building sprite-map provenance

## Artifact

- Output: `design/kidquest/sprite-maps/kingdom/buildings_v1.png`
- Contract: `building_sprite_map.v1`
- Contract source: `content/kidquest/building_sprite_map.v1.json`
- Generation date: 2026-11-22
- Creator/operator: `codex-core`
- Tool: OpenAI built-in `image_gen` image-generation/editing tool
- Model/version: not exposed by the built-in tool
- Background setting: transparent
- Generated canvas: 1536 × 1024; no crop, pad, stretch, or global resize
- Final SHA-256: `c34df76c8438370f0bab768d840ef785b127e06443ef5b47cd4307f954f2ea75`
- Rights/license status: generated specifically for this repository; no separate license grant was returned by the tool; product-owner acceptance remains pending
- Human cultural review: pending
- Independent art review: pending
- Self-review: passed at native size and 38/48/64 px per world cell, with weaknesses recorded below

## Reference images and roles

1. `design/kidquest/templates/building_sprite_map_graybox_v1.png` — immutable slot, footprint, scale, anchor, and connection geometry. Its visible guides were forbidden in production output.
2. `static/images/kidquest/themes/kingdom/props/quest_board--base@2x.webp` — primary palette, outline, material, shape, and lighting reference.
3. `static/images/kidquest/themes/kingdom/terrain/ground_buildable--base@2x.webp` — meadow palette and saturation reference only; terrain was excluded from the output.
4. `static/images/kidquest/themes/kingdom/roads/road_basic--mask_15@2x.webp` — rounded cobble material reference only; road tiles were excluded from the output.
5. `static/images/kidquest/themes/kingdom/terrain/shore--mask_15@2x.webp` — warm dressed-stone and calm-water palette reference only; shore/water tiles were excluded from the output.

## Base generation prompt (revision 1)

```text
Create one complete transparent KidQuest Kingdom building sprite map for children ages 6–9.

Use the graybox only as immutable geometry: preserve its exact 1536×1024 canvas, 3×2 array of
512×512 slots, true footprint scale, and bottom-center anchors, but remove every guide, rectangle,
marker, fill, grid line, and background. Use the Kingdom quest board, terrain, road, and shore only
as palette/material/outline references. Return one complete map, never six independent images.

Slot order is starter house, herb garden, bakery, park, bridge, market stall. Keep every visible
pixel inside slot-local x=32..480 and y=32..480. Use 128 source pixels per logical cell. The four
2×2 footprints are x=128..384,y=208..464; the 1×2 bridge is x=192..320,y=208..464; the 1×1 market
stall is x=192..320,y=336..464. Every south entrance reaches (256,464); the bridge also reaches
(256,208). Do not enlarge the bridge or stall.

Use polished 2D storybook game art matching the Kingdom references: rounded tactile forms, restrained
texture, crisp 5–7 px dark-indigo outlines, orthographic three-quarter front view from the south,
vertical edges vertical, no perspective convergence, and one soft upper-left light. Use warm rounded
stone, timber, royal blue, berry, gold, parchment cream, and no detached cast-ground shadows.

Keeper's Cottage: safe home, centered south door, no shop/income cue. Royal Herb Garden: exactly four
countable beds, accessible low boundary, centered south gap, no tools/sale cue. Castle Bakehouse:
centered south door, safe oven/chimney, exactly three visible breads, no flame/price/brand/machinery.
Royal Garden: open symmetrical community garden, bench, small fountain/birdbath, centered south entry,
no vendor/production/payout cue. Stone Story Bridge: narrow north-south cobbled deck, low side rails,
two unobstructed ends, no water/toll/vehicle/gate/damage. Royal Bazaar Stall: smallest asset, compact
timber stall, blue/berry canopy and tiny bunting, exactly three display groups, no price/cash/payment.

No people, text, glyphs, logos, advertising, currency, coins, prices, registers, payment terminals,
reward/status badges, heraldry, crowns, shields, real flags, religious symbols, weapons, armour,
soldiers, battlements, portcullis, throne, dungeon, ruins, dragons, danger, dark moat, or dense foliage.
Use a genuinely transparent background, colorless alpha-zero pixels, and clean edges. Optimize all
silhouettes and entrances for 38, 48, and 64 px per world cell.
```

Built-in result/job path:
`01a20347-8623-7c93-bcd3-48aa4f9cbbb7/exec-46dffe71-80e0-4c59-a3c5-9d7d121f2063.png`.

## Revision history and prompts

| Revision | Stored artifact | Prompt/change | Reason and result |
|---|---|---|---|
| 1 | `revisions/buildings_v1_r1.png` | Base prompt above; generated the full six-slot map together. | Strong, coherent designs and recognition, but all silhouettes overfilled true scale; garden, park, bridge, and stall missed the south anchor; alpha-zero RGB retained a colored matte. |
| 2 | `revisions/buildings_v1_r2.png` | Precise-object edit of the complete map: preserve all designs and materials; shrink/reposition each coherent building to graybox scale; align 2×2, 1×2, and 1×1 footprints; extend entrance surfaces to exact anchors; keep generous transparent margins. | True relative scale and spacing improved substantially. All buildings then fit inside safe bounds after translation, but the bridge deck remained too short to touch both connections and the stall center still ended above its anchor. Job `exec-f5a158af-dc05-4adc-b87e-ca1fd18f3ff2.png`. |
| 3 | `revisions/buildings_v1_r3.png` | Complete-map edit changing only slot 5: retain the same stone bridge, make the center deck span x=192..320,y=208..464 with open short ends and side rails only. | Kept visual quality but lengthened rails rather than the walkable center; south connection still could not be reached by translation without losing the north connection. Job `exec-396342f2-c66e-4081-87f1-0a27c5405a96.png`. |
| 4 | `revisions/buildings_v1_r4.png` | Complete-map edit changing only slot 5: add an approximately 52 px straight cobbled approach to the existing south end; keep north end fixed and open; preserve every other asset. | Bridge center became continuous through both connection positions and remained a narrow 1×2 pedestrian bridge. Job `exec-45f560c4-f8ca-4fe2-9992-a24163b3966e.png`. |
| 5 | `revisions/buildings_v1_r5.png` | Complete-map edit changing only slot 6: add one small plain centered timber threshold/step, connected between the two existing front supports and reaching their bottom level; preserve the compact stall and exactly three display groups. | Created legitimate centered ground contact for the 1×1 anchor without adding a commercial/payment cue. Job `exec-0dcd1f27-5a5c-46d9-9d1a-7a6fd1a750b5.png`. |
| Final | `buildings_v1.png` | Deterministic post-processing only: remove alpha ≤4 background residue; discard non-art partial-alpha components without an alpha ≥250 core; zero RGB for transparent pixels; promote alpha ≥250 cores to 255; encode with sRGB intent 0; translate each whole slot by y offsets `[22, 25, 20, 53, 1, 46]`. | No pixels were painted, spliced from other generations, independently rescaled, rotated, or stretched. The final map passes the contract validator. |

## Review captures

`review/` contains 28 PNGs: the complete map and all six cells at native size plus exact proofs at
38, 48, and 64 px per world cell. Full-map proof sizes are 456×304, 576×384, and 768×512. Per-cell
proof sizes are 152×152, 192×192, and 256×256.

## Self-review weaknesses

- The generated rendering is more polished and dimensional, with slightly heavier outlines, than the flatter KQ-006 quest-board reference; the palette, rounded material language, and light direction remain coherent.
- Gold spherical finials are plain architectural ornaments with no markings, amounts, stacking, or payout behavior, but the art lead should confirm they cannot be mistaken for coin cues at larger sizes.
- The bridge reads as a flat, safe stone causeway rather than a visibly arched bridge. Its narrow north–south pedestrian deck and two open connections remain clear at 38 px.
- Cultural review and independent art approval remain pending; this self-review does not claim either approval.
