"""Hand-authored V2 landscaping for the reference north district."""

from __future__ import annotations

try:
    from tools.mapgen.claudeville_reference_layout import (
        BUILDINGS,
        MAIN_PATHS,
        PARCEL_PATHS,
        WATER_RUNS,
    )
except ModuleNotFoundError:  # Direct module execution.
    from claudeville_reference_layout import (  # type: ignore[no-redef]
        BUILDINGS,
        MAIN_PATHS,
        PARCEL_PATHS,
        WATER_RUNS,
    )


TREE_03 = "prop.landscape.conifer_tall_01"
TREE_05 = "prop.landscape.conifer_tall_02"
TREE_11 = "prop.landscape.conifer_tall_03"
TREE_15 = "prop.landscape.tree_cluster_15"
BUSH_01 = "prop.landscape.flower_bush_01"
BUSH_03 = "prop.landscape.flower_bush_03"
BUSH_05 = "prop.landscape.flower_bush_05"
BUSH_07 = "prop.landscape.flower_bush_07"
HEDGE_LEFT = "prop.landscape.hedge_flowered_left"
HEDGE_MIDDLE = "prop.landscape.hedge_flowered_middle"
HEDGE_RIGHT = "prop.landscape.hedge_flowered_right"
BENCH = "prop.garden.bench_horizontal"
LAMP_01 = "prop.street.lamp_01"
LAMP_03 = "prop.street.lamp_03"
LAMP_05 = "prop.street.lamp_05"

APPROVED_KEYS = frozenset(
    {
        TREE_03,
        TREE_05,
        TREE_11,
        TREE_15,
        BUSH_01,
        BUSH_03,
        BUSH_05,
        BUSH_07,
        HEDGE_LEFT,
        HEDGE_MIDDLE,
        HEDGE_RIGHT,
        BENCH,
        LAMP_01,
        LAMP_03,
        LAMP_05,
    }
)
TREE_KEYS = frozenset({TREE_03, TREE_05, TREE_11, TREE_15})

# Bounds include each parcel's adjacent northern perimeter but stop before the
# main avenue. The Home and University ranges deliberately overlap at the
# shared riverbank; sector ownership remains explicit in each placement.
TARGET_BOUNDS = {
    "Bank": (0, 0, 34, 34),
    "Home 1": (40, 0, 69, 34),
    "University": (66, 0, 106, 34),
}
VALID_ZONES = {
    "Bank": frozenset({"bank.waiting"}),
    "Home 1": frozenset({"home_1.garden"}),
    "University": frozenset(
        {
            "university.lecture",
            "university.study_lab",
            "university.cafeteria",
        }
    ),
}
STRUCTURE_RECTS = {
    "Bank": tuple(BUILDINGS["Bank"][key] for key in ("room", "facade", "entry")),
    "Home 1": tuple(BUILDINGS["Home 1"][key] for key in ("room", "facade", "entry")),
    "University": (
        *BUILDINGS["University"]["room_union"],
        *BUILDINGS["University"]["facade_union"],
        BUILDINGS["University"]["entry"],
    ),
}
TRACED_PATHS = MAIN_PATHS + PARCEL_PATHS

