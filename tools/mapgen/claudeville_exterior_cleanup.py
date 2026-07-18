"""Deterministic visual cleanup and blocking landscaping for Claudeville."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

try:
    from tools.mapgen.claudeville_scenery_blocks import (
        LANDSCAPED_BUFFER_BLOCKS,
        RETIRED_PATH_BLOCKS,
        RETIRED_PATH_VISUAL_RECTS,
    )
except ModuleNotFoundError:  # Direct script imports.
    from claudeville_scenery_blocks import (  # type: ignore[no-redef]
        LANDSCAPED_BUFFER_BLOCKS,
        RETIRED_PATH_BLOCKS,
        RETIRED_PATH_VISUAL_RECTS,
    )

Point = tuple[int, int]
Rect = tuple[int, int, int, int]
WIDTH, HEIGHT = 176, 96
LOGICAL_WIDTH, LOGICAL_HEIGHT = 88, 48
LANDSCAPE_ID_PREFIX = "claudeville-exterior-cleanup/"
LANDSCAPE_OBJECT_ID_BASE = 12_000
EXTERIOR_GROUND_CLEAR_RECTS: tuple[Rect, ...] = RETIRED_PATH_VISUAL_RECTS


class ExteriorCleanupError(ValueError):
    """Raised when cleanup input cannot preserve the reviewed world contract."""


@dataclass(frozen=True, slots=True)
class LandscapePlacement:
    """One physical, visible landscape blocker on the logical grid."""

    point: Point
    asset_key: str
    style: str


LANDSCAPE_PLACEMENTS: tuple[LandscapePlacement, ...] = (
    LandscapePlacement((51, 5), "prop.landscape.tree_05", "north buffer tree"),
    LandscapePlacement((51, 6), "prop.landscape.flower_bush_01", "north hedge"),
    LandscapePlacement((51, 7), "prop.landscape.flower_bush_03", "north hedge"),
    LandscapePlacement((51, 8), "prop.landscape.tree_07", "north buffer tree"),
    LandscapePlacement((51, 9), "prop.landscape.flower_bush_05", "north hedge"),
    LandscapePlacement((51, 10), "prop.landscape.flower_bush_07", "north hedge"),
    LandscapePlacement((51, 11), "prop.landscape.tree_03", "north buffer tree"),
    LandscapePlacement((81, 11), "prop.landscape.tree_05", "east buffer tree"),
    LandscapePlacement((51, 12), "prop.landscape.flower_bush_01", "north hedge"),
    LandscapePlacement((81, 12), "prop.landscape.flower_bush_03", "east hedge"),
    LandscapePlacement((82, 12), "prop.landscape.flower_bush_07", "east hedge"),
    LandscapePlacement((51, 13), "prop.landscape.flower_bush_03", "north hedge"),
    LandscapePlacement((81, 13), "prop.landscape.flower_bush_05", "east hedge"),
    LandscapePlacement((51, 14), "prop.landscape.tree_09", "north buffer tree"),
    LandscapePlacement((81, 14), "prop.landscape.tree_07", "east buffer tree"),
    LandscapePlacement((51, 15), "prop.landscape.flower_bush_05", "north hedge"),
    LandscapePlacement((79, 41), "prop.landscape.tree_03", "south buffer tree"),
    LandscapePlacement((42, 42), "prop.landscape.flower_bush_01", "retired path hedge"),
    LandscapePlacement((54, 42), "prop.landscape.flower_bush_05", "retired path hedge"),
    LandscapePlacement((42, 43), "prop.landscape.flower_bush_03", "retired path hedge"),
    LandscapePlacement((62, 43), "prop.landscape.tree_09", "south buffer tree"),
    LandscapePlacement((54, 44), "prop.landscape.flower_bush_07", "retired path hedge"),
)


def _properties(value: object) -> dict[str, object]:
    if not isinstance(value, list):
        return {}
    return {
        item.get("name"): item.get("value")
        for item in value
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _layers(map_data: dict) -> dict[str, dict]:
    dimensions = (
        map_data.get("width"),
        map_data.get("height"),
        map_data.get("tilewidth"),
        map_data.get("tileheight"),
    )
    if dimensions != (WIDTH, HEIGHT, 16, 16):
        raise ExteriorCleanupError("Claudeville cleanup requires 176x96 at 16px")
    layers = {
        item.get("name"): item
        for item in map_data.get("layers", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for name in ("Bottom Ground", "Exterior Ground"):
        data = layers.get(name, {}).get("data")
        if not isinstance(data, list) or len(data) != WIDTH * HEIGHT:
            raise ExteriorCleanupError(f"{name} must be a complete tile layer")
    objects = layers.get("Depth Props", {}).get("objects")
    if not isinstance(objects, list):
        raise ExteriorCleanupError("Depth Props must be an object layer")
    return layers


def _cleanup_indices() -> tuple[int, ...]:
    result = []
    for left, top, right, bottom in EXTERIOR_GROUND_CLEAR_RECTS:
        if not (0 <= left < right <= WIDTH and 0 <= top < bottom <= HEIGHT):
            raise ExteriorCleanupError("exterior cleanup rectangle is outside the map")
        result.extend(y * WIDTH + x for y in range(top, bottom) for x in range(left, right))
    if len(result) != len(set(result)):
        raise ExteriorCleanupError("exterior cleanup rectangles overlap")
    return tuple(result)


def _validate_recipe(available_prop_keys: Collection[str]) -> None:
    points = {placement.point for placement in LANDSCAPE_PLACEMENTS}
    expected = set(LANDSCAPED_BUFFER_BLOCKS | RETIRED_PATH_BLOCKS)
    if len(points) != len(LANDSCAPE_PLACEMENTS) or points != expected:
        raise ExteriorCleanupError("landscape recipe must cover every reviewed blocker once")
    if any(
        not (0 <= x < LOGICAL_WIDTH and 0 <= y < LOGICAL_HEIGHT)
        for x, y in points
    ):
        raise ExteriorCleanupError("landscape blocker is outside the logical grid")
    missing = sorted(
        {placement.asset_key for placement in LANDSCAPE_PLACEMENTS}
        - set(available_prop_keys)
    )
    if missing:
        raise ExteriorCleanupError(f"curated landscape props are missing: {missing}")


def _landscape_object(placement: LandscapePlacement, ordinal: int) -> dict:
    x, y = placement.point
    cleanup_id = f"{LANDSCAPE_ID_PREFIX}x{x:02d}-y{y:02d}"
    properties = [
        {"name": "asset_key", "type": "string", "value": placement.asset_key},
        {"name": "anchor_x", "type": "float", "value": 0.5},
        {"name": "anchor_y", "type": "float", "value": 1},
        {"name": "display_scale", "type": "float", "value": 1},
        {"name": "sector", "type": "string", "value": "Exterior"},
        {"name": "blocks", "type": "bool", "value": True},
        {"name": "cleanup_id", "type": "string", "value": cleanup_id},
        {"name": "scenery_group", "type": "string", "value": placement.style},
        {"name": "depth_offset", "type": "float", "value": 0},
    ]
    return {
        "id": LANDSCAPE_OBJECT_ID_BASE + ordinal,
        "name": f"{placement.style.title()} {x},{y}",
        "type": "blocking landscape",
        "x": x * 32 + 16,
        "y": y * 32 + 16,
        "width": 0,
        "height": 0,
        "rotation": 0,
        "visible": True,
        "properties": properties,
    }


def apply_exterior_cleanup(
    map_data: dict, available_prop_keys: Collection[str]
) -> dict[str, int]:
    """Mutate one Tiled map with deterministic ground cleanup and landscaping."""
    if not isinstance(map_data, dict):
        raise ExteriorCleanupError("Tiled map must be an object")
    _validate_recipe(available_prop_keys)
    layers = _layers(map_data)
    bottom = layers["Bottom Ground"]["data"]
    exterior = layers["Exterior Ground"]["data"]
    indices = _cleanup_indices()
    if any(not bottom[index] for index in indices):
        raise ExteriorCleanupError("cleanup cell has no Bottom Ground to reveal")
    for index in indices:
        exterior[index] = 0

    existing = layers["Depth Props"]["objects"]
    retained = [
        item
        for item in existing
        if not str(_properties(item.get("properties")).get("cleanup_id", "")).startswith(
            LANDSCAPE_ID_PREFIX
        )
    ]
    retained_ids = {item.get("id") for item in retained}
    reserved = set(
        range(
            LANDSCAPE_OBJECT_ID_BASE,
            LANDSCAPE_OBJECT_ID_BASE + len(LANDSCAPE_PLACEMENTS),
        )
    )
    if retained_ids & reserved:
        raise ExteriorCleanupError("landscape object id range is already occupied")
    declared = sorted(LANDSCAPE_PLACEMENTS, key=lambda item: (item.point[1], item.point[0]))
    rebuilt = [
        _landscape_object(placement, ordinal)
        for ordinal, placement in enumerate(declared)
    ]
    layers["Depth Props"]["objects"] = [*retained, *rebuilt]
    ids = [item.get("id") for item in layers["Depth Props"]["objects"]]
    if any(not isinstance(value, int) or isinstance(value, bool) for value in ids):
        raise ExteriorCleanupError("Depth Props require integer object ids")
    if len(ids) != len(set(ids)):
        raise ExteriorCleanupError("Depth Props object ids must be unique")
    map_data["nextobjectid"] = max(ids, default=0) + 1
    return {
        "cleared_exterior_ground_cells": len(indices),
        "landscape_props": len(rebuilt),
    }


__all__ = (
    "EXTERIOR_GROUND_CLEAR_RECTS",
    "ExteriorCleanupError",
    "LANDSCAPE_ID_PREFIX",
    "LANDSCAPE_OBJECT_ID_BASE",
    "LANDSCAPE_PLACEMENTS",
    "LandscapePlacement",
    "apply_exterior_cleanup",
)
