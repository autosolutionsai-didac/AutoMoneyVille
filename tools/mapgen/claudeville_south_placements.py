"""Purposeful native-16 placements and semantic migrations for south Claudeville."""

TARGET_BOUNDS = {
    "Home 2": (4, 70, 18, 91),
    "Home 3": (20, 70, 34, 91),
    "Home 4": (36, 70, 50, 91),
    "Home 6": (68, 70, 84, 91),
    "Town Hall": (86, 68, 108, 91),
    "Home 7": (110, 70, 124, 91),
    "Home 8": (126, 70, 140, 91),
    "Home 9": (142, 70, 158, 91),
    "Home 10": (160, 70, 174, 91),
}
TARGETS = frozenset(TARGET_BOUNDS)
REVISION = 11

# Revision-one floor data is retained for audit only; it painted fragmented
# semantic cells and is intentionally excluded from the production pass.
ZONE_FLOOR_PATCHES_V1 = (
    ("Home 2", "home_2.main_room", 54544),
    ("Home 2", "home_2.bathroom", 54626),
    ("Home 3", "home_3.main_room", 54544),
    ("Home 3", "home_3.bathroom", 54626),
    ("Home 4", "home_4.main_room", 53796),
    ("Home 4", "home_4.bathroom", 54626),
    ("Home 6", "home_6.living_room", 54544),
    ("Home 6", "home_6.bedroom", 54544),
    ("Home 6", "home_6.kitchen", 54626),
    ("Home 6", "home_6.bathroom", 55219),
    ("Home 7", "home_7.living_room", 54626),
    ("Home 7", "home_7.bedroom", 54626),
    ("Home 7", "home_7.kitchen", 54544),
    ("Home 7", "home_7.bathroom", 55219),
    ("Home 8", "home_8.living_room", 53796),
    ("Home 8", "home_8.bedroom", 53796),
    ("Home 8", "home_8.kitchen", 54544),
    ("Home 8", "home_8.bathroom", 55219),
    ("Home 9", "home_9.living_room", 54626),
    ("Home 9", "home_9.bedroom", 54626),
    ("Home 9", "home_9.kitchen", 54544),
    ("Home 9", "home_9.bathroom", 55219),
    ("Home 10", "home_10.living_room", 54544),
    ("Home 10", "home_10.bedroom", 54544),
    ("Home 10", "home_10.kitchen", 38169),
    ("Home 10", "home_10.bathroom", 55219),
    ("Town Hall", "hall.public_service", 55219),
    ("Town Hall", "hall.administration", 55219),
    ("Town Hall", "hall.council", 54544),
)
FLOOR_PATCHES = ()

# Remove three legacy 32px threshold remnants just outside the authoring
# rectangles. Native entry arches replace every oversized entrance object.
TILE_EDITS = (
    ("Interior Ground", 16, 91, 0),
    ("Interior Ground", 17, 91, 0),
    ("Interior Ground", 32, 91, 0),
    ("Interior Ground", 33, 91, 0),
    ("Interior Ground", 36, 91, 0),
    ("Interior Ground", 37, 91, 0),
)

SAFE_LEGACY_FACADE_RECTS = (
    ("Home 2", 5, 73, 18, 75),
    ("Home 3", 21, 72, 34, 74),
    ("Home 4", 38, 73, 50, 75),
    ("Home 6", 69, 73, 84, 75),
    ("Town Hall", 88, 73, 107, 75),
    ("Home 7", 111, 73, 124, 75),
    ("Home 8", 127, 73, 140, 75),
    ("Home 9", 143, 73, 158, 75),
    ("Home 10", 161, 73, 174, 75),
)
TILE_FILLS = tuple(
    ("Foreground L1", left, top, right, bottom, 0)
    for _sector, left, top, right, bottom in SAFE_LEGACY_FACADE_RECTS
)

V3_TILE_SOURCES = ("room.floors", "room.walls", "room.arched_entryways")
FLOOR_PATTERNS = {
    "research-oak": ((("room.floors", 12, 1),),),
    "studio-birch": ((("room.floors", 10, 1),),),
    "writer-walnut": ((("room.floors", 12, 5),),),
    "music-maple": ((("room.floors", 25, 1),),),
    "planner-cream": ((("room.floors", 10, 5),),),
    "ledger-parquet": ((("room.floors", 28, 1),),),
    "music-herringbone": ((("room.floors", 10, 9),),),
    "reader-ash": ((("room.floors", 31, 5),),),
    "civic-gray": ((("room.floors", 9, 13),),),
}
WALL_TILE_STYLE = {
    "horizontal": ("room.walls", 0, 12),
    "top_left": ("room.walls", 0, 11),
    "top_right": ("room.walls", 0, 14),
    "left": ("room.walls", 1, 16),
    "right": ("room.walls", 1, 16),
}
# sector, inclusive shell bounds, inclusive front-door gap, floor style.
VISUAL_SHELLS = (
    ("Home 2", 5, 75, 17, 90, 10, 11, "research-oak"),
    ("Home 3", 21, 74, 33, 90, 26, 27, "studio-birch"),
    ("Home 4", 38, 75, 49, 90, 42, 43, "writer-walnut"),
    ("Home 6", 69, 75, 83, 90, 76, 77, "music-maple"),
    ("Town Hall", 88, 75, 106, 90, 95, 96, "civic-gray"),
    ("Home 7", 111, 75, 123, 90, 116, 117, "planner-cream"),
    ("Home 8", 127, 75, 139, 90, 132, 133, "ledger-parquet"),
    ("Home 9", 143, 75, 157, 90, 150, 151, "music-herringbone"),
    ("Home 10", 161, 75, 173, 90, 166, 167, "reader-ash"),
)

