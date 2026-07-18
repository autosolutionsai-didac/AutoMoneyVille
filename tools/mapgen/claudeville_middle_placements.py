"""Purposeful native-16 prop placements for Claudeville's middle district."""

TARGET_BOUNDS = {
    "Workshop": (8, 40, 29, 63),
    "Community Center": (45, 43, 65, 63),
    "Library": (112, 42, 131, 64),
}
TARGETS = frozenset(TARGET_BOUNDS)
STRUCTURE_TARGETS = frozenset({"Community Center", "Library"})
REVISION = 5

V3_TILE_SOURCES = ("room.floors", "room.walls", "room.arched_entryways")
FLOOR_PATTERNS = {
    "community-maple": ((("room.floors", 25, 1),),),
    "library-wood": ((("room.floors", 12, 1),),),
}
WALL_TILE_STYLE = {
    "horizontal": ("room.walls", 0, 12),
    "top_left": ("room.walls", 0, 11),
    "top_right": ("room.walls", 0, 14),
    "left": ("room.walls", 1, 16),
    "right": ("room.walls", 1, 16),
}
VISUAL_SHELLS = (
    ("Community Center", 46, 44, 64, 62, 51, 52, "community-maple", "bottom"),
    ("Library", 113, 43, 130, 63, 118, 119, "library-wood", "bottom"),
)
FLOOR_STAMPS = ()
FLOOR_PATCHES = ()
ROOM_FLOOR_RECTS = (
    ("Community Center", 59, 57, 63, 61, ("room.floors", 9, 13)),
)
WALL_RUNS = (
    ("Community Center", "horizontal", 56, 46, 64, (51, 52, 60, 61)),
    ("Community Center", "vertical", 58, 56, 62, (59, 60)),
    ("Library", "horizontal", 56, 113, 130, (120, 121)),
)

# Remove only the detached legacy facade strips above the new cutaway shells.
TILE_FILLS = (
    ("Foreground L1", 48, 41, 64, 43, 0),
    ("Foreground L1", 116, 40, 127, 42, 0),
)

# Native 2x2 thresholds replace the oversized exterior door sprites.
VISUAL_TILE_EDITS = (
    ("Wall", 18, 61, ("room.arched_entryways", 10, 4)),
    ("Wall", 19, 61, ("room.arched_entryways", 10, 5)),
    ("Wall", 18, 62, ("room.arched_entryways", 11, 4)),
    ("Wall", 19, 62, ("room.arched_entryways", 11, 5)),
    ("Wall", 51, 61, ("room.arched_entryways", 22, 4)),
    ("Wall", 52, 61, ("room.arched_entryways", 22, 5)),
    ("Wall", 51, 62, ("room.arched_entryways", 23, 4)),
    ("Wall", 52, 62, ("room.arched_entryways", 23, 5)),
    ("Wall", 118, 62, ("room.arched_entryways", 22, 4)),
    ("Wall", 119, 62, ("room.arched_entryways", 22, 5)),
    ("Wall", 118, 63, ("room.arched_entryways", 23, 4)),
    ("Wall", 119, 63, ("room.arched_entryways", 23, 5)),
)

# The existing exterior plaza is already a purposeful four-quadrant composition.
# Keep it outside TARGETS so a district re-author never clears its fountain or trees.
PRESERVED_PLAZA_BOUNDS = (68, 42, 90, 63)
PRESERVED_PLAZA_ASSETS = frozenset({
    "prop.plaza.fountain_blue",
    "prop.garden.bench_horizontal",
    "prop.garden.bench_vertical",
    "prop.street.lamp_01",
    "prop.street.lamp_03",
})

# source atlas/key, source rect (x, y, width, height), destination (x, y), layer
WORKSHOP_TILE_STAMPS = (
    # Deliberate machine and storage stamps; the visual x=18-19 lane stays clear.
    ("exteriors_worksite", (8, 12, 2, 7), (10, 42), "Interior Furniture L1"),
    ("exteriors_worksite", (3, 13, 5, 6), (13, 42), "Interior Furniture L1"),
    ("exteriors_worksite", (28, 7, 4, 7), (23, 42), "Interior Furniture L1"),
    ("exteriors_worksite", (14, 6, 3, 6), (12, 49), "Interior Furniture L1"),
    ("exteriors_worksite", (7, 7, 2, 2), (20, 54), "Interior Furniture L1"),
)

