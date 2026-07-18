"""Focused contract tests for the Claudeville v2 authoring-palette culler."""

from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

from tools.mapgen import tiled_gid, tilemap_culler


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class TilemapCullerTests(unittest.TestCase):
    def _authoring_root(self, root: Path) -> Path:
        authoring = root / "authoring"
        tiles = authoring / "tiles"
        tiles.mkdir(parents=True)
        terrain = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
        terrain.paste(Image.new("RGBA", (16, 16), (20, 90, 50, 255)), (0, 0))
        terrain.paste(Image.new("RGBA", (16, 16), (40, 100, 150, 255)), (16, 0))
        terrain.save(tiles / "terrain.png")
        Image.new("RGBA", (16, 16), (160, 90, 60, 255)).save(
            tiles / "interiors.png"
        )
        write_json(authoring / "atlas.json", {
            "atlases": [
                {"key": "terrain", "image": "tiles/terrain.png", "columns": 2},
                {"key": "interiors", "image": "tiles/interiors.png", "columns": 1},
            ],
            "sources": [
                {"source_id": "test_terrain", "atlas": "terrain", "pack": "Test Pack"},
                {"source_id": "test_interiors", "atlas": "interiors", "pack": "Legacy Pack"},
            ],
        })
        write_json(authoring / "credits.json", {
            "packs": [
                {"name": "Test Pack", "license_sha256": "a" * 64},
                {"name": "Legacy Pack", "license_sha256": "b" * 64},
            ],
        })
        write_json(authoring / "tiles.json", {"tiles": [
            {"asset_key": "tile.test.grass", "atlas": "terrain", "atlas_index": 0,
             "source_id": "test_terrain"},
            {"asset_key": "tile.test.water", "atlas": "terrain", "atlas_index": 1,
             "source_id": "test_terrain"},
            {
                "asset_key": "tile.interiors.full.r0000.c00",
                "atlas": "interiors",
                "atlas_index": 0,
                "source_id": "test_interiors",
            },
        ]})
        write_json(authoring / "catalog.json", {"props": [
            {"asset_key": "prop.plaza.fountain", "pack": "Test Pack"},
            {"asset_key": "prop.street.bench", "pack": "Test Pack"},
        ]})
        props = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
        props.paste(Image.new("RGBA", (16, 16), (240, 210, 90, 255)), (0, 0))
        props.paste(Image.new("RGBA", (16, 16), (120, 100, 70, 255)), (16, 0))
        props.save(authoring / "props.png")
        write_json(authoring / "props.json", {"frames": {
            "prop.plaza.fountain": {"frame": {"x": 0, "y": 0, "w": 16, "h": 16}},
            "prop.street.bench": {"frame": {"x": 16, "y": 0, "w": 16, "h": 16}},
        }})
        return authoring

    def _tmj(self, root: Path, asset_key: str = "prop.plaza.fountain") -> Path:
        data = [0] * (176 * 96)
        data[:3] = [1, 2, 1]
        source = root / "town.tmj"
        write_json(source, {
            "width": 176, "height": 96, "tilewidth": 16, "tileheight": 16, "infinite": False,
            "tilesets": [{"firstgid": 1, "source": "terrain.tsj"}],
            "layers": [
                {"type": "tilelayer", "data": data},
                {"type": "objectgroup", "objects": [{"properties": [{"name": "asset_key", "value": asset_key}]}]},
            ],
        })
        return source

    def test_culls_only_referenced_tiles_and_props_deterministically(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            source = self._tmj(root)
            first, second = root / "first", root / "second"
            manifest = tilemap_culler.cull_runtime_tilesets(source, first, authoring_root=authoring)
            tilemap_culler.cull_runtime_tilesets(source, second, authoring_root=authoring)
            self.assertEqual(manifest["tile_gid_remap"], {"1": 1, "2": 2})
            self.assertEqual(manifest["tile_gid_clear_mask"], tiled_gid.ALL_FLAG_MASK)
            self.assertEqual(
                manifest["tile_gid_flip_mask"], tiled_gid.ORTHOGONAL_FLIP_MASK
            )
            self.assertEqual(manifest["props"]["asset_keys"], ["prop.plaza.fountain"])
            self.assertEqual(manifest["tilesets"][0]["tile_count"], 2)
            props = json.loads((first / "props.json").read_text(encoding="utf-8"))
            self.assertEqual(set(props["frames"]), {"prop.plaza.fountain"})
            for relative in ("runtime_manifest.json", "tiles/terrain.png", "props.png", "props.json"):
                self.assertEqual(
                    hashlib.sha256((first / relative).read_bytes()).hexdigest(),
                    hashlib.sha256((second / relative).read_bytes()).hexdigest(),
                    relative,
                )
            self.assertEqual(manifest["credits"], "credits.json")
            credits = json.loads((first / "credits.json").read_text(encoding="utf-8"))
            self.assertEqual([item["name"] for item in credits["packs"]], ["Test Pack"])

    def test_unknown_object_asset_fails_before_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            with self.assertRaisesRegex(tilemap_culler.CullError, "missing from props"):
                tilemap_culler.cull_runtime_tilesets(
                    self._tmj(root, "prop.unlicensed.missing"), root / "runtime", authoring_root=authoring
                )
            self.assertFalse((root / "runtime").exists())

    def test_culls_all_allowlisted_design_stamps_with_hash_and_credit_evidence(self):
        cases = (
            ("prop.design.academy_gym", (304, 240), "Modern Interiors"),
            ("prop.design.bank_office", (192, 173), "Modern Office Revamped"),
            ("prop.design.frontage.home_japanese", (192, 80), "Modern Exteriors"),
            ("prop.design.frontage.home_modern", (192, 80), "Modern Exteriors"),
            ("prop.design.frontage.home_one_story", (192, 80), "Modern Exteriors"),
            ("prop.design.frontage.home_terraced_1", (192, 80), "Modern Exteriors"),
            ("prop.design.frontage.home_terraced_3", (192, 80), "Modern Exteriors"),
            ("prop.design.frontage.home_terraced_4", (192, 80), "Modern Exteriors"),
            ("prop.design.frontage.home_terraced_5", (192, 80), "Modern Exteriors"),
            ("prop.design.frontage.home_villa_1", (144, 80), "Modern Exteriors"),
            ("prop.design.frontage.home_villa_3", (144, 80), "Modern Exteriors"),
            ("prop.design.home_cluster.generic_ne", (112, 112), "Modern Interiors"),
            ("prop.design.home_cluster.generic_nw", (112, 112), "Modern Interiors"),
            ("prop.design.home_cluster.generic_south", (160, 118), "Modern Interiors"),
            ("prop.design.home_cluster.japanese_ne", (128, 112), "Modern Interiors"),
            ("prop.design.home_cluster.japanese_nw", (128, 112), "Modern Interiors"),
            ("prop.design.home_cluster.japanese_se", (144, 112), "Modern Interiors"),
            ("prop.design.home_cluster.japanese_sw", (144, 112), "Modern Interiors"),
            ("prop.design.home_generic", (224, 214), "Modern Interiors"),
            ("prop.design.home_japanese", (272, 202), "Modern Interiors"),
            ("prop.design.university_lab", (221, 253), "Modern Office Revamped"),
            ("prop.design.university_lab_main", (221, 157), "Modern Office Revamped"),
            ("prop.design.university_lounge", (176, 80), "Modern Office Revamped"),
        )
        catalog = tilemap_culler.prop_atlas.DEFAULT_DESIGN_STAMP_ROOT / "catalog.json"
        catalog_bytes = catalog.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        expected_catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
        for asset_key, size, pack in cases:
            with self.subTest(asset_key=asset_key), TemporaryDirectory() as tmp:
                root = Path(tmp)
                authoring = self._authoring_root(root)
                runtime = root / "runtime"
                manifest = tilemap_culler.cull_runtime_tilesets(
                    self._tmj(root, asset_key), runtime, authoring_root=authoring
                )
                self.assertEqual(
                    manifest["design_stamp_catalog_sha256"], expected_catalog_hash
                )
                self.assertEqual(manifest["props"]["asset_keys"], [asset_key])
                frames = json.loads(
                    (runtime / "props.json").read_text(encoding="utf-8")
                )["frames"]
                self.assertEqual(
                    (frames[asset_key]["frame"]["w"], frames[asset_key]["frame"]["h"]),
                    size,
                )
                credits = json.loads(
                    (runtime / "credits.json").read_text(encoding="utf-8")
                )
                self.assertIn(pack, {item["name"] for item in credits["packs"]})
                if asset_key == "prop.design.bank_office":
                    second = root / "runtime-second"
                    tilemap_culler.cull_runtime_tilesets(
                        root / "town.tmj", second, authoring_root=authoring
                    )
                    for relative in ("props.png", "props.json", "runtime_manifest.json"):
                        self.assertEqual(
                            (runtime / relative).read_bytes(), (second / relative).read_bytes()
                        )

    def test_culls_all_graystone_frontages_in_one_runtime_atlas(self):
        expected = {
            "prop.design.frontage.bank_graystone": (352, 48),
            "prop.design.frontage.agent_academy_graystone": (368, 48),
            "prop.design.frontage.workshop_graystone": (352, 48),
            "prop.design.frontage.community_center_graystone": (192, 48),
            "prop.design.frontage.library_graystone": (400, 48),
            "prop.design.frontage.home_1_graystone": (336, 48),
            "prop.design.frontage.home_2_graystone": (208, 48),
            "prop.design.frontage.home_3_graystone": (192, 48),
            "prop.design.frontage.home_4_graystone": (144, 48),
            "prop.design.frontage.home_5_graystone": (160, 48),
            "prop.design.frontage.home_7_graystone": (192, 48),
            "prop.design.frontage.home_8_graystone": (208, 48),
            "prop.design.frontage.home_9_graystone": (192, 48),
            "prop.design.frontage.home_10_graystone": (192, 48),
        }
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._tmj(root)
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["layers"][1]["objects"] = [
                {"properties": [{"name": "asset_key", "value": key}]}
                for key in expected
            ]
            write_json(source, payload)
            runtime = root / "runtime"
            manifest = tilemap_culler.cull_runtime_tilesets(
                source, runtime, authoring_root=self._authoring_root(root)
            )
            self.assertEqual(manifest["props"]["asset_keys"], sorted(expected))
            frames = json.loads(
                (runtime / "props.json").read_text(encoding="utf-8")
            )["frames"]
            self.assertEqual(
                {
                    key: (record["frame"]["w"], record["frame"]["h"])
                    for key, record in frames.items()
                },
                expected,
            )

    def test_rejects_unknown_or_tampered_design_stamps_before_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            with self.assertRaisesRegex(tilemap_culler.CullError, "unapproved"):
                tilemap_culler.cull_runtime_tilesets(
                    self._tmj(root, "prop.design.unreviewed"), root / "unknown",
                    authoring_root=authoring,
                )
            stamp_root = root / "stamps"
            shutil.copytree(tilemap_culler.prop_atlas.DEFAULT_DESIGN_STAMP_ROOT, stamp_root)
            with self.assertRaisesRegex(tilemap_culler.CullError, "remain separate"):
                tilemap_culler.cull_runtime_tilesets(
                    self._tmj(root, "prop.design.bank_office"), stamp_root / "runtime",
                    authoring_root=authoring, design_stamp_root=stamp_root,
                )
            stamp = stamp_root / "bank_office.png"
            stamp.write_bytes(stamp.read_bytes() + b"tampered")
            with self.assertRaisesRegex(tilemap_culler.CullError, "hash changed"):
                tilemap_culler.cull_runtime_tilesets(
                    self._tmj(root, "prop.design.bank_office"), root / "tampered",
                    authoring_root=authoring, design_stamp_root=stamp_root,
                )
            self.assertFalse((root / "unknown").exists())
            self.assertFalse((root / "tampered").exists())

    def test_design_stamp_rejects_tampered_catalog_license_evidence(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            stamp_root = root / "stamps"
            shutil.copytree(tilemap_culler.prop_atlas.DEFAULT_DESIGN_STAMP_ROOT, stamp_root)
            catalog_path = stamp_root / "catalog.json"
            catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
            catalog["pack_credits"][0]["license_sha256"] = "f" * 64
            write_json(catalog_path, catalog)
            with self.assertRaisesRegex(tilemap_culler.CullError, "license evidence changed"):
                tilemap_culler.cull_runtime_tilesets(
                    self._tmj(root, "prop.design.bank_office"), root / "runtime",
                    authoring_root=authoring, design_stamp_root=stamp_root,
                )
            self.assertFalse((root / "runtime").exists())

    def test_v3_credit_supersedes_same_named_design_stamp_credit(self):
        v3_credit = {
            "name": "Modern Interiors",
            "profile": tilemap_culler.modern_interiors_v3_source.PROFILE,
        }
        credits = tilemap_culler.runtime_support.used_pack_credits(
            {"packs": [{"name": "Modern Interiors", "license_sha256": "a" * 64}]},
            {"sources": []},
            {"props": [{
                "asset_key": "prop.design.home_japanese",
                "pack": "Modern Interiors",
            }]},
            [{"atlas": "interiors_v3"}],
            ["prop.design.home_japanese"],
            v3_credit,
        )
        self.assertEqual(credits, [v3_credit])

    def test_v2_only_map_does_not_require_local_v3_sources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = tilemap_culler.cull_runtime_tilesets(
                self._tmj(root), root / "runtime",
                authoring_root=self._authoring_root(root),
                interiors_v3_authoring_root=root / "missing-v3-authoring",
                interiors_v3_source_root=root / "missing-moderninteriors-win",
            )
            self.assertNotIn("interiors_v3_catalog_sha256", manifest)

    def test_v3_license_preflight_fails_before_creating_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            source = self._tmj(root)
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["tilesets"].append({"firstgid": 3, "source": "room_floors.tsj"})
            write_json(source, payload)
            v3_authoring = root / "v3-authoring"
            v3_source = root / "moderninteriors-win"
            v3_authoring.mkdir()
            v3_source.mkdir()
            runtime = root / "runtime"
            error = tilemap_culler.modern_interiors_v3_source.ModernInteriorsV3Error(
                "license evidence changed"
            )
            with patch.object(
                tilemap_culler.modern_interiors_v3_source,
                "validate_pack",
                side_effect=error,
            ), self.assertRaisesRegex(tilemap_culler.CullError, "preflight failed"):
                tilemap_culler.cull_runtime_tilesets(
                    source, runtime, authoring_root=authoring,
                    interiors_v3_authoring_root=v3_authoring,
                    interiors_v3_source_root=v3_source,
                )
            self.assertFalse(runtime.exists())

    def test_generation_failure_preserves_the_previous_runtime(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            source = self._tmj(root)
            runtime = root / "runtime"
            runtime.mkdir()
            previous = {
                runtime / "runtime_manifest.json": b"previous manifest",
                runtime / "props.png": b"previous props",
            }
            for path, payload in previous.items():
                path.write_bytes(payload)
            with patch.object(
                tilemap_culler,
                "_write_runtime_tiles",
                side_effect=tilemap_culler.CullError("injected generation failure"),
            ), self.assertRaisesRegex(tilemap_culler.CullError, "injected"):
                tilemap_culler.cull_runtime_tilesets(
                    source, runtime, authoring_root=authoring,
                )
            self.assertEqual(
                {path: path.read_bytes() for path in previous}, previous,
            )

    def test_commit_failure_rolls_back_every_generated_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            source = self._tmj(root)
            runtime = root / "runtime"
            tilemap_culler.cull_runtime_tilesets(
                source, runtime, authoring_root=authoring,
            )
            previous = {
                path.relative_to(runtime): path.read_bytes()
                for path in runtime.rglob("*") if path.is_file()
            }
            original_replace = Path.replace
            calls = 0

            def fail_during_install(path, target):
                nonlocal calls
                calls += 1
                if calls == len(previous) + 2:
                    raise OSError("injected commit failure")
                return original_replace(path, target)

            with patch.object(Path, "replace", autospec=True, side_effect=fail_during_install), \
                    self.assertRaisesRegex(tilemap_culler.CullError, "transaction"):
                tilemap_culler.cull_runtime_tilesets(
                    source, runtime, authoring_root=authoring,
                )
            self.assertEqual(
                {
                    path.relative_to(runtime): path.read_bytes()
                    for path in runtime.rglob("*") if path.is_file()
                },
                previous,
            )

    def test_rebuild_removes_only_known_stale_runtime_assets(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            source = self._tmj(root)
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["layers"][1]["objects"] = []
            write_json(source, payload)
            runtime = root / "runtime"
            tiles = runtime / "tiles"
            tiles.mkdir(parents=True)
            stale = (
                runtime / "props.png", runtime / "props.json",
                tiles / "interiors_v3.png", tiles / "interiors_v3.tsj",
                tiles / "town.png", tiles / "town.tsj",
            )
            for path in stale:
                path.write_bytes(b"stale")
            unrelated = runtime / "keep.txt"
            unrelated.write_text("keep", encoding="utf-8")
            manifest = tilemap_culler.cull_runtime_tilesets(
                source, runtime, authoring_root=authoring,
                interiors_v3_authoring_root=root / "missing-v3-authoring",
                interiors_v3_source_root=root / "missing-moderninteriors-win",
            )
            self.assertIsNone(manifest["props"])
            self.assertTrue(all(not path.exists() for path in stale))
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_rejects_non_native_map_dimensions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            source = self._tmj(root)
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["width"] = 88
            write_json(source, payload)
            with self.assertRaisesRegex(tilemap_culler.CullError, "176x96"):
                tilemap_culler.cull_runtime_tilesets(source, root / "runtime", authoring_root=authoring)

    def test_culls_the_fourth_interiors_atlas_without_shipping_full_sources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            source = self._tmj(root)
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["tilesets"].append({"firstgid": 3, "source": "interiors.tsj"})
            payload["layers"][0]["data"][3] = 3
            write_json(source, payload)
            runtime = root / "runtime"
            manifest = tilemap_culler.cull_runtime_tilesets(
                source, runtime, authoring_root=authoring
            )
            self.assertEqual(
                [page["key"] for page in manifest["tilesets"]],
                ["terrain", "interiors"],
            )
            self.assertEqual(manifest["tilesets"][1]["tile_count"], 1)
            self.assertTrue((runtime / "tiles/interiors.png").is_file())

    def test_v3_profile_rejects_the_legacy_interiors_tileset(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            source = self._tmj(root)
            payload = json.loads(source.read_text(encoding="utf-8"))
            payload["properties"] = [{
                "name": "authoring_profile",
                "value": tilemap_culler.V3_PROFILE,
            }]
            payload["tilesets"].append({"firstgid": 3, "source": "interiors.tsj"})
            write_json(source, payload)
            with self.assertRaisesRegex(tilemap_culler.CullError, "legacy interiors"):
                tilemap_culler.cull_runtime_tilesets(
                    source, root / "runtime", authoring_root=authoring,
                )

    def test_runtime_prop_packer_grows_for_a_finished_civic_building(self):
        school = Image.new("RGBA", (384, 368), (64, 90, 112, 255))
        width, height, placements = tilemap_culler._pack_props([("prop.building.school", school)])
        self.assertEqual((width, height), (512, 372))
        self.assertEqual(placements[0][0], "prop.building.school")

    def test_rejects_authoring_atlas_path_traversal(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            outside = root / "outside.png"
            Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(outside)
            atlas = json.loads((authoring / "atlas.json").read_text(encoding="utf-8"))
            atlas["atlases"][0]["image"] = "../outside.png"
            write_json(authoring / "atlas.json", atlas)
            with self.assertRaisesRegex(tilemap_culler.CullError, "escapes"):
                tilemap_culler.cull_runtime_tilesets(
                    self._tmj(root), root / "runtime", authoring_root=authoring
                )


if __name__ == "__main__":
    unittest.main()
