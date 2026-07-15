"""Stamps, entrances, spawns, and semantic objects for Claudeville."""

from __future__ import annotations

try:
    from tools.mapgen.claudeville_purpose_types import (
        AtlasStamp,
        Point,
        Rect,
        SemanticObject,
    )
except ModuleNotFoundError:
    from claudeville_purpose_types import (  # type: ignore[no-redef]
        AtlasStamp,
        Point,
        Rect,
        SemanticObject,
    )


def _old(source_rect: Rect, destination: Point) -> AtlasStamp:
    return AtlasStamp(
        "legacy_the_ville",
        source_rect,
        destination,
        "source-layers",
        "preserve-collision",
    )


PURPOSE_STAMPS: dict[str, tuple[AtlasStamp, ...]] = {
    "Bank": (
        AtlasStamp(
            "office_furniture",
            (0, 23, 2, 3),
            (16, 14),
            "Interior Furniture L1",
            "preserve-collision",
        ),
        AtlasStamp(
            "office_furniture",
            (4, 23, 2, 3),
            (18, 14),
            "Interior Furniture L1",
            "preserve-collision",
        ),
    ),
    "University": (
        _old((108, 19, 8, 11), (74, 9)),
        _old((118, 19, 7, 11), (86, 9)),
        _old((72, 19, 12, 8), (87, 21)),
    ),
    "Agent Academy": (_old((108, 19, 8, 11), (110, 11)),),
    "Market": (_old((78, 45, 14, 6), (147, 23)),),
    "Workshop": (
        AtlasStamp(
            "exteriors_worksite",
            (8, 12, 2, 7),
            (10, 42),
            "Interior Furniture L1",
            "preserve-collision",
        ),
        AtlasStamp(
            "exteriors_worksite",
            (3, 13, 5, 6),
            (15, 42),
            "Interior Furniture L1",
            "preserve-collision",
        ),
        AtlasStamp(
            "exteriors_worksite",
            (28, 7, 4, 7),
            (23, 42),
            "Interior Furniture L1",
            "preserve-collision",
        ),
        AtlasStamp(
            "exteriors_worksite",
            (14, 6, 3, 6),
            (12, 49),
            "Interior Furniture L1",
            "preserve-collision",
        ),
        AtlasStamp(
            "exteriors_worksite",
            (7, 7, 2, 2),
            (20, 54),
            "Interior Furniture L1",
            "preserve-collision",
        ),
    ),
    "Claudeville Cafe": (
        _old((72, 19, 12, 8), (95, 44)),
        _old((53, 20, 10, 7), (96, 50)),
    ),
    "Library": (
        _old((56, 41, 4, 3), (113, 43)),
        _old((56, 41, 4, 3), (117, 43)),
        _old((56, 45, 8, 3), (113, 48)),
        _old((110, 20, 6, 7), (114, 54)),
        _old((56, 41, 4, 3), (122, 43)),
        _old((56, 45, 8, 3), (122, 48)),
    ),
    "Post Office": (
        AtlasStamp(
            "exteriors_post",
            (0, 13, 7, 4),
            (162, 45),
            "Interior Furniture L1",
            "preserve-collision",
        ),
    ),
}
HOME_KITCHEN_STAMPS: dict[str, tuple[AtlasStamp, ...]] = {
    "Home 1": (_old((53, 18, 10, 3), (47, 12)),),
    "Home 5": (_old((53, 18, 10, 3), (54, 75)),),
    "Home 6": (_old((53, 18, 10, 3), (71, 75)),),
    "Home 7": (_old((53, 18, 10, 3), (112, 75)),),
    "Home 8": (_old((53, 18, 10, 3), (128, 75)),),
    "Home 9": (_old((53, 18, 10, 3), (145, 75)),),
    "Home 10": (_old((53, 18, 10, 3), (162, 75)),),
}
ENTRANCES: dict[str, Point] = {
    "Bank": (9, 16),
    "University": (42, 16),
    "Agent Academy": (56, 16),
    "Market": (77, 16),
    "Workshop": (9, 31),
    "Community Center": (26, 31),
    "Claudeville Cafe": (50, 31),
    "Library": (59, 31),
    "Post Office": (80, 31),
    "Town Hall": (48, 37),
}
SPAWNS: dict[str, Point] = {
    "Bank": (9, 13),
    "University": (42, 12),
    "Agent Academy": (57, 12),
    "Market": (77, 13),
    "Workshop": (10, 28),
    "Community Center": (24, 30),
    "Claudeville Cafe": (49, 27),
    "Library": (60, 30),
    "Post Office": (80, 27),
    "Town Hall": (47, 39),
}
SEMANTIC_OBJECTS: dict[str, tuple[SemanticObject, ...]] = {
    "Bank": (
        SemanticObject(
            "bank.teller", "teller counter", ((10, 11), (11, 11), (12, 11), (13, 11))
        ),
        SemanticObject("bank.advisory", "advisory desk", ((6, 11), (6, 14))),
        SemanticObject("bank.archive", "secure records", ((9, 8),)),
        SemanticObject("bank.archive", "archive cabinets", ((8, 7), (9, 7))),
        SemanticObject(
            "bank.waiting", "waiting seating", ((10, 13), (11, 13), (12, 13))
        ),
    ),
    "University": (
        SemanticObject(
            "university.lecture",
            "lecture seating",
            ((38, 7), (41, 7), (38, 9), (41, 9)),
        ),
        SemanticObject("university.study_lab", "computer station", ((44, 7), (47, 7))),
        SemanticObject(
            "university.cafeteria", "service counter", ((43, 12), (44, 12), (45, 12))
        ),
        SemanticObject("university.cafeteria", "dining table", ((42, 14), (45, 14))),
    ),
    "Agent Academy": (
        SemanticObject(
            "academy.training_lab", "training simulator", ((56, 7), (58, 7))
        ),
        SemanticObject(
            "academy.classroom",
            "classroom seating",
            ((61, 8), (63, 8), (61, 10), (63, 10)),
        ),
        SemanticObject("academy.reception", "reception desk", ((55, 14), (57, 14))),
        SemanticObject("academy.lounge", "lounge seating", ((59, 14), (61, 14))),
    ),
    "Market": (
        SemanticObject(
            "market.retail",
            "stock display",
            ((75, 12), (76, 12), (77, 12), (78, 12), (79, 12)),
        ),
        SemanticObject(
            "market.checkout",
            "checkout counter",
            ((75, 14), (76, 14)),
        ),
    ),
    "Workshop": (
        SemanticObject(
            "workshop.machine_bay", "tool storage", ((5, 21), (8, 21), (12, 21))
        ),
        SemanticObject("workshop.machine_bay", "work machine", ((6, 25),)),
        SemanticObject("workshop.machine_bay", "workbench", ((10, 27),)),
        SemanticObject("workshop.intake", "job intake", ((6, 28), (7, 28), (8, 28))),
    ),
    "Community Center": (
        SemanticObject(
            "community.event_hall", "presentation area", ((25, 24), (27, 24), (30, 24))
        ),
        SemanticObject("community.event_hall", "event table", ((26, 26), (29, 26))),
        SemanticObject(
            "community.lounge", "lounge seating", ((24, 29), (26, 29), (27, 29))
        ),
        SemanticObject("community.reception", "help desk", ((29, 30), (31, 30))),
    ),
    "Claudeville Cafe": (
        SemanticObject(
            "cafe.service", "service counter", ((49, 25), (50, 25), (51, 25), (52, 25))
        ),
        SemanticObject("cafe.dining", "dining table", ((48, 27), (51, 27))),
        SemanticObject("cafe.terrace", "terrace table", ((47, 29), (52, 30))),
    ),
    "Library": (
        SemanticObject(
            "library.stacks", "bookshelf", ((58, 22), (59, 22), (57, 24), (59, 24))
        ),
        SemanticObject(
            "library.stacks",
            "east bookshelf",
            ((61, 22), (62, 22), (61, 24), (62, 24), (63, 24), (64, 24)),
        ),
        SemanticObject("library.reading", "reading table", ((60, 29), (62, 29))),
        SemanticObject("library.circulation", "circulation desk", ((57, 29), (57, 30))),
    ),
    "Post Office": (
        SemanticObject(
            "post.service", "postal counter", ((75, 26), (76, 26), (77, 26), (78, 26))
        ),
        SemanticObject(
            "post.waiting", "waiting seating", ((75, 28), (77, 28), (78, 28))
        ),
        SemanticObject(
            "post.sorting", "sorting station", ((81, 27), (83, 28), (84, 27))
        ),
        SemanticObject(
            "post.sorting", "parcel sorting rack", ((81, 23), (82, 23), (83, 23), (84, 23))
        ),
        SemanticObject(
            "post.sorting", "mail sorting table", ((82, 29), (84, 29))
        ),
    ),
    "Town Hall": (
        SemanticObject("hall.public_service", "public counter", ((45, 39), (46, 39))),
        SemanticObject(
            "hall.administration", "administration desk", ((50, 39), (52, 39))
        ),
        SemanticObject("hall.council", "council table", ((47, 44), (49, 44))),
    ),
}
