"""Input-boundary tests for Claudeville's hand-authored Tiled compiler."""

from __future__ import annotations

import unittest

from tools.mapgen import build_tilemap


def authored_source(*, object_properties: list[dict] | None = None, x: int = 16, y: int = 16) -> dict:
    """Return the smallest valid root TMJ shape for compiler validation tests."""
    data = [0] * (176 * 96)
    tile_layers = [
        {"name": name, "type": "tilelayer", "width": 176, "height": 96, "data": data}
        for name in build_tilemap.TILE_LAYERS
    ]
    properties = object_properties or [{"name": "asset_key", "value": "prop.street.lamp_01"}]
    object_layers = [
        {"name": name, "type": "objectgroup", "objects": [{"x": x, "y": y, "properties": properties}]}
        for name in build_tilemap.OBJECT_LAYERS
    ]
    return {
        "width": 176,
        "height": 96,
        "tilewidth": 16,
        "tileheight": 16,
        "infinite": False,
        "orientation": "orthogonal",
        "layers": [*tile_layers[:-1], *object_layers, tile_layers[-1]],
        "tilesets": [
            {"firstgid": 1, "source": "terrain.tsj"},
            {"firstgid": 2, "source": "town.tsj"},
            {"firstgid": 3, "source": "office.tsj"},
        ],
    }


class BuildTilemapValidationTests(unittest.TestCase):
    def test_accepts_bounded_native_object_metadata(self):
        source = authored_source(object_properties=[
            {"name": "asset_key", "value": "prop.plaza.fountain_blue"},
            {"name": "anchor_x", "value": 0.5},
            {"name": "anchor_y", "value": 1},
            {"name": "display_scale", "value": 2},
        ])
        self.assertEqual(set(build_tilemap._validate_source(source)), set(
            build_tilemap.TILE_LAYERS + build_tilemap.OBJECT_LAYERS
        ))

    def test_rejects_invalid_scale_and_out_of_bounds_objects(self):
        bad_scale = authored_source(object_properties=[
            {"name": "asset_key", "value": "prop.street.lamp_01"},
            {"name": "display_scale", "value": 0},
        ])
        with self.assertRaisesRegex(build_tilemap.TilemapError, "display_scale"):
            build_tilemap._validate_source(bad_scale)

        with self.assertRaisesRegex(build_tilemap.TilemapError, "in-bounds"):
            build_tilemap._validate_source(authored_source(x=2817))


if __name__ == "__main__":
    unittest.main()
