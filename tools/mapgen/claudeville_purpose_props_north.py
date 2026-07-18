"""Purposeful props for Claudeville's north public district."""

from __future__ import annotations

try:
    from tools.mapgen.claudeville_purpose_types import PurposeProp, _p
except ModuleNotFoundError:
    from claudeville_purpose_types import PurposeProp, _p  # type: ignore[no-redef]

NORTH_PURPOSE_PROPS: dict[str, tuple[PurposeProp, ...]] = {
    "Bank": (
        _p("prop.office.counter_walnut_left", 20, 23, "bank.teller", "teller counter"),
        *(
            _p(
                "prop.office.counter_walnut_middle",
                x,
                23,
                "bank.teller",
                "teller counter",
            )
            for x in range(21, 26)
        ),
        _p("prop.office.counter_walnut_right", 26, 23, "bank.teller", "teller counter"),
        *(
            _p(
                "prop.office.cash_register",
                x,
                21,
                "bank.teller",
                "teller terminal",
                False,
            )
            for x in (21, 23, 25)
        ),
        *(
            _p(key, x, 22, "bank.teller", "staff chair", False)
            for key, x in (
                ("prop.office.chair_blue", 21),
                ("prop.office.chair_orange", 23),
                ("prop.office.chair_blue", 25),
            )
        ),
        *(
            _p("prop.office.computer_desk", x, 15, "bank.operations", "operations desk")
            for x in (22, 26)
        ),
        *(
            _p("prop.office.manager_chair", x, 17, "bank.operations", "staff chair", False)
            for x in (22, 26)
        ),
        _p("prop.office.filing_cabinet", 24, 17, "bank.operations", "operations records"),
        _p("prop.office.notice_board", 27, 14, "bank.operations", "operations board", False),
        _p("prop.office.computer_desk", 12, 23, "bank.advisory", "advisory desk"),
        _p("prop.office.manager_chair", 12, 26, "bank.advisory", "advisor chair", False),
        _p("prop.office.chair_blue_side", 15, 24, "bank.advisory", "client chair", False),
        _p("prop.office.computer_desk", 12, 27, "bank.advisory", "advisory desk"),
        _p("prop.office.manager_chair", 12, 30, "bank.advisory", "advisor chair", False),
        _p("prop.office.chair_orange_side", 15, 28, "bank.advisory", "client chair", False),
        *(
            _p(key, x, 27, "bank.waiting", "waiting chair", False)
            for key, x in (
                ("prop.office.chair_blue_side", 21),
                ("prop.office.chair_orange_side", 23),
                ("prop.office.chair_blue_side", 25),
            )
        ),
        _p("prop.office.notice_board", 27, 28, "bank.waiting", "rate notice", False),
    ),
    "University": (
        _p(
            "prop.office.whiteboard",
            78,
            11,
            "university.lecture",
            "lecture board",
            False,
        ),
        *(
            _p(key, x, y, "university.lecture", "lecture table")
            for key, x, y in (
                ("prop.office.table_light", 77, 15),
                ("prop.office.table_light", 82, 15),
                ("prop.office.table_walnut_long", 77, 19),
                ("prop.office.table_walnut_long", 82, 19),
            )
        ),
        *(
            _p(key, x, y, "university.lecture", "student chair", False)
            for key, x, y in (
                ("prop.office.chair_blue", 77, 17),
                ("prop.office.chair_orange", 82, 17),
                ("prop.office.chair_blue_side", 80, 20),
            )
        ),
        *(
            _p(
                "prop.office.computer_desk",
                x,
                15,
                "university.study_lab",
                "computer station",
            )
            for x in (89, 94)
        ),
        _p(
            "prop.office.manager_chair",
            89,
            18,
            "university.study_lab",
            "study chair",
            False,
        ),
        _p(
            "prop.office.chair_blue",
            94,
            18,
            "university.study_lab",
            "study chair",
            False,
        ),
        _p(
            "prop.office.display_cabinet",
            97,
            19,
            "university.study_lab",
            "reference display",
        ),
        _p(
            "prop.office.counter_cream_left",
            86,
            24,
            "university.cafeteria",
            "service counter",
        ),
        *(
            _p(
                "prop.office.counter_cream_middle",
                x,
                24,
                "university.cafeteria",
                "service counter",
            )
            for x in range(87, 90)
        ),
        _p(
            "prop.office.counter_cream_right",
            90,
            24,
            "university.cafeteria",
            "service counter",
        ),
        _p(
            "prop.office.coffee_station",
            91,
            22,
            "university.cafeteria",
            "coffee station",
        ),
        _p(
            "prop.office.vending_machine",
            90,
            26,
            "university.cafeteria",
            "vending machine",
        ),
        _p("prop.office.table_walnut", 84, 29, "university.cafeteria", "dining table"),
        _p("prop.office.table_light", 90, 29, "university.cafeteria", "dining table"),
        _p(
            "prop.office.chair_blue_side",
            82,
            30,
            "university.cafeteria",
            "dining chair",
            False,
        ),
        _p(
            "prop.office.chair_orange_side",
            92,
            30,
            "university.cafeteria",
            "dining chair",
            False,
        ),
    ),
    "Agent Academy": (
        *(
            _p(
                "prop.office.training_station",
                x,
                14,
                "academy.training_lab",
                "training simulator",
            )
            for x in (112, 116)
        ),
        _p(
            "prop.office.dual_monitors",
            112,
            11,
            "academy.training_lab",
            "monitor station",
            False,
        ),
        _p(
            "prop.office.monitor_blue",
            116,
            11,
            "academy.training_lab",
            "monitor station",
            False,
        ),
        *(
            _p(
                "prop.office.computer_desk",
                x,
                19,
                "academy.training_lab",
                "computer station",
            )
            for x in (112, 116)
        ),
        _p(
            "prop.office.whiteboard", 124, 11, "academy.classroom", "class board", False
        ),
        *(
            _p(key, x, y, "academy.classroom", "class table")
            for key, x, y in (
                ("prop.office.table_walnut_long", 122, 16),
                ("prop.office.table_walnut_long", 126, 16),
                ("prop.office.table_light", 122, 21),
                ("prop.office.table_light", 126, 21),
            )
        ),
        _p(
            "prop.office.chair_blue",
            122,
            18,
            "academy.classroom",
            "student chair",
            False,
        ),
        _p(
            "prop.office.chair_orange",
            126,
            18,
            "academy.classroom",
            "student chair",
            False,
        ),
        _p(
            "prop.office.chair_blue",
            122,
            23,
            "academy.classroom",
            "student chair",
            False,
        ),
        _p(
            "prop.office.chair_orange",
            126,
            23,
            "academy.classroom",
            "student chair",
            False,
        ),
        _p(
            "prop.office.reception_corner",
            111,
            28,
            "academy.reception",
            "reception desk",
        ),
        _p(
            "prop.office.reception_desk", 114, 28, "academy.reception", "reception desk"
        ),
        _p(
            "prop.office.notice_board",
            111,
            26,
            "academy.reception",
            "academy notice",
            False,
        ),
        _p("prop.office.town_map", 116, 26, "academy.reception", "training map", False),
        _p("prop.office.sofa_dark", 122, 29, "academy.lounge", "lounge sofa", False),
        _p(
            "prop.office.armchair_mustard",
            118,
            29,
            "academy.lounge",
            "lounge chair",
            False,
        ),
        _p("prop.office.side_table", 120, 28, "academy.lounge", "lounge table"),
        _p("prop.office.water_cooler", 124, 27, "academy.lounge", "water cooler"),
        _p(
            "prop.office.wall_chart",
            118,
            22,
            "academy.training_lab",
            "training chart",
            False,
        ),
    ),
    "Market": (
        _p(
            "prop.office.counter_cream_left",
            150,
            28,
            "market.checkout",
            "checkout counter",
        ),
        _p(
            "prop.office.counter_cream_middle",
            151,
            28,
            "market.checkout",
            "checkout counter",
        ),
        _p(
            "prop.office.counter_cream_right",
            152,
            28,
            "market.checkout",
            "checkout counter",
        ),
        _p(
            "prop.office.cash_register",
            150,
            26,
            "market.checkout",
            "checkout terminal",
            False,
        ),
        _p("prop.cafe.food_display", 153, 25, "market.retail", "fresh food display"),
        _p("prop.cafe.food_display", 154, 25, "market.retail", "fresh food display"),
        _p("prop.cafe.food_display", 157, 25, "market.retail", "fresh food display"),
        _p("prop.cafe.food_display", 158, 25, "market.retail", "fresh food display"),
    ),
}
