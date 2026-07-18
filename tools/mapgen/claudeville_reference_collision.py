"""Collision compiler for the target-photo Claudeville sprite map."""

from __future__ import annotations

import math
from collections import defaultdict

try:
    from tools.mapgen import claudeville_reference_bank as reference_bank
    from tools.mapgen import claudeville_reference_home1 as reference_home
    from tools.mapgen import claudeville_reference_layout as layout
    from tools.mapgen import claudeville_reference_middle as reference_middle
    from tools.mapgen import claudeville_reference_stamps as reference_stamps
    from tools.mapgen import claudeville_tiled_authoring as authoring
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_reference_bank as reference_bank  # type: ignore[no-redef]
    import claudeville_reference_home1 as reference_home  # type: ignore[no-redef]
    import claudeville_reference_layout as layout  # type: ignore[no-redef]
    import claudeville_reference_middle as reference_middle  # type: ignore[no-redef]
    import claudeville_reference_stamps as reference_stamps  # type: ignore[no-redef]
    import claudeville_tiled_authoring as authoring  # type: ignore[no-redef]


PIXEL_SIZE = 32
DEEP_FOOTPRINT_TOKENS = (
    "bed", "bath", "shower", "table", "sofa", "lounge-seating",
    "workbench", "work-machine", "machine", "simulator",
)
WIDE_FOOTPRINT_TOKENS = ("counter", "bench", "shelf-run")
NONBLOCKING_TOKENS = (
    "mirror", "wall-", "notice", "chart", "map", "painting", "runner-panel",
    "planning-board", "teaching-board", "class-board", "rate-notice",
    "terminal", "register", "paper", "linen", "small-appliance", "decor-",
    "design-facade", "decor-sprite-composition", "resident-hobby",
)


def _props(item: dict) -> dict:
    return authoring.properties(item.get("properties"))


def _layer(tmj: dict, name: str) -> dict:
    return next(layer for layer in tmj["layers"] if layer.get("name") == name)


