"""Focused contracts for Claudeville's exterior-cleanup recipe."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.mapgen import claudeville_exterior_cleanup as cleanup
from tools.mapgen import claudeville_semantic_graph as semantic_graph
from tools.mapgen.claudeville_purpose_semantics import SEMANTIC_OBJECTS
from tools.mapgen.claudeville_scenery_blocks import (
    LANDSCAPED_BUFFER_BLOCKS,
    RETIRED_PATH_BLOCKS,
    RETIRED_PATH_VISUAL_RECTS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals"
    / "claudeville_full_town_v2.tmj"
)
PROPS_PATH = REPO_ROOT / "output/claudeville/modern_pixels_v2/props.json"


def _layers(map_data: dict) -> dict[str, dict]:
    return {layer["name"]: layer for layer in map_data["layers"]}


def _properties(item: dict) -> dict[str, object]:
    return {prop["name"]: prop["value"] for prop in item["properties"]}


def _cleanup_objects(map_data: dict) -> list[dict]:
    return [
        item
        for item in _layers(map_data)["Depth Props"]["objects"]
        if str(_properties(item).get("cleanup_id", "")).startswith(
            cleanup.LANDSCAPE_ID_PREFIX
        )
    ]


class ExteriorCleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        cls.prop_keys = set(
            json.loads(PROPS_PATH.read_text(encoding="utf-8"))["frames"]
        )

    def test_recipe_exactly_covers_reviewed_scenery_cells(self):
        expected = set(LANDSCAPED_BUFFER_BLOCKS | RETIRED_PATH_BLOCKS)
        placements = cleanup.LANDSCAPE_PLACEMENTS
        self.assertEqual({item.point for item in placements}, expected)
        self.assertEqual(len(placements), len(expected))
        self.assertEqual(len(placements), 22)
        self.assertEqual(
            cleanup.EXTERIOR_GROUND_CLEAR_RECTS, RETIRED_PATH_VISUAL_RECTS
        )
        self.assertGreaterEqual(len({item.asset_key for item in placements}), 8)
        self.assertTrue({item.asset_key for item in placements} <= self.prop_keys)

        public_objects = {
            point
            for entries in SEMANTIC_OBJECTS.values()
            for semantic in entries
            for point in semantic.logical_tiles
        }
        self.assertFalse(expected & public_objects)

    def test_apply_reveals_bottom_ground_and_builds_visible_blockers(self):
        map_data = copy.deepcopy(self.source)
        layers = _layers(map_data)
        indices = [
            y * 176 + x
            for left, top, right, bottom in cleanup.EXTERIOR_GROUND_CLEAR_RECTS
            for y in range(top, bottom)
            for x in range(left, right)
        ]
        bottom_before = [layers["Bottom Ground"]["data"][index] for index in indices]
        stats = cleanup.apply_exterior_cleanup(map_data, self.prop_keys)
        self.assertEqual(
            stats, {"cleared_exterior_ground_cells": 24, "landscape_props": 22}
        )
        layers = _layers(map_data)
        self.assertEqual(
            [layers["Bottom Ground"]["data"][index] for index in indices],
            bottom_before,
        )
        self.assertTrue(all(bottom_before))
        self.assertTrue(all(not layers["Exterior Ground"]["data"][index] for index in indices))

        objects = _cleanup_objects(map_data)
        self.assertEqual(len(objects), 22)
        self.assertEqual(
            {item["id"] for item in objects},
            set(range(cleanup.LANDSCAPE_OBJECT_ID_BASE, cleanup.LANDSCAPE_OBJECT_ID_BASE + 22)),
        )
        occupied = set()
        for item in objects:
            values = _properties(item)
            point = item["x"] // 32, item["y"] // 32
            occupied.add(point)
            self.assertTrue(item["visible"])
            self.assertTrue(values["blocks"])
            self.assertIn(values["asset_key"], self.prop_keys)
            self.assertEqual(values["anchor_x"], 0.5)
            self.assertEqual(values["anchor_y"], 1)
            self.assertNotIn("zone", values)
            self.assertNotIn("semantic_type", values)
        self.assertEqual(
            occupied, set(LANDSCAPED_BUFFER_BLOCKS | RETIRED_PATH_BLOCKS)
        )
        self.assertTrue(occupied <= semantic_graph.depth_prop_blocks(map_data))

    def test_apply_is_byte_stable_when_repeated(self):
        map_data = copy.deepcopy(self.source)
        first_stats = cleanup.apply_exterior_cleanup(map_data, self.prop_keys)
        first = json.dumps(map_data, sort_keys=True, separators=(",", ":"))
        second_stats = cleanup.apply_exterior_cleanup(map_data, self.prop_keys)
        second = json.dumps(map_data, sort_keys=True, separators=(",", ":"))
        self.assertEqual(first_stats, second_stats)
        self.assertEqual(first, second)

    def test_rejects_missing_art_or_bottom_ground(self):
        with self.assertRaisesRegex(cleanup.ExteriorCleanupError, "props are missing"):
            cleanup.apply_exterior_cleanup(copy.deepcopy(self.source), set())

        map_data = copy.deepcopy(self.source)
        left, top, _right, _bottom = cleanup.EXTERIOR_GROUND_CLEAR_RECTS[0]
        _layers(map_data)["Bottom Ground"]["data"][top * 176 + left] = 0
        with self.assertRaisesRegex(cleanup.ExteriorCleanupError, "no Bottom Ground"):
            cleanup.apply_exterior_cleanup(map_data, self.prop_keys)

    def test_module_stays_focused(self):
        source = Path(cleanup.__file__).read_text(encoding="utf-8")
        self.assertLessEqual(len(source.splitlines()), 500)


if __name__ == "__main__":
    unittest.main()
