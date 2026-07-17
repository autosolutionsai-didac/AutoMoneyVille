"""Contracts for Claudeville's coherent south residential district."""

import json
import unittest
from collections import defaultdict
from pathlib import Path

from tools.mapgen import claudeville_south_placements as south

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "tools/mapgen/town_spec.json"

EXPECTED = {
    "Home 2": [2, 35, 8, 45], "Home 3": [10, 35, 16, 45],
    "Home 4": [18, 35, 24, 45], "Home 5": [26, 35, 32, 45],
    "Home 6": [34, 35, 41, 45], "Town Hall": [43, 34, 53, 45],
    "Home 7": [55, 35, 61, 45], "Home 8": [63, 35, 69, 45],
    "Home 9": [71, 35, 78, 45], "Home 10": [80, 35, 86, 45],
}
AUTHORED_HOMES = tuple(
    name for name in EXPECTED if name.startswith("Home ") and name != "Home 5"
)


class SouthDistrictTests(unittest.TestCase):
    def test_south_sector_row_matches_authored_facade_lots(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        sectors = {item["name"]: item["rect"] for item in spec["sectors"]}
        self.assertEqual({name: sectors[name] for name in EXPECTED}, EXPECTED)

    def test_all_south_arenas_objects_and_spawns_remain_inside_their_sector(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        sectors = {item["name"]: item["rect"] for item in spec["sectors"]}

        def inside(rect, point):
            return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]

        for arena in spec["arenas"]:
            if arena["sector"] not in EXPECTED:
                continue
            rects = arena.get("rects", [arena.get("rect")])
            self.assertTrue(all(rect is not None for rect in rects))
            for x0, y0, x1, y1 in rects:
                self.assertTrue(inside(sectors[arena["sector"]], (x0, y0)))
                self.assertTrue(inside(sectors[arena["sector"]], (x1, y1)))
        for collection, key in ((spec["objects"], "tiles"), (spec["spawns"], "tile")):
            for item in collection:
                if item["sector"] not in EXPECTED:
                    continue
                points = item[key] if key == "tiles" else [item[key]]
                self.assertTrue(all(inside(sectors[item["sector"]], point) for point in points))

    def test_production_homes_have_distinct_palettes_and_room_graphs(self):
        self.assertNotIn("Home 5", south.TARGETS)
        shells = {record[0]: record for record in south.VISUAL_SHELLS}
        palettes = [shells[name][7] for name in AUTHORED_HOMES]
        self.assertEqual(len(palettes), len(set(palettes)))

        signatures = []
        for name in AUTHORED_HOMES:
            _, left, top, *_tail = shells[name]
            signature = []
            for sector, orientation, fixed, start, end, gaps in south.WALL_RUNS:
                if sector != name:
                    continue
                fixed_origin = left if orientation == "vertical" else top
                run_origin = top if orientation == "vertical" else left
                signature.append((
                    orientation, fixed - fixed_origin, start - run_origin,
                    end - run_origin, tuple(gap - run_origin for gap in gaps),
                ))
            signatures.append(tuple(signature))
        self.assertEqual(len(signatures), len(set(signatures)))

    def test_every_home_has_complete_purposeful_clusters(self):
        by_home = defaultdict(list)
        for placement in south.PLACEMENTS:
            by_home[placement[0]].append(placement)
        for home in AUTHORED_HOMES:
            with self.subTest(home=home):
                placements = by_home[home]
                roles = {item[2] for item in placements}
                self.assertTrue({"bed", "cooking-area", "refrigerator"} <= roles)
                self.assertTrue({"kitchen-counter", "kitchen-prep"} <= roles)
                self.assertTrue({"closet", "wardrobe", "dresser"} & roles)
                self.assertTrue({"sofa", "common-room-sofa"} & roles)
                self.assertTrue(any("sink" in role for role in roles))
                self.assertTrue(any("shower" in role for role in roles))
                self.assertTrue(any("toilet" in role for role in roles))
                self.assertGreaterEqual(len({item[3] for item in placements}), 6)

                counter = next(item for item in placements if item[2] == "kitchen-counter")
                sink = next(item for item in placements if item[2] == "kitchen-prep")
                self.assertEqual(counter[5], sink[5])
                self.assertEqual(counter[6] - 1, sink[6])

    def test_native_arches_replace_all_giant_entrance_props(self):
        self.assertIn("room.arched_entryways", south.V3_TILE_SOURCES)
        self.assertFalse(any(
            placement[4].startswith("prop.facade.") or placement[2] == "entrance"
            for placement in south.PLACEMENTS
        ))
        for layer, x, y, reference in south.VISUAL_TILE_EDITS:
            self.assertEqual(layer, "Wall")
            self.assertEqual(reference[0], "room.arched_entryways")
        self.assertEqual(len(south.VISUAL_TILE_EDITS), len(south.TARGETS) * 4)
        for shell in south.VISUAL_SHELLS:
            sector, _left, top, _right, _bottom, door_left, door_right, _floor = shell
            expected = {
                (x, y) for x in range(door_left, door_right + 1)
                for y in range(top, top + 2)
            }
            actual = {
                (x, y) for _layer, x, y, _reference in south.VISUAL_TILE_EDITS
                if (x, y) in expected
            }
            with self.subTest(sector=sector):
                self.assertEqual(actual, expected)

    def test_facade_cleanup_is_limited_to_two_safe_rows_per_parcel(self):
        self.assertEqual(len(south.SAFE_LEGACY_FACADE_RECTS), len(south.TARGETS))
        for sector, left, top, right, bottom in south.SAFE_LEGACY_FACADE_RECTS:
            target_left, target_top, target_right, target_bottom = south.TARGET_BOUNDS[sector]
            self.assertEqual(bottom - top, 2)
            self.assertTrue(target_left <= left < right <= target_right)
            self.assertTrue(target_top <= top < bottom <= target_bottom)
        self.assertEqual(
            south.TILE_FILLS,
            tuple(
                ("Foreground L1", left, top, right, bottom, 0)
                for _sector, left, top, right, bottom
                in south.SAFE_LEGACY_FACADE_RECTS
            ),
        )

    def test_town_hall_has_public_admin_and_council_clusters(self):
        placements = [item for item in south.PLACEMENTS if item[0] == "Town Hall"]
        zones = {item[1] for item in placements}
        roles = {item[2] for item in placements}
        self.assertEqual(zones, {
            "hall.public_service", "hall.administration", "hall.council",
        })
        self.assertTrue({
            "public-counter", "administration-desk", "council-table",
            "waiting-sofa", "printer", "council-screen",
        } <= roles)


if __name__ == "__main__":
    unittest.main()