FLOOR_STAMPS = ()

# sector, inclusive visual rectangle, floor gid. These are deliberate room
# transitions inside the continuous shells, independent of semantic geometry.
ROOM_FLOOR_RECTS = (
    ("Home 2", 6, 85, 13, 89, ("room.floors", 32, 13)),
    ("Home 3", 22, 85, 29, 89, ("room.floors", 32, 9)),
    ("Home 4", 41, 85, 48, 89, ("room.floors", 29, 13)),
    ("Home 6", 80, 76, 82, 82, ("room.floors", 25, 9)),
    ("Home 7", 120, 76, 122, 83, ("room.floors", 33, 13)),
    ("Home 8", 128, 76, 130, 83, ("room.floors", 31, 9)),
    ("Home 9", 144, 76, 147, 83, ("room.floors", 32, 5)),
    ("Home 10", 162, 76, 165, 83, ("room.floors", 29, 9)),
    ("Town Hall", 89, 84, 105, 89, ("room.floors", 25, 1)),
)

# sector, orientation, fixed coordinate, inclusive run, visual door gaps.
WALL_RUNS = (
    ("Home 2", "vertical", 12, 75, 84, (81, 82)),
    ("Home 2", "horizontal", 84, 5, 14, (8, 9)),
    ("Home 2", "vertical", 14, 84, 90, (86, 87)),
    ("Home 3", "vertical", 28, 74, 83, (79, 80)),
    ("Home 3", "horizontal", 84, 21, 33, (26, 27)),
    ("Home 3", "vertical", 30, 85, 90, (87, 88)),
    ("Home 4", "vertical", 44, 75, 82, (79, 80)),
    ("Home 4", "horizontal", 82, 44, 49, (46, 47)),
    ("Home 4", "horizontal", 84, 38, 45, (42, 43)),
    ("Home 4", "vertical", 48, 84, 90, (86, 87)),
    ("Home 6", "horizontal", 83, 69, 83, (75, 76)),
    ("Home 6", "vertical", 79, 75, 83, (79, 80)),
    ("Town Hall", "horizontal", 83, 88, 106, (95, 96, 100, 101)),
    ("Town Hall", "vertical", 97, 75, 83, (79, 80)),
    ("Home 7", "vertical", 118, 75, 90, (82, 83)),
    ("Home 7", "horizontal", 84, 111, 118, (114, 115)),
    ("Home 7", "horizontal", 84, 118, 123, (120, 121)),
    ("Home 8", "vertical", 131, 75, 84, (79, 80)),
    ("Home 8", "horizontal", 84, 127, 139, (134, 135)),
    ("Home 8", "vertical", 135, 84, 90, (86, 87)),
    ("Home 9", "horizontal", 84, 143, 157, (151, 152)),
    ("Home 9", "vertical", 148, 75, 84, (79, 80)),
    ("Home 9", "vertical", 153, 84, 90, (87, 88)),
    ("Home 10", "vertical", 166, 75, 84, (79, 80)),
    ("Home 10", "horizontal", 84, 161, 173, (164, 165)),
    ("Home 10", "vertical", 168, 84, 90, (86, 87)),
)

VISUAL_TILE_EDITS = tuple(
    ("Wall", x + dx, y + dy, ("room.arched_entryways", row + dy, column + dx))
    for x, y, row, column in (
        (10, 75, 18, 2), (26, 74, 18, 2), (42, 75, 18, 2),
        (76, 75, 18, 2), (95, 75, 22, 4), (116, 75, 18, 2),
        (132, 75, 18, 2), (150, 75, 18, 2), (166, 75, 18, 2),
    )
    for dy in range(2) for dx in range(2)
)

