"""Deterministically prepare City revision 2 for the frozen v1 contract.

This script never draws or alters individual building parts. It removes generator
haze, normalizes alpha, translates each complete slot as one unit, applies
documented uniform whole-slot scales to the bridge and market stall, clears pixels outside
the safe area, and writes an sRGB PNG.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_building_sprite_map import decode_png_rgba, encode_png_rgba


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "revisions" / "revision-02-generated.png"
OUTPUT = HERE / "buildings_v1.png"

WIDTH = 1536
HEIGHT = 1024
SLOT = 512
SAFE_MIN = 32
SAFE_MAX = 480

# Whole-slot transforms chosen from measured alpha>16 bounds and entrance centers.
# Slot order: house, garden, bakery, park, bridge, market stall. The bridge's
# 27/25 scale aligns both generated short-end deck contacts with the frozen
# endpoints while staying inside its 32 px height-overhang profile. The stall's
# 49/50 scale reduces its generated 208 px opaque width to <=204 px.
TRANSLATIONS = ((-6, -27), (-1, -24), (7, -29), (-7, 19), (-6, 17), (7, 11))
SCALE_RATIOS = ((1, 1), (1, 1), (1, 1), (1, 1), (27, 25), (49, 50))
ANCHOR = (256, 464)


def cleaned_slot(source: bytes, ox: int, oy: int) -> tuple[bytes, int, int]:
    rgba = bytearray(SLOT * SLOT * 4)
    removed_haze = promoted_opaque = 0
    for local_y in range(SLOT):
        for local_x in range(SLOT):
            src_offset = ((oy + local_y) * WIDTH + ox + local_x) * 4
            red, green, blue, alpha = source[src_offset:src_offset + 4]
            if alpha < 16:
                removed_haze += alpha > 0
                continue
            if alpha >= 250:
                alpha = 255
                promoted_opaque += 1
            dst_offset = (local_y * SLOT + local_x) * 4
            rgba[dst_offset:dst_offset + 4] = bytes((red, green, blue, alpha))
    return bytes(rgba), removed_haze, promoted_opaque


def alpha_sample(rgba: bytes, x: int, y: int) -> tuple[int, int, int, int]:
    if not (0 <= x < SLOT and 0 <= y < SLOT):
        return 0, 0, 0, 0
    offset = (y * SLOT + x) * 4
    return tuple(rgba[offset:offset + 4])


def transformed_pixel(rgba: bytes, target_x: int, target_y: int, dx: int, dy: int,
                      numerator: int, denominator: int) -> tuple[int, int, int, int]:
    if numerator == denominator:
        return alpha_sample(rgba, target_x - dx, target_y - dy)

    scale = numerator / denominator
    source_x = ((target_x + 0.5 - ANCHOR[0] - dx) / scale) + ANCHOR[0] - 0.5
    source_y = ((target_y + 0.5 - ANCHOR[1] - dy) / scale) + ANCHOR[1] - 0.5
    x0, y0 = int(source_x // 1), int(source_y // 1)
    fx, fy = source_x - x0, source_y - y0
    samples = (
        (alpha_sample(rgba, x0, y0), (1 - fx) * (1 - fy)),
        (alpha_sample(rgba, x0 + 1, y0), fx * (1 - fy)),
        (alpha_sample(rgba, x0, y0 + 1), (1 - fx) * fy),
        (alpha_sample(rgba, x0 + 1, y0 + 1), fx * fy),
    )
    alpha = round(sum(pixel[3] * weight for pixel, weight in samples))
    if alpha < 16:
        return 0, 0, 0, 0
    premultiplied = [sum(pixel[channel] * pixel[3] * weight for pixel, weight in samples)
                     for channel in range(3)]
    rgb = [max(0, min(255, round(value / alpha))) for value in premultiplied]
    if alpha >= 250:
        alpha = 255
    return rgb[0], rgb[1], rgb[2], alpha


def main() -> None:
    image = decode_png_rgba(SOURCE.read_bytes())
    if (image.width, image.height) != (WIDTH, HEIGHT):
        raise ValueError(f"unexpected source size: {image.width}x{image.height}")

    source = image.rgba
    result = bytearray(WIDTH * HEIGHT * 4)
    removed_haze = promoted_opaque = 0
    clipped_safe = 0

    for slot_index, ((dx, dy), (numerator, denominator)) in enumerate(zip(TRANSLATIONS, SCALE_RATIOS, strict=True)):
        ox = (slot_index % 3) * SLOT
        oy = (slot_index // 3) * SLOT
        slot, removed, promoted = cleaned_slot(source, ox, oy)
        removed_haze += removed
        promoted_opaque += promoted
        for local_y in range(SLOT):
            for local_x in range(SLOT):
                red, green, blue, alpha = transformed_pixel(
                    slot, local_x, local_y, dx, dy, numerator, denominator
                )
                if alpha == 0:
                    continue
                if not (SAFE_MIN <= local_x <= SAFE_MAX and SAFE_MIN <= local_y <= SAFE_MAX):
                    clipped_safe += 1
                    continue
                dst_offset = ((oy + local_y) * WIDTH + ox + local_x) * 4
                result[dst_offset:dst_offset + 4] = bytes((red, green, blue, alpha))

    OUTPUT.write_bytes(encode_png_rgba(WIDTH, HEIGHT, bytes(result)))
    print(f"source={SOURCE}")
    print(f"output={OUTPUT}")
    print(f"removed_haze_pixels={removed_haze}")
    print(f"promoted_opaque_pixels={promoted_opaque}")
    print(f"clipped_outside_safe_bounds={clipped_safe}")
    for index, (translation, scale) in enumerate(zip(TRANSLATIONS, SCALE_RATIOS, strict=True), 1):
        print(f"slot_{index}_translation={translation} scale={scale[0]}/{scale[1]}")


if __name__ == "__main__":
    main()
