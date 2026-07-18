"""Native-16 geometry measured from the approved Claudeville target image."""

from __future__ import annotations

VISUAL_WIDTH = 176
VISUAL_HEIGHT = 96
TILE_SIZE = 16


def _building(
    parcel: tuple[int, int, int, int],
    room: tuple[int, int, int, int],
    facade: tuple[int, int, int, int],
    entry: tuple[int, int, int, int],
    *,
    shared_compound: str | None = None,
    paint_shell: bool = True,
    paint_facade: bool = True,
    subroom: tuple[int, int, int, int] | None = None,
    door_side: str = "bottom",
) -> dict:
    """Build one sector record while retaining all twenty simulation sectors."""
    result = {
        "parcel": parcel,
        "room": room,
        "facade": facade,
        "entry": entry,
        "paint_shell": paint_shell,
        "paint_facade": paint_facade,
        "door_side": door_side,
    }
    if shared_compound is not None:
        result["shared_compound"] = shared_compound
    if subroom is not None:
        result["subroom"] = subroom
    return result


# Rectangles are half-open visual-cell coordinates.  The public buildings now
# follow the target's four-compound rhythm rather than v44's five small slots.
BUILDINGS = {
    "Bank": _building(
        (23, 10, 54, 40), (27, 12, 51, 36), (27, 32, 51, 36), (36, 32, 42, 45),
    ),
    "Home 1": _building(
        (62, 10, 95, 40), (67, 12, 91, 36), (67, 32, 91, 36), (76, 32, 82, 45),
    ),
    "University": {
        "parcel": (94, 4, 137, 40),
        "room_union": ((98, 5, 110, 36), (110, 5, 121, 16), (121, 5, 133, 36)),
        "facade_union": ((98, 32, 110, 36), (121, 32, 133, 36)),
        "entry": (113, 16, 121, 45),
        "shared_compound": "north_education",
        "paint_shell": True,
        "paint_facade": True,
        "subroom": (98, 5, 121, 36),
    },
    "Agent Academy": _building(
        (94, 4, 137, 40), (121, 5, 133, 36), (121, 32, 133, 36),
        (113, 16, 121, 45), shared_compound="north_education",
        paint_shell=False, paint_facade=False, subroom=(121, 5, 133, 36),
    ),
    "Market": _building(
        (137, 10, 158, 40), (141, 11, 158, 36), (141, 32, 158, 36),
        (146, 32, 152, 45),
    ),
    "Post Office": _building(
        (158, 10, 176, 40), (158, 11, 176, 36), (158, 31, 176, 36),
        (163, 32, 169, 45),
    ),
    "Workshop": _building(
        (23, 43, 54, 75), (27, 44, 51, 72), (27, 68, 51, 72), (36, 68, 42, 80),
    ),
    "Community Center": _building(
        (62, 43, 95, 75), (67, 45, 91, 72), (67, 68, 91, 72),
        (71, 68, 77, 80), shared_compound="middle_social",
        subroom=(67, 45, 79, 72),
    ),
    "Claudeville Cafe": _building(
        (62, 43, 95, 75), (79, 45, 91, 72), (79, 68, 91, 72),
        (82, 68, 88, 80), shared_compound="middle_social",
        paint_shell=False, paint_facade=False, subroom=(79, 45, 91, 72),
    ),
    "Library": _building(
        (137, 43, 170, 75), (143, 45, 170, 72), (143, 68, 170, 72),
        (144, 68, 150, 80),
    ),
    "Home 2": _building(
        (23, 79, 54, 96), (27, 80, 39, 96), (27, 92, 39, 96),
        (31, 72, 36, 96), door_side="top",
    ),
    "Home 3": _building(
        (23, 79, 54, 96), (39, 80, 51, 96), (39, 92, 51, 96),
        (43, 72, 48, 96), door_side="top",
    ),
    "Home 4": _building(
        (62, 79, 95, 96), (67, 80, 75, 96), (67, 92, 75, 96),
        (69, 72, 74, 96), door_side="top",
    ),
    "Home 5": _building(
        (62, 79, 95, 96), (75, 80, 83, 96), (75, 92, 83, 96),
        (77, 72, 81, 96), door_side="top",
    ),
    "Home 6": _building(
        (62, 79, 95, 96), (83, 80, 91, 96), (83, 92, 91, 96),
        (85, 72, 89, 96), door_side="top",
    ),
    "Town Hall": _building(
        (95, 79, 117, 96), (99, 80, 114, 96), (99, 92, 114, 96),
        (104, 72, 110, 96), door_side="top",
    ),
    "Home 7": _building(
        (117, 79, 137, 96), (118, 80, 128, 96), (118, 92, 128, 96),
        (121, 72, 126, 96), door_side="top",
    ),
    "Home 8": _building(
        (117, 79, 137, 96), (128, 80, 137, 96), (128, 92, 137, 96),
        (131, 72, 135, 96), door_side="top",
    ),
    "Home 9": _building(
        (137, 79, 158, 96), (143, 80, 150, 96), (143, 92, 150, 96),
        (144, 72, 149, 96), door_side="top",
    ),
    "Home 10": _building(
        (137, 79, 158, 96), (150, 80, 158, 96), (150, 92, 158, 96),
        (152, 72, 157, 96), door_side="top",
    ),
}

