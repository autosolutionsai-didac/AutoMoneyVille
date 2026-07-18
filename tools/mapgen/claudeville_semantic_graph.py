"""Small deterministic graph and collision helpers for Claudeville semantics."""

from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path

LOGICAL_WIDTH, LOGICAL_HEIGHT = 88, 48
BLOCKING_DEPTH_PREFIXES = (
    "prop.landscape.tree_",
    "prop.garden.bench_",
    "prop.street.mailbox",
)
Point = tuple[int, int]


class SemanticGraphError(ValueError):
    """Raised when collision or override inputs are malformed."""


def _point(value: object, label: str) -> Point:
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        raise SemanticGraphError(f"{label} must be an integer point")
    point = value[0], value[1]
    if not (0 <= point[0] < LOGICAL_WIDTH and 0 <= point[1] < LOGICAL_HEIGHT):
        raise SemanticGraphError(f"{label} is outside the logical grid")
    return point


def sector_cells(spec: dict) -> dict[str, set[Point]]:
    """Expand and validate each inclusive logical sector rectangle."""
    result: dict[str, set[Point]] = {}
    for sector in spec.get("sectors", []):
        if not isinstance(sector, dict) or not isinstance(sector.get("name"), str):
            raise SemanticGraphError("town sectors are malformed")
        value = sector.get("rect")
        if not isinstance(value, list) or len(value) != 4:
            raise SemanticGraphError(f"sector {sector['name']} needs one logical rect")
        x0, y0, x1, y1 = value
        if not (0 <= x0 <= x1 < LOGICAL_WIDTH and 0 <= y0 <= y1 < LOGICAL_HEIGHT):
            raise SemanticGraphError(f"sector {sector['name']} rect is invalid")
        result[sector["name"]] = {
            (x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
        }
    return result


def prop_cells(layout, *, blocked_only: bool = False) -> set[Point]:
    """Return logical cells occupied by authored purpose props."""
    return {
        _point((prop.visual_x // 2, prop.visual_y // 2), f"{sector} prop")
        for sector, props in layout.PURPOSE_PROPS.items()
        for prop in props
        if not blocked_only or prop.blocks
    }


def authored_block_cells(layout) -> set[Point]:
    """Validate authored collision cells justified by visible landscaping."""
    return {
        _point(value, "authored scenery blocker")
        for value in getattr(layout, "SCENERY_BLOCK_CELLS", ())
    }


def depth_prop_blocks(tmj: dict) -> set[Point]:
    """Map physical depth props to their bottom-centre logical foot cells."""
    layer = next(
        (item for item in tmj.get("layers", []) if item.get("name") == "Depth Props"),
        None,
    )
    if layer is None:
        return set()
    if not isinstance(layer.get("objects"), list):
        raise SemanticGraphError("Depth Props must be an object layer")
    result: set[Point] = set()
    for item in layer["objects"]:
        properties = {
            prop.get("name"): prop.get("value")
            for prop in item.get("properties", [])
            if isinstance(prop, dict)
        }
        asset_key = properties.get("asset_key", "")
        blocks = properties.get("blocks") is True or (
            isinstance(asset_key, str) and asset_key.startswith(BLOCKING_DEPTH_PREFIXES)
        )
        if not blocks:
            continue
        x, y = item.get("x"), item.get("y")
        if any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            for value in (x, y)
        ):
            raise SemanticGraphError("blocking Depth Prop needs numeric x/y")
        result.add(
            (
                min(LOGICAL_WIDTH - 1, max(0, int(x) // 32)),
                min(LOGICAL_HEIGHT - 1, max(0, int(y) // 32)),
            )
        )
    return result


def has_visible_object_art(
    layers: dict[str, dict], layer_names: tuple[str, ...], point: Point
) -> bool:
    """Find visible authored pixels on an object cell or its cardinal art edge."""
    return any(
        layers[name]["data"][(2 * y + dy) * 176 + 2 * x + dx]
        for name in layer_names
        for x, y in (
            point,
            (point[0] - 1, point[1]),
            (point[0] + 1, point[1]),
            (point[0], point[1] - 1),
            (point[0], point[1] + 1),
        )
        if 0 <= x < LOGICAL_WIDTH and 0 <= y < LOGICAL_HEIGHT
        for dy in (0, 1)
        for dx in (0, 1)
    )


def has_tile(
    layers: dict[str, dict], layer_names: tuple[str, ...], point: Point
) -> bool:
    """Check the exact 2x2 visual footprint for one of the named tile layers."""
    x, y = point
    return any(
        layers[name]["data"][(2 * y + dy) * 176 + 2 * x + dx]
        for name in layer_names
        for dy in (0, 1)
        for dx in (0, 1)
    )


def select_object_stances(
    records: list[tuple[str, str, str, tuple[Point, ...], Point | None]],
    zone_cells: dict[str, set[Point]],
    owners: dict[str, str],
    collision: list[list[bool]],
) -> tuple[list[Point], list[dict]]:
    """Select truthful cardinal stances and report every unusable object."""
    stances: list[Point] = []
    failures: list[dict] = []
    for sector, zone, kind, points, preferred in records:
        raw = [preferred] if preferred is not None else []
        for x, y in points:
            raw.extend(
                (x + dx, y + dy)
                for dx, dy in ((0, 1), (-1, 0), (1, 0), (0, -1))
            )
        neighbors = tuple(dict.fromkeys(raw))
        cardinal = [
            point
            for point in neighbors
            if 0 <= point[0] < LOGICAL_WIDTH
            and 0 <= point[1] < LOGICAL_HEIGHT
            and any(
                abs(point[0] - x) + abs(point[1] - y) == 1 for x, y in points
            )
        ]
        owned_floor = set().union(
            *(
                cells
                for name, cells in zone_cells.items()
                if owners.get(name) == sector
            )
        )
        clear = [point for point in cardinal if not collision[point[1]][point[0]]]
        candidates = [point for point in clear if point in zone_cells[zone]]
        candidates = candidates or [point for point in clear if point in owned_floor]
        if candidates:
            stances.append(
                candidates[0]
                if preferred in candidates
                else sorted(set(candidates), key=lambda p: (p[1], p[0]))[0]
            )
            continue
        nearby = []
        for point in neighbors:
            if not (
                0 <= point[0] < LOGICAL_WIDTH
                and 0 <= point[1] < LOGICAL_HEIGHT
            ):
                state = "outside-grid"
            elif collision[point[1]][point[0]]:
                state = "blocked"
            elif point not in owned_floor:
                state = "outside-sector-floor"
            else:
                state = "non-cardinal"
            nearby.append({"point": list(point), "state": state})
        failures.append(
            {
                "sector": sector,
                "type": kind,
                "tiles": [list(point) for point in points],
                "nearby": nearby,
            }
        )
    return stances, failures


def read_collision(path: Path) -> list[list[bool]]:
    """Read the authoritative 88x48 collision CSV."""
    values = [
        token.strip() for token in Path(path).read_text(encoding="utf-8").split(",")
    ]
    if len(values) != LOGICAL_WIDTH * LOGICAL_HEIGHT or any(
        value not in ("0", "32125") for value in values
    ):
        raise SemanticGraphError("collision matrix has invalid dimensions or values")
    return [
        [values[y * LOGICAL_WIDTH + x] != "0" for x in range(LOGICAL_WIDTH)]
        for y in range(LOGICAL_HEIGHT)
    ]


def components(collision: list[list[bool]]) -> tuple[dict[Point, int], list[int]]:
    """Label every four-directional walkable component."""
    labels: dict[Point, int] = {}
    sizes: list[int] = []
    for y in range(LOGICAL_HEIGHT):
        for x in range(LOGICAL_WIDTH):
            start = x, y
            if collision[y][x] or start in labels:
                continue
            component = len(sizes)
            labels[start] = component
            queue, size = deque([start]), 0
            while queue:
                cx, cy = queue.popleft()
                size += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    point = cx + dx, cy + dy
                    if (
                        0 <= point[0] < LOGICAL_WIDTH
                        and 0 <= point[1] < LOGICAL_HEIGHT
                        and not collision[point[1]][point[0]]
                        and point not in labels
                    ):
                        labels[point] = component
                        queue.append(point)
            sizes.append(size)
    return labels, sizes


def compress(cells: set[Point]) -> list[list[int]]:
    """Compress cells into deterministic inclusive horizontal rectangles."""
    rows: dict[int, list[int]] = defaultdict(list)
    for x, y in cells:
        rows[y].append(x)
    result: list[list[int]] = []
    for y in sorted(rows):
        values = sorted(rows[y])
        start = previous = values[0]
        for x in values[1:]:
            if x != previous + 1:
                result.append([start, y, previous, y])
                start = x
            previous = x
        result.append([start, y, previous, y])
    return result


def preserved_points(
    overrides: dict, sectors: dict[str, set[Point]]
) -> tuple[list[list[int]], set[Point], set[Point]]:
    """Keep only outdoor, border and plaza overrides from the legacy world."""
    interior = set().union(
        *(cells for name, cells in sectors.items() if name != "Central Plaza")
    )
    plaza = sectors.get("Central Plaza", set())

    def keep(point: Point) -> bool:
        x, y = point
        return (
            x in (0, LOGICAL_WIDTH - 1)
            or y in (0, LOGICAL_HEIGHT - 1)
            or point in plaza
            or point not in interior
        )

    regions = deepcopy(overrides.get("blocked_regions", []))
    blocked = {
        _point(value, "preserved blocked point")
        for value in overrides.get("blocked", [])
    }
    walkable = {
        _point(value, "preserved walkable point")
        for value in overrides.get("walkable", [])
    }
    return (
        regions,
        {point for point in blocked if keep(point)},
        {point for point in walkable if keep(point)},
    )