# sector, zone, semantic role, purpose cluster, stable asset key, visual x, visual y
PLACEMENTS = (
    # Workshop: job intake and estimating support the deliberate machine/storage stamps.
    # A continuous 32px circulation lane remains open at visual x=18-19.
    ("Workshop", "workshop.intake", "job-intake", "intake-line", "prop.office.counter_walnut_left", 13, 57),
    ("Workshop", "workshop.intake", "job-intake", "intake-line", "prop.office.counter_walnut_middle", 15, 57),
    ("Workshop", "workshop.intake", "job-intake", "intake-line", "prop.office.counter_walnut_right", 17, 57),
    ("Workshop", "workshop.intake", "design-desk", "estimating", "prop.office.computer_desk", 11, 61),
    ("Workshop", "workshop.intake", "job-records", "estimating", "prop.office.filing_cabinet", 14, 61),
    ("Workshop", "workshop.intake", "print-jobs", "estimating", "prop.office.printer_station", 16, 61),
    ("Workshop", "workshop.intake", "job-board", "intake-line", "prop.office.notice_board", 10, 55),
    ("Workshop", "workshop.intake", "paperwork", "intake-line", "prop.office.paper_stack", 15, 55),
    ("Workshop", "workshop.intake", "client-phone", "intake-line", "prop.office.phone", 17, 55),
    # Community Center: the stage remains interaction-linked, but its podium,
    # presentation display, and speakers sort in front of it instead of being
    # hidden underneath the large stage sprite. Two aligned seating banks leave
    # a continuous two-tile aisle between the entrance and presentation area.
    ("Community Center", "community.event_hall", "presentation-area", "stage", "prop.community.stage_small", 55, 51),
    ("Community Center", "community.event_hall", "stage-speaker", "stage", "prop.interiors_v3.music_sport.0043", 52, 52),
    ("Community Center", "community.event_hall", "stage-podium", "stage", "prop.interiors_v3.conference.0028", 54, 52),
    ("Community Center", "community.event_hall", "presentation-display", "stage", "prop.interiors_v3.conference.0030", 56, 52),
    ("Community Center", "community.event_hall", "stage-speaker", "stage", "prop.interiors_v3.music_sport.0043", 58, 52),
    ("Community Center", "community.event_hall", "event-table", "west-activity-table", "prop.interiors_v3.art.0023", 52, 53),
    ("Community Center", "community.event_hall", "event-table", "east-activity-table", "prop.interiors_v3.art.0024", 58, 53),
    ("Community Center", "community.event_hall", "audience-seat", "west-front-row", "prop.interiors_v3.conference.0037", 48, 53),
    ("Community Center", "community.event_hall", "audience-seat", "west-front-row", "prop.interiors_v3.conference.0037", 50, 53),
    ("Community Center", "community.event_hall", "audience-seat", "east-front-row", "prop.interiors_v3.conference.0037", 60, 53),
    ("Community Center", "community.event_hall", "audience-seat", "east-front-row", "prop.interiors_v3.conference.0037", 62, 53),
    ("Community Center", "community.event_hall", "audience-seat", "west-rear-row", "prop.interiors_v3.conference.0037", 48, 55),
    ("Community Center", "community.event_hall", "audience-seat", "west-rear-row", "prop.interiors_v3.conference.0037", 50, 55),
    ("Community Center", "community.event_hall", "audience-seat", "west-rear-row", "prop.interiors_v3.conference.0037", 52, 55),
    ("Community Center", "community.event_hall", "audience-seat", "east-rear-row", "prop.interiors_v3.conference.0037", 58, 55),
    ("Community Center", "community.event_hall", "audience-seat", "east-rear-row", "prop.interiors_v3.conference.0037", 60, 55),
    ("Community Center", "community.event_hall", "audience-seat", "east-rear-row", "prop.interiors_v3.conference.0037", 62, 55),
    # The lower west room combines a compact lounge with a staffed activity
    # table while keeping the entrance lane at visual x=51-52 unobstructed.
    ("Community Center", "community.lounge", "lounge-seating", "west-lounge", "prop.interiors_v3.living.0003", 49, 59),
    ("Community Center", "community.lounge", "lounge-seating", "west-lounge", "prop.interiors_v3.living.0005", 47, 61),
    ("Community Center", "community.lounge", "lounge-seating", "west-lounge", "prop.interiors_v3.living.0007", 55, 58),
    ("Community Center", "community.lounge", "lounge-table", "west-lounge", "prop.interiors_v3.living.0008", 50, 61),
    ("Community Center", "community.lounge", "planter", "west-lounge", "prop.interiors_v3.living.0016", 47, 58),
    ("Community Center", "community.lounge", "activity-table", "community-workshop", "prop.interiors_v3.art.0023", 55, 60),
    ("Community Center", "community.lounge", "activity-seat", "community-workshop", "prop.interiors_v3.classroom_library.0003", 53, 60),
    ("Community Center", "community.lounge", "activity-seat", "community-workshop", "prop.interiors_v3.classroom_library.0004", 57, 60),
    # The east room is a compact reception: two counter sections, one terminal,
    # and wall-mounted notice/map support rather than a wall-to-wall desk row.
    ("Community Center", "community.reception", "community-notice", "help-point", "prop.office.notice_board", 60, 58),
    ("Community Center", "community.reception", "town-map", "help-point", "prop.office.town_map", 62, 58),
    ("Community Center", "community.reception", "service-terminal", "help-point", "prop.office.monitor_blue", 61, 60),
    ("Community Center", "community.reception", "help-desk", "help-point", "prop.office.counter_walnut_left", 60, 61),
    ("Community Center", "community.reception", "help-desk", "help-point", "prop.office.counter_walnut_right", 62, 61),
    # Library: two continuous shelf banks have a two-tile cross aisle and a
    # two-tile central spine. The lower room is a compact checkout/study zone.
    ("Library", "library.stacks", "bookshelf", "west-north-bank", "prop.interiors_v3.classroom_library.0069", 115, 47),
    ("Library", "library.stacks", "bookshelf", "west-north-bank", "prop.interiors_v3.classroom_library.0071", 117, 47),
    ("Library", "library.stacks", "bookshelf", "west-north-bank", "prop.interiors_v3.classroom_library.0069", 119, 47),
    ("Library", "library.stacks", "bookshelf", "west-south-bank", "prop.interiors_v3.classroom_library.0055", 115, 53),
    ("Library", "library.stacks", "bookshelf", "west-south-bank", "prop.interiors_v3.classroom_library.0057", 117, 53),
    ("Library", "library.stacks", "bookshelf", "west-south-bank", "prop.interiors_v3.classroom_library.0055", 119, 53),
    ("Library", "library.stacks", "east-bookshelf", "east-north-bank", "prop.interiors_v3.classroom_library.0043", 123, 47),
    ("Library", "library.stacks", "east-bookshelf", "east-north-bank", "prop.interiors_v3.classroom_library.0045", 125, 47),
    ("Library", "library.stacks", "east-bookshelf", "east-north-bank", "prop.interiors_v3.classroom_library.0043", 127, 47),
    ("Library", "library.stacks", "east-bookshelf", "east-north-bank", "prop.interiors_v3.classroom_library.0045", 129, 47),
    ("Library", "library.stacks", "east-bookshelf", "east-south-bank", "prop.interiors_v3.classroom_library.0060", 123, 53),
    ("Library", "library.stacks", "east-bookshelf", "east-south-bank", "prop.interiors_v3.classroom_library.0062", 125, 53),
    ("Library", "library.stacks", "east-bookshelf", "east-south-bank", "prop.interiors_v3.classroom_library.0064", 127, 53),
    ("Library", "library.stacks", "east-bookshelf", "east-south-bank", "prop.interiors_v3.classroom_library.0062", 129, 53),
    ("Library", "library.circulation", "circulation-desk", "checkout", "prop.interiors_v3.classroom_library.0049", 115, 61),
    ("Library", "library.circulation", "circulation-desk", "checkout", "prop.interiors_v3.classroom_library.0052", 117, 61),
    ("Library", "library.circulation", "checkout-terminal", "checkout", "prop.office.monitor_blue", 117, 59),
    ("Library", "library.reading", "reading-table", "west-study", "prop.interiors_v3.classroom_library.0025", 124, 61),
    ("Library", "library.reading", "reading-table", "east-study", "prop.interiors_v3.classroom_library.0025", 128, 61),
    ("Library", "library.reading", "reading-chair", "west-study", "prop.interiors_v3.classroom_library.0003", 122, 61),
    ("Library", "library.reading", "reading-chair", "shared-study", "prop.interiors_v3.classroom_library.0004", 126, 61),
    ("Library", "library.reading", "reading-chair", "east-study", "prop.interiors_v3.classroom_library.0004", 129, 61),
    ("Library", "library.reading", "library-schedule", "reading-support", "prop.interiors_v3.classroom_library.0032", 123, 58),
    ("Library", "library.reading", "learning-globe", "reading-support", "prop.interiors_v3.classroom_library.0034", 129, 58),
    ("Library", "library.reading", "plant", "checkout", "prop.interiors_v3.living.0016", 114, 62),
    ("Library", "library.reading", "plant", "east-study", "prop.interiors_v3.living.0013", 129, 62),
)