# sector, zone, semantic role, purpose cluster, stable asset key, visual x, visual y
PLACEMENTS = (
    # Home 2 / Milo Chen: compact research studio.
    ("Home 2", "home_2.main_room", "bed", "enclosed sleep nook", "prop.interiors_v3.bedroom.0090", 14, 78),
    ("Home 2", "home_2.main_room", "closet", "personal storage", "prop.interiors_v3.living.0037", 10, 80),
    ("Home 2", "home_2.main_room", "wardrobe", "enclosed sleep nook", "prop.interiors_v3.bedroom.0383", 16, 82),
    ("Home 2", "home_2.main_room", "desk", "research workstation", "prop.interiors_v3.bedroom.0262", 8, 80),
    ("Home 2", "home_2.main_room", "shelf", "research library", "prop.interiors_v3.classroom_library.0056", 6, 81),
    ("Home 2", "home_2.main_room", "research-board", "research workstation", "prop.office.notice_board", 7, 78),
    ("Home 2", "home_2.main_room", "kitchen-counter", "wall kitchen", "prop.interiors_v3.kitchen.0121", 8, 84),
    ("Home 2", "home_2.main_room", "kitchen-prep", "wall kitchen", "prop.interiors_v3.kitchen.0142", 8, 83),
    ("Home 2", "home_2.main_room", "cooking-area", "wall kitchen", "prop.interiors_v3.kitchen.0148", 11, 84),
    ("Home 2", "home_2.main_room", "refrigerator", "wall kitchen", "prop.interiors_v3.kitchen.0160", 12, 84),
    ("Home 2", "home_2.main_room", "sofa", "reading corner", "prop.interiors_v3.bedroom.0424", 15, 84),
    ("Home 2", "home_2.main_room", "side-table", "reading corner", "prop.interiors_v3.living.0051", 15, 85),
    ("Home 2", "home_2.bathroom", "bathroom-sink", "washroom", "prop.interiors_v3.bathroom.0002", 8, 88),
    ("Home 2", "home_2.bathroom", "shower", "washroom", "prop.interiors_v3.bathroom.0064", 8, 90),
    ("Home 2", "home_2.bathroom", "toilet", "washroom", "prop.interiors_v3.bathroom.0035", 12, 88),
    ("Home 2", "home_2.main_room", "plant", "reading corner", "prop.interiors_v3.living.0015", 16, 88),

    # Home 3 / Iris Morgan: visual-offer and art studio.
    ("Home 3", "home_3.main_room", "bed", "enclosed sleep nook", "prop.interiors_v3.bedroom.0103", 30, 78),
    ("Home 3", "home_3.main_room", "closet", "personal storage", "prop.interiors_v3.bedroom.0384", 24, 80),
    ("Home 3", "home_3.main_room", "wardrobe", "enclosed sleep nook", "prop.interiors_v3.living.0040", 32, 82),
    ("Home 3", "home_3.main_room", "desk", "art workstation", "prop.interiors_v3.art.0023", 26, 80),
    ("Home 3", "home_3.main_room", "easel", "art workstation", "prop.interiors_v3.art.0034", 27, 81),
    ("Home 3", "home_3.main_room", "wall-art", "art display", "prop.interiors_v3.art.0043", 23, 78),
    ("Home 3", "home_3.main_room", "shelf", "reference library", "prop.interiors_v3.classroom_library.0060", 22, 82),
    ("Home 3", "home_3.main_room", "kitchen-counter", "wall kitchen", "prop.interiors_v3.kitchen.0122", 25, 84),
    ("Home 3", "home_3.main_room", "kitchen-prep", "wall kitchen", "prop.interiors_v3.kitchen.0141", 25, 83),
    ("Home 3", "home_3.main_room", "cooking-area", "wall kitchen", "prop.interiors_v3.kitchen.0150", 28, 84),
    ("Home 3", "home_3.main_room", "refrigerator", "wall kitchen", "prop.interiors_v3.kitchen.0160", 29, 84),
    ("Home 3", "home_3.main_room", "sofa", "sketch review", "prop.interiors_v3.bedroom.0434", 31, 84),
    ("Home 3", "home_3.main_room", "side-table", "sketch review", "prop.interiors_v3.living.0053", 32, 85),
    ("Home 3", "home_3.bathroom", "bathroom-sink", "washroom", "prop.interiors_v3.bathroom.0003", 24, 88),
    ("Home 3", "home_3.bathroom", "shower", "washroom", "prop.interiors_v3.bathroom.0065", 24, 90),
    ("Home 3", "home_3.bathroom", "toilet", "washroom", "prop.interiors_v3.bathroom.0036", 28, 88),
    ("Home 3", "home_3.main_room", "plant", "art display", "prop.interiors_v3.living.0015", 31, 89),

    # Home 4 / Theo Grant: writing and swipe-file studio.
    ("Home 4", "home_4.main_room", "bed", "private sleep nook", "prop.interiors_v3.bedroom.0111", 40, 78),
    ("Home 4", "home_4.main_room", "closet", "private sleep nook", "prop.interiors_v3.bedroom.0387", 42, 82),
    ("Home 4", "home_4.main_room", "common-room-sofa", "reading corner", "prop.interiors_v3.bedroom.0440", 46, 81),
    ("Home 4", "home_4.main_room", "desk", "writing workstation", "prop.interiors_v3.bedroom.0266", 40, 82),
    ("Home 4", "home_4.main_room", "swipe-board", "writing workstation", "prop.office.notice_board", 46, 78),
    ("Home 4", "home_4.main_room", "bookcase", "swipe-file library", "prop.interiors_v3.classroom_library.0062", 48, 80),
    ("Home 4", "home_4.main_room", "kitchen-counter", "wall kitchen", "prop.interiors_v3.kitchen.0121", 41, 84),
    ("Home 4", "home_4.main_room", "kitchen-prep", "wall kitchen", "prop.interiors_v3.kitchen.0143", 41, 83),
    ("Home 4", "home_4.main_room", "cooking-area", "wall kitchen", "prop.interiors_v3.kitchen.0152", 44, 84),
    ("Home 4", "home_4.main_room", "refrigerator", "wall kitchen", "prop.interiors_v3.kitchen.0160", 45, 84),
    ("Home 4", "home_4.main_room", "side-table", "reading corner", "prop.interiors_v3.living.0051", 47, 82),
    ("Home 4", "home_4.bathroom", "bathroom-sink", "washroom", "prop.interiors_v3.bathroom.0005", 46, 88),
    ("Home 4", "home_4.bathroom", "shower", "washroom", "prop.interiors_v3.bathroom.0061", 42, 90),
    ("Home 4", "home_4.bathroom", "toilet", "washroom", "prop.interiors_v3.bathroom.0038", 44, 88),

    # Home 6 / Ravi Singh: market analysis and classical music.
    ("Home 6", "home_6.living_room", "shelf", "analysis library", "prop.interiors_v3.classroom_library.0069", 70, 79),
    ("Home 6", "home_6.living_room", "harp", "music corner", "prop.interiors_v3.music_sport.0058", 72, 80),
    ("Home 6", "home_6.living_room", "sofa", "conversation", "prop.interiors_v3.bedroom.0452", 74, 83),
    ("Home 6", "home_6.living_room", "common-room-table", "conversation", "prop.office.side_table", 73, 81),
    ("Home 6", "home_6.kitchen", "kitchen-counter", "wall kitchen", "prop.interiors_v3.kitchen.0121", 76, 80),
    ("Home 6", "home_6.kitchen", "kitchen-prep", "wall kitchen", "prop.interiors_v3.kitchen.0144", 76, 79),
    ("Home 6", "home_6.kitchen", "cooking-area", "wall kitchen", "prop.interiors_v3.kitchen.0154", 78, 80),
    ("Home 6", "home_6.kitchen", "refrigerator", "wall kitchen", "prop.interiors_v3.kitchen.0160", 78, 82),
    ("Home 6", "home_6.bathroom", "bathroom-sink", "washroom", "prop.interiors_v3.bathroom.0006", 81, 79),
    ("Home 6", "home_6.bathroom", "shower", "washroom", "prop.interiors_v3.bathroom.0062", 81, 82),
    ("Home 6", "home_6.bathroom", "toilet-fixture", "washroom", "prop.interiors_v3.bathroom.0042", 82, 80),
    ("Home 6", "home_6.bedroom", "bed", "sleep", "prop.interiors_v3.bedroom.0092", 77, 87),
    ("Home 6", "home_6.bedroom", "closet", "personal storage", "prop.interiors_v3.bedroom.0388", 81, 87),
    ("Home 6", "home_6.bedroom", "analysis-desk", "analysis workstation", "prop.interiors_v3.bedroom.0267", 72, 87),
    ("Home 6", "home_6.bedroom", "side-table", "sleep", "prop.interiors_v3.living.0065", 79, 88),
    ("Home 6", "home_6.bedroom", "desk-chair", "analysis workstation", "prop.interiors_v3.living.0074", 74, 89),
    ("Home 6", "home_6.garden", "garden-chair", "quiet patio", "prop.interiors_v3.living.0073", 73, 91),
    ("Home 6", "home_6.garden", "side-table", "quiet patio", "prop.interiors_v3.living.0065", 71, 91),
    ("Home 6", "home_6.bedroom", "plant", "sleep", "prop.interiors_v3.living.0017", 82, 89),

    # Home 7 / June Park: tidy project-planning household.
    ("Home 7", "home_7.living_room", "shelf", "project library", "prop.interiors_v3.classroom_library.0071", 112, 79),
    ("Home 7", "home_7.living_room", "sofa", "planning conversation", "prop.interiors_v3.bedroom.0458", 115, 83),
    ("Home 7", "home_7.living_room", "common-room-table", "planning conversation", "prop.office.side_table", 113, 81),
    ("Home 7", "home_7.kitchen", "kitchen-counter", "compact L-kitchen", "prop.interiors_v3.kitchen.0122", 119, 80),
    ("Home 7", "home_7.kitchen", "kitchen-prep", "compact L-kitchen", "prop.interiors_v3.kitchen.0145", 119, 79),
    ("Home 7", "home_7.kitchen", "cooking-area", "compact L-kitchen", "prop.interiors_v3.kitchen.0156", 116, 79),
    ("Home 7", "home_7.kitchen", "refrigerator", "compact L-kitchen", "prop.interiors_v3.kitchen.0169", 118, 82),
    ("Home 7", "home_7.bathroom", "bathroom-sink", "washroom", "prop.interiors_v3.bathroom.0009", 121, 79),
    ("Home 7", "home_7.bathroom", "shower", "washroom", "prop.interiors_v3.bathroom.0063", 121, 83),
    ("Home 7", "home_7.bathroom", "toilet", "washroom", "prop.interiors_v3.bathroom.0045", 122, 81),
    ("Home 7", "home_7.bedroom", "desk", "planning workstation", "prop.interiors_v3.bedroom.0268", 112, 87),
    ("Home 7", "home_7.bedroom", "filing", "planning workstation", "prop.office.filing_cabinet", 115, 87),
    ("Home 7", "home_7.bedroom", "bed", "sleep", "prop.interiors_v3.bedroom.0108", 119, 87),
    ("Home 7", "home_7.bedroom", "closet", "personal storage", "prop.interiors_v3.bedroom.0389", 121, 87),
    ("Home 7", "home_7.bedroom", "side-table", "sleep", "prop.interiors_v3.living.0063", 117, 88),
    ("Home 7", "home_7.bedroom", "plant", "planning workstation", "prop.interiors_v3.living.0016", 112, 89),

    # Home 8 / Amara Cole: ledger and accounting household.
    ("Home 8", "home_8.bathroom", "bathroom-sink-fixture", "washroom", "prop.interiors_v3.bathroom.0010", 129, 79),
    ("Home 8", "home_8.bathroom", "shower-fixture", "washroom", "prop.interiors_v3.bathroom.0064", 128, 83),
    ("Home 8", "home_8.bathroom", "toilet", "washroom", "prop.interiors_v3.bathroom.0050", 130, 82),
    ("Home 8", "home_8.kitchen", "kitchen-counter", "compact L-kitchen", "prop.interiors_v3.kitchen.0121", 134, 80),
    ("Home 8", "home_8.kitchen", "kitchen-prep", "compact L-kitchen", "prop.interiors_v3.kitchen.0146", 134, 79),
    ("Home 8", "home_8.kitchen", "cooking-area", "compact L-kitchen", "prop.interiors_v3.kitchen.0148", 132, 80),
    ("Home 8", "home_8.kitchen", "refrigerator", "compact L-kitchen", "prop.interiors_v3.kitchen.0160", 132, 82),
    ("Home 8", "home_8.living_room", "common-room-table", "accounting workstation", "prop.office.computer_desk", 134, 83),
    ("Home 8", "home_8.living_room", "desk-chair", "accounting workstation", "prop.office.manager_chair", 134, 84),
    ("Home 8", "home_8.living_room", "shelf", "ledger archive", "prop.interiors_v3.classroom_library.0074", 138, 77),
    ("Home 8", "home_8.living_room", "sofa", "client conversation", "prop.interiors_v3.bedroom.0464", 137, 83),
    ("Home 8", "home_8.living_room", "side-table", "client conversation", "prop.interiors_v3.living.0051", 138, 85),
    ("Home 8", "home_8.bedroom", "wardrobe", "personal storage", "prop.interiors_v3.bedroom.0383", 129, 87),
    ("Home 8", "home_8.bedroom", "bed", "sleep", "prop.interiors_v3.bedroom.0097", 132, 87),
    ("Home 8", "home_8.bedroom", "desk", "private accounts", "prop.interiors_v3.bedroom.0269", 136, 87),
    ("Home 8", "home_8.bedroom", "side-table", "sleep", "prop.interiors_v3.living.0064", 134, 88),
    ("Home 8", "home_8.bedroom", "dresser", "personal storage", "prop.interiors_v3.living.0051", 137, 89),

    # Home 9 / Felix Reed: coordination and harp hobby.
    ("Home 9", "home_9.bathroom", "bathroom-sink", "washroom", "prop.interiors_v3.bathroom.0012", 145, 79),
    ("Home 9", "home_9.bathroom", "shower", "washroom", "prop.interiors_v3.bathroom.0065", 145, 83),
    ("Home 9", "home_9.bathroom", "toilet", "washroom", "prop.interiors_v3.bathroom.0053", 147, 82),
    ("Home 9", "home_9.kitchen", "kitchen-counter", "compact L-kitchen", "prop.interiors_v3.kitchen.0122", 151, 80),
    ("Home 9", "home_9.kitchen", "kitchen-prep", "compact L-kitchen", "prop.interiors_v3.kitchen.0141", 151, 79),
    ("Home 9", "home_9.kitchen", "cooking-area", "compact L-kitchen", "prop.interiors_v3.kitchen.0150", 149, 80),
    ("Home 9", "home_9.kitchen", "refrigerator", "compact L-kitchen", "prop.interiors_v3.kitchen.0169", 149, 82),
    ("Home 9", "home_9.living_room", "harp", "music corner", "prop.interiors_v3.music_sport.0057", 154, 79),
    ("Home 9", "home_9.living_room", "common-room-table", "music lounge", "prop.office.side_table", 153, 81),
    ("Home 9", "home_9.living_room", "sofa", "music lounge", "prop.interiors_v3.bedroom.0472", 155, 82),
    ("Home 9", "home_9.living_room", "shelf", "coordination library", "prop.interiors_v3.classroom_library.0060", 156, 80),
    ("Home 9", "home_9.living_room", "coordination-board", "coordination table", "prop.office.notice_board", 156, 77),
    ("Home 9", "home_9.bedroom", "bed", "sleep", "prop.interiors_v3.bedroom.0118", 148, 87),
    ("Home 9", "home_9.bedroom", "wardrobe", "personal storage", "prop.interiors_v3.bedroom.0385", 153, 87),
    ("Home 9", "home_9.bedroom", "desk", "coordination workstation", "prop.interiors_v3.bedroom.0270", 156, 87),
    ("Home 9", "home_9.bedroom", "side-table", "sleep", "prop.interiors_v3.living.0069", 150, 88),
    ("Home 9", "home_9.bedroom", "plant", "music corner", "prop.interiors_v3.living.0018", 155, 89),
    ("Home 9", "home_9.garden", "garden-chair", "quiet patio", "prop.interiors_v3.living.0073", 153, 91),
    ("Home 9", "home_9.garden", "side-table", "quiet patio", "prop.interiors_v3.living.0067", 156, 91),

    # Home 10 / Sofia Lane: compliance and reading household.
    ("Home 10", "home_10.bathroom", "bathroom-sink", "washroom", "prop.interiors_v3.bathroom.0013", 163, 79),
    ("Home 10", "home_10.bathroom", "shower", "washroom", "prop.interiors_v3.bathroom.0061", 163, 83),
    ("Home 10", "home_10.bathroom", "toilet", "washroom", "prop.interiors_v3.bathroom.0054", 165, 82),
    ("Home 10", "home_10.kitchen", "kitchen-counter", "north-wall kitchen", "prop.interiors_v3.kitchen.0130", 170, 80),
    ("Home 10", "home_10.kitchen", "kitchen-prep", "north-wall kitchen", "prop.interiors_v3.kitchen.0143", 170, 79),
    ("Home 10", "home_10.kitchen", "cooking-area", "north-wall kitchen", "prop.interiors_v3.kitchen.0152", 168, 80),
    ("Home 10", "home_10.kitchen", "refrigerator", "north-wall kitchen", "prop.interiors_v3.kitchen.0160", 167, 82),
    ("Home 10", "home_10.living_room", "common-room-table", "reading table", "prop.office.side_table", 169, 81),
    ("Home 10", "home_10.living_room", "sofa", "reading corner", "prop.interiors_v3.bedroom.0478", 171, 82),
    ("Home 10", "home_10.living_room", "shelf", "compliance library", "prop.interiors_v3.classroom_library.0056", 171, 77),
    ("Home 10", "home_10.bedroom", "closet", "personal storage", "prop.interiors_v3.bedroom.0386", 163, 87),
    ("Home 10", "home_10.bedroom", "bed", "sleep", "prop.interiors_v3.bedroom.0135", 165, 87),
    ("Home 10", "home_10.bedroom", "filing", "compliance workstation", "prop.office.filing_cabinet", 169, 87),
    ("Home 10", "home_10.bedroom", "desk", "compliance workstation", "prop.interiors_v3.bedroom.0265", 171, 87),
    ("Home 10", "home_10.bedroom", "plant", "reading corner", "prop.interiors_v3.living.0015", 172, 89),
    ("Home 10", "home_10.bedroom", "side-table", "sleep", "prop.interiors_v3.living.0065", 167, 88),
    ("Home 10", "home_10.bedroom", "floor-lamp", "reading corner", "prop.interiors_v3.living.0085", 169, 89),

    # Town Hall: public service, complete administration, and council chamber.
    ("Town Hall", "hall.public_service", "public-counter", "service line", "prop.office.counter_cream_left", 90, 80),
    ("Town Hall", "hall.public_service", "public-counter", "service line", "prop.office.counter_cream_middle", 91, 80),
    ("Town Hall", "hall.public_service", "public-counter", "service line", "prop.office.counter_cream_middle", 92, 80),
    ("Town Hall", "hall.public_service", "public-counter", "service line", "prop.office.counter_cream_right", 93, 80),
    ("Town Hall", "hall.public_service", "service-monitor", "service line", "prop.office.monitor_blue", 90, 78),
    ("Town Hall", "hall.public_service", "service-terminal", "service line", "prop.office.cash_register", 92, 78),
    ("Town Hall", "hall.public_service", "waiting-sofa", "waiting area", "prop.office.sofa_dark", 92, 82),
    ("Town Hall", "hall.public_service", "side-table", "waiting area", "prop.office.side_table", 94, 82),
    ("Town Hall", "hall.public_service", "waiting-chair", "waiting area", "prop.office.armchair_ice", 90, 83),
    ("Town Hall", "hall.public_service", "waiting-chair", "waiting area", "prop.office.armchair_mustard", 95, 83),
    ("Town Hall", "hall.public_service", "town-map", "waiting area", "prop.office.town_map", 91, 77),
    ("Town Hall", "hall.administration", "administration-desk", "west workstation", "prop.office.computer_desk", 100, 80),
    ("Town Hall", "hall.administration", "administration-desk", "east workstation", "prop.office.computer_desk", 104, 80),
    ("Town Hall", "hall.administration", "admin-chair", "west workstation", "prop.office.chair_blue", 100, 82),
    ("Town Hall", "hall.administration", "admin-chair", "east workstation", "prop.office.chair_orange", 104, 82),
    ("Town Hall", "hall.administration", "printer", "shared administration", "prop.office.printer_station", 102, 78),
    ("Town Hall", "hall.administration", "records", "east workstation", "prop.office.filing_cabinet", 98, 82),
    ("Town Hall", "hall.administration", "admin-board", "shared administration", "prop.office.notice_board", 100, 77),
    ("Town Hall", "hall.administration", "records", "east workstation", "prop.office.display_cabinet", 106, 82),
    ("Town Hall", "hall.administration", "refreshments", "staff support", "prop.office.coffee_station", 105, 78),
    ("Town Hall", "hall.council", "council-table", "council table", "prop.interiors_v3.conference.0001", 96, 87),
    ("Town Hall", "hall.council", "council-table", "council table", "prop.interiors_v3.conference.0002", 98, 87),
    ("Town Hall", "hall.council", "council-table", "council table", "prop.interiors_v3.conference.0003", 99, 87),
    ("Town Hall", "hall.council", "council-table", "council table", "prop.interiors_v3.conference.0002", 100, 87),
    ("Town Hall", "hall.council", "council-table", "council table", "prop.interiors_v3.conference.0007", 101, 87),
    ("Town Hall", "hall.council", "council-chair", "south council seating", "prop.interiors_v3.conference.0040", 97, 89),
    ("Town Hall", "hall.council", "council-chair", "south council seating", "prop.interiors_v3.conference.0037", 99, 89),
    ("Town Hall", "hall.council", "council-chair", "south council seating", "prop.interiors_v3.conference.0038", 101, 89),
    ("Town Hall", "hall.council", "council-chair", "north council seating", "prop.interiors_v3.conference.0039", 97, 85),
    ("Town Hall", "hall.council", "council-chair", "north council seating", "prop.interiors_v3.conference.0040", 99, 85),
    ("Town Hall", "hall.council", "council-chair", "north council seating", "prop.interiors_v3.conference.0038", 101, 85),
    ("Town Hall", "hall.council", "visitor-chair", "public gallery", "prop.office.chair_blue", 91, 88),
    ("Town Hall", "hall.council", "visitor-chair", "public gallery", "prop.office.chair_orange", 104, 89),
    ("Town Hall", "hall.council", "council-screen", "presentation wall", "prop.interiors_v3.conference.0029", 99, 84),
    ("Town Hall", "hall.council", "council-board", "presentation wall", "prop.office.wall_chart", 93, 85),
    ("Town Hall", "hall.council", "records", "council support", "prop.office.display_cabinet", 105, 88),
    ("Town Hall", "hall.council", "plant", "council support", "prop.interiors_v3.living.0017", 105, 90),
)

