"""Generate Pred-Oracle wordmark for the show-n-tell brand badge.

Outputs a black-on-transparent PNG. The badge renderer recolors black->cream
automatically via _lib.load_logo, so this just needs to be the silhouette.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


TEXT = "Pred-Oracle"
WIDTH = 800
HEIGHT = 180
FONT_PATH_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
]


def _load_font(target_px: int) -> ImageFont.FreeTypeFont:
    for path in FONT_PATH_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=target_px)
    raise SystemExit("No suitable bold sans-serif font found")


def render() -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(target_px=112)
    bbox = draw.textbbox((0, 0), TEXT, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (WIDTH - tw) // 2 - bbox[0]
    y = (HEIGHT - th) // 2 - bbox[1]
    draw.text((x, y), TEXT, font=font, fill=(0, 0, 0, 255))
    return img


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    img = render()
    img.save(args.out, format="PNG")
    print(f"wrote {args.out}  size={img.size}")


if __name__ == "__main__":
    main()
