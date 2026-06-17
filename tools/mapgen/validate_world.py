"""Load the generated world through the real engine Maze and assert it is sane:
 - every authored sector/arena/object address resolves to >=1 tile in maze.address_tiles
 - from each spawn, a path exists to that building's first object's adjacent tile
   (reachability -> catches sealed doors / walled-off rooms)
 - collision_maze contains only "0" and the world's collision_block_id

Run from repo root: python tools/mapgen/validate_world.py
(It chdir's into reverie/backend_server so the relative asset paths resolve, exactly
 like reverie.py does.)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).resolve().parent / "town_spec.json"
BACKEND = REPO_ROOT / "reverie" / "backend_server"


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    world = spec["world_name"]
    folder = world.lower()

    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    from maze import Maze
    from path_finder import PathFinder

    maze = Maze(folder)
    print(f"Loaded '{folder}': {maze.maze_width}x{maze.maze_height} cbid={maze.collision_block_id}")

    fails = []

    # 1) address resolution
    def check(addr):
        if addr not in maze.address_tiles or not maze.address_tiles[addr]:
            fails.append(f"address not resolvable: {addr}")
            return False
        return True

    for s in spec.get("sectors", []):
        check(f"{world}:{s['name']}")
    for a in spec.get("arenas", []):
        check(f"{world}:{a['sector']}:{a['name']}")
    for o in spec.get("objects", []):
        check(f"{world}:{o['sector']}:{o['arena']}:{o['type']}")

    # 2) collision token sanity
    bad = set()
    for row in maze.collision_maze:
        for c in row:
            if c not in ("0", maze.collision_block_id):
                bad.add(c)
    if bad:
        fails.append(f"collision_maze has unexpected tokens: {sorted(bad)[:5]}")

    # 3) reachability: from each spawn, path to its building's first object's adj tile
    pf = PathFinder(maze.collision_maze, maze.collision_block_id)
    spawn_by_sector = {sp["sector"]: tuple(sp["tile"]) for sp in spec.get("spawns", [])}
    for o in spec.get("objects", []):
        sec = o["sector"]
        if sec not in spawn_by_sector:
            continue
        start = spawn_by_sector[sec]
        obj_tiles = maze.address_tiles.get(
            f"{world}:{sec}:{o['arena']}:{o['type']}", set()
        )
        # adjacent walkable tiles of the object
        targets = []
        for (ox, oy) in obj_tiles:
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ax, ay = ox + dx, oy + dy
                if (
                    0 <= ay < maze.maze_height
                    and 0 <= ax < maze.maze_width
                    and maze.collision_maze[ay][ax] == "0"
                ):
                    targets.append((ax, ay))
        ok = False
        for t in targets[:6]:
            path = pf.find_path(start, t)
            if path and path[-1] == t:
                ok = True
                break
        if not ok and obj_tiles:
            fails.append(
                f"UNREACHABLE: spawn {start} cannot reach {sec}:{o['arena']}:{o['type']}"
            )

    # 4) walkable connectivity: the largest walkable component should cover ~all
    #    walkable tiles (a low % means whole regions are sealed off from each other)
    from collections import deque

    cm = maze.collision_maze
    Wd, Hd = maze.maze_width, maze.maze_height
    walk = [(x, y) for y in range(Hd) for x in range(Wd) if cm[y][x] == "0"]
    walkset = set(walk)
    seen = set()
    biggest = 0
    for start in walk:
        if start in seen:
            continue
        comp = 0
        q = deque([start])
        seen.add(start)
        while q:
            cx, cy = q.popleft()
            comp += 1
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if (nx, ny) in walkset and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        biggest = max(biggest, comp)
    pct = 100.0 * biggest / max(1, len(walk))
    print(f"Walkable connectivity: largest component {biggest}/{len(walk)} = {pct:.1f}%")
    if pct < 98.0:
        fails.append(f"walkable graph fragmented: largest component only {pct:.1f}% (<98%)")

    # 5) no spawn / arena-center sits on a wall (blocked) tile
    def on_wall(x, y):
        return not (0 <= x < Wd and 0 <= y < Hd) or cm[y][x] != "0"

    for sp in spec.get("spawns", []):
        x, y = sp["tile"]
        if on_wall(x, y):
            fails.append(f"spawn {sp['name']} @ {sp['tile']} is on a wall tile")
    # each arena must contain >=1 walkable floor tile (else it is fully walled/furnished)
    for a in spec.get("arenas", []):
        x0, y0, x1, y1 = a["rect"]
        floor = sum(
            1
            for yy in range(y0, y1 + 1)
            for xx in range(x0, x1 + 1)
            if not on_wall(xx, yy)
        )
        if floor == 0:
            fails.append(f"arena {a['sector']}:{a['name']} has no walkable floor tile")

    if fails:
        print(f"\nFAILURES ({len(fails)}):")
        for f in fails:
            print("  -", f)
        raise SystemExit(1)
    print("\nALL CHECKS PASSED: addresses resolve, collision clean, objects reachable, "
          f"connectivity {pct:.1f}%, no spawn/room-center on a wall.")


if __name__ == "__main__":
    main()
