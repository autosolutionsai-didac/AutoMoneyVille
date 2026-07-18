"""Validate and compile Claudeville's Tiled-first semantic authoring group."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from dataclasses import dataclass

try:
    from tools.mapgen import claudeville_semantic_graph as semantic_graph
except ModuleNotFoundError:  # Direct script imports.
    import claudeville_semantic_graph as semantic_graph  # type: ignore[no-redef]

PROFILE = "claudeville-modern-interiors-v3"
GROUP_NAME = "Authoring"
AUTHORING_LAYERS = ("Zones", "Interactions", "Entrances", "Spawns", "Blockers")
RUNTIME_LAYERS = (
    "Bottom Ground", "Exterior Ground", "Exterior Decoration L1",
    "Exterior Decoration L2", "Interior Ground", "Wall",
    "Interior Furniture L1", "Interior Furniture L2", "Foreground L1",
    "Foreground L2", "Depth Props", "Overhead Props", "Collisions",
)
ART_LAYERS = frozenset(
    {
        "Exterior Decoration L1", "Exterior Decoration L2", "Wall",
        "Interior Furniture L1", "Interior Furniture L2", "Foreground L1",
        "Foreground L2", "Depth Props", "Overhead Props",
    }
)
BLOCKER_POLICIES = frozenset(
    {"nonblocking", "preserve-collision", "require-blocked"}
)
SEMANTIC_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
ROOM_TYPE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
PIXEL_SIZE = 32
LOGICAL_WIDTH, LOGICAL_HEIGHT = 88, 48
Point = tuple[int, int]

AUTHORING_SCHEMA = {
    "Zones": ("semantic_id", "sector", "room_type"),
    "Interactions": (
        "semantic_id", "sector", "zone", "interaction_type", "art_layer",
        "allowed_room_types", "stance_x", "stance_y",
    ),
    "Entrances": ("semantic_id", "sector"),
    "Spawns": ("semantic_id", "sector", "zone"),
    "Blockers": ("semantic_id", "sector", "art_layer", "blocker_policy"),
}

BEDROOMS = frozenset({"bedroom", "main-room", "studio"})
BATHROOMS = frozenset({"bathroom", "restroom"})
KITCHENS = frozenset(
    {
        "kitchen", "kitchen-dining", "prep-kitchen", "cafe-kitchen", "cafeteria",
        "main-room", "studio",
    }
)
BANK_ROOMS = frozenset(
    {
        "advisory", "archive", "operations", "teller",
        "bank-advisory", "bank-archive", "bank-operations", "bank-teller",
    }
)
TEACHING_ROOMS = frozenset({"classroom", "lecture", "training-lab"})


class TiledAuthoringError(ValueError):
    """Raised when the source-of-truth Tiled semantics are malformed."""


@dataclass(frozen=True)
class AuthoredObject:
    semantic_id: str
    layer: str
    cells: frozenset[Point]
    point: Point | None
    properties: dict


@dataclass(frozen=True)
class AuthoredZone:
    sector: str
    room_type: str
    cells: frozenset[Point]


@dataclass(frozen=True)
class AuthoringModel:
    by_layer: dict[str, tuple[AuthoredObject, ...]]
    zones: dict[str, AuthoredZone]


@dataclass(frozen=True)
class AuthoringCompilation:
    town_spec: dict
    collision_overrides: dict
    collision: tuple[tuple[bool, ...], ...]
    object_stances: tuple[Point, ...]
    stats: dict[str, int | float]


def properties(value: object) -> dict:
    """Normalize Tiled's property array without accepting duplicate names."""
    if isinstance(value, dict):
        return dict(value)
    if not isinstance(value, list):
        return {}
    result = {}
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise TiledAuthoringError("Tiled properties must have string names")
        name = item["name"]
        if name in result:
            raise TiledAuthoringError(f"duplicate Tiled property: {name}")
        result[name] = item.get("value")
    return result


def is_tiled_first(tmj: dict) -> bool:
    """Return whether this map opts into the non-procedural candidate profile."""
    return properties(tmj.get("properties")).get("authoring_profile") == PROFILE


def _property_record(name: str, value: object) -> dict:
    kind = "bool" if isinstance(value, bool) else "int" if isinstance(value, int) \
        else "float" if isinstance(value, float) else "string"
    return {"name": name, "type": kind, "value": value}


