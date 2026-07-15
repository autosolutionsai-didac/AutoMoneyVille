"""Contract tests for Claudeville's hand-authored native-16px Tiled world."""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

from tools.mapgen import build_tilemap, curate_modern_pixels_v2

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = REPO_ROOT / "environment/frontend_server/static_dirs/assets/claudeville"
AUTHORING_ROOT = build_tilemap.AUTHORING_ROOT
APPROVED_ROOT = ASSET_ROOT / "visual_candidates/browser-full-town-interiors-v8"
SOURCE_MAP = build_tilemap.AUTHORING_MAP
COLLISION = ASSET_ROOT / "matrix/maze/collision_maze.csv"
SPEC = REPO_ROOT / "tools/mapgen/town_spec.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class HandAuthoredClaudevilleTests(unittest.TestCase):
    maxDiff = None

    def test_authoring_source_is_native_16px_and_has_only_declared_layers(self):
        source = load_json(SOURCE_MAP)
        self.assertEqual(
            (source["width"], source["height"], source["tilewidth"], source["tileheight"]),
            (176, 96, 16, 16),
        )
        self.assertFalse(source["infinite"])
        self.assertEqual(source["orientation"], "orthogonal")
        self.assertEqual(
            [layer["name"] for layer in source["layers"]],
            list(build_tilemap.MAP_LAYER_ORDER),
        )
        self.assertEqual(
            {Path(tileset["source"]).stem for tileset in source["tilesets"]},
            {"terrain", "town", "office", "interiors"},
        )
        self.assertEqual(
            {property["name"]: property["value"] for property in source["properties"]},
            {
                "authoring_style": "hand-authored-modern-pixels",
                "collision_authority": "../matrix/maze/collision_maze.csv",
                "logical_grid": "88x48@32",
                "visual_grid": "176x96@16",
                "world_pixel_size": "2816x1536",
            },
        )
        object_layers = [layer for layer in source["layers"] if layer["type"] == "objectgroup"]
        self.assertEqual([layer["name"] for layer in object_layers], list(build_tilemap.OBJECT_LAYERS))
        self.assertGreaterEqual(sum(len(layer["objects"]) for layer in object_layers), 100)
        for layer in object_layers:
            for obj in layer["objects"]:
                with self.subTest(layer=layer["name"], object=obj.get("name")):
                    self.assertNotIn("text", obj)
                    properties = {item["name"]: item.get("value") for item in obj["properties"]}
                    self.assertRegex(properties["asset_key"], r"^prop\.[A-Za-z0-9_.-]+$")
                    display_scale = properties.get("display_scale")
                    self.assertIsInstance(display_scale, (int, float))
                    self.assertNotIsInstance(display_scale, bool)
                    self.assertGreater(display_scale, 0)
                    self.assertLessEqual(display_scale, 4)

    @unittest.skipUnless(AUTHORING_ROOT.is_dir(), "licensed authoring cache not generated")
    def test_local_authoring_cache_is_licensed_native16_and_not_distributable(self):
        atlas = load_json(AUTHORING_ROOT / "atlas.json")
        catalog = load_json(AUTHORING_ROOT / "catalog.json")
        credits = load_json(AUTHORING_ROOT / "credits.json")
        self.assertEqual(atlas["mode"], "exteriors-office-interiors-native-16")
        self.assertEqual(atlas["tile_size"], 16)
        self.assertEqual({source["pack"] for source in atlas["sources"]}, {
            "Modern Exteriors", "Modern Office Revamped", "Modern Interiors",
        })
        self.assertNotIn("modern_interiors_free", json.dumps(atlas).lower())
        self.assertNotIn("rpg", json.dumps(atlas).lower())
        self.assertEqual(len(catalog["props"]), len(curate_modern_pixels_v2.PROP_SPECS))
        self.assertTrue(all(prop["display_scale"] == 1 for prop in catalog["props"]))
        self.assertFalse(credits["distribution_allowed"])
        self.assertIn("Local authoring cache", credits["distribution_scope"])
        for page in atlas["atlases"]:
            with self.subTest(page=page["key"]), Image.open(AUTHORING_ROOT / page["image"]) as image:
                self.assertEqual(image.size, (page["width"], page["height"]))
                self.assertLessEqual(max(image.size), 4096)

    def test_compiler_expands_authoritative_collision_and_emits_compact_candidate(self):
        candidate = load_json(APPROVED_ROOT / "claudeville_v2.json")
        manifest = load_json(APPROVED_ROOT / "world.json")
        self.assertEqual(
            (candidate["width"], candidate["height"], candidate["tilewidth"], candidate["tileheight"]),
            (176, 96, 16, 16),
        )
        self.assertEqual(candidate["width"] * candidate["tilewidth"], 2816)
        self.assertEqual(candidate["height"] * candidate["tileheight"], 1536)
        self.assertEqual([layer["name"] for layer in candidate["layers"]], list(build_tilemap.MAP_LAYER_ORDER))
        self.assertEqual(manifest, load_json(ASSET_ROOT / "world.json"))
        self.assertEqual(manifest["version"], 2)
        self.assertNotIn("scene_image_url", manifest)
        self.assertEqual(manifest["visual_dimensions"], {"width": 176, "height": 96, "tile_size": 16})
        self.assertEqual(
            manifest["candidate_source_sha256"], build_tilemap.stable_source_sha256(SOURCE_MAP)
        )
        self.assertEqual(manifest["candidate_source_url"], build_tilemap._static_url(SOURCE_MAP))
        self.assertEqual(manifest["layer_order"], list(build_tilemap.MAP_LAYER_ORDER))
        self.assertEqual(
            manifest["address_alias_manifest_url"],
            "assets/claudeville/legacy_address_aliases.v1.json",
        )
        self.assertNotIn("aliases", manifest)
        self.assertEqual([entry["name"] for entry in manifest["object_layers"]], list(build_tilemap.OBJECT_LAYERS))

        blocked = [token.strip() == "32125" for token in COLLISION.read_text(encoding="utf-8").split(",")]
        collisions = next(layer["data"] for layer in candidate["layers"] if layer["name"] == "Collisions")
        for y in range(48):
            for x in range(88):
                values = [
                    collisions[(y * 2 + row) * 176 + x * 2 + column]
                    for row in range(2) for column in range(2)
                ]
                self.assertEqual({value != 0 for value in values}, {blocked[y * 88 + x]})
        for tileset in candidate["tilesets"]:
            image = APPROVED_ROOT / tileset["image"]
            with self.subTest(runtime_image=image), Image.open(image) as texture:
                self.assertLessEqual(max(texture.size), 4096)
        with Image.open(APPROVED_ROOT / "claudeville_v2_preview.png") as preview:
            self.assertEqual(preview.size, (2816, 1536))

    def test_candidate_build_is_deterministic_and_promotion_needs_matching_review_hash(self):
        manifest_path = APPROVED_ROOT / "world.json"
        source_sha = build_tilemap.stable_source_sha256(SOURCE_MAP)
        self.assertEqual(load_json(manifest_path), load_json(ASSET_ROOT / "world.json"))
        with self.assertRaisesRegex(build_tilemap.TilemapError, "approval hash"):
            build_tilemap.promote_candidate(manifest_path, approved_source_sha256="not-reviewed")
        with TemporaryDirectory() as temporary:
            promoted = Path(temporary) / "promoted-world.json"
            with patch.object(build_tilemap, "WORLD_MANIFEST_PATH", promoted):
                self.assertEqual(
                    build_tilemap.promote_candidate(
                        manifest_path, approved_source_sha256=source_sha
                    ),
                    promoted,
                )
            self.assertEqual(load_json(promoted), load_json(manifest_path))

    def test_promotion_rejects_tampered_layers_assets_source_and_collision(self):
        candidate_parent = ASSET_ROOT / "visual_candidates"
        with TemporaryDirectory(prefix="test-v2-gate-", dir=candidate_parent) as temporary:
            candidate_root = Path(temporary) / "candidate"
            shutil.copytree(APPROVED_ROOT, candidate_root)
            old_prefix = build_tilemap._static_url(APPROVED_ROOT)
            new_prefix = build_tilemap._static_url(candidate_root)
            original = json.loads(
                json.dumps(load_json(candidate_root / "world.json")).replace(old_prefix, new_prefix)
            )
            source_sha = original["candidate_source_sha256"]

            def rejected(manifest: dict, message: str):
                path = Path(temporary) / "tampered-world.json"
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(build_tilemap.TilemapError, message):
                    build_tilemap.promote_candidate(path, approved_source_sha256=source_sha)

            bad_layers = dict(original)
            bad_layers["layer_order"] = bad_layers["layer_order"][:-1]
            rejected(bad_layers, "13-layer")

            bad_asset = json.loads(json.dumps(original))
            bad_asset["tilesets"][0]["image_url"] = "assets/claudeville/legacy_address_aliases.v1.json"
            rejected(bad_asset, "escapes")

            bad_source = dict(original)
            bad_source["candidate_source_url"] = build_tilemap._static_url(
                SOURCE_MAP.with_name("claudeville_bg.png")
            )
            rejected(bad_source, "reviewed hash")

            bad_gid_map = load_json(candidate_root / "claudeville_v2.json")
            furniture = next(
                layer for layer in bad_gid_map["layers"]
                if layer["name"] == "Interior Furniture L1"
            )
            furniture["data"][next(index for index, gid in enumerate(furniture["data"]) if gid)] = 999999
            bad_gid_path = candidate_root / "tampered-gid-map.json"
            bad_gid_path.write_text(json.dumps(bad_gid_map), encoding="utf-8")
            bad_gid = dict(original)
            bad_gid["tilemap_url"] = build_tilemap._static_url(bad_gid_path)
            rejected(bad_gid, "unresolved GID 999999")

            bad_prop_map = load_json(candidate_root / "claudeville_v2.json")
            depth_objects = next(
                layer["objects"] for layer in bad_prop_map["layers"]
                if layer["name"] == "Depth Props"
            )
            asset_property = next(
                item for item in depth_objects[0]["properties"] if item["name"] == "asset_key"
            )
            asset_property["value"] = "prop.missing.tampered"
            bad_prop_path = candidate_root / "tampered-prop-map.json"
            bad_prop_path.write_text(json.dumps(bad_prop_map), encoding="utf-8")
            bad_prop = dict(original)
            bad_prop["tilemap_url"] = build_tilemap._static_url(bad_prop_path)
            rejected(bad_prop, "do not resolve")

            tampered_map = load_json(candidate_root / "claudeville_v2.json")
            collisions = next(layer for layer in tampered_map["layers"] if layer["name"] == "Collisions")
            collisions["data"][0] = 0 if collisions["data"][0] else 1
            tampered_map_path = candidate_root / "tampered-map.json"
            tampered_map_path.write_text(json.dumps(tampered_map), encoding="utf-8")
            bad_collision = dict(original)
            bad_collision["tilemap_url"] = build_tilemap._static_url(tampered_map_path)
            rejected(bad_collision, "collision has 1 canonical mismatch")

    def test_active_world_spec_retains_all_english_public_destinations(self):
        spec = load_json(SPEC)
        sectors = {sector["name"] for sector in spec["sectors"]}
        self.assertEqual(sectors, {
            "Bank", "Home 1", "University", "Agent Academy", "Market", "Post Office",
            "Workshop", "Community Center", "Central Plaza", "Claudeville Cafe", "Library",
            "Home 2", "Home 3", "Home 4", "Home 5", "Home 6", "Town Hall", "Home 7",
            "Home 8", "Home 9", "Home 10",
        })


if __name__ == "__main__":
    unittest.main()
