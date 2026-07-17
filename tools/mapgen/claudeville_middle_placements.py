"""Purposeful native-16 prop placements for Claudeville's middle district."""

TARGET_BOUNDS = {
    "Workshop": (8, 40, 29, 63),
    "Community Center": (45, 43, 65, 63),
    "Library": (112, 42, 131, 64),
}
TARGETS = frozenset(TARGET_BOUNDS)
REVISION = 2

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
    ("Workshop", "workshop.circulation", "entrance", "threshold", "prop.facade.door_open", 18, 63),

    # Community Center: a usable stage, two activity tables, lounge, and help point.
    # Chairs stay above/below tables so stance cell (25, 26) remains open.
    ("Community Center", "community.event_hall", "presentation-area", "stage", "prop.community.stage_small", 55, 49),
    ("Community Center", "community.event_hall", "stage-speaker", "stage", "prop.interiors_v3.music_sport.0043", 50, 49),
    ("Community Center", "community.event_hall", "stage-speaker", "stage", "prop.interiors_v3.music_sport.0043", 60, 49),
    ("Community Center", "community.event_hall", "stage-microphone", "stage", "prop.interiors_v3.music_sport.0062", 55, 50),
    ("Community Center", "community.event_hall", "stage-keyboard", "stage", "prop.interiors_v3.music_sport.0066", 52, 49),
    ("Community Center", "community.event_hall", "event-table", "west-activity-table", "prop.interiors_v3.art.0023", 52, 53),
    ("Community Center", "community.event_hall", "event-table", "east-activity-table", "prop.interiors_v3.art.0024", 58, 53),
    ("Community Center", "community.event_hall", "event-chair", "west-activity-table", "prop.interiors_v3.classroom_library.0002", 52, 51),
    ("Community Center", "community.event_hall", "event-chair", "east-activity-table", "prop.interiors_v3.classroom_library.0002", 58, 51),
    ("Community Center", "community.event_hall", "event-chair", "west-activity-table", "prop.interiors_v3.classroom_library.0001", 52, 55),
    ("Community Center", "community.event_hall", "event-chair", "east-activity-table", "prop.interiors_v3.classroom_library.0001", 58, 55),
    ("Community Center", "community.lounge", "lounge-seating", "west-lounge", "prop.interiors_v3.living.0003", 49, 59),
    ("Community Center", "community.lounge", "lounge-seating", "east-lounge", "prop.interiors_v3.living.0003", 53, 59),
    ("Community Center", "community.lounge", "lounge-seating", "east-lounge", "prop.interiors_v3.living.0005", 55, 59),
    ("Community Center", "community.lounge", "lounge-table", "west-lounge", "prop.interiors_v3.living.0065", 51, 59),
    ("Community Center", "community.lounge", "planter", "west-lounge", "prop.interiors_v3.living.0016", 47, 59),
    ("Community Center", "community.reception", "help-desk", "help-point", "prop.office.counter_walnut_left", 59, 61),
    ("Community Center", "community.reception", "help-desk", "help-point", "prop.office.counter_walnut_middle", 61, 61),
    ("Community Center", "community.reception", "help-desk", "help-point", "prop.office.counter_walnut_right", 63, 61),
    ("Community Center", "community.reception", "service-terminal", "help-point", "prop.office.cash_register", 61, 59),
    ("Community Center", "community.reception", "community-notice", "help-point", "prop.office.notice_board", 59, 57),
    ("Community Center", "community.reception", "town-map", "help-point", "prop.office.town_map", 62, 57),
    ("Community Center", "community_center.circulation", "entrance", "threshold", "prop.facade.door_open", 52, 63),

    # Library: warm shelf rows at y=45 and y=49 frame open logical aisles.
    # Logical aisle row y=23 and cross-aisle y=26 remain clear; x=122-123 is a reading stance.
    ("Library", "library.stacks", "bookshelf", "west-north-stacks", "prop.interiors_v3.classroom_library.0069", 116, 45),
    ("Library", "library.stacks", "bookshelf", "west-north-stacks", "prop.interiors_v3.classroom_library.0071", 119, 45),
    ("Library", "library.stacks", "bookshelf", "west-lower-stacks", "prop.interiors_v3.classroom_library.0055", 114, 49),
    ("Library", "library.stacks", "bookshelf", "west-lower-stacks", "prop.interiors_v3.classroom_library.0057", 118, 49),
    ("Library", "library.stacks", "east-bookshelf", "east-north-stacks", "prop.interiors_v3.classroom_library.0043", 122, 45),
    ("Library", "library.stacks", "east-bookshelf", "east-north-stacks", "prop.interiors_v3.classroom_library.0045", 125, 45),
    ("Library", "library.stacks", "east-bookshelf", "east-lower-stacks", "prop.interiors_v3.classroom_library.0060", 122, 49),
    ("Library", "library.stacks", "east-bookshelf", "east-lower-stacks", "prop.interiors_v3.classroom_library.0062", 125, 49),
    ("Library", "library.stacks", "east-bookshelf", "east-lower-stacks", "prop.interiors_v3.classroom_library.0064", 128, 49),
    ("Library", "library.reading", "reading-table", "west-study", "prop.interiors_v3.classroom_library.0025", 120, 59),
    ("Library", "library.reading", "reading-table", "east-study", "prop.interiors_v3.classroom_library.0025", 125, 59),
    ("Library", "library.reading", "reading-chair", "west-study", "prop.interiors_v3.classroom_library.0002", 120, 57),
    ("Library", "library.reading", "reading-chair", "east-study", "prop.interiors_v3.classroom_library.0002", 125, 57),
    ("Library", "library.reading", "reading-chair", "west-study", "prop.interiors_v3.classroom_library.0001", 120, 60),
    ("Library", "library.reading", "reading-chair", "east-study", "prop.interiors_v3.classroom_library.0001", 125, 60),
    ("Library", "library.circulation", "circulation-desk", "checkout", "prop.interiors_v3.classroom_library.0049", 115, 59),
    ("Library", "library.circulation", "circulation-desk", "checkout", "prop.interiors_v3.classroom_library.0052", 115, 61),
    ("Library", "library.circulation", "checkout-terminal", "checkout", "prop.interiors_v3.classroom_library.0054", 117, 58),
    ("Library", "library.reading", "library-schedule", "reading-support", "prop.interiors_v3.classroom_library.0032", 118, 55),
    ("Library", "library.reading", "learning-globe", "reading-support", "prop.interiors_v3.classroom_library.0034", 129, 55),
    ("Library", "library.reading", "periodical-shelf", "west-periodicals", "prop.interiors_v3.classroom_library.0043", 114, 55),
    ("Library", "library.reading", "periodical-shelf", "east-periodicals", "prop.interiors_v3.classroom_library.0045", 129, 59),
    ("Library", "library.reading", "lounge-seating", "central-reading-lounge", "prop.interiors_v3.living.0003", 123, 55),
    ("Library", "library.reading", "lounge-seating", "central-reading-lounge", "prop.interiors_v3.living.0004", 120, 57),
    ("Library", "library.reading", "lounge-seating", "central-reading-lounge", "prop.interiors_v3.living.0004", 126, 57),
    ("Library", "library.reading", "lounge-table", "central-reading-lounge", "prop.interiors_v3.living.0051", 123, 57),
    ("Library", "library.reading", "plant", "west-periodicals", "prop.interiors_v3.living.0016", 114, 61),
    ("Library", "library.reading", "plant", "east-periodicals", "prop.interiors_v3.living.0013", 129, 61),
    ("Library", "library.circulation", "entrance", "threshold", "prop.facade.door_open", 119, 64),
)