# sector, existing zone, exact single logical shape cell to reassign.
ZONE_SHAPE_REMOVALS = (
    ("Home 8", "home_8.living_room", (65, 41)),
)

# sector, zone, room type, logical cells. Cells are unassigned after removals.
ZONE_ADDITIONS = (
    ("Home 2", "home_2.bathroom", "bathroom", ((4, 43), (6, 43))),
    ("Home 3", "home_3.bathroom", "bathroom", ((11, 43), (12, 43), (14, 43))),
    ("Home 4", "home_4.bathroom", "bathroom", ((21, 43), (23, 43))),
    ("Home 6", "home_6.bathroom", "bathroom", ((39, 39),)),
    ("Home 8", "home_8.bathroom", "bathroom", ((63, 38), (64, 38), (63, 39), (64, 39), (63, 40), (64, 40), (64, 41), (65, 41))),
    ("Home 9", "home_9.bathroom", "bathroom", ((72, 40),)),
    ("Home 10", "home_10.bathroom", "bathroom", ((82, 39),)),
)

# sector, zone, semantic id, type, logical cells, stance, art key, blocker policy.
# Home 6's toilet and Home 8's sink/shower stay visual-only: no cardinal stance exists.
INTERACTION_ADDITIONS = (
    ("Home 2", "home_2.bathroom", "home_2.bathroom.bathroom-sink-001", "bathroom-sink", ((4, 43),), (5, 43), "prop.interiors_v3.bathroom.0002", "require-blocked"),
    ("Home 2", "home_2.bathroom", "home_2.bathroom.toilet-001", "toilet", ((6, 43),), (5, 43), "prop.interiors_v3.bathroom.0035", "require-blocked"),
    ("Home 3", "home_3.bathroom", "home_3.bathroom.bathroom-sink-001", "bathroom-sink", ((12, 43),), (13, 43), "prop.interiors_v3.bathroom.0003", "require-blocked"),
    ("Home 3", "home_3.bathroom", "home_3.bathroom.toilet-001", "toilet", ((14, 43),), (13, 43), "prop.interiors_v3.bathroom.0036", "require-blocked"),
    ("Home 4", "home_4.bathroom", "home_4.bathroom.toilet-001", "toilet", ((21, 43),), (22, 43), "prop.interiors_v3.bathroom.0038", "require-blocked"),
    ("Home 4", "home_4.bathroom", "home_4.bathroom.bathroom-sink-001", "bathroom-sink", ((23, 43),), (22, 43), "prop.interiors_v3.bathroom.0005", "require-blocked"),
    ("Home 7", "home_7.bathroom", "home_7.bathroom.toilet-001", "toilet", ((61, 40),), (60, 40), "prop.interiors_v3.bathroom.0045", "require-blocked"),
    ("Home 8", "home_8.bathroom", "home_8.bathroom.toilet-001", "toilet", ((64, 41),), (65, 41), "prop.interiors_v3.bathroom.0050", "require-blocked"),
    ("Home 9", "home_9.bathroom", "home_9.bathroom.toilet-001", "toilet", ((72, 40),), (71, 40), "prop.interiors_v3.bathroom.0053", "require-blocked"),
    ("Home 10", "home_10.bathroom", "home_10.bathroom.toilet-001", "toilet", ((82, 39),), (82, 40), "prop.interiors_v3.bathroom.0054", "require-blocked"),
)

