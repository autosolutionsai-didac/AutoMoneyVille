"""Focused contract tests for the Claudeville v2 authoring-palette culler."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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
        })
        write_json(authoring / "credits.json", {
            "packs": [{"name": "Test Pack", "license_sha256": "a" * 64}],
        })
        write_json(authoring / "tiles.json", {"tiles": [
            {"asset_key": "tile.test.grass", "atlas": "terrain", "atlas_index": 0},
            {"asset_key": "tile.test.water", "atlas": "terrain", "atlas_index": 1},
            {
                "asset_key": "tile.interiors.full.r0000.c00",
                "atlas": "interiors",
                "atlas_index": 0,
            },
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
            self.assertEqual(credits["packs"][0]["name"], "Test Pack")

    def test_unknown_object_asset_fails_before_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            authoring = self._authoring_root(root)
            with self.assertRaisesRegex(tilemap_culler.CullError, "missing from props"):
                tilemap_culler.cull_runtime_tilesets(
                    self._tmj(root, "prop.unlicensed.missing"), root / "runtime", authoring_root=authoring
                )
            self.assertFalse((root / "runtime").exists())

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
