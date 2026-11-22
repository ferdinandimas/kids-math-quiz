# Kota Ceria building sprite-map provenance

## Required fields

- **creator:** `codex-core`
- **model_or_tool:** OpenAI built-in `image_gen` tool
- **model_or_tool_version:** Not exposed by the built-in tool
- **generation_date:** 2026-11-22
- **prompt_revision:** `city-buildings-r1`
- **contract_id:** `building_sprite_map.v1`
- **source_graybox:** `design/kidquest/templates/building_sprite_map_graybox_v1.png`
- **seed_or_job_id:** No seed exposed; output job directory `01a20347-8623-7592-94e1-32900025c9fa`, artifact ID `exec-0a32acda-61d1-4ee2-b648-05eeff4f1853`
- **rights_or_license_status:** AI-generated project asset; ownership/license clearance remains subject to the repository owner's normal release review
- **human_cultural_review_status:** Pending; no cultural approval is claimed
- **art_review_status:** Self-reviewed by `codex-core`; pending independent lead/product-owner review
- **post_generation_edits:** Deterministic alpha cleanup, whole-slot translations, contract-safe clipping, opaque-alpha normalization, and sRGB re-encoding only; no art was redrawn, spliced, independently rescaled, or transplanted

## Input references

The final generation used five local inputs, the maximum accepted by the built-in tool:

1. `design/kidquest/templates/building_sprite_map_graybox_v1.png` — immutable geometry reference only; its guides were explicitly excluded from output.
2. `static/images/kidquest/themes/city/props/quest_board--base@2x.webp` — style, palette, outline, and awning reference.
3. `static/images/kidquest/themes/city/icons/theme_thumbnail--base@2x.webp` — assembled theme palette and lighting reference.
4. `static/images/kidquest/themes/city/roads/road_basic--mask_15@2x.webp` — pale running-bond paving and curb reference.
5. `static/images/kidquest/themes/city/terrain/shore--mask_05@2x.webp` — civic masonry, teal water, and light-value reference.

The prompt also encoded the colors and material direction from `design/kidquest/art-bibles/kota-ceria.md`, including the ground and water references omitted from the tool call because of the five-reference limit.

## Generation settings

- Built-in tool mode (not CLI/API fallback).
- `transparent_background: true`.
- Requested and received `1536 x 1024` RGBA PNG.
- Generated all six slots in one call as one complete map.
- No seed, quality control, or model identifier was exposed by the built-in tool.

## Final prompt (`city-buildings-r1`)

