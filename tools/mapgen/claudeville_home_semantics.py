"""Map licensed The Ville home templates into Claudeville semantic cells."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

try:
    from tools.mapgen.claudeville_home_clearances import (
        HomeSemanticError,
        align_refrigerator_rooms,
        assign_reviewed_stance_rooms,
        reviewed_clearance_points,
    )
    from tools.mapgen.claudeville_home_stances import HOME_STANCE_CELLS
    from tools.mapgen.claudeville_interior_layouts import (
        BUILDING_BOUNDS,
        HOMES,
        SOURCE_TEMPLATES,
        Stamp,
    )
except ModuleNotFoundError:  # Direct script import.
    from claudeville_home_clearances import (  # type: ignore[no-redef]
        HomeSemanticError,
        align_refrigerator_rooms,
        assign_reviewed_stance_rooms,
        reviewed_clearance_points,
    )
    from claudeville_home_stances import HOME_STANCE_CELLS  # type: ignore[no-redef]
    from claudeville_interior_layouts import (  # type: ignore
        BUILDING_BOUNDS,
        HOMES,
        SOURCE_TEMPLATES,
        Stamp,
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_ROOT = (
    REPO_ROOT / "environment/frontend_server/static_dirs/assets/the_ville/matrix"
)
VISUAL_WIDTH = 176
Point = tuple[int, int]

HOME_ENTRANCES: dict[str, Point] = {
    "Home 1": (26, 16),
    "Home 2": (5, 37),
    "Home 3": (13, 37),
    "Home 4": (21, 37),
    "Home 5": (29, 37),
    "Home 6": (38, 37),
    "Home 7": (58, 37),
    "Home 8": (66, 37),
    "Home 9": (75, 37),
    "Home 10": (83, 37),
}
IGNORED_OBJECT_TYPES = frozenset({"house garden"})
KITCHEN_TYPES = frozenset({"kitchen sink", "refrigerator", "cooking area"})


@dataclass(frozen=True, slots=True)
class HomeObject:
    zone: str
    type: str
    logical_tiles: tuple[Point, ...]


@dataclass(frozen=True)
class HomeSemantics:
    zones: dict[str, frozenset[Point]]
    owners: dict[str, str]
    objects: dict[str, tuple[HomeObject, ...]]
    spawn_candidates: dict[str, tuple[Point, ...]]
    preferred_spawn_cells: dict[str, tuple[Point, ...]]
    entrances: dict[str, Point]


def _flat(root: Path, name: str) -> list[str]:
    path = root / "maze" / f"{name}_maze.csv"
    values = [item.strip() for item in path.read_text(encoding="utf-8").split(",")]
    if len(values) != 14000:
        raise HomeSemanticError(f"The Ville {name} matrix must contain 14000 cells")
    return values


def _legend(root: Path, name: str) -> dict[str, str]:
    path = root / "special_blocks" / f"{name}_blocks.csv"
    result: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.reader(source):
            if row:
                result[row[0].strip()] = row[-1].strip()
    return result


def _room_name(value: str) -> str:
    name = value.casefold()
    if "bathroom" in name:
        return "bathroom"
    if "kitchen" in name:
        return "kitchen"
    if "garden" in name:
        return "garden"
    if "study" in name or "office" in name:
        return "study"
    if "common" in name or "living" in name:
        return "living room"
    if "bedroom" in name or ("room" in name and "main room" not in name):
        return "bedroom"
    return "main room"


def _slug(value: str) -> str:
    return value.casefold().replace(" ", "_")


def _floor(layers: dict[str, dict], bounds: tuple[int, int, int, int]) -> set[Point]:
    interior = layers["Interior Ground"]["data"]
    exterior = layers["Exterior Ground"]["data"]
    wall = layers["Wall"]["data"]
    left, top, right, bottom = bounds
    result: set[Point] = set()
    for y in range((top + 1) // 2, bottom // 2):
        for x in range((left + 1) // 2, right // 2):
            indices = [
                (2 * y + dy) * VISUAL_WIDTH + 2 * x + dx
                for dy in (0, 1)
                for dx in (0, 1)
            ]
            if all(interior[i] or exterior[i] for i in indices) and not any(
                wall[i] for i in indices
            ):
                result.add((x, y))
    return result


def _clear_ground(layers: dict[str, dict], cells: set[Point]) -> set[Point]:
    """Return visually clear parcel ground, including purposeful home gardens."""
    if "Bottom Ground" not in layers:
        raise HomeSemanticError("TMJ needs Bottom Ground to derive home gardens")
    ground_names = ("Bottom Ground", "Exterior Ground", "Interior Ground")
    wall = layers["Wall"]["data"]
    result: set[Point] = set()
    for x, y in cells:
        indices = [
            (2 * y + dy) * VISUAL_WIDTH + 2 * x + dx for dy in (0, 1) for dx in (0, 1)
        ]
        if all(
            any(layers[name]["data"][index] for name in ground_names)
            for index in indices
        ) and not any(wall[index] for index in indices):
            result.add((x, y))
    return result


def _mapped(home, offset_x: int, offset_y: int, width: int) -> Point:
    target_x = home.stamp.destination[0] + (
        width - 1 - offset_x if home.stamp.mirror_x else offset_x
    )
    target_y = home.stamp.destination[1] + offset_y
    return target_x // 2, target_y // 2


def _nearest_room(
    point: Point, votes: dict[Point, Counter[str]], default: str = "main room"
) -> str:
    if point in votes:
        return sorted(votes[point].items(), key=lambda item: (-item[1], item[0]))[0][0]
    if not votes:
        return default
    nearest = min(
        votes,
        key=lambda other: (
            abs(point[0] - other[0]) + abs(point[1] - other[1]),
            other[1],
            other[0],
        ),
    )
    return sorted(votes[nearest].items(), key=lambda item: (-item[1], item[0]))[0][0]


def partition_public_zones(
    layers: dict[str, dict], layout, sectors: dict[str, set[Point]]
) -> tuple[dict[str, set[Point]], dict[str, str], set[Point]]:
    """Partition every public floor cell into one purposeful navigation zone."""
    uses: dict[str, set[str]] = defaultdict(set)
    for mapping in (layout.PURPOSE_PROPS, layout.SEMANTIC_OBJECTS):
        for sector, entries in mapping.items():
            if sector not in sectors:
                raise HomeSemanticError(
                    f"purpose data references unknown sector {sector}"
                )
            for entry in entries:
                uses[entry.zone].add(sector)
    owners: dict[str, str] = {}
    raw: dict[str, set[Point]] = {}
    for zone, bounds in layout.ZONE_RECTS.items():
        candidates = uses.get(zone, set())
        if len(candidates) != 1:
            raise HomeSemanticError(f"zone {zone} must resolve to one sector")
        owner = next(iter(candidates))
        owners[zone] = owner
        raw[zone] = _floor(layers, bounds) & sectors[owner]
        if not raw[zone]:
            raise HomeSemanticError(f"zone {zone} has no supported logical floor")
    unknown = set(uses) - set(owners)
    if unknown:
        raise HomeSemanticError(
            f"semantic entries reference unknown zones: {sorted(unknown)}"
        )

    reserved: dict[str, set[Point]] = defaultdict(set)
    reserved_owner: dict[Point, str] = {}
    for sector, entries in layout.SEMANTIC_OBJECTS.items():
        for entry in entries:
            if owners.get(entry.zone) != sector:
                raise HomeSemanticError(
                    f"object zone {entry.zone} is not owned by {sector}"
                )
            for point in entry.logical_tiles:
                if point not in raw[entry.zone]:
                    raise HomeSemanticError(
                        f"object {sector}:{entry.type} is outside zone floor"
                    )
                prior = reserved_owner.setdefault(point, entry.zone)
                if prior != entry.zone:
                    raise HomeSemanticError(f"object tile {point} belongs to two zones")
                reserved[entry.zone].add(point)

    zones: dict[str, set[Point]] = {}
    clear_floor: set[Point] = set()
    terraces = getattr(layout, "TERRACE_BOUNDS", {})
    for sector, bounds in layout.PUBLIC_BUILDING_BOUNDS.items():
        footprint = _floor(layers, bounds)
        if sector in terraces:
            footprint |= _floor(layers, terraces[sector])
        footprint &= sectors[sector]
        clear_floor |= footprint
        sector_zones = [zone for zone in layout.ZONE_RECTS if owners[zone] == sector]
        all_reserved = set().union(*(reserved[zone] for zone in sector_zones))
        assigned: set[Point] = set()
        for zone in sector_zones:
            cells = reserved[zone] | (
                raw[zone] - (all_reserved - reserved[zone]) - assigned
            )
            if not cells:
                raise HomeSemanticError(
                    f"zone {zone} lost all floor after partitioning"
                )
            zones[zone] = cells
            assigned |= cells
        circulation = footprint - assigned
        if circulation:
            name = f"{_slug(sector)}.circulation"
            zones.setdefault(name, set()).update(circulation)
            owners[name] = sector
    return zones, owners, clear_floor


def derive_home_semantics(
    layers: dict[str, dict],
    layout,
    matrix_root: Path = MATRIX_ROOT,
    active_sectors: set[str] | None = None,
    sector_cells: dict[str, set[Point]] | None = None,
) -> HomeSemantics:
    """Translate home arenas, objects and spawn candidates onto the 32px grid."""
    active = set(HOME_ENTRANCES) if active_sectors is None else set(active_sectors)
    unknown = active - set(HOME_ENTRANCES)
    if unknown:
        raise HomeSemanticError(f"unknown home sectors: {sorted(unknown)}")
    if not active:
        return HomeSemantics({}, {}, {}, {}, {}, {})
    root = Path(matrix_root)
    matrices = {
        name: _flat(root, name)
        for name in ("arena", "game_object", "spawning_location")
    }
    legends = {
        name: _legend(root, name)
        for name in ("arena", "game_object", "spawning_location")
    }
    zones: dict[str, frozenset[Point]] = {}
    owners: dict[str, str] = {}
    objects: dict[str, tuple[HomeObject, ...]] = {}
    spawn_candidates: dict[str, tuple[Point, ...]] = {}
    preferred: dict[str, tuple[Point, ...]] = {}

    for home in HOMES:
        if home.name not in active:
            continue
        source_x, source_y, width, height = SOURCE_TEMPLATES[home.stamp.template]
        floor = _floor(layers, home.bounds)
        if sector_cells is not None:
            if home.name not in sector_cells:
                raise HomeSemanticError(f"missing sector footprint for {home.name}")
            floor |= _clear_ground(layers, sector_cells[home.name])
        if not floor:
            raise HomeSemanticError(f"{home.name} has no supported floor")
        arena_votes: dict[Point, Counter[str]] = defaultdict(Counter)
        object_votes: dict[Point, Counter[str]] = defaultdict(Counter)
        mapped_spawns: set[Point] = set()
        for offset_y in range(height):
            for offset_x in range(width):
                source_index = (source_y + offset_y) * 140 + source_x + offset_x
                point = _mapped(home, offset_x, offset_y, width)
                if point not in floor:
                    continue
                arena_id = matrices["arena"][source_index]
                if arena_id != "0" and arena_id in legends["arena"]:
                    arena_votes[point][_room_name(legends["arena"][arena_id])] += 1
                object_id = matrices["game_object"][source_index]
                if object_id != "0" and object_id in legends["game_object"]:
                    object_type = legends["game_object"][object_id]
                    if object_type not in IGNORED_OBJECT_TYPES:
                        object_votes[point][object_type] += 1
                if matrices["spawning_location"][source_index] != "0":
                    mapped_spawns.add(point)

        stance_recipes = HOME_STANCE_CELLS.get(home.name, ())
        clearance_points = reviewed_clearance_points(home.name, stance_recipes, floor)
        for point in clearance_points:
            object_votes.pop(point, None)

        assignment = {point: _nearest_room(point, arena_votes) for point in floor}
        align_refrigerator_rooms(assignment, object_votes)
        assign_reviewed_stance_rooms(home.name, stance_recipes, assignment)
        room_cells: dict[str, set[Point]] = defaultdict(set)
        for point, room in assignment.items():
            room_cells[room].add(point)
        for room, cells in sorted(room_cells.items()):
            zone = f"{_slug(home.name)}.{_slug(room)}"
            zones[zone] = frozenset(cells)
            owners[zone] = home.name

        grouped: dict[tuple[str, str], set[Point]] = defaultdict(set)
        for point, votes in object_votes.items():
            object_type = sorted(votes.items(), key=lambda item: (-item[1], item[0]))[
                0
            ][0]
            zone = f"{_slug(home.name)}.{_slug(assignment[point])}"
            grouped[(zone, object_type)].add(point)
        objects[home.name] = tuple(
            HomeObject(
                zone, object_type, tuple(sorted(cells, key=lambda p: (p[1], p[0])))
            )
            for (zone, object_type), cells in sorted(grouped.items())
        )
        for recipe in stance_recipes:
            matches = [
                entry
                for entry in objects[home.name]
                if (entry.zone, entry.type) == (recipe.zone, recipe.object_type)
            ]
            if len(matches) != 1 or not any(
                abs(recipe.point[0] - x) + abs(recipe.point[1] - y) == 1
                for x, y in matches[0].logical_tiles
            ):
                raise HomeSemanticError(
                    f"{home.name} stance does not match {recipe.object_type}"
                )
        spawn_candidates[home.name] = tuple(
            sorted(mapped_spawns, key=lambda p: (p[1], p[0]))
        )
        origin = min(mapped_spawns, default=HOME_ENTRANCES[home.name])
        order = {"bedroom": 0, "main room": 1, "living room": 2}
        preferred[home.name] = tuple(
            sorted(
                (point for point in floor if assignment[point] in order),
                key=lambda p: (
                    order.get(assignment[p], 3),
                    abs(p[0] - origin[0]) + abs(p[1] - origin[1]),
                    p[1],
                    p[0],
                ),
            )
        )

    for sector, stamps in layout.HOME_KITCHEN_STAMPS.items():
        if sector not in active:
            continue
        if any(stamp.source_id != "legacy_the_ville" for stamp in stamps):
            raise HomeSemanticError(
                f"{sector} kitchen stamp must use the licensed source"
            )
        entries = objects.get(sector, ())
        if not any(
            entry.type in KITCHEN_TYPES and entry.zone.endswith(".kitchen")
            for entry in entries
        ):
            raise HomeSemanticError(
                f"{sector} kitchen has no mapped kitchen interactions"
            )
    return HomeSemantics(
        zones,
        owners,
        objects,
        spawn_candidates,
        preferred,
        {sector: point for sector, point in HOME_ENTRANCES.items() if sector in active},
    )


def _visible(layers: dict[str, dict], names: tuple[str, ...], x: int, y: int) -> bool:
    index = y * VISUAL_WIDTH + x
    return any(layers[name]["data"][index] for name in names)


def old_stamp_blocks(
    layers: dict[str, dict], old_map: dict, layout, visible_layers: tuple[str, ...]
) -> set[Point]:
    """Map collision-marked licensed stamp cells, respecting mirrors and crops."""
    old_layers = {layer.get("name"): layer for layer in old_map.get("layers", [])}
    collision = old_layers.get("Collisions", {}).get("data")
    old_width = old_map.get("width")
    if not isinstance(collision, list) or not isinstance(old_width, int):
        raise HomeSemanticError("legacy room map has no collision layer")
    by_sector: dict[str, list[object]] = defaultdict(list)
    for mapping in (layout.PURPOSE_STAMPS, layout.HOME_KITCHEN_STAMPS):
        for sector, stamps in mapping.items():
            by_sector[sector].extend(stamps)
    for home in HOMES:
        by_sector[home.name].append(home.stamp)
    bounds_lookup = {**BUILDING_BOUNDS, **layout.PUBLIC_BUILDING_BOUNDS}
    result: set[Point] = set()
    for sector, stamps in by_sector.items():
        bounds = bounds_lookup.get(sector)
        if bounds is None:
            raise HomeSemanticError(f"no visual bounds for {sector}")
        for stamp in stamps:
            mirror = False
            if isinstance(stamp, Stamp):
                source = SOURCE_TEMPLATES.get(stamp.template)
                if source is None:
                    raise HomeSemanticError(
                        f"unknown old-map template {stamp.template}"
                    )
                mirror = stamp.mirror_x
            elif getattr(stamp, "source_id", None) == "legacy_the_ville":
                source = stamp.source_rect
            else:
                continue
            sx, sy, width, height = source
            dx, dy = stamp.destination
            for oy in range(height):
                for ox in range(width):
                    if not collision[(sy + oy) * old_width + sx + ox]:
                        continue
                    target_x = dx + (width - 1 - ox if mirror else ox)
                    target_y = dy + oy
                    if (
                        bounds[0] <= target_x < bounds[2]
                        and bounds[1] <= target_y < bounds[3]
                        and _visible(layers, visible_layers, target_x, target_y)
                    ):
                        result.add((target_x // 2, target_y // 2))
    return result


def atlas_blocks(layers: dict[str, dict], layout) -> set[Point]:
    """Map occupied AtlasStamp cells whose policy requires collision."""
    result: set[Point] = set()
    bounds_lookup = {**BUILDING_BOUNDS, **layout.PUBLIC_BUILDING_BOUNDS}
    for mapping in (layout.PURPOSE_STAMPS, layout.HOME_KITCHEN_STAMPS):
        for sector, stamps in mapping.items():
            bounds = bounds_lookup.get(sector)
            if bounds is None:
                raise HomeSemanticError(f"no visual bounds for {sector}")
            for stamp in stamps:
                if (
                    isinstance(stamp, Stamp)
                    or stamp.blocker_policy == "preserve-collision"
                ):
                    continue
                if stamp.blocker_policy != "require-blocked":
                    raise HomeSemanticError(
                        f"unknown AtlasStamp blocker policy {stamp.blocker_policy}"
                    )
                layer_name = stamp.target_layer.strip()
                if layer_name not in layers:
                    raise HomeSemanticError(
                        f"AtlasStamp target layer is missing: {layer_name}"
                    )
                width, height = stamp.source_rect[2:]
                dx, dy = stamp.destination
                data = layers[layer_name]["data"]
                for y in range(dy, dy + height):
                    for x in range(dx, dx + width):
                        if (
                            bounds[0] <= x < bounds[2]
                            and bounds[1] <= y < bounds[3]
                            and data[y * VISUAL_WIDTH + x]
                        ):
                            result.add((x // 2, y // 2))
    return result
