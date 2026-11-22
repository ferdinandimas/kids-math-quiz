#!/usr/bin/env python3
"""Render KQ-006 proofs, geometry templates, the graybox building study and the gallery data.

Usage (repository root, venv with requirements-assets.txt; run generate_golden_assets.py first):
    python design/kidquest/tools/render_proofs.py

Reads the EXPORTED runtime WebP files through their manifests (so the proofs show exactly what the
app would load) and writes only under design/kidquest/:
    proofs/        38/48/64 px proof sheets, 3x3 road scenes, island scenes, theme-switch matrix
    templates/     geometry templates (cell, quest board, 2x2/1x2/1x1 buildings) + geometry.json
    templates/graybox-buildings/   NON-PRODUCTION graybox building study
    gallery/gallery-data.js        data for the development gallery
Proofs are drawn at 1 device pixel per CSS pixel (the worst case for a 38 px cell).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import generate_golden_assets as gen  # noqa: E402
import kq_art as art  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

REPO = gen.REPO
DESIGN = REPO / "design" / "kidquest"
PROOFS = DESIGN / "proofs"
TEMPLATES = DESIGN / "templates"
GRAYBOX = TEMPLATES / "graybox-buildings"
GALLERY = DESIGN / "gallery"
PANEL = (15, 23, 48, 255)       # app --panel #0f1730
CARD = (36, 58, 113, 255)       # app card #243a71
TEXT = (233, 240, 255, 255)     # app --text
MUTED = (180, 194, 223, 255)    # app help text
GOLD = (255, 189, 22, 255)
PINK = (255, 137, 174, 255)
SIZES = (38, 48, 64)
SIDE_NAMES = {"N": "N", "E": "E", "S": "S", "W": "W"}


def font(size: int):
    return ImageFont.load_default(size=size)


def load_theme(theme: str) -> dict[str, Image.Image]:
    manifest = json.loads((REPO / "static/images/kidquest/themes" / theme / "manifest.json").read_text())
    return {a["asset_id"]: Image.open(REPO / a["runtime_path"]).convert("RGBA") for a in manifest["assets"]}


def scale(img: Image.Image, factor: float) -> Image.Image:
    return img.resize((max(1, round(img.width * factor)), max(1, round(img.height * factor))), Image.Resampling.LANCZOS)


def sides(mask: int) -> str:
    return "+".join(s for s in art.SIDES if mask & art.BITS[s]) or "none"


# --------------------------------------------------------------------------- graybox building study

GRAYBOX_SPECS = {
    # name: footprint (w, h), overhang top (cells), entrances, logical example
    "2x2": {"footprint": (2, 2), "overhang_top": 1.0, "entrances": ["S"], "example": "starter_house, garden, bakery, park"},
    "1x2": {"footprint": (1, 2), "overhang_top": 0.25, "entrances": ["N", "S"], "example": "bridge"},
    "1x1": {"footprint": (1, 1), "overhang_top": 0.75, "entrances": ["S"], "example": "market_stall"},
}
G_PLATE, G_LINE, G_WALL, G_SIDE, G_ROOF, G_ROOF_HI, G_DOOR, G_WIN = (
    "#d5d9dd", "#7c848c", "#aab0b6", "#8f969d", "#6f767e", "#868d95", "#3d434a", "#c6cbd0")


def graybox(name: str) -> Image.Image:
    spec = GRAYBOX_SPECS[name]
    fw, fh = spec["footprint"]
    top = round(spec["overhang_top"] * 128)
    w, h = fw * 128, fh * 128 + top
    pen = art.Pen((w, h))
    ink = art.rgba("#30363c")
    if name == "1x2":       # bridge deck: walking surface matches the road band (x 34..93)
        y0, y1 = top + 6, h - 6
        pen.rect((22, y0, 106, y1), art.rgba(G_SIDE), ink, 2.5, 6)
        pen.rect((34, y0, 94, y1), art.rgba(G_WALL), ink, 2)
        for y in range(y0 + 12, y1 - 4, 14):
            pen.line([(36, y), (92, y)], art.rgba(G_LINE), 1.5)
        for x in (24, 98):
            pen.rect((x, y0 - 18, x + 6, y1 - 6), art.rgba(G_ROOF), ink, 2, 3)          # railings
    else:
        inset = 14
        base_y = h - 10                                  # contact line just above the south edge
        wall_top = h - fh * 128 * 0.55
        pen.rect((inset, wall_top, w - inset, base_y), art.rgba(G_WALL), ink, 3, 4)
        pen.rect((w - inset - 18, wall_top + 6, w - inset, base_y), art.rgba(G_SIDE))
        roof_top = max(6, round(top * 0.35))                 # the roof uses the approved top overhang
        pen.poly([(inset - 8, wall_top + 4), (w / 2, roof_top), (w - inset + 8, wall_top + 4)], art.rgba(G_ROOF), ink, 3)
        pen.poly([(inset - 2, wall_top), (w / 2, roof_top + 8), (w / 2, wall_top)], art.rgba(G_ROOF_HI))
        dw = 22 if fw == 1 else 30
        pen.rect((w / 2 - dw / 2, base_y - dw * 1.5, w / 2 + dw / 2, base_y), art.rgba(G_DOOR), ink, 2, 4)
        if fw == 2:
            for x in (inset + 22, w - inset - 62):
                pen.rect((x, wall_top + 24, x + 40, wall_top + 58), art.rgba(G_WIN), ink, 2, 3)
    return pen.done((w, h))


def graybox_study(name: str, img: Image.Image) -> Image.Image:
    """Annotated study at 2x: footprint, overhang, anchor, entrances, 38 px preview."""
    spec = GRAYBOX_SPECS[name]
    fw, fh = spec["footprint"]
    k = 2
    pad = 90
    W, H = max(img.width * k + pad * 2 + 120, 980), img.height * k + pad * 2
    sheet = Image.new("RGBA", (W, H), PANEL)
    d = ImageDraw.Draw(sheet)
    ox, oy = pad, pad
    top = img.height - fh * 128
    ground = load_theme("perkampungan")["ground_buildable--base"]
    for cy in range(fh):
        for cx in range(fw):
            sheet.paste(scale(ground, k), (ox + cx * 128 * k, oy + (top + cy * 128) * k))
    d.rectangle([ox, oy, ox + img.width * k - 1, oy + top * k - 1], outline=MUTED, width=1)
    for y in range(oy, oy + top * k, 12):
        d.line([(ox, y), (ox + 10, y)], fill=MUTED)
    sheet.alpha_composite(scale(img, k), (ox, oy))
    for cx in range(fw + 1):
        x = ox + cx * 128 * k
        d.line([(x, oy + top * k), (x, oy + img.height * k)], fill=(127, 208, 255, 255), width=2)
    for cy in range(fh + 1):
        y = oy + (top + cy * 128) * k
        d.line([(ox, y), (ox + fw * 128 * k, y)], fill=(127, 208, 255, 255), width=2)
    ax, ay = ox + fw * 64 * k, oy + img.height * k
    d.line([(ax - 16, ay), (ax + 16, ay)], fill=PINK, width=3)
    d.line([(ax, ay - 16), (ax, ay + 16)], fill=PINK, width=3)
    for side in spec["entrances"]:
        y = oy + top * k if side == "N" else ay
        dy = -1 if side == "N" else 1
        d.polygon([(ax - 12, y + dy * 6), (ax + 12, y + dy * 6), (ax, y + dy * 24)], fill=(159, 245, 200, 255))
    f = font(16)
    d.text((16, 14), f"GRAYBOX {name} - NON-PRODUCTION (KQ-006 geometry study)", font=font(18), fill=GOLD)
    d.text((16, 40), f"footprint {fw}x{fh} cells | canvas {img.width}x{img.height} px @2x | overhang top {spec['overhang_top']} | "
                     f"anchor ({fw / 2:g}, {fh}) | entrances {'+'.join(spec['entrances'])}", font=f, fill=TEXT)
    d.text((16, 62), f"used by: {spec['example']} (production art: KQ-025..KQ-029)", font=f, fill=MUTED)
    d.text((ox + 4, oy + 4), "overhang", font=font(14), fill=MUTED)
    d.text((ax + 18, ay - 22), "anchor", font=font(14), fill=PINK)
    px = ox + img.width * k + 30
    d.text((px, oy), "38 px", font=f, fill=MUTED)
    small = Image.new("RGBA", (fw * 38, round(img.height * 38 / 128)), (0, 0, 0, 0))
    for cy in range(fh):
        for cx in range(fw):
            small.paste(scale(ground, 38 / 128), (cx * 38, round(top * 38 / 128) + cy * 38))
    small.alpha_composite(scale(img, 38 / 128))
    sheet.alpha_composite(small, (px, oy + 24))
    return sheet


# --------------------------------------------------------------------------- scenes

def compose(tiles: dict[str, Image.Image], width: int, height: int, water: set, roads: set, objects: list,
            top_margin: int = 1) -> Image.Image:
    """World scene at @2x. objects: (x, y, footprint_h, image, kind). Rows sorted by lowest footprint row."""
    C = 128
    canvas = Image.new("RGBA", (width * C, (height + top_margin) * C), PANEL)
    oy = top_margin * C
    for y in range(height):
        for x in range(width):
            if (x, y) in water:
                mask = 0
                for side, (dx, dy) in (("N", (0, -1)), ("E", (1, 0)), ("S", (0, 1)), ("W", (-1, 0))):
                    n = (x + dx, y + dy)
                    if 0 <= n[0] < width and 0 <= n[1] < height and n not in water:
                        mask |= art.BITS[side]
                canvas.paste(tiles[f"shore--mask_{mask:02d}"] if mask else tiles["water--base"], (x * C, oy + y * C))
            else:
                canvas.paste(tiles["ground_buildable--base"], (x * C, oy + y * C))
    for (x, y) in sorted(roads):
        mask = sum(art.BITS[s] for s, (dx, dy) in (("N", (0, -1)), ("E", (1, 0)), ("S", (0, 1)), ("W", (-1, 0))) if (x + dx, y + dy) in roads)
        canvas.alpha_composite(tiles[f"road_basic--mask_{mask:02d}"], (x * C, oy + y * C))
    for x, y, fh, img, _kind in sorted(objects, key=lambda o: (o[1] + o[2], o[0])):
        canvas.alpha_composite(img, (x * C, oy + (y + fh) * C - img.height))
    return canvas


def graybox_marker(kind: str) -> Image.Image:
    """Neutral stand-ins for tree/rock: not golden assets, clearly graybox."""
    pen = art.Pen((128, 192))
    ink = art.rgba("#30363c")
    if kind == "blocked_tree":
        pen.rect((56, 120, 72, 182), art.rgba(G_SIDE), ink, 2.5, 3)
        pen.ellipse((22, 40, 106, 140), art.rgba(G_WALL), ink, 3)
        pen.ellipse((36, 52, 70, 84), art.rgba(G_WIN))
    else:
        pen.ellipse((20, 120, 108, 184), art.rgba(G_WALL), ink, 3)
        pen.ellipse((34, 128, 66, 148), art.rgba(G_WIN))
    return pen.done((128, 192))


def island(tiles: dict[str, Image.Image], gray: dict[str, Image.Image]) -> tuple[Image.Image, dict]:
    layout = json.loads((REPO / "content/kidquest/layouts/pulau_tunas_v1.json").read_text())
    water = {(c["x"], c["y"]) for c in layout["water"]}
    roads = {(1, 3), (2, 3), (3, 3), (2, 4), (2, 5), (5, 3), (5, 6), (6, 6)}
    objects = []
    for obj in layout["fixed_objects"]:
        img = tiles["quest_board--base"] if obj["kind"] == "quest_board" else gray[obj["kind"]]
        objects.append((obj["x"], obj["y"], 1, img, obj["kind"]))
    objects.append((1, 1, 2, gray["2x2"], "graybox 2x2"))
    objects.append((5, 4, 2, gray["1x2"], "graybox 1x2 bridge"))
    meta = {"layout": layout["layout_id"], "roads": sorted(roads), "objects": [(o[0], o[1], o[4]) for o in objects]}
    return compose(tiles, layout["width"], layout["height"], water, roads, objects), meta


def label_sheet(img: Image.Image, title: str, subtitle: str = "") -> Image.Image:
    head = 64 if subtitle else 40
    sheet = Image.new("RGBA", (img.width + 32, img.height + head + 16), PANEL)
    d = ImageDraw.Draw(sheet)
    d.text((16, 12), title, font=font(18), fill=TEXT)
    if subtitle:
        d.text((16, 36), subtitle, font=font(14), fill=MUTED)
    sheet.alpha_composite(img, (16, head))
    return sheet


def roads_3x3(tiles: dict[str, Image.Image], cell: int) -> Image.Image:
    """16 scenes: the centre tile has mask m, each connected neighbour has the matching end cap."""
    C = 128
    gap = 24
    scene_px = 3 * cell
    out = Image.new("RGBA", (4 * scene_px + 5 * gap, 4 * (scene_px + 22) + 5 * gap), PANEL)
    d = ImageDraw.Draw(out)
    for m in range(16):
        roads = {(1, 1)}
        for side, (dx, dy) in (("N", (0, -1)), ("E", (1, 0)), ("S", (0, 1)), ("W", (-1, 0))):
            if m & art.BITS[side]:
                roads.add((1 + dx, 1 + dy))
        scene = compose(tiles, 3, 3, set(), roads, [], top_margin=0)
        scene = scale(scene, cell / C)
        col, row = m % 4, m // 4
        x, y = gap + col * (scene_px + gap), gap + row * (scene_px + 22 + gap)
        out.alpha_composite(scene, (x, y + 22))
        d.text((x, y + 2), f"mask {m:02d}  {sides(m)}", font=font(14), fill=TEXT)
    return out


def proof_sheet(theme: str, tiles: dict[str, Image.Image]) -> Image.Image:
    """Every golden asset at 38/48/64 px per cell (icon 24/32/48, thumbnail 64/96/128)."""
    ids = [a for _g, a in gen.golden_ids(*gen.load_content())]
    col_w, row_h = 3 * 64 + 4 * 10 + 70, 130
    cols = 5
    rows = (len(ids) + cols - 1) // cols
    out = Image.new("RGBA", (cols * col_w + 20, rows * row_h + 70), PANEL)
    d = ImageDraw.Draw(out)
    d.text((16, 12), f"{theme}: golden set at 38 / 48 / 64 px per cell (1x DPR, worst case)", font=font(18), fill=TEXT)
    d.text((16, 36), "Generated reference art - pending art review and cultural review. Not production-approved.", font=font(14), fill=PINK)
    ground = tiles["ground_buildable--base"]
    for i, asset_id in enumerate(ids):
        x0, y0 = 10 + (i % cols) * col_w, 64 + (i // cols) * row_h
        d.rounded_rectangle([x0, y0, x0 + col_w - 10, y0 + row_h - 8], radius=12, fill=CARD)
        d.text((x0 + 8, y0 + 6), asset_id, font=font(13), fill=TEXT)
        img = tiles[asset_id]
        if asset_id == "wood--icon":
            sizes = (24, 32, 48)
        elif asset_id == "theme_thumbnail--base":
            sizes = (48, 64, 80)
        else:
            sizes = SIZES
        x = x0 + 8
        for s in sizes:
            if asset_id.startswith(("road_basic", "quest_board")):
                cell_h = img.height * s // 128
                base = Image.new("RGBA", (s, cell_h), (0, 0, 0, 0))
                base.paste(scale(ground, s / 128), (0, cell_h - s))
                base.alpha_composite(scale(img, s / 128))
                shown = base
            elif asset_id in ("wood--icon", "theme_thumbnail--base"):
                shown = scale(img, s / img.width)
            else:
                shown = scale(img, s / 128)
            out.alpha_composite(shown, (x, y0 + row_h - 14 - shown.height))
            x += shown.width + 10
    return out


# --------------------------------------------------------------------------- templates

def cell_template() -> Image.Image:
    k = 4
    C = 128 * k
    pad = 70
    img = Image.new("RGBA", (C + pad * 2 + 260, C + pad * 2), PANEL)
    d = ImageDraw.Draw(img)
    ox, oy = pad, pad
    d.rectangle([ox, oy, ox + C - 1, oy + C - 1], fill=(230, 236, 222, 255), outline=TEXT, width=2)
    for i in range(0, 129, 16):
        d.line([(ox + i * k, oy), (ox + i * k, oy + C)], fill=(200, 208, 196, 255))
        d.line([(ox, oy + i * k), (ox + C, oy + i * k)], fill=(200, 208, 196, 255))
    a, b = (64 - art.ROAD_HALF - art.ROAD_BORDER) * k, (64 + art.ROAD_HALF + art.ROAD_BORDER) * k
    d.rectangle([ox + a, oy, ox + b - 1, oy + C - 1], outline=(196, 120, 60, 255), width=3)
    d.rectangle([ox, oy + a, ox + C - 1, oy + b - 1], outline=(196, 120, 60, 255), width=3)
    ia, ib = (64 - art.ROAD_HALF) * k, (64 + art.ROAD_HALF) * k
    d.rectangle([ox + ia, oy, ox + ib - 1, oy + C - 1], outline=(140, 80, 30, 255), width=1)
    for depth, col in ((art.SHORE_LAND, (60, 140, 70, 255)), (art.SHORE_BANK, (60, 110, 180, 255))):
        d.rectangle([ox + depth * k, oy + depth * k, ox + C - depth * k, oy + C - depth * k], outline=col, width=2)
    d.rectangle([ox + art.ROAD_HALF * 0, oy + C - 8 * k, ox + C, oy + C], outline=(170, 60, 60, 255), width=1)
    for (x, y) in ((64, 0), (128, 64), (64, 128), (0, 64)):
        d.ellipse([ox + x * k - 7, oy + y * k - 7, ox + x * k + 7, oy + y * k + 7], fill=PINK)
    f = font(15)
    tx = ox + C + 24
    lines = [
        ("Cell template 128 x 128 px @2x", TEXT),
        ("(64 CSS px max, 38 px min)", MUTED),
        ("origin = north-west corner", TEXT),
        ("pink dots = edge midpoints", PINK),
        (f"road band {64 - art.ROAD_HALF - art.ROAD_BORDER}..{64 + art.ROAD_HALF + art.ROAD_BORDER - 1}", (230, 160, 90, 255)),
        (f"  surface {art.ROAD_HALF * 2} px + border {art.ROAD_BORDER} px", MUTED),
        (f"open side: empty within {8} px", (230, 120, 120, 255)),
        (f"shore land strip {art.SHORE_LAND} px", (110, 200, 120, 255)),
        (f"shore bank to {art.SHORE_BANK} px + foam", (120, 170, 240, 255)),
        ("16 px guide grid", MUTED),
    ]
    for i, (text, col) in enumerate(lines):
        d.text((tx, oy + i * 28), text, font=f, fill=col)
    d.text((ox, 20), "KQ-006 geometry template (shared by all three themes)", font=font(18), fill=GOLD)
    return img


def board_template(tiles: dict[str, Image.Image]) -> Image.Image:
    k = 3
    w, h = 128 * k, 192 * k
    pad = 70
    img = Image.new("RGBA", (w + pad * 2 + 280, h + pad * 2), PANEL)
    d = ImageDraw.Draw(img)
    ox, oy = pad, pad
    img.paste(scale(tiles["ground_buildable--base"], k), (ox, oy + 64 * k))
    d.rectangle([ox, oy, ox + w - 1, oy + 64 * k - 1], outline=MUTED, width=1)
    ghost = scale(tiles["quest_board--base"], k)
    ghost.putalpha(ghost.getchannel("A").point(lambda a: a * 55 // 100))
    img.alpha_composite(ghost, (ox, oy))
    d.rectangle([ox, oy + 64 * k, ox + w - 1, oy + h - 1], outline=(127, 208, 255, 255), width=3)
    safe = 20 * k
    d.rectangle([ox + safe, oy + 64 * k + safe, ox + w - safe, oy + h - safe], outline=(159, 245, 200, 255), width=2)
    ax, ay = ox + w // 2, oy + h
    d.line([(ax - 18, ay), (ax + 18, ay)], fill=PINK, width=4)
    d.line([(ax, ay - 18), (ax, ay + 18)], fill=PINK, width=4)
    d.line([(ox, oy + 184 * k), (ox + w, oy + 184 * k)], fill=GOLD, width=1)
    tx = ox + w + 24
    for i, (text, col) in enumerate([
        ("quest_board--base: 1x1 fixed feature", TEXT), ("canvas 128 x 192 px @2x (64 x 96 CSS)", MUTED),
        ("overhang top 0.5 cell, left/right 0", MUTED), ("anchor (0.5, 1) = bottom-centre", PINK),
        ("blue = footprint / collision (1 cell)", (127, 208, 255, 255)), ("green = interaction-safe region", (159, 245, 200, 255)),
        ("gold = contact line y 184", GOLD), ("roads connect on N/E/S/W cell edges", MUTED),
        ("(domain: geometry.reachable_from_quest_board)", MUTED), ("ghost = perkampungan reference", MUTED)]):
        d.text((tx, oy + i * 28), text, font=font(15), fill=col)
    d.text((ox, 20), "KQ-006 quest board template", font=font(18), fill=GOLD)
    return img


# --------------------------------------------------------------------------- main

def main() -> int:
    for folder in (PROOFS, TEMPLATES, GRAYBOX, GALLERY):
        folder.mkdir(parents=True, exist_ok=True)
    themes_raw, roads_raw = gen.load_content()
    theme_ids = [t["id"] for t in themes_raw["themes"]]
    tiles = {t: load_theme(t) for t in theme_ids}

    gray = {name: graybox(name) for name in GRAYBOX_SPECS}
    gray["blocked_tree"] = graybox_marker("blocked_tree")
    gray["blocked_rock"] = graybox_marker("blocked_rock")
    for name in GRAYBOX_SPECS:
        gray[name].save(GRAYBOX / f"graybox_{name}--plain.png", optimize=True)
        graybox_study(name, gray[name]).save(GRAYBOX / f"graybox_{name}--study.png", optimize=True)

    cell_template().save(TEMPLATES / "cell-128-template.png", optimize=True)
    board_template(tiles[theme_ids[0]]).save(TEMPLATES / "quest-board-1x1-template.png", optimize=True)

    islands, drift = {}, {}
    for t in theme_ids:
        proof_sheet(t, tiles[t]).save(PROOFS / f"golden-{t}-38-48-64.png", optimize=True)
        for cell in (64, 38):
            label_sheet(roads_3x3(tiles[t], cell), f"{t}: all 16 road masks in 3x3 scenes at {cell} px per cell",
                        "Centre = mask; each connected neighbour = the matching end cap. Roads are theme-neutral logical state."
                        ).save(PROOFS / f"roads-3x3-{t}-{cell}.png", optimize=True)
        scene, meta = island(tiles[t], gray)
        sample_roads = {tuple(c) for c in meta["roads"]}
        islands[t] = scene
        for cell in (64, 38):
            label_sheet(scale(scene, cell / 128), f"{t}: pulau_tunas_v1 at {cell} px per cell",
                        "Golden terrain/shore/roads/quest board + GRAYBOX buildings, trees and rock (non-production)."
                        ).save(PROOFS / f"island-{t}-{cell}.png", optimize=True)
        board = tiles[t]["quest_board--base"]
        alpha = board.getchannel("A")
        bbox = alpha.point(lambda a: 255 if a >= 128 else 0).getbbox()
        drift[t] = {"quest_board_bbox": list(bbox)}

    # theme-switch matrix: the three islands side by side + per-layer drift check
    W = 64
    row = [scale(islands[t], W / 128) for t in theme_ids]
    gapx = 24
    matrix = Image.new("RGBA", (sum(r.width for r in row) + gapx * 4 + row[0].width, row[0].height + 110), PANEL)
    d = ImageDraw.Draw(matrix)
    d.text((16, 12), "Theme-switch matrix: same coordinates, three themes (64 px per cell)", font=font(18), fill=TEXT)
    road_layers = []
    x = gapx
    for t, r in zip(theme_ids, row):
        matrix.alpha_composite(r, (x, 70))
        d.text((x, 44), t, font=font(16), fill=MUTED)
        for gx in range(9):
            d.line([(x + gx * W, 70 + W), (x + gx * W, 70 + 9 * W)], fill=(255, 255, 255, 70))
            d.line([(x, 70 + W + gx * W), (x + 8 * W, 70 + W + gx * W)], fill=(255, 255, 255, 70))
        x += r.width + gapx
        road_only = Image.new("RGBA", (8 * 128, 8 * 128), (0, 0, 0, 0))
        for (rx, ry) in sample_roads:
            mask = sum(art.BITS[sd] for sd, (dx, dy) in (("N", (0, -1)), ("E", (1, 0)), ("S", (0, 1)), ("W", (-1, 0)))
                       if (rx + dx, ry + dy) in sample_roads)
            road_only.alpha_composite(tiles[t][f"road_basic--mask_{mask:02d}"], (rx * 128, ry * 128))
        road_layers.append(road_only)
    # drift panel: per-pixel difference of the road layer between themes (black = no drift)
    import numpy as np
    alphas = [np.asarray(scale(r, W / 128).getchannel("A")).astype(int) for r in road_layers]
    diff = np.zeros_like(alphas[0])
    for a in alphas[1:]:
        diff = np.maximum(diff, np.abs(a - alphas[0]))
    ghost = (alphas[0] > 127).astype(np.uint8) * 70
    red = np.clip(diff * 4, 0, 255).astype(np.uint8)
    panel = Image.fromarray(np.dstack([np.maximum(ghost, red), ghost, ghost, np.full_like(ghost, 255)]), "RGBA")
    matrix.alpha_composite(panel, (x, 70 + W))
    d.text((x, 44), f"road layer drift, grey = roads, red = differs (max {int(diff.max())}/255)", font=font(16), fill=GOLD if diff.max() == 0 else PINK)
    for t in theme_ids:
        drift[t]["road_layer_max_alpha_diff"] = int(diff.max())
    matrix.save(PROOFS / "theme-switch-matrix.png", optimize=True)

    geometry = {
        "cell_px_at_2x": 128, "css_px_per_cell": {"min": 38, "max": 64, "rule": "clamp(38px, 10vw, 64px)"},
        "css_cell_size_reading": "manifest css_cell_size = intended CSS px at the 64 px maximum cell = pixel_size / 2",
        "road": {"surface_half_width_px": art.ROAD_HALF, "border_px": art.ROAD_BORDER, "band_px": [64 - art.ROAD_HALF - art.ROAD_BORDER, 64 + art.ROAD_HALF + art.ROAD_BORDER - 1],
                 "inner_fillet_px": art.ROAD_FILLET, "open_edge_clear_px": 8, "bits": art.BITS},
        "shore": {"land_strip_px": art.SHORE_LAND, "bank_to_px": art.SHORE_BANK, "foam_px": art.SHORE_FOAM, "concave_fillet_px": art.SHORE_FILLET,
                  "mask_meaning": "water cell; bit set = land inside the map on that side (roads.shore_mask)"},
        "quest_board": {"canvas_px": list(art.QUEST_BOARD_SIZE), "footprint": [1, 1], "anchor": [0.5, 1], "overhang_top": 0.5, "contact_row_px": 184},
        "graybox_buildings_proposal_for_KQ025": {n: {"footprint": list(s["footprint"]), "overhang_top": s["overhang_top"],
                                                     "canvas_px": [s["footprint"][0] * 128, round((s["footprint"][1] + s["overhang_top"]) * 128)],
                                                     "anchor": [s["footprint"][0] / 2, s["footprint"][1]], "entrances": s["entrances"]}
                                                 for n, s in GRAYBOX_SPECS.items()},
        "lighting": "upper-left, one shared angle", "status": "KQ-006 proposal; KQ-025 freezes building geometry",
    }
    (TEMPLATES / "geometry.json").write_text(json.dumps(geometry, indent=2) + "\n")

    # gallery data
    sys.path.insert(0, str(REPO / "scripts"))
    import validate_kidquest_assets as validator
    report = validator.validate()
    manifests = {t: json.loads((REPO / "static/images/kidquest/themes" / t / "manifest.json").read_text()) for t in theme_ids}
    shared = json.loads((REPO / "static/images/kidquest/shared/manifest.json").read_text())
    groups = validator.group_of(themes_raw, roads_raw, json.loads((REPO / "content/kidquest/buildings.json").read_text()))
    golden = [a for _g, a in gen.golden_ids(themes_raw, roads_raw)]
    layout = json.loads((REPO / "content/kidquest/layouts/pulau_tunas_v1.json").read_text())
    data = {
        "themes": [{"id": t["id"], "name": t["name"], "labels": t["labels"]} for t in themes_raw["themes"]],
        "runtime_assets": themes_raw["runtime_assets"],
        "catalog": {t["id"]: [{"asset_id": a, "group": groups.get(a), "golden": a in golden} for a in t["assets"]] for t in themes_raw["themes"]},
        "manifests": manifests, "shared": shared, "geometry": geometry, "drift": drift,
        "layout": {"width": layout["width"], "height": layout["height"], "water": layout["water"], "fixed_objects": layout["fixed_objects"],
                   "zones": layout["zones"], "sample_roads": sorted(sample_roads)},
        "validator": {"ok": report.ok, "decoder": report.decoder, "problems": report.problems, "summary": report.summary},
    }
    (GALLERY / "gallery-data.js").write_text("// Generated by design/kidquest/tools/render_proofs.py - do not edit.\n"
                                            "window.KQ_GALLERY = " + json.dumps(data, indent=1) + ";\n")
    print(f"Proofs, templates, graybox study and gallery data written. Validator ok={report.ok}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