```text
Use case: stylized-concept
Asset type: production 2D building sprite map for the KidQuest children's world game
Primary request: Create one complete Kota Ceria / City building sprite map containing exactly six coordinated buildings. The result must be a single 1536 x 1024 pixel 8-bit RGBA PNG with a genuinely transparent background.

Input images:
- Image 1 is the immutable geometry-only graybox reference. Match its 3-by-2 slot layout, relative footprint scale, anchor locations, and safe padding, but DO NOT reproduce any gray shapes, colored diamonds, borders, grid lines, or guides.
- Images 2–5 are style-only references from the existing Kota Ceria theme. Match their flat polished 2D game illustration, rounded friendly forms, #20343E dark blue-gray outline feel, teal/coral/yellow/light-surface palette, pale civic masonry, restrained texture, and upper-left light. Do not copy their surrounding terrain or backgrounds into the sprite map.

OUTPUT AND LAYOUT:
- Exactly 1536 x 1024, transparent everywhere except the six building artworks.
- Six 512 x 512 slots, 3 columns by 2 rows, no gutters.
- Fixed order left-to-right, top-to-bottom:
  1 starter_house, 2 garden, 3 bakery,
  4 park, 5 bridge, 6 market_stall.
- Absolutely no labels, words, letters, numbers, logos, brand marks, currency, prices, badges, slot borders, grid, guides, or background.
- No visible art outside each slot's local safe bounds x=32..480 and y=32..480.
- Keep the same visual camera, outline weight, rendering finish, and upper-left key light for all six.

GEOMETRY:
- True world scale is 128 source pixels per logical cell.
- All slot-local footprint bottom-center anchors are exactly (256,464).
- Four 2x2 assets occupy ground footprint x=128..384, y=208..464: house, garden, bakery, park.
- Bridge is much narrower: 1x2, long north-south, ground footprint x=192..320, y=208..464, with both north and south short ends fully open.
- Market stall is visibly much smaller: 1x1, ground footprint x=192..320, y=336..464.
- Entrances are centered and unobstructed at the south anchor; bridge also open at north center.
- Viewer is south looking north and down, front/south faces parallel to canvas, vertical edges vertical, no perspective convergence.
- Allow decorative vertical mass above footprints while keeping true scale and safe bounds. Soft lower-right shadows may end no lower than local y=480.

THEME AND BUILDINGS:
Bright, clean, contemporary pedestrian civic town. Simple masonry, broad windows, awnings, planters, community greenery, accessible paving. Rounded forms and strong silhouettes readable by children aged 6–9 at tiny display size. Flat 2D game sprite illustration, not photorealistic, not isometric diamond projection, not 3D render.

1 starter_house — Colorful Townhouse: safe welcoming compact home, clear centered south door, broad windows, teal/coral/yellow accents, small planter; reads as a home and first achievement, never a shop or productive building.
2 garden — Community Garden: open accessible low boundary, clear south gate, several countable raised planting beds/crop groups, tidy greenery, no tools or shop cue.
3 bakery — City Bakery: compact civic bakery building with clear south door, friendly bread purpose communicated only through simple bread-loaf shapes visible in a broad window and a subtle safe chimney/oven cue; coral-and-white awning without text; no branding, price, open flame, machinery, or cash register.
4 park — City Park: open 2x2 community space with a simple geometric/pattern-friendly paved path, two benches, planters and one rounded shade tree arranged so the south entrance stays open; no kiosk, vendor, production, reward or payout cue.
5 bridge — Pedestrian City Bridge: narrow one-cell-wide, two-cell-long north-south bridge with pale masonry/paver deck, low safe teal rails along the long sides only, both short ends unobstructed, clearly pedestrian, no water baked in, no road vehicles or toll.
6 market_stall — City Kiosk: clearly smaller one-cell stall with teal frame and coral-and-white awning, open south side, exactly several countable produce/bread-like display items as plain colored shapes; no sign, text, advertising, money, price, register, payment terminal, transaction, person, or automatic-payment cue.

Color palette: primary teal #167A91, coral #E66A5A, accent yellow #F3C64E, clean light surfaces #F5FAFC, ink #20343E, greenery around #73B65C to #8BC96C, pale pavers #E6E1D6 and light gray curbs.
Materials/textures: clean painted masonry, pale running-bond pedestrian pavers, simple glass highlights, soft foliage, restrained detail.
Lighting/mood: optimistic daylight; one soft upper-left key; subtle consistent lower-right shadow.
Constraints: preserve exact layout and relative footprint scale; six complete coordinated assets generated together; true transparent background; crisp anti-aliased edges; alpha-zero pixels visually empty.
Avoid: cars, roads for cars, traffic lights, parking, pollution, construction hazards, people, national or religious symbols, luxury cues, weapons, unsafe heat, damaged structures, advertising, corporate colors, text of any kind, letters including an information "i", numbers, money, coins, banknotes, prices, ATMs, cash registers, payment terminals, trading action, gradients fading into a background, matte halos, graybox guides.
```

## Revision history

| Revision | Date | Artifact | Change and reason |
|---|---|---|---|
| Attempt 0 | 2026-11-22 | No artifact | The first built-in call named seven references and was rejected before generation because the tool accepts at most five paths. The prompt was unchanged; representative references were reduced to five. |
| Revision 1 | 2026-11-22 | `revisions/revision-01-generated.png` | Complete six-slot built-in generation. Visual content was strong and internally consistent, but validation found missing sRGB metadata, colored alpha-zero pixels, low-alpha atmospheric haze outside every safe area, and no fully opaque component. |
| Revision 2 (final candidate) | 2026-11-22 | `buildings_v1.png` | `postprocess_generated.py` removed source alpha below 16, promoted alpha 250–254 to 255, zeroed RGB wherever alpha became zero, translated each complete slot as one unit, clipped the remaining 404 pixels outside safe bounds, and re-encoded with sRGB intent 0. This was geometry/alpha normalization only; the generated artwork was not redrawn. |

