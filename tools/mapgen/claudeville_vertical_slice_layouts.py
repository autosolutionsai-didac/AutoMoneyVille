"""Explicit visual records for the three Claudeville production slices."""

from __future__ import annotations

from types import SimpleNamespace

SLICE_REVISION = 14
TARGETS = {"Bank", "Home 5", "Claudeville Cafe"}
TARGET_BOUNDS = {
    "Bank": (10, 12, 29, 32),
    "Home 5": (52, 70, 67, 92),
    "Claudeville Cafe": (92, 43, 109, 64),
}
V3_TILE_SOURCES = ("room.floors", "room.walls", "room.arched_entryways")
FLOOR_PATTERNS = {
    "cafe-wood": ((("room.floors", 25, 1),),),
    "civic-gray": ((("room.floors", 9, 13),),),
    "home-wood": ((("room.floors", 12, 1),),),
}
WALL_TILE_STYLE = {
    "horizontal": ("room.walls", 0, 12),
    "top_left": ("room.walls", 0, 11),
    "top_right": ("room.walls", 0, 14),
    "left": ("room.walls", 1, 16),
    "right": ("room.walls", 1, 16),
}
VISUAL_SHELLS = (
    ("Bank", 11, 13, 28, 31, 18, 19, "civic-gray", "bottom"),
    ("Home 5", 53, 71, 66, 91, 58, 59, "home-wood", "top"),
    ("Claudeville Cafe", 93, 44, 108, 57, 100, 101, "cafe-wood", "bottom"),
)
FLOOR_STAMPS = ()
FLOOR_PATCHES = ()
ROOM_FLOOR_RECTS = (
    ("Bank", 12, 14, 18, 19, ("room.floors", 10, 13)),
    ("Bank", 20, 14, 27, 22, ("room.floors", 8, 13)),
    ("Bank", 20, 24, 27, 28, ("room.floors", 10, 13)),
    ("Home 5", 61, 73, 65, 81, ("room.floors", 10, 1)),
    ("Home 5", 54, 83, 62, 90, ("room.floors", 11, 1)),
    ("Home 5", 64, 83, 65, 90, ("room.floors", 32, 13)),
    ("Claudeville Cafe", 94, 45, 103, 51, ("room.floors", 9, 13)),
    ("Claudeville Cafe", 105, 45, 107, 50, ("room.floors", 32, 13)),
)
WALL_RUNS = (
    ("Bank", "horizontal", 20, 11, 19, ()),
    ("Bank", "vertical", 19, 13, 20, (17, 18)),
    ("Home 5", "vertical", 60, 71, 82, (76, 77)),
    ("Home 5", "horizontal", 82, 53, 66, (58, 59)),
    ("Home 5", "vertical", 63, 82, 91, (85, 86)),
    ("Claudeville Cafe", "vertical", 104, 44, 51, (48, 49)),
    ("Claudeville Cafe", "horizontal", 51, 104, 108, ()),
)
VISUAL_TILE_EDITS = (
    ("Wall", 18, 30, ("room.arched_entryways", 10, 4)),
    ("Wall", 19, 30, ("room.arched_entryways", 10, 5)),
    ("Wall", 18, 31, ("room.arched_entryways", 11, 4)),
    ("Wall", 19, 31, ("room.arched_entryways", 11, 5)),
    ("Wall", 58, 71, ("room.arched_entryways", 18, 2)),
    ("Wall", 59, 71, ("room.arched_entryways", 18, 3)),
    ("Wall", 58, 72, ("room.arched_entryways", 19, 2)),
    ("Wall", 59, 72, ("room.arched_entryways", 19, 3)),
    ("Wall", 100, 56, ("room.arched_entryways", 22, 4)),
    ("Wall", 101, 56, ("room.arched_entryways", 22, 5)),
    ("Wall", 100, 57, ("room.arched_entryways", 23, 4)),
    ("Wall", 101, 57, ("room.arched_entryways", 23, 5)),
)
LEGACY_FACADE_CLEARS = (
    ("Foreground L1", 10, 10, 29, 12),
    ("Foreground L1", 97, 41, 106, 43),
)
INTERACTION_STANCE_UPDATES = (
    ("Claudeville Cafe", "cafe.service.service-counter-001", 49, 24),
)
CLEAR_TILE_LAYERS = (
    "Interior Furniture L1", "Interior Furniture L2", "Foreground L1", "Foreground L2",
)

