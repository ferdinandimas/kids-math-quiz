"""Create native and responsive QA captures from the final City sprite map."""

from __future__ import annotations

import math
from pathlib import Path

from scripts.validate_building_sprite_map import decode_png_rgba, encode_png_rgba


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "buildings_v1.png"
REVIEW = HERE / "review"

SLOTS = (
    ("starter_house", 0, 0),
    ("garden", 512, 0),
    ("bakery", 1024, 0),
    ("park", 0, 512),
    ("bridge", 512, 512),
    ("market_stall", 1024, 512),
)


def crop(rgba: bytes, width: int, x: int, y: int, crop_width: int, crop_height: int) -> bytes:
    result = bytearray(crop_width * crop_height * 4)
    source_stride = width * 4
    target_stride = crop_width * 4
    for row in range(crop_height):
        source_start = (y + row) * source_stride + x * 4
        target_start = row * target_stride
        result[target_start:target_start + target_stride] = rgba[source_start:source_start + target_stride]
    return bytes(result)


def resize_premultiplied(rgba: bytes, width: int, height: int, target_width: int, target_height: int) -> bytes:
    """Bilinear resize in premultiplied-alpha space to avoid transparent-edge halos."""
    result = bytearray(target_width * target_height * 4)
    scale_x = width / target_width
    scale_y = height / target_height
    for target_y in range(target_height):
        source_y = (target_y + 0.5) * scale_y - 0.5
        y0 = max(0, min(height - 1, math.floor(source_y)))
        y1 = min(height - 1, y0 + 1)
        fy = max(0.0, min(1.0, source_y - y0))
        for target_x in range(target_width):
            source_x = (target_x + 0.5) * scale_x - 0.5
            x0 = max(0, min(width - 1, math.floor(source_x)))
            x1 = min(width - 1, x0 + 1)
            fx = max(0.0, min(1.0, source_x - x0))
            samples = (
                (x0, y0, (1.0 - fx) * (1.0 - fy)),
                (x1, y0, fx * (1.0 - fy)),
                (x0, y1, (1.0 - fx) * fy),
                (x1, y1, fx * fy),
            )
            alpha = 0.0
            red = green = blue = 0.0
            for sx, sy, weight in samples:
                offset = (sy * width + sx) * 4
                sample_alpha = rgba[offset + 3]
                alpha += sample_alpha * weight
                red += rgba[offset] * sample_alpha * weight
                green += rgba[offset + 1] * sample_alpha * weight
                blue += rgba[offset + 2] * sample_alpha * weight
            target_offset = (target_y * target_width + target_x) * 4
            if alpha > 0.0:
                result[target_offset] = max(0, min(255, round(red / alpha)))
                result[target_offset + 1] = max(0, min(255, round(green / alpha)))
                result[target_offset + 2] = max(0, min(255, round(blue / alpha)))
                result[target_offset + 3] = max(0, min(255, round(alpha)))
    return bytes(result)


def write_capture(name: str, width: int, height: int, rgba: bytes) -> None:
    path = REVIEW / name
    path.write_bytes(encode_png_rgba(width, height, rgba))
    print(path.relative_to(HERE))


def main() -> None:
    REVIEW.mkdir(parents=True, exist_ok=True)
    image = decode_png_rgba(SOURCE.read_bytes())
    write_capture("full-native.png", image.width, image.height, image.rgba)

    slot_images: dict[str, bytes] = {}
    for name, x, y in SLOTS:
        slot_rgba = crop(image.rgba, image.width, x, y, 512, 512)
        slot_images[name] = slot_rgba
        write_capture(f"{name}-native.png", 512, 512, slot_rgba)

    for cell_px in (38, 48, 64):
        full_width, full_height = cell_px * 12, cell_px * 8
        full_scaled = resize_premultiplied(image.rgba, image.width, image.height, full_width, full_height)
        write_capture(f"full-cell-{cell_px}.png", full_width, full_height, full_scaled)
        slot_size = cell_px * 4
        for name, slot_rgba in slot_images.items():
            scaled = resize_premultiplied(slot_rgba, 512, 512, slot_size, slot_size)
            write_capture(f"{name}-cell-{cell_px}.png", slot_size, slot_size, scaled)


if __name__ == "__main__":
    main()
