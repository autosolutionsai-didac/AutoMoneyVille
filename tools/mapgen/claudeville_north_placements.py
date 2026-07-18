"""Target-photo north-compound geometry and native-sprite placements."""

from __future__ import annotations

try:
    from tools.mapgen import claudeville_reference_home1 as home1
    from tools.mapgen import claudeville_reference_middle as middle
    from tools.mapgen import claudeville_reference_university as university
except ModuleNotFoundError:  # Direct mapgen execution.
    import claudeville_reference_home1 as home1
    import claudeville_reference_middle as middle
    import claudeville_reference_university as university

TARGET_BOUNDS = {
    "Home 1": (67, 12, 91, 36),
    "University": (98, 5, 123, 36),
    "Agent Academy": (123, 5, 133, 36),
    "Market": (141, 11, 158, 36),
    "Post Office": (158, 11, 176, 36),
}
TARGETS = frozenset(TARGET_BOUNDS)
REVISION = 15
INTERACTION_STANCE_UPDATES: tuple[tuple, ...] = ()

V3_TILE_SOURCES = ("room.floors", "room.walls", "room.arched_entryways")
FLOOR_PATTERNS = {
    "civic-gray": ((("room.floors", 9, 13),),),
    "home-wood": ((("room.floors", 12, 1),),),
}
WALL_TILE_STYLE = {
    "horizontal": ("room.walls", 22, 1),
    "top_left": ("room.walls", 22, 0),
    "top_right": ("room.walls", 22, 2),
    "left": ("room.walls", 22, 4),
    "right": ("room.walls", 22, 6),
}

# Inclusive shell coordinates used by the generic district author. The strict
# reference author paints the University as a real U rather than this envelope.
VISUAL_SHELLS = (
    ("Home 1", 67, 12, 90, 35, 78, 81, "home-wood", "bottom"),
    ("University", 98, 5, 122, 35, 113, 116, "civic-gray", "bottom"),
    ("Agent Academy", 123, 5, 132, 35, 126, 129, "civic-gray", "bottom"),
    ("Market", 141, 11, 157, 35, 148, 151, "civic-gray", "bottom"),
    ("Post Office", 158, 11, 175, 35, 163, 168, "civic-gray", "bottom"),
)
FLOOR_STAMPS: tuple[tuple, ...] = ()
FLOOR_PATCHES: tuple[tuple, ...] = ()
ROOM_FLOOR_RECTS = (
    ("Home 1", 86, 13, 90, 25, ("room.floors", 32, 13)),
    ("University", 100, 29, 112, 35, ("room.floors", 25, 1)),
    ("Agent Academy", 124, 28, 132, 35, ("room.floors", 25, 1)),
    ("Post Office", 159, 13, 175, 35, ("room.floors", 25, 1)),
)
WALL_RUNS = home1.PARTITIONS[:3]
TILE_FILLS: tuple[tuple, ...] = ()
SAFE_LEGACY_CLEAR_RECTS: dict[str, tuple] = {}
SAFE_TOWN_CLEAR_RECTS: tuple[tuple, ...] = ()
LEGACY_TILESET_CLEARS: tuple[tuple, ...] = ()
TILE_EDITS: tuple[tuple, ...] = ()
VISUAL_TILE_EDITS: tuple[tuple, ...] = ()


def _p(sector: str, zone: str, role: str, cluster: str, key: str,
       x: int, y: int) -> tuple:
    return sector, zone, role, cluster, key, x, y


ACADEMY_PLACEMENTS = (
    _p("Agent Academy", "academy.training_lab", "simulator-monitor", "simulator wall", "prop.interiors_v3.shooting_range.0011", 125, 10),
    _p("Agent Academy", "academy.training_lab", "simulator-monitor", "simulator wall", "prop.interiors_v3.shooting_range.0012", 129, 10),
    _p("Agent Academy", "academy.training_lab", "training-simulator", "simulator pair", "prop.office.training_station", 125, 13),
    _p("Agent Academy", "academy.training_lab", "training-simulator", "simulator pair", "prop.office.training_station", 129, 13),
    _p("Agent Academy", "academy.training_lab", "target-trainer", "practical circuit", "prop.interiors_v3.shooting_range.0015", 125, 16),
    _p("Agent Academy", "academy.training_lab", "fitness-trainer", "practical circuit", "prop.interiors_v3.gym.0176", 130, 16),
    _p("Agent Academy", "academy.training_lab", "training-mat", "practical circuit", "prop.interiors_v3.gym.0196", 127, 17),
    _p("Agent Academy", "academy.training_lab", "training-chart", "debrief wall", "prop.office.wall_chart", 131, 8),
    _p("Agent Academy", "academy.classroom", "class-board", "teaching wall", "prop.interiors_v3.classroom_library.0036", 125, 20),
    _p("Agent Academy", "academy.classroom", "instructor-desk", "teaching wall", "prop.interiors_v3.classroom_library.0025", 130, 20),
    _p("Agent Academy", "academy.classroom", "classroom-seating", "class row one", "prop.interiors_v3.classroom_library.0015", 125, 23),
    _p("Agent Academy", "academy.classroom", "classroom-seating", "class row one", "prop.interiors_v3.classroom_library.0016", 130, 23),
    _p("Agent Academy", "academy.classroom", "classroom-seating", "class row two", "prop.interiors_v3.classroom_library.0017", 125, 26),
    _p("Agent Academy", "academy.classroom", "classroom-seating", "class row two", "prop.interiors_v3.classroom_library.0018", 130, 26),
    _p("Agent Academy", "academy.reception", "notice-board", "information wall", "prop.office.notice_board", 125, 29),
    _p("Agent Academy", "academy.reception", "reception-desk", "front desk", "prop.office.counter_walnut_left", 125, 32),
    _p("Agent Academy", "academy.reception", "reception-desk", "front desk", "prop.office.counter_walnut_right", 129, 32),
    _p("Agent Academy", "academy.reception", "terminal", "front desk", "prop.office.monitor_blue", 126, 30),
    _p("Agent Academy", "academy.lounge", "vending", "refreshment wall", "prop.office.vending_machine", 131, 29),
    _p("Agent Academy", "academy.lounge", "lounge-seating", "conversation set", "prop.office.sofa_dark", 132, 33),
    _p("Agent Academy", "academy.lounge", "side-table", "conversation set", "prop.office.side_table", 128, 34),
)

