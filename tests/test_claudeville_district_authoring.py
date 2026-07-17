"""Contracts for the explicit Claudeville district authoring passes."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from tools.mapgen import author_claudeville_districts as districts
from tools.mapgen import claudeville_tiled_authoring as authoring
from tools.mapgen import compile_claudeville_semantics as compiler

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PROPS = (
    ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visual_candidates/"
    / "browser-modern-interiors-v16/runtime/props.json"
)


class DistrictAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(districts.DEFAULT_MAP.read_text(encoding="utf-8"))
        cls.depth = next(
            layer for layer in cls.source["layers"] if layer["name"] == "Depth Props"
        )
        cls.authoring_group = next(
            layer for layer in cls.source["layers"]
            if layer["name"] == authoring.GROUP_NAME
        )

    def test_every_registered_district_matches_its_explicit_placement_table(self):
        source_properties = authoring.properties(self.source.get("properties"))
        for district, module in districts.DISTRICTS.items():
            with self.subTest(district=district):
                self.assertEqual(
                    source_properties[f"{district}_district_revision"],
                    module.REVISION,
                )
                actual = Counter()
                for item in self.depth["objects"]:
                    if not item.get("name", "").startswith(f"{district}-"):
                        continue
                    values = authoring.properties(item.get("properties"))
                    actual[(
                        values["sector"], values["zone"],
                        values["semantic_type"], values["purpose_cluster"],
                        values["asset_key"], item["x"], item["y"],
                    )] += 1
                expected = Counter(
                    (sector, zone, role, cluster, key, x * 16, y * 16)
                    for sector, zone, role, cluster, key, x, y in module.PLACEMENTS
                )
                self.assertEqual(actual, expected)

    def test_north_interactions_link_only_to_the_new_purposeful_objects(self):
        created_ids = {
            item["id"] for item in self.depth["objects"]
            if item.get("name", "").startswith("north-")
        }
        interactions = next(
            layer for layer in self.authoring_group["layers"]
            if layer["name"] == "Interactions"
        )
        north = []
        for item in interactions["objects"]:
            values = authoring.properties(item.get("properties"))
            if values.get("sector") not in districts.DISTRICTS["north"].TARGETS:
                continue
            north.append(values)
            self.assertEqual(values["art_layer"], "Depth Props")
            self.assertIn(values["art_object_id"], created_ids)
        self.assertEqual(len(north), 55)

    def test_middle_workshop_uses_real_tiles_and_keeps_the_actor_lane_clear(self):
        middle = districts.DISTRICTS["middle"]
        furniture = next(
            layer for layer in self.source["layers"]
            if layer["name"] == "Interior Furniture L1"
        )
        left, top, right, bottom = middle.TARGET_BOUNDS["Workshop"]
        occupied = sum(
            bool(furniture["data"][y * self.source["width"] + x])
            for y in range(top, bottom) for x in range(left, right)
        )
        self.assertEqual(occupied, 85)
        self.assertTrue(all(
            not furniture["data"][y * self.source["width"] + x]
            for y in range(42, 48) for x in (18, 19)
        ))

    def test_middle_preserves_only_intentional_tile_backed_interactions(self):
        created_ids = {
            item["id"] for item in self.depth["objects"]
            if item.get("name", "").startswith("middle-")
        }
        interactions = next(
            layer for layer in self.authoring_group["layers"]
            if layer["name"] == "Interactions"
        )
        tile_backed = set()
        for item in interactions["objects"]:
            values = authoring.properties(item.get("properties"))
            if values.get("sector") not in districts.DISTRICTS["middle"].TARGETS:
                continue
            if values["art_layer"] == "Interior Furniture L1":
                tile_backed.add((values["sector"], values["interaction_type"]))
            else:
                self.assertEqual(values["art_layer"], "Depth Props")
                self.assertIn(values["art_object_id"], created_ids)
        self.assertEqual(tile_backed, {
            ("Workshop", "tool-storage"),
            ("Workshop", "work-machine"),
            ("Workshop", "workbench"),
        })

    def test_runtime_atlas_contains_every_registered_district_prop(self):
        frames = json.loads(RUNTIME_PROPS.read_text(encoding="utf-8"))["frames"]
        requested = {
            placement[4]
            for module in districts.DISTRICTS.values()
            for placement in module.PLACEMENTS
        }
        self.assertTrue(requested <= frames.keys())

    def test_complete_candidate_preserves_navigation(self):
        result = compiler.compile_semantics(tmj_path=districts.DEFAULT_MAP)
        self.assertEqual(result.stats["collision_mismatches"], 0)
        self.assertGreaterEqual(result.stats["connectivity_pct"], 98)
        self.assertEqual(result.stats["stances"], result.stats["objects"])


if __name__ == "__main__":
    unittest.main()