def make_authoring_object(
    object_id: int, semantic_id: str, x: int, y: int, *, width: int = 0,
    height: int = 0, point: bool = False, **values: object,
) -> dict:
    """Build one deterministic Tiled semantic object for scripts and tests."""
    payload = {"semantic_id": semantic_id, **values}
    result = {
        "id": object_id, "name": semantic_id, "type": "", "x": x, "y": y,
        "width": width, "height": height, "rotation": 0, "visible": True,
        "properties": [_property_record(key, payload[key]) for key in sorted(payload)],
    }
    if point:
        result["point"] = True
    return result


def make_authoring_group(
    group_id: int, *, zones=(), interactions=(), entrances=(), spawns=(), blockers=(),
) -> dict:
    """Build the required hidden group without adding it to the runtime contract."""
    values = (zones, interactions, entrances, spawns, blockers)
    layers = [
        {
            "id": group_id + offset + 1, "name": name, "type": "objectgroup",
            "draworder": "topdown", "opacity": 1, "visible": True,
            "objects": list(objects),
        }
        for offset, (name, objects) in enumerate(zip(AUTHORING_LAYERS, values, strict=True))
    ]
    return {
        "id": group_id, "name": GROUP_NAME, "type": "group", "opacity": 1,
        "visible": False, "layers": layers,
    }


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise TiledAuthoringError(f"{label} must be a finite number")
    return float(value)


