"""Reproducible visual thresholds linking Claudeville entrances to interior floor."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from tools.mapgen.claudeville_circulation_cells import CIRCULATION_CELLS
    from tools.mapgen.claudeville_home_stances import HOME_STANCE_CELLS
except ModuleNotFoundError:  # Direct script import.
    from claudeville_circulation_cells import (  # type: ignore[no-redef]
        CIRCULATION_CELLS,
    )
    from claudeville_home_stances import HOME_STANCE_CELLS  # type: ignore[no-redef]

Rect = tuple[int, int, int, int]
Point = tuple[int, int]
PUBLIC_TILE_LAYERS = (
    "Interior Furniture L1", "Interior Furniture L2", "Foreground L1", "Foreground L2"
)
PATH_SOURCE = ("exteriors_city", 1, 1)
WALL_MIDDLE_SOURCE = ("office_room_builder", 2, 1)
WALL_RIGHT_SOURCE = ("office_room_builder", 7, 1)

SOUTH_FRONT_ENTRANCES: dict[str, Point] = {
    "Home 2": (5, 37),
    "Home 3": (13, 37),
    "Home 4": (21, 37),
    "Home 5": (29, 37),
    "Home 6": (38, 37),
    "Town Hall": (48, 37),
    "Home 7": (58, 37),
    "Home 8": (66, 37),
    "Home 9": (75, 37),
    "Home 10": (83, 37),
}

SOUTH_REAR_PATHS: dict[str, Rect] = {
    "Home 2": (10, 90, 16, 92),
    "Home 3": (26, 90, 32, 92),
    "Home 4": (42, 90, 48, 92),
    "Home 5": (58, 90, 60, 92),
    "Home 6": (76, 90, 78, 92),
    "Town Hall": (96, 90, 98, 92),
    "Home 7": (116, 90, 118, 92),
    "Home 8": (132, 90, 134, 92),
    "Home 9": (150, 90, 152, 92),
    "Home 10": (166, 90, 168, 92),
}

SOUTH_REAR_WALL_REPAIRS: tuple[tuple[Rect, tuple[str, int, int]], ...] = (
    ((10, 90, 15, 91), WALL_MIDDLE_SOURCE),
    ((15, 90, 16, 91), WALL_RIGHT_SOURCE),
    ((21, 90, 22, 91), ("office_room_builder", 9, 1)),
    ((22, 90, 31, 91), WALL_MIDDLE_SOURCE),
    ((31, 90, 32, 91), WALL_RIGHT_SOURCE),
    ((42, 90, 48, 91), WALL_MIDDLE_SOURCE),
    ((96, 90, 98, 91), WALL_MIDDLE_SOURCE),
)
HOME_OBJECT_ART_RELOCATIONS: tuple[tuple[Point, Point], ...] = (
    ((59, 38), (58, 38)),
    ((82, 38), (83, 38)),
)


@dataclass(frozen=True, slots=True)
class EntryPath:
    bounds: Rect
    interior: tuple[Rect, ...] = ()
    exterior: tuple[Rect, ...] = ()
    floor: tuple[Rect, ...] = ()


def _south_entry(
    bounds: Rect,
    logical_x: int,
    *,
    detour_x: int | None = None,
    bottom: int = 78,
    bridges: tuple[Rect, ...] = (),
) -> EntryPath:
    visual_x = 2 * logical_x
    interior = [(visual_x, 75, visual_x + 2, 76)]
    if detour_x is None:
        interior[0] = (visual_x, 75, visual_x + 2, bottom)
    else:
        detour = 2 * detour_x
        left = 2 * (logical_x + 1) if detour_x > logical_x else detour
        right = 2 * (detour_x + 1) if detour_x > logical_x else visual_x
        interior.extend(((left, 74, right, 76), (detour, 76, detour + 2, 82)))
    interior.extend(bridges)
    return EntryPath(
        (bounds[0], 71, bounds[2], bounds[3]),
        interior=tuple(interior),
        exterior=((visual_x, 71, visual_x + 2, 75),),
    )


ENTRY_PATHS: dict[str, EntryPath] = {
    "Bank": EntryPath((10, 12, 29, 34), exterior=((18, 31, 20, 34),)),
    "Home 1": EntryPath(
        (45, 10, 62, 34),
        ((52, 26, 54, 32), (52, 26, 58, 28), (56, 22, 58, 28)),
        ((52, 32, 54, 34),),
    ),
    "University": EntryPath(
        (73, 8, 100, 34),
        ((82, 24, 84, 32), (82, 24, 86, 26), (82, 30, 86, 32)),
        ((84, 32, 86, 34),),
    ),
    "Agent Academy": EntryPath(
        (109, 10, 130, 34),
        ((112, 26, 114, 32), (112, 26, 116, 28)),
        ((112, 32, 114, 34),),
        ((118, 26, 126, 32),),
    ),
    "Market": EntryPath(
        (147, 22, 161, 34),
        ((154, 26, 160, 28), (158, 26, 160, 32), (154, 30, 160, 32)),
        ((154, 32, 156, 34),),
    ),
    "Workshop": EntryPath((8, 40, 29, 64), exterior=((18, 62, 20, 64),)),
    "Community Center": EntryPath((45, 43, 65, 64), exterior=((52, 62, 54, 64),)),
    "Claudeville Cafe": EntryPath(
        (92, 43, 109, 64),
        ((100, 54, 102, 57),),
        ((100, 57, 102, 64),),
    ),
    "Library": EntryPath(
        (112, 42, 131, 64), ((118, 60, 122, 62),), ((118, 62, 120, 64),)
    ),
    "Post Office": EntryPath(
        (149, 43, 172, 64), ((160, 54, 162, 62),), ((160, 62, 162, 64),)
    ),
    "Home 2": _south_entry((5, 75, 16, 92), 5),
    "Home 3": _south_entry((21, 75, 32, 92), 13),
    "Home 4": _south_entry((38, 75, 49, 92), 21),
    "Home 5": _south_entry((53, 75, 65, 92), 29),
    "Home 6": _south_entry(
        (68, 75, 84, 92), 38, detour_x=41, bridges=((78, 80, 80, 82),)
    ),
    "Town Hall": _south_entry((88, 75, 107, 92), 48, bottom=80),
    "Home 7": _south_entry(
        (111, 75, 124, 92), 58, detour_x=61, bridges=((118, 80, 122, 82),)
    ),
    "Home 8": _south_entry((127, 75, 139, 92), 66),
    "Home 9": _south_entry((144, 75, 158, 92), 75),
    "Home 10": _south_entry(
        (160, 75, 172, 92), 83, detour_x=80, bridges=((164, 80, 166, 82),)
    ),
}


def cells(rect: Rect):
    left, top, right, bottom = rect
    for y in range(top, bottom):
        for x in range(left, right):
            yield x, y


def authored_walkable_cells(
    layers: dict[str, dict], visible_blocks: set[Point], width: int = 176
) -> set[Point]:
    """Return final grounded 2x2 cells deliberately opened by this recipe."""
    declared = {
        point
        for entry in ENTRY_PATHS.values()
        for rect in (*entry.interior, *entry.exterior, *entry.floor)
        for point in cells(rect)
    }
    declared.update(
        (2 * stance.point[0] + dx, 2 * stance.point[1] + dy)
        for stances in HOME_STANCE_CELLS.values()
        for stance in stances
        for dy in (0, 1)
        for dx in (0, 1)
    )
    declared.update(
        (2 * point[0] + dx, 2 * point[1] + dy)
        for points in CIRCULATION_CELLS.values()
        for point in points
        for dy in (0, 1)
        for dx in (0, 1)
    )
    ground_layers = ("Bottom Ground", "Exterior Ground", "Interior Ground")
    height = len(layers[ground_layers[0]]["data"]) // width
    result: set[Point] = set()
    for logical_y in range(height // 2):
        for logical_x in range(width // 2):
            footprint = {
                (2 * logical_x + dx, 2 * logical_y + dy)
                for dy in (0, 1)
                for dx in (0, 1)
            }
            indices = [y * width + x for x, y in footprint]
            visibly_paved = all(
                layers["Exterior Ground"]["data"][index] for index in indices
            )
            if (
                not (footprint <= declared or visibly_paved)
                or (logical_x, logical_y) in visible_blocks
            ):
                continue
            if all(
                any(layers[name]["data"][index] for name in ground_layers)
                for index in indices
            ) and not any(
                layers[name]["data"][index]
                for name in ("Wall", *PUBLIC_TILE_LAYERS)
                for index in indices
            ):
                result.add((logical_x, logical_y))
    return result


def _nearest_ground(data: list[int], x: int, y: int, bounds: Rect, width: int) -> int:
    candidates = (
        (abs(other_x - x) + abs(other_y - y), other_y, other_x, data[other_y * width + other_x])
        for other_x, other_y in cells(bounds)
        if data[other_y * width + other_x]
    )
    try:
        return min(candidates)[3]
    except ValueError as exc:
        raise ValueError(f"entry path has no interior floor source: {bounds}") from exc


def _retire_south_rear_entries(
    layers: dict[str, dict], atlas_gids: dict[tuple[str, int, int], int], width: int
) -> int:
    exterior = layers["Exterior Ground"]["data"]
    interior = layers["Interior Ground"]["data"]
    wall = layers["Wall"]["data"]
    changed = 0
    for rect in SOUTH_REAR_PATHS.values():
        for x, y in cells(rect):
            exterior[y * width + x] = 0
            changed += 1
    for rect, source in SOUTH_REAR_WALL_REPAIRS:
        gid = atlas_gids.get(source)
        if not gid:
            raise ValueError(f"curated rear wall tile is missing: {source}")
        for x, y in cells(rect):
            index = y * width + x
            wall[index], interior[index], exterior[index] = gid, 0, 0
            for blocker in PUBLIC_TILE_LAYERS:
                layers[blocker]["data"][index] = 0
            changed += 1
    return changed


def apply_entry_paths(
    layers: dict[str, dict], atlas_gids: dict[tuple[str, int, int], int], width: int
) -> int:
    """Open every declared route while leaving collision generation authoritative."""
    path_gid = atlas_gids.get(PATH_SOURCE)
    if not path_gid:
        raise ValueError(f"curated exterior path tile is missing: {PATH_SOURCE}")
    relocated_art: list[tuple[Point, dict[str, tuple[int, ...]]]] = []
    for source, target in HOME_OBJECT_ART_RELOCATIONS:
        source_indices = tuple(
            (2 * source[1] + dy) * width + 2 * source[0] + dx
            for dy in (0, 1)
            for dx in (0, 1)
        )
        values = {
            name: tuple(layers[name]["data"][index] for index in source_indices)
            for name in PUBLIC_TILE_LAYERS
        }
        if not any(value for items in values.values() for value in items):
            raise ValueError(f"home object art is missing before relocation: {source}")
        relocated_art.append((target, values))
    changed = _retire_south_rear_entries(layers, atlas_gids, width)
    for entry in ENTRY_PATHS.values():
        interior = layers["Interior Ground"]["data"]
        exterior = layers["Exterior Ground"]["data"]
        for layer_name, rects in (
            ("Interior Ground", (*entry.interior, *entry.floor)),
            ("Exterior Ground", entry.exterior),
        ):
            for rect in rects:
                for x, y in cells(rect):
                    index = y * width + x
                    for blocker in ("Wall", *PUBLIC_TILE_LAYERS):
                        layers[blocker]["data"][index] = 0
                    if layer_name == "Interior Ground":
                        interior[index] = _nearest_ground(interior, x, y, entry.bounds, width)
                        exterior[index] = 0
                    else:
                        exterior[index], interior[index] = path_gid, 0
                    changed += 1
    for sector, stances in HOME_STANCE_CELLS.items():
        entry = ENTRY_PATHS[sector]
        interior = layers["Interior Ground"]["data"]
        exterior = layers["Exterior Ground"]["data"]
        for stance in stances:
            logical_x, logical_y = stance.point
            for x, y in cells((2 * logical_x, 2 * logical_y, 2 * logical_x + 2, 2 * logical_y + 2)):
                index = y * width + x
                for blocker in ("Wall", *PUBLIC_TILE_LAYERS):
                    layers[blocker]["data"][index] = 0
                if not interior[index]:
                    interior[index] = _nearest_ground(
                        interior, x, y, entry.bounds, width
                    )
                exterior[index] = 0
                changed += 1
    for sector, points in CIRCULATION_CELLS.items():
        entry = ENTRY_PATHS[sector]
        interior = layers["Interior Ground"]["data"]
        exterior = layers["Exterior Ground"]["data"]
        for logical_x, logical_y in points:
            for x, y in cells(
                (
                    2 * logical_x,
                    2 * logical_y,
                    2 * logical_x + 2,
                    2 * logical_y + 2,
                )
            ):
                index = y * width + x
                for blocker in ("Wall", *PUBLIC_TILE_LAYERS):
                    layers[blocker]["data"][index] = 0
                if not interior[index]:
                    interior[index] = _nearest_ground(
                        interior, x, y, entry.bounds, width
                    )
                exterior[index] = 0
                changed += 1
    for target, values in relocated_art:
        target_indices = tuple(
            (2 * target[1] + dy) * width + 2 * target[0] + dx
            for dy in (0, 1)
            for dx in (0, 1)
        )
        for name, gids in values.items():
            for index, gid in zip(target_indices, gids, strict=True):
                layers[name]["data"][index] = gid
        changed += 4
    return changed
