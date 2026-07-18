"""Runtime and navigation gates for the complete Claudeville candidate."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.mapgen import claudeville_reference_bank as reference_bank
from tools.mapgen import claudeville_reference_collision as reference_collision
from tools.mapgen import claudeville_reference_middle as reference_middle
from tools.mapgen import claudeville_semantic_graph as semantic_graph
from tools.mapgen import claudeville_tiled_authoring as authoring
from tools.mapgen import compile_claudeville_semantics as compiler

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PROPS = (
    ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visual_candidates/"
    / "browser-target-v45/runtime/props.json"
)
RUNTIME_ROOT = RUNTIME_PROPS.parent
SOURCE = (
    ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
    / "claudeville_target_v45.tmj"
)


class ClaudevilleCandidateRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(SOURCE.read_text(encoding="utf-8"))

    def test_runtime_atlas_contains_every_registered_district_prop(self):
        frames = json.loads(RUNTIME_PROPS.read_text(encoding="utf-8"))["frames"]
        requested = {
            authoring.properties(item.get("properties"))["asset_key"]
            for layer in self.source["layers"]
            if layer.get("type") == "objectgroup"
            for item in layer.get("objects", [])
            if authoring.properties(item.get("properties")).get("asset_key")
        }
        self.assertTrue(requested <= frames.keys())

    def test_complete_candidate_preserves_navigation(self):
        source = json.loads(json.dumps(self.source))
        spec = compiler._read_json(compiler.SPEC_PATH)
        result = authoring.compile_authoring(
            source, spec, semantic_graph.read_collision(compiler.COLLISION_PATH),
        )
        self.assertEqual(result.stats["collision_mismatches"], 0)
        self.assertEqual(result.stats["connectivity_pct"], 100)
        self.assertEqual(result.stats["stances"], result.stats["objects"])

    def test_every_visible_wall_and_large_workshop_machine_is_solid(self):
        collision = reference_collision.compile_collision(self.source)
        walls = next(
            layer for layer in self.source["layers"] if layer["name"] == "Wall"
        )["data"]
        visible_wall_cells = {
            (x, y)
            for y in range(48)
            for x in range(88)
            if any(
                walls[(2 * y + dy) * 176 + 2 * x + dx]
                for dy in (0, 1) for dx in (0, 1)
            )
        }
        self.assertTrue(visible_wall_cells)
        self.assertTrue(all(collision[y][x] for x, y in visible_wall_cells))
        self.assertTrue(all(
            collision[y][x] for x, y in reference_middle.WORKSHOP_COLLISION_BLOCKS
        ))
        self.assertTrue(all(
            collision[y][x] for x, y in reference_bank.BANK_COLLISION_BLOCKS
        ))

    def test_every_solid_prop_footprint_is_blocked(self):
        collision = reference_collision.compile_collision(self.source)
        blocked = {
            (x, y)
            for y, row in enumerate(collision)
            for x, value in enumerate(row)
            if value
        }
        solid = set(reference_collision._solid_prop_cells(self.source))
        _zones, _required, nonblocking, clear = reference_collision._authoring(
            self.source
        )
        self.assertTrue(solid)
        self.assertFalse(solid & clear)
        self.assertFalse(solid & nonblocking)
        self.assertEqual(solid - blocked, set())

    def test_every_interaction_stance_is_clear_and_policy_is_respected(self):
        collision = reference_collision.compile_collision(self.source)
        group = next(
            layer for layer in self.source["layers"]
            if layer["name"] == authoring.GROUP_NAME
        )
        interactions = next(
            layer for layer in group["layers"] if layer["name"] == "Interactions"
        )["objects"]
        for item in interactions:
            values = authoring.properties(item.get("properties"))
            cell = int(item["x"] // 32), int(item["y"] // 32)
            stance = values["stance_x"], values["stance_y"]
            with self.subTest(semantic_id=values["semantic_id"]):
                self.assertFalse(collision[stance[1]][stance[0]])
                expected = values["blocker_policy"] == "require-blocked"
                self.assertEqual(collision[cell[1]][cell[0]], expected)

    def test_collision_uses_floor_footprints_not_transparent_sprite_height(self):
        def prop(kind: str) -> dict:
            return {
                "x": 64, "y": 96, "width": 64, "height": 64,
                "properties": [{"name": "semantic_type", "value": kind}],
            }

        self.assertEqual(reference_collision._object_cells(prop("terminal")), {(2, 3)})
        self.assertEqual(reference_collision._object_cells(prop("bed")), {
            (2, 2), (3, 2), (2, 3), (3, 3),
        })
        scaled = prop("bed")
        scaled["properties"].append({"name": "display_scale", "value": 1.5})
        self.assertEqual(reference_collision._object_cells(scaled), {
            (1, 1), (2, 1), (3, 1), (1, 2), (2, 2), (3, 2),
            (1, 3), (2, 3), (3, 3),
        })

    def test_candidate_excludes_the_legacy_interior_runtime_page(self):
        self.assertNotIn("interiors", {
            Path(item["source"]).stem for item in self.source["tilesets"]
        })
        manifest = json.loads(
            (RUNTIME_ROOT / "runtime_manifest.json").read_text(encoding="utf-8")
        )
        runtime_keys = {item["key"] for item in manifest["tilesets"]}
        self.assertIn("interiors_v3", runtime_keys)
        self.assertNotIn("interiors", runtime_keys)
        self.assertFalse((RUNTIME_ROOT / "tiles/interiors.png").exists())
        self.assertFalse((RUNTIME_ROOT / "tiles/interiors.tsj").exists())


if __name__ == "__main__":
    unittest.main()
