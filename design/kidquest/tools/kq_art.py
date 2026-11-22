"""KidQuest KQ-006 procedural art library (golden non-building set).

Everything here is deterministic: every random choice comes from a seed derived from
``(theme_id, purpose)``, textures are periodic with the 128 px cell so neighbouring tiles join,
and no timestamps are written. Drawing happens at ``SS``x supersampling and is reduced with a
box filter for the alpha channel, so alpha edges that sit on the 128 px grid stay exact.

Geometry (shared by all three themes, see ``design/kidquest/templates/geometry.json``):

* Road surface half-width ``ROAD_HALF`` = 24 px, border ``ROAD_BORDER`` = 6 px, so a connected
  edge carries an opaque run of 60 px centred on the edge midpoint (x or y 34..93).
* Shore: land strip ``SHORE_LAND`` = 18 px from each land edge, then a bank to ``SHORE_BANK`` = 28 px,
  then a foam line on the water.

Requires requirements-assets.txt (Pillow 10.4.0 wheel with libwebp 1.4.0, numpy 1.26.4); that
environment produced the committed files byte for byte.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
from PIL import Image, ImageDraw

CELL = 128          # px per cell at @2x (64 CSS px at the maximum world size)
SS = 4              # supersampling factor
T = CELL * SS       # supersampled cell
THEMES = ("perkampungan", "kingdom", "city")
SIDES = ("N", "E", "S", "W")
BITS = {"N": 1, "E": 2, "S": 4, "W": 8}

ROAD_HALF = 24
ROAD_BORDER = 6
ROAD_FILLET = 14
SHORE_LAND = 18
SHORE_BANK = 28
SHORE_FOAM = 3
SHORE_FILLET = 10

QUEST_BOARD_SIZE = (128, 192)   # 1x1 footprint, 0.5 cell overhang on top, anchor bottom-centre
ICON_SIZE = (96, 96)            # 48 CSS px
THUMB_SIZE = (256, 256)         # 128 CSS px


def hexc(value: str) -> np.ndarray:
    value = value.lstrip("#")
    return np.array([int(value[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64)


def rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(v) for v in hexc(value))


def rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    return (*rgb(value), alpha)


# Palettes. World art is natural and light; the token colours come from the art bibles
# (pipeline section 10) and are used for accents, roofs, trims and ink outlines.
PALETTES = {
    "perkampungan": {
        "ground": ("#6c9b48", "#93bd60"), "ground_patch": "#b39360", "tuft": "#4a7a35", "tuft_light": "#bcd97f",
        "water": ("#3d8b88", "#66b4a8"), "ripple": "#e4f6ec", "foam": "#eef8ef",
        "bank": ("#c9a46c", "#dcbd86"), "bank_detail": "#a99f8c", "bank_wet": "#86683f",
        "road": ("#bf935d", "#d6b07a"), "road_detail": ("#aaa391", "#c9c2b0", "#8f8877"),
        "road_border": ("#4f8a3b", "#6aa24b"), "road_line": "#7a5a36", "road_edge": "#3c6a2c",
        "ink": "#26352b", "primary": "#367a4a", "secondary": "#c76d3a", "accent": "#f2c14e", "surface": "#fff4d8",
    },
    "kingdom": {
        "ground": ("#4c8a48", "#6caa58"), "ground_patch": None, "tuft": "#3d7339", "tuft_light": "#a9d48a",
        "water": ("#3d72b8", "#68a0dc"), "ripple": "#eaf2ff", "foam": "#f1f6ff",
        "bank": ("#c8bea9", "#d8cfbd"), "bank_detail": "#968b78", "bank_wet": "#5f5b56",
        "road": ("#857b6c", "#968c7c"), "road_detail": ("#c9bfae", "#bdb2a0", "#d6ccba"),
        "road_border": ("#4a7431", "#668f42"), "road_line": "#615849", "road_edge": "#30502a",
        "ink": "#252a45", "primary": "#3558a8", "secondary": "#8b4a83", "accent": "#e7b93f", "surface": "#fff2cf",
    },
    "city": {
        "ground": ("#73b65c", "#8bc96c"), "ground_patch": None, "tuft": "#5c9c48", "tuft_light": "#b9e39b",
        "water": ("#3aa3c6", "#6cc8e0"), "ripple": "#f5fafc", "foam": "#f7fcfe",
        "bank": ("#d3d8dc", "#e4e8eb"), "bank_detail": "#aeb6bd", "bank_wet": "#6f7a84",
        "road": ("#b0a89a", "#bab3a6"), "road_detail": ("#e6e1d6", "#dcd5c8", "#ece8df"),
        "road_border": ("#c7cdd3", "#dde2e6"), "road_line": "#959ea7", "road_edge": "#5f6a74",
        "ink": "#20343e", "primary": "#167a91", "secondary": "#e66a5a", "accent": "#f3c64e", "surface": "#f5fafc",
    },
}


def seed(theme: str, purpose: str) -> int:
    return int(hashlib.sha256(f"kq006:{theme}:{purpose}".encode()).hexdigest()[:12], 16)


# --------------------------------------------------------------------------- noise and masks

def pnoise(s: int, cells: int, size: int = T) -> np.ndarray:
    """Periodic value noise in [0, 1]; period == size, so tiles wrap seamlessly."""
    grid = np.random.default_rng(s).random((cells, cells))
    u = np.arange(size) * cells / size
    i0 = np.floor(u).astype(int)
    f = u - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % cells
    a, b = grid[np.ix_(i0, i0)], grid[np.ix_(i0, i1)]
    c, d = grid[np.ix_(i1, i0)], grid[np.ix_(i1, i1)]
    fx, fy = f[None, :], f[:, None]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(s: int, base: int = 4, octaves: int = 4, size: int = T) -> np.ndarray:
    total = np.zeros((size, size))
    amp, norm = 1.0, 0.0
    for octave in range(octaves):
        total += amp * pnoise(s + octave, base * 2 ** octave, size)
        norm += amp
        amp *= 0.5
    return total / norm


def lerp(c1: str, c2: str, t: np.ndarray) -> np.ndarray:
    a, b = hexc(c1), hexc(c2)
    return a + (b - a) * t[..., None]


def to_img(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(np.rint(arr), 0, 255).astype(np.uint8), "RGB")


def morph(mask: np.ndarray, k: int, grow: bool) -> np.ndarray:
    """Square dilation/erosion with edge replication (no artificial seam at the tile border)."""
    if k <= 0:
        return mask
    op = np.maximum if grow else np.minimum
    padded = np.pad(mask, k, mode="edge")
    h, w = mask.shape
    out = padded[:, k:k + w].copy()
    for dx in range(-k, k + 1):
        out = op(out, padded[:, k + dx:k + dx + w])
    res = out[k:k + h, :].copy()
    for dy in range(-k, k + 1):
        res = op(res, out[k + dy:k + dy + h, :])
    return res


def blend(base: np.ndarray, color, mask: np.ndarray, opacity: float = 1.0) -> np.ndarray:
    m = (mask.astype(np.float64) / 255.0 * opacity)[..., None]
    col = hexc(color) if isinstance(color, str) else color
    return base * (1 - m) + col * m


def wrapped(size: int, draw_fn) -> Image.Image:
    """Draw on a transparent RGBA layer, repeating each primitive across the wrap boundary."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for oy in (-size, 0, size):
        for ox in (-size, 0, size):
            draw_fn(d, ox, oy)
    return layer


