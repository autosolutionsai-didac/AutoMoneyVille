"""Runtime and navigation gates for the complete Claudeville candidate."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tools.mapgen import author_claudeville_districts as districts
from tools.mapgen import compile_claudeville_semantics as compiler

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PROPS = (
    ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visual_candidates/"
    / "browser-modern-interiors-v16/runtime/props.json"
)
RUNTIME_ROOT = RUNTIME_PROPS.parent


class ClaudevilleCandidateRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(districts.DEFAULT_MAP.read_text(encoding="utf-8"))

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

    def test_candidate_excludes_the_legacy_interior_runtime_page(self):
        self.assertNotIn(
            "interiors",
            {Path(item["source"]).stem for item in self.source["tilesets"]},
        )
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