REFERENCE_ADDITIONS = frozenset({"Claudeville Cafe", "Home 6"})

PLAZA = {
    "parcel": (95, 43, 137, 75),
    "quadrants": (
        ((97, 45), (111, 45), (111, 55), (97, 55)),
        ((123, 45), (135, 45), (135, 55), (123, 55)),
        ((97, 61), (111, 61), (111, 72), (97, 72)),
        ((123, 61), (135, 61), (135, 72), (123, 72)),
    ),
    "fountain": (114, 51, 121, 63),
    "vertical_axis": (111, 43, 123, 75),
    "horizontal_axis": (95, 55, 137, 61),
}

MAIN_PATHS = (
    (18, 37, 176, 43),
    (18, 73, 176, 79),
    (58, 0, 62, 96),
    (139, 0, 142, 96),
)
PARCEL_PATHS: tuple[tuple[int, int, int, int], ...] = ()
SOUTH_PATHS: tuple[tuple[int, int, int, int], ...] = ()

# An organic top river occupies only the northern shore.  Land gaps at the two
# civic spines read as bridges and the U-shaped education court stays dry.
WATER_RUNS = {
    0: ((18, 56), (63, 137), (143, 176)),
    1: ((18, 56), (63, 137), (143, 176)),
    2: ((19, 56), (63, 137), (143, 176)),
    3: ((19, 56), (63, 137), (143, 176)),
    4: ((20, 56), (64, 94), (143, 175)),
    5: ((20, 55), (64, 94), (144, 175)),
    6: ((21, 55), (65, 94), (144, 174)),
    7: ((20, 54), (65, 93), (145, 174)),
    8: ((21, 53), (66, 93), (145, 173)),
    9: ((22, 52), (67, 92), (146, 172)),
    10: ((18, 22),),
    11: ((18, 21),),
}


def validate() -> None:
    """Reject drift from the target-photo compound geometry."""
    if len(BUILDINGS) != 20 or PLAZA["parcel"] != (95, 43, 137, 75):
        raise ValueError("Claudeville requires twenty sectors and the measured plaza")
    rectangles = []
    for name, record in BUILDINGS.items():
        rectangles.append((name, record["parcel"]))
        rectangles.extend(
            (name, record[key])
            for key in ("room", "facade", "entry", "subroom") if key in record
        )
        rectangles.extend((name, rect) for rect in record.get("room_union", ()))
        rectangles.extend((name, rect) for rect in record.get("facade_union", ()))
    for name, (left, top, right, bottom) in rectangles:
        if not (0 <= left < right <= VISUAL_WIDTH and 0 <= top < bottom <= VISUAL_HEIGHT):
            raise ValueError(f"invalid {name} reference rectangle")
    for row, runs in WATER_RUNS.items():
        if not 0 <= row <= 11:
            raise ValueError("the target river belongs only on the northern shore")
        for left, right in runs:
            if not 0 <= left < right <= VISUAL_WIDTH:
                raise ValueError("water run outside reference grid")
    expected_groups = {
        "north_education": {"University", "Agent Academy"},
        "middle_social": {"Community Center", "Claudeville Cafe"},
    }
    for group, members in expected_groups.items():
        actual = {name for name, record in BUILDINGS.items() if record.get("shared_compound") == group}
        if actual != members or sum(BUILDINGS[name]["paint_shell"] for name in members) != 1:
            raise ValueError(f"malformed shared compound: {group}")


validate()
