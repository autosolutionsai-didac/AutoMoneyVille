"""Formal planted-square and street furniture for the reference map."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

Placement = tuple[str, str, str, str, str, int, int]
Point = tuple[int, int]
Rect = tuple[int, int, int, int]

TREE_KEYS = (
    "prop.landscape.conifer_tall_01",
    "prop.landscape.conifer_tall_02",
    "prop.landscape.conifer_tall_03",
    "prop.landscape.tree_cluster_15",
)
BUSH_KEYS = tuple(f"prop.landscape.flower_bush_0{number}" for number in (1, 3, 5, 7))
HEDGE_HORIZONTAL = "prop.landscape.hedge_flowered_middle"
HEDGE_VERTICAL = (
    "prop.landscape.hedge_flowered_vertical_mid",
    "prop.landscape.hedge_flowered_vertical_mid_alt",
)
BENCH = "prop.garden.bench_horizontal"
LAMP = "prop.street.lamp_05"
FOUNTAIN = "prop.plaza.fountain_round_blue"
NOTICE_BOARD = "prop.office.notice_board"

PLAZA_TREE_POINTS = (
    (99, 47), (103, 47), (107, 47), (99, 52), (103, 52), (107, 52),
    (125, 47), (129, 47), (133, 47), (125, 52), (129, 52), (133, 52),
    (99, 63), (103, 63), (107, 63), (99, 69), (103, 69), (107, 69),
    (125, 63), (129, 63), (133, 63), (125, 69), (129, 69), (133, 69),
)
PLAZA_BUSH_POINTS: tuple[Point, ...] = ()
PLAZA_BENCH_POINTS = (
    (100, 57), (106, 57), (126, 57), (132, 57),
    (112, 48), (122, 48), (112, 68), (122, 68),
)
PLAZA_LAMP_POINTS = ((96, 44), (136, 44), (96, 74), (136, 74))
AVENUE_LAMP_POINTS = (
    *((x, y) for y in (38, 43, 74, 78)
      for x in (20, 54, 64, 93, 136, 144, 158)),
)
AVENUE_BENCH_POINTS = (
    *((x, 38) for x in (25, 51, 65, 92, 135, 157)),
    *((x, 74) for x in (25, 51, 65, 94, 135, 157)),
)


def _boundary(cells: set[Point]) -> set[Point]:
    return {
        (x, y)
        for x, y in cells
        if any(
            neighbor not in cells
            for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
        )
    }


def _hedge_key(point: Point, cells: set[Point]) -> str:
    x, y = point
    vertical_edge = (x - 1, y) not in cells or (x + 1, y) not in cells
    horizontal_edge = (x, y - 1) not in cells or (x, y + 1) not in cells
    if vertical_edge and not horizontal_edge:
        return HEDGE_VERTICAL[(x + y) % len(HEDGE_VERTICAL)]
    return HEDGE_HORIZONTAL


def placements(
    owner: Callable[[int, int], str],
    sector_zone: Mapping[str, str],
    water_cells: set[Point] | frozenset[Point],
    structure_rects: Sequence[Rect],
    inside: Callable[[Point, Rect], bool],
    bed_cells: Sequence[set[Point] | frozenset[Point]],
) -> tuple[Placement, ...]:
    """Return dense, deterministic plaza beds plus the avenue lamp rhythm."""
    result: list[Placement] = []
    zone = sector_zone["Central Plaza"]
    reserved = (
        set(PLAZA_TREE_POINTS) | set(PLAZA_BUSH_POINTS) | set(PLAZA_BENCH_POINTS)
    )
    for index, cells_value in enumerate(bed_cells, 1):
        cells = set(cells_value)
        for x, y in sorted(_boundary(cells), key=lambda point: (point[1], point[0])):
            if (x, y) in reserved:
                continue
            result.append((
                "Central Plaza", zone, "plaza-hedge", f"formal bed {index}",
                _hedge_key((x, y), cells), x, y,
            ))
    for index, (x, y) in enumerate(PLAZA_TREE_POINTS):
        result.append((
            "Central Plaza", zone, "plaza-tree", "quadrant grove",
            TREE_KEYS[index % len(TREE_KEYS)], x, y,
        ))
    for x, y in PLAZA_BENCH_POINTS:
        result.append(("Central Plaza", zone, "bench", "quadrant seat", BENCH, x, y))
    for index, (x, y) in enumerate(PLAZA_BUSH_POINTS):
        result.append((
            "Central Plaza", zone, "plaza-flower", "quadrant understory",
            BUSH_KEYS[index % len(BUSH_KEYS)], x, y,
        ))
    for x, y in PLAZA_LAMP_POINTS:
        result.append(("Central Plaza", zone, "lamp", "plaza lamp", LAMP, x, y))
    result.extend((
        ("Central Plaza", zone, "fountain", "central fountain", FOUNTAIN, 118, 63),
        (
            "Central Plaza", zone, "notice-board", "civic notice point",
            NOTICE_BOARD, 111, 54,
        ),
    ))
    for x, y in AVENUE_LAMP_POINTS:
        sector = owner(x, y)
        point = (x, y)
        if point in water_cells or any(inside(point, rect) for rect in structure_rects):
            continue
        result.append((
            sector, sector_zone[sector], "lamp", "street rhythm", LAMP, x, y,
        ))
    for x, y in AVENUE_BENCH_POINTS:
        sector = owner(x, y)
        point = (x, y)
        if point in water_cells or any(inside(point, rect) for rect in structure_rects):
            continue
        result.append((
            sector, sector_zone[sector], "bench", "avenue resting point", BENCH, x, y,
        ))
    return tuple(result)


def validate() -> None:
    if len(PLAZA_TREE_POINTS) != 24 or PLAZA_BUSH_POINTS:
        raise ValueError("Central Plaza requires six tree masses per quadrant")
    if len(set(PLAZA_TREE_POINTS)) != 24 or len(set(PLAZA_BENCH_POINTS)) != 8:
        raise ValueError("Central Plaza furniture points must be unique")
    if not all(95 <= x < 137 and 43 <= y < 75 for x, y in PLAZA_TREE_POINTS):
        raise ValueError("Central Plaza trees escaped the measured parcel")


validate()
