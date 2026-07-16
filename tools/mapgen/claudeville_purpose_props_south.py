"""Purposeful props for Claudeville's middle and south public districts."""

from __future__ import annotations

try:
    from tools.mapgen.claudeville_purpose_types import PurposeProp, _p
except ModuleNotFoundError:
    from claudeville_purpose_types import PurposeProp, _p  # type: ignore[no-redef]

SOUTH_PURPOSE_PROPS: dict[str, tuple[PurposeProp, ...]] = {
    "Workshop": (
        _p(
            "prop.office.counter_walnut_left",
            13,
            57,
            "workshop.intake",
            "intake counter",
        ),
        _p(
            "prop.office.counter_walnut_middle",
            15,
            57,
            "workshop.intake",
            "intake counter",
        ),
        _p(
            "prop.office.counter_walnut_right",
            17,
            57,
            "workshop.intake",
            "intake counter",
        ),
        _p("prop.office.computer_desk", 11, 61, "workshop.intake", "design desk"),
        _p("prop.office.filing_cabinet", 14, 61, "workshop.intake", "job records"),
        _p("prop.office.notice_board", 10, 55, "workshop.intake", "job board", False),
    ),
    "Community Center": (
        _p(
            "prop.community.stage_small",
            55,
            49,
            "community.event_hall",
            "community stage",
        ),
        *(
            _p(
                "prop.community.loudspeaker",
                x,
                48,
                "community.event_hall",
                "public address",
                False,
            )
            for x in (50, 60)
        ),
        *(
            _p(
                "prop.office.table_walnut_long",
                x,
                53,
                "community.event_hall",
                "event table",
            )
            for x in (52, 58)
        ),
        *(
            _p(key, x, y, "community.event_hall", "event chair", False)
            for key, x, y in (
                ("prop.office.chair_blue", 52, 50),
                ("prop.office.chair_orange_side", 50, 54),
                ("prop.office.chair_blue_side", 54, 54),
                ("prop.office.chair_orange", 58, 50),
                ("prop.office.chair_blue_side", 56, 54),
                ("prop.office.chair_orange_side", 60, 54),
            )
        ),
        _p(
            "prop.office.sofa_corner",
            49,
            59,
            "community.lounge",
            "community sofa",
            False,
        ),
        _p(
            "prop.office.sofa_dark", 52, 59, "community.lounge", "community sofa", False
        ),
        _p(
            "prop.office.armchair_mustard",
            54,
            59,
            "community.lounge",
            "lounge chair",
            False,
        ),
        _p("prop.office.side_table", 52, 57, "community.lounge", "lounge table"),
        _p("prop.office.reception_corner", 59, 60, "community.reception", "help desk"),
        _p("prop.office.reception_desk", 62, 60, "community.reception", "help desk"),
        _p(
            "prop.office.notice_board",
            59,
            57,
            "community.reception",
            "community notice",
            False,
        ),
        _p(
            "prop.office.town_map",
            62,
            57,
            "community.reception",
            "community map",
            False,
        ),
    ),
    "Claudeville Cafe": (
        _p(
            "prop.office.cash_register",
            104,
            48,
            "cafe.service",
            "payment terminal",
            False,
        ),
        _p("prop.office.table_light", 97, 54, "cafe.dining", "dining table"),
        _p("prop.office.table_walnut", 103, 54, "cafe.dining", "dining table"),
        *(
            _p(key, x, 55, "cafe.dining", "dining chair", False)
            for key, x in (
                ("prop.office.chair_blue_side", 96),
                ("prop.office.chair_orange_side", 99),
                ("prop.office.chair_blue_side", 102),
                ("prop.office.chair_orange_side", 104),
            )
        ),
        _p("prop.office.table_light", 95, 59, "cafe.terrace", "terrace table"),
        _p(
            "prop.office.chair_blue_side",
            93,
            60,
            "cafe.terrace",
            "terrace chair",
            False,
        ),
        _p(
            "prop.office.chair_orange_side",
            97,
            60,
            "cafe.terrace",
            "terrace chair",
            False,
        ),
        _p("prop.office.table_walnut", 105, 61, "cafe.terrace", "terrace table"),
        _p(
            "prop.office.chair_blue_side",
            103,
            62,
            "cafe.terrace",
            "terrace chair",
            False,
        ),
        _p(
            "prop.office.chair_orange_side",
            107,
            62,
            "cafe.terrace",
            "terrace chair",
            False,
        ),
    ),
    "Library": (
        _p(
            "prop.office.reception_corner",
            115,
            59,
            "library.circulation",
            "circulation desk",
        ),
        _p(
            "prop.office.reception_desk",
            115,
            61,
            "library.circulation",
            "circulation desk",
        ),
        _p(
            "prop.office.cash_register",
            117,
            59,
            "library.circulation",
            "checkout scanner",
            False,
        ),
        _p(
            "prop.office.notice_board",
            118,
            57,
            "library.circulation",
            "library notice",
            False,
        ),
        *(
            _p(
                "prop.office.table_walnut_long",
                x,
                59,
                "library.reading",
                "reading table",
            )
            for x in (120, 125)
        ),
        *(
            _p(key, x, y, "library.reading", "reading chair", False)
            for key, x, y in (
                ("prop.office.chair_blue", 120, 56),
                ("prop.office.chair_orange_side", 118, 60),
                ("prop.office.chair_orange", 125, 56),
                ("prop.office.chair_blue_side", 127, 60),
            )
        ),
    ),
    "Post Office": (
        _p(
            "prop.office.counter_cream_left", 151, 52, "post.service", "service counter"
        ),
        *(
            _p(
                "prop.office.counter_cream_middle",
                x,
                52,
                "post.service",
                "service counter",
            )
            for x in range(152, 156)
        ),
        _p(
            "prop.office.counter_cream_right",
            156,
            52,
            "post.service",
            "service counter",
        ),
        *(
            _p(
                "prop.office.cash_register",
                x,
                50,
                "post.service",
                "postal terminal",
                False,
            )
            for x in (153, 156)
        ),
        *(
            _p(key, x, 51, "post.service", "postal clerk chair", False)
            for key, x in (
                ("prop.office.chair_blue", 153),
                ("prop.office.chair_orange", 156),
            )
        ),
        *(
            _p(key, x, 57, "post.waiting", "waiting chair", False)
            for key, x in (
                ("prop.office.chair_blue_side", 151),
                ("prop.office.chair_orange_side", 154),
            )
        ),
        _p(
            "prop.office.notice_board", 151, 46, "post.service", "service notice", False
        ),
        _p("prop.office.table_light", 157, 59, "post.waiting", "parcel preparation table"),
        _p("prop.office.paper_stack", 157, 58, "post.waiting", "packing forms", False),
        _p("prop.office.filing_cabinet", 169, 53, "post.sorting", "postal records"),
        _p("prop.office.printer_station", 167, 56, "post.sorting", "label printer"),
        _p("prop.office.copier", 169, 55, "post.sorting", "document copier"),
        _p("prop.office.table_light", 165, 59, "post.sorting", "mail sorting table"),
        _p("prop.office.table_light", 168, 59, "post.sorting", "mail sorting table"),
        _p(
            "prop.office.paper_stack",
            165,
            58,
            "post.sorting",
            "sorted mail",
            False,
        ),
        _p(
            "prop.office.paper_stack",
            168,
            58,
            "post.sorting",
            "sorted mail",
            False,
        ),
        _p("prop.office.waste_bin", 169, 61, "post.sorting", "recycling bin", False),
    ),
    "Town Hall": (
        _p(
            "prop.office.counter_cream_left",
            90,
            78,
            "hall.public_service",
            "public counter",
        ),
        *(
            _p(
                "prop.office.counter_cream_middle",
                x,
                78,
                "hall.public_service",
                "public counter",
            )
            for x in (91, 92)
        ),
        _p(
            "prop.office.counter_cream_right",
            93,
            78,
            "hall.public_service",
            "public counter",
        ),
        *(
            _p(
                "prop.office.monitor_blue",
                x,
                76,
                "hall.public_service",
                "service terminal",
                False,
            )
            for x in (91, 93)
        ),
        *(
            _p(key, x, 77, "hall.public_service", "service chair", False)
            for key, x in (
                ("prop.office.chair_blue", 91),
                ("prop.office.chair_orange", 93),
            )
        ),
        *(
            _p(key, x, 82, "hall.public_service", "waiting chair", False)
            for key, x in (
                ("prop.office.chair_blue_side", 89),
                ("prop.office.chair_orange_side", 92),
                ("prop.office.chair_blue_side", 95),
            )
        ),
        *(
            _p("prop.office.computer_desk", x, 79, "hall.administration", "admin desk")
            for x in (100, 104)
        ),
        *(
            _p(
                "prop.office.manager_chair",
                x,
                82,
                "hall.administration",
                "admin chair",
                False,
            )
            for x in (100, 104)
        ),
        _p(
            "prop.office.filing_cabinet",
            106,
            78,
            "hall.administration",
            "civic records",
        ),
        _p(
            "prop.office.whiteboard",
            103,
            76,
            "hall.administration",
            "planning board",
            False,
        ),
        *(
            _p(key, x, y, "hall.council", "council chair", False)
            for key, x, y in (
                ("prop.office.chair_blue", 94, 85),
                ("prop.office.chair_orange", 97, 85),
                ("prop.office.chair_blue", 100, 85),
                ("prop.office.chair_orange", 94, 90),
                ("prop.office.chair_blue", 97, 90),
                ("prop.office.chair_orange", 100, 90),
            )
        ),
        _p("prop.office.table_walnut_long", 96, 88, "hall.council", "council table"),
        _p("prop.office.table_walnut_long", 98, 88, "hall.council", "council table"),
        _p("prop.office.wall_chart", 99, 84, "hall.council", "agenda board", False),
    ),
}
