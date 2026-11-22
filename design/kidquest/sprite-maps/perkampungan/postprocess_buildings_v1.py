"""Deterministic alpha cleanup and whole-sprite anchor alignment for KQ-028."""

from pathlib import Path

from scripts.validate_building_sprite_map import decode_png_rgba, encode_png_rgba


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "revisions" / "buildings_v1_r2_raw.png"
OUTPUT = HERE / "buildings_v1.png"
SLOT_SIZE = 512
SAFE_MIN = 32
SAFE_MAX = 480
ALPHA_FLOOR = 8

# Whole-sprite translations only. Each value aligns the generated center contact
# with slot-local y=464; x remains unchanged and no sprite is rescaled.
DY_BY_SLOT = (3, 20, 3, 59, 62, 64)


def main() -> None:
    image = decode_png_rgba(SOURCE.read_bytes())
    if (image.width, image.height) != (1536, 1024):
        raise SystemExit(f"unexpected source size: {image.width}x{image.height}")

    cleaned = bytearray(image.width * image.height * 4)
    kept = 0
    removed_glow = 0
    clipped_to_safe_area = 0

    for slot, dy in enumerate(DY_BY_SLOT):
        slot_x = (slot % 3) * SLOT_SIZE
        slot_y = (slot // 3) * SLOT_SIZE
        for local_y in range(SLOT_SIZE):
            for local_x in range(SLOT_SIZE):
                source_offset = ((slot_y + local_y) * image.width + slot_x + local_x) * 4
                alpha = image.rgba[source_offset + 3]
                if alpha < ALPHA_FLOOR:
                    removed_glow += alpha > 0
                    continue

                target_y = local_y + dy
                if not (SAFE_MIN <= local_x <= SAFE_MAX and SAFE_MIN <= target_y <= SAFE_MAX):
                    clipped_to_safe_area += 1
                    continue

                target_offset = ((slot_y + target_y) * image.width + slot_x + local_x) * 4
                cleaned[target_offset:target_offset + 3] = image.rgba[source_offset:source_offset + 3]
                cleaned[target_offset + 3] = 255 if alpha >= 250 else alpha
                kept += 1

    # Remove only detached antialias/glow fragments that contain no opaque art.
    # This is background extraction, not a shape edit: connected sprite edges stay.
    visited = bytearray(image.width * image.height)
    detached_partial_pixels = 0
    for start in range(image.width * image.height):
        if visited[start] or cleaned[start * 4 + 3] == 0:
            continue
        component = []
        stack = [start]
        visited[start] = 1
        has_opaque = False
        while stack:
            index = stack.pop()
            component.append(index)
            has_opaque |= cleaned[index * 4 + 3] == 255
            x, y = index % image.width, index // image.width
            for neighbor in (
                index - 1 if x else -1,
                index + 1 if x + 1 < image.width else -1,
                index - image.width if y else -1,
                index + image.width if y + 1 < image.height else -1,
            ):
                if neighbor >= 0 and not visited[neighbor] and cleaned[neighbor * 4 + 3] > 0:
                    visited[neighbor] = 1
                    stack.append(neighbor)
        if not has_opaque:
            for index in component:
                cleaned[index * 4:index * 4 + 4] = b"\x00\x00\x00\x00"
            detached_partial_pixels += len(component)

    OUTPUT.write_bytes(encode_png_rgba(image.width, image.height, bytes(cleaned)))
    print(
        f"wrote {OUTPUT} ({kept} visible pixels kept, "
        f"{removed_glow} low-alpha glow pixels removed, "
        f"{clipped_to_safe_area} edge pixels removed outside safe bounds, "
        f"{detached_partial_pixels} detached partial-alpha pixels removed)"
    )


if __name__ == "__main__":
    main()
