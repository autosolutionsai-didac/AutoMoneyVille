"""Render the canonical background with a labeled tile grid, so building/room/object
rectangles can be read off in TILE coordinates for town_spec.json.

Bold lines + column/row numbers every 4 tiles. Output: tools/mapgen/out/grid_ref.png
Run: python tools/mapgen/grid_ref.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SQ = 32
W = 88
H = 48
REPO_ROOT = Path(__file__).resolve().parents[2]
BG = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/claudeville_bg.png"
)
OUT = Path(__file__).resolve().parent / "out" / "grid_ref.png"


def main() -> None:
    img = Image.open(BG).convert("RGB")
    d = ImageDraw.Draw(img)
    for tx in range(W + 1):
        col = (255, 255, 0) if tx % 4 == 0 else (0, 0, 0)
        wdt = 2 if tx % 4 == 0 else 1
        d.line([(tx * SQ, 0), (tx * SQ, H * SQ)], fill=col, width=wdt)
    for ty in range(H + 1):
        col = (255, 255, 0) if ty % 4 == 0 else (0, 0, 0)
        wdt = 2 if ty % 4 == 0 else 1
        d.line([(0, ty * SQ), (W * SQ, ty * SQ)], fill=col, width=wdt)
    for tx in range(0, W, 4):
        d.text((tx * SQ + 2, 1), str(tx), fill=(255, 255, 0))
        d.text((tx * SQ + 2, H * SQ - 10), str(tx), fill=(255, 255, 0))
    for ty in range(0, H, 4):
        d.text((2, ty * SQ + 1), str(ty), fill=(255, 255, 0))
        d.text((W * SQ - 16, ty * SQ + 1), str(ty), fill=(255, 255, 0))
    OUT.parent.mkdir(exist_ok=True)
    img.save(OUT)
    print(str(OUT.relative_to(REPO_ROOT)))


if __name__ == "__main__":
    main()
