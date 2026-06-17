"""Generate the engine's world data from town_spec.json.

Emits, under environment/frontend_server/static_dirs/assets/<world>/matrix/:
  maze_meta_info.json
  maze/{collision,sector,arena,game_object,spawning_location}_maze.csv   (one row each, row-major)
  special_blocks/{world,sector,arena,game_object,spawning_location}_blocks.csv

Collision model (hybrid):
  - Outdoor tiles (no sector): blocked from collision_draft.json (streets walkable; water/trees blocked).
  - Building footprint tile inside a room (arena): walkable floor, UNLESS an object sits there (furniture -> blocked).
  - Building footprint tile NOT in any room: WALL (blocked, arena="") -> opaque per maze._is_wall.
  - blocked_regions / walkable_regions in the spec override afterward (e.g. carve a door, block a pond).
Exact-match collision contract: blocked == collision_block_id string, free == "0" (path_finder compares ==).

Run: python tools/mapgen/generate_world.py [tools/mapgen/town_spec.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPGEN = Path(__file__).resolve().parent
DEFAULT_SPEC = MAPGEN / "town_spec.json"
DRAFT = MAPGEN / "out" / "collision_draft.json"

ID_WORLD = 32100
ID_SECTOR0 = 32200
ID_ARENA0 = 32300
ID_OBJECT0 = 32400
ID_SPAWN0 = 32500


def _rects(entry):
    if "rects" in entry:
        return entry["rects"]
    if "rect" in entry:
        return [entry["rect"]]
    return []


def _fill(grid, rect, val):
    x0, y0, x1, y1 = rect
    gh, gw = len(grid), len(grid[0])
    for y in range(max(0, y0), min(gh, y1 + 1)):
        for x in range(max(0, x0), min(gw, x1 + 1)):
            grid[y][x] = val


def _connect_components(collision, cbid, H, W):
    """Carve short walkable channels (doors) so every walkable region of size>=3
    reaches the largest (street) component. Channels are collision-only (invisible
    on the PNG) and minimal (nearest manhattan bridge)."""
    from collections import deque

    def walk(x, y):
        return collision[y][x] != cbid

    comp = [[-1] * W for _ in range(H)]
    comps = []
    for sy in range(H):
        for sx in range(W):
            if walk(sx, sy) and comp[sy][sx] == -1:
                cid = len(comps)
                comp[sy][sx] = cid
                q = deque([(sx, sy)])
                tiles = [(sx, sy)]
                while q:
                    cx, cy = q.popleft()
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < W and 0 <= ny < H and walk(nx, ny) and comp[ny][nx] == -1:
                            comp[ny][nx] = cid
                            q.append((nx, ny))
                            tiles.append((nx, ny))
                comps.append(tiles)
    if len(comps) <= 1:
        return 0
    main = max(range(len(comps)), key=lambda i: len(comps[i]))
    main_set = set(comps[main])
    carved = 0
    for i, tiles in enumerate(comps):
        if i == main or len(tiles) < 3:
            continue
        best = None
        for (x, y) in tiles:
            for (mx, my) in main_set:
                d = abs(x - mx) + abs(y - my)
                if best is None or d < best[0]:
                    best = (d, x, y, mx, my)
        if not best:
            continue
        _, x0, y0, x1, y1 = best
        for x in range(min(x0, x1), max(x0, x1) + 1):
            collision[y0][x] = "0"
        for y in range(min(y0, y1), max(y0, y1) + 1):
            collision[y][x1] = "0"
        main_set.update(tiles)
        carved += 1
    return carved


def main() -> None:
    spec_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SPEC
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    world = spec["world_name"]
    W = spec["grid"]["maze_width"]
    H = spec["grid"]["maze_height"]
    sq = spec["grid"]["sq_tile_size"]
    cbid = str(spec.get("collision_block_id", "32125"))

    errors = []

    def blank():
        return [[0] * W for _ in range(H)]

    sector_g, arena_g, object_g, spawn_g = blank(), blank(), blank(), blank()
    collision = [["0"] * W for _ in range(H)]

    # --- legends + id assignment ---
    sector_ids, object_ids = {}, {}
    sector_rows, arena_rows, object_rows, spawn_rows = [], [], [], []

    # Sectors (footprints)
    for i, sec in enumerate(spec.get("sectors", [])):
        name = sec["name"]
        sid = ID_SECTOR0 + i
        sector_ids[name] = sid
        sector_rows.append([sid, world, name])
        for r in _rects(sec):
            _fill(sector_g, r, sid)

    # Arenas (rooms) -- override sector footprint inside
    for i, ar in enumerate(spec.get("arenas", [])):
        sname, aname = ar["sector"], ar["name"]
        if sname not in sector_ids:
            errors.append(f"arena '{aname}' references unknown sector '{sname}'")
            continue
        aid = ID_ARENA0 + i
        arena_rows.append([aid, world, sname, aname])
        for r in _rects(ar):
            _fill(arena_g, r, aid)
            # ensure the room's tiles are also inside the sector footprint
            _fill(sector_g, r, sector_ids[sname])

    # Game objects (unique per type name; <all> sector slot per the_ville convention)
    for i, t in enumerate(sorted({o["type"] for o in spec.get("objects", [])})):
        object_ids[t] = ID_OBJECT0 + i
        object_rows.append([ID_OBJECT0 + i, world, "<all>", t])

    # --- collision: outdoor from draft ---
    draft = json.loads(DRAFT.read_text())["grid"] if DRAFT.exists() else None
    for y in range(H):
        for x in range(W):
            if sector_g[y][x] == 0:  # outdoor
                if draft is not None and draft[y][x]:
                    collision[y][x] = cbid
            else:  # inside a building footprint
                if arena_g[y][x] == 0:
                    collision[y][x] = cbid  # wall (no arena)
                # else: room floor -> walkable (stays "0")

    # --- objects: stamp ids + mark furniture (blocked, must be inside an arena) ---
    for o in spec.get("objects", []):
        oid = object_ids[o["type"]]
        for x, y in o.get("tiles", []):
            if not (0 <= x < W and 0 <= y < H):
                errors.append(f"object {o['type']} tile ({x},{y}) out of bounds")
                continue
            if arena_g[y][x] == 0:
                errors.append(
                    f"object {o['type']} at ({x},{y}) is not inside any arena "
                    f"(would become a wall, not furniture)"
                )
            object_g[y][x] = oid
            collision[y][x] = cbid  # furniture blocks pathing (sight ok: arena!='')

    # --- spawns ---
    for i, sp in enumerate(spec.get("spawns", [])):
        sid = ID_SPAWN0 + i
        spawn_rows.append([sid, world, sp["sector"], sp["arena"], sp["name"]])
        x, y = sp["tile"]
        spawn_g[y][x] = sid

    # --- explicit overrides ---
    for r in spec.get("blocked_regions", []):
        _fill(collision, r, cbid)
    for r in spec.get("walkable_regions", []):
        _fill(collision, r, "0")

    # --- auto-connect: carve short invisible doors so every room/region reaches
    # the main street network. The color-drafted collision tends to seal building
    # interiors off from the streets (the #1 stuck-agent failure); this guarantees
    # the walkable graph is connected without hand-placing every door. ---
    if spec.get("auto_connect", True):
        _connect_components(collision, cbid, H, W)

    # --- validation ---
    for sp in spec.get("spawns", []):
        x, y = sp["tile"]
        if collision[y][x] != "0":
            errors.append(f"spawn {sp['name']} at ({x},{y}) sits on a blocked tile")
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print("  -", e)
        raise SystemExit(1)

    # --- write ---
    out = (
        REPO_ROOT
        / "environment/frontend_server/static_dirs/assets"
        / world.lower()
        / "matrix"
    )
    (out / "maze").mkdir(parents=True, exist_ok=True)
    (out / "special_blocks").mkdir(parents=True, exist_ok=True)

    (out / "maze_meta_info.json").write_text(
        json.dumps(
            {
                "world_name": world,
                "maze_width": W,
                "maze_height": H,
                "sq_tile_size": sq,
                "collision_block_id": cbid,
                "special_constraint": "",
            },
            indent=2,
        )
    )

    def write_matrix(name, grid):
        flat = ", ".join(str(grid[y][x]) for y in range(H) for x in range(W))
        (out / "maze" / f"{name}_maze.csv").write_text(flat)

    write_matrix("collision", collision)
    write_matrix("sector", sector_g)
    write_matrix("arena", arena_g)
    write_matrix("game_object", object_g)
    write_matrix("spawning_location", spawn_g)

    def write_legend(name, rows):
        (out / "special_blocks" / f"{name}_blocks.csv").write_text(
            "\n".join(", ".join(str(c) for c in r) for r in rows) + "\n"
        )

    write_legend("world", [[ID_WORLD, world]])
    write_legend("sector", sector_rows)
    write_legend("arena", arena_rows)
    write_legend("game_object", object_rows)
    write_legend("spawning_location", spawn_rows)

    print(
        json.dumps(
            {
                "world": world,
                "grid": [W, H],
                "sectors": len(sector_rows),
                "arenas": len(arena_rows),
                "objects": len(object_rows),
                "spawns": len(spawn_rows),
                "blocked_tiles": sum(
                    1 for y in range(H) for x in range(W) if collision[y][x] != "0"
                ),
                "out": str(out.relative_to(REPO_ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
