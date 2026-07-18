"""Native-sprite University program for the target-photo U compound."""

from __future__ import annotations

UNIVERSITY_BOUNDS = ((98, 5, 110, 36), (110, 5, 121, 16))
COURT_BOUNDS = (110, 16, 121, 36)


def _p(zone: str, role: str, cluster: str, key: str, x: int, y: int) -> tuple:
    return "University", zone, role, cluster, key, x, y


PLACEMENTS = (
    # A fitted archive wall defines the north and west edges of the library wing.
    *(
        _p("university.lecture", "reference-shelf", "west archive wall", key, x, 9)
        for x, key in (
            (101, "prop.interiors_v3.classroom_library.0043"),
            (103, "prop.interiors_v3.classroom_library.0045"),
            (105, "prop.interiors_v3.classroom_library.0047"),
            (107, "prop.interiors_v3.classroom_library.0043"),
            (109, "prop.interiors_v3.classroom_library.0045"),
        )
    ),
    *(
        _p("university.lecture", "reference-shelf", "west archive return", key, 101, y)
        for y, key in (
            (12, "prop.interiors_v3.classroom_library.0055"),
            (15, "prop.interiors_v3.classroom_library.0058"),
            (18, "prop.interiors_v3.classroom_library.0060"),
            (21, "prop.interiors_v3.classroom_library.0064"),
        )
    ),
    _p("university.lecture", "reference-shelf", "west archive wall",
       "prop.interiors_v3.classroom_library.0047", 109, 12),
    _p("university.lecture", "teaching-board", "lecture wall",
       "prop.interiors_v3.classroom_library.0039", 109, 13),
    _p("university.lecture", "instructor-desk", "lecture wall",
       "prop.interiors_v3.classroom_library.0025", 109, 16),
    _p("university.lecture", "learning-globe", "lecture wall",
       "prop.interiors_v3.classroom_library.0034", 107, 16),

    # Two joined seating rows face the teaching wall with a two-tile aisle.
    _p("university.lecture", "lecture-seating", "lecture row one",
       "prop.interiors_v3.classroom_library.0015", 104, 17),
    _p("university.lecture", "lecture-seating", "lecture row one",
       "prop.interiors_v3.classroom_library.0016", 109, 17),
    _p("university.lecture", "lecture-seating", "lecture row two",
       "prop.interiors_v3.classroom_library.0017", 104, 21),
    _p("university.lecture", "lecture-seating", "lecture row two",
       "prop.interiors_v3.classroom_library.0018", 109, 21),

    # Research stations run along the lower west wall, never into the court.
    _p("university.study_lab", "computer-station", "research pair",
       "prop.office.computer_desk", 103, 25),
    _p("university.study_lab", "study-chair", "research pair",
       "prop.office.chair_blue", 103, 27),
    _p("university.study_lab", "computer-station", "research pair",
       "prop.office.computer_desk", 108, 25),
    _p("university.study_lab", "study-chair", "research pair",
       "prop.office.chair_orange", 108, 27),
    _p("university.study_lab", "reference-map", "research support",
       "prop.interiors_v3.classroom_library.0031", 109, 24),
    _p("university.study_lab", "document-printer", "research support",
       "prop.office.printer_station", 109, 27),

    # The cafeteria is a compact, complete service-and-dining room at the base.
    _p("university.cafeteria", "refrigerator", "campus cafe back wall",
       "prop.interiors_v3.kitchen.0160", 101, 29),
    _p("university.cafeteria", "prep", "campus cafe back wall",
       "prop.interiors_v3.kitchen.0121", 103, 29),
    _p("university.cafeteria", "food-display", "campus cafe back wall",
       "prop.interiors_v3.ice_cream.0020", 105, 29),
    _p("university.cafeteria", "service-counter", "campus cafe service line",
       "prop.office.counter_cream_left", 105, 32),
    _p("university.cafeteria", "service-counter", "campus cafe service line",
       "prop.office.counter_cream_middle", 107, 32),
    _p("university.cafeteria", "service-counter", "campus cafe service line",
       "prop.office.counter_cream_right", 109, 32),
    _p("university.cafeteria", "dining-table", "campus dining pocket",
       "prop.office.table_walnut", 104, 34),
    _p("university.cafeteria", "dining-chair", "campus dining pocket",
       "prop.interiors_v3.kitchen.0369", 101, 34),
    _p("university.cafeteria", "dining-chair", "campus dining pocket",
       "prop.interiors_v3.kitchen.0372", 108, 34),

    # The north bridge is a continuous reference library overlooking the court.
    *(
        _p("university.lecture", "reference-shelf", "north bridge collection",
           key, x, 9)
        for x, key in (
            (111, "prop.interiors_v3.classroom_library.0044"),
            (114, "prop.interiors_v3.classroom_library.0046"),
            (117, "prop.interiors_v3.classroom_library.0048"),
            (120, "prop.interiors_v3.classroom_library.0044"),
        )
    ),
    _p("university.study_lab", "reference-table", "north bridge study table",
       "prop.office.table_walnut_long", 116, 13),
    _p("university.study_lab", "reference-table", "north bridge study table",
       "prop.office.table_walnut_long", 119, 13),
    _p("university.study_lab", "study-chair", "north bridge study table",
       "prop.interiors_v3.classroom_library.0003", 115, 11),
    _p("university.study_lab", "study-chair", "north bridge study table",
       "prop.interiors_v3.classroom_library.0004", 120, 11),
)


def _inside(x: int, y: int) -> bool:
    return any(left < x < right and top < y < bottom
               for left, top, right, bottom in UNIVERSITY_BOUNDS)


def validate() -> None:
    occupied: set[tuple[int, int]] = set()
    for item in PLACEMENTS:
        sector, _zone, _role, _cluster, key, x, y = item
        if sector != "University" or not _inside(x, y):
            raise ValueError(f"University placement left target U: {item}")
        if key.startswith("prop.design.") or (x, y) in occupied:
            raise ValueError(f"invalid University placement: {item}")
        occupied.add((x, y))
    if any(COURT_BOUNDS[0] <= x < COURT_BOUNDS[2] and
           COURT_BOUNDS[1] <= y < COURT_BOUNDS[3] for x, y in occupied):
        raise ValueError("University furniture obstructs the open court")
    roles = {item[2] for item in PLACEMENTS}
    if not {"lecture-seating", "computer-station", "service-counter",
            "dining-table", "reference-shelf"} <= roles:
        raise ValueError("University lost a required teaching function")
    if not 34 <= len(PLACEMENTS) <= 48:
        raise ValueError("University target coverage changed")


validate()
