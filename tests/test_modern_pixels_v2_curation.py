"""Safety and runtime-contract checks for the native-16 Claudeville art palette."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from tools.mapgen import curate_modern_pixels_v2

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPO_ROOT / "environment/frontend_server/static_dirs/assets/claudeville"
AUTHORING_CACHE = curate_modern_pixels_v2.DEFAULT_OUTPUT_ROOT
APPROVED_ROOT = ASSET_ROOT / "visual_candidates/browser-full-town-v7"


class ModernPixelsV2CurationTests(unittest.TestCase):
    def test_allowlist_rejects_free_rpg_preview_and_generator_inputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (
                "Modern_Interiors_Free_v2.2/tiles.png",
                "Modern_Exteriors_RPG_Maker_MV_v42.3/tiles.png",
                "modernexteriors-win/preview/tiles.png",
                "Portrait_Generator_1.5.0_Linux_Build/portrait.png",
            ):
                with self.subTest(relative=relative):
                    with self.assertRaisesRegex(curate_modern_pixels_v2.CurationError, "forbidden|approved"):
                        curate_modern_pixels_v2.validate_source_path(root, relative)

    @unittest.skipUnless(AUTHORING_CACHE.is_dir(), "licensed authoring cache not generated")
    def test_local_authoring_palette_is_native16_safe_and_not_distributable(self):
        atlas = json.loads((AUTHORING_CACHE / "atlas.json").read_text(encoding="utf-8"))
        catalog = json.loads((AUTHORING_CACHE / "catalog.json").read_text(encoding="utf-8"))
        credits = json.loads((AUTHORING_CACHE / "credits.json").read_text(encoding="utf-8"))
        self.assertEqual(atlas["mode"], "exteriors-office-native-16")
        self.assertEqual(atlas["tile_size"], 16)
        self.assertEqual({source["pack"] for source in atlas["sources"]}, set(curate_modern_pixels_v2.PACKS))
        self.assertTrue(all("free" not in source["relative_path"].lower() for source in atlas["sources"]))
        self.assertTrue(all("rpg" not in source["relative_path"].lower() for source in atlas["sources"]))
        self.assertTrue(all(max(page["width"], page["height"]) <= 4096 for page in atlas["atlases"]))
        self.assertEqual(len(catalog["props"]), len(curate_modern_pixels_v2.PROP_SPECS))
        self.assertTrue(all(prop["asset_key"].startswith("prop.") for prop in catalog["props"]))
        self.assertTrue(all(prop["anchor"] == [0.5, 1.0] for prop in catalog["props"]))
        self.assertTrue(all(prop["display_scale"] == 1 for prop in catalog["props"]))
        self.assertFalse(credits["distribution_allowed"])
        self.assertIn("Local authoring cache", credits["distribution_scope"])
        for page in atlas["atlases"]:
            with Image.open(AUTHORING_CACHE / page["image"]) as image:
                self.assertEqual(image.size, (page["width"], page["height"]))

    def test_committed_runtime_contains_only_referenced_tiles_and_credits(self):
        manifest = json.loads(
            (APPROVED_ROOT / "runtime/runtime_manifest.json").read_text(encoding="utf-8")
        )
        credits = json.loads((APPROVED_ROOT / "runtime/credits.json").read_text(encoding="utf-8"))
        world = json.loads((ASSET_ROOT / "world.json").read_text(encoding="utf-8"))
        runtime_tile_count = sum(page["tile_count"] for page in manifest["tilesets"])
        self.assertEqual(runtime_tile_count, 428)
        self.assertLess(runtime_tile_count, 500)
        self.assertEqual(manifest["credits"], "credits.json")
        self.assertEqual(
            {pack["name"] for pack in credits["packs"]},
            {"Modern Exteriors", "Modern Office Revamped"},
        )
        self.assertNotIn("free", json.dumps(credits).lower())
        self.assertEqual(
            world["credits_url"],
            "assets/claudeville/visual_candidates/browser-full-town-v7/runtime/credits.json",
        )
        for page in manifest["tilesets"]:
            with Image.open(APPROVED_ROOT / "runtime" / page["image"]) as image:
                self.assertLessEqual(max(image.size), 4096)

    def test_atlas_limit_is_enforced_before_allocation(self):
        limit = (curate_modern_pixels_v2.MAX_ATLAS_SIZE // curate_modern_pixels_v2.TILE_SIZE) ** 2
        with self.assertRaisesRegex(curate_modern_pixels_v2.CurationError, "4096x4096"):
            curate_modern_pixels_v2.atlas_dimensions(limit + 1)

    @unittest.skipUnless(AUTHORING_CACHE.is_dir(), "licensed authoring cache not generated")
    def test_semantic_catalog_uses_verified_wall_and_prop_sources(self):
        palette = json.loads((AUTHORING_CACHE / "palette.json").read_text(encoding="utf-8"))["tiles"]
        catalog = json.loads((AUTHORING_CACHE / "catalog.json").read_text(encoding="utf-8"))["props"]
        self.assertEqual(palette["terrain.river_water"]["asset_key"], "tile.exteriors_terrain.0448.0080")
        self.assertEqual(palette["interior.wall_horizontal"]["asset_key"], "tile.office_room_builder.0032.0016")
        self.assertEqual(palette["interior.wall_vertical_left"]["asset_key"], "tile.office_room_builder.0144.0016")
        self.assertEqual(palette["frontage.warm"]["asset_key"], "tile.exteriors_generic.0032.0160")
        self.assertFalse(any(key.startswith("interior.partition_") for key in palette))
        by_key = {prop["asset_key"]: prop for prop in catalog}
        expected_numbers = {
            "prop.office.notice_board": 116,
            "prop.office.whiteboard": 170,
            "prop.office.cash_register": 121,
            "prop.office.table_light": 190,
            "prop.office.table_walnut": 193,
            "prop.office.coffee_station": 318,
            "prop.office.waste_bin": 329,
        }
        for key, number in expected_numbers.items():
            self.assertTrue(by_key[key]["source"].endswith(f"Modern_Office_Singles_{number}.png"))
        self.assertIn("prop.cafe.coffee_kiosk", by_key)
        self.assertIn("prop.library.shelf_warm", by_key)
        self.assertIn("prop.community.stage_small", by_key)
        self.assertIn("prop.facade.door_open", by_key)


if __name__ == "__main__":
    unittest.main()
