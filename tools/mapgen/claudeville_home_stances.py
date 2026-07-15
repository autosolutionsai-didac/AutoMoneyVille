"""Purposeful standing cells beside Claudeville home interactions."""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[int, int]


@dataclass(frozen=True, slots=True)
class HomeStance:
    """One authored cardinal stance for a grouped semantic home object."""

    zone: str
    object_type: str
    point: Point


def _s(zone: str, object_type: str, x: int, y: int) -> HomeStance:
    return HomeStance(zone, object_type, (x, y))


HOME_STANCE_CELLS: dict[str, tuple[HomeStance, ...]] = {
    "Home 1": (
        _s("home_1.kitchen", "cooking area", 27, 6),
        _s("home_1.kitchen", "refrigerator", 27, 9),
    ),
    "Home 2": (_s("home_2.main_room", "desk", 4, 41),),
    "Home 3": (_s("home_3.main_room", "closet", 11, 39),),
    "Home 4": (
        _s("home_4.main_room", "closet", 21, 38),
        _s("home_4.main_room", "common room sofa", 22, 38),
        _s("home_4.main_room", "cooking area", 22, 41),
    ),
    "Home 5": (
        _s("home_5.bedroom", "desk", 28, 41),
        _s("home_5.bedroom", "bed", 29, 41),
    ),
    "Home 6": (
        _s("home_6.bathroom", "bathroom sink", 41, 38),
        _s("home_6.kitchen", "cooking area", 37, 38),
        _s("home_6.living_room", "harp", 37, 38),
        _s("home_6.living_room", "shelf", 34, 38),
    ),
    "Home 7": (
        _s("home_7.bathroom", "bathroom sink", 59, 38),
        _s("home_7.bedroom", "bed", 59, 41),
        _s("home_7.bedroom", "desk", 56, 41),
        _s("home_7.kitchen", "cooking area", 57, 38),
        _s("home_7.living_room", "shelf", 57, 38),
    ),
    "Home 8": (
        _s("home_8.bedroom", "desk", 67, 41),
        _s("home_8.bedroom", "bed", 66, 41),
    ),
    "Home 9": (
        _s("home_9.kitchen", "cooking area", 75, 38),
        _s("home_9.living_room", "harp", 75, 38),
        _s("home_9.living_room", "shelf", 78, 38),
    ),
    "Home 10": (
        _s("home_10.bathroom", "bathroom sink", 82, 38),
        _s("home_10.bathroom", "shower", 81, 40),
        _s("home_10.bedroom", "bed", 82, 41),
        _s("home_10.kitchen", "cooking area", 84, 38),
    ),
}
