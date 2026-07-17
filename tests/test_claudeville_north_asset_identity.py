"""Asset-identity contracts for Claudeville's north district."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from tools.mapgen import claudeville_north_placements as north

ROOT = Path(__file__).resolve().parents[1]
V2_CATALOG = ROOT / "output/claudeville/modern_pixels_v2/catalog.json"
V3_CATALOG = ROOT / "output/claudeville/modern_interiors_v3/catalog.json"
SOURCE_MAP = (
    ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
    / "claudeville_modern_interiors_v3.tmj"
)


def _placements(sector: str) -> list[tuple]:
    return [item for item in north.PLACEMENTS if item[0] == sector]


class NorthAssetIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        records = []
        for path in (V2_CATALOG, V3_CATALOG):
            records.extend(json.loads(path.read_text(encoding="utf-8"))["props"])
        cls.catalog = {item["asset_key"]: item for item in records}
        cls.source = json.loads(SOURCE_MAP.read_text(encoding="utf-8"))

    def test_revision_fourteen_uses_verified_home_wardrobes(self):
        self.assertEqual(north.REVISION, 14)
        closets = [item for item in _placements("Home 1") if item[2] == "closet"]
        self.assertEqual(
            {item[4] for item in closets},
            {
                "prop.interiors_v3.bedroom.0386",
                "prop.interiors_v3.bedroom.0388",
            },
        )
        self.assertNotIn(
            "prop.interiors_v3.bedroom.0004",
            {item[4] for item in _placements("Home 1")},
        )

    def test_market_uses_real_checkouts_produce_crates_and_carts(self):
        placements = _placements("Market")
        by_role = {}
        for item in placements:
            by_role.setdefault(item[2], []).append(item)
        self.assertEqual(
            {item[4] for item in by_role["checkout-counter"]},
            {
                "prop.interiors_v3.grocery.0162",
                "prop.interiors_v3.grocery.0166",
            },
        )
        self.assertEqual(
            {item[4] for item in by_role["produce-crate"]},
            {
                "prop.interiors_v3.grocery.0371",
                "prop.interiors_v3.grocery.0373",
                "prop.interiors_v3.grocery.0374",
            },
        )
        self.assertEqual(
            {item[4] for item in by_role["shopping-cart"]},
            {
                "prop.interiors_v3.grocery.0413",
                "prop.interiors_v3.grocery.0414",
            },
        )
        keys = {item[4] for item in placements}
        self.assertTrue({
            "prop.interiors_v3.grocery.0177",
            "prop.interiors_v3.grocery.0249",
            "prop.interiors_v3.grocery.0251",
        }.isdisjoint(keys))

    def test_market_props_do_not_overlap_the_right_shell_wall_or_entry_lane(self):
        shell = next(item for item in north.VISUAL_SHELLS if item[0] == "Market")
        _sector, left, _top, right, _bottom, *_tail = shell
        interior_left = (left + 1) * 16
        right_wall = right * 16
        for item in _placements("Market"):
            key, x, y = item[4], item[5], item[6]
            record = self.catalog[key]
            width = record["native_size"][0] * record.get("display_scale", 1)
            anchor_x = record["anchor"][0]
            prop_left = x * 16 - width * anchor_x
            prop_right = x * 16 + width * (1 - anchor_x)
            with self.subTest(key=key, x=x, y=y):
                self.assertGreaterEqual(prop_left, interior_left)
                self.assertLessEqual(prop_right, right_wall)
                if y >= 29:
                    self.assertNotIn(x, {154, 155})

    def test_post_office_uses_postal_racks_without_library_or_gym_fiction(self):
        placements = _placements("Post Office")
        racks = [item for item in placements if item[2] == "parcel-sorting-rack"]
        self.assertEqual(
            [item[4] for item in racks],
            [
                "prop.library.shelf_dark_1",
                "prop.library.shelf_dark_2",
                "prop.library.shelf_dark_3",
            ],
        )
        self.assertFalse(any(
            item[4].startswith("prop.interiors_v3.classroom_library.")
            or item[4] == "prop.interiors_v3.gym.0196"
            or item[2] == "queue-runner"
            for item in placements
        ))

    def test_refreshment_assets_are_floor_standing_and_academy_desks_clear_wall(self):
        education = _placements("University") + _placements("Agent Academy")
        self.assertNotIn("prop.office.coffee_station", {item[4] for item in education})
        for sector in ("University", "Agent Academy"):
            vending = [
                item for item in _placements(sector)
                if item[4] == "prop.office.vending_machine"
            ]
            self.assertEqual(len(vending), 1)
        academy_desks = [
            item for item in _placements("Agent Academy")
            if item[2] == "classroom-seating"
        ]
        self.assertEqual(Counter(item[5] for item in academy_desks), Counter({122: 2, 126: 2}))
        for item in academy_desks:
            record = self.catalog[item[4]]
            width = record["native_size"][0] * record.get("display_scale", 1)
            right_edge = item[5] * 16 + width * (1 - record["anchor"][0])
            self.assertLess(right_edge, 127 * 16)

    def test_university_dining_stance_moves_to_the_walkable_central_aisle(self):
        self.assertEqual(
            north.INTERACTION_STANCE_UPDATES,
            (("University", "university.cafeteria.dining-table-001", 43, 14),),
        )

    def test_exact_source_specific_legacy_clear_rectangles_are_declared(self):
        expected = {
            "University": ((73, 8, 100, 10), (73, 10, 74, 21), (98, 10, 100, 21)),
            "Agent Academy": ((109, 10, 130, 12), (109, 12, 110, 32), (128, 12, 130, 26)),
            "Market": ((147, 22, 161, 23), (147, 23, 148, 30), (160, 23, 161, 30)),
            "Post Office": (
                (149, 43, 172, 44),
                (149, 44, 150, 64),
                (170, 44, 172, 64),
                (150, 63, 170, 64),
            ),
        }
        self.assertEqual(north.SAFE_LEGACY_CLEAR_RECTS, expected)
        clears = dict(north.LEGACY_TILESET_CLEARS)
        self.assertEqual(clears["interiors"], expected["Market"])
        self.assertEqual(clears["town"], north.SAFE_TOWN_CLEAR_RECTS)
        self.assertEqual(
            clears["office"],
            tuple(
                rect
                for sector in ("University", "Agent Academy", "Market", "Post Office")
                for rect in expected[sector]
            ),
        )

    def test_detached_town_facade_strips_are_absent_from_the_authored_map(self):
        reference = next(
            item for item in self.source["tilesets"]
            if Path(item["source"]).stem == "town"
        )
        tileset_path = SOURCE_MAP.parent / reference["source"]
        tilecount = json.loads(tileset_path.read_text(encoding="utf-8"))["tilecount"]
        firstgid, lastgid = reference["firstgid"], reference["firstgid"] + tilecount
        for layer in self.source["layers"]:
            if layer.get("type") != "tilelayer":
                continue
            for left, top, right, bottom in north.SAFE_TOWN_CLEAR_RECTS:
                for y in range(top, bottom):
                    for x in range(left, right):
                        gid = layer["data"][y * self.source["width"] + x] & 0x0FFFFFFF
                        self.assertFalse(firstgid <= gid < lastgid)


if __name__ == "__main__":
    unittest.main()
