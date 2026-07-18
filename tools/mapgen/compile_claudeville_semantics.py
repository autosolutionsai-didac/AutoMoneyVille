"""Compile Claudeville navigation semantics from the final authored Tiled map."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

try:
    from tools.mapgen import claudeville_home_semantics as home_semantics
    from tools.mapgen import claudeville_semantic_graph as semantic_graph
    from tools.mapgen import claudeville_semantic_io as semantic_io
    from tools.mapgen import claudeville_tiled_authoring as tiled_authoring
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_home_semantics as home_semantics  # type: ignore[no-redef]
    import claudeville_semantic_graph as semantic_graph  # type: ignore[no-redef]
    import claudeville_semantic_io as semantic_io  # type: ignore[no-redef]
    import claudeville_tiled_authoring as tiled_authoring  # type: ignore[no-redef]

SemanticCompileError = semantic_io.SemanticCompileError
_atomic_json = semantic_io.atomic_json
_point = semantic_io.logical_point
_read_json = semantic_io.read_json

try:
    from tools.mapgen import claudeville_purpose_layouts as purpose_layouts
except ModuleNotFoundError:
    try:
        import claudeville_purpose_layouts as purpose_layouts  # type: ignore[no-redef]
    except ModuleNotFoundError:
        purpose_layouts = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[2]
MAPGEN_ROOT = Path(__file__).resolve().parent
WORLD_ROOT = REPO_ROOT / "environment/frontend_server/static_dirs/assets/claudeville"
TMJ_PATH = WORLD_ROOT / "visuals/claudeville_target_v45.tmj"
SPEC_PATH = MAPGEN_ROOT / "town_spec.json"
OVERRIDES_PATH = MAPGEN_ROOT / "town_spec.collisions.json"
COLLISION_PATH = WORLD_ROOT / "matrix/maze/collision_maze.csv"
OLD_MAP_PATH = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/the_ville/visuals"
    / "the_ville_jan7.json"
)
VISUAL_WIDTH, VISUAL_HEIGHT = 176, 96
LOGICAL_WIDTH, LOGICAL_HEIGHT = 88, 48
VISIBLE_BLOCKER_LAYERS = (
    "Wall",
    "Interior Furniture L1",
    "Interior Furniture L2",
    "Foreground L1",
    "Foreground L2",
)
PLAZA_OBJECTS = (
    ("fountain", ((39, 27),), (39, 28)),
    ("bench", ((35, 23),), None),
    ("notice board", ((44, 22),), None),
)
PLAZA_SPAWN = (39, 29)

Point = tuple[int, int]


@dataclass(frozen=True)
class Compilation:
    """Validated, deterministic semantic outputs; no filesystem writes occur."""

    town_spec: dict
    collision_overrides: dict
    collision: tuple[tuple[bool, ...], ...]
    object_stances: tuple[Point, ...]
    stats: dict[str, int | float]


def _layers(tmj: dict) -> dict[str, dict]:
    dimensions = (
        tmj.get("width"),
        tmj.get("height"),
        tmj.get("tilewidth"),
        tmj.get("tileheight"),
    )
    if dimensions != (VISUAL_WIDTH, VISUAL_HEIGHT, 16, 16):
        raise SemanticCompileError("Claudeville TMJ must remain 176x96 at 16px")
    layers = {
        layer.get("name"): layer
        for layer in tmj.get("layers", [])
        if isinstance(layer, dict) and isinstance(layer.get("name"), str)
    }
    required = {"Interior Ground", "Exterior Ground", *VISIBLE_BLOCKER_LAYERS}
    if not required <= layers.keys():
        raise SemanticCompileError("TMJ is missing required semantic visual layers")
    for name in required:
        if (
            not isinstance(layers[name].get("data"), list)
            or len(layers[name]["data"]) != 16896
        ):
            raise SemanticCompileError(f"TMJ layer {name} has invalid tile data")
    return layers


def compile_semantics(
    *,
    tmj_path: Path = TMJ_PATH,
    spec_path: Path = SPEC_PATH,
    overrides_path: Path = OVERRIDES_PATH,
    collision_path: Path = COLLISION_PATH,
    old_map_path: Path = OLD_MAP_PATH,
    layout: ModuleType | None = None,
) -> Compilation:
    """Return validated semantic payloads without writing any project files."""
    tmj, spec = _read_json(tmj_path), _read_json(spec_path)
    if tiled_authoring.is_tiled_first(tmj):
        try:
            collision = semantic_graph.read_collision(collision_path)
            result = tiled_authoring.compile_authoring(tmj, spec, collision)
        except (semantic_graph.SemanticGraphError, tiled_authoring.TiledAuthoringError) as exc:
            raise SemanticCompileError(str(exc)) from exc
        return Compilation(
            result.town_spec, result.collision_overrides, result.collision,
            result.object_stances, result.stats,
        )
    layout = purpose_layouts if layout is None else layout
    if layout is None:
        raise SemanticCompileError("claudeville_purpose_layouts.py is required")
    overrides, old_map = _read_json(overrides_path), _read_json(old_map_path)
    layers = _layers(tmj)
    try:
        sectors = semantic_graph.sector_cells(spec)
        prop_art = semantic_graph.prop_cells(layout)
        prop_blocks = semantic_graph.prop_cells(layout, blocked_only=True)
        depth_blocks = semantic_graph.depth_prop_blocks(tmj)
    except semantic_graph.SemanticGraphError as exc:
        raise SemanticCompileError(str(exc)) from exc
    active_homes = set(home_semantics.HOME_ENTRANCES) & set(sectors)
    try:
        zone_cells, owners, clear_floor = home_semantics.partition_public_zones(
            layers, layout, sectors
        )
        homes = home_semantics.derive_home_semantics(
            layers, layout, active_sectors=active_homes, sector_cells=sectors
        )
    except home_semantics.HomeSemanticError as exc:
        raise SemanticCompileError(str(exc)) from exc
    zone_cells.update({name: set(cells) for name, cells in homes.zones.items()})
    owners.update(homes.owners)
    clear_floor |= set().union(*(set(cells) for cells in homes.zones.values()))
    if "Central Plaza" in sectors:
        zone_cells["plaza"], owners["plaza"] = (
            set(sectors["Central Plaza"]),
            "Central Plaza",
        )

    objects: list[dict] = []
    object_records: list[tuple[str, str, str, tuple[Point, ...], Point | None]] = []
    object_blocks: set[Point] = set()

    def add_object(sector: str, zone: str, kind: str, values, stance=None) -> None:
        points = tuple(_point(value, f"{sector}:{kind} object") for value in values)
        if (
            owners.get(zone) != sector
            or not points
            or any(point not in zone_cells[zone] for point in points)
        ):
            raise SemanticCompileError(f"object {sector}:{kind} is outside zone floor")
        invisible = (
            set()
            if sector == "Central Plaza"
            else {
                point
                for point in points
                if not any(
                    abs(point[0] - art[0]) + abs(point[1] - art[1]) <= 1
                    for art in prop_art
                )
                and not semantic_graph.has_visible_object_art(
                    layers, VISIBLE_BLOCKER_LAYERS, point
                )
            }
        )
        if invisible:
            raise SemanticCompileError(
                f"object {sector}:{kind} has no visible art at {sorted(invisible)}"
            )
        duplicate = object_blocks & set(points)
        if duplicate:
            raise SemanticCompileError(
                f"semantic objects overlap at {sorted(duplicate)}"
            )
        object_blocks.update(points)
        object_records.append((sector, zone, kind, points, stance))
        objects.append(
            {
                "sector": sector,
                "arena": zone,
                "type": kind,
                "tiles": [list(point) for point in points],
            }
        )

    for sector, entries in layout.SEMANTIC_OBJECTS.items():
        for entry in entries:
            add_object(sector, entry.zone, entry.type, entry.logical_tiles)
    for sector, entries in homes.objects.items():
        for entry in entries:
            add_object(sector, entry.zone, entry.type, entry.logical_tiles)
    if "Central Plaza" in sectors:
        for kind, points, stance in PLAZA_OBJECTS:
            add_object("Central Plaza", "plaza", kind, points, stance)

    try:
        old_blocks = home_semantics.old_stamp_blocks(
            layers, old_map, layout, VISIBLE_BLOCKER_LAYERS
        )
        atlas_blocks = home_semantics.atlas_blocks(layers, layout)
    except home_semantics.HomeSemanticError as exc:
        raise SemanticCompileError(str(exc)) from exc
    visible_blocks = (
        old_blocks | atlas_blocks | prop_blocks | depth_blocks | object_blocks
    )
    try:
        authored_blocked = semantic_graph.authored_block_cells(layout)
    except semantic_graph.SemanticGraphError as exc:
        raise SemanticCompileError(str(exc)) from exc
    walkable_recipe = getattr(layout, "authored_walkable_cells", None)
    authored_walkable = (
        walkable_recipe(layers, visible_blocks | authored_blocked)
        if walkable_recipe
        else set()
    )
    try:
        base = semantic_graph.read_collision(collision_path)
    except semantic_graph.SemanticGraphError as exc:
        raise SemanticCompileError(str(exc)) from exc
    collision = [row[:] for row in base]
    for sector, cells in sectors.items():
        if sector != "Central Plaza":
            for x, y in cells:
                collision[y][x] = True
    for zone, cells in zone_cells.items():
        if zone != "plaza":
            for x, y in cells:
                collision[y][x] = False
    for x, y in visible_blocks:
        collision[y][x] = True

    try:
        regions, preserved_blocked, preserved_walkable = (
            semantic_graph.preserved_points(overrides, sectors)
        )
        preserved_blocked |= authored_blocked
        preserved_walkable -= authored_blocked
    except semantic_graph.SemanticGraphError as exc:
        raise SemanticCompileError(str(exc)) from exc
    if "Central Plaza" in sectors:
        preserved_blocked |= {(x, y) for x, y in sectors["Central Plaza"] if base[y][x]}
    for x0, y0, x1, y1 in regions:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                collision[y][x] = True
    for x, y in preserved_blocked:
        collision[y][x] = True

    entrances = {
        sector: _point(value, f"{sector} entrance")
        for sector, value in layout.ENTRANCES.items()
    }
    entrances.update(homes.entrances)
    bad_doors = (set(entrances.values()) & visible_blocks) | {
        point
        for point in entrances.values()
        if semantic_graph.has_tile(layers, ("Wall",), point)
    }
    if bad_doors:
        raise SemanticCompileError(
            f"entrance overlaps a visible blocker: {sorted(bad_doors)}"
        )
    bad_overrides = preserved_walkable & visible_blocks
    if bad_overrides:
        raise SemanticCompileError(
            f"walkable override overlaps a blocker: {sorted(bad_overrides)}"
        )
    for x, y in preserved_walkable | authored_walkable | set(entrances.values()):
        collision[y][x] = False

    spawn_points = {
        sector: _point(value, f"{sector} spawn")
        for sector, value in layout.SPAWNS.items()
    }
    if "Central Plaza" in sectors:
        spawn_points["Central Plaza"] = PLAZA_SPAWN
    provisional_labels, _ = semantic_graph.components(collision)
    for sector, entrance in homes.entrances.items():
        candidates = (
            *homes.spawn_candidates[sector],
            *homes.preferred_spawn_cells[sector],
        )
        spawn = next(
            (
                point
                for point in dict.fromkeys(candidates)
                if not collision[point[1]][point[0]]
                and provisional_labels.get(point) == provisional_labels.get(entrance)
            ),
            None,
        )
        if spawn is None:
            raise SemanticCompileError(
                f"{sector} has no clear spawn connected to its entrance"
            )
        spawn_points[sector] = spawn

    for sector, point in spawn_points.items():
        matches = [
            zone
            for zone, cells in zone_cells.items()
            if owners[zone] == sector and point in cells
        ]
        if len(matches) != 1 or collision[point[1]][point[0]]:
            raise SemanticCompileError(
                f"spawn for {sector} is blocked or not in one zone"
            )

    stances, stance_failures = semantic_graph.select_object_stances(
        object_records, zone_cells, owners, collision
    )
    if stance_failures:
        details = json.dumps(stance_failures, separators=(",", ":"))
        raise SemanticCompileError(f"objects have no radius-1 stance: {details}")

    explicit = set(entrances.values()) | set(spawn_points.values()) | set(stances)
    blocked_explicit = {point for point in explicit if collision[point[1]][point[0]]}
    if blocked_explicit:
        raise SemanticCompileError(
            f"spawn, entrance or stance is blocked: {sorted(blocked_explicit)}"
        )
    walkable = preserved_walkable | authored_walkable | explicit
    blocked = (preserved_blocked | visible_blocks) - walkable
    invisible = {
        point
        for point in clear_floor
        if collision[point[1]][point[0]] and point not in visible_blocks
    }
    if invisible:
        raise SemanticCompileError(
            f"clear interior floor is invisibly blocked: {sorted(invisible)[:12]}"
        )
    sealed_zones = sorted(
        zone
        for zone, cells in zone_cells.items()
        if not any(not collision[y][x] for x, y in cells)
    )
    if sealed_zones:
        raise SemanticCompileError(f"zones have no walkable floor: {sealed_zones}")

    labels, sizes = semantic_graph.components(collision)
    walkable_count = sum(sizes)
    connectivity = 100.0 * max(sizes, default=0) / max(1, walkable_count)
    main_component = sizes.index(max(sizes)) if sizes else -1
    named_explicit = [
        *((f"entrance:{sector}", point) for sector, point in entrances.items()),
        *((f"spawn:{sector}", point) for sector, point in spawn_points.items()),
        *(
            (f"stance:{record[0]}:{record[2]}", point)
            for record, point in zip(object_records, stances, strict=True)
        ),
    ]
    disconnected = sorted(
        (name, point, sizes[labels[point]])
        for name, point in named_explicit
        if labels.get(point) != main_component
    )
    if disconnected:
        raise SemanticCompileError(
            f"door, spawn or stance is disconnected: {disconnected}"
        )
    if connectivity < 98.0:
        raise SemanticCompileError(
            f"walkable connectivity {connectivity:.1f}% is below 98%"
        )

    arenas = [
        {
            "sector": owners[zone],
            "name": zone,
            "rects": semantic_graph.compress(cells),
        }
        for zone, cells in sorted(
            zone_cells.items(), key=lambda item: (owners[item[0]], item[0])
        )
    ]
    spawns = []
    old_spawn_names = {
        entry["sector"]: entry["name"] for entry in spec.get("spawns", [])
    }
    for sector, point in sorted(spawn_points.items()):
        matches = [
            zone
            for zone, cells in zone_cells.items()
            if owners[zone] == sector and point in cells
        ]
        spawns.append(
            {
                "sector": sector,
                "arena": matches[0],
                "name": old_spawn_names.get(sector, "sp"),
                "tile": list(point),
            }
        )

    output_spec = deepcopy(spec)
    output_spec.update(
        {
            "_generated_by": "compile_claudeville_semantics.py",
            "auto_connect": False,
            "arenas": arenas,
            "objects": sorted(
                objects, key=lambda item: (item["sector"], item["arena"], item["type"])
            ),
            "spawns": spawns,
            "entrances": [
                {"sector": sector, "tile": list(point)}
                for sector, point in sorted(entrances.items())
            ],
            "required_zones": [
                {"sector": owners[zone], "arena": zone} for zone in sorted(zone_cells)
            ],
        }
    )
    output_overrides = {
        "blocked_regions": regions,
        "blocked": [
            list(point) for point in sorted(blocked, key=lambda p: (p[1], p[0]))
        ],
        "walkable": [
            list(point) for point in sorted(walkable, key=lambda p: (p[1], p[0]))
        ],
    }
    stats: dict[str, int | float] = {
        "zones": len(zone_cells),
        "objects": len(objects),
        "blockers": len(visible_blocks),
        "authored_walkable": len(authored_walkable),
        "stances": len(stances),
        "walkable": walkable_count,
        "connectivity_pct": round(connectivity, 3),
    }
    return Compilation(
        output_spec,
        output_overrides,
        tuple(tuple(row) for row in collision),
        tuple(stances),
        stats,
    )


def write_compilation(
    compilation: Compilation, spec_output: Path, overrides_output: Path
) -> None:
    """Atomically write an already validated compilation to explicit paths."""
    _atomic_json(spec_output, compilation.town_spec)
    _atomic_json(overrides_output, compilation.collision_overrides)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tmj", type=Path, default=TMJ_PATH)
    parser.add_argument("--spec", type=Path, default=SPEC_PATH)
    parser.add_argument("--overrides", type=Path, default=OVERRIDES_PATH)
    parser.add_argument("--collision", type=Path, default=COLLISION_PATH)
    parser.add_argument("--old-map", type=Path, default=OLD_MAP_PATH)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--spec-output", type=Path, default=SPEC_PATH)
    parser.add_argument("--overrides-output", type=Path, default=OVERRIDES_PATH)
    args = parser.parse_args()
    result = compile_semantics(
        tmj_path=args.tmj,
        spec_path=args.spec,
        overrides_path=args.overrides,
        collision_path=args.collision,
        old_map_path=args.old_map,
    )
    if args.write:
        write_compilation(result, args.spec_output, args.overrides_output)
    print(json.dumps(result.stats, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
