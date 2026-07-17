"""Purposeful native-16 prop placements for Claudeville's north district."""

TARGET_BOUNDS = {
    "Home 1": (44, 8, 64, 33),
    "University": (74, 10, 98, 33),
    "Agent Academy": (110, 12, 128, 33),
    "Market": (148, 24, 160, 33),
    "Post Office": (150, 44, 170, 63),
}
TARGETS = frozenset(TARGET_BOUNDS)
REVISION = 14
INTERACTION_STANCE_UPDATES = (
    ("University", "university.cafeteria.dining-table-001", 43, 14),
)

V3_TILE_SOURCES = ("room.floors", "room.walls", "room.arched_entryways")
FLOOR_PATTERNS = {
    "civic-gray": ((("room.floors", 9, 13),),),
    "home-wood": ((("room.floors", 12, 1),),),
    "home-maple": ((("room.floors", 25, 1),),),
}
WALL_TILE_STYLE = {
    "horizontal": ("room.walls", 0, 12),
    "top_left": ("room.walls", 0, 11),
    "top_right": ("room.walls", 0, 14),
    "left": ("room.walls", 1, 16),
    "right": ("room.walls", 1, 16),
}

# Inclusive room shells. Public front doors open toward the southern pavements.
VISUAL_SHELLS = (
    ("Home 1", 45, 9, 63, 26, 52, 53, "home-wood", "bottom"),
    ("University", 75, 11, 97, 32, 84, 85, "civic-gray", "bottom"),
    ("Agent Academy", 111, 13, 127, 32, 112, 113, "civic-gray", "bottom"),
    ("Market", 148, 24, 159, 32, 154, 155, "civic-gray", "bottom"),
    ("Post Office", 151, 45, 169, 62, 160, 161, "civic-gray", "bottom"),
)
FLOOR_STAMPS = ()
FLOOR_PATCHES = ()

# Floor changes denote actual wet/service rooms, never arbitrary decoration.
ROOM_FLOOR_RECTS = (
    ("Home 1", 58, 13, 62, 19, ("room.floors", 32, 13)),
    ("University", 76, 24, 96, 31, ("room.floors", 25, 1)),
    ("Agent Academy", 121, 26, 126, 31, ("room.floors", 25, 1)),
    ("Post Office", 152, 55, 160, 61, ("room.floors", 25, 1)),
)

# Internal partitions keep 32px-wide circulation and intentional room doors.
WALL_RUNS = (
    ("Home 1", "horizontal", 20, 45, 63, (52, 53, 60, 61)),
    ("Home 1", "vertical", 54, 9, 20, (16, 17)),
    ("Home 1", "vertical", 58, 9, 20, (17, 18)),
    ("University", "vertical", 87, 11, 23, (19, 20)),
    ("University", "horizontal", 23, 75, 97, (84, 85, 92, 93)),
    ("Agent Academy", "vertical", 120, 13, 25, (19, 20)),
    ("Agent Academy", "horizontal", 25, 111, 127, (112, 113, 124, 125)),
    ("Post Office", "vertical", 161, 45, 61, (53, 54)),
)

# layer, left, top, right, bottom, gid
TILE_FILLS = (
    ("Exterior Ground", 48, 27, 64, 32, 1328),  # Home 1 garden patio.
    # The first-pass University facade sat four tiles above the actual cutaway.
    ("Foreground L1", 73, 4, 100, 8, 0),
)

