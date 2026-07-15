"""Hand-authored Modern Interiors placement plan for Claudeville v2."""

from __future__ import annotations

from dataclasses import dataclass

Rect = tuple[int, int, int, int]
Point = tuple[int, int]


@dataclass(frozen=True)
class Stamp:
    """Copy one coherent room assembly from the licensed legacy sample map."""

    template: str
    destination: Point
    mirror_x: bool = False


@dataclass(frozen=True)
class Home:
    """One complete or deliberately cropped residential layout."""

    name: str
    bounds: Rect
    stamp: Stamp


# Coordinates are old The Ville cells. The art is exact nearest-neighbour 2x,
# so one old 32px cell becomes one native 16px Claudeville visual cell.
SOURCE_TEMPLATES: dict[str, Rect] = {
    "cafe": (72, 19, 12, 8),
    "bar": (53, 20, 10, 7),
    "classroom": (108, 19, 8, 11),
    "college_library": (118, 19, 7, 11),
    "book_library": (56, 41, 16, 14),
    "market_core": (78, 45, 14, 6),
    "dorm_common": (113, 45, 12, 10),
    "compact_adam": (19, 58, 7, 13),
    "compact_yuriko": (27, 58, 7, 13),
    "compact_moore": (35, 58, 7, 13),
    "family_tamara": (50, 64, 14, 19),
    "family_moreno_narrow": (70, 64, 10, 16),
    "family_lin_narrow": (88, 64, 10, 16),
    "family_tamara_narrow": (50, 64, 10, 16),
}


# Exclusive visual-cell bounds follow the existing building shells. They are
# also used to keep imported furniture away from roads, gardens and entrances.
BUILDING_BOUNDS: dict[str, Rect] = {
    "Bank": (10, 12, 29, 32),
    "Home 1": (45, 10, 62, 32),
    "University": (73, 8, 100, 32),
    "Agent Academy": (109, 10, 130, 32),
    "Market": (147, 22, 161, 30),
    "Workshop": (8, 40, 29, 63),
    "Community Center": (45, 43, 65, 63),
    "Claudeville Cafe": (94, 43, 109, 57),
    "Library": (112, 42, 131, 64),
    "Post Office": (149, 43, 172, 64),
    "Home 2": (5, 75, 16, 91),
    "Home 3": (21, 75, 32, 91),
    "Home 4": (38, 75, 49, 91),
    "Home 5": (53, 75, 65, 91),
    "Home 6": (69, 75, 83, 91),
    "Town Hall": (88, 75, 107, 91),
    "Home 7": (111, 75, 124, 91),
    "Home 8": (127, 75, 139, 91),
    "Home 9": (144, 75, 157, 91),
    "Home 10": (161, 75, 172, 91),
}


# Repeating 4x2 floor motifs from the paid Room Builder sheet. Coordinates are
# native tile rows/columns. Institutional lab/workshop floors stay Office;
# civilian-facing rooms get the warmer Modern Interiors palette.
FLOOR_THEMES: dict[str, tuple[int, int]] = {
    "Bank": (60, 19),
    "Market": (54, 25),
    "Community Center": (60, 19),
    "Claudeville Cafe": (54, 25),
    "Library": (60, 19),
    "Town Hall": (60, 19),
}

HOME_FLOOR_THEMES: dict[str, tuple[int, int]] = {
    "Home 1": (60, 19),
    "Home 2": (54, 1),
    "Home 3": (54, 7),
    "Home 4": (54, 25),
    "Home 5": (60, 19),
    "Home 6": (54, 1),
    "Home 7": (54, 7),
    "Home 8": (60, 19),
    "Home 9": (54, 1),
    "Home 10": (54, 7),
}


# Public rooms retain the existing Modern Office shell and receive coherent
# Modern Interiors furniture assemblies. Repeated assemblies are deliberately
# combined differently so each civic building reads as a separate function.
PUBLIC_STAMPS: dict[str, tuple[Stamp, ...]] = {
    "Bank": (
        Stamp("bar", (11, 14)),
        Stamp("college_library", (20, 14)),
        Stamp("cafe", (12, 23)),
    ),
    "University": (
        Stamp("classroom", (74, 9)),
        Stamp("college_library", (84, 9)),
        Stamp("classroom", (91, 9), mirror_x=True),
        Stamp("cafe", (87, 21)),
    ),
    "Agent Academy": (
        Stamp("classroom", (110, 11)),
        Stamp("dorm_common", (118, 11)),
        Stamp("cafe", (110, 22)),
    ),
    "Market": (Stamp("market_core", (147, 23)),),
    "Workshop": (
        Stamp("market_core", (10, 42)),
        Stamp("market_core", (10, 48), mirror_x=True),
        Stamp("bar", (17, 53), mirror_x=True),
    ),
    "Community Center": (
        Stamp("cafe", (46, 44)),
        Stamp("college_library", (57, 44)),
        Stamp("bar", (51, 54), mirror_x=True),
    ),
    "Claudeville Cafe": (
        Stamp("cafe", (95, 44)),
        Stamp("bar", (97, 50), mirror_x=True),
    ),
    "Library": (
        Stamp("book_library", (113, 43)),
        Stamp("classroom", (114, 53)),
    ),
    "Post Office": (
        Stamp("bar", (150, 44)),
        Stamp("market_core", (158, 44)),
        Stamp("market_core", (151, 49), mirror_x=True),
        Stamp("cafe", (152, 55)),
    ),
    "Town Hall": (
        Stamp("college_library", (89, 76)),
        Stamp("classroom", (98, 76)),
        Stamp("bar", (92, 84), mirror_x=True),
    ),
}


HOMES: tuple[Home, ...] = (
    Home("Home 1", BUILDING_BOUNDS["Home 1"], Stamp("family_tamara", (47, 12))),
    Home("Home 2", BUILDING_BOUNDS["Home 2"], Stamp("compact_adam", (7, 77))),
    Home("Home 3", BUILDING_BOUNDS["Home 3"], Stamp("compact_yuriko", (23, 77))),
    Home("Home 4", BUILDING_BOUNDS["Home 4"], Stamp("compact_moore", (40, 77))),
    Home("Home 5", BUILDING_BOUNDS["Home 5"], Stamp("family_tamara_narrow", (54, 75))),
    Home("Home 6", BUILDING_BOUNDS["Home 6"], Stamp("family_moreno_narrow", (71, 75))),
    Home("Home 7", BUILDING_BOUNDS["Home 7"], Stamp("family_lin_narrow", (112, 75))),
    Home("Home 8", BUILDING_BOUNDS["Home 8"], Stamp("family_tamara_narrow", (128, 75), True)),
    Home("Home 9", BUILDING_BOUNDS["Home 9"], Stamp("family_moreno_narrow", (145, 75), True)),
    Home("Home 10", BUILDING_BOUNDS["Home 10"], Stamp("family_lin_narrow", (162, 75), True)),
)
