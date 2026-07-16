"""Generate the engine's world data from town_spec.json.

Emits, under environment/frontend_server/static_dirs/assets/<world>/matrix/:
  maze_meta_info.json
  maze/{collision,sector,arena,game_object,spawning_location}_maze.csv   (one row each, row-major)
  special_blocks/{world,sector,arena,game_object,spawning_location}_blocks.csv

Collision model (hybrid):
  - Outdoor tiles (no sector): blocked from collision_draft.json (streets walkable; water/trees blocked).
  - Building room floor is walkable unless an object explicitly keeps the default blocking policy.
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


def _validated_collision_overrides(spec, width, height):
    overrides = spec.get("collision_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("collision_overrides must be an object")
    unknown = set(overrides) - {"blocked_regions", "blocked", "walkable"}
    if unknown:
        raise ValueError(f"unknown collision override keys: {sorted(unknown)}")

    def points(label):
        value = overrides.get(label, [])
        if not isinstance(value, list):
            raise ValueError(f"collision_overrides.{label} must be a list")
        result = []
        for point in value:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(not isinstance(item, int) or isinstance(item, bool) for item in point)
            ):
                raise ValueError(f"collision_overrides.{label} contains an invalid point")
            x, y = point
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(f"collision_overrides.{label} point is out of bounds")
            result.append((x, y))
        if len(result) != len(set(result)):
            raise ValueError(f"collision_overrides.{label} contains duplicate points")
        return tuple(result)

    regions = overrides.get("blocked_regions", [])
    if not isinstance(regions, list):
        raise ValueError("collision_overrides.blocked_regions must be a list")
    for rect in regions:
        if (
            not isinstance(rect, list)
            or len(rect) != 4
            or any(not isinstance(item, int) or isinstance(item, bool) for item in rect)
            or not (0 <= rect[0] <= rect[2] < width)
            or not (0 <= rect[1] <= rect[3] < height)
        ):
            raise ValueError("collision_overrides.blocked_regions contains an invalid rect")
    blocked, walkable = points("blocked"), points("walkable")
    if set(blocked) & set(walkable):
        raise ValueError("collision override points cannot be both blocked and walkable")
    return tuple(regions), blocked, walkable


def resolve_world_asset_root(world: str, *, repo_root: Path = REPO_ROOT) -> Path:
    """Resolve one direct world directory strictly beneath the assets root."""
    if (
        not isinstance(world, str)
        or not world
        or world != world.strip()
        or world in (".", "..")
        or "/" in world
        or "\\" in world
        or Path(world).name != world
        or Path(world).is_absolute()
    ):
        raise ValueError("world_name must be a non-empty path-safe leaf name")

    assets_root = (
        repo_root / "environment/frontend_server/static_dirs/assets"
    ).resolve()
    world_root = (assets_root / world.lower()).resolve()
    if world_root.parent != assets_root:
        raise ValueError("resolved world asset root escapes the assets directory")
    return world_root


def resolve_world_asset_path(
    world: str, *parts: str, repo_root: Path = REPO_ROOT
) -> Path:
    """Resolve a contained world asset path, rejecting symlink/path escapes."""
    world_root = resolve_world_asset_root(world, repo_root=repo_root)
    candidate = world_root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(world_root)
    except ValueError as exc:
        raise ValueError("resolved world asset path escapes its world root") from exc
    return candidate


def load_collision_source(
    *,
    world: str,
    width: int,
    height: int,
    collision_block_id: str,
    repo_root: Path = REPO_ROOT,
    draft_path: Path = DRAFT,
) -> list[list[bool]]:
    """Load the draft, or the selected world's existing collision matrix."""
    resolve_world_asset_root(world, repo_root=repo_root)
    if width < 1 or height < 1:
        raise ValueError("maze dimensions must be positive")

    if draft_path.is_file():
        grid = json.loads(draft_path.read_text(encoding="utf-8")).get("grid")
        if (
            not isinstance(grid, list)
            or len(grid) != height
            or any(not isinstance(row, list) or len(row) != width for row in grid)
            or any(cell not in (0, 1, False, True) for row in grid for cell in row)
        ):
            raise SystemExit("collision draft has invalid dimensions or values")
        return [[bool(cell) for cell in row] for row in grid]

    existing_path = resolve_world_asset_path(
        world,
        "matrix",
        "maze",
        "collision_maze.csv",
        repo_root=repo_root,
    )
    if not existing_path.is_file():
        raise SystemExit(
            "collision draft and existing world collision matrix are missing"
        )
    existing = [
        token.strip() for token in existing_path.read_text(encoding="utf-8").split(",")
    ]
    if len(existing) != width * height or any(
        token not in ("0", collision_block_id) for token in existing
    ):
        raise SystemExit("existing collision matrix has invalid dimensions or tokens")
    return [
        [existing[y * width + x] != "0" for x in range(width)] for y in range(height)
    ]


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
                        if (
                            0 <= nx < W
                            and 0 <= ny < H
                            and walk(nx, ny)
                            and comp[ny][nx] == -1
                        ):
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
        for x, y in tiles:
            for mx, my in main_set:
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
    overrides_path = spec_path.with_name(f"{spec_path.stem}.collisions.json")
    override_spec = dict(spec)
    if overrides_path.is_file():
        if "collision_overrides" in spec:
            raise ValueError("collision overrides must have exactly one source")
        override_spec["collision_overrides"] = json.loads(
            overrides_path.read_text(encoding="utf-8")
        )
    world = spec["world_name"]
    W = spec["grid"]["maze_width"]
    H = spec["grid"]["maze_height"]
    sq = spec["grid"]["sq_tile_size"]
    cbid = str(spec.get("collision_block_id", "32125"))
    collision_overrides = _validated_collision_overrides(override_spec, W, H)

    # Resolve every output before loading collision input or writing anything.
    out = resolve_world_asset_path(world, "matrix")
    maze_out = resolve_world_asset_path(world, "matrix", "maze")
    blocks_out = resolve_world_asset_path(world, "matrix", "special_blocks")
    meta_out = resolve_world_asset_path(world, "matrix", "maze_meta_info.json")
    matrix_outputs = {
        name: resolve_world_asset_path(world, "matrix", "maze", f"{name}_maze.csv")
        for name in ("collision", "sector", "arena", "game_object", "spawning_location")
    }
    legend_outputs = {
        name: resolve_world_asset_path(
            world, "matrix", "special_blocks", f"{name}_blocks.csv"
        )
        for name in ("world", "sector", "arena", "game_object", "spawning_location")
    }

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
    draft = load_collision_source(
        world=world,
        width=W,
        height=H,
        collision_block_id=cbid,
    )
    for y in range(H):
        for x in range(W):
            if sector_g[y][x] == 0:  # outdoor
                if draft[y][x]:
                    collision[y][x] = cbid
            else:  # inside a building footprint
                if arena_g[y][x] == 0:
                    collision[y][x] = cbid  # wall (no arena)
                # else: room floor -> walkable (stays "0")

    # --- objects: stamp ids + mark furniture (blocked, must be inside an arena) ---
    for o in spec.get("objects", []):
        oid = object_ids[o["type"]]
        blocks = o.get("blocks", True)
        if not isinstance(blocks, bool):
            errors.append(f"object {o['type']} has a non-boolean blocks policy")
            continue
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
            if blocks:
                collision[y][x] = cbid  # Furniture blocks pathing, not sight.

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

    # Authoritative visual overrides run after auto-connect so the connectivity
    # helper cannot carve through visible walls or furniture. Explicit walkable
    # points are applied last for doors, crossings, and unrendered placeholders.
    blocked_regions, blocked_points, walkable_points = collision_overrides
    for rect in blocked_regions:
        _fill(collision, rect, cbid)
    for x, y in blocked_points:
        collision[y][x] = cbid
    for x, y in walkable_points:
        collision[y][x] = "0"

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
    maze_out.mkdir(parents=True, exist_ok=True)
    blocks_out.mkdir(parents=True, exist_ok=True)

    meta_info = {
        "world_name": world,
        "maze_width": W,
        "maze_height": H,
        "sq_tile_size": sq,
        "collision_block_id": cbid,
        "special_constraint": "",
    }
    if "address_alias_manifest" in spec:
        meta_info["address_alias_manifest"] = spec["address_alias_manifest"]
    meta_out.write_text(json.dumps(meta_info, indent=2))

    def write_matrix(name, grid):
        flat = ", ".join(str(grid[y][x]) for y in range(H) for x in range(W))
        matrix_outputs[name].write_text(flat)

    write_matrix("collision", collision)
    write_matrix("sector", sector_g)
    write_matrix("arena", arena_g)
    write_matrix("game_object", object_g)
    write_matrix("spawning_location", spawn_g)

    def write_legend(name, rows):
        legend_outputs[name].write_text(
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
                "out": str(out.relative_to(REPO_ROOT.resolve())),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
