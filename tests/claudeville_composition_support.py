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
    spec = json.loads(
        composer.REPO_ROOT.joinpath("tools/mapgen/town_spec.json").read_text(
            encoding="utf-8"
        )
    )
    return home_semantics.derive_home_semantics(
        layers,
        purpose,
        active_sectors=set(HOME_ENTRANCES),
        sector_cells=semantic_graph.sector_cells(spec),
    )