# sector, zone, semantic role, cluster, asset key, visual foot x, visual foot y
BASE_PLACEMENTS = (
    # Bank: the northwest canopy closes around the parcel in an uneven arc.
    ("Bank", "bank.waiting", "perimeter-tree", "northwest forest", TREE_05, 2, 7),
    ("Bank", "bank.waiting", "perimeter-tree", "northwest forest", TREE_11, 5, 5),
    ("Bank", "bank.waiting", "perimeter-tree", "northwest forest", TREE_15, 8, 8),
    ("Bank", "bank.waiting", "perimeter-tree", "northwest forest", TREE_03, 12, 6),
    ("Bank", "bank.waiting", "perimeter-tree", "northwest forest", TREE_11, 16, 9),
    ("Bank", "bank.waiting", "perimeter-tree", "northwest forest", TREE_05, 20, 7),
    ("Bank", "bank.waiting", "perimeter-tree", "west foundation grove", TREE_03, 7, 18),
    (
        "Bank",
        "bank.waiting",
        "perimeter-tree",
        "east foundation grove",
        TREE_15,
        30,
        20,
    ),
    ("Bank", "bank.waiting", "garden-plant", "west foundation strip", BUSH_01, 7, 28),
    ("Bank", "bank.waiting", "garden-plant", "east foundation strip", BUSH_07, 30, 28),
    ("Bank", "bank.waiting", "garden-plant", "west front garden", BUSH_05, 13, 31),
    ("Bank", "bank.waiting", "garden-plant", "east front garden", BUSH_03, 24, 31),
    ("Bank", "bank.waiting", "garden-seat", "west front garden", BENCH, 11, 31),
    ("Bank", "bank.waiting", "garden-seat", "east front garden", BENCH, 26, 31),
    ("Bank", "bank.waiting", "lamp", "west front garden", LAMP_05, 7, 31),
    ("Bank", "bank.waiting", "lamp", "east front garden", LAMP_05, 30, 31),
    # Home 1: riverbank trees gather in two loose groups, not a picket line.
    (
        "Home 1",
        "home_1.garden",
        "perimeter-tree",
        "west riverbank grove",
        TREE_11,
        42,
        3,
    ),
    (
        "Home 1",
        "home_1.garden",
        "perimeter-tree",
        "west riverbank grove",
        TREE_05,
        46,
        3,
    ),
    (
        "Home 1",
        "home_1.garden",
        "perimeter-tree",
        "west riverbank grove",
        TREE_15,
        48,
        2,
    ),
    (
        "Home 1",
        "home_1.garden",
        "perimeter-tree",
        "east riverbank grove",
        TREE_03,
        63,
        7,
    ),
    (
        "Home 1",
        "home_1.garden",
        "perimeter-tree",
        "east riverbank grove",
        TREE_11,
        67,
        7,
    ),
    ("Home 1", "home_1.garden", "perimeter-tree", "west side garden", TREE_03, 43, 18),
    ("Home 1", "home_1.garden", "perimeter-tree", "east side garden", TREE_05, 65, 20),
    (
        "Home 1",
        "home_1.garden",
        "garden-plant",
        "west foundation strip",
        BUSH_03,
        43,
        27,
    ),
    (
        "Home 1",
        "home_1.garden",
        "garden-plant",
        "east foundation strip",
        BUSH_07,
        65,
        27,
    ),
    ("Home 1", "home_1.garden", "garden-plant", "west front garden", BUSH_05, 49, 31),
    ("Home 1", "home_1.garden", "garden-plant", "east front garden", BUSH_01, 60, 31),
    ("Home 1", "home_1.garden", "garden-seat", "west front garden", BENCH, 47, 31),
    ("Home 1", "home_1.garden", "garden-seat", "east front garden", BENCH, 62, 31),
    ("Home 1", "home_1.garden", "lamp", "west front garden", LAMP_05, 43, 31),
    ("Home 1", "home_1.garden", "lamp", "east front garden", LAMP_05, 65, 31),
    # University: side groves overlap around the U-shaped campus and court.
    (
        "University",
        "university.lecture",
        "perimeter-tree",
        "west campus grove",
        TREE_11,
        68,
        5,
    ),
    (
        "University",
        "university.lecture",
        "perimeter-tree",
        "west campus grove",
        TREE_03,
        70,
        9,
    ),
    (
        "University",
        "university.lecture",
        "perimeter-tree",
        "west campus grove",
        TREE_15,
        69,
        17,
    ),
    (
        "University",
        "university.lecture",
        "perimeter-tree",
        "west campus grove",
        TREE_05,
        70,
        26,
    ),
    (
        "University",
        "university.study_lab",
        "perimeter-tree",
        "east campus grove",
        TREE_05,
        104,
        7,
    ),
    (
        "University",
        "university.study_lab",
        "perimeter-tree",
        "east campus grove",
        TREE_03,
        103,
        13,
    ),
    (
        "University",
        "university.study_lab",
        "perimeter-tree",
        "east campus grove",
        TREE_15,
        103,
        22,
    ),
    (
        "University",
        "university.study_lab",
        "perimeter-tree",
        "east campus grove",
        TREE_11,
        103,
        28,
    ),
    (
        "University",
        "university.cafeteria",
        "garden-plant",
        "west entry court",
        BUSH_03,
        83,
        22,
    ),
    (
        "University",
        "university.cafeteria",
        "garden-plant",
        "east entry court",
        BUSH_01,
        92,
        22,
    ),
    (
        "University",
        "university.cafeteria",
        "garden-plant",
        "west campus front",
        BUSH_05,
        76,
        30,
    ),
    (
        "University",
        "university.cafeteria",
        "garden-plant",
        "east campus front",
        BUSH_05,
        98,
        30,
    ),
    (
        "University",
        "university.cafeteria",
        "garden-seat",
        "west campus front",
        BENCH,
        76,
        31,
    ),
    (
        "University",
        "university.cafeteria",
        "garden-seat",
        "east campus front",
        BENCH,
        98,
        31,
    ),
    (
        "University",
        "university.cafeteria",
        "lamp",
        "west campus front",
        LAMP_05,
        70,
        31,
    ),
    (
        "University",
        "university.cafeteria",
        "lamp",
        "east campus front",
        LAMP_05,
        102,
        31,
    ),
)

