import struct
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).parent
ICON_SOURCE = ROOT / "Chess Chase.png"
ICON_DIR = ROOT / "build" / "icons"
SIZES = [16, 32, 48, 64, 128, 256, 512, 1024]


def png(size):
    path = ICON_DIR / f"icon-{size}.png"
    image = Image.open(ICON_SOURCE).convert("RGBA").resize((size, size), Image.LANCZOS)
    image.save(path)
    return path.read_bytes()


def write_icns(pngs):
    parts = []
    for kind, size in [
        (b"icp4", 16),
        (b"icp5", 32),
        (b"icp6", 64),
        (b"ic07", 128),
        (b"ic08", 256),
        (b"ic09", 512),
        (b"ic10", 1024),
    ]:
        data = pngs[size]
        parts.append(kind + struct.pack(">I", len(data) + 8) + data)
    (ICON_DIR / "Chess Chase.icns").write_bytes(
        b"icns" + struct.pack(">I", sum(map(len, parts)) + 8) + b"".join(parts)
    )


def write_ico(pngs):
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    entries = []
    for size in sizes:
        data = pngs[size]
        width = 0 if size == 256 else size
        entries.append((width, width, len(data), 6 + 16 * len(sizes) + sum(len(i) for i in images)))
        images.append(data)

    header = struct.pack("<HHH", 0, 1, len(entries))
    directory = b"".join(
        struct.pack("<BBBBHHII", width, height, 0, 0, 1, 32, length, offset)
        for width, height, length, offset in entries
    )
    (ICON_DIR / "Chess Chase.ico").write_bytes(header + directory + b"".join(images))


def main():
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    pngs = {size: png(size) for size in SIZES}
    write_icns(pngs)
    write_ico(pngs)


if __name__ == "__main__":
    main()
