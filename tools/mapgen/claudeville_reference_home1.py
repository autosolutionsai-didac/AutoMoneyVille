"""Dense native-sprite Home 1 and rowhouse partition topology."""

from __future__ import annotations

ROOM_BOUNDS = (67, 12, 91, 36)
ENTRANCE_SPINE = (78, 32, 82, 36)

# sector, orientation, fixed coordinate, run start/end, door-gap coordinates
PARTITIONS = (
    ("Home 1", "vertical", 77, 12, 25, (20, 21)),
    ("Home 1", "vertical", 85, 12, 25, (20, 21)),
    ("Home 1", "horizontal", 25, 77, 90, (80, 81, 88, 89)),
    # Compact bathroom returns inside the nine individual south homes.
    ("Home 2", "horizontal", 86, 27, 39, (34, 35)),
    ("Home 3", "horizontal", 86, 40, 51, (44, 45)),
    ("Home 4", "horizontal", 86, 67, 75, (70, 71)),
    ("Home 5", "horizontal", 86, 76, 83, (78, 79)),
    ("Home 6", "horizontal", 86, 84, 91, (86, 87)),
    ("Home 7", "horizontal", 86, 118, 128, (122, 123)),
    ("Home 8", "horizontal", 86, 129, 137, (132, 133)),
    ("Home 9", "horizontal", 86, 143, 150, (144, 145, 146, 147)),
    ("Home 10", "horizontal", 86, 151, 158, (154, 155)),
)

SOUTH_HOME_SECTORS = frozenset({f"Home {number}" for number in range(2, 11)})

