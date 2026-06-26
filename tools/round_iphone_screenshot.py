# /// script
# dependencies = ["pillow"]
# ///

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


IPHONE_17_CORNER_RADIUS_RATIO = 0.145


def rounded(path, radius=None):
    image = Image.open(path).convert("RGBA")
    width, height = image.size
    radius = radius or round(min(width, height) * IPHONE_17_CORNER_RADIUS_RATIO)

    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
    image.putalpha(mask)
    image.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("png", type=Path)
    parser.add_argument("--radius", type=int)
    args = parser.parse_args()
    rounded(args.png, args.radius)


if __name__ == "__main__":
    main()
