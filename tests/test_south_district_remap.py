"""Contracts for Claudeville's coherent south residential district."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "tools/mapgen/town_spec.json"

EXPECTED = {
    "Home 2": [2, 35, 8, 45], "Home 3": [10, 35, 16, 45],
    "Home 4": [18, 35, 24, 45], "Home 5": [26, 35, 32, 45],
    "Home 6": [34, 35, 41, 45], "Town Hall": [43, 34, 53, 45],
    "Home 7": [55, 35, 61, 45], "Home 8": [63, 35, 69, 45],
    "Home 9": [71, 35, 78, 45], "Home 10": [80, 35, 86, 45],
}


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


if __name__ == "__main__":
    unittest.main()