def _foot(item: dict) -> tuple[int, int]:
    return int(item["x"] // PIXEL_SIZE), int(item["y"] // PIXEL_SIZE)


def _object_cells(item: dict) -> set[tuple[int, int]]:
    """Return the logical floor footprint, excluding transparent sprite height."""
    values = _props(item)
    width, height = item.get("width", 0), item.get("height", 0)
    scale = values.get("display_scale", 1)
    numeric = (item.get("x"), item.get("y"), width, height, scale)
    if not all(isinstance(value, (int, float)) and math.isfinite(value)
               for value in numeric) or width <= 0 or height <= 0 or scale <= 0:
        return {_foot(item)}
    width *= scale
    height *= scale
    kind = str(values.get("semantic_type", ""))
    foot_x, foot_y = _foot(item)
    # Native-16 sprites can deliberately sit halfway between two 32 px
    # movement nodes.  A narrow fixture in that pocket does not cover either
    # node, so assigning it to floor(x / 32) would invent a collision (or make
    # the compiler reopen the fixture as a fake corridor).
    if width < PIXEL_SIZE * 0.7 and math.isclose(item["x"] % PIXEL_SIZE, PIXEL_SIZE / 2):
        return set()
    # Logical movement nodes are a full 32 px apart.  Round the displayed
    # footprint to that grid instead of using ceil: a deliberately modest
    # 1.1x art scale must not turn one chair into a two-cell barricade, while
    # genuinely wide/deep furniture still expands to every occupied node.
    columns = max(1, round(width / PIXEL_SIZE))
    rows = max(1, round(height / PIXEL_SIZE))
    if not any(token in kind for token in DEEP_FOOTPRINT_TOKENS):
        rows = 1
    if columns > 1 and not any(
        token in kind for token in (*DEEP_FOOTPRINT_TOKENS, *WIDE_FOOTPRINT_TOKENS)
    ):
        columns = 1
    left = foot_x - (columns - 1) // 2
    top = foot_y - rows + 1
    return {
        (cell_x, cell_y)
        for cell_y in range(top, foot_y + 1)
        for cell_x in range(left, left + columns)
        if 0 <= cell_x < 88 and 0 <= cell_y < 48
    }


def base_blocked(tmj: dict) -> set[tuple[int, int]]:
    """Block visible walls, water, the world rim, and outdoor solid props."""
    blocked = {(x, y) for x in range(88) for y in range(48)
               if x in {0, 87} or y in {0, 47}}
    walls = _layer(tmj, "Wall")["data"]
    for y in range(48):
        for x in range(88):
            if any(walls[(2 * y + dy) * 176 + 2 * x + dx]
                   for dy in (0, 1) for dx in (0, 1)):
                blocked.add((x, y))
    for visual_y, runs in layout.WATER_RUNS.items():
        for left, right in runs:
            blocked.update((x // 2, visual_y // 2) for x in range(left, right))
    for item in _layer(tmj, "Depth Props")["objects"]:
        kind = str(_props(item).get("semantic_type", ""))
        if any(token in kind for token in (
            "tree", "hedge", "forest-wall", "fountain", "bench", "lamp",
        )):
            blocked.add(_foot(item))
    blocked.update(reference_stamps.COLLISION_BLOCKS)
    blocked.update(reference_bank.BANK_COLLISION_BLOCKS)
    blocked.update(reference_middle.WORKSHOP_COLLISION_BLOCKS)
    return blocked


def _components(blocked: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = {(x, y) for y in range(48) for x in range(88) if (x, y) not in blocked}
    result = []
    while remaining:
        found, pending = set(), [next(iter(remaining))]
        while pending:
            point = pending.pop()
            if point in found or point not in remaining:
                continue
            found.add(point)
            x, y = point
            pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
        remaining -= found
        result.append(found)
    return result


def _authoring(tmj: dict) -> tuple[dict, set, set, set]:
    group = _layer(tmj, authoring.GROUP_NAME)
    children = {layer["name"]: layer for layer in group["layers"]}
    zones: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for item in children["Zones"]["objects"]:
        values = _props(item)
        for y in range(item["y"] // PIXEL_SIZE,
                       (item["y"] + item["height"]) // PIXEL_SIZE):
            for x in range(item["x"] // PIXEL_SIZE,
                           (item["x"] + item["width"]) // PIXEL_SIZE):
                zones[values.get("zone", values["semantic_id"])].add((x, y))
    required, nonblocking, clear = set(), set(), set()
    for item in children["Interactions"]["objects"]:
        values, point = _props(item), _foot(item)
        (required if values.get("blocker_policy") == "require-blocked"
         else nonblocking).add(point)
        clear.add((values["stance_x"], values["stance_y"]))
    for name in ("Entrances", "Spawns"):
        clear.update(_foot(item) for item in children[name]["objects"])
    return zones, required, nonblocking, clear


def _solid_prop_cells(tmj: dict) -> list[tuple[int, int]]:
    cells = set()
    for item in _layer(tmj, "Depth Props")["objects"]:
        kind = str(_props(item).get("semantic_type", ""))
        if kind and not any(token in kind for token in NONBLOCKING_TOKENS):
            cells.update(_object_cells(item))
    return sorted(cells, key=lambda point: (point[1], point[0]))


def _partition_circulation() -> set[tuple[int, int]]:
    """Keep each visible internal doorway and its landing traversable."""
    clear: set[tuple[int, int]] = set()
    for _sector, orientation, fixed, _start, _end, gaps in reference_home.PARTITIONS:
        if orientation == "horizontal":
            for x in {gap // 2 for gap in gaps}:
                clear.update(
                    ((x, fixed // 2 - 1), (x, fixed // 2), (x, fixed // 2 + 1))
                )
        else:
            for y in {gap // 2 for gap in gaps}:
                clear.update(((fixed // 2, y), (fixed // 2 + 1, y)))
    return clear


def compile_collision(tmj: dict) -> list[list[bool]]:
    """Maximize solid sprite footprints without splitting a navigable room."""
    blocked = base_blocked(tmj)
    zones, required, nonblocking, clear = _authoring(tmj)
    clear.update(_partition_circulation() - required)
    blocked.update(required)
    blocked -= clear | nonblocking
    components = _components(blocked)
    main = max(components, key=len)
    blocked.update(set().union(*(part for part in components if part is not main)))
    for point in _solid_prop_cells(tmj):
        if point in blocked or point in clear or point in nonblocking:
            continue
        owners = [cells for cells in zones.values() if point in cells]
        if any(sum(cell not in blocked for cell in cells) <= 2 for cells in owners):
            continue
        blocked.add(point)
        if len(_components(blocked)) != 1:
            blocked.remove(point)
    return [[(x, y) in blocked for x in range(88)] for y in range(48)]
