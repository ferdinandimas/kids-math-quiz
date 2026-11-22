# KidQuest content

Versioned, logical source of truth for KidQuest. Themes, art, and UI must reconcile with these
files; they never redefine IDs, geometry, costs, or rules.

| File | Contents |
| --- | --- |
| `quests.json` | Q001–Q006 in teaching order. Only Q001 is `playable`; Q002–Q006 are `planned` (title, skills, building, prerequisite, required features). |
| `buildings.json` | The six core buildings: footprint, collision cells, entrances, anchor, cost, quest, zone, visual asset key. |
| `themes.json` | `perkampungan` (default), `kingdom`, `city`: names, Indonesian child-facing `labels` (PRD §10.1), PRD §11.7 `art_reference_names` for artists only (never shown to a child), the 56 logical asset IDs each theme must supply, and `runtime_assets`, the single rule that turns a theme and logical asset ID into a runtime path. |
| `roads.json` | `basic_road` and shore autotile masks 00–15 (N=1, E=2, S=4, W=8), 48-segment limit, road editing unlocked by Q003. |
| `assets.schema.json` | JSON Schema for one theme asset manifest entry (pipeline §14.3). |
| `building_sprite_map.v1.json` / `building_sprite_map.schema.json` | Frozen v1 geometry, slot order, alpha/edge rules, and checklist for the six-building theme sprite maps (KQ-025). |
| `layouts/pulau_tunas_v1.json` | The 8×8 starter map: water, fixed objects, and zones. |
| `ui_strings.json` | Child-facing copy of the KidQuest page (`GET /kidquest`, `static/js/kidquest.js`), grouped by screen, Indonesian. Validated with the rest: non-empty text, only known `{placeholders}`, no money (Rp/rupiah). Quest, hint, reward and placement-rule wording is not here; it comes from the API. |

## Coordinate convention

- A cell is `(x, y)`. `(0, 0)` is the **north-west** corner of the 8×8 grid.
- `x` grows **east** (0–7, left to right). `y` grows **south** (0–7, top to bottom).
- The position of a building, path, or zone rectangle is its **top-left (north-west) cell**. A
  footprint at `(x, y)` with size `width × height` covers `x … x+width−1` and `y … y+height−1`.
- A building's anchor is the bottom-centre of its footprint, in cell units from its top-left cell
  (a 2×2 building's anchor is `{x: 1, y: 2}`).
- An entrance is a footprint side (`N`, `E`, `S`, `W`). A road touches it when the road occupies
  one of the cells just outside that side; for a 2×2 building at `(x, y)` with a south entrance,
  those cells are `(x, y+2)` and `(x+1, y+2)`.
- Rotation is fixed at `0` in the MVP.

## `pulau_tunas_v1`

```text
      x→  0  1  2  3  4  5  6  7
  y↓ 0    T  .  .  .  .  .  .  T
     1    .  t  t  t  t  .  .  .
     2    .  t  t  t  t  .  .  .
     3    .  .  .  .  Q  .  .  .
     4    .  .  .  ~  ~  B  ~  ~
     5    .  .  .  ~  ~  B  ~  ~
     6    .  .  .  ~  e  e  e  e
     7    R  .  .  ~  e  e  e  T

  T tree   R rock   Q quest board   ~ water   B bridge_zone (water)
  t tutorial_zone   e expansion_zone   . open land
```

| Feature | Cells |
| --- | --- |
| Water (12 cells) | rows 4–5 for x 3–7, plus (3,6) and (3,7) |
| `blocked_tree` | (0,0), (7,0), (7,7) |
| `blocked_rock` | (0,7) |
| `quest_board` (1×1, fixed) | (4,3) |
| `tutorial_zone` | x 1–4, y 1–2 (`{x: 1, y: 1, width: 4, height: 2}`). Q001 house positions: (1,1), (2,1), (3,1) |
| `bridge_zone` | (5,4)–(5,5) (`{x: 5, y: 4, width: 1, height: 2}`), water, road ends at (5,3) and (5,6) |
| `expansion_zone` | x 4–7, y 6–7, reachable only across the bridge; opened by Q005 |

The validator proves that:

- every bridge cell is water with land at both ends and water beside it;
- the expansion zone is unreachable without the bridge and reachable with it;
- **for every tutorial position** of the house, the other five core buildings can still be placed
  (Q002–Q004 outside the locked expansion zone) with an entrance a road can connect to the quest
  board.

## Q001 reward visibility

The Q001 reward amount equals the answer (10 − 6 = 4). Before a correct answer, show
`reward_preview` ("Hadiah: kayu yang kurang + Cetak biru Rumah"), which never states the amount.
After a correct answer, use `reward` (4 wood and the `starter_house` blueprint) and
`reward_message`. The validator rejects any prompt, story, hint, or preview that contains the answer.

Child-facing copy is `pending_product_review` (see `quests.json`).

## Child-facing language and runtime asset paths

Every child-facing name (`themes[].name`, `themes[].labels`, quest titles and copy, building names) is
Indonesian (`child_facing_language: "id"`). The English names in PRD §11.7 survive only as
`art_reference_names`, which artists use as briefs; the API never sends them to a child. The validator
rejects a missing, empty, or unknown label or art reference.

`runtime_assets.path_template` plus `runtime_assets.directories` (one directory per asset group) give
the runtime path of any logical asset in any theme, for example
`/static/images/kidquest/themes/kingdom/buildings/starter_house--base@2x.webp` (pipeline §14.1–§14.2).
The API resolves assets with this rule only, so code never branches on a theme. The image files arrive
with KQ-006/KQ-029; until then the client uses the PRD §11.3 fallback order.

## Validating

```bash
PYTHONPATH=. python scripts/validate_kidquest_content.py
```

This checks logical content only (IDs, references, geometry, zones, masks, and theme parity on
logical asset IDs). It does not look for image files; that is the asset validator's job (KQ-006).
With `KIDQUEST_ENABLED=true`, the app runs the same validation at startup and refuses to start on
invalid content. When KidQuest is disabled, content is never loaded, so it cannot affect the
legacy quiz.