def _geometry(item: dict, layer_name: str, semantic_id: str) -> tuple[frozenset[Point], Point | None]:
    x = _number(item.get("x"), f"{semantic_id}.x")
    y = _number(item.get("y"), f"{semantic_id}.y")
    width = _number(item.get("width", 0), f"{semantic_id}.width")
    height = _number(item.get("height", 0), f"{semantic_id}.height")
    if any(value % PIXEL_SIZE for value in (x, y, width, height)):
        raise TiledAuthoringError(f"{semantic_id} must snap to the 32px logical grid")
    if not (0 <= x <= LOGICAL_WIDTH * PIXEL_SIZE and 0 <= y <= LOGICAL_HEIGHT * PIXEL_SIZE):
        raise TiledAuthoringError(f"{semantic_id} is outside the logical grid")
    is_point = item.get("point") is True
    if layer_name in {"Entrances", "Spawns"}:
        if not is_point or width or height or x == LOGICAL_WIDTH * PIXEL_SIZE or y == LOGICAL_HEIGHT * PIXEL_SIZE:
            raise TiledAuthoringError(f"{semantic_id} must be an in-bounds Tiled point")
        point = int(x // PIXEL_SIZE), int(y // PIXEL_SIZE)
        return frozenset({point}), point
    if is_point or width <= 0 or height <= 0 or x + width > LOGICAL_WIDTH * PIXEL_SIZE \
            or y + height > LOGICAL_HEIGHT * PIXEL_SIZE:
        raise TiledAuthoringError(f"{semantic_id} must be an in-bounds rectangle")
    cells = frozenset(
        (logical_x, logical_y)
        for logical_y in range(int(y // PIXEL_SIZE), int((y + height) // PIXEL_SIZE))
        for logical_x in range(int(x // PIXEL_SIZE), int((x + width) // PIXEL_SIZE))
    )
    return cells, None


def _required(values: dict, names: tuple[str, ...], semantic_id: str) -> None:
    missing = [name for name in names if name not in values]
    if missing:
        raise TiledAuthoringError(f"{semantic_id} is missing properties: {missing}")


def _allowed_rooms(value: object, semantic_id: str) -> frozenset[str]:
    if not isinstance(value, str):
        raise TiledAuthoringError(f"{semantic_id}.allowed_room_types must be a string")
    rooms = frozenset(item.strip() for item in value.split(",") if item.strip())
    if not rooms or any(not ROOM_TYPE.fullmatch(room) for room in rooms):
        raise TiledAuthoringError(f"{semantic_id} has invalid allowed room types")
    return rooms


def _built_in_rooms(kind: str) -> frozenset[str] | None:
    tokens = set(kind.split("-"))
    if "bed" in tokens:
        return BEDROOMS
    if tokens & {"toilet", "shower", "bathtub"}:
        return BATHROOMS
    if tokens & {"stove", "oven", "refrigerator", "fridge", "cooking"}:
        return KITCHENS
    if tokens & {"teller", "vault"}:
        return BANK_ROOMS
    if tokens & {"classroom", "student", "lecture"} or kind == "training-simulator":
        return TEACHING_ROOMS
    return None


def _art_cells(layer: dict, item: AuthoredObject) -> set[Point]:
    properties_value = item.properties
    if layer.get("type") == "tilelayer":
        data = layer.get("data")
        if not isinstance(data, list) or len(data) != 176 * 96:
            raise TiledAuthoringError(f"art layer {layer.get('name')} has invalid tile data")
        return {
            (x, y) for x, y in item.cells
            if any(
                0 <= x + dx < LOGICAL_WIDTH and 0 <= y + dy < LOGICAL_HEIGHT
                and any(data[(2 * (y + dy) + sy) * 176 + 2 * (x + dx) + sx]
                        for sy in (0, 1) for sx in (0, 1))
                for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
            )
        }
    if layer.get("type") != "objectgroup" or not isinstance(layer.get("objects"), list):
        raise TiledAuthoringError(f"art layer {layer.get('name')} is malformed")
    art_id, art_key = properties_value.get("art_object_id"), properties_value.get("art_asset_key")
    if not isinstance(art_id, int) and not isinstance(art_key, str):
        raise TiledAuthoringError(f"{item.semantic_id} needs art_object_id or art_asset_key")
    result = set()
    for art in layer["objects"]:
        if not isinstance(art, dict) or art.get("visible") is False:
            continue
        values = properties(art.get("properties"))
        if (isinstance(art_id, int) and art.get("id") != art_id) or \
                (not isinstance(art_id, int) and values.get("asset_key") != art_key):
            continue
        x, y = art.get("x"), art.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            foot = int(x // PIXEL_SIZE), int(y // PIXEL_SIZE)
            width, height = art.get("width", 0), art.get("height", 0)
            scale = values.get("display_scale", 1)
            anchor_x, anchor_y = values.get("anchor_x", 0.5), values.get("anchor_y", 1)
            covered = {foot}
            numeric = width, height, scale, anchor_x, anchor_y
            if all(isinstance(value, (int, float)) and math.isfinite(value)
                   for value in numeric) and width > 0 and height > 0 and scale > 0:
                left, top = x - width * scale * anchor_x, y - height * scale * anchor_y
                right, bottom = x + width * scale * (1 - anchor_x), \
                    y + height * scale * (1 - anchor_y)
                xs = range(math.floor(left / PIXEL_SIZE),
                           math.floor((right - 1e-6) / PIXEL_SIZE) + 1)
                ys = range(math.floor(top / PIXEL_SIZE),
                           math.floor((bottom - 1e-6) / PIXEL_SIZE) + 1)
                covered.update((cell_x, cell_y) for cell_y in ys for cell_x in xs)
            if any(
                abs(cell_x - px) + abs(cell_y - py) <= 1
                for cell_x, cell_y in covered for px, py in item.cells
            ):
                result.add(foot)
    return result


def validate_authoring_group(tmj: dict) -> AuthoringModel:
    """Validate profile structure, semantic IDs, room rules, and visible-art links."""
    if not is_tiled_first(tmj):
        raise TiledAuthoringError(f"map must opt into {PROFILE}")
    if (tmj.get("width"), tmj.get("height"), tmj.get("tilewidth"), tmj.get("tileheight"),
            tmj.get("infinite"), tmj.get("orientation")) != (176, 96, 16, 16, False, "orthogonal"):
        raise TiledAuthoringError("Tiled-first map must remain finite 176x96 native-16 orthogonal")
    root_layers = tmj.get("layers")
    if not isinstance(root_layers, list):
        raise TiledAuthoringError("Tiled map must contain root layers")
    if [layer.get("name") for layer in root_layers if isinstance(layer, dict)] != [*RUNTIME_LAYERS, GROUP_NAME]:
        raise TiledAuthoringError("Tiled-first source must contain 13 runtime layers then Authoring")
    groups = [layer for layer in root_layers if isinstance(layer, dict) and layer.get("name") == GROUP_NAME]
    if len(groups) != 1 or groups[0].get("type") != "group" or groups[0].get("visible") is not False:
        raise TiledAuthoringError("Authoring must be one hidden Tiled group")
    children = groups[0].get("layers")
    if not isinstance(children, list) or [item.get("name") for item in children] != list(AUTHORING_LAYERS):
        raise TiledAuthoringError("Authoring group layers must follow the declared order")
    runtime = {layer.get("name"): layer for layer in root_layers if isinstance(layer, dict)}
    seen_ids, seen_object_ids, by_layer = set(), set(), {}
    for child in children:
        name, objects = child.get("name"), child.get("objects")
        if child.get("type") != "objectgroup" or not isinstance(objects, list):
            raise TiledAuthoringError(f"Authoring/{name} must be an object layer")
        parsed = []
        for item in objects:
            if not isinstance(item, dict) or not isinstance(item.get("id"), int) or item["id"] < 1:
                raise TiledAuthoringError(f"Authoring/{name} contains an invalid object")
            if item["id"] in seen_object_ids:
                raise TiledAuthoringError(f"duplicate Tiled object id: {item['id']}")
            seen_object_ids.add(item["id"])
            values = properties(item.get("properties"))
            semantic_id = values.get("semantic_id")
            if not isinstance(semantic_id, str) or not SEMANTIC_ID.fullmatch(semantic_id):
                raise TiledAuthoringError(f"Authoring/{name} needs a stable semantic_id")
            if semantic_id in seen_ids:
                raise TiledAuthoringError(f"duplicate semantic_id: {semantic_id}")
            seen_ids.add(semantic_id)
            _required(values, AUTHORING_SCHEMA[name], semantic_id)
            cells, point = _geometry(item, name, semantic_id)
            parsed.append(AuthoredObject(semantic_id, name, cells, point, values))
        by_layer[name] = tuple(parsed)
    zone_parts, occupied = {}, {}
    for item in by_layer["Zones"]:
        zone_id = item.properties.get("zone", item.semantic_id)
        sector, room_type = item.properties["sector"], item.properties["room_type"]
        if not isinstance(zone_id, str) or not (SEMANTIC_ID.fullmatch(zone_id) or ROOM_TYPE.fullmatch(zone_id)) \
                or not isinstance(sector, str) or not isinstance(room_type, str) \
                or not ROOM_TYPE.fullmatch(room_type):
            raise TiledAuthoringError(f"{item.semantic_id} has invalid zone, sector, or room_type")
        previous = zone_parts.get(zone_id)
        if previous and previous[:2] != (sector, room_type):
            raise TiledAuthoringError(f"zone shapes disagree on metadata: {zone_id}")
        for cell in item.cells:
            if cell in occupied:
                raise TiledAuthoringError(f"zones overlap at {cell}: {occupied[cell]}, {item.semantic_id}")
            occupied[cell] = zone_id
        zone_parts[zone_id] = (sector, room_type, set(item.cells) | (previous[2] if previous else set()))
    zones = {
        zone_id: AuthoredZone(sector, room_type, frozenset(cells))
        for zone_id, (sector, room_type, cells) in zone_parts.items()
    }
    for item in (*by_layer["Interactions"], *by_layer["Blockers"]):
        art_layer = item.properties["art_layer"]
        if art_layer not in ART_LAYERS or art_layer not in runtime \
                or runtime[art_layer].get("visible") is False or not _art_cells(runtime[art_layer], item):
            raise TiledAuthoringError(f"{item.semantic_id} has no linked visible art")
        policy = item.properties.get("blocker_policy", "nonblocking")
        if policy not in BLOCKER_POLICIES:
            raise TiledAuthoringError(f"{item.semantic_id} has invalid blocker_policy")
        if item.layer == "Blockers" and policy != "require-blocked":
            raise TiledAuthoringError(f"{item.semantic_id} blocker must require blocked collision")
    for item in by_layer["Interactions"]:
        zone_id = item.properties["zone"]
        kind = item.properties["interaction_type"]
        interaction_id = item.properties.get("interaction", item.semantic_id)
        if not isinstance(interaction_id, str) or not SEMANTIC_ID.fullmatch(interaction_id):
            raise TiledAuthoringError(f"{item.semantic_id} has an invalid interaction id")
        if zone_id not in zones or not isinstance(kind, str) or not ROOM_TYPE.fullmatch(kind):
            raise TiledAuthoringError(f"{item.semantic_id} has invalid zone or interaction_type")
        zone = zones[zone_id]
        if item.properties["sector"] != zone.sector or not item.cells <= zone.cells:
            raise TiledAuthoringError(f"{item.semantic_id} is outside its authored zone")
        allowed = _allowed_rooms(item.properties["allowed_room_types"], item.semantic_id)
        room_type, built_in = zone.room_type, _built_in_rooms(kind)
        if room_type not in allowed or (built_in is not None and room_type not in built_in):
            raise TiledAuthoringError(f"{item.semantic_id} is not allowed in room type {room_type}")
    return AuthoringModel(by_layer, zones)


def _authoritative_overrides(collision: list[list[bool]]) -> dict:
    return {
        "blocked_regions": [],
        "blocked": [[x, y] for y in range(LOGICAL_HEIGHT) for x in range(LOGICAL_WIDTH) if collision[y][x]],
        "walkable": [[x, y] for y in range(LOGICAL_HEIGHT) for x in range(LOGICAL_WIDTH) if not collision[y][x]],
    }


def compile_authoring(tmj: dict, spec: dict, collision: list[list[bool]]) -> AuthoringCompilation:
    """Compile authored semantics while preserving the backend collision bit-for-bit."""
    if len(collision) != LOGICAL_HEIGHT or any(len(row) != LOGICAL_WIDTH for row in collision):
        raise TiledAuthoringError("authoritative collision must remain 88x48")
    model = validate_authoring_group(tmj)
    try:
        sectors = semantic_graph.sector_cells(spec)
    except semantic_graph.SemanticGraphError as exc:
        raise TiledAuthoringError(str(exc)) from exc
    for zone_id, zone in model.zones.items():
        sector = zone.sector
        if sector not in sectors or not zone.cells <= sectors[sector]:
            raise TiledAuthoringError(f"{zone_id} falls outside sector {sector}")
        if not any(not collision[y][x] for x, y in zone.cells):
            raise TiledAuthoringError(f"{zone_id} has no walkable floor")
    interaction_groups = {}
    for item in model.by_layer["Interactions"]:
        interaction_groups.setdefault(item.properties.get("interaction", item.semantic_id), []).append(item)
    stances = []
    objects = []
    for interaction_id, parts in sorted(interaction_groups.items()):
        item = parts[0]
        fields = ("sector", "zone", "interaction_type", "stance_x", "stance_y", "blocker_policy")
        signatures = {
            tuple(part.properties.get(field, "nonblocking" if field == "blocker_policy" else None)
                  for field in fields)
            for part in parts
        }
        if len(signatures) != 1:
            raise TiledAuthoringError(f"interaction shapes disagree on metadata: {interaction_id}")
        cells = frozenset().union(*(part.cells for part in parts))
        stance = item.properties["stance_x"], item.properties["stance_y"]
        zone = model.zones[item.properties["zone"]]
        owned_floor = set().union(*(
            candidate.cells for candidate in model.zones.values()
            if candidate.sector == zone.sector
        ))
        if any(not isinstance(value, int) or isinstance(value, bool) for value in stance) \
                or stance not in owned_floor \
                or not any(abs(stance[0] - x) + abs(stance[1] - y) == 1 for x, y in cells) \
                or collision[stance[1]][stance[0]]:
            raise TiledAuthoringError(f"{item.semantic_id} has no reachable cardinal stance")
        policy = item.properties.get("blocker_policy", "nonblocking")
        if policy == "nonblocking" and any(collision[y][x] for x, y in cells):
            raise TiledAuthoringError(f"{item.semantic_id} nonblocking footprint is blocked")
        if policy == "require-blocked" and any(not collision[y][x] for x, y in cells):
            raise TiledAuthoringError(f"{item.semantic_id} blocker is missing canonical collision")
        stances.append(stance)
        objects.append({
            "semantic_id": interaction_id, "sector": item.properties["sector"],
            "arena": item.properties["zone"],
            "type": item.properties["interaction_type"].replace("-", " "),
            "tiles": [list(point) for point in sorted(cells, key=lambda p: (p[1], p[0]))],
            "stance": list(stance), "blocks": policy == "require-blocked",
        })
    for item in model.by_layer["Blockers"]:
        if any(not collision[y][x] for x, y in item.cells):
            raise TiledAuthoringError(f"{item.semantic_id} blocker is missing canonical collision")
        sector = item.properties["sector"]
        if sector not in sectors or not item.cells <= sectors[sector]:
            raise TiledAuthoringError(f"{item.semantic_id} falls outside sector {sector}")
        zone_id = item.properties.get("zone")
        if zone_id is not None and (zone_id not in model.zones
                or model.zones[zone_id].sector != sector or not item.cells <= model.zones[zone_id].cells):
            raise TiledAuthoringError(f"{item.semantic_id} falls outside zone {zone_id}")
    entrances = {}
    for item in model.by_layer["Entrances"]:
        sector, point = item.properties["sector"], item.point
        if sector in entrances or sector not in sectors or point is None or collision[point[1]][point[0]] \
                or not any(abs(point[0] - x) + abs(point[1] - y) <= 2 for x, y in sectors[sector]):
            raise TiledAuthoringError(f"{item.semantic_id} is not a clear unique sector entrance")
        entrances[sector] = point
    spawns = {}
    for item in model.by_layer["Spawns"]:
        sector, zone_id, point = item.properties["sector"], item.properties["zone"], item.point
        if sector in spawns or zone_id not in model.zones or point is None \
                or model.zones[zone_id].sector != sector \
                or point not in model.zones[zone_id].cells or collision[point[1]][point[0]]:
            raise TiledAuthoringError(f"{item.semantic_id} is not a clear unique zone spawn")
        spawns[sector] = (point, zone_id, item.properties.get("spawn_name", "sp"))
    authored_sectors = {zone.sector for zone in model.zones.values()}
    if authored_sectors != set(sectors):
        raise TiledAuthoringError("Authoring zones must cover every town sector")
    missing_entrances = authored_sectors - set(entrances) - {"Central Plaza"}
    if missing_entrances or authored_sectors - set(spawns):
        raise TiledAuthoringError("every authored destination needs an entrance and spawn")
    labels, sizes = semantic_graph.components(collision)
    walkable = sum(sizes)
    connectivity = 100.0 * max(sizes, default=0) / max(1, walkable)
    main = sizes.index(max(sizes)) if sizes else -1
    unreachable_zones = sorted(
        zone_id for zone_id, zone in model.zones.items()
        if not any(labels.get(point) == main for point in zone.cells)
    )
    if unreachable_zones:
        raise TiledAuthoringError(f"zones are disconnected: {unreachable_zones}")
    explicit = [*entrances.values(), *(value[0] for value in spawns.values()), *stances]
    if any(labels.get(point) != main for point in explicit):
        raise TiledAuthoringError("an entrance, spawn, or stance is disconnected")
    if connectivity < 98.0:
        raise TiledAuthoringError(f"walkable connectivity {connectivity:.1f}% is below 98%")
    arenas = [
        {"sector": zone.sector, "name": zone_id,
         "rects": semantic_graph.compress(set(zone.cells)), "room_type": zone.room_type}
        for zone_id, zone in sorted(model.zones.items())
    ]
    output = deepcopy(spec)
    output.update({
        "_generated_by": "compile_claudeville_semantics.py",
        "_authoring_profile": PROFILE, "auto_connect": False, "arenas": arenas,
        "objects": objects,
        "spawns": [
            {"sector": sector, "arena": zone, "name": name, "tile": list(point)}
            for sector, (point, zone, name) in sorted(spawns.items())
        ],
        "entrances": [
            {"sector": sector, "tile": list(point)} for sector, point in sorted(entrances.items())
        ],
        "required_zones": [
            {"sector": zone.sector, "arena": zone_id}
            for zone_id, zone in sorted(model.zones.items())
        ],
    })
    stats: dict[str, int | float] = {
        "zones": len(model.zones), "objects": len(objects),
        "blockers": len(model.by_layer["Blockers"]), "authored_walkable": 0,
        "stances": len(stances), "walkable": walkable,
        "connectivity_pct": round(connectivity, 3), "collision_mismatches": 0,
    }
    return AuthoringCompilation(
        output, _authoritative_overrides(collision),
        tuple(tuple(row) for row in collision), tuple(stances), stats,
    )
