"""Canonicalize the source town PNG to an exact tile grid.

The Gemini-generated map is 2814x1536. The engine grid is sq_tile_size=32, so we
need a width divisible by 32. 88*32 = 2816 (pad +2px), 48*32 = 1536 (already exact).
We PAD (edge-replicate), never rescale -- rescaling resamples colors and smears tile
boundaries, which would wreck the per-tile color classification in draft_collision.

The single canonical background written here is shared by:
  - the Phaser frontend (rendered as the flat map background),
  - draft_collision.py / debug_overlay.py (per-tile analysis),
so geometry can never drift between renderer, generator, and engine.

For art that doesn't already match the grid aspect (e.g. a cleanly-rendered map at
a different resolution), pass `rescale` to resize the whole image to the exact grid
instead of padding. The structural detector (detect_zones.py) uses edges/contours,
which survive a clean LANCZOS upscale -- unlike the legacy per-tile color classifier.

Usage:
  python tools/mapgen/canonicalize_map.py <source.png> [rescale]
Writes: environment/frontend_server/static_dirs/assets/claudeville/visuals/claudeville_bg.png
Prints the locked grid dims as JSON for downstream tools.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

SQ_TILE_SIZE = 32
MAZE_WIDTH = 88   # 88 * 32 = 2816
MAZE_HEIGHT = 48  # 48 * 32 = 1536

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = (
    REPO_ROOT
    / "environment"
    / "frontend_server"
    / "static_dirs"
    / "assets"
    / "claudeville"
    / "visuals"
)
OUT_PATH = OUT_DIR / "claudeville_bg.png"


def canonicalize(source: Path, rescale: bool = False) -> dict:
    target_w = MAZE_WIDTH * SQ_TILE_SIZE
    target_h = MAZE_HEIGHT * SQ_TILE_SIZE

    img = Image.open(source).convert("RGB")
    src_w, src_h = img.size

    if rescale:
        # Clean art at a different resolution: resize the whole image to the exact
        # grid with LANCZOS. The structural detector uses edges/contours, which
        # survive a clean resample, so no padding/size guard is needed here.
        canvas = img.resize((target_w, target_h), Image.LANCZOS)
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        canvas.save(OUT_PATH)
        return {
            "world_name": "Claudeville",
            "source": str(source),
            "source_size": [src_w, src_h],
            "mode": "rescale",
            "pad_right": 0,
            "pad_bottom": 0,
            "maze_width": MAZE_WIDTH,
            "maze_height": MAZE_HEIGHT,
            "sq_tile_size": SQ_TILE_SIZE,
            "background_px": [target_w, target_h],
            "background": str(OUT_PATH.relative_to(REPO_ROOT)),
        }

    if src_w > target_w or src_h > target_h:
        raise SystemExit(
            f"Source {src_w}x{src_h} exceeds target {target_w}x{target_h}; "
            "adjust MAZE_WIDTH/MAZE_HEIGHT or downscale deliberately first "
            "(or pass `rescale` to resize to the exact grid)."
        )

    pad_right = target_w - src_w
    pad_bottom = target_h - src_h

    # Edge-replicate pad (avoid a fake colored border that would mis-classify).
    canvas = Image.new("RGB", (target_w, target_h))
    canvas.paste(img, (0, 0))
    if pad_right:
        right_edge = img.crop((src_w - 1, 0, src_w, src_h))
        for x in range(src_w, target_w):
            canvas.paste(right_edge, (x, 0))
    if pad_bottom:
        bottom_edge = canvas.crop((0, src_h - 1, target_w, src_h))
        for y in range(src_h, target_h):
            canvas.paste(bottom_edge, (0, y))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT_PATH)

    return {
        "world_name": "Claudeville",
        "source": str(source),
        "source_size": [src_w, src_h],
        "pad_right": pad_right,
        "pad_bottom": pad_bottom,
        "maze_width": MAZE_WIDTH,
        "maze_height": MAZE_HEIGHT,
        "sq_tile_size": SQ_TILE_SIZE,
        "background_px": [target_w, target_h],
        "background": str(OUT_PATH.relative_to(REPO_ROOT)),
    }


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "rescale"):
        raise SystemExit("usage: canonicalize_map.py <source.png> [rescale]")
    info = canonicalize(Path(sys.argv[1]), rescale=(len(sys.argv) == 3))
    print(json.dumps(info, indent=2))
