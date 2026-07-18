"""Validation tests for the paid Modern Interiors source normalization."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from tools.mapgen import modern_interiors_source


class ModernInteriorsSourceTests(unittest.TestCase):
    def test_project_sources_are_exact_lossless_2x_native_16_sheets(self):
        expected = {
            "interiors.full": ((256, 17024), 14916),
            "interiors.room_builder": ((1216, 1744), 3795),
        }
        entries, records = modern_interiors_source.read_source_tiles()
        self.assertEqual(sum(record["tile_count"] for record in records), 18711)
        self.assertEqual(len(entries), 18711)
        for record in records:
            with self.subTest(source=record["source_id"]):
                native_size, tile_count = expected[record["source_id"]]
                self.assertEqual(record["native_size"], list(native_size))
                self.assertEqual(record["tile_count"], tile_count)
                self.assertEqual(record["pack"], "Modern Interiors")
                self.assertEqual(record["source_scope"], "project")
                self.assertEqual(
                    record["normalization"],
                    "lossless-nearest-neighbour-2x-to-native-16",
                )

    def test_credit_record_is_bound_to_exact_project_source_hashes(self):
        credit = modern_interiors_source.credit_record()
        self.assertEqual(credit["name"], "Modern Interiors")
        self.assertEqual(
            {item["sha256"] for item in credit["sources"]},
            {sheet.expected_sha256 for sheet in modern_interiors_source.SHEETS},
        )

    def test_free_traversal_and_modified_sources_are_rejected(self):
        root = modern_interiors_source.DEFAULT_SOURCE_ROOT
        for relative in (
            "../Interiors_32x32_full.png",
            "Modern_Interiors_Free_v2.2.png",
            "interiors_pt1.png",
        ):
            with self.subTest(relative=relative), self.assertRaisesRegex(
                modern_interiors_source.ModernInteriorsSourceError, "unapproved"
            ):
                modern_interiors_source.validate_source_path(root, relative)

        with TemporaryDirectory() as temporary:
            source = Path(temporary) / "Interiors_32x32_full.png"
            Image.new("RGBA", (32, 32), (1, 2, 3, 255)).save(source)
            with self.assertRaisesRegex(
                modern_interiors_source.ModernInteriorsSourceError, "hash changed"
            ):
                modern_interiors_source.load_native_sheet(
                    "interiors.full", Path(temporary)
                )


if __name__ == "__main__":
    unittest.main()
