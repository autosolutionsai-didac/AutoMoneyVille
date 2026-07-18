"""Parcel-grove data and validation for the Claudeville public realm."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

try:
    from tools.mapgen import claudeville_reference_layout as layout
except ModuleNotFoundError:  # Direct mapgen execution.
    import claudeville_reference_layout as layout


PARCEL_GROVES = {
    "Bank": ((24, 14), (24, 21), (25, 29), (52, 14), (52, 22), (52, 29)),
    "Home 1": ((63, 14), (64, 22), (65, 29), (92, 14), (93, 22), (92, 29)),
    "University": ((96, 8), (96, 18), (96, 28), (134, 9), (135, 20), (135, 29)),
    "Agent Academy": (),
    "Market": (),
    "Workshop": ((24, 47), (24, 55), (25, 64), (52, 48), (52, 57), (52, 65)),
    "Community Center": ((63, 48), (64, 57), (65, 65), (92, 49), (93, 58), (92, 66)),
    "Claudeville Cafe": (),
    "Library": (),
    "Post Office": (),
    "Home 2": ((24, 83), (24, 89), (52, 84), (52, 90)),
    "Home 3": (),
    "Home 4": ((63, 83), (64, 90), (92, 84), (93, 90)),
    "Home 5": (),
    "Home 6": (),
    "Town Hall": ((96, 84), (96, 90), (115, 84), (115, 90)),
    "Home 7": (),
    "Home 8": (),
    "Home 9": (),
    "Home 10": (),
}


def parcel_grove_placements(context: Mapping[str, Any]) -> tuple:
    """Build the parcel groves after all traced exclusions are available."""
    result = []
    for sector, points in PARCEL_GROVES.items():
        for index, point in enumerate(points):
            if (
                point in context["WATER_CELLS"]
                or point in context["PROP_EXCLUSION_CELLS"]
                or any(context["_inside"](point, rect)
                       for rect in context["STRUCTURE_RECTS"])
            ):
                raise ValueError(f"parcel grove blocks traced geometry: {point}")
            result.append((
                sector, context["SECTOR_ZONE"][sector], "perimeter-tree",
                "parcel side grove", context["TREE_KEYS"][index % len(context["TREE_KEYS"])],
                point[0], point[1],
            ))
    return tuple(result)


def merge_placements(*groups: tuple) -> tuple:
    """Deduplicate layered landscape art by its native-16 foot point."""
    by_point = {
        (item[5], item[6]): item
        for group in groups
        for item in group
    }
    return tuple(by_point.values())


def finalize_placements(
    context: Mapping[str, Any], civic_landscape: Any,
) -> tuple[tuple, tuple, tuple]:
    """Create the late-bound grove/plaza groups and their merged placement list."""
    groves = parcel_grove_placements(context)
    plaza = civic_landscape.placements(
        context["_owner"], context["SECTOR_ZONE"], context["WATER_CELLS"],
        context["STRUCTURE_RECTS"], context["_inside"],
        tuple(context["_polygon_cells"](points)
              for points in context["PLAZA_BED_POLYGONS"]),
    )
    merged = merge_placements(
        context["FOREST_WALL_PLACEMENTS"], context["PERIMETER_PLACEMENTS"],
        context["FOUNDATION_PLACEMENTS"], groves, plaza,
    )
    return groves, plaza, merged


def validate_public_realm(context: Mapping[str, Any]) -> None:
    """Validate the assembled public-realm module without a circular import."""
    width, height = context["WIDTH"], context["HEIGHT"]
    water_runs = context["WATER_RUNS"]
    avenue_rects = context["AVENUE_RECTS"]
    polygons = context["PLAZA_BED_POLYGONS"]
    polygon_cells = context["_polygon_cells"]
    water_tile_plan = context["water_tile_plan"]
    water_cells = context["WATER_CELLS"]
    iter_bottom_tiles = context["iter_bottom_tiles"]
    public_paths = context["PUBLIC_PATH_CELLS"]
    planting_beds = context["PLANTING_BED_CELLS"]
    placements = context["PLACEMENTS"]
    sector_zone = context["SECTOR_ZONE"]
    prop_keys = context["PROP_ASSET_KEYS"]
    structure_rects = context["STRUCTURE_RECTS"]
    inside = context["_inside"]

    if (width, height) != (176, 96) or water_runs != layout.WATER_RUNS:
        raise ValueError("public realm must preserve the 176x96 reference water mask")
    if avenue_rects != ((18, 37, 176, 43), (18, 73, 176, 79)):
        raise ValueError("target avenues must retain their measured warm-paver bands")
    if layout.MAIN_PATHS[2:] != ((58, 0, 62, 96), (139, 0, 142, 96)):
        raise ValueError("target map requires the two measured civic spines")
    if any(row > 11 for row in water_runs):
        raise ValueError("the river must not recreate a bottom or side frame")
    if len(polygons) != 4 or any(
        polygon_cells(a) & polygon_cells(b)
        for index, a in enumerate(polygons)
        for b in polygons[index + 1:]
    ):
        raise ValueError("Central Plaza requires four disjoint planted quadrants")
    if len(water_tile_plan()) != len(water_cells):
        raise ValueError("water transition plan no longer matches WATER_RUNS")
    if len(tuple(iter_bottom_tiles())) != context["TILE_COUNT"]:
        raise ValueError("Bottom Ground plan must cover the complete visual map")
    if not public_paths or public_paths & planting_beds:
        raise ValueError("public paths must circulate around, not through, plaza beds")

    occupied: set[tuple[int, int]] = set()
    counts: dict[str, int] = {}
    quadrant_trees = [0, 0, 0, 0]
    for sector, zone, role, _cluster, key, x, y in placements:
        point = (x, y)
        if sector not in sector_zone or zone != sector_zone[sector]:
            raise ValueError(f"invalid public-realm sector or zone: {(sector, zone)}")
        if key not in prop_keys or not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"invalid public-realm asset or foot: {(key, point)}")
        if point in occupied:
            raise ValueError(f"duplicate public-realm prop foot: {point}")
        if point in water_cells or any(inside(point, rect) for rect in structure_rects):
            raise ValueError(f"public-realm prop overlaps water or structure: {point}")
        if role in {"perimeter-tree", "foundation-hedge"} and point in public_paths:
            raise ValueError(f"planting blocks a public path: {point}")
        occupied.add(point)
        counts[role] = counts.get(role, 0) + 1
        if role == "plaza-tree":
            matches = [
                index for index, polygon in enumerate(polygons)
                if point in polygon_cells(polygon)
            ]
            if len(matches) != 1:
                raise ValueError(f"plaza tree is outside a unique quadrant: {point}")
            quadrant_trees[matches[0]] += 1
    if counts.get("perimeter-tree", 0) < 60:
        raise ValueError("the west woodland and top shore need at least 60 conifers")
    if min(quadrant_trees) < 3 or (
        counts.get("garden-seat", 0) + counts.get("bench", 0) < 20
    ):
        raise ValueError("plaza quadrants and facade gardens are under-furnished")
    if counts.get("lamp", 0) < 20 or counts.get("foundation-hedge", 0) < 80:
        raise ValueError("civic lamp or continuous hedge rhythm is incomplete")
