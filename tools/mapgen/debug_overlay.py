"""Render the authored zones + generated collision over the background, so the
spec can be visually aligned to the art. Output: tools/mapgen/out/zones_overlay.png

  - red fill           = collision (blocked) tiles, read from the GENERATED collision_maze.csv
  - colored rectangle  = sector footprint (+ label)
  - white outline      = arena (room)
  - yellow dot         = object (furniture) tile
  - green dot          = spawn tile

Run after generate_world.py: python tools/mapgen/debug_overlay.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

SQ = 32
REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).resolve().parent / "town_spec.json"
OUT = Path(__file__).resolve().parent / "out" / "zones_overlay.png"
PALETTE = [
    (255, 80, 80), (80, 160, 255), (80, 255, 120), (255, 200, 60),
    (220, 100, 255), (60, 230, 230), (255, 140, 60), (180, 255, 80),
]


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    world = spec["world_name"]
    W = spec["grid"]["maze_width"]
    matrix = (
        REPO_ROOT
        / "environment/frontend_server/static_dirs/assets"
        / world.lower()
        / "matrix"
    )
    bg = Image.open(matrix.parent / "visuals" / "claudeville_bg.png").convert("RGBA")
    ov = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # collision from the generated matrix
    cbid = str(spec.get("collision_block_id", "32125"))
    flat = (matrix / "maze" / "collision_maze.csv").read_text().split(",")
    flat = [t.strip() for t in flat]
    for i, t in enumerate(flat):
        if t == cbid:
            x, y = i % W, i // W
            d.rectangle([x * SQ, y * SQ, x * SQ + SQ - 1, y * SQ + SQ - 1], fill=(255, 0, 0, 70))

    # sectors
    for idx, s in enumerate(spec.get("sectors", [])):
        col = PALETTE[idx % len(PALETTE)]
        rects = s.get("rects", [s["rect"]] if "rect" in s else [])
        for (x0, y0, x1, y1) in rects:
            d.rectangle(
                [x0 * SQ, y0 * SQ, (x1 + 1) * SQ - 1, (y1 + 1) * SQ - 1],
                outline=col + (255,), width=3,
            )
            d.text((x0 * SQ + 3, y0 * SQ + 3), s["name"], fill=col + (255,))

    # arenas
    for a in spec.get("arenas", []):
        rects = a.get("rects", [a["rect"]] if "rect" in a else [])
        for (x0, y0, x1, y1) in rects:
            d.rectangle(
                [x0 * SQ, y0 * SQ, (x1 + 1) * SQ - 1, (y1 + 1) * SQ - 1],
                outline=(255, 255, 255, 200), width=1,
            )

    # objects + spawns
    for o in spec.get("objects", []):
        for (x, y) in o.get("tiles", []):
            d.ellipse([x * SQ + 8, y * SQ + 8, x * SQ + 24, y * SQ + 24], fill=(255, 230, 0, 230))
    for sp in spec.get("spawns", []):
        x, y = sp["tile"]
        d.ellipse([x * SQ + 6, y * SQ + 6, x * SQ + 26, y * SQ + 26], outline=(0, 255, 0, 255), width=3)

    OUT.parent.mkdir(exist_ok=True)
    Image.alpha_composite(bg, ov).convert("RGB").save(OUT)
    print(str(OUT.relative_to(REPO_ROOT)))


if __name__ == "__main__":
    main()
