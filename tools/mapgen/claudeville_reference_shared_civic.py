"""Dense native-sprite Town Hall program within the south rowhouse band."""

ROOM_BOUNDS = (99, 80, 114, 96)
ENTRANCE_SPINE = (104, 92, 110, 96)

PLACEMENTS = (
    # Records and public information consume most of the north wall.
    ("Town Hall", "hall.public_service", "records", "town records wall",
     "prop.office.filing_cabinet", 101, 82),
    ("Town Hall", "hall.public_service", "records", "town records wall",
     "prop.office.display_cabinet", 106, 82),
    ("Town Hall", "hall.public_service", "records", "town records wall",
     "prop.office.filing_cabinet", 107, 82),
    ("Town Hall", "hall.public_service", "records", "town records wall",
     "prop.office.display_cabinet", 110, 82),
    ("Town Hall", "hall.public_service", "planning-board", "town records wall",
     "prop.office.whiteboard", 112, 82),
    # One joined council table is the room's dominant anchor.
    ("Town Hall", "hall.council", "council-table", "council table",
     "prop.interiors_v3.conference.0001", 101, 88),
    ("Town Hall", "hall.council", "council-table", "council table",
     "prop.interiors_v3.conference.0002", 103, 88),
    ("Town Hall", "hall.council", "council-table", "council table",
     "prop.interiors_v3.conference.0003", 104, 88),
    ("Town Hall", "hall.council", "council-table", "council table",
     "prop.interiors_v3.conference.0004", 105, 88),
    ("Town Hall", "hall.council", "council-table", "council table",
     "prop.interiors_v3.conference.0005", 106, 88),
    ("Town Hall", "hall.council", "council-table", "council table",
     "prop.interiors_v3.conference.0006", 107, 88),
    ("Town Hall", "hall.council", "council-chair", "council table",
     "prop.office.chair_blue", 101, 85),
    ("Town Hall", "hall.council", "council-chair", "council table",
     "prop.office.chair_orange", 104, 85),
    ("Town Hall", "hall.council", "council-chair", "council table",
     "prop.office.chair_blue", 107, 85),
    ("Town Hall", "hall.council", "council-chair", "council table",
     "prop.office.chair_orange", 101, 91),
    ("Town Hall", "hall.council", "council-chair", "council table",
     "prop.office.chair_blue", 104, 91),
    ("Town Hall", "hall.council", "council-chair", "council table",
     "prop.office.chair_orange", 110, 91),
    # Public service and administration use the narrow east bay.
    ("Town Hall", "hall.public_service", "service-terminal", "service counter",
     "prop.office.monitor_blue", 110, 85),
    ("Town Hall", "hall.public_service", "service-terminal", "service counter",
     "prop.office.cash_register", 112, 85),
    ("Town Hall", "hall.public_service", "counter-wing", "service counter",
     "prop.office.counter_cream_left", 110, 87),
    ("Town Hall", "hall.public_service", "counter-wing", "service counter",
     "prop.office.counter_cream_right", 112, 87),
    ("Town Hall", "hall.administration", "admin-desk", "administration desk",
     "prop.office.computer_desk", 111, 90),
    ("Town Hall", "hall.administration", "admin-chair", "administration desk",
     "prop.office.manager_chair", 112, 92),
    ("Town Hall", "hall.administration", "document-printer", "administration desk",
     "prop.office.printer", 112, 94),
    # Waiting remains west of the six-tile entrance pocket.
    ("Town Hall", "hall.public_service", "waiting-seat", "public waiting",
     "prop.office.armchair_ice", 101, 93),
    ("Town Hall", "hall.public_service", "side-table", "public waiting",
     "prop.office.side_table", 100, 90),
)


def validate() -> None:
    occupied: set[tuple[int, int]] = set()
    left, top, right, bottom = ROOM_BOUNDS
    for item in PLACEMENTS:
        sector, _zone, _role, _cluster, key, x, y = item
        if sector != "Town Hall" or not (left < x < right and top < y < bottom):
            raise ValueError(f"Town Hall placement left target room: {item}")
        if key.startswith("prop.design.") or (x, y) in occupied:
            raise ValueError(f"invalid Town Hall placement: {item}")
        occupied.add((x, y))
    if any(ENTRANCE_SPINE[0] <= x < ENTRANCE_SPINE[2] and
           ENTRANCE_SPINE[1] <= y < ENTRANCE_SPINE[3] for x, y in occupied):
        raise ValueError("Town Hall entrance spine is obstructed")
    if not 24 <= len(PLACEMENTS) <= 32:
        raise ValueError("Town Hall target coverage changed")


validate()
