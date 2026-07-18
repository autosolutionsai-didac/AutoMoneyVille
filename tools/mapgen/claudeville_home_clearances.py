"""Reviewed home clearances and their purpose-aware room assignments."""

from __future__ import annotations

from collections import defaultdict

try:
    from tools.mapgen.claudeville_circulation_cells import HOME_CIRCULATION_CELLS
except ModuleNotFoundError:  # Direct script import.
    from claudeville_circulation_cells import (  # type: ignore[no-redef]
        HOME_CIRCULATION_CELLS,
    )

Point = tuple[int, int]


class HomeSemanticError(ValueError):
    """Raised when a licensed home template cannot be mapped truthfully."""


def reviewed_clearance_points(home_name: str, recipes, floor: set[Point]) -> set[Point]:
    """Return exact stance and circulation cells after floor validation."""
    points = {recipe.point for recipe in recipes} | set(
        HOME_CIRCULATION_CELLS.get(home_name, ())
    )
    if unknown := points - floor:
        raise HomeSemanticError(
            f"{home_name} authored clearances are outside floor: {sorted(unknown)}"
        )
    return points


def assign_reviewed_stance_rooms(home_name: str, recipes, assignment) -> None:
    """Keep an unambiguous object stance inside the room it serves."""
    zone_prefix = f"{home_name.casefold().replace(' ', '_')}."
    targets: dict[Point, set[str]] = defaultdict(set)
    for recipe in recipes:
        if not recipe.zone.startswith(zone_prefix):
            raise HomeSemanticError(
                f"{home_name} stance has invalid zone {recipe.zone}"
            )
        targets[recipe.point].add(recipe.zone)
    for point, zones in targets.items():
        if len(zones) == 1:
            assignment[point] = next(iter(zones)).removeprefix(zone_prefix).replace(
                "_", " "
            )


def align_refrigerator_rooms(assignment, object_votes) -> None:
    """Keep each refrigerator with its nearest cooking area, not a legacy boundary."""
    dominant = {
        point: sorted(votes.items(), key=lambda item: (-item[1], item[0]))[0][0]
        for point, votes in object_votes.items()
    }
    cooking = [point for point, object_type in dominant.items() if object_type == "cooking area"]
    for point, object_type in dominant.items():
        if object_type != "refrigerator" or not cooking:
            continue
        nearest = min(
            cooking,
            key=lambda other: (
                abs(point[0] - other[0]) + abs(point[1] - other[1]),
                other[1],
                other[0],
            ),
        )
        assignment[point] = assignment[nearest]