# sector, interaction id, exact logical shape cell to remove, retained cell.
INTERACTION_SHAPE_REMOVALS = (
    ("Home 6", "home_6.bedroom.bed-001", (36, 42), (38, 42)),
    ("Home 7", "home_7.bedroom.bed-001", (57, 42), (59, 42)),
    ("Home 8", "home_8.bedroom.bed-001", (64, 42), (66, 42)),
    ("Home 9", "home_9.bedroom.bed-001", (76, 42), (74, 42)),
    ("Home 10", "home_10.bedroom.bed-001", (84, 42), (82, 42)),
)

# sector, optional zone, semantic id, logical cells, linked art key, policy.
BLOCKER_ADDITIONS = (
    ("Home 2", None, "home_2.bed-blocker", ((6, 37), (7, 37)), "prop.interiors_v3.bedroom.0090", "require-blocked"),
    ("Home 3", None, "home_3.bed-blocker", ((14, 37), (15, 37)), "prop.interiors_v3.bedroom.0103", "require-blocked"),
    ("Home 4", None, "home_4.bed-blocker", ((19, 37), (20, 37)), "prop.interiors_v3.bedroom.0111", "require-blocked"),
    ("Home 6", "home_6.bedroom", "home_6.analysis-desk-blocker", ((36, 42),), "prop.interiors_v3.bedroom.0267", "require-blocked"),
    ("Home 7", "home_7.bedroom", "home_7.filing-blocker", ((57, 42),), "prop.office.filing_cabinet", "require-blocked"),
    ("Home 8", "home_8.bedroom", "home_8.wardrobe-blocker", ((64, 42),), "prop.interiors_v3.bedroom.0383", "require-blocked"),
    ("Home 9", "home_9.bedroom", "home_9.wardrobe-blocker", ((76, 42),), "prop.interiors_v3.bedroom.0385", "require-blocked"),
    ("Home 10", "home_10.bedroom", "home_10.filing-blocker", ((84, 42),), "prop.office.filing_cabinet", "require-blocked"),
)

SEMANTIC_MIGRATIONS = {
    "zone_shape_removals": ZONE_SHAPE_REMOVALS,
    "zone_additions": ZONE_ADDITIONS,
    "interaction_additions": INTERACTION_ADDITIONS,
    "interaction_shape_removals": INTERACTION_SHAPE_REMOVALS,
    "blocker_additions": BLOCKER_ADDITIONS,
}