MARKET_PLACEMENTS = (
    *(_p("Market", "market.retail", "stock-display", "north stock wall", key, x, 15)
      for x, key in ((143, "prop.interiors_v3.grocery.0058"), (146, "prop.interiors_v3.grocery.0060"), (149, "prop.interiors_v3.grocery.0062"), (152, "prop.interiors_v3.grocery.0099"), (155, "prop.interiors_v3.grocery.0101"))),
    *(_p("Market", "market.retail", "produce-crate", cluster, key, x, y)
      for cluster, x, y, key in (("west produce island", 146, 21, "prop.interiors_v3.grocery.0371"), ("west produce island", 149, 21, "prop.interiors_v3.grocery.0373"), ("east produce island", 152, 21, "prop.interiors_v3.grocery.0374"), ("east produce island", 155, 21, "prop.interiors_v3.grocery.0371"), ("west produce island", 146, 25, "prop.interiors_v3.grocery.0374"), ("east produce island", 154, 25, "prop.interiors_v3.grocery.0373"))),
    *(_p("Market", "market.retail", "stock-display", cluster, key, x, y)
      for cluster, y, entries in (
          ("north aisle", 18, ((146, "prop.interiors_v3.grocery.0058"),
                                (149, "prop.interiors_v3.grocery.0060"),
                                (152, "prop.interiors_v3.grocery.0062"),
                                (155, "prop.interiors_v3.grocery.0099"))),
          ("south aisle", 27, ((146, "prop.interiors_v3.grocery.0099"),
                                (149, "prop.interiors_v3.grocery.0101"),
                                (152, "prop.interiors_v3.grocery.0058"),
                                (155, "prop.interiors_v3.grocery.0062"))),
      ) for x, key in entries),
    _p("Market", "market.checkout", "checkout-counter", "west checkout", "prop.interiors_v3.grocery.0162", 145, 30),
    _p("Market", "market.checkout", "checkout-counter", "east checkout", "prop.interiors_v3.grocery.0166", 155, 30),
    _p("Market", "market.checkout", "shopping-cart", "customer tools", "prop.interiors_v3.grocery.0413", 144, 33),
    _p("Market", "market.checkout", "shopping-cart", "customer tools", "prop.interiors_v3.grocery.0414", 156, 33),
    _p("Market", "market.retail", "stock-display", "west stock return", "prop.interiors_v3.grocery.0058", 143, 21),
    _p("Market", "market.retail", "stock-display", "west stock return", "prop.interiors_v3.grocery.0062", 143, 25),
    _p("Market", "market.retail", "stock-display", "east stock return", "prop.interiors_v3.grocery.0099", 156, 19),
    _p("Market", "market.retail", "stock-display", "east stock return", "prop.interiors_v3.grocery.0101", 156, 25),
)

PLACEMENTS = (
    *home1.PLACEMENTS,
    *university.PLACEMENTS,
    *ACADEMY_PLACEMENTS,
    *MARKET_PLACEMENTS,
    *middle.POST_PLACEMENTS,
)


def validate() -> None:
    for sector, placements in (("Agent Academy", ACADEMY_PLACEMENTS),
                               ("Market", MARKET_PLACEMENTS)):
        left, top, right, bottom = TARGET_BOUNDS[sector]
        points = [(item[5], item[6]) for item in placements]
        if len(points) != len(set(points)):
            raise ValueError(f"duplicate {sector} target placement")
        if any(not (left < x < right and top < y < bottom) for x, y in points):
            raise ValueError(f"{sector} target placement escaped its room")
    if len(ACADEMY_PLACEMENTS) < 20 or len(MARKET_PLACEMENTS) < 18:
        raise ValueError("north target compound lost furnishing density")


validate()