# Exact, exclusive rectangles containing the first-pass facade shell. These are
# intentionally narrow so a migration cannot erase production interior art.
SAFE_LEGACY_CLEAR_RECTS = {
    "University": ((73, 8, 100, 10), (73, 10, 74, 21), (98, 10, 100, 21)),
    "Agent Academy": ((109, 10, 130, 12), (109, 12, 110, 32), (128, 12, 130, 26)),
    "Market": ((147, 22, 161, 23), (147, 23, 148, 30), (160, 23, 161, 30)),
    "Post Office": (
        (149, 43, 172, 44),
        (149, 44, 150, 64),
        (170, 44, 172, 64),
        (150, 63, 170, 64),
    ),
}
SAFE_TOWN_CLEAR_RECTS = (
    (45, 7, 54, 8),
    (109, 8, 130, 10),
    (148, 20, 160, 22),
    (149, 41, 172, 43),
)
LEGACY_TILESET_CLEARS = (
    (
        "office",
        tuple(
            rect
            for sector in ("University", "Agent Academy", "Market", "Post Office")
            for rect in SAFE_LEGACY_CLEAR_RECTS[sector]
        ),
    ),
    ("interiors", SAFE_LEGACY_CLEAR_RECTS["Market"]),
    ("town", SAFE_TOWN_CLEAR_RECTS),
)

# Only the detached Office-source University wall survives outside TARGET_BOUNDS.
_UNIVERSITY_LEGACY_WALL_CELLS = (
    *((x, 8) for x in range(73, 100)),
    (73, 9), (86, 9), (99, 9),
    *((73, y) for y in range(10, 20)),
    *((99, y) for y in range(10, 20)),
    (73, 20), (98, 20), (99, 20),
)
TILE_EDITS = tuple(("Wall", x, y, 0) for x, y in _UNIVERSITY_LEGACY_WALL_CELLS)

# Native 2x2 openings replace oversized 48px facade objects.
VISUAL_TILE_EDITS = (
    ("Wall", 52, 25, ("room.arched_entryways", 18, 2)),
    ("Wall", 53, 25, ("room.arched_entryways", 18, 3)),
    ("Wall", 52, 26, ("room.arched_entryways", 19, 2)),
    ("Wall", 53, 26, ("room.arched_entryways", 19, 3)),
    ("Wall", 84, 31, ("room.arched_entryways", 10, 4)),
    ("Wall", 85, 31, ("room.arched_entryways", 10, 5)),
    ("Wall", 84, 32, ("room.arched_entryways", 11, 4)),
    ("Wall", 85, 32, ("room.arched_entryways", 11, 5)),
    ("Wall", 112, 31, ("room.arched_entryways", 10, 4)),
    ("Wall", 113, 31, ("room.arched_entryways", 10, 5)),
    ("Wall", 112, 32, ("room.arched_entryways", 11, 4)),
    ("Wall", 113, 32, ("room.arched_entryways", 11, 5)),
    ("Wall", 154, 31, ("room.arched_entryways", 22, 4)),
    ("Wall", 155, 31, ("room.arched_entryways", 22, 5)),
    ("Wall", 154, 32, ("room.arched_entryways", 23, 4)),
    ("Wall", 155, 32, ("room.arched_entryways", 23, 5)),
    ("Wall", 160, 61, ("room.arched_entryways", 22, 4)),
    ("Wall", 161, 61, ("room.arched_entryways", 22, 5)),
    ("Wall", 160, 62, ("room.arched_entryways", 23, 4)),
    ("Wall", 161, 62, ("room.arched_entryways", 23, 5)),
)