# Three staggered conifer rows reconstruct the reference's continuous north
# canopy.  Their feet remain outside water, structures, and all 32px paths;
# their crowns overlap naturally behind the cutaway walls.
FOREST_BELT_PLACEMENTS = (
    # Bank riverbank: two irregular rows, with the opening kept over the parcel path.
    ("Bank", "bank.waiting", "perimeter-tree", "north canopy", TREE_03, 1, 3),
    ("Bank", "bank.waiting", "perimeter-tree", "north canopy", TREE_05, 4, 2),
    ("Bank", "bank.waiting", "perimeter-tree", "north canopy", TREE_11, 7, 3),
    ("Bank", "bank.waiting", "perimeter-tree", "north canopy", TREE_03, 10, 2),
    ("Bank", "bank.waiting", "perimeter-tree", "north canopy", TREE_05, 13, 3),
    ("Bank", "bank.waiting", "perimeter-tree", "north canopy", TREE_11, 16, 2),
    ("Bank", "bank.waiting", "perimeter-tree", "north canopy", TREE_03, 19, 3),
    ("Bank", "bank.waiting", "perimeter-tree", "inner canopy", TREE_05, 3, 9),
    ("Bank", "bank.waiting", "perimeter-tree", "inner canopy", TREE_11, 6, 8),
    ("Bank", "bank.waiting", "perimeter-tree", "inner canopy", TREE_03, 10, 9),
    ("Bank", "bank.waiting", "perimeter-tree", "inner canopy", TREE_05, 14, 8),
    ("Bank", "bank.waiting", "perimeter-tree", "inner canopy", TREE_11, 18, 8),
    ("Bank", "bank.waiting", "perimeter-tree", "inner canopy", TREE_03, 21, 9),
    # Home riverbank follows the two land shelves around the inlet.
    ("Home 1", "home_1.garden", "perimeter-tree", "north canopy", TREE_05, 41, 1),
    ("Home 1", "home_1.garden", "perimeter-tree", "north canopy", TREE_11, 44, 1),
    ("Home 1", "home_1.garden", "perimeter-tree", "north canopy", TREE_03, 47, 1),
    ("Home 1", "home_1.garden", "perimeter-tree", "north canopy", TREE_05, 50, 1),
    ("Home 1", "home_1.garden", "perimeter-tree", "north canopy", TREE_11, 64, 1),
    ("Home 1", "home_1.garden", "perimeter-tree", "inlet canopy", TREE_03, 40, 4),
    ("Home 1", "home_1.garden", "perimeter-tree", "inlet canopy", TREE_05, 62, 4),
    ("Home 1", "home_1.garden", "perimeter-tree", "inlet canopy", TREE_11, 65, 4),
    ("Home 1", "home_1.garden", "perimeter-tree", "inlet canopy", TREE_03, 68, 4),
    ("Home 1", "home_1.garden", "perimeter-tree", "inlet canopy", TREE_05, 59, 6),
    ("Home 1", "home_1.garden", "perimeter-tree", "inlet canopy", TREE_11, 66, 6),
    ("Home 1", "home_1.garden", "perimeter-tree", "inner canopy", TREE_03, 55, 8),
    ("Home 1", "home_1.garden", "perimeter-tree", "inner canopy", TREE_05, 59, 8),
    ("Home 1", "home_1.garden", "perimeter-tree", "inner canopy", TREE_11, 62, 9),
    ("Home 1", "home_1.garden", "perimeter-tree", "inner canopy", TREE_03, 65, 9),
    # University crowns sit immediately behind the U-shaped archive wings.
    ("University", "university.lecture", "perimeter-tree", "north canopy", TREE_03, 67, 3),
    ("University", "university.lecture", "perimeter-tree", "north canopy", TREE_05, 70, 3),
    ("University", "university.lecture", "perimeter-tree", "north canopy", TREE_11, 73, 3),
    ("University", "university.lecture", "perimeter-tree", "north canopy", TREE_03, 76, 3),
    ("University", "university.lecture", "perimeter-tree", "north canopy", TREE_05, 79, 3),
    ("University", "university.lecture", "perimeter-tree", "north canopy", TREE_11, 82, 3),
    ("University", "university.cafeteria", "perimeter-tree", "north canopy", TREE_03, 85, 3),
    ("University", "university.cafeteria", "perimeter-tree", "north canopy", TREE_05, 88, 3),
    ("University", "university.cafeteria", "perimeter-tree", "north canopy", TREE_11, 91, 3),
    ("University", "university.study_lab", "perimeter-tree", "north canopy", TREE_03, 94, 3),
    ("University", "university.study_lab", "perimeter-tree", "north canopy", TREE_05, 97, 3),
    ("University", "university.study_lab", "perimeter-tree", "north canopy", TREE_11, 100, 3),
    ("University", "university.study_lab", "perimeter-tree", "north canopy", TREE_03, 103, 3),
    ("University", "university.study_lab", "perimeter-tree", "north canopy", TREE_05, 105, 3),
)

