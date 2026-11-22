"""Create native and responsive review captures for the KQ-028 handoff."""

from pathlib import Path
import shutil
import subprocess

from scripts.validate_building_sprite_map import decode_png_rgba, encode_png_rgba


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "buildings_v1.png"
REVIEW = HERE / "review"
SLOT_NAMES = (
    "starter_house",
    "garden",
    "bakery",
    "park",
    "bridge",
    "market_stall",
)


def crop_rgba(rgba: bytes, canvas_width: int, x: int, y: int, width: int, height: int) -> bytes:
    rows = []
    for source_y in range(y, y + height):
        start = (source_y * canvas_width + x) * 4
        rows.append(rgba[start:start + width * 4])
    return b"".join(rows)


def resize(source: Path, output: Path, width: int, height: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["/usr/bin/sips", "--resampleHeightWidth", str(height), str(width), str(source), "--out", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> None:
    image = decode_png_rgba(SOURCE.read_bytes())
    native = REVIEW / "native"
    native.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, native / "full_map.png")

    native_cells = []
    for index, name in enumerate(SLOT_NAMES):
        x = (index % 3) * 512
        y = (index // 3) * 512
        output = native / f"{name}.png"
        output.write_bytes(encode_png_rgba(512, 512, crop_rgba(image.rgba, image.width, x, y, 512, 512)))
        native_cells.append(output)

    for cell_px in (38, 48, 64):
        scaled = REVIEW / f"{cell_px}px-per-cell"
        resize(native / "full_map.png", scaled / "full_map.png", cell_px * 12, cell_px * 8)
        for source, name in zip(native_cells, SLOT_NAMES):
            resize(source, scaled / f"{name}.png", cell_px * 4, cell_px * 4)

    print(f"wrote native plus 38/48/64 px-per-cell captures under {REVIEW}")


if __name__ == "__main__":
    main()