def over(base_rgb: Image.Image, layer: Image.Image) -> Image.Image:
    return Image.alpha_composite(base_rgb.convert("RGBA"), layer).convert("RGB")


def reduce(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Downsample: Lanczos for colour, box for alpha (keeps grid-aligned alpha edges exact)."""
    if img.mode == "RGBA":
        r, g, b, a = img.split()
        colour = Image.merge("RGB", (r, g, b)).resize(size, Image.Resampling.LANCZOS)
        alpha = a.resize(size, Image.Resampling.BOX)
        out = colour.convert("RGBA")
        out.putalpha(alpha)
        return out
    return img.resize(size, Image.Resampling.LANCZOS)


# --------------------------------------------------------------------------- textures (SS scale)

def ground_texture(theme: str) -> Image.Image:
    p = PALETTES[theme]
    n = fbm(seed(theme, "ground"), 4, 4)
    arr = lerp(*p["ground"], n)
    if p["ground_patch"]:
        patch = np.clip((fbm(seed(theme, "ground-patch"), 2, 3) - 0.6) / 0.12, 0, 1)
        arr = arr * (1 - 0.45 * patch[..., None]) + hexc(p["ground_patch"]) * 0.45 * patch[..., None]
    if theme == "city":   # maintained civic lawn: soft mowing stripes, period of half a cell
        stripes = ((np.arange(T) // (T // 4)) % 2).astype(np.float64)
        arr = arr * (1 + 0.035 * (stripes[None, :, None] * 2 - 1))
    img = to_img(arr)
    rng = np.random.default_rng(seed(theme, "ground-deco"))
    tuft, light = rgba(p["tuft"], 200), rgba(p["tuft_light"], 190)
    count = {"perkampungan": 34, "kingdom": 26, "city": 14}[theme]
    pts = [(rng.random() * T, rng.random() * T, rng.random()) for _ in range(count)]
    flowers = [(rng.random() * T, rng.random() * T, int(rng.integers(0, 3))) for _ in range(9 if theme == "kingdom" else 0)]

    def deco(d, ox, oy):
        for x, y, r in pts:
            x, y = x + ox, y + oy
            h = (5 + 3 * r) * SS
            w = 2.2 * SS
            for dx in (-3.2 * SS, 0, 3.2 * SS):
                d.line([(x + dx * 0.4, y), (x + dx, y - h)], fill=tuft, width=int(w))
            d.line([(x - 1.2 * SS, y - h * 0.9), (x - 2 * SS, y - h)], fill=light, width=int(1.4 * SS))
        for x, y, k in flowers:
            x, y = x + ox, y + oy
            petal = (rgba("#fff2cf"), rgba("#e7b93f"), rgba("#d9a6cf"))[k]
            for ang in range(0, 360, 72):
                px = x + math.cos(math.radians(ang)) * 2.6 * SS
                py = y + math.sin(math.radians(ang)) * 2.6 * SS
                d.ellipse([px - 1.8 * SS, py - 1.8 * SS, px + 1.8 * SS, py + 1.8 * SS], fill=petal)
            d.ellipse([x - 1.3 * SS, y - 1.3 * SS, x + 1.3 * SS, y + 1.3 * SS], fill=rgba("#c98a2b"))

    return over(img, wrapped(T, deco))


def water_texture(theme: str) -> Image.Image:
    p = PALETTES[theme]
    n = fbm(seed(theme, "water"), 2, 3)
    img = to_img(lerp(*p["water"], n * 0.8 + 0.1))
    rng = np.random.default_rng(seed(theme, "ripples"))
    ripples = [(rng.random() * T, rng.random() * T, 7 + 6 * rng.random()) for _ in range(6)]
    col = rgba(p["ripple"], 120)

    def deco(d, ox, oy):
        for x, y, r in ripples:
            x, y, r = x + ox, y + oy, r * SS
            d.arc([x - r, y - r * 0.45, x + r, y + r * 0.45], 200, 340, fill=col, width=int(1.6 * SS))

    return over(img, wrapped(T, deco))


def bank_texture(theme: str) -> Image.Image:
    """Horizontal bank material; transposed for east/west banks."""
    p = PALETTES[theme]
    n = fbm(seed(theme, "bank"), 4, 3)
    img = to_img(lerp(*p["bank"], n))
    detail = rgba(p["bank_detail"], 230)
    rng = np.random.default_rng(seed(theme, "bank-deco"))
    if theme == "perkampungan":     # sandy earth with river pebbles
        pebbles = [(rng.random() * T, rng.random() * T, 2.2 + 1.8 * rng.random()) for _ in range(40)]

        def deco(d, ox, oy):
            for x, y, r in pebbles:
                x, y, r = x + ox, y + oy, r * SS
                d.ellipse([x - r, y - r * 0.75, x + r, y + r * 0.75], fill=detail)
                d.ellipse([x - r * 0.6, y - r * 0.6, x, y - r * 0.1], fill=rgba("#e9e1cf", 200))
    elif theme == "kingdom":        # dressed stone blocks, 16 x 10 px, staggered
        bw, bh = 16 * SS, 10 * SS

        def deco(d, ox, oy):
            for row in range(-1, T // bh + 2):
                off = (row % 2) * bw / 2
                for col in range(-1, T // bw + 2):
                    x0, y0 = col * bw + off + ox, row * bh + oy
                    d.rectangle([x0, y0, x0 + bw - 1, y0 + 1.2 * SS], fill=detail)
                    d.rectangle([x0, y0, x0 + 1.2 * SS, y0 + bh - 1], fill=detail)
                    d.line([(x0 + 2 * SS, y0 + 2.4 * SS), (x0 + bw * 0.6, y0 + 2.4 * SS)], fill=rgba("#efe8da", 170), width=SS)
    else:                           # concrete promenade with expansion joints every 32 px
        def deco(d, ox, oy):
            for k in range(0, T, 32 * SS):
                d.rectangle([k + ox, oy, k + ox + 1.2 * SS, T + oy], fill=detail)
                d.rectangle([ox, k + oy, T + ox, k + oy + 1.2 * SS], fill=detail)
    return over(img, wrapped(T, deco))


def road_textures(theme: str) -> tuple[Image.Image, Image.Image]:
    """(surface, border) textures, periodic with the cell."""
    p = PALETTES[theme]
    rng = np.random.default_rng(seed(theme, "road-deco"))
    surf = to_img(lerp(*p["road"], fbm(seed(theme, "road"), 4, 3)))
    det = p["road_detail"]
    if theme == "perkampungan":     # packed earth with embedded stones
        stones = [(rng.random() * T, rng.random() * T, 2.4 + 2.2 * rng.random(), det[int(rng.integers(0, 3))]) for _ in range(34)]
        grit = [(rng.random() * T, rng.random() * T) for _ in range(120)]

        def deco(d, ox, oy):
            for x, y in grit:
                d.point((x + ox, y + oy), fill=rgba("#8c6a43", 160))
                d.ellipse([x + ox - SS, y + oy - SS, x + ox + SS, y + oy + SS], fill=rgba("#a57f50", 120))
            for x, y, r, c in stones:
                x, y, r = x + ox, y + oy, r * SS
                d.ellipse([x - r + SS, y - r * 0.8 + SS, x + r + SS, y + r * 0.8 + SS], fill=rgba("#7f6143", 150))
                d.ellipse([x - r, y - r * 0.8, x + r, y + r * 0.8], fill=rgba(c))
                d.ellipse([x - r * 0.6, y - r * 0.6, x - r * 0.05, y - r * 0.15], fill=rgba("#f1ebdd", 170))
    elif theme == "kingdom":        # rounded cobblestones, 16 px, staggered rows
        cw = 16 * SS
        shades = [det[int(rng.integers(0, 3))] for _ in range((T // cw) ** 2)]

        def deco(d, ox, oy):
            n = T // cw
            for row in range(-1, n + 1):
                off = (row % 2) * cw / 2
                for col in range(-1, n + 1):
                    shade = shades[(row % n) * n + (col % n)]
                    x0, y0 = col * cw + off + ox + 1.5 * SS, row * cw + oy + 1.5 * SS
                    x1, y1 = x0 + cw - 3 * SS, y0 + cw - 3 * SS
                    d.rounded_rectangle([x0 + 0.8 * SS, y0 + 0.8 * SS, x1 + 0.8 * SS, y1 + 0.8 * SS], radius=5 * SS, fill=rgba("#5d5548", 200))
                    d.rounded_rectangle([x0, y0, x1, y1], radius=5 * SS, fill=rgba(shade))
                    d.arc([x0 + 2 * SS, y0 + 2 * SS, x1 - 2 * SS, y1 - 2 * SS], 190, 260, fill=rgba("#f3ede2", 200), width=int(1.4 * SS))
    else:                           # pedestrian pavers, running bond 16 x 8 px
        pw, ph = 16 * SS, 8 * SS
        shades = [det[int(rng.integers(0, 3))] for _ in range((T // pw) * (T // ph))]

        def deco(d, ox, oy):
            nx, ny = T // pw, T // ph
            for row in range(-1, ny + 1):
                off = (row % 2) * pw / 2
                for col in range(-1, nx + 1):
                    shade = shades[(row % ny) * nx + (col % nx)]
                    x0, y0 = col * pw + off + ox + 0.8 * SS, row * ph + oy + 0.8 * SS
                    d.rectangle([x0, y0, x0 + pw - 1.6 * SS, y0 + ph - 1.6 * SS], fill=rgba(shade))
                    d.line([(x0, y0), (x0 + pw - 2 * SS, y0)], fill=rgba("#f8f6f1", 170), width=SS)
    surf = over(surf, wrapped(T, deco))

    border = to_img(lerp(*p["road_border"], fbm(seed(theme, "road-border"), 8, 3)))
    if theme == "city":     # curb stones with joints every 16 px
        def bdeco(d, ox, oy):
            for k in range(0, T, 16 * SS):
                d.rectangle([k + ox, oy, k + ox + 0.8 * SS, T + oy], fill=rgba("#aab2b9", 200))
                d.rectangle([ox, k + oy, T + ox, k + oy + 0.8 * SS], fill=rgba("#aab2b9", 200))
    else:                   # grass / moss blades
        blades = [(rng.random() * T, rng.random() * T) for _ in range(160)]
        light = rgba(p["tuft_light"], 170)

        def bdeco(d, ox, oy):
            for x, y in blades:
                d.line([(x + ox, y + oy), (x + ox - SS, y + oy - 3 * SS)], fill=light, width=SS)
    border = over(border, wrapped(T, bdeco))
    return surf, border


# --------------------------------------------------------------------------- shapes

CORNERS = {("N", "E"): (1, -1), ("E", "S"): (1, 1), ("S", "W"): (-1, 1), ("W", "N"): (-1, -1)}


def _fillet(d: ImageDraw.ImageDraw, sx: int, sy: int, half: float, radius: float, centre_offset: float) -> None:
    """Concave fillet between two perpendicular arms; ``centre_offset`` is the inner fillet's h + R."""
    c = T / 2
    px, py = c + sx * half, c + sy * half
    cx, cy = c + sx * centre_offset, c + sy * centre_offset
    d.rectangle([min(px, cx), min(py, cy), max(px, cx) - 1, max(py, cy) - 1], fill=255)
    d.ellipse([cx - radius, cy - radius, cx + radius - 1, cy + radius - 1], fill=0)


def road_shape(mask: int, half_px: float, fillet_px: float, inner_half_px: float) -> np.ndarray:
    c, h = T / 2, half_px * SS
    shape = Image.new("L", (T, T), 0)
    d = ImageDraw.Draw(shape)
    d.ellipse([c - h, c - h, c + h - 1, c + h - 1], fill=255)
    if mask & 1:
        d.rectangle([c - h, 0, c + h - 1, c - 1], fill=255)
    if mask & 2:
        d.rectangle([c, c - h, T - 1, c + h - 1], fill=255)
    if mask & 4:
        d.rectangle([c - h, c, c + h - 1, T - 1], fill=255)
    if mask & 8:
        d.rectangle([0, c - h, c - 1, c + h - 1], fill=255)
    fil = Image.new("L", (T, T), 0)
    fd = ImageDraw.Draw(fil)
    centre = (inner_half_px + ROAD_FILLET) * SS
    for (a, b), (sx, sy) in CORNERS.items():
        if mask & BITS[a] and mask & BITS[b]:
            _fillet(fd, sx, sy, h, fillet_px * SS, centre)
    return np.maximum(np.asarray(shape), np.asarray(fil))


def road_tile(theme: str, mask: int, textures=None) -> Image.Image:
    p = PALETTES[theme]
    surf, border = textures or road_textures(theme)
    outer = road_shape(mask, ROAD_HALF + ROAD_BORDER, ROAD_FILLET - ROAD_BORDER, ROAD_HALF)
    inner = road_shape(mask, ROAD_HALF, ROAD_FILLET, ROAD_HALF)
    line = morph(inner, int(1.5 * SS), True)
    edge = outer - morph(outer, int(1.5 * SS), False)
    arr = np.asarray(border).astype(np.float64)
    arr = blend(arr, p["road_edge"], edge, 0.85)
    arr = blend(arr, p["road_line"], line)
    # soft upper-left light: the surface is a touch darker toward its lower-right border
    shade = morph(inner, 3 * SS, False)
    arr = blend(arr, np.asarray(surf).astype(np.float64), inner)
    arr = blend(arr, "#000000", (inner - shade) // 2, 0.12)
    img = to_img(arr).convert("RGBA")
    img.putalpha(Image.fromarray(outer))
    return reduce(img, (CELL, CELL))


def shore_tile(theme: str, mask: int, cache: dict | None = None) -> Image.Image:
    p = PALETTES[theme]
    cache = cache if cache is not None else {}
    water = cache.get("water") or water_texture(theme)
    ground = cache.get("ground") or ground_texture(theme)
    bank_h = cache.get("bank") or bank_texture(theme)
    bank_v = bank_h.transpose(Image.Transpose.TRANSPOSE)
    land_d, bank_d = SHORE_LAND * SS, SHORE_BANK * SS
    rects = {
        "N": lambda depth: (0, 0, T, depth), "S": lambda depth: (0, T - depth, T, T),
        "W": lambda depth: (0, 0, depth, T), "E": lambda depth: (T - depth, 0, T, T),
    }
    sides = [s for s in SIDES if mask & BITS[s]]

    def region(depth: int, which: list[str], fillet: float) -> np.ndarray:
        im = Image.new("L", (T, T), 0)
        d = ImageDraw.Draw(im)
        for s in which:
            x0, y0, x1, y1 = rects[s](depth)
            d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
        fil = Image.new("L", (T, T), 0)
        fd = ImageDraw.Draw(fil)
        r = fillet * SS
        for (a, b), (sx, sy) in CORNERS.items():
            if fillet and a in which and b in which:    # concave water corner: round it toward the centre
                c = T / 2
                px, py = c + sx * (c - depth), c + sy * (c - depth)
                cx, cy = px - sx * r, py - sy * r
                fd.rectangle([min(px, cx), min(py, cy), max(px, cx) - 1, max(py, cy) - 1], fill=255)
                fd.ellipse([cx - r, cy - r, cx + r - 1, cy + r - 1], fill=0)
        return np.maximum(np.asarray(im), np.asarray(fil)).astype(np.int32)

    bank_all = region(bank_d, sides, SHORE_FILLET)
    land_all = region(land_d, sides, SHORE_FILLET * 0.6)
    arr = np.asarray(water).astype(np.float64)
    foam = morph(bank_all, SHORE_FOAM * SS, True) - bank_all
    arr = blend(arr, p["foam"], foam, 0.55)
    for group, tex in ((["N", "S"], bank_h), (["W", "E"], bank_v)):
        part = region(bank_d, [s for s in sides if s in group], 0)
        arr = blend(arr, np.asarray(tex).astype(np.float64), part)
    # corners where two banks meet keep the fillet in the horizontal bank material
    corner_fill = np.clip(bank_all - region(bank_d, sides, 0), 0, 255)
    arr = blend(arr, np.asarray(bank_h).astype(np.float64), corner_fill)
    wet = bank_all - morph(bank_all, int(1.5 * SS), False)
    arr = blend(arr, p["bank_wet"], wet, 0.9)
    lip = morph(land_all, int(1.5 * SS), True) - land_all
    arr = blend(arr, "#000000", lip, 0.18)
    arr = blend(arr, np.asarray(ground).astype(np.float64), land_all)
    return reduce(to_img(arr), (CELL, CELL))


def ground_tile(theme: str) -> Image.Image:
    return reduce(ground_texture(theme), (CELL, CELL))


def water_tile(theme: str) -> Image.Image:
    return reduce(water_texture(theme), (CELL, CELL))


# --------------------------------------------------------------------------- props and icons

class Pen:
    """ImageDraw wrapper in base (@2x) pixel units, drawing at SS scale."""

    def __init__(self, size: tuple[int, int]):
        self.img = Image.new("RGBA", (size[0] * SS, size[1] * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    @staticmethod
    def _s(points):
        return [v * SS for v in points]

    def rect(self, box, fill, outline=None, width=0, radius=0):
        w = int(width * SS)
        if radius:
            self.d.rounded_rectangle(self._s(box), radius=radius * SS, fill=fill, outline=outline, width=w)
        else:
            self.d.rectangle(self._s(box), fill=fill, outline=outline, width=w)

    def poly(self, pts, fill, outline=None, width=0):
        flat = [v * SS for pt in pts for v in pt]
        self.d.polygon(flat, fill=fill, outline=outline, width=int(width * SS))

    def ellipse(self, box, fill, outline=None, width=0):
        self.d.ellipse(self._s(box), fill=fill, outline=outline, width=int(width * SS))

    def line(self, pts, fill, width=1):
        self.d.line([(x * SS, y * SS) for x, y in pts], fill=fill, width=max(1, int(width * SS)), joint="curve")

    def done(self, size):
        return reduce(self.img, size)


def quest_board(theme: str) -> Image.Image:
    """1x1 fixed feature on a 128x192 canvas. Contact line y=184, centred on x=64."""
    p = PALETTES[theme]
    ink = rgba(p["ink"])
    pen = Pen(QUEST_BOARD_SIZE)
    if theme == "perkampungan":     # Papan Pengumuman: timber, clay-tile roof, woven bamboo panel
        for x in (34, 84):
            pen.rect((x - 1, 170, x + 11, 184), rgba("#9c948a"), ink, 2, 2)          # stone footings
            pen.rect((x, 70, x + 10, 174), rgba("#8a5a35"), ink, 2.5)                  # timber posts
            pen.rect((x + 2, 74, x + 4, 170), rgba("#b07a4a"))
        pen.rect((18, 66, 110, 132), rgba("#d9b977"), ink, 3, 4)                       # woven panel
        for k in range(22, 108, 8):
            pen.line([(k, 69), (k + 6, 129)], rgba("#b8935a"), 1.2)
        pen.rect((26, 76, 60, 112), rgba(p["surface"]), ink, 1.5, 2)                   # notices (no text)
        pen.rect((66, 82, 100, 120), rgba(p["surface"]), ink, 1.5, 2)
        for x, y, c in ((43, 80, p["primary"]), (83, 86, p["secondary"])):
            pen.ellipse((x - 3, y - 3, x + 3, y + 3), rgba(c), ink, 1)
        for y in (90, 97, 104):
            pen.line([(31, y), (55, y)], rgba("#cbbf9f"), 2)
        pen.poly([(8, 66), (64, 22), (120, 66)], rgba(p["secondary"]), ink, 3)        # clay-tile roof
        for k in range(0, 5):
            y = 34 + k * 8
            half = (y - 22) * 56 / 44
            pen.line([(64 - half + 4, y), (64 + half - 4, y)], rgba("#9e4f27"), 1.6)
        pen.line([(60, 22), (68, 22)], ink, 3)
    elif theme == "kingdom":        # Papan Berita Kerajaan: stone pillars, timber board, arched crest
        for x in (30, 82):
            pen.rect((x, 76, x + 16, 184), rgba("#cfc5b3"), ink, 2.5, 3)
            for y in (96, 120, 144, 166):
                pen.line([(x + 2, y), (x + 14, y)], rgba("#9d927f"), 1.4)
            pen.rect((x - 2, 70, x + 18, 80), rgba("#d8cfbd"), ink, 2, 2)
        pen.rect((20, 74, 108, 134), rgba("#9a6a3e"), ink, 3, 6)
        pen.rect((28, 82, 62, 124), rgba(p["surface"]), ink, 1.5, 3)
        pen.rect((68, 86, 100, 120), rgba(p["surface"]), ink, 1.5, 3)
        for y in (94, 101, 108):
            pen.line([(33, y), (57, y)], rgba("#d8c79a"), 2)
        pen.ellipse((79, 92, 89, 102), rgba(p["accent"]), ink, 1.2)                     # gold seal (no emblem)
        pen.poly([(14, 74), (14, 54), (64, 26), (114, 54), (114, 74)], rgba(p["primary"]), ink, 3)
        pen.line([(18, 66), (64, 38), (110, 66)], rgba(p["accent"]), 3)
        for k, x in enumerate((26, 46, 82, 102)):                                       # bunting, not a flag
            pen.poly([(x - 6, 74), (x + 6, 74), (x, 86)], rgba(p["secondary"] if k % 2 == 0 else p["accent"]), ink, 1.2)
        pen.ellipse((58, 18, 70, 30), rgba(p["accent"]), ink, 2)
    else:                           # Kios Info Kota: teal kiosk, coral awning, planter base
        pen.rect((24, 162, 104, 184), rgba("#c9cfd4"), ink, 2.5, 5)                     # planter
        for x in (34, 52, 70, 88):
            pen.ellipse((x - 9, 150, x + 9, 168), rgba("#5fa34a"), ink, 1.5)
        pen.rect((54, 120, 74, 166), rgba("#5b6b75"), ink, 2.5, 4)                      # post
        pen.rect((16, 58, 112, 128), rgba(p["primary"]), ink, 3, 10)                    # kiosk frame
        pen.rect((24, 66, 104, 120), rgba(p["surface"]), ink, 1.5, 6)
        for box, c in (((30, 72, 58, 96), p["secondary"]), ((64, 72, 98, 90), p["accent"]), ((64, 96, 98, 114), "#9fd3e0"), ((30, 102, 58, 114), "#cfe8c4")):
            pen.rect(box, rgba(c), ink, 1.2, 3)
        stripes = [(18 + k * 12, 18 + (k + 1) * 12) for k in range(8)]
        for k, (x0, x1) in enumerate(stripes):                                          # striped awning
            pen.poly([(x0, 40), (x1, 40), (x1 + 1, 58), (x0 + 1, 58)], rgba(p["secondary"] if k % 2 == 0 else "#ffffff"))
        pen.rect((16, 30, 112, 42), rgba(p["secondary"]), ink, 2.5, 6)
        pen.line([(18, 58), (110, 58)], ink, 2.5)
    return pen.done(QUEST_BOARD_SIZE)


def wood_icon(theme: str) -> Image.Image:
    """Resource icon, 96x96, same three-log stack silhouette in each theme."""
    p = PALETTES[theme]
    ink = rgba(p["ink"])
    pen = Pen(ICON_SIZE)
    bark = {"perkampungan": "#8a5a35", "kingdom": "#7d4f33", "city": "#a0704a"}[theme]
    end = {"perkampungan": "#e2b97a", "kingdom": "#dcb07a", "city": "#ecc995"}[theme]
    ring = "#b98a52"
    band = {"perkampungan": p["accent"], "kingdom": p["primary"], "city": p["secondary"]}[theme]
    if theme == "city":     # sawn planks, stacked and strapped
        for k, y in enumerate((60, 40, 20)):
            x0 = 8 + (k % 2) * 6
            pen.rect((x0, y, x0 + 70, y + 18), rgba(bark), ink, 3, 3)
            pen.rect((x0 + 60, y, x0 + 76, y + 18), rgba(end), ink, 3, 3)
            pen.line([(x0 + 8, y + 7), (x0 + 50, y + 7)], rgba("#c58f5c"), 1.6)
            pen.line([(x0 + 16, y + 12), (x0 + 44, y + 12)], rgba("#c58f5c"), 1.6)
        pen.rect((30, 16, 42, 82), rgba(band), ink, 2.5, 2)
    else:                   # three round logs seen end-on, tied with a band
        for cx, cy in ((28, 68), (66, 68), (47, 36)):
            r = 20
            pen.ellipse((cx - r, cy - r, cx + r, cy + r), rgba(bark), ink, 3)
            pen.ellipse((cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6), rgba(end))
            pen.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), None, rgba(ring), 1.8)
            pen.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), rgba(ring))
            pen.line([(cx - 12, cy - 12), (cx - 6, cy - 15)], rgba("#f6e2bd"), 2)
        if theme == "perkampungan":     # two-leaf sprig
            pen.poly([(62, 14), (80, 4), (76, 20)], rgba(p["primary"]), ink, 2)
            pen.poly([(62, 14), (84, 18), (70, 26)], rgba("#5f9e55"), ink, 2)
        else:                           # small ribbon bow
            pen.poly([(47, 8), (33, 1), (33, 15)], rgba(band), ink, 2)
            pen.poly([(47, 8), (61, 1), (61, 15)], rgba(band), ink, 2)
            pen.ellipse((43, 4, 51, 12), rgba(p["accent"]), ink, 1.5)
    return pen.done(ICON_SIZE)
