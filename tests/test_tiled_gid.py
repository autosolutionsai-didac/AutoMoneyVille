"""Focused contracts for orthogonal Tiled GID handling."""

from __future__ import annotations

import unittest

from PIL import Image

from tools.mapgen import tiled_gid


class TiledGidTests(unittest.TestCase):
    def test_all_nonempty_gids_must_resolve_to_nonoverlapping_tilesets(self):
        layers = {"Ground": {"data": [0, 1, tiled_gid.HORIZONTAL_FLIP | 2, 10]}}
        tilesets = [
            {"firstgid": 1, "tilecount": 2, "name": "terrain"},
            {"firstgid": 10, "tilecount": 1, "name": "interiors"},
        ]
        tiled_gid.validate_runtime_gids(layers, tilesets, ("Ground",))

        layers["Ground"]["data"][-1] = 9
        with self.assertRaisesRegex(tiled_gid.TiledGidError, "unresolved GID 9"):
            tiled_gid.validate_runtime_gids(layers, tilesets, ("Ground",))

        overlapping = [*tilesets, {"firstgid": 2, "tilecount": 2, "name": "bad"}]
        with self.assertRaisesRegex(tiled_gid.TiledGidError, "overlap"):
            tiled_gid.validate_runtime_gids({"Ground": {"data": [1]}}, overlapping, ("Ground",))

    def test_orthogonal_runtime_rejects_the_ignored_fourth_tiled_flag(self):
        layers = {
            "Ground": {"data": [tiled_gid.IGNORED_HEX_ROTATION | 1]},
        }
        tilesets = [{"firstgid": 1, "tilecount": 1, "name": "terrain"}]
        with self.assertRaisesRegex(tiled_gid.TiledGidError, "invalid orthogonal GID"):
            tiled_gid.validate_runtime_gids(layers, tilesets, ("Ground",))

    def test_preview_transform_uses_diagonal_then_horizontal_then_vertical(self):
        image = Image.new("RGBA", (2, 2))
        image.putdata([
            (255, 0, 0, 255), (0, 255, 0, 255),
            (0, 0, 255, 255), (255, 255, 0, 255),
        ])
        diagonal = tiled_gid.transform_orthogonal_tile(image, tiled_gid.DIAGONAL_FLIP)
        self.assertEqual(
            list(diagonal.get_flattened_data()),
            [
                (255, 0, 0, 255), (0, 0, 255, 255),
                (0, 255, 0, 255), (255, 255, 0, 255),
            ],
        )
        all_flips = tiled_gid.transform_orthogonal_tile(
            image, tiled_gid.ORTHOGONAL_FLIP_MASK
        )
        self.assertEqual(
            list(all_flips.get_flattened_data()),
            [
                (255, 255, 0, 255), (0, 255, 0, 255),
                (0, 0, 255, 255), (255, 0, 0, 255),
            ],
        )


if __name__ == "__main__":
    unittest.main()