HEDGE_RUNS = (
    ("Bank", "bank.waiting", range(9, 15), 30),
    ("Bank", "bank.waiting", range(23, 29), 30),
    ("Home 1", "home_1.garden", range(45, 52), 30),
    ("Home 1", "home_1.garden", range(59, 65), 30),
    ("University", "university.cafeteria", range(72, 82), 29),
    ("University", "university.cafeteria", range(94, 103), 29),
)


def _hedge_placements() -> tuple[tuple, ...]:
    placements = []
    for sector, zone, positions, foot_y in HEDGE_RUNS:
        last = positions.stop - 1
        for foot_x in positions:
            key = (
                HEDGE_LEFT if foot_x == positions.start
                else HEDGE_RIGHT if foot_x == last
                else HEDGE_MIDDLE
            )
            placements.append(
                (sector, zone, "foundation-hedge", "continuous hedge", key, foot_x, foot_y)
            )
    return tuple(placements)


PLACEMENTS = (
    *BASE_PLACEMENTS,
    *FOREST_BELT_PLACEMENTS,
    *_hedge_placements(),
)


def _inside(point: tuple[int, int], rect: tuple[int, int, int, int]) -> bool:
    x, y = point
    left, top, right, bottom = rect
    return left <= x < right and top <= y < bottom


def _in_water(point: tuple[int, int]) -> bool:
    x, y = point
    return any(left <= x < right for left, right in WATER_RUNS.get(y, ()))


def validate() -> None:
    """Reject paths, water, structures, invalid zones, and regularized drift."""
    if not 130 <= len(PLACEMENTS) <= 145:
        raise ValueError("north landscaping must contain 130 to 145 placements")

    occupied: set[tuple[int, int]] = set()
    role_counts: dict[str, dict[str, int]] = {sector: {} for sector in TARGET_BOUNDS}
    north_tree_count = 0
    for placement in PLACEMENTS:
        sector, zone, role, _cluster, asset_key, foot_x, foot_y = placement
        point = (foot_x, foot_y)
        if sector not in TARGET_BOUNDS or zone not in VALID_ZONES[sector]:
            raise ValueError(f"invalid north landscape sector or zone: {placement}")
        if not _inside(point, TARGET_BOUNDS[sector]):
            raise ValueError(f"north landscape placement outside sector: {placement}")
        if asset_key not in APPROVED_KEYS or asset_key.startswith("prop.design."):
            raise ValueError(f"unapproved north landscape asset: {asset_key}")
        if point in occupied:
            raise ValueError(f"duplicate north landscape foot: {point}")
        if _in_water(point):
            raise ValueError(f"north landscape placement is in water: {placement}")
        if any(_inside(point, rect) for rect in STRUCTURE_RECTS[sector]):
            raise ValueError(
                f"north landscape placement overlaps structure: {placement}"
            )
        if any(_inside(point, rect) for rect in TRACED_PATHS):
            raise ValueError(f"north landscape placement blocks path: {placement}")
        occupied.add(point)
        role_counts[sector][role] = role_counts[sector].get(role, 0) + 1
        if role == "perimeter-tree" and foot_y < 10:
            north_tree_count += 1

    for sector, counts in role_counts.items():
        if counts.get("garden-seat") != 2 or counts.get("lamp") != 2:
            raise ValueError(f"{sector} requires a paired bench and lamp composition")
    if north_tree_count < 45:
        raise ValueError("north perimeter requires at least 45 overlapping trees")
    if len({placement[4] for placement in PLACEMENTS if placement[4] in TREE_KEYS}) < 4:
        raise ValueError("north tree belt must use all four irregular tree silhouettes")


validate()
