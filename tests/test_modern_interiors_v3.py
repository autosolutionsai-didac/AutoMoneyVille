"""Focused safety and determinism tests for the paid Modern Interiors v3 profile."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from tools.mapgen import (
    curate_modern_interiors_v3,
    modern_interiors_v3_source,
    pack_modern_interiors_v3,
    tilemap_culler,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = modern_interiors_v3_source.DEFAULT_SOURCE_ROOT
HAS_PACK = SOURCE_ROOT.is_dir()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


@unittest.skipUnless(HAS_PACK, "paid moderninteriors-win source not installed")
class ModernInteriorsV3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.authoring = cls.root / "authoring"
        curate_modern_interiors_v3.curate_profile(SOURCE_ROOT, cls.authoring)
        cls.catalog = read_json(cls.authoring / "catalog.json")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_paid_native16_gate_matches_exact_selected_inventory(self):
        evidence = modern_interiors_v3_source.validate_pack(SOURCE_ROOT)
        self.assertEqual(evidence["profile"], "claudeville-modern-interiors-v3")
        self.assertEqual(evidence["license_sha256"], modern_interiors_v3_source.LICENSE_SHA256)
        self.assertEqual(evidence["selected_fingerprints"]["room-builder"]["file_count"], 9)
        self.assertEqual(evidence["selected_fingerprints"]["theme"]["file_count"], 16)
        self.assertEqual(evidence["selected_fingerprints"]["prop"]["file_count"], 2726)
        self.assertEqual(
            {tuple(item["size"]) for item in evidence["master_sources"]},
            {(256, 17024), (1216, 1808)},
        )

    def test_gate_rejects_free_old_scaled_preview_generator_and_zip_paths(self):
        rejected = (
            "Modern_Interiors_Free_v2.2/tiles.png",
            "1_Interiors/16x16/Old stuff/tiles.png",
            "1_Interiors/32x32/Interiors_32x32.png",
            "1_Interiors/48x48/Interiors_48x48.png",
            "1_Interiors/16x16/preview/tiles.png",
            "1_Interiors/16x16/generator/portrait.png",
            "1_Interiors/16x16/tiles.zip",
            "1_Interiors/16x16/Theme_Sorter/2_LivingRoom_16x16.png",
        )
        for relative in rejected:
            with self.subTest(relative=relative):
                with self.assertRaisesRegex(
                    modern_interiors_v3_source.ModernInteriorsV3Error,
                    "forbidden|unapproved",
                ):
                    modern_interiors_v3_source.validate_source_path(SOURCE_ROOT, relative)

    def test_catalog_exposes_black_shadow_tiled_sources_and_stable_keys(self):
        self.assertEqual(self.catalog["profile"], "claudeville-modern-interiors-v3")
        self.assertEqual(self.catalog["tile_size"], 16)
        self.assertEqual(len(self.catalog["tilesets"]), 25)
        self.assertEqual(len(self.catalog["tiles"]), 12001)
        self.assertEqual(len(self.catalog["props"]), 2721)
        self.assertEqual(self.catalog["omitted_empty_prop_count"], 5)
        required = {
            "theme.generic", "theme.living", "theme.bathroom", "theme.bedroom",
            "theme.kitchen", "theme.classroom_library", "theme.conference",
            "theme.grocery", "theme.japanese", "theme.condominium", "theme.ice_cream",
        }
        by_source = {item["source_id"]: item for item in self.catalog["tilesets"]}
        self.assertLessEqual(required, set(by_source))
        for source_id in required:
            record = by_source[source_id]
            self.assertEqual(record["shadow_variant"], "black")
            tsj = read_json(self.authoring / record["tileset"])
            self.assertEqual(tsj["tilecount"], tsj["columns"] * (tsj["imageheight"] // 16))
            properties = {item["name"]: item["value"] for item in tsj["properties"]}
            self.assertEqual(properties["claudeville_asset_profile"], modern_interiors_v3_source.PROFILE)
            self.assertEqual(properties["shadow_variant"], "black")
        for record in self.catalog["props"]:
            self.assertEqual(record["shadow_variant"], "black")
            self.assertIn("Theme_Sorter_Black_Shadow_Singles", record["source"])
            self.assertRegex(record["asset_key"], r"^prop\.interiors_v3\.[a-z_]+\.\d{4}$")

    def test_coordinate_and_numbered_contact_sheets_are_bounded_and_indexed(self):
        index = read_json(self.authoring / "selection_index.json")
        requested = {
            "living", "bathroom", "bedroom", "kitchen", "classroom_library",
            "conference", "grocery", "japanese", "condominium", "ice_cream",
        }
        self.assertLessEqual(requested, set(index["themes"]))
        for theme in requested:
            record = index["themes"][theme]
            self.assertEqual(record["shadow_variant"], "black")
            self.assertTrue(record["prop_key_pattern"].endswith(".NNNN"))
            for key in ("contact_sheet", "tile_contact_sheet"):
                path = self.authoring / record[key]
                self.assertTrue(path.is_file())
                with Image.open(path) as image:
                    self.assertLessEqual(max(image.size), 4096)
        for record in index["room_builder"].values():
            with Image.open(self.authoring / record["contact_sheet"]) as image:
                self.assertLessEqual(max(image.size), 4096)
        self.assertEqual(index["tiled_map_property"]["value"], modern_interiors_v3_source.PROFILE)
        self.assertIn("counters_and_queue", index["base_v15"]["office_groups"])
        self.assertTrue(index["base_v15"]["office_tileset"].endswith("/tiles/office.tsj"))
        with Image.open(self.authoring / index["base_v15"]["office_contact_sheet"]) as image:
            self.assertLessEqual(max(image.size), 4096)

    def test_prop_collection_is_bottom_aligned_and_source_referenced(self):
        profile = read_json(self.authoring / "profile.json")
        collection = read_json(self.authoring / profile["prop_collection"])
        self.assertEqual(collection["objectalignment"], "bottom")
        self.assertEqual(collection["tilecount"], len(self.catalog["props"]))
        self.assertEqual(len(collection["tiles"]), collection["tilecount"])
        self.assertTrue(all(item["image"] for item in collection["tiles"]))
        self.assertEqual(profile["extends"]["profile"], "claudeville-modern-pixels-v2")

    def test_runtime_packs_only_requested_assets_deterministically(self):
        floor = next(item["asset_key"] for item in self.catalog["tiles"] if item["source_id"] == "room.floors")
        kitchen_tile = next(item["asset_key"] for item in self.catalog["tiles"] if item["source_id"] == "theme.kitchen")
        living_prop = next(item["asset_key"] for item in self.catalog["props"] if item["theme"] == "living")
        kitchen_prop = next(item["asset_key"] for item in self.catalog["props"] if item["theme"] == "kitchen")
        request = self.root / "used_assets.json"
        write_json(request, {
            "profile": modern_interiors_v3_source.PROFILE,
            "prop_asset_keys": [kitchen_prop, living_prop],
            "tile_asset_keys": [kitchen_tile, floor],
        })
        first, second = self.root / "runtime-first", self.root / "runtime-second"
        manifest = pack_modern_interiors_v3.pack_runtime(
            request, first, source_root=SOURCE_ROOT, authoring_root=self.authoring
        )
        pack_modern_interiors_v3.pack_runtime(
            request, second, source_root=SOURCE_ROOT, authoring_root=self.authoring
        )
        self.assertEqual(set(manifest["tile_asset_remap"]), {floor, kitchen_tile})
        self.assertEqual(set(manifest["prop_asset_remap"]), {living_prop, kitchen_prop})
        self.assertEqual(sum(page["tile_count"] for page in manifest["tile_pages"]), 2)
        self.assertEqual(sum(page["asset_count"] for page in manifest["prop_pages"]), 2)
        self.assertEqual(tree_hashes(first), tree_hashes(second))
        for page in manifest["tile_pages"] + manifest["prop_pages"]:
            with Image.open(first / page["image"]) as image:
                self.assertLessEqual(max(image.size), 4096)

    def test_unknown_runtime_asset_fails_before_output(self):
        request = self.root / "unknown_assets.json"
        write_json(request, {
            "profile": modern_interiors_v3_source.PROFILE,
            "prop_asset_keys": ["prop.interiors_v3.kitchen.9999"],
            "tile_asset_keys": [],
        })
        output = self.root / "runtime-unknown"
        with self.assertRaisesRegex(pack_modern_interiors_v3.RuntimePackError, "unknown prop"):
            pack_modern_interiors_v3.pack_runtime(
                request, output, source_root=SOURCE_ROOT, authoring_root=self.authoring
            )
        self.assertFalse(output.exists())

    @unittest.skipUnless(
        tilemap_culler.DEFAULT_OUTPUT_ROOT.is_dir(),
        "base v15 authoring cache not generated",
    )
    def test_town_culler_merges_selected_v3_props_into_one_runtime_atlas(self):
        source_path = (
            REPO_ROOT
            / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
            / "claudeville_full_town_v2.tmj"
        )
        town = read_json(source_path)
        record = next(
            item for item in self.catalog["props"]
            if item["asset_key"] == "prop.interiors_v3.living.0013"
        )
        layer = next(item for item in town["layers"] if item["name"] == "Depth Props")
        layer["objects"].append({
            "id": town["nextobjectid"],
            "name": "v3-prop-test",
            "type": "",
            "x": 384,
            "y": 384,
            "width": record["native_size"][0],
            "height": record["native_size"][1],
            "rotation": 0,
            "visible": True,
            "properties": [
                {"name": "anchor_x", "type": "float", "value": 0.5},
                {"name": "anchor_y", "type": "float", "value": 1.0},
                {"name": "asset_key", "type": "string", "value": record["asset_key"]},
                {"name": "display_scale", "type": "float", "value": 1.0},
            ],
        })
        tmj = self.root / "town-with-v3-prop.tmj"
        write_json(tmj, town)
        runtime = self.root / "town-runtime"
        result = tilemap_culler.cull_runtime_tilesets(
            tmj,
            runtime,
            interiors_v3_authoring_root=self.authoring,
            interiors_v3_source_root=SOURCE_ROOT,
        )
        self.assertIn(record["asset_key"], result["props"]["asset_keys"])
        self.assertIn(record["asset_key"], read_json(runtime / "props.json")["frames"])
        with Image.open(runtime / "props.png") as atlas:
            self.assertLessEqual(max(atlas.size), 4096)
        credits = read_json(runtime / "credits.json")
        self.assertIn(
            "claudeville-modern-interiors-v3",
            {item.get("profile") for item in credits["packs"]},
        )

    def test_complete_candidate_runtime_rebuild_is_deterministic_and_used_only(self):
        source = (
            REPO_ROOT
            / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
            / "claudeville_modern_interiors_v3.tmj"
        )
        payload = read_json(source)
        self.assertNotIn(
            "interiors",
            {Path(item["source"]).stem for item in payload["tilesets"]},
        )
        first, second = self.root / "candidate-runtime-a", self.root / "candidate-runtime-b"
        kwargs = {
            "interiors_v3_authoring_root": self.authoring,
            "interiors_v3_source_root": SOURCE_ROOT,
        }
        manifest = tilemap_culler.cull_runtime_tilesets(source, first, **kwargs)
        tilemap_culler.cull_runtime_tilesets(source, second, **kwargs)
        self.assertEqual(tree_hashes(first), tree_hashes(second))
        self.assertEqual(
            [item["key"] for item in manifest["tilesets"]],
            ["terrain", "town", "office", "interiors_v3"],
        )
        credits = read_json(first / "credits.json")
        serialized = json.dumps(credits)
        self.assertNotIn("Interiors_32x32_full.png", serialized)
        self.assertEqual(
            sum(item.get("profile") == modern_interiors_v3_source.PROFILE
                for item in credits["packs"]),
            1,
        )

    def test_runtime_atlas_limit_is_enforced_before_allocation(self):
        with self.assertRaisesRegex(pack_modern_interiors_v3.RuntimePackError, "65,536"):
            pack_modern_interiors_v3._atlas_dimensions(
                pack_modern_interiors_v3.MAX_TILES_PER_PAGE + 1
            )


if __name__ == "__main__":
    unittest.main()
