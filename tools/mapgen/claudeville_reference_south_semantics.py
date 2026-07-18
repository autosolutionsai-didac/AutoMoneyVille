"""Align south-district semantics with the traced reference cutaways."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

try:
    from tools.mapgen import claudeville_semantic_graph as semantic_graph
    from tools.mapgen import claudeville_tiled_authoring as authoring
except ModuleNotFoundError:  # Direct module execution.
    import claudeville_semantic_graph as semantic_graph  # type: ignore[no-redef]
    import claudeville_tiled_authoring as authoring  # type: ignore[no-redef]


PIXEL_SIZE = 32
REPO_ROOT = Path(__file__).resolve().parents[2]
COLLISION_PATH = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/matrix/maze/"
    / "collision_maze.csv"
)
COLLISION_BLUEPRINT_PATH = REPO_ROOT / "tools/mapgen/town_spec.collisions.json"
SOUTH_SECTORS = frozenset(
    {f"Home {index}" for index in range(2, 11)} | {"Town Hall"}
)
SECTOR_RECTS = {
    "Home 2": [2, 35, 8, 46],
    "Home 3": [10, 35, 16, 46],
    "Home 4": [20, 35, 24, 46],
    "Home 5": [25, 35, 29, 46],
    "Home 6": [30, 35, 34, 46],
    "Town Hall": [39, 35, 47, 46],
    "Home 7": [53, 35, 58, 46],
    "Home 8": [60, 35, 66, 46],
    "Home 9": [70, 35, 76, 46],
    "Home 10": [77, 35, 83, 46],
}


def _rect(left: int, top: int, right: int, bottom: int) -> frozenset[tuple[int, int]]:
    return frozenset(
        (x, y)
        for y in range(top, bottom + 1)
        for x in range(left, right + 1)
    )


# Exact 32px rooms within the native-16 traced shells. Irregular Home 5 and
# Home 8 partitions follow the visible furniture clusters instead of slicing
# through their bathrooms or bedroom storage.
ZONE_DEFINITIONS = {
    "home_2.main_room": ("Home 2", "main-room", _rect(2, 35, 8, 41)),
    "home_2.bathroom": ("Home 2", "bathroom", _rect(2, 42, 8, 45)),
    "home_3.main_room": ("Home 3", "main-room", _rect(10, 35, 16, 41)),
    "home_3.bathroom": ("Home 3", "bathroom", _rect(10, 42, 16, 45)),
    "home_4.main_room": ("Home 4", "main-room", _rect(20, 35, 24, 41)),
    "home_4.bathroom": ("Home 4", "bathroom", _rect(20, 42, 24, 45)),
    "home_5.living_room": ("Home 5", "living-room", _rect(25, 35, 27, 40)),
    "home_5.kitchen": ("Home 5", "kitchen", _rect(28, 35, 29, 40)),
    "home_5.bedroom": (
        "Home 5", "bedroom", _rect(25, 41, 29, 41) | _rect(25, 42, 27, 44),
    ),
    "home_5.bathroom": ("Home 5", "bathroom", _rect(28, 42, 29, 44)),
    "home_5.garden": ("Home 5", "garden", _rect(25, 45, 29, 45)),
    "home_6.living_room": (
        "Home 6", "living-room", _rect(30, 35, 32, 39),
    ),
    "home_6.kitchen": ("Home 6", "kitchen", _rect(33, 35, 34, 39)),
    "home_6.bathroom": ("Home 6", "bathroom", _rect(33, 40, 34, 44)),
    "home_6.bedroom": ("Home 6", "bedroom", _rect(30, 40, 32, 44)),
    "home_6.garden": ("Home 6", "garden", _rect(30, 45, 34, 45)),
    "hall.public_service": ("Town Hall", "public-service", _rect(39, 35, 47, 39)),
    "town_hall.circulation": ("Town Hall", "circulation", _rect(39, 40, 47, 40)),
    "hall.administration": ("Town Hall", "administration", _rect(39, 41, 47, 42)),
    "hall.council": ("Town Hall", "council", _rect(39, 43, 47, 45)),
    "home_7.living_room": ("Home 7", "living-room", _rect(53, 35, 55, 40)),
    "home_7.kitchen": ("Home 7", "kitchen", _rect(56, 35, 57, 40)),
    "home_7.bathroom": ("Home 7", "bathroom", _rect(58, 35, 58, 40)),
    "home_7.bedroom": ("Home 7", "bedroom", _rect(53, 41, 58, 43)),
    "home_7.garden": ("Home 7", "garden", _rect(53, 44, 58, 45)),
    "home_8.kitchen": (
        "Home 8", "kitchen", _rect(60, 35, 63, 37) | _rect(63, 38, 63, 40),
    ),
    "home_8.bathroom": ("Home 8", "bathroom", _rect(60, 38, 62, 40)),
    "home_8.living_room": ("Home 8", "living-room", _rect(64, 35, 66, 40)),
    "home_8.bedroom": ("Home 8", "bedroom", _rect(60, 41, 66, 43)),
    "home_8.garden": ("Home 8", "garden", _rect(60, 44, 66, 45)),
    "home_9.bathroom": ("Home 9", "bathroom", _rect(70, 35, 72, 41)),
    "home_9.kitchen": ("Home 9", "kitchen", _rect(73, 35, 74, 41)),
    "home_9.living_room": ("Home 9", "living-room", _rect(75, 35, 76, 41)),
    "home_9.bedroom": ("Home 9", "bedroom", _rect(70, 42, 76, 43)),
    "home_9.garden": ("Home 9", "garden", _rect(70, 44, 76, 45)),
    "home_10.bathroom": ("Home 10", "bathroom", _rect(77, 35, 79, 40)),
    "home_10.kitchen": ("Home 10", "kitchen", _rect(80, 35, 81, 40)),
    "home_10.living_room": ("Home 10", "living-room", _rect(82, 35, 83, 40)),
    "home_10.bedroom": ("Home 10", "bedroom", _rect(77, 41, 83, 43)),
    "home_10.garden": ("Home 10", "garden", _rect(77, 44, 83, 45)),
}

B = "require-blocked"
N = "nonblocking"
# Stable interaction id: logical cell, reachable stance, canonical collision policy.
INTERACTION_LAYOUT = {
    "home_2.bathroom.shower-001": ((4, 42), (4, 41), B),
    "home_2.bathroom.bathroom-sink-001": ((4, 43), (5, 43), B),
    "home_2.bathroom.toilet-001": ((6, 42), (6, 41), B),
    "home_2.main_room.closet-001": ((4, 37), (3, 37), B),
    "home_2.main_room.cooking-area-001": ((5, 39), (5, 38), B),
    "home_2.main_room.desk-001": ((3, 37), (2, 37), N),
    "home_2.main_room.refrigerator-001": ((6, 38), (5, 38), B),
    "home_3.bathroom.shower-001": ((12, 43), (13, 43), B),
    "home_3.bathroom.bathroom-sink-001": ((13, 42), (13, 41), B),
    "home_3.bathroom.toilet-001": ((14, 42), (14, 41), B),
    "home_3.main_room.closet-001": ((12, 38), (11, 38), B),
    "home_3.main_room.cooking-area-001": ((13, 39), (13, 38), B),
    "home_3.main_room.desk-001": ((12, 37), (13, 37), B),
    "home_3.main_room.refrigerator-001": ((14, 40), (14, 41), B),
    "home_3.main_room.shelf-001": ((10, 38), (11, 38), B),
    "home_4.bathroom.shower-001": ((22, 42), (22, 41), N),
    "home_4.bathroom.toilet-001": ((23, 42), (22, 42), B),
    "home_4.bathroom.bathroom-sink-001": ((23, 43), (22, 43), B),
    "home_4.main_room.closet-001": ((22, 38), (21, 38), N),
    "home_4.main_room.common-room-sofa-001": ((23, 37), (22, 37), B),
    "home_4.main_room.cooking-area-001": ((23, 38), (22, 38), B),
    "home_4.main_room.desk-001": ((21, 38), (22, 38), N),
    "home_5.bedroom.bed-001": ((27, 41), (28, 41), N),
    "home_5.bedroom.desk-001": ((28, 41), (27, 41), N),
    "home_5.kitchen.cooking-area-001": ((28, 36), (27, 36), N),
    "home_5.kitchen.refrigerator-001": ((28, 37), (27, 37), B),
    "home_5.living_room.common-room-table-001": ((27, 38), (26, 38), B),
    "home_5.living_room.shelf-001": ((26, 37), (26, 36), N),
    "home_5.bathroom.toilet-001": ((28, 42), (27, 42), B),
    "home_6.living_room.common-room-table-001": ((31, 38), (31, 39), B),
    "home_6.living_room.harp-001": ((31, 36), (31, 37), B),
    "home_6.living_room.shelf-001": ((32, 36), (32, 37), B),
    "home_6.kitchen.cooking-area-001": ((33, 36), (33, 37), B),
    "home_6.kitchen.refrigerator-001": ((33, 38), (32, 38), B),
    "home_6.bathroom.bathroom-sink-001": ((33, 43), (32, 43), B),
    "home_6.bathroom.shower-001": ((33, 44), (32, 44), B),
    "home_6.bedroom.bed-001": ((30, 43), (30, 44), B),
    "home_6.bedroom.closet-001": ((31, 43), (31, 44), B),
    "home_6.garden.garden-chair-001": ((33, 45), (32, 45), B),
    "hall.public_service.public-counter-001": ((45, 39), (45, 40), B),
    "hall.administration.administration-desk-001": ((44, 41), (43, 41), B),
    "hall.council.council-table-001": ((44, 43), (43, 43), B),
    "home_7.bathroom.bathroom-sink-001": ((58, 37), (57, 37), N),
    "home_7.bathroom.shower-001": ((58, 39), (58, 40), B),
    "home_7.bathroom.toilet-001": ((58, 38), (57, 38), B),
    "home_7.bedroom.bed-001": ((57, 41), (58, 41), N),
    "home_7.bedroom.closet-001": ((58, 41), (57, 41), N),
    "home_7.bedroom.desk-001": ((53, 41), (54, 41), B),
    "home_7.kitchen.cooking-area-001": ((56, 37), (57, 37), B),
    "home_7.kitchen.refrigerator-001": ((56, 38), (57, 38), B),
    "home_7.living_room.common-room-table-001": ((53, 37), (54, 37), B),
    "home_7.living_room.shelf-001": ((53, 36), (54, 36), B),
    "home_8.bedroom.bed-001": ((63, 41), (62, 41), B),
    "home_8.bedroom.desk-001": ((65, 41), (66, 41), N),
    "home_8.kitchen.cooking-area-001": ((63, 37), (62, 37), B),
    "home_8.kitchen.refrigerator-001": ((63, 38), (62, 38), B),
    "home_8.living_room.common-room-table-001": ((64, 37), (64, 36), B),
    "home_8.living_room.shelf-001": ((66, 36), (66, 37), N),
    "home_8.bathroom.toilet-001": ((61, 38), (61, 39), B),
    "home_9.bathroom.bathroom-sink-001": ((71, 37), (71, 38), N),
    "home_9.bathroom.shower-001": ((71, 39), (71, 40), N),
    "home_9.bathroom.toilet-001": ((72, 38), (71, 38), B),
    "home_9.bedroom.bed-001": ((72, 42), (73, 42), B),
    "home_9.garden.garden-chair-001": ((75, 44), (75, 45), N),
    "home_9.kitchen.cooking-area-001": ((73, 37), (73, 36), B),
    "home_9.kitchen.refrigerator-001": ((73, 39), (73, 40), B),
    "home_9.living_room.common-room-table-001": ((75, 38), (75, 37), N),
    "home_9.living_room.harp-001": ((75, 37), (75, 38), N),
    "home_9.living_room.shelf-001": ((76, 37), (75, 37), B),
    "home_10.bathroom.bathroom-sink-001": ((78, 37), (78, 38), N),
    "home_10.bathroom.shower-001": ((78, 39), (78, 38), B),
    "home_10.bathroom.toilet-001": ((79, 38), (80, 38), B),
    "home_10.bedroom.bed-001": ((80, 41), (80, 40), B),
    "home_10.bedroom.closet-001": ((78, 42), (78, 43), B),
    "home_10.bedroom.desk-001": ((82, 41), (82, 40), N),
    "home_10.kitchen.cooking-area-001": ((81, 37), (82, 37), N),
    "home_10.kitchen.refrigerator-001": ((80, 38), (80, 39), N),
    "home_10.living_room.common-room-table-001": ((82, 38), (82, 37), N),
    "home_10.living_room.shelf-001": ((82, 36), (82, 37), N),
}

ENTRANCES = {
    "Home 2": (6, 46), "Home 3": (13, 46), "Home 4": (23, 46),
    "Home 5": (27, 46), "Home 6": (32, 46), "Town Hall": (45, 46),
    "Home 7": (56, 46), "Home 8": (63, 46), "Home 9": (73, 46),
    "Home 10": (81, 46),
}
SPAWNS = {
    "Home 2": ((5, 37), "home_2.main_room"),
    "Home 3": ((13, 37), "home_3.main_room"),
    "Home 4": ((22, 37), "home_4.main_room"),
    "Home 5": ((27, 44), "home_5.bedroom"),
    "Home 6": ((32, 43), "home_6.bedroom"),
    "Town Hall": ((47, 39), "hall.public_service"),
    "Home 7": ((54, 41), "home_7.bedroom"),
    "Home 8": ((66, 41), "home_8.bedroom"),
    "Home 9": ((73, 42), "home_9.bedroom"),
    "Home 10": ((82, 41), "home_10.bedroom"),
}
# Semantic id, sector, zone, cells, visible support role.
BLOCKERS = (
    ("home_2.bed-blocker.reference", "Home 2", "home_2.main_room", ((6, 37), (7, 37)), "bed"),
    ("home_3.bed-blocker.reference", "Home 3", "home_3.main_room", ((14, 37), (15, 37)), "bed"),
    ("home_4.bed-blocker.reference", "Home 4", "home_4.main_room", ((23, 37),), "bed"),
    ("home_5.storage-blocker.reference", "Home 5", "home_5.bedroom", ((26, 42),), "storage"),
    ("home_6.analysis-desk-blocker.reference", "Home 6", "home_6.bedroom", ((31, 42),), "analysis-desk"),
    ("home_7.filing-blocker.reference", "Home 7", "home_7.bedroom", ((55, 42),), "filing"),
    ("home_8.wardrobe-blocker.reference", "Home 8", "home_8.bedroom", ((61, 42),), "wardrobe"),
    ("home_9.wardrobe-blocker.reference", "Home 9", "home_9.bedroom", ((75, 42),), "wardrobe"),
    ("home_10.filing-blocker.reference", "Home 10", "home_10.bedroom", ((81, 41),), "filing"),
)

ROWHOUSE_COLLISION_PATTERN = (
    "#####", "#...#", "#...#", "#...#", "#...#", "#...#",
    "#...#", "#...#", ".....", ".....", ".....", ".....",
)


def migrate_rowhouse_collision(path: Path = COLLISION_BLUEPRINT_PATH) -> dict[str, int]:
    """Rewrite only the Home 4–6 block as three deterministic five-cell homes."""
    source = Path(path).expanduser().resolve(strict=True)
    data = json.loads(source.read_text(encoding="utf-8"))
    blocked = {tuple(point) for point in data["blocked"]}
    walkable = {tuple(point) for point in data["walkable"]}
    target = {(x, y) for y in range(35, 47) for x in range(20, 35)}
    blocked.difference_update(target)
    walkable.difference_update(target)
    wall_cells: set[tuple[int, int]] = set()
    for left in (20, 25, 30):
        for row, pattern in enumerate(ROWHOUSE_COLLISION_PATTERN, 35):
            for offset, token in enumerate(pattern):
                cell = left + offset, row
                (blocked if token == "#" else walkable).add(cell)
                if token == "#":
                    wall_cells.add(cell)
    for semantic_id, (cell, stance, policy) in INTERACTION_LAYOUT.items():
        if semantic_id.startswith(("home_4.", "home_5.", "home_6.")):
            blocked.discard(stance)
            walkable.add(stance)
            (blocked if policy == B else walkable).add(cell)
            (walkable if policy == B else blocked).discard(cell)
    for _semantic_id, sector, _zone, cells, _role in BLOCKERS:
        if sector in {"Home 4", "Home 5", "Home 6"}:
            for cell in cells:
                walkable.discard(cell)
                blocked.add(cell)
    for sector in ("Home 4", "Home 5", "Home 6"):
        points = (ENTRANCES[sector], SPAWNS[sector][0])
        for point in points:
            blocked.discard(point)
            walkable.add(point)
    if not wall_cells <= blocked:
        raise ValueError("rowhouse semantics reopened a visual wall")
    if blocked & walkable or len(blocked | walkable) != 88 * 48:
        raise ValueError("rowhouse collision migration lost grid parity")
    labels, _sizes = semantic_graph.components([
        [(x, y) in blocked for x in range(88)] for y in range(48)
    ])
    for sector in ("Home 4", "Home 5", "Home 6"):
        prefix = sector.lower().replace(" ", "_") + "."
        required = {ENTRANCES[sector], SPAWNS[sector][0]} | {
            stance for key, (_cell, stance, _policy) in INTERACTION_LAYOUT.items()
            if key.startswith(prefix)
        }
        if len({labels.get(point) for point in required}) != 1:
            raise ValueError(f"{sector} is not reachable from its entrance")
    data["blocked"] = [list(point) for point in sorted(blocked, key=lambda p: (p[1], p[0]))]
    data["walkable"] = [list(point) for point in sorted(walkable, key=lambda p: (p[1], p[0]))]
    temporary = source.with_name(f".{source.name}.tmp")
    temporary.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(source)
    return {"blocked": len(blocked), "walkable": len(walkable)}


def _properties(item: dict) -> dict:
    return authoring.properties(item.get("properties"))


def _set_property(item: dict, name: str, value: object) -> None:
    props = [prop for prop in item.get("properties", []) if prop.get("name") != name]
    kind = "bool" if isinstance(value, bool) else "int" if isinstance(value, int) else "string"
    props.append({"name": name, "type": kind, "value": value})
    item["properties"] = sorted(props, key=lambda prop: prop["name"])


def _runs(cells: frozenset[tuple[int, int]]) -> list[tuple[int, int, int, int]]:
    result = []
    for y in sorted({point[1] for point in cells}):
        xs = sorted(x for x, row in cells if row == y)
        left = previous = xs[0]
        for x in xs[1:]:
            if x != previous + 1:
                result.append((left, y, previous, y))
                left = x
            previous = x
        result.append((left, y, previous, y))
    return result


def _max_object_id(tmj: dict) -> int:
    values = [0]
    for layer in tmj.get("layers", []):
        values.extend(item.get("id", 0) for item in layer.get("objects", []))
        for child in layer.get("layers", []):
            values.extend(item.get("id", 0) for item in child.get("objects", []))
    return max(values)


def _art_coverage(item: dict) -> set[tuple[int, int]]:
    values = _properties(item)
    x, y = item["x"], item["y"]
    width, height = item.get("width", 0), item.get("height", 0)
    scale = values.get("display_scale", 1)
    anchor_x, anchor_y = values.get("anchor_x", 0.5), values.get("anchor_y", 1)
    left, top = x - width * scale * anchor_x, y - height * scale * anchor_y
    right = x + width * scale * (1 - anchor_x)
    bottom = y + height * scale * (1 - anchor_y)
    result = {(int(x // PIXEL_SIZE), int(y // PIXEL_SIZE))}
    for cell_y in range(
        math.floor(top / PIXEL_SIZE), math.floor((bottom - 1e-6) / PIXEL_SIZE) + 1,
    ):
        for cell_x in range(
            math.floor(left / PIXEL_SIZE), math.floor((right - 1e-6) / PIXEL_SIZE) + 1,
        ):
            result.add((cell_x, cell_y))
    return result


def _nearest_art(
    depth: dict, parts: list[dict], sector: str, zone: str,
    role: str, cell: tuple[int, int], used: set[int],
) -> dict:
    values = _properties(parts[0]) if parts else {}
    art_id, art_key = values.get("art_object_id"), values.get("art_asset_key")
    available = [item for item in depth.get("objects", []) if item.get("visible") is not False]
    exact = next((item for item in available if item.get("id") == art_id), None)
    candidates = [
        item for item in available
        if _properties(item).get("sector") == sector
        and (
            (isinstance(art_key, str) and _properties(item).get("asset_key") == art_key)
            or _properties(item).get("semantic_type") == role
        )
    ]
    if exact is not None and exact.get("id") not in used:
        return exact
    candidates = [item for item in candidates if item.get("id") not in used]
    if not candidates:
        raise ValueError(f"missing south support art: {sector} / {zone} / {role}")
    return min(
        candidates,
        key=lambda item: abs(item["x"] / PIXEL_SIZE - cell[0])
        + abs(item["y"] / PIXEL_SIZE - cell[1]),
    )


def _align_art(
    art: dict, sector: str, zone: str, role: str,
    cells: tuple[tuple[int, int], ...], relocate: bool,
) -> None:
    distance = min(
        abs(cell[0] - point[0]) + abs(cell[1] - point[1])
        for cell in cells for point in _art_coverage(art)
    )
    if relocate and distance > 1:
        x, y = cells[0]
        art["x"], art["y"] = x * PIXEL_SIZE + 16, (y + 1) * PIXEL_SIZE
    _set_property(art, "sector", sector)
    _set_property(art, "zone", zone)
    _set_property(art, "semantic_type", role)
    _set_property(art, "reference_semantic_support", True)


def apply_spec_sector_rects(spec: dict) -> None:
    """Snap candidate south sectors to their exact traced visual footprints."""
    sectors = {item.get("name"): item for item in spec.get("sectors", [])}
    missing = sorted(SOUTH_SECTORS - set(sectors))
    if missing:
        raise ValueError(f"town spec is missing south sectors: {missing}")
    for sector, rect in SECTOR_RECTS.items():
        sectors[sector]["rect"] = list(rect)


def apply_south_reference_migration(
    tmj: dict, *, collision: list[list[bool]] | None = None,
    relocate_support_art: bool = True,
) -> frozenset[int]:
    """Replace south semantics while preserving canonical collision bit-for-bit."""
    collision = collision or semantic_graph.read_collision(COLLISION_PATH)
    group = next(
        layer for layer in tmj.get("layers", []) if layer.get("name") == authoring.GROUP_NAME
    )
    children = {layer["name"]: layer for layer in group.get("layers", [])}
    depth = next(layer for layer in tmj["layers"] if layer.get("name") == "Depth Props")
    if set(children) != set(authoring.AUTHORING_LAYERS):
        raise ValueError("reference map has an incomplete Authoring group")

    interaction_parts: dict[str, list[dict]] = defaultdict(list)
    for item in children["Interactions"].get("objects", []):
        values = _properties(item)
        if values.get("sector") in SOUTH_SECTORS:
            interaction_parts[values.get("interaction", values["semantic_id"])].append(item)
    if set(interaction_parts) != set(INTERACTION_LAYOUT):
        missing = sorted(set(INTERACTION_LAYOUT) - set(interaction_parts))
        extra = sorted(set(interaction_parts) - set(INTERACTION_LAYOUT))
        raise ValueError(f"south interaction contract changed; missing={missing}, extra={extra}")

    for name in ("Zones", "Interactions", "Blockers"):
        children[name]["objects"] = [
            item for item in children[name].get("objects", [])
            if _properties(item).get("sector") not in SOUTH_SECTORS
        ]
    next_id = _max_object_id(tmj) + 1

    def add(layer_name: str, semantic_id: str, x: int, y: int, **values) -> None:
        nonlocal next_id
        children[layer_name]["objects"].append(
            authoring.make_authoring_object(next_id, semantic_id, x, y, **values)
        )
        next_id += 1

    for zone, (sector, room_type, cells) in ZONE_DEFINITIONS.items():
        for index, (left, top, right, bottom) in enumerate(_runs(cells), 1):
            add(
                "Zones", f"{zone}.reference-shape-{index:03d}",
                left * PIXEL_SIZE, top * PIXEL_SIZE,
                width=(right - left + 1) * PIXEL_SIZE,
                height=(bottom - top + 1) * PIXEL_SIZE,
                sector=sector, zone=zone, room_type=room_type,
            )

    used_art: set[int] = set()
    for interaction_id, (cell, stance, policy) in INTERACTION_LAYOUT.items():
        parts = interaction_parts[interaction_id]
        values = _properties(parts[0])
        sector, zone, role = (
            values["sector"], values["zone"], values["interaction_type"]
        )
        if cell not in ZONE_DEFINITIONS[zone][2]:
            raise ValueError(f"{interaction_id} falls outside {zone}")
        is_blocked = collision[cell[1]][cell[0]]
        if is_blocked != (policy == B) or collision[stance[1]][stance[0]] \
                or abs(cell[0] - stance[0]) + abs(cell[1] - stance[1]) != 1:
            raise ValueError(f"{interaction_id} disagrees with canonical collision")
        art = _nearest_art(depth, parts, sector, zone, role, cell, used_art)
        used_art.add(art["id"])
        _align_art(art, sector, zone, role, (cell,), relocate_support_art)
        add(
            "Interactions", f"{interaction_id}.reference-shape-001",
            cell[0] * PIXEL_SIZE, cell[1] * PIXEL_SIZE,
            width=PIXEL_SIZE, height=PIXEL_SIZE, interaction=interaction_id,
            sector=sector, zone=zone, interaction_type=role,
            art_layer="Depth Props", art_object_id=art["id"],
            allowed_room_types=values["allowed_room_types"],
            blocker_policy=policy, stance_x=stance[0], stance_y=stance[1],
        )

    for base_id, sector, zone, cells, role in BLOCKERS:
        art = _nearest_art(depth, [], sector, zone, role, cells[0], used_art)
        used_art.add(art["id"])
        _align_art(art, sector, zone, role, cells, relocate_support_art)
        for index, (x, y) in enumerate(cells, 1):
            if not collision[y][x] or (x, y) not in ZONE_DEFINITIONS[zone][2]:
                raise ValueError(f"{base_id} disagrees with canonical collision")
            add(
                "Blockers", f"{base_id}-shape-{index:03d}",
                x * PIXEL_SIZE, y * PIXEL_SIZE, width=PIXEL_SIZE,
                height=PIXEL_SIZE, sector=sector, zone=zone,
                art_layer="Depth Props", art_object_id=art["id"],
                blocker_policy=B,
            )

    for layer_name, coordinates in (("Entrances", ENTRANCES), ("Spawns", SPAWNS)):
        indexed = {
            _properties(item).get("sector"): item
            for item in children[layer_name].get("objects", [])
            if _properties(item).get("sector") in SOUTH_SECTORS
        }
        if set(indexed) != SOUTH_SECTORS:
            raise ValueError(f"south {layer_name.lower()} contract changed")
        for sector, value in coordinates.items():
            point, zone = value if layer_name == "Spawns" else (value, None)
            item = indexed[sector]
            item["x"], item["y"] = point[0] * PIXEL_SIZE, point[1] * PIXEL_SIZE
            if collision[point[1]][point[0]]:
                raise ValueError(f"{sector} {layer_name.lower()} is blocked")
            if zone is not None:
                _set_property(item, "zone", zone)
                if point not in ZONE_DEFINITIONS[zone][2]:
                    raise ValueError(f"{sector} spawn falls outside {zone}")

    tmj["nextobjectid"] = next_id
    return frozenset(used_art)
