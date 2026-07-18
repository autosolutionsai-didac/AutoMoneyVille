"""Purpose-first native-sprite programs for the target-photo middle compounds."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from tools.mapgen import claudeville_reference_middle_validation as validation
except ModuleNotFoundError:  # Direct mapgen execution.
    import claudeville_reference_middle_validation as validation

Placement = tuple[str, str, str, str, str, int, int]
V2_CATALOG = validation.V2_CATALOG
V3_CATALOG = validation.V3_CATALOG

REFERENCE_ROOMS = {
    "Workshop": (27, 44, 51, 72),
    "Community Center": (67, 45, 79, 72),
    "Claudeville Cafe": (79, 45, 91, 72),
    "Library": (143, 45, 170, 72),
    "Post Office": (158, 11, 176, 36),
}
REFERENCE_FACADES = {
    "Workshop": (27, 69, 51, 72),
    "Community Center": (67, 69, 91, 72),
    "Claudeville Cafe": (67, 69, 91, 72),
    "Library": (143, 69, 170, 72),
    "Post Office": (158, 31, 176, 36),
}
PLACEMENT_BOUNDS = {
    **REFERENCE_ROOMS,
    # The target's broad lower paver band carries the Cafe terrace.
    "Claudeville Cafe": (79, 45, 91, 78),
}
TARGET_BOUNDS = PLACEMENT_BOUNDS
TARGETS = frozenset(TARGET_BOUNDS)

# Two coherent licensed Worksite crops frame a central assembly aisle.
WORKSHOP_TILE_STAMPS = (
    ("exteriors_worksite", (12, 0, 7, 12), (28, 46), "Interior Furniture L1"),
    # A real five-tile worksite bench bridges the former dead void between
    # the machine bank and parts racks.  Transparent source cells keep a
    # continuous north/south service aisle around it.
    ("exteriors_worksite", (8, 0, 5, 5), (36, 48), "Interior Furniture L1"),
    ("exteriors_worksite", (20, 0, 6, 14), (44, 46), "Interior Furniture L1"),
)

# Logical 32px footprints for the large machinery painted by the worksite
# tile stamps.  The authored visible machines must be as solid as the object
# sprites used elsewhere in the room.
WORKSHOP_COLLISION_BLOCKS = frozenset({
    (15, 25), (16, 25), (15, 27), (16, 27), (17, 27),
    (18, 25), (19, 25), (20, 25),
    (22, 25), (23, 25), (24, 25),
    (22, 27), (23, 27), (24, 27),
})


def _p(
    sector: str, zone: str, role: str, cluster: str, key: str, x: int, y: int,
) -> Placement:
    return sector, zone, role, cluster, key, x, y


WORKSHOP_PLACEMENTS = (
    # Continuous parts storage uses most of the north wall.
    *(
        _p("Workshop", "workshop.machine_bay", "tool-storage", "north parts wall",
           key, x, 47)
        for x, key in (
            (29, "prop.office.display_cabinet"),
            (33, "prop.office.filing_cabinet"),
            (37, "prop.office.display_cabinet"),
            (41, "prop.office.filing_cabinet"),
            (45, "prop.office.display_cabinet"),
            (49, "prop.office.filing_cabinet"),
        )
    ),
    # Three machine cells pair every machine with controls and parts.
    *(
        _p("Workshop", "workshop.machine_bay", role, cluster, key, x, y)
        for cluster, x, y, role, key in (
            ("west machine cell", 30, 52, "machine-control", "prop.office.monitor_blue"),
            ("west machine cell", 30, 55, "work-machine", "prop.office.dual_monitors"),
            ("west machine cell", 33, 55, "parts-bin", "prop.post.package_large"),
            ("centre machine cell", 39, 52, "machine-control", "prop.office.dual_monitors"),
            ("centre machine cell", 39, 55, "work-machine", "prop.office.monitor_blue"),
            ("centre machine cell", 42, 55, "parts-bin", "prop.post.package_small"),
            ("east machine cell", 49, 52, "machine-control", "prop.office.monitor_blue"),
            ("east machine cell", 49, 55, "work-machine", "prop.office.dual_monitors"),
            ("east machine cell", 49, 57, "parts-bin", "prop.post.package_stack"),
        )
    ),
    # A joined repair island occupies the central lower bay.
    _p("Workshop", "workshop.machine_bay", "workbench", "repair island",
       "prop.office.counter_walnut_left", 34, 60),
    _p("Workshop", "workshop.machine_bay", "workbench", "repair island",
       "prop.office.counter_walnut_middle", 35, 60),
    _p("Workshop", "workshop.machine_bay", "workbench", "repair island",
       "prop.office.counter_walnut_middle", 36, 60),
    _p("Workshop", "workshop.machine_bay", "workbench", "repair island",
       "prop.office.counter_walnut_right", 37, 60),
    _p("Workshop", "workshop.machine_bay", "test-terminal", "repair island",
       "prop.office.laptop", 35, 58),
    _p("Workshop", "workshop.machine_bay", "parts-printer", "repair island",
       "prop.office.printer", 39, 58),
    _p("Workshop", "workshop.machine_bay", "technician-seat", "repair island",
       "prop.office.chair_orange", 37, 62),
    # Intake and dispatch hug opposing walls, leaving x38..41 open to the door.
    _p("Workshop", "workshop.intake", "job-intake", "intake counter",
       "prop.office.counter_cream_left", 29, 66),
    _p("Workshop", "workshop.intake", "job-intake", "intake counter",
       "prop.office.counter_cream_right", 31, 66),
    _p("Workshop", "workshop.intake", "estimate-terminal", "intake counter",
       "prop.office.cash_register", 31, 64),
    _p("Workshop", "workshop.intake", "job-board", "intake support",
       "prop.office.notice_board", 29, 64),
    _p("Workshop", "workshop.intake", "job-records", "intake support",
       "prop.office.filing_cabinet", 35, 64),
    _p("Workshop", "workshop.circulation", "finished-job", "dispatch pocket",
       "prop.post.package_stack", 46, 65),
    _p("Workshop", "workshop.circulation", "dispatch-records", "dispatch pocket",
       "prop.office.printer_station", 49, 65),
    _p("Workshop", "workshop.circulation", "dispatch-counter", "dispatch counter",
       "prop.office.counter_walnut_left", 44, 68),
    _p("Workshop", "workshop.circulation", "dispatch-counter", "dispatch counter",
       "prop.office.counter_walnut_middle", 46, 68),
    _p("Workshop", "workshop.circulation", "dispatch-counter", "dispatch counter",
       "prop.office.counter_walnut_right", 48, 68),
    _p("Workshop", "workshop.circulation", "dispatch-seat", "dispatch counter",
       "prop.office.chair_blue", 44, 70),
    _p("Workshop", "workshop.circulation", "dispatch-seat", "dispatch counter",
       "prop.office.chair_orange", 48, 70),
)

CAFE_PLACEMENTS = (
    # The licensed transparent cafe composition supplies the continuous back
    # line.  These five semantic props keep the appliances and service point
    # individually addressable without doubling every sprite in the artwork.
    _p("Claudeville Cafe", "cafe.service", "refrigerator", "cafe back wall",
       "prop.interiors_v3.kitchen.0160", 81, 49),
    _p("Claudeville Cafe", "cafe.service", "prep-counter", "cafe back wall",
       "prop.interiors_v3.kitchen.0126", 84, 49),
    _p("Claudeville Cafe", "cafe.service", "service-counter", "cafe service line",
       "prop.office.counter_cream_left", 81, 55),
    _p("Claudeville Cafe", "cafe.service", "food-display", "cafe service line",
       "prop.interiors_v3.ice_cream.0020", 82, 53),
    _p("Claudeville Cafe", "cafe.service", "checkout-terminal", "cafe service line",
       "prop.office.cash_register", 86, 53),
    _p("Claudeville Cafe", "cafe.dining", "dining-table", "window table one",
       "prop.interiors_v3.japanese.0039", 83, 61),
    _p("Claudeville Cafe", "cafe.dining", "dining-chair", "window table one",
       "prop.interiors_v3.japanese.0042", 81, 60),
    _p("Claudeville Cafe", "cafe.dining", "dining-chair", "window table one",
       "prop.interiors_v3.japanese.0043", 85, 60),
    _p("Claudeville Cafe", "cafe.dining", "dining-table", "window table two",
       "prop.interiors_v3.japanese.0039", 88, 64),
    _p("Claudeville Cafe", "cafe.dining", "dining-chair", "window table two",
       "prop.interiors_v3.japanese.0042", 86, 63),
    _p("Claudeville Cafe", "cafe.dining", "dining-chair", "window table two",
       "prop.interiors_v3.japanese.0043", 89, 62),
    _p("Claudeville Cafe", "cafe.dining", "dining-table", "window table three",
       "prop.interiors_v3.japanese.0039", 83, 65),
    _p("Claudeville Cafe", "cafe.dining", "dining-chair", "window table three",
       "prop.interiors_v3.japanese.0042", 81, 64),
    _p("Claudeville Cafe", "cafe.dining", "dining-chair", "window table three",
       "prop.interiors_v3.japanese.0043", 85, 64),
    _p("Claudeville Cafe", "cafe.service", "dry-storage", "service support wall",
       "prop.interiors_v3.kitchen.0126", 89, 55),
    _p("Claudeville Cafe", "cafe.service", "supply-cabinet", "service support wall",
       "prop.interiors_v3.kitchen.0160", 89, 57),
    _p("Claudeville Cafe", "cafe.restroom", "bathroom-sink", "cafe washroom",
       "prop.interiors_v3.bathroom.0006", 89, 67),
    _p("Claudeville Cafe", "cafe.restroom", "toilet", "cafe washroom",
       "prop.interiors_v3.bathroom.0035", 87, 67),
    _p("Claudeville Cafe", "cafe.terrace", "terrace-table", "paved terrace",
       "prop.interiors_v3.japanese.0039", 84, 75),
    _p("Claudeville Cafe", "cafe.terrace", "terrace-chair", "paved terrace",
       "prop.interiors_v3.japanese.0042", 83, 74),
    _p("Claudeville Cafe", "cafe.terrace", "terrace-chair", "paved terrace",
       "prop.interiors_v3.japanese.0043", 86, 74),
)

COMMUNITY_PLACEMENTS = (
    # Two long event tables fill the narrow west wing without blocking its door.
    *(
        _p("Community Center", "community.event_hall", role, cluster, key, x, y)
        for cluster, x, y, role, key in (
            ("north event table", 70, 60, "event-table", "prop.office.table_walnut_long"),
            ("north event table", 72, 60, "event-table", "prop.office.table_walnut_long"),
            ("north event table", 73, 60, "event-table", "prop.office.table_walnut_long"),
            ("north event table", 69, 58, "event-seat", "prop.office.chair_blue_side"),
            ("north event table", 77, 58, "event-seat", "prop.office.chair_orange_side"),
            ("south event table", 70, 64, "event-table", "prop.office.table_walnut_long"),
            ("south event table", 72, 64, "event-table", "prop.office.table_walnut_long"),
            ("south event table", 73, 64, "event-table", "prop.office.table_walnut_long"),
            ("south event table", 70, 62, "event-seat", "prop.office.chair_orange_side"),
            ("south event table", 78, 62, "event-seat", "prop.office.chair_blue_side"),
        )
    ),
    _p("Community Center", "community.event_hall", "presentation-area",
       "event information wall", "prop.office.whiteboard", 69, 57),
    _p("Community Center", "community.event_hall", "event-notice",
       "event information wall", "prop.office.notice_board", 73, 57),
    _p("Community Center", "community.reception", "help-desk", "help counter",
       "prop.office.counter_walnut_left", 70, 67),
    _p("Community Center", "community.reception", "help-desk", "help counter",
       "prop.office.counter_walnut_right", 72, 67),
    _p("Community Center", "community.reception", "help-terminal", "help counter",
       "prop.office.monitor_blue", 71, 65),
    _p("Community Center", "community.lounge", "lounge-seating", "east lounge",
       "prop.office.sofa_dark", 78, 67),
    _p("Community Center", "community.lounge", "lounge-seating", "east lounge",
       "prop.office.armchair_mustard", 76, 68),
    _p("Community Center", "community.lounge", "side-table", "east lounge",
       "prop.office.side_table", 78, 65),
    _p("Community Center", "community.reception", "notice-board", "help counter",
       "prop.office.notice_board", 74, 65),
)

LIBRARY_PLACEMENTS = (
    # The Library is one full public building again.  Continuous north and
    # side stacks frame two reading tables and a staffed checkout line.
    *(
        _p("Library", "library.stacks", role, "library perimeter", key, x, y)
        for x, y, role, key in (
            (144, 48, "bookshelf", "prop.interiors_v3.classroom_library.0043"),
            (146, 48, "bookshelf", "prop.interiors_v3.classroom_library.0045"),
            (148, 48, "bookshelf", "prop.interiors_v3.classroom_library.0047"),
            (150, 48, "bookshelf", "prop.interiors_v3.classroom_library.0044"),
            (152, 48, "bookshelf", "prop.interiors_v3.classroom_library.0046"),
            (154, 48, "bookshelf", "prop.interiors_v3.classroom_library.0048"),
            (156, 48, "east-bookshelf", "prop.interiors_v3.classroom_library.0044"),
            (158, 48, "east-bookshelf", "prop.interiors_v3.classroom_library.0046"),
            (160, 48, "east-bookshelf", "prop.interiors_v3.classroom_library.0048"),
            (162, 48, "east-bookshelf", "prop.interiors_v3.classroom_library.0044"),
            (164, 48, "east-bookshelf", "prop.interiors_v3.classroom_library.0046"),
            (166, 48, "east-bookshelf", "prop.interiors_v3.classroom_library.0048"),
            (168, 48, "east-bookshelf", "prop.interiors_v3.classroom_library.0044"),
            (144, 52, "bookshelf", "prop.interiors_v3.classroom_library.0055"),
            (144, 56, "bookshelf", "prop.interiors_v3.classroom_library.0058"),
            (144, 60, "bookshelf", "prop.interiors_v3.classroom_library.0055"),
            (144, 64, "bookshelf", "prop.interiors_v3.classroom_library.0058"),
            (168, 52, "east-bookshelf", "prop.interiors_v3.classroom_library.0062"),
            (168, 56, "east-bookshelf", "prop.interiors_v3.classroom_library.0064"),
            (168, 60, "east-bookshelf", "prop.interiors_v3.classroom_library.0062"),
            (168, 64, "east-bookshelf", "prop.interiors_v3.classroom_library.0064"),
        )
    ),
    _p("Library", "library.reading", "reading-table", "west reading table",
       "prop.office.table_walnut_long", 148, 55),
    _p("Library", "library.reading", "reading-table", "west reading table",
       "prop.office.table_walnut_long", 150, 55),
    _p("Library", "library.reading", "reading-table", "west reading table",
       "prop.office.table_walnut_long", 152, 55),
    _p("Library", "library.reading", "reading-chair", "west reading table",
       "prop.interiors_v3.classroom_library.0003", 148, 52),
    _p("Library", "library.reading", "reading-chair", "west reading table",
       "prop.interiors_v3.classroom_library.0004", 152, 58),
    _p("Library", "library.reading", "reading-table", "east reading table",
       "prop.office.table_walnut_long", 158, 56),
    _p("Library", "library.reading", "reading-table", "east reading table",
       "prop.office.table_walnut_long", 160, 56),
    _p("Library", "library.reading", "reading-table", "east reading table",
       "prop.office.table_walnut_long", 162, 56),
    _p("Library", "library.reading", "reading-chair", "east reading table",
       "prop.interiors_v3.classroom_library.0003", 158, 53),
    _p("Library", "library.reading", "reading-chair", "east reading table",
       "prop.interiors_v3.classroom_library.0004", 162, 59),
    _p("Library", "library.circulation", "circulation-desk", "library checkout",
       "prop.office.counter_walnut_left", 146, 66),
    _p("Library", "library.circulation", "circulation-desk", "library checkout",
       "prop.office.counter_walnut_middle", 148, 66),
    _p("Library", "library.circulation", "circulation-desk", "library checkout",
       "prop.office.counter_walnut_right", 150, 66),
    _p("Library", "library.circulation", "checkout-terminal", "library checkout",
       "prop.office.monitor_blue", 148, 64),
    _p("Library", "library.circulation", "returns-cart", "library checkout",
       "prop.office.filing_cabinet", 154, 66),
    *(
        _p("Library", "library.stacks", "east-bookshelf", "lower reference stacks",
           key, x, 65)
        for x, key in (
            (158, "prop.interiors_v3.classroom_library.0043"),
            (160, "prop.interiors_v3.classroom_library.0045"),
            (162, "prop.interiors_v3.classroom_library.0047"),
            (164, "prop.interiors_v3.classroom_library.0043"),
        )
    ),
    _p("Library", "library.reading", "reading-chair", "quiet reading lounge",
       "prop.office.armchair_ice", 147, 61),
    _p("Library", "library.reading", "reading-chair", "quiet reading lounge",
       "prop.office.armchair_mustard", 151, 61),
    _p("Library", "library.reading", "side-table", "quiet reading lounge",
       "prop.office.side_table", 149, 62),
    _p("Library", "library.reading", "reference-terminal", "reference station",
       "prop.office.computer_desk", 166, 64),
    _p("Library", "library.reading", "reference-seat", "reference station",
       "prop.office.chair_blue", 166, 67),
)

POST_PLACEMENTS = (
    # The Post Office is a separate northern building.  Sorting racks fill the
    # back wall, a joined counter controls the public half, and waiting stays
    # clear of the central entrance lane.
    *(
        _p("Post Office", "post.sorting", "parcel-sorting-rack",
           "postal pigeonhole wall", key, x, 15)
        for x, key in (
            (159, "prop.office.display_cabinet"),
            (161, "prop.office.filing_cabinet"),
            (163, "prop.office.display_cabinet"),
            (165, "prop.office.filing_cabinet"),
            (167, "prop.office.display_cabinet"),
            (169, "prop.office.filing_cabinet"),
            (171, "prop.office.display_cabinet"),
            (173, "prop.office.filing_cabinet"),
        )
    ),
    _p("Post Office", "post.service", "postal-counter", "postal service line",
       "prop.office.counter_cream_left", 159, 28),
    _p("Post Office", "post.service", "postal-counter", "postal service line",
       "prop.office.counter_cream_middle", 161, 28),
    _p("Post Office", "post.service", "postal-counter", "postal service line",
       "prop.office.counter_cream_middle", 163, 28),
    _p("Post Office", "post.service", "postal-counter", "postal service line",
       "prop.office.counter_cream_right", 165, 28),
    _p("Post Office", "post.service", "service-terminal", "postal service line",
       "prop.office.cash_register", 161, 26),
    _p("Post Office", "post.service", "postal-scale", "postal service line",
       "prop.office.paper_stack", 165, 26),
    _p("Post Office", "post.sorting", "mail-sorting-table", "sorting pod",
       "prop.office.table_walnut_long", 161, 21),
    _p("Post Office", "post.sorting", "mail-sorting-table", "sorting pod",
       "prop.office.table_walnut_long", 164, 21),
    _p("Post Office", "post.sorting", "mail-sorting-table", "sorting pod",
       "prop.office.table_walnut_long", 167, 21),
    _p("Post Office", "post.sorting", "sorting-station", "sorting pod",
       "prop.office.printer_station", 172, 21),
    _p("Post Office", "post.sorting", "sorted-parcel", "sorting pod",
       "prop.post.package_stack", 170, 24),
    _p("Post Office", "post.sorting", "sorted-parcel", "sorting pod",
       "prop.post.package_large", 173, 24),
    _p("Post Office", "post.waiting", "waiting-seating", "postal waiting",
       "prop.office.armchair_ice", 170, 31),
    _p("Post Office", "post.waiting", "waiting-seating", "postal waiting",
       "prop.office.armchair_mustard", 173, 31),
    _p("Post Office", "post.waiting", "side-table", "postal waiting",
       "prop.office.side_table", 172, 33),
)

PLACEMENTS = (
    *WORKSHOP_PLACEMENTS,
    *CAFE_PLACEMENTS,
    *COMMUNITY_PLACEMENTS,
    *LIBRARY_PLACEMENTS,
    *POST_PLACEMENTS,
)

REQUIRED_ROLES = {
    "Workshop": {"job-intake", "tool-storage", "work-machine", "workbench"},
    "Community Center": {"event-table", "help-desk", "lounge-seating"},
    "Claudeville Cafe": {
        "service-counter", "dining-table", "prep-counter", "terrace-table",
    },
    "Library": {"bookshelf", "east-bookshelf", "circulation-desk", "reading-table"},
    "Post Office": {"postal-counter", "mail-sorting-table", "parcel-sorting-rack"},
}


def validate_catalogs(
    v2_path: Path = V2_CATALOG, v3_path: Path = V3_CATALOG,
) -> dict[str, int]:
    return validation.validate_catalogs(PLACEMENTS, v2_path, v3_path)


def validate() -> None:
    validation.validate(PLACEMENTS, PLACEMENT_BOUNDS, REQUIRED_ROLES)
    occupied: set[tuple[str, int, int]] = set()
    for item in PLACEMENTS:
        point = (item[0], item[5], item[6])
        if point in occupied or item[4].startswith("prop.design."):
            raise ValueError(f"invalid target middle placement: {item}")
        occupied.add(point)
    counts = {sector: sum(item[0] == sector for item in PLACEMENTS) for sector in TARGETS}
    minimums = {"Workshop": 28, "Community Center": 18, "Claudeville Cafe": 16,
                "Library": 41, "Post Office": 22}
    if any(counts[sector] < minimum for sector, minimum in minimums.items()):
        raise ValueError("target middle compound lost furnishing density")


validate()


if __name__ == "__main__":
    print(json.dumps({"placements": len(PLACEMENTS), "packs": validate_catalogs()}))
