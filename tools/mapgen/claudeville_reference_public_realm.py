"""Deterministic native-16 public realm traced from ``claudeville_bg.png``.

The module contains no Tiled global IDs.  Tile painters receive a resolver for
stable curated asset keys, while prop placements use the existing V2 catalog
keys consumed by the reference authoring pipeline.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

try:
    from tools.mapgen import claudeville_reference_civic_landscape as civic_landscape
    from tools.mapgen import claudeville_reference_layout as layout
    from tools.mapgen import claudeville_reference_public_support as public_support
except ModuleNotFoundError:  # Direct module execution.
    import claudeville_reference_civic_landscape as civic_landscape
    import claudeville_reference_layout as layout
    import claudeville_reference_public_support as public_support


WIDTH = layout.VISUAL_WIDTH
HEIGHT = layout.VISUAL_HEIGHT
TILE_COUNT = WIDTH * HEIGHT
TileCell = tuple[int, int, str]
Placement = tuple[str, str, str, str, str, int, int]

# Stable curated tile keys.  The water rings are the exact source tiles that
# the earlier proof encoded as fragile map-local GIDs 78..228.
# The theme sheet contains a genuinely seamless grass cell at (48, 128).
# The older selection sampled shoreline transition cells, whose three brown
# edge pixels became an obvious diagonal confetti pattern over the whole map.
GRASS_TILES = (
    *("tile.exteriors_terrain.0048.0128" for _ in range(12)),
    *("tile.exteriors_terrain.0048.0096" for _ in range(3)),
    *("tile.exteriors_terrain.0064.0096" for _ in range(3)),
    *("tile.exteriors_terrain.0048.0112" for _ in range(2)),
    "tile.exteriors_terrain.0064.0112",
)
GRASS = GRASS_TILES[0]
WARM_STONE_TILES = tuple(
    tuple(f"tile.exteriors_city.{x:04d}.{y:04d}" for x in (144, 160, 176, 192))
    for y in (368, 384, 400, 416)
)
LIGHT_WATER = "tile.exteriors_terrain.0320.0128"
DEEP_WATER = "tile.exteriors_terrain.0272.0192"
SHORE = {
    "tl": "tile.exteriors_terrain.0256.0096",
    "t": "tile.exteriors_terrain.0272.0096",
    "tr": "tile.exteriors_terrain.0288.0096",
    "r": "tile.exteriors_terrain.0288.0112",
    "br": "tile.exteriors_terrain.0288.0128",
    "b": "tile.exteriors_terrain.0272.0128",
    "bl": "tile.exteriors_terrain.0256.0128",
    "l": "tile.exteriors_terrain.0256.0112",
}
DEEP_EDGE = {
    "tl": "tile.exteriors_terrain.0256.0176",
    "t": "tile.exteriors_terrain.0272.0176",
    "tr": "tile.exteriors_terrain.0288.0176",
    "r": "tile.exteriors_terrain.0288.0192",
    "br": "tile.exteriors_terrain.0288.0208",
    "b": "tile.exteriors_terrain.0272.0208",
    "bl": "tile.exteriors_terrain.0256.0208",
    "l": "tile.exteriors_terrain.0256.0192",
}
TILE_ASSET_KEYS = frozenset({*GRASS_TILES, LIGHT_WATER, DEEP_WATER}) | frozenset(
    key for row in WARM_STONE_TILES for key in row
) | frozenset(
    SHORE.values()
) | frozenset(DEEP_EDGE.values())

TREE_KEYS = (
    "prop.landscape.conifer_tall_01",
    "prop.landscape.conifer_tall_02",
    "prop.landscape.conifer_tall_03",
)
PLAZA_PLANT_KEYS = (
    "prop.landscape.tree_cluster_15",
    *(f"prop.landscape.flower_bush_0{number}" for number in (1, 3, 5, 7)),
)
FOREST_WALL_KEYS = (
    ("prop.landscape.forest_wall_back_left",
     "prop.landscape.forest_wall_back_center",
     "prop.landscape.forest_wall_back_right"),
    ("prop.landscape.forest_wall_mid_left",
     "prop.landscape.forest_wall_mid_center",
     "prop.landscape.forest_wall_mid_right"),
    ("prop.landscape.forest_wall_front_left",
     "prop.landscape.forest_wall_front_center",
     "prop.landscape.forest_wall_front_right"),
)
HEDGE_KEYS = (
    "prop.landscape.hedge_flowered_left",
    "prop.landscape.hedge_flowered_middle",
    "prop.landscape.hedge_flowered_right",
)
VERTICAL_HEDGE_KEYS = (
    "prop.landscape.hedge_flowered_vertical_top",
    "prop.landscape.hedge_flowered_vertical_mid",
    "prop.landscape.hedge_flowered_vertical_mid_alt",
    "prop.landscape.hedge_flowered_vertical_bottom",
)
BENCH = "prop.garden.bench_horizontal"
LAMP = "prop.street.lamp_05"
FOUNTAIN = "prop.plaza.fountain_round_blue"
NOTICE_BOARD = "prop.office.notice_board"
PROP_ASSET_KEYS = frozenset(
    (*TREE_KEYS, *PLAZA_PLANT_KEYS, *(key for row in FOREST_WALL_KEYS for key in row),
     *HEDGE_KEYS, *VERTICAL_HEDGE_KEYS, BENCH, LAMP, FOUNTAIN, NOTICE_BOARD)
)
REQUIRED_ASSET_KEYS = TILE_ASSET_KEYS | PROP_ASSET_KEYS

WATER_RUNS = {row: tuple(runs) for row, runs in layout.WATER_RUNS.items()}
AVENUE_RECTS = ((18, 37, 176, 43), (18, 73, 176, 79))
VERTICAL_CONNECTOR_RECTS = tuple(
    rect for rect in layout.MAIN_PATHS if rect not in AVENUE_RECTS
)
ENTRY_PATH_RECTS = tuple(
    record["entry"] for record in layout.BUILDINGS.values() if "entry" in record
)
PUBLIC_PATH_RECTS = (
    *layout.MAIN_PATHS,
    *layout.PARCEL_PATHS,
    *layout.SOUTH_PATHS,
    *ENTRY_PATH_RECTS,
)
PLAZA_PARCEL = layout.PLAZA["parcel"]
PLAZA_BED_POLYGONS = tuple(tuple(points) for points in layout.PLAZA["quadrants"])


def _rect_frame(rect: tuple[int, int, int, int]) -> set[tuple[int, int]]:
    """Return the one-cell civic walk that frames a traced parcel."""
    left, top, right, bottom = rect
    return (
        {(x, top) for x in range(left, right)}
        | {(x, bottom - 1) for x in range(left, right)}
        | {(left, y) for y in range(top + 1, bottom - 1)}
        | {(right - 1, y) for y in range(top + 1, bottom - 1)}
    )

SECTOR_ZONE = {
    "Bank": "bank.waiting",
    "Home 1": "home_1.garden",
    "University": "university.cafeteria",
    "Agent Academy": "academy.reception",
    "Market": "market.retail",
    "Workshop": "workshop.intake",
    "Community Center": "community.lounge",
    "Claudeville Cafe": "cafe.terrace",
    "Central Plaza": "plaza",
    "Library": "library.reading",
    "Post Office": "post.waiting",
    "Home 2": "home_2.main_room",
    "Home 3": "home_3.main_room",
    "Home 4": "home_4.main_room",
    "Home 5": "home_5.garden",
    "Home 6": "home_6.garden",
    "Town Hall": "hall.public_service",
    "Home 7": "home_7.garden",
    "Home 8": "home_8.garden",
    "Home 9": "home_9.garden",
    "Home 10": "home_10.garden",
}


def _rect_cells(rect: tuple[int, int, int, int]) -> Iterator[tuple[int, int]]:
    left, top, right, bottom = rect
    for y in range(top, bottom):
        for x in range(left, right):
            yield x, y


def _polygon_cells(points: tuple[tuple[int, int], ...]) -> set[tuple[int, int]]:
    """Return cells whose centres fall inside an orthogonal Tiled polygon."""
    min_x, max_x = min(x for x, _ in points), max(x for x, _ in points)
    min_y, max_y = min(y for _, y in points), max(y for _, y in points)
    cells: set[tuple[int, int]] = set()
    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            px, py = x + 0.5, y + 0.5
            inside = False
            previous = points[-1]
            for current in points:
                x1, y1 = previous
                x2, y2 = current
                if (y1 > py) != (y2 > py):
                    crossing = (x2 - x1) * (py - y1) / (y2 - y1) + x1
                    if px < crossing:
                        inside = not inside
                previous = current
            if inside:
                cells.add((x, y))
    return cells


PLANTING_BED_CELLS = frozenset(
    cell for polygon in PLAZA_BED_POLYGONS for cell in _polygon_cells(polygon)
)
PLAZA_PATH_CELLS = frozenset(_rect_cells(PLAZA_PARCEL)) - PLANTING_BED_CELLS
# The supplied target frames each compound with one narrow civic walk.  A
# single native tile keeps those parcels legible without recreating the broad,
# road-like bands from the rejected procedural version.
PARCEL_FRAME_CELLS = frozenset(
    cell
    for rect in {tuple(record["parcel"]) for record in layout.BUILDINGS.values()}
    for cell in _rect_frame(rect)
)
WATER_CELLS = frozenset(
    (x, row)
    for row, runs in WATER_RUNS.items()
    for left, right in runs
    for x in range(left, right)
)
PUBLIC_PATH_CELLS = (
    frozenset(cell for rect in PUBLIC_PATH_RECTS for cell in _rect_cells(rect))
    | PARCEL_FRAME_CELLS
    | PLAZA_PATH_CELLS
) - PLANTING_BED_CELLS - WATER_CELLS
# Keep the newly exposed grass shoulders clear of trees and hedges.  They are
# visual lawns/sidewalk verges, not extra buildable or forest space.
PROP_EXCLUSION_CELLS = PUBLIC_PATH_CELLS | frozenset(
    cell
    for rect in ((18, 36, 176, 45), (18, 72, 176, 80),
                 (56, 0, 63, 96), (137, 0, 143, 96))
    for cell in _rect_cells(rect)
)


def _edge_key(directions: set[str], tiles: dict[str, str], fallback: str) -> str:
    for corner, sides in (
        ("tl", {"t", "l"}),
        ("tr", {"t", "r"}),
        ("br", {"b", "r"}),
        ("bl", {"b", "l"}),
    ):
        if sides <= directions:
            return tiles[corner]
    for side in ("t", "r", "b", "l"):
        if side in directions:
            return tiles[side]
    return fallback


def water_tile_plan() -> dict[tuple[int, int], str]:
    """Resolve the complete traced water mask into two native transition rings."""
    offsets = {"t": (0, -1), "r": (1, 0), "b": (0, 1), "l": (-1, 0)}

    def is_water(x: int, y: int) -> bool:
        return not (0 <= x < WIDTH and 0 <= y < HEIGHT) or (x, y) in WATER_CELLS

    boundary: dict[tuple[int, int], set[str]] = {}
    for x, y in WATER_CELLS:
        land = {
            side
            for side, (dx, dy) in offsets.items()
            if not is_water(x + dx, y + dy)
        }
        if land:
            boundary[(x, y)] = land
    result: dict[tuple[int, int], str] = {}
    for x, y in sorted(WATER_CELLS, key=lambda point: (point[1], point[0])):
        if (x, y) in boundary:
            result[(x, y)] = _edge_key(boundary[(x, y)], SHORE, LIGHT_WATER)
            continue
        toward_shore = {
            side
            for side, (dx, dy) in offsets.items()
            if (x + dx, y + dy) in boundary
        }
        result[(x, y)] = _edge_key(toward_shore, DEEP_EDGE, DEEP_WATER)
    return result


def iter_bottom_tiles() -> Iterator[TileCell]:
    """Yield a complete grass-and-water Bottom Ground plan in row order."""
    water = water_tile_plan()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            grass_index = (x * 17 + y * 31 + x * y * 7) % len(GRASS_TILES)
            yield x, y, water.get((x, y), GRASS_TILES[grass_index])


def iter_public_ground_tiles() -> Iterator[TileCell]:
    """Yield warm-stone avenues, connectors, entrances, and plaza circulation."""
    for x, y in sorted(PUBLIC_PATH_CELLS, key=lambda point: (point[1], point[0])):
        yield x, y, WARM_STONE_TILES[y % 4][x % 4]


def paint_public_realm(
    bottom: list[int], exterior: list[int], resolve_key: Callable[[str], int]
) -> None:
    """Paint public-realm tiles using a caller-owned stable-key-to-GID resolver."""
    if len(bottom) != TILE_COUNT or len(exterior) != TILE_COUNT:
        raise ValueError(f"public realm layers must contain {TILE_COUNT} cells")
    resolved = {key: resolve_key(key) for key in TILE_ASSET_KEYS}
    for x, y, key in iter_bottom_tiles():
        bottom[y * WIDTH + x] = resolved[key]
    for x, y, key in iter_public_ground_tiles():
        exterior[y * WIDTH + x] = resolved[key]


def _inside(point: tuple[int, int], rect: tuple[int, int, int, int]) -> bool:
    x, y = point
    left, top, right, bottom = rect
    return left <= x < right and top <= y < bottom


def _structure_rects() -> tuple[tuple[int, int, int, int], ...]:
    result = []
    for record in layout.BUILDINGS.values():
        # Shared-compound followers contribute semantic subrooms but do not
        # create a second physical shell or facade.
        if not record.get("paint_shell", True):
            continue
        for name in ("room", "facade", "entry"):
            if name in record:
                result.append(record[name])
        result.extend(record.get("room_union", ()))
        result.extend(record.get("facade_union", ()))
    return tuple(result)


STRUCTURE_RECTS = _structure_rects()


def _owner(x: int, y: int) -> str:
    if y < 43:
        boundaries = ((56, "Bank"), (94, "Home 1"), (137, "University"),
                      (WIDTH + 1, "Market"))
    elif y < 79:
        boundaries = ((56, "Workshop"), (95, "Community Center"),
                      (137, "Central Plaza"), (WIDTH + 1, "Library"))
    else:
        boundaries = ((39, "Home 2"), (56, "Home 3"), (75, "Home 4"),
                      (83, "Home 5"), (95, "Home 6"),
                      (117, "Town Hall"), (128, "Home 7"),
                      (137, "Home 8"), (150, "Home 9"),
                      (WIDTH + 1, "Home 10"))
    return next(sector for right, sector in boundaries if x < right)


def _forest_candidates() -> tuple[tuple[str, int, int], ...]:
    """Concentrate woodland at both edges and along the broken north shore."""
    points: list[tuple[str, int, int]] = []
    for column, start in ((1, 3), (4, 5), (7, 2), (10, 6), (13, 4), (16, 7)):
        for index, y in enumerate(range(start, HEIGHT - 2, 3)):
            points.append(("west forest belt", column + index % 2, y))
    for column, start in (
        (159, 7), (162, 4), (165, 6), (168, 2), (171, 5), (174, 3),
    ):
        for index, y in enumerate(range(start, HEIGHT - 2, 3)):
            points.append(("east forest belt", column - index % 2, y))
    north_land_masses = ((1, 18), (54, 64), (92, 99), (133, 145), (169, 176))
    north_y = (2, 5, 8, 3, 7)
    for mass_index, (left, right) in enumerate(north_land_masses):
        for index, x in enumerate(range(left, right, 2)):
            points.append((
                "north shore canopy", x,
                north_y[(index + mass_index) % len(north_y)],
            ))
    # Extra irregular points keep the planted belt from reading as a grid.
    for x, y in (
        (161, 4), (166, 7), (171, 12), (163, 20), (169, 27),
        (161, 47), (168, 53), (163, 61),
    ):
        points.append(("east shore cluster", x, y))
    return tuple(points)


def _perimeter_placements() -> tuple[Placement, ...]:
    placements: list[Placement] = []
    occupied: set[tuple[int, int]] = set()
    for index, (cluster, x, y) in enumerate(_forest_candidates()):
        point = (x, y)
        if (
            point in occupied
            or point in FOREST_WALL_POINTS
            or point in FOUNDATION_POINTS
            or point in WATER_CELLS
            or point in PROP_EXCLUSION_CELLS
            or any(_inside(point, rect) for rect in STRUCTURE_RECTS)
        ):
            continue
        sector = _owner(x, y)
        key = TREE_KEYS[(index + x + 2 * y) % len(TREE_KEYS)]
        placements.append(
            (sector, SECTOR_ZONE[sector], "perimeter-tree", cluster, key, x, y)
        )
        occupied.add(point)
    return tuple(placements)


def _forest_wall_placements() -> tuple[Placement, ...]:
    """Join vendor forest modules into a dense west-side woodland mass."""
    result: list[Placement] = []
    forest_runs = ((0, 18), (158, 176))
    for row, (keys, y) in enumerate(zip(FOREST_WALL_KEYS, (8, 11, 14))):
        for left, right in forest_runs:
            points = [(left + 2, keys[0]), (right - 2, keys[2])]
            points.extend((x, keys[1]) for x in range(left + 7, right - 5, 7))
            for x, key in points:
                point = (x, y)
                if (
                    point in WATER_CELLS
                    or point in PROP_EXCLUSION_CELLS
                    or any(_inside(point, rect) for rect in STRUCTURE_RECTS)
                ):
                    continue
                sector = _owner(x, y)
                result.append((sector, SECTOR_ZONE[sector], "forest-wall",
                               f"north forest layer {row + 1}", key, x, y))
    return tuple(result)


def _contiguous(values: list[int]) -> Iterator[list[int]]:
    if not values:
        return
    run = [values[0]]
    for value in values[1:]:
        if value == run[-1] + 1:
            run.append(value)
        else:
            yield run
            run = [value]
    yield run


def _foundation_placements() -> tuple[Placement, ...]:
    result: list[Placement] = []
    extra_gaps = {"University": set(range(124, 129))}
    for sector, record in layout.BUILDINGS.items():
        if not record.get("paint_shell", True):
            continue
        facades = (record["facade"],) if "facade" in record else record["facade_union"]
        entry = record.get("entry")
        entry_x = set(range(entry[0], entry[2])) if entry else set()
        entry_x.update(extra_gaps.get(sector, ()))
        for left, _top, right, bottom in facades:
            # The target has a narrow, planted frontage between each cutaway
            # and the avenue.  Put the hedge on that one-cell grass shoulder;
            # the old +1/+3 offsets dropped it into the public path exclusion,
            # leaving every building floating on an empty lawn.
            hedge_y = bottom
            if not 0 <= hedge_y < HEIGHT:
                continue
            positions = [
                x
                for x in range(left + 1, right - 1)
                if x not in entry_x and (x, hedge_y) not in PUBLIC_PATH_CELLS
            ]
            for run in _contiguous(positions):
                for index, x in enumerate(run):
                    key = HEDGE_KEYS[0 if index == 0 else 2 if index == len(run) - 1 else 1]
                    result.append(
                        (sector, SECTOR_ZONE[sector], "foundation-hedge",
                         "continuous facade garden", key, x, hedge_y)
                    )
                if len(run) >= 4:
                    result.append(
                        (sector, SECTOR_ZONE[sector], "garden-seat",
                         "facade garden seat", BENCH, run[len(run) // 2], hedge_y + 2)
                    )
        room = record.get("room")
        facade = record.get("facade")
        if room is not None and facade is not None:
            for x in (room[0] - 1, room[2]):
                points = [
                    (x, y)
                    for y in range(max(room[1] + 2, facade[1] - 5), facade[1])
                    if 0 <= x < WIDTH
                    and (x, y) not in PROP_EXCLUSION_CELLS
                    and (x, y) not in WATER_CELLS
                    and not any(_inside((x, y), rect) for rect in STRUCTURE_RECTS)
                ]
                for index, (visual_x, visual_y) in enumerate(points):
                    key = (
                        VERTICAL_HEDGE_KEYS[0] if index == 0
                        else VERTICAL_HEDGE_KEYS[3] if index == len(points) - 1
                        else VERTICAL_HEDGE_KEYS[1 + index % 2]
                    )
                    result.append(
                        (sector, SECTOR_ZONE[sector], "foundation-hedge",
                         "side garden boundary", key, visual_x, visual_y)
                    )
    return tuple(result)


PARCEL_GROVES = public_support.PARCEL_GROVES
FOREST_WALL_PLACEMENTS = _forest_wall_placements()
FOREST_WALL_POINTS = frozenset((item[5], item[6]) for item in FOREST_WALL_PLACEMENTS)
FOUNDATION_PLACEMENTS = _foundation_placements()
FOUNDATION_POINTS = frozenset((item[5], item[6]) for item in FOUNDATION_PLACEMENTS)
PERIMETER_PLACEMENTS = _perimeter_placements()
(
    PARCEL_GROVE_PLACEMENTS, PLAZA_PLACEMENTS, PLACEMENTS,
) = public_support.finalize_placements(globals(), civic_landscape)
public_support.validate_public_realm(globals())
