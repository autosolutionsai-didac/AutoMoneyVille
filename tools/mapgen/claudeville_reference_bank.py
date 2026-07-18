"""Compact native-16 banking program for the target-photo Bank cutaway."""

from __future__ import annotations

ROOM_BOUNDS = (27, 12, 51, 36)
ENTRANCE_SPINE = (38, 31, 42, 36)
BANK_COLLISION_BLOCKS = frozenset({
    (x, y) for y in (9, 10) for x in range(17, 21)
})


def _p(zone: str, role: str, cluster: str, key: str, x: int, y: int) -> tuple:
    return "Bank", zone, role, cluster, key, x, y


PLACEMENTS = (
    # A fitted archive wall and compact staff operations table replace the
    # former pasted office scene.  The six cabinets read as one secure run;
    # the paired seats around the table leave a continuous central aisle.
    *(
        _p("bank.archive", "archive-cabinets", "secure archive wall",
           "prop.office.display_cabinet" if x % 4 else "prop.office.filing_cabinet",
           x, 14)
        for x in range(29, 49, 2)
    ),
    _p("bank.archive", "archive-cabinets", "secure archive wall",
       "prop.office.filing_cabinet", 50, 17),
    _p("bank.archive", "archive-cabinets", "secure archive wall",
       "prop.office.filing_cabinet", 48, 19),
    _p("bank.archive", "archive-cabinets", "secure archive wall",
       "prop.office.display_cabinet", 48, 21),
    _p("bank.archive", "archive-cabinets", "west archive return",
       "prop.office.display_cabinet", 29, 17),
    _p("bank.archive", "archive-cabinets", "west archive return",
       "prop.office.filing_cabinet", 29, 20),
    _p("bank.archive", "archive-cabinets", "west archive return",
       "prop.office.display_cabinet", 29, 23),
    _p("bank.archive", "archive-cabinets", "west archive return",
       "prop.office.filing_cabinet", 29, 26),
    _p("bank.archive", "archive-cabinets", "west archive return",
       "prop.office.display_cabinet", 29, 29),
    _p("bank.archive", "archive-cabinets", "east archive return",
       "prop.office.display_cabinet", 48, 23),
    _p("bank.archive", "archive-cabinets", "east archive return",
       "prop.office.filing_cabinet", 48, 25),
    _p("bank.archive", "archive-cabinets", "east archive return",
       "prop.office.display_cabinet", 48, 27),
    _p("bank.archive", "archive-cabinets", "east archive return",
       "prop.office.filing_cabinet", 48, 29),
    _p("bank.operations", "plant", "operations green corner",
       "prop.interiors_v3.living.0017", 49, 24),
    *(
        _p("bank.operations", "operations-chair", "staff review table",
           "prop.office.chair_blue", x, y)
        for y, xs in ((17, (34, 36, 38, 40)), (23, (36, 38, 40)))
        for x in xs
    ),
    _p("bank.operations", "operations-desk", "operations station",
       "prop.office.computer_desk", 44, 18),
    _p("bank.operations", "operations-desk", "operations station",
       "prop.office.computer_desk", 46, 18),
    _p("bank.operations", "document-copier", "operations station",
       "prop.office.copier", 45, 21),
    _p("bank.operations", "rate-notice", "operations station",
       "prop.office.notice_board", 49, 14),

    # Counter pieces sit on consecutive 16px cells: one actual teller barrier.
    _p("bank.teller", "teller-counter", "continuous teller line",
       "prop.office.counter_walnut_left", 30, 26),
    *(
        _p("bank.teller", "teller-counter", "continuous teller line",
           "prop.office.counter_walnut_middle", x, 26)
        for x in range(31, 39)
    ),
    _p("bank.teller", "teller-counter", "continuous teller line",
       "prop.office.counter_walnut_right", 39, 26),
    _p("bank.teller", "checkout-terminal", "west teller station",
       "prop.office.cash_register", 31, 25),
    _p("bank.teller", "staff-chair", "west teller station",
       "prop.office.chair_blue", 31, 23),
    _p("bank.teller", "checkout-terminal", "centre teller station",
       "prop.office.cash_register", 34, 25),
    _p("bank.teller", "staff-chair", "centre teller station",
       "prop.office.chair_orange", 34, 23),
    _p("bank.teller", "checkout-terminal", "east teller station",
       "prop.office.cash_register", 37, 25),
    _p("bank.teller", "staff-chair", "east teller station",
       "prop.office.chair_blue", 37, 23),

    # Two advisory clusters use paired staff/client seating.
    _p("bank.advisory", "advisor-terminal", "west advisory desk",
       "prop.office.laptop", 31, 28),
    _p("bank.advisory", "advisory-desk", "west advisory desk",
       "prop.office.table_walnut_long", 32, 30),
    _p("bank.advisory", "advisor-chair", "west advisory desk",
       "prop.office.chair_blue_side", 29, 30),
    _p("bank.advisory", "client-chair", "west advisory desk",
       "prop.office.chair_orange_side", 34, 30),
    _p("bank.advisory", "advisor-terminal", "south advisory desk",
       "prop.office.monitor_blue", 31, 31),
    _p("bank.advisory", "advisory-desk", "south advisory desk",
       "prop.office.table_light", 31, 33),
    _p("bank.advisory", "advisor-chair", "south advisory desk",
       "prop.office.chair_blue_side", 29, 33),
    # A compact waiting lounge leaves the central entrance spine open.
    _p("bank.waiting", "waiting-seating", "waiting lounge",
       "prop.office.sofa_dark", 46, 28),
    _p("bank.waiting", "waiting-seating", "waiting lounge",
       "prop.office.armchair_ice", 43, 30),
    _p("bank.waiting", "waiting-seating", "waiting lounge",
       "prop.office.armchair_mustard", 49, 30),
    _p("bank.waiting", "side-table", "waiting lounge",
       "prop.office.side_table", 46, 31),
    _p("bank.waiting", "water-cooler", "waiting support",
       "prop.office.water_cooler", 49, 33),
    _p("bank.waiting", "rate-notice", "waiting support",
       "prop.office.town_map", 46, 26),
)


def validate() -> None:
    occupied: set[tuple[int, int]] = set()
    left, top, right, bottom = ROOM_BOUNDS
    for placement in PLACEMENTS:
        sector, _zone, _role, _cluster, key, x, y = placement
        if sector != "Bank" or not (left < x < right and top < y < bottom):
            raise ValueError(f"Bank placement outside target room: {placement}")
        if key.startswith("prop.design.") or (x, y) in occupied:
            raise ValueError(f"invalid Bank placement: {placement}")
        occupied.add((x, y))
    roles = {item[2] for item in PLACEMENTS}
    required = {"advisory-desk", "archive-cabinets", "operations-desk",
                "teller-counter", "waiting-seating"}
    if not required <= roles or not 62 <= len(PLACEMENTS) <= 70:
        raise ValueError("Bank lost its complete banking program")
    teller_xs = [item[5] for item in PLACEMENTS if item[2] == "teller-counter"]
    if teller_xs != list(range(30, 40)):
        raise ValueError("Bank teller line must use consecutive native cells")
    if any(ENTRANCE_SPINE[0] <= x < ENTRANCE_SPINE[2]
           and ENTRANCE_SPINE[1] <= y < ENTRANCE_SPINE[3] for x, y in occupied):
        raise ValueError("Bank entrance spine is obstructed")


validate()
