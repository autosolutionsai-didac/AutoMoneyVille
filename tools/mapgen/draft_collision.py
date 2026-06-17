"""Auto-draft an 88x48 collision mask from the canonical background, by per-tile
median color (HSV heuristics). This is a STARTING POINT, not ground truth -- the
output overlay is meant to be eyeballed and the mask hand-corrected in town_spec.json.

Outputs (under tools/mapgen/out/):
  collision_draft.json   {"maze_width":88,"maze_height":48,"grid":[[0/1,...],...]}  (1 = blocked)
  collision_overlay.png  background with red tint on blocked tiles + tile grid (for QA)

Run: python tools/mapgen/draft_collision.py
"""

from __future__ import annotations

import colorsys
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SQ = 32
W = 88
H = 48
REPO_ROOT = Path(__file__).resolve().parents[2]
BG = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/claudeville_bg.png"
)
OUT = Path(__file__).resolve().parent / "out"


def classify(h_deg: float, s: float, v: float, var: float) -> int:
    """Return 1 = blocked, 0 = walkable for a tile's median color + patch variance."""
    # Water / river: blue band, reasonably saturated.
    if 185 <= h_deg <= 260 and s > 0.22 and v > 0.18:
        return 1
    # Trees / dense canopy: green band AND (dark OR busy).
    if 70 <= h_deg <= 170 and (v < 0.50 or var > 0.10):
        return 1
    # Open grass: green band, bright, smooth -> walkable.
    if 70 <= h_deg <= 170:
        return 0
    # Very dark (walls/roof shadow) -> blocked.
    if v < 0.22:
        return 1
    # Gray pavement / plaza / light interior floor -> walkable.
    if s < 0.18 and v >= 0.30:
        return 0
    # Saturated warm roofs (terracotta/brown/red) -> blocked.
    if (h_deg <= 55 or h_deg >= 300) and s > 0.30:
        return 1
    # Busy/high-variance leftover (furniture, decoration) -> blocked; smooth -> walkable.
    return 1 if var > 0.08 else 0


def main() -> None:
    arr = np.asarray(Image.open(BG).convert("RGB"), dtype=np.float32) / 255.0
    # (H, W, 3) -> tiles (48,88,32,32,3)
    tiles = arr.reshape(H, SQ, W, SQ, 3).transpose(0, 2, 1, 3, 4)
    grid = [[0] * W for _ in range(H)]
    for ty in range(H):
        for tx in range(W):
            patch = tiles[ty, tx].reshape(-1, 3)
            med = np.median(patch, axis=0)
            var = float(np.mean(np.var(patch, axis=0)))  # color variance within tile
            r, g, b = (float(c) for c in med)
            hh, _l, ss = colorsys.rgb_to_hls(r, g, b)
            _h2, sv, vv = colorsys.rgb_to_hsv(r, g, b)
            grid[ty][tx] = classify(hh * 360.0, sv, vv, var)

    # Two-pass morphology: fill 1-tile holes (walkable fully surrounded by blocked).
    for _ in range(2):
        for ty in range(1, H - 1):
            for tx in range(1, W - 1):
                if grid[ty][tx] == 0:
                    nb = (
                        grid[ty - 1][tx]
                        + grid[ty + 1][tx]
                        + grid[ty][tx - 1]
                        + grid[ty][tx + 1]
                    )
                    if nb == 4:
                        grid[ty][tx] = 1

    blocked = sum(sum(r) for r in grid)
    OUT.mkdir(exist_ok=True)
    (OUT / "collision_draft.json").write_text(
        json.dumps({"maze_width": W, "maze_height": H, "grid": grid})
    )

    # Diagnostic overlay.
    bg = Image.open(BG).convert("RGBA")
    ov = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for ty in range(H):
        for tx in range(W):
            if grid[ty][tx]:
                d.rectangle(
                    [tx * SQ, ty * SQ, tx * SQ + SQ - 1, ty * SQ + SQ - 1],
                    fill=(255, 0, 0, 90),
                )
    for tx in range(W + 1):
        d.line([(tx * SQ, 0), (tx * SQ, H * SQ)], fill=(0, 0, 0, 40))
    for ty in range(H + 1):
        d.line([(0, ty * SQ), (W * SQ, ty * SQ)], fill=(0, 0, 0, 40))
    Image.alpha_composite(bg, ov).convert("RGB").save(OUT / "collision_overlay.png")
    print(
        json.dumps(
            {
                "blocked_tiles": blocked,
                "walkable_tiles": W * H - blocked,
                "pct_blocked": round(100 * blocked / (W * H), 1),
                "overlay": str((OUT / "collision_overlay.png").relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