Whole-slot translations in Revision 2, in frozen slot order:

| Building | Translation `(x, y)` source px | Reason |
|---|---:|---|
| `starter_house` | `(-30, -36)` | Center south door on the shared anchor and raise contact line into the safe region. |
| `garden` | `(0, -40)` | Raise the south gate/contact line to the shared anchor. |
| `bakery` | `(+32, -26)` | Center the door while retaining the complete chimney silhouette inside safe bounds. |
| `park` | `(-26, 0)` | Center the open south walkway on the shared anchor. |
| `bridge` | `(0, 0)` | Generated deck already aligned to both connection windows. |
| `market_stall` | `(+26, 0)` | Center the small kiosk and south opening without changing its 1x1 scale. |

## Validation and review

- Final SHA-256: `0338271f7583c4fccc4c8dee4b063c199062fbed38595a5e92a80e94c6982534`.
- Preserved generated revision SHA-256: `1f3ea5944ea1f2cd0b2eb8f5008f92e1b6df3d74a476a582adf66d40bb481c05`.
- Contract validator: **PASS** — `theme city: 1536 x 1024 RGBA/sRGB; six slots; padding, alpha, footprint, anchor, and entrances valid`.
- `make_review_captures.py` produced 28 PNGs in `review/`: the full sheet and every slot at native size and at 38, 48, and 64 px per world cell.
- All 28 captures were visually inspected by `codex-core` on 2026-11-22.

## Building review matrix

| Slot | Building | Required communication | Result at 38 / 48 / 64 px per cell | Prohibited-cue review | Known weakness |
|---:|---|---|---|---|---|
| 1 | `starter_house` | Safe home, south door, first achievement | **Pass / Pass / Pass** — townhouse silhouette, centered coral door, windows and planters remain clear. | No shopfront, income, supply, machinery, damage, text, or money cue. | Symmetrical townhouse is intentionally conventional; its small yellow doorknob is clearly contextualized as door hardware. |
| 2 | `garden` | Countable planting groups, accessible boundary, south entrance | **Pass / Pass / Pass** — four raised beds and distinct crop groups remain readable; gate is open and centered. | No sale, payout, text, hazardous tool, or dense-foliage cue. | The formal masonry boundary makes it read as a civic garden rather than a loose allotment, but accessibility and category remain clear. |
| 3 | `bakery` | Bread/oven purpose, south door, friendly preparation | **Pass / Pass / Pass** — loaf emblem and window loaves remain legible without words; teal door stays clear. | No brand, price, money, cash register, machinery, or open flame. | Chimney puff adds visual density and is the strongest production cue, though it remains soft, friendly, and non-hazardous. |
| 4 | `park` | Open pattern-friendly community space, south entrance | **Pass / Pass / Pass** — two benches, central tree, paved pattern, and wide open walkway remain distinct. | No vendor, supply, production, income, reward, or blocked-entrance cue. | Low masonry edges make it a formal pocket park/courtyard; the wide south opening prevents it from reading as closed. |
| 5 | `bridge` | Open north/south ends, 1x2 safe pedestrian crossing | **Pass / Pass / Pass** — long pale deck and low side rails remain clear; both short ends are unobstructed. | No toll, vehicle lane, money, damage, water, or blocked end. | Deliberately minimal without baked water; final world placement over the canal will strengthen the bridge reading. |
| 6 | `market_stall` | Countable display, small 1x1 scale, south opening | **Pass / Pass / Pass** — three display bins and produce groups remain distinguishable; kiosk is visibly smallest. | No text, advertising, price, currency, register, payment terminal, person, trading action, or gambling cue. | Individual items compress at 38 px, but the three-bin count and kiosk category remain readable. |

Independent art review, product-owner review, and human Indonesian cultural review remain pending.