# sector, zone, semantic role, cluster, stable asset key, visual x, visual y
PLACEMENTS = (
    # Bank: secure archive, operations, teller line, advisory and customer queue.
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.filing_cabinet", 13, 18),
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.display_cabinet", 16, 18),
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.filing_cabinet", 18, 18),
    ("Bank", "bank.archive", "archive-supplies", "secure archive", "prop.office.paper_stack", 16, 17),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.computer_desk", 22, 17),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.manager_chair", 22, 19),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.computer_desk", 26, 17),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.manager_chair", 26, 19),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.printer_station", 24, 20),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.notice_board", 25, 14),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_cream_left", 21, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_cream_middle", 23, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_cream_middle", 25, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_cream_right", 27, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.cash_register", 22, 22),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.cash_register", 26, 22),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.chair_blue", 22, 21),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.chair_orange", 26, 21),
    ("Bank", "bank.advisory", "advisory-desk", "advisory west", "prop.office.computer_desk", 13, 24),
    ("Bank", "bank.advisory", "advisory-desk", "advisory west", "prop.office.manager_chair", 13, 25),
    ("Bank", "bank.advisory", "advisory-desk", "advisory west", "prop.office.chair_blue_side", 16, 24),
    ("Bank", "bank.advisory", "advisory-desk", "advisory east", "prop.office.computer_desk", 13, 28),
    ("Bank", "bank.advisory", "advisory-desk", "advisory east", "prop.office.manager_chair", 13, 29),
    ("Bank", "bank.advisory", "advisory-desk", "advisory east", "prop.office.chair_orange_side", 16, 28),
    ("Bank", "bank.advisory", "advisory-desk", "advisory support", "prop.office.wall_chart", 13, 22),
    ("Bank", "bank.advisory", "advisory-desk", "advisory support", "prop.office.water_cooler", 16, 30),
    ("Bank", "bank.waiting", "waiting-seating", "waiting", "prop.office.sofa_dark", 22, 29),
    ("Bank", "bank.waiting", "side-table", "waiting", "prop.office.side_table", 24, 29),
    ("Bank", "bank.waiting", "waiting-seating", "waiting", "prop.office.armchair_dark", 26, 29),
    ("Bank", "bank.waiting", "wall-decor", "queue information", "prop.office.town_map", 27, 26),
    ("Bank", "bank.waiting", "plant", "waiting comfort", "prop.interiors_v3.living.0017", 27, 30),

    # Home 5: entry/living and kitchen above; bedroom, bathroom and storage below.
    ("Home 5", "home_5.living_room", "wall-decor", "entry warmth", "prop.interiors_v3.living.0012", 56, 73),
    ("Home 5", "home_5.living_room", "shelf", "media", "prop.interiors_v3.living.0019", 56, 77),
    ("Home 5", "home_5.living_room", "plant", "entry warmth", "prop.interiors_v3.living.0016", 59, 76),
    ("Home 5", "home_5.living_room", "lounge-seating", "media", "prop.interiors_v3.bedroom.0424", 55, 79),
    ("Home 5", "home_5.living_room", "common-room-table", "media", "prop.office.side_table", 58, 79),
    ("Home 5", "home_5.living_room", "decor", "entry console", "prop.interiors_v3.living.0052", 54, 75),
    ("Home 5", "home_5.kitchen", "cooking-area", "kitchen", "prop.interiors_v3.kitchen.0121", 62, 75),
    ("Home 5", "home_5.kitchen", "cooking-area", "kitchen", "prop.interiors_v3.kitchen.0142", 62, 74),
    ("Home 5", "home_5.kitchen", "cooking-area", "kitchen", "prop.interiors_v3.kitchen.0156", 64, 75),
    ("Home 5", "home_5.kitchen", "refrigerator", "kitchen", "prop.interiors_v3.kitchen.0160", 63, 79),
    ("Home 5", "home_5.kitchen", "dining-table", "kitchen dining", "prop.office.table_walnut_medium", 63, 81),
    ("Home 5", "home_5.kitchen", "dining-chair", "kitchen dining", "prop.interiors_v3.kitchen.0369", 61, 81),
    ("Home 5", "home_5.kitchen", "dining-chair", "kitchen dining", "prop.interiors_v3.kitchen.0372", 65, 81),
    ("Home 5", "home_5.bedroom", "wall-decor", "resident planning", "prop.interiors_v3.bedroom.0302", 56, 84),
    ("Home 5", "home_5.bedroom", "desk", "planning", "prop.interiors_v3.bedroom.0262", 60, 86),
    ("Home 5", "home_5.bedroom", "desk", "planning", "prop.office.notice_board", 60, 84),
    ("Home 5", "home_5.bedroom", "bed", "sleep", "prop.interiors_v3.bedroom.0088", 56, 88),
    ("Home 5", "home_5.bedroom", "decor", "bedside", "prop.interiors_v3.living.0008", 59, 88),
    ("Home 5", "home_5.bedroom", "plant", "bedroom comfort", "prop.interiors_v3.living.0015", 54, 86),
    ("Home 5", "home_5.bedroom", "storage", "storage", "prop.interiors_v3.bedroom.0384", 62, 89),
    ("Home 5", "home_5.bathroom", "wash", "bathroom", "prop.interiors_v3.bathroom.0002", 65, 85),
    ("Home 5", "home_5.bathroom", "toilet", "bathroom", "prop.interiors_v3.bathroom.0035", 64, 88),
    ("Home 5", "home_5.bathroom", "shower", "bathroom", "prop.interiors_v3.bathroom.0064", 64, 90),

    # Cafe: prep workflow, enclosed restroom, display counter and complete seating sets.
    ("Claudeville Cafe", "cafe.service", "wall-decor", "menu", "prop.interiors_v3.ice_cream.0012", 98, 46),
    ("Claudeville Cafe", "cafe.service", "wall-decor", "menu", "prop.interiors_v3.ice_cream.0015", 101, 46),
    ("Claudeville Cafe", "cafe.service", "decor", "warm lighting", "prop.interiors_v3.living.0012", 102, 45),
    ("Claudeville Cafe", "cafe.service", "prep", "prep kitchen", "prop.interiors_v3.kitchen.0160", 95, 49),
    ("Claudeville Cafe", "cafe.service", "prep", "prep kitchen", "prop.interiors_v3.kitchen.0121", 97, 49),
    ("Claudeville Cafe", "cafe.service", "prep", "prep kitchen", "prop.interiors_v3.kitchen.0142", 97, 48),
    ("Claudeville Cafe", "cafe.service", "cooking-area", "prep island", "prop.interiors_v3.kitchen.0156", 100, 48),
    ("Claudeville Cafe", "cafe.service", "prep", "prep kitchen", "prop.office.coffee_station", 103, 48),
    ("Claudeville Cafe", "cafe.service", "storage", "prep kitchen", "prop.interiors_v3.kitchen.0195", 103, 49),
    ("Claudeville Cafe", "cafe.restroom", "wash", "restroom", "prop.interiors_v3.bathroom.0002", 106, 47),
    ("Claudeville Cafe", "cafe.restroom", "toilet", "restroom", "prop.interiors_v3.bathroom.0035", 105, 50),
    ("Claudeville Cafe", "cafe.service", "food-display", "display freezer", "prop.interiors_v3.ice_cream.0002", 96, 50),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0100", 98, 52),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0101", 100, 52),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0102", 102, 52),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0100", 104, 52),
    ("Claudeville Cafe", "cafe.service", "checkout-terminal", "service line", "prop.office.cash_register", 104, 51),
    ("Claudeville Cafe", "cafe.dining", "plant", "dining comfort", "prop.interiors_v3.living.0017", 94, 53),
    ("Claudeville Cafe", "cafe.dining", "dining-table", "west table", "prop.office.table_walnut", 96, 56),
    ("Claudeville Cafe", "cafe.dining", "dining-chair", "west table", "prop.interiors_v3.kitchen.0369", 94, 56),
    ("Claudeville Cafe", "cafe.dining", "dining-chair", "west table", "prop.interiors_v3.kitchen.0372", 98, 56),
    ("Claudeville Cafe", "cafe.dining", "dining-table", "east table", "prop.office.table_walnut_medium", 104, 56),
    ("Claudeville Cafe", "cafe.dining", "dining-chair", "east table", "prop.interiors_v3.kitchen.0369", 102, 56),
    ("Claudeville Cafe", "cafe.dining", "dining-chair", "east table", "prop.interiors_v3.kitchen.0372", 106, 56),
    ("Claudeville Cafe", "cafe.terrace", "terrace-table", "west terrace", "prop.office.table_light", 95, 59),
    ("Claudeville Cafe", "cafe.terrace", "terrace-chair", "west terrace", "prop.interiors_v3.kitchen.0369", 93, 59),
    ("Claudeville Cafe", "cafe.terrace", "terrace-chair", "west terrace", "prop.interiors_v3.kitchen.0372", 97, 59),
    ("Claudeville Cafe", "cafe.terrace", "terrace-table", "east terrace", "prop.office.table_light", 105, 61),
    ("Claudeville Cafe", "cafe.terrace", "terrace-chair", "east terrace", "prop.interiors_v3.kitchen.0369", 103, 61),
    ("Claudeville Cafe", "cafe.terrace", "terrace-chair", "east terrace", "prop.interiors_v3.kitchen.0372", 107, 61),
    ("Claudeville Cafe", "cafe.terrace", "planter", "terrace boundary", "prop.landscape.flower_bush_01", 92, 62),
    ("Claudeville Cafe", "cafe.terrace", "planter", "terrace boundary", "prop.landscape.flower_bush_03", 107, 59),
)

STRUCTURE_CONFIG = SimpleNamespace(
    FLOOR_PATCHES=FLOOR_PATCHES,
    FLOOR_PATTERNS=FLOOR_PATTERNS,
    FLOOR_STAMPS=FLOOR_STAMPS,
    ROOM_FLOOR_RECTS=ROOM_FLOOR_RECTS,
    TARGET_BOUNDS=TARGET_BOUNDS,
    TARGETS=TARGETS,
    V3_TILE_SOURCES=V3_TILE_SOURCES,
    VISUAL_TILE_EDITS=VISUAL_TILE_EDITS,
    VISUAL_SHELLS=VISUAL_SHELLS,
    WALL_RUNS=WALL_RUNS,
    WALL_TILE_STYLE=WALL_TILE_STYLE,
)