# sector, zone, role, purpose cluster, stable asset key, native-16 foot x/y
PLACEMENTS = (
    # A fitted L-shaped kitchen uses almost the complete northwest wall.
    ("Home 1", "home_1.kitchen", "refrigerator", "northwest kitchen run",
     "prop.interiors_v3.kitchen.0159", 69, 16),
    ("Home 1", "home_1.kitchen", "base-cabinet", "northwest kitchen run",
     "prop.interiors_v3.kitchen.0121", 71, 16),
    ("Home 1", "home_1.kitchen", "sink-cabinet", "northwest kitchen run",
     "prop.interiors_v3.kitchen.0122", 73, 16),
    ("Home 1", "home_1.kitchen", "base-cabinet", "northwest kitchen run",
     "prop.interiors_v3.kitchen.0123", 75, 16),
    ("Home 1", "home_1.kitchen", "wall-shelf", "northwest kitchen run",
     "prop.interiors_v3.kitchen.0127", 71, 14),
    ("Home 1", "home_1.kitchen", "sink", "northwest kitchen run",
     "prop.interiors_v3.kitchen.0142", 73, 14),
    ("Home 1", "home_1.kitchen", "cooking-area", "west appliance run",
     "prop.interiors_v3.kitchen.0148", 69, 20),
    ("Home 1", "home_1.kitchen", "cooking-appliance", "west appliance run",
     "prop.interiors_v3.kitchen.0152", 69, 22),
    ("Home 1", "home_1.kitchen", "small-appliance", "west appliance run",
     "prop.interiors_v3.kitchen.0178", 69, 24),

    # One joined family table sits a one-tile gap from the kitchen work zone.
    ("Home 1", "home_1.living_room", "common-room-table", "family dining",
     "prop.interiors_v3.kitchen.0301", 71, 26),
    ("Home 1", "home_1.living_room", "common-room-table", "family dining",
     "prop.interiors_v3.kitchen.0302", 72, 26),
    ("Home 1", "home_1.living_room", "common-room-table", "family dining",
     "prop.interiors_v3.kitchen.0302", 73, 26),
    ("Home 1", "home_1.living_room", "common-room-table", "family dining",
     "prop.interiors_v3.kitchen.0303", 74, 26),
    ("Home 1", "home_1.living_room", "dining-chair", "family dining",
     "prop.interiors_v3.kitchen.0369", 70, 25),
    ("Home 1", "home_1.living_room", "dining-chair", "family dining",
     "prop.interiors_v3.kitchen.0372", 75, 25),
    ("Home 1", "home_1.living_room", "dining-chair", "family dining",
     "prop.interiors_v3.kitchen.0273", 71, 28),
    ("Home 1", "home_1.living_room", "dining-chair", "family dining",
     "prop.interiors_v3.kitchen.0274", 74, 28),

    # The bedroom reads as one compact, fully supported sleeping alcove.
    ("Home 1", "home_1.bedroom", "closet", "north bedroom storage",
     "prop.interiors_v3.living.0037", 79, 16),
    ("Home 1", "home_1.bedroom", "closet", "north bedroom storage",
     "prop.interiors_v3.bedroom.0384", 82, 16),
    ("Home 1", "home_1.bedroom", "wall-light", "sleep wall",
     "prop.interiors_v3.bedroom.0259", 81, 14),
    ("Home 1", "home_1.bedroom", "bed", "blue sleep alcove",
     "prop.interiors_v3.bedroom.0087", 80, 22),
    ("Home 1", "home_1.bedroom", "bedside-table", "blue sleep alcove",
     "prop.interiors_v3.living.0063", 85, 20),
    ("Home 1", "home_1.bedroom", "dresser", "bedroom storage",
     "prop.interiors_v3.living.0051", 84, 23),
    ("Home 1", "home_1.bedroom", "folded-linen", "bedroom storage",
     "prop.interiors_v3.bedroom.0069", 82, 23),

    # Every bathroom fixture hugs the narrow east wet-room perimeter.
    ("Home 1", "home_1.bathroom", "mirror", "east washstand",
     "prop.interiors_v3.bathroom.0066", 88, 14),
    ("Home 1", "home_1.bathroom", "washstand", "east washstand",
     "prop.interiors_v3.bathroom.0002", 90, 16),
    ("Home 1", "home_1.bathroom", "towel-shelf", "east washstand",
     "prop.interiors_v3.bathroom.0076", 86, 16),
    ("Home 1", "home_1.bathroom", "toilet-fixture", "east washroom",
     "prop.interiors_v3.bathroom.0021", 87, 20),
    ("Home 1", "home_1.bathroom", "shower", "east washroom",
     "prop.interiors_v3.bathroom.0151", 90, 20),
    ("Home 1", "home_1.bathroom", "linen-cabinet", "east washroom",
     "prop.interiors_v3.bathroom.0121", 89, 24),

    # The south lounge is dense but preserves a four-tile front-door approach.
    ("Home 1", "home_1.living_room", "runner-panel", "blue living spine",
     "prop.interiors_v3.bedroom.0241", 78, 27),
    ("Home 1", "home_1.living_room", "runner-panel", "blue living spine",
     "prop.interiors_v3.bedroom.0242", 79, 27),
    ("Home 1", "home_1.living_room", "runner-panel", "blue living spine",
     "prop.interiors_v3.bedroom.0243", 80, 27),
    ("Home 1", "home_1.living_room", "lounge-seating", "blue living spine",
     "prop.interiors_v3.living.0009", 78, 30),
    ("Home 1", "home_1.living_room", "lounge-seating", "blue living spine",
     "prop.interiors_v3.living.0010", 79, 30),
    ("Home 1", "home_1.living_room", "lounge-seating", "blue living spine",
     "prop.interiors_v3.living.0011", 81, 30),
    ("Home 1", "home_1.living_room", "media-console", "east media wall",
     "prop.interiors_v3.living.0019", 90, 28),
    ("Home 1", "home_1.living_room", "low-bookcase", "east media wall",
     "prop.interiors_v3.living.0057", 90, 31),
    ("Home 1", "home_1.living_room", "lounge-seating", "conversation group",
     "prop.interiors_v3.living.0002", 84, 30),
    ("Home 1", "home_1.living_room", "lounge-seating", "conversation group",
     "prop.interiors_v3.living.0003", 86, 30),
    ("Home 1", "home_1.living_room", "side-table", "conversation group",
     "prop.office.side_table", 87, 33),
    ("Home 1", "home_1.living_room", "low-bookcase", "south storage wall",
     "prop.interiors_v3.living.0051", 69, 32),
    ("Home 1", "home_1.living_room", "low-bookcase", "south storage wall",
     "prop.interiors_v3.living.0053", 72, 32),
    ("Home 1", "home_1.living_room", "floor-lamp", "south storage wall",
     "prop.interiors_v3.living.0085", 75, 32),
    ("Home 1", "home_1.living_room", "plant", "southwest green corner",
     "prop.interiors_v3.living.0017", 69, 34),
    ("Home 1", "home_1.living_room", "plant", "southeast green corner",
     "prop.interiors_v3.living.0015", 89, 33),
)


def validate() -> None:
    for sector, orientation, _fixed, start, end, gaps in PARTITIONS:
        if start >= end or any(not start <= gap < end for gap in gaps):
            raise ValueError(f"invalid {orientation} partition in {sector}")
    if {item[0] for item in PARTITIONS if item[0] in SOUTH_HOME_SECTORS} != SOUTH_HOME_SECTORS:
        raise ValueError("every rowhouse needs a purposeful internal partition")
    occupied: set[tuple[int, int]] = set()
    left, top, right, bottom = ROOM_BOUNDS
    for item in PLACEMENTS:
        sector, _zone, _role, _cluster, key, x, y = item
        if sector != "Home 1" or not (left < x < right and top < y < bottom):
            raise ValueError(f"Home 1 placement left target room: {item}")
        if key.startswith("prop.design.") or (x, y) in occupied:
            raise ValueError(f"invalid Home 1 placement: {item}")
        occupied.add((x, y))
    if not 44 <= len(PLACEMENTS) <= 56:
        raise ValueError("Home 1 must retain dense household coverage")
    if any(ENTRANCE_SPINE[0] <= x < ENTRANCE_SPINE[2] and
           ENTRANCE_SPINE[1] <= y < ENTRANCE_SPINE[3] for x, y in occupied):
        raise ValueError("Home 1 front approach is obstructed")


validate()
