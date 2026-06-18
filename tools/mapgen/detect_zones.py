"""Structural detection of tile-grid zones from the canonical claudeville_bg.png.

Walls are EDGES/dark frames (not a color) and rooms are color-coded floors, so we
detect geometry (contours / edges / per-footprint color clusters), NOT per-tile
color thresholds (which conflate brown walls with brown floors).

Pipeline:
  1. HSV terrain masks (water / tree / grass / street) -> outdoor collision.
  2. Dark "wall/frame" mask -> external contours -> grid-snapped building footprints.
  3. (v2) per-footprint k-means on interior color -> rooms (arenas); generic objects.
Outputs under tools/mapgen/out/:
  collision_draft.json   {"maze_width","maze_height","grid":[[0/1,...]]}  (1=blocked, outdoor)
  detect_overlay.png     debug: footprint boxes + collision tint over the art
  footprints.json        [{"rect":[x0,y0,x1,y1],"area_tiles":N}, ...]  (for naming step)

Run: python tools/mapgen/detect_zones.py
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

SQ = 32
W = 88
H = 48
REPO_ROOT = Path(__file__).resolve().parents[2]
BG = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/claudeville_bg.png"
)
OUT = Path(__file__).resolve().parent / "out"

# --- tunables (HSV: H in [0,179], S/V in [0,255]) ---
WATER_H = (90, 135)
WATER_S = 55
WATER_V = 45
GREEN_H = (32, 90)
TREE_V_MAX = 85           # green darker than this = tree/canopy (blocked)
STREET_S_MAX = 50         # low saturation = gray pavement
STREET_V_MIN = 95
DARK_V_MAX = 95           # building frames / partition walls are dark brown
TILE_FRAC = 0.40          # a tile takes a class if >40% of its pixels match
MIN_BUILDING_TILES = 30   # contour bbox area in tiles to count as a building
MIN_KEEP_TILES = 20       # after de-overlap trimming, drop a footprint smaller than this
ASPECT = (0.22, 4.5)


def tile_frac(mask: np.ndarray) -> np.ndarray:
    """Reduce a full-res 0/255 mask to an (H,W) fraction-of-pixels-set per tile."""
    m = (mask > 0).astype(np.float32)
    return m.reshape(H, SQ, W, SQ).mean(axis=(1, 3))


def _overlap_tiles(a, b) -> int:
    """Shared tile-area of two inclusive rects (0 if disjoint)."""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    if ix1 < ix0 or iy1 < iy0:
        return 0
    return (ix1 - ix0 + 1) * (iy1 - iy0 + 1)


def _trim_away(r, kr):
    """Shrink rect `r` so it no longer overlaps kept rect `kr`, cutting along the axis
    with the smaller overlap extent (the likely street/frame seam between two stacked
    buildings). Mutates and returns `r`; the kept box is authoritative on its edge."""
    ow = min(r[2], kr[2]) - max(r[0], kr[0]) + 1
    oh = min(r[3], kr[3]) - max(r[1], kr[1]) + 1
    if oh <= ow:  # thinner in y -> cut horizontally
        if r[1] >= kr[1]:
            r[1] = kr[3] + 1
        else:
            r[3] = kr[1] - 1
    else:  # thinner in x -> cut vertically
        if r[0] >= kr[0]:
            r[0] = kr[2] + 1
        else:
            r[2] = kr[0] - 1
    return r


def _dedup(boxes):
    """Keep footprints DISJOINT so generate_world's per-sector tile stamping never
    overwrites a neighbour (an object tile mis-tagged with the wrong sector makes its
    address unresolvable). Process largest-first; the kept (larger, more confident) box
    wins the contested seam, and the smaller box is trimmed back to the seam. Only if a
    box would shrink below MIN_KEEP_TILES (or fully vanish inside another) is it dropped
    -- so two stacked buildings merged by a thin street/frame both survive, disjoint."""
    boxes = sorted(boxes, key=lambda f: f["area_tiles"], reverse=True)
    kept = []
    for b in boxes:
        r = list(b["rect"])
        drop = False
        # trim against every kept box (repeat until stable: a trim can expose a new seam)
        for _ in range(len(kept) + 1):
            changed = False
            for k in kept:
                if _overlap_tiles(r, k["rect"]):
                    _trim_away(r, k["rect"])
                    changed = True
                    if r[2] <= r[0] or r[3] <= r[1]:
                        drop = True
                        break
            if drop or not changed:
                break
        if drop or r[2] <= r[0] or r[3] <= r[1]:
            continue
        if (r[2] - r[0] + 1) * (r[3] - r[1] + 1) < MIN_KEEP_TILES:
            continue
        if any(_overlap_tiles(r, k["rect"]) for k in kept):
            continue
        b["rect"] = r
        b["area_tiles"] = (r[2] - r[0] + 1) * (r[3] - r[1] + 1)
        kept.append(b)
    return kept


# Landmark name anchors (tile center) read from the art layout; nearest footprint
# within MATCH_DIST tiles claims the name. Unmatched footprints become Residencia N.
LANDMARKS = {
    "Banco": (8, 11),
    "Universidad": (42, 8),
    "Academia de Agentes": (60, 8),
    "Mercado": (75, 11),
    "Taller de Trabajo": (8, 26),
    "Sala de Acuerdos": (27, 26),
    "Biblioteca": (61, 26),
    "Oficina de Correos": (79, 25),
    "Oficina de Gobierno": (51, 41),
}
MATCH_DIST = 11


def assign_names(footprints):
    names = [None] * len(footprints)
    pairs = []
    for lname, (lx, ly) in LANDMARKS.items():
        for fi, f in enumerate(footprints):
            x0, y0, x1, y1 = f["rect"]
            d = abs((x0 + x1) / 2 - lx) + abs((y0 + y1) / 2 - ly)
            pairs.append((d, lname, fi))
    pairs.sort()
    lused = set()
    for d, lname, fi in pairs:
        if d <= MATCH_DIST and names[fi] is None and lname not in lused:
            names[fi] = lname
            lused.add(lname)
    res = 1
    for fi in range(len(footprints)):
        if names[fi] is None:
            names[fi] = f"Residencia {res}"
            res += 1
    return names


def build_arenas_objects(name, rect):
    """Arenas inset 1 tile (perimeter stays an opaque wall = the drawn frame).
    Objects placed on interior corner tiles (must lie inside their arena)."""
    x0, y0, x1, y1 = rect
    ix0, iy0, ix1, iy1 = x0 + 1, y0 + 1, x1 - 1, y1 - 1
    if ix1 <= ix0 or iy1 <= iy0:
        ix0, iy0, ix1, iy1 = x0, y0, x1, y1
    arenas, objects = [], []

    arena_by_name: dict = {}

    def o(arena, typ, tile):
        # Clamp every object strictly inside its own arena rect so its engine address
        # (sector:arena:type) always resolves to a tile tagged with that arena.
        ar = arena_by_name.get(arena)
        tx, ty = tile
        if ar is not None:
            ax0, ay0, ax1, ay1 = ar["rect"]
            tx = min(max(tx, ax0), ax1)
            ty = min(max(ty, ay0), ay1)
        objects.append({"sector": name, "arena": arena, "type": typ, "tiles": [[tx, ty]]})

    def add_arena(aname, arect):
        a = {"sector": name, "name": aname, "rect": list(arect)}
        arenas.append(a)
        arena_by_name[aname] = a

    if name == "Academia de Agentes":
        add_arena("classroom", [ix0, iy0, ix1, iy1])
        o("classroom", "blackboard", (ix0, iy0))
        o("classroom", "classroom student seating", ((ix0 + ix1) // 2, iy1))
        o("classroom", "desk", (ix1, iy0))
    elif name.startswith("Residencia"):
        # A 2-room split needs >=2 columns of interior; otherwise keep one bedroom so
        # the bathroom never collapses to an empty/degenerate rect.
        if ix1 - ix0 >= 1:
            midx = (ix0 + ix1) // 2
            add_arena("bedroom", [ix0, iy0, midx, iy1])
            add_arena("bathroom", [midx + 1, iy0, ix1, iy1])
            o("bathroom", "toilet", (ix1, iy1))
            o("bathroom", "shower", (ix1, iy0))
        else:
            add_arena("bedroom", [ix0, iy0, ix1, iy1])
        o("bedroom", "bed", (ix0, iy0))
        o("bedroom", "desk", (ix0, iy1))
    elif name == "Biblioteca":
        add_arena("reading room", [ix0, iy0, ix1, iy1])
        o("reading room", "bookshelf", (ix0, iy0))
        o("reading room", "library table", ((ix0 + ix1) // 2, (iy0 + iy1) // 2))
    else:
        add_arena("main", [ix0, iy0, ix1, iy1])
        o("main", "table", ((ix0 + ix1) // 2, (iy0 + iy1) // 2))
    return arenas, objects


def main() -> None:
    OUT.mkdir(exist_ok=True)
    img = cv2.imread(str(BG))  # BGR
    if img is None:
        raise SystemExit(f"cannot read {BG}")
    img = img[: H * SQ, : W * SQ]  # ensure exact grid size
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    Hh, Sh, Vh = hsv[..., 0], hsv[..., 1], hsv[..., 2]

    green = ((Hh >= GREEN_H[0]) & (Hh <= GREEN_H[1]) & (Sh > 40)).astype(np.uint8) * 255
    water = (
        (Hh >= WATER_H[0]) & (Hh <= WATER_H[1]) & (Sh > WATER_S) & (Vh > WATER_V)
    ).astype(np.uint8) * 255
    tree = ((green > 0) & (Vh < TREE_V_MAX)).astype(np.uint8) * 255
    street = ((Sh < STREET_S_MAX) & (Vh > STREET_V_MIN)).astype(np.uint8) * 255
    dark = (
        (Vh < DARK_V_MAX) & (green == 0) & (water == 0)
    ).astype(np.uint8) * 255
    fd = tile_frac(dark)  # per-tile dark-wall fraction (for perimeter-frame test)

    # --- building footprints from the dark wall/frame mask ---
    closed = cv2.morphologyEx(
        dark, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    )
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    footprints = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        tw, th = w / SQ, h / SQ
        if tw * th < MIN_BUILDING_TILES:
            continue
        if not (ASPECT[0] <= (tw / th) <= ASPECT[1]):
            continue
        x0 = max(0, round(x / SQ))
        y0 = max(0, round(y / SQ))
        x1 = min(W - 1, round((x + w) / SQ) - 1)
        y1 = min(H - 1, round((y + h) / SQ) - 1)
        if x1 <= x0 or y1 <= y0:
            continue
        footprints.append(
            {"rect": [x0, y0, x1, y1], "area_tiles": (x1 - x0 + 1) * (y1 - y0 + 1)}
        )
    footprints = _dedup(footprints)
    footprints.sort(key=lambda f: (f["rect"][1] // 6, f["rect"][0]))

    # reject open areas (park/plaza): a real building's bbox perimeter is a dark wall
    # FRAME; an open plaza has none (perim_dark ~ 0). Real buildings measured >=0.16.
    kept = []
    for f in footprints:
        x0, y0, x1, y1 = f["rect"]
        perim = np.concatenate([
            fd[y0, x0 : x1 + 1], fd[y1, x0 : x1 + 1],
            fd[y0 : y1 + 1, x0], fd[y0 : y1 + 1, x1],
        ])
        f["perim_dark"] = round(float((perim > 0.25).mean()), 2)
        if f["perim_dark"] < 0.12:
            continue
        kept.append(f)
    footprints = kept
    names = assign_names(footprints)

    # --- outdoor collision draft (1 = blocked): water, trees blocked; street/grass walkable ---
    fw, ft, fs, fg = (tile_frac(m) for m in (water, tree, street, green))
    grid = [[0] * W for _ in range(H)]
    for ty in range(H):
        for tx in range(W):
            blocked = 0
            if fw[ty, tx] > 0.30:
                blocked = 1
            elif ft[ty, tx] > 0.45:
                blocked = 1
            grid[ty][tx] = blocked

    (OUT / "collision_draft.json").write_text(
        json.dumps({"maze_width": W, "maze_height": H, "grid": grid})
    )
    (OUT / "footprints.json").write_text(json.dumps(footprints, indent=2))

    # --- assemble town_spec.auto.json (sectors / arenas / objects / spawns) ---
    sectors, arenas, objects, spawns = [], [], [], []
    for name, f in zip(names, footprints):
        sectors.append({"name": name, "rect": f["rect"]})
        a, o = build_arenas_objects(name, f["rect"])
        arenas.extend(a)
        objects.extend(o)
    # one spawn per sector at a safe interior tile (left-middle, never an object corner)
    for name, f in zip(names, footprints):
        x0, y0, x1, y1 = f["rect"]
        ar = next((a for a in arenas if a["sector"] == name), None)
        if not ar:
            continue
        ax0, ay0, ax1, ay1 = ar["rect"]
        sx = min(ax1, ax0 + 1)
        sy = (ay0 + ay1) // 2
        spawns.append({"sector": name, "arena": ar["name"], "name": "sp", "tile": [sx, sy]})
    spec = {
        "world_name": "Claudeville",
        "grid": {"maze_width": W, "maze_height": H, "sq_tile_size": SQ},
        "collision_block_id": "32125",
        "outdoor_collision_from_draft": True,
        "auto_connect": True,
        "_generated_by": "detect_zones.py (structural OpenCV auto-detection)",
        "sectors": sectors,
        "arenas": arenas,
        "objects": objects,
        "spawns": spawns,
    }
    (OUT / "town_spec.auto.json").write_text(json.dumps(spec, indent=2))

    # --- debug overlay ---
    ov = img.copy()
    tint = ov.copy()
    for ty in range(H):
        for tx in range(W):
            if grid[ty][tx]:
                cv2.rectangle(
                    tint, (tx * SQ, ty * SQ), (tx * SQ + SQ, ty * SQ + SQ),
                    (0, 0, 255), -1,
                )
    ov = cv2.addWeighted(tint, 0.28, ov, 0.72, 0)
    for name, f in zip(names, footprints):
        x0, y0, x1, y1 = f["rect"]
        cv2.rectangle(
            ov, (x0 * SQ, y0 * SQ), ((x1 + 1) * SQ, (y1 + 1) * SQ), (0, 255, 0), 3
        )
        cv2.putText(
            ov, name, (x0 * SQ + 4, y0 * SQ + 22),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
        )
    for tx in range(W + 1):
        cv2.line(ov, (tx * SQ, 0), (tx * SQ, H * SQ), (0, 0, 0), 1)
    for ty in range(H + 1):
        cv2.line(ov, (0, ty * SQ), (W * SQ, ty * SQ), (0, 0, 0), 1)
    cv2.imwrite(str(OUT / "detect_overlay.png"), ov)

    print(json.dumps({
        "buildings": len(footprints),
        "named": {n: f["rect"] for n, f in zip(names, footprints)},
        "arenas": len(arenas),
        "objects": len(objects),
        "outdoor_blocked_tiles": sum(sum(r) for r in grid),
        "spec": str((OUT / "town_spec.auto.json").relative_to(REPO_ROOT)),
        "overlay": str((OUT / "detect_overlay.png").relative_to(REPO_ROOT)),
    }, indent=2))


if __name__ == "__main__":
    main()