# sector, zone, semantic role, purpose cluster, stable asset key, visual x, visual y
PLACEMENTS = (
    # Home 1: compact house, separate garden, and no indoor patio fiction.
    ("Home 1", "home_1.living_room", "storage", "media wall", "prop.interiors_v3.living.0038", 47, 14),
    ("Home 1", "home_1.living_room", "media", "media wall", "prop.interiors_v3.living.0019", 52, 14),
    ("Home 1", "home_1.living_room", "common-room-table", "conversation set", "prop.office.side_table", 49, 17),
    ("Home 1", "home_1.living_room", "lounge-seating", "conversation set", "prop.interiors_v3.living.0004", 52, 18),
    ("Home 1", "home_1.living_room", "lounge-seating", "conversation set", "prop.interiors_v3.living.0003", 49, 19),
    ("Home 1", "home_1.living_room", "plant", "garden household", "prop.interiors_v3.living.0013", 47, 19),
    ("Home 1", "home_1.living_room", "common-room-table", "family dining", "prop.office.table_walnut_medium", 52, 19),
    ("Home 1", "home_1.kitchen", "cooking-area", "sink run", "prop.interiors_v3.kitchen.0121", 55, 15),
    ("Home 1", "home_1.kitchen", "prep", "sink run", "prop.interiors_v3.kitchen.0142", 55, 14),
    ("Home 1", "home_1.kitchen", "cooking-area", "cook line", "prop.interiors_v3.kitchen.0148", 57, 17),
    ("Home 1", "home_1.kitchen", "refrigerator", "cold storage", "prop.interiors_v3.kitchen.0160", 57, 16),
    ("Home 1", "home_1.bathroom", "shower", "washroom", "prop.interiors_v3.bathroom.0064", 59, 14),
    ("Home 1", "home_1.bathroom", "wash", "washroom", "prop.interiors_v3.bathroom.0151", 61, 14),
    ("Home 1", "home_1.bathroom", "toilet-fixture", "washroom", "prop.interiors_v3.bathroom.0021", 59, 19),
    ("Home 1", "home_1.bathroom", "storage", "washroom", "prop.interiors_v3.bathroom.0083", 61, 19),
    ("Home 1", "home_1.bedroom", "closet", "sleep storage", "prop.interiors_v3.bedroom.0388", 47, 24),
    ("Home 1", "home_1.bedroom", "bed", "sleep", "prop.interiors_v3.bedroom.0088", 50, 24),
    ("Home 1", "home_1.bedroom", "bed", "guest sleep", "prop.interiors_v3.bedroom.0088", 54, 24),
    ("Home 1", "home_1.bedroom", "nightstand", "sleep", "prop.office.side_table", 52, 24),
    ("Home 1", "home_1.bedroom", "closet", "sleep storage", "prop.interiors_v3.bedroom.0386", 62, 24),
    ("Home 1", "home_1.bedroom", "desk", "garden planning", "prop.interiors_v3.bedroom.0263", 59, 24),
    ("Home 1", "home_1.bedroom", "desk-chair", "garden planning", "prop.interiors_v3.classroom_library.0002", 59, 25),
    ("Home 1", "home_1.garden", "garden-seat", "potting garden", "prop.garden.bench_horizontal", 48, 29),
    ("Home 1", "home_1.garden", "potting-display", "potting garden", "prop.interiors_v3.grocery.0371", 54, 30),
    ("Home 1", "home_1.garden", "flower-display", "potting garden", "prop.interiors_v3.grocery.0374", 58, 30),
    ("Home 1", "home_1.garden", "shade-tree", "potting garden", "prop.landscape.tree_07", 62, 30),
    ("Home 1", "home_1.garden", "mailbox", "front garden", "prop.street.mailbox", 46, 32),

    # University: lecture hall, research lab, and a separate cafeteria.
    ("University", "university.lecture", "lecture-board", "teaching wall", "prop.interiors_v3.classroom_library.0036", 81, 14),
    ("University", "university.lecture", "instructor-desk", "teaching wall", "prop.interiors_v3.classroom_library.0025", 81, 16),
    ("University", "university.lecture", "globe", "teaching wall", "prop.interiors_v3.classroom_library.0034", 85, 16),
    ("University", "university.lecture", "reference-shelf", "reference wall", "prop.interiors_v3.classroom_library.0043", 77, 15),
    ("University", "university.lecture", "lecture-seating", "lecture row A", "prop.interiors_v3.classroom_library.0015", 78, 19),
    ("University", "university.lecture", "lecture-seating", "lecture row A", "prop.interiors_v3.classroom_library.0016", 84, 19),
    ("University", "university.lecture", "lecture-seating", "lecture row B", "prop.interiors_v3.classroom_library.0017", 78, 22),
    ("University", "university.lecture", "lecture-seating", "lecture row B", "prop.interiors_v3.classroom_library.0018", 84, 22),
    ("University", "university.study_lab", "reference-shelf", "research wall", "prop.interiors_v3.classroom_library.0055", 90, 15),
    ("University", "university.study_lab", "reference-shelf", "research wall", "prop.interiors_v3.classroom_library.0058", 95, 15),
    ("University", "university.study_lab", "computer-station", "research workstation", "prop.office.computer_desk", 90, 18),
    ("University", "university.study_lab", "computer-station", "research workstation", "prop.office.computer_desk", 95, 18),
    ("University", "university.study_lab", "study-chair", "research workstation", "prop.interiors_v3.classroom_library.0002", 90, 20),
    ("University", "university.study_lab", "study-chair", "research workstation", "prop.interiors_v3.classroom_library.0004", 95, 20),
    ("University", "university.study_lab", "reference-table", "research bench", "prop.interiors_v3.classroom_library.0015", 90, 22),
    ("University", "university.study_lab", "reference-table", "research bench", "prop.interiors_v3.classroom_library.0016", 95, 22),
    ("University", "university.cafeteria", "prep", "service kitchen", "prop.interiors_v3.kitchen.0121", 92, 24),
    ("University", "university.cafeteria", "prep", "service kitchen", "prop.interiors_v3.kitchen.0142", 92, 23),
    ("University", "university.cafeteria", "vending", "service kitchen", "prop.office.vending_machine", 95, 24),
    ("University", "university.cafeteria", "refrigerator", "service kitchen", "prop.interiors_v3.kitchen.0160", 97, 24),
    ("University", "university.cafeteria", "service-counter", "service line", "prop.office.counter_cream_left", 87, 26),
    ("University", "university.cafeteria", "service-counter", "service line", "prop.office.counter_cream_middle", 89, 26),
    ("University", "university.cafeteria", "service-counter", "service line", "prop.office.counter_cream_right", 91, 26),
    ("University", "university.cafeteria", "food-display", "service line", "prop.interiors_v3.ice_cream.0020", 87, 25),
    ("University", "university.cafeteria", "food-display", "service line", "prop.interiors_v3.ice_cream.0023", 90, 25),
    ("University", "university.cafeteria", "dining-table", "west dining group", "prop.office.table_light", 82, 29),
    ("University", "university.cafeteria", "dining-table", "east dining group", "prop.office.table_walnut", 91, 29),
    ("University", "university.cafeteria", "dining-chair", "west dining group", "prop.interiors_v3.kitchen.0369", 78, 29),
    ("University", "university.cafeteria", "dining-chair", "west dining group", "prop.interiors_v3.kitchen.0372", 82, 29),
    ("University", "university.cafeteria", "dining-chair", "east dining group", "prop.interiors_v3.kitchen.0369", 89, 29),
    ("University", "university.cafeteria", "dining-chair", "east dining group", "prop.interiors_v3.kitchen.0372", 94, 29),
    ("University", "university.cafeteria", "waste-bin", "tray return", "prop.office.waste_bin", 89, 31),

    # Agent Academy: simulator lab, classroom, reception, and staff lounge.
    ("Agent Academy", "academy.training_lab", "simulator-monitor", "simulator wall", "prop.interiors_v3.shooting_range.0011", 113, 16),
    ("Agent Academy", "academy.training_lab", "simulator-monitor", "simulator wall", "prop.interiors_v3.shooting_range.0012", 117, 16),
    ("Agent Academy", "academy.training_lab", "training-simulator", "simulator bay", "prop.office.training_station", 113, 19),
    ("Agent Academy", "academy.training_lab", "training-simulator", "simulator bay", "prop.office.training_station", 117, 19),
    ("Agent Academy", "academy.training_lab", "target-trainer", "practical circuit", "prop.interiors_v3.shooting_range.0015", 113, 23),
    ("Agent Academy", "academy.training_lab", "fitness-trainer", "practical circuit", "prop.interiors_v3.gym.0176", 118, 23),
    ("Agent Academy", "academy.training_lab", "training-mat", "practical circuit", "prop.interiors_v3.gym.0196", 115, 24),
    ("Agent Academy", "academy.training_lab", "training-chart", "debrief wall", "prop.office.wall_chart", 119, 16),
    ("Agent Academy", "academy.classroom", "class-board", "teaching wall", "prop.interiors_v3.classroom_library.0036", 124, 16),
    ("Agent Academy", "academy.classroom", "instructor-desk", "teaching wall", "prop.interiors_v3.classroom_library.0025", 124, 18),
    ("Agent Academy", "academy.classroom", "classroom-seating", "class row A", "prop.interiors_v3.classroom_library.0015", 122, 20),
    ("Agent Academy", "academy.classroom", "classroom-seating", "class row A", "prop.interiors_v3.classroom_library.0015", 126, 20),
    ("Agent Academy", "academy.classroom", "classroom-seating", "class row B", "prop.interiors_v3.classroom_library.0017", 122, 24),
    ("Agent Academy", "academy.classroom", "classroom-seating", "class row B", "prop.interiors_v3.classroom_library.0017", 126, 24),
    ("Agent Academy", "academy.reception", "notice-board", "information wall", "prop.office.notice_board", 115, 28),
    ("Agent Academy", "academy.reception", "reception-desk", "front desk", "prop.office.counter_walnut_left", 110, 30),
    ("Agent Academy", "academy.reception", "reception-desk", "front desk", "prop.office.counter_walnut_right", 114, 30),
    ("Agent Academy", "academy.reception", "terminal", "front desk", "prop.office.monitor_blue", 115, 29),
    ("Agent Academy", "academy.lounge", "vending", "refreshment wall", "prop.office.vending_machine", 125, 28),
    ("Agent Academy", "academy.lounge", "lounge-seating", "conversation set", "prop.office.armchair_mustard", 120, 30),
    ("Agent Academy", "academy.lounge", "lounge-seating", "conversation set", "prop.office.sofa_dark", 123, 30),
    ("Agent Academy", "academy.lounge", "side-table", "conversation set", "prop.office.side_table", 121, 31),
    ("Agent Academy", "academy.lounge", "plant", "refreshment wall", "prop.interiors_v3.living.0016", 126, 31),

    # Market: continuous stock wall, fresh produce, and two clear checkouts.
    ("Market", "market.retail", "stock-display", "chilled wall", "prop.interiors_v3.grocery.0058", 150, 28),
    ("Market", "market.retail", "stock-display", "chilled wall", "prop.interiors_v3.grocery.0060", 152, 28),
    ("Market", "market.retail", "stock-display", "chilled wall", "prop.interiors_v3.grocery.0062", 154, 28),
    ("Market", "market.retail", "stock-display", "dry-goods wall", "prop.interiors_v3.grocery.0099", 156, 28),
    ("Market", "market.retail", "stock-display", "dry-goods wall", "prop.interiors_v3.grocery.0101", 158, 28),
    ("Market", "market.checkout", "checkout-counter", "west checkout", "prop.interiors_v3.grocery.0162", 150, 31),
    ("Market", "market.checkout", "checkout-counter", "east checkout", "prop.interiors_v3.grocery.0166", 158, 31),
    ("Market", "market.retail", "produce-crate", "fresh produce", "prop.interiors_v3.grocery.0371", 151, 29),
    ("Market", "market.retail", "produce-crate", "fresh produce", "prop.interiors_v3.grocery.0373", 153, 29),
    ("Market", "market.retail", "produce-crate", "fresh produce", "prop.interiors_v3.grocery.0374", 157, 29),
    ("Market", "market.checkout", "shopping-cart", "customer tools", "prop.interiors_v3.grocery.0413", 150, 33),
    ("Market", "market.checkout", "shopping-cart", "customer tools", "prop.interiors_v3.grocery.0414", 158, 33),

    # Post Office: clerk line, sorting room, packing benches, and waiting bay.
    ("Post Office", "post.service", "service-notice", "postal information", "prop.office.notice_board", 153, 49),
    ("Post Office", "post.service", "rate-board", "postal information", "prop.office.town_map", 157, 49),
    ("Post Office", "post.service", "records", "clerk support", "prop.office.filing_cabinet", 159, 49),
    ("Post Office", "post.service", "postal-terminal", "west clerk", "prop.office.cash_register", 153, 52),
    ("Post Office", "post.service", "postal-terminal", "east clerk", "prop.office.cash_register", 157, 52),
    ("Post Office", "post.service", "clerk-chair", "west clerk", "prop.office.chair_blue", 153, 53),
    ("Post Office", "post.service", "clerk-chair", "east clerk", "prop.office.chair_orange", 157, 53),
    ("Post Office", "post.service", "printer", "clerk support", "prop.office.printer_station", 159, 52),
    ("Post Office", "post.service", "postal-counter", "service line", "prop.office.counter_cream_left", 152, 54),
    ("Post Office", "post.service", "postal-counter", "service line", "prop.office.counter_cream_middle", 154, 54),
    ("Post Office", "post.service", "postal-counter", "service line", "prop.office.counter_cream_middle", 156, 54),
    ("Post Office", "post.service", "postal-counter", "service line", "prop.office.counter_cream_right", 158, 54),
    ("Post Office", "post.sorting", "parcel-sorting-rack", "continuous cubby wall", "prop.library.shelf_dark_1", 163, 49),
    ("Post Office", "post.sorting", "parcel-sorting-rack", "continuous cubby wall", "prop.library.shelf_dark_2", 165, 49),
    ("Post Office", "post.sorting", "parcel-sorting-rack", "continuous cubby wall", "prop.library.shelf_dark_3", 167, 49),
    ("Post Office", "post.sorting", "parcel", "continuous cubby wall", "prop.post.package_stack", 164, 51),
    ("Post Office", "post.sorting", "parcel", "continuous cubby wall", "prop.post.package_large", 168, 51),
    ("Post Office", "post.sorting", "sorting-station", "label workstation", "prop.office.computer_desk", 164, 54),
    ("Post Office", "post.sorting", "sorting-station", "label workstation", "prop.office.printer_station", 168, 54),
    ("Post Office", "post.sorting", "sorting-station", "copy station", "prop.office.copier", 166, 57),
    ("Post Office", "post.sorting", "mail-sorting-table", "west sorting table", "prop.office.table_light", 164, 60),
    ("Post Office", "post.sorting", "mail-sorting-table", "east sorting table", "prop.office.table_light", 168, 60),
    ("Post Office", "post.sorting", "sorted-mail", "west sorting table", "prop.office.paper_stack", 164, 59),
    ("Post Office", "post.sorting", "sorted-mail", "east sorting table", "prop.office.paper_stack", 168, 59),
    ("Post Office", "post.waiting", "waiting-seating", "waiting bay", "prop.office.armchair_ice", 151, 58),
    ("Post Office", "post.waiting", "waiting-seating", "waiting bay", "prop.office.armchair_mustard", 155, 58),
    ("Post Office", "post.waiting", "side-table", "waiting bay", "prop.office.side_table", 153, 58),
    ("Post Office", "post.waiting", "parcel-preparation-table", "packing station", "prop.office.table_light", 158, 57),
    ("Post Office", "post.waiting", "packing-forms", "packing station", "prop.office.paper_stack", 158, 56),
    ("Post Office", "post.waiting", "parcel", "packing station", "prop.post.package_small", 159, 57),
    ("Post Office", "post.waiting", "water-cooler", "waiting support", "prop.office.water_cooler", 151, 61),
)
