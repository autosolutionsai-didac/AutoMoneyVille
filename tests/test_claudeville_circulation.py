"""Purpose and collision contracts for Claudeville's reviewed circulation."""

from __future__ import annotations

import unittest

from tools.mapgen import claudeville_circulation_cells as circulation
from tools.mapgen import claudeville_entry_paths as entry_paths
from tools.mapgen import claudeville_home_semantics as homes
from tools.mapgen import claudeville_home_stances as home_stances
from tools.mapgen import claudeville_purpose_layouts as layout
from tools.mapgen import claudeville_scenery_blocks as scenery
from tools.mapgen import claudeville_semantic_graph as graph
from tools.mapgen import compile_claudeville_semantics as compiler


def empty_layers() -> dict[str, dict]:
    names = (
        "Bottom Ground",
        "Interior Ground",
        "Exterior Ground",
        "Wall",
        *entry_paths.PUBLIC_TILE_LAYERS,
    )
    return {name: {"data": [0] * (176 * 96)} for name in names}


class ClaudevilleCirculationTests(unittest.TestCase):
    def test_blocker_free_exterior_paving_replaces_stale_collision(self):
        layers = empty_layers()
        layers["Bottom Ground"]["data"] = [1] * (176 * 96)
        logical = (12, 11)
        indices = [
            (2 * logical[1] + dy) * 176 + 2 * logical[0] + dx
            for dy in (0, 1)
            for dx in (0, 1)
        ]
        for index in indices:
            layers["Exterior Ground"]["data"][index] = 1
        self.assertIn(logical, entry_paths.authored_walkable_cells(layers, set()))
        self.assertNotIn(
            logical, entry_paths.authored_walkable_cells(layers, {logical})
        )
        layers["Wall"]["data"][indices[0]] = 1
        self.assertNotIn(logical, entry_paths.authored_walkable_cells(layers, set()))

    def test_reviewed_cells_preserve_objects_blockers_and_scenery(self):
        tmj = compiler._read_json(compiler.TMJ_PATH)
        layers = compiler._layers(tmj)
        sectors = graph.sector_cells(compiler._read_json(compiler.SPEC_PATH))
        home_data = homes.derive_home_semantics(layers, layout, sector_cells=sectors)
        reviewed = set().union(*circulation.CIRCULATION_CELLS.values())
        occupied = {
            point
            for entries in (*layout.SEMANTIC_OBJECTS.values(), *home_data.objects.values())
            for entry in entries
            for point in entry.logical_tiles
        }
        stances = {
            item.point
            for items in home_stances.HOME_STANCE_CELLS.values()
            for item in items
        }
        protected = (
            occupied
            | graph.prop_cells(layout, blocked_only=True)
            | graph.depth_prop_blocks(tmj)
            | stances
            | scenery.SCENERY_BLOCK_CELLS
        )
        self.assertEqual(len(reviewed), 44)
        self.assertFalse(reviewed & protected)


if __name__ == "__main__":
    unittest.main()
