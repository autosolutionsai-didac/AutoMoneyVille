"""Shared topology helpers for Claudeville composition tests."""

from __future__ import annotations

import json
from pathlib import Path

from tools.mapgen import claudeville_entry_paths as entry_paths
from tools.mapgen import claudeville_home_semantics as home_semantics
from tools.mapgen import claudeville_purpose_layouts as purpose
from tools.mapgen import claudeville_semantic_graph as semantic_graph
from tools.mapgen import compose_claudeville_interiors as composer
from tools.mapgen.claudeville_home_semantics import HOME_ENTRANCES

LEGACY_V2_SECTOR_RECTS = {
    "Bank": [4, 5, 14, 15],
    "Home 1": [22, 4, 31, 16],
    "University": [36, 2, 50, 16],
    "Agent Academy": [54, 4, 65, 16],
    "Post Office": [73, 15, 87, 32],
    "Market": [73, 12, 80, 14],
    "Workshop": [4, 20, 14, 31],
    "Community Center": [22, 20, 31, 32],
    "Library": [55, 20, 65, 31],
    "Home 2": [2, 35, 8, 45],
    "Home 3": [10, 35, 16, 45],
    "Home 4": [18, 35, 24, 45],
    "Home 5": [26, 35, 32, 45],
    "Home 6": [34, 35, 41, 45],
    "Town Hall": [43, 34, 53, 45],
    "Home 7": [55, 35, 61, 45],
    "Home 8": [63, 35, 69, 45],
    "Home 9": [71, 35, 78, 45],
    "Home 10": [80, 35, 86, 45],
    "Central Plaza": [33, 20, 45, 31],
    "Claudeville Cafe": [46, 20, 53, 31],
}


def legacy_v2_sector_cells() -> dict[str, set[tuple[int, int]]]:
    """Return the complete geometry owned by the legacy full-town fixture."""
    return semantic_graph.sector_cells({
        "sectors": [
            {"name": name, "rect": rect}
            for name, rect in LEGACY_V2_SECTOR_RECTS.items()
        ],
    })


def load_map(path: Path = composer.SOURCE_MAP) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def layer_lookup(map_data: dict) -> dict[str, dict]:
    return {layer["name"]: layer for layer in map_data["layers"]}


def cells_in(bounds: tuple[int, int, int, int]):
    left, top, right, bottom = bounds
    for y in range(top, bottom):
        for x in range(left, right):
            yield x, y, y * composer.WIDTH + x


def logical_clear_cells(
    layers: dict[str, dict], bounds: tuple[int, int, int, int]
) -> set[tuple[int, int]]:
    left, top, right, bottom = bounds
    blocked_props = {
        (item.visual_x // 2, item.visual_y // 2)
        for items in purpose.PURPOSE_PROPS.values()
        for item in items
        if item.blocks
    }
    result = set()
    for y in range((top + 1) // 2, bottom // 2):
        for x in range((left + 1) // 2, right // 2):
            indices = [
                (2 * y + dy) * composer.WIDTH + 2 * x + dx
                for dy in (0, 1)
                for dx in (0, 1)
            ]
            has_ground = all(
                layers["Interior Ground"]["data"][index]
                or layers["Exterior Ground"]["data"][index]
                for index in indices
            )
            has_blocker = any(
                layers[name]["data"][index]
                for name in ("Wall", *entry_paths.PUBLIC_TILE_LAYERS)
                for index in indices
            )
            if has_ground and not has_blocker and (x, y) not in blocked_props:
                result.add((x, y))
    return result


def reachable(
    start: tuple[int, int], clear: set[tuple[int, int]]
) -> set[tuple[int, int]]:
    found = {start} if start in clear else set()
    pending = list(found)
    while pending:
        x, y = pending.pop()
        for candidate in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if candidate in clear and candidate not in found:
                found.add(candidate)
                pending.append(candidate)
    return found


def derive_homes(layers: dict[str, dict]):
    return home_semantics.derive_home_semantics(
        layers,
        purpose,
        active_sectors=set(HOME_ENTRANCES),
        sector_cells=legacy_v2_sector_cells(),
    )
