"""Contracts for the active reference-traced south residential district."""

from __future__ import annotations

import json
import unittest
from collections import defaultdict
from pathlib import Path

from tools.mapgen import claudeville_reference_facade_assets as facades
from tools.mapgen import claudeville_reference_home1 as partitions
from tools.mapgen import claudeville_reference_layout as layout
from tools.mapgen import claudeville_reference_semantics as semantics
from tools.mapgen import claudeville_reference_shared_civic as town_hall
from tools.mapgen import claudeville_reference_stamps as homes
from tools.mapgen import claudeville_semantic_graph as semantic_graph
from tools.mapgen import claudeville_tiled_authoring as authoring
from tools.mapgen import compile_claudeville_semantics as compiler

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "tools/mapgen/town_spec.json"
TARGET_SOURCE = (
    ROOT / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
    / "claudeville_target_v45.tmj"
)
SOUTH = frozenset({f"Home {number}" for number in range(2, 11)} | {"Town Hall"})
EXPECTED = {name: semantics.EMBEDDED_SECTOR_RECTS[name] for name in SOUTH}


class SouthDistrictTests(unittest.TestCase):
    def test_south_sector_row_matches_the_active_cutaway_lots(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        sectors = {item["name"]: item["rect"] for item in spec["sectors"]}
        self.assertEqual({name: sectors[name] for name in SOUTH}, EXPECTED)

    def test_all_south_arenas_objects_entrances_and_spawns_stay_in_sector(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        sectors = {item["name"]: item["rect"] for item in spec["sectors"]}

        def inside(rect, point):
            return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]

        for arena in spec["arenas"]:
            if arena["sector"] not in SOUTH:
                continue
            for x0, y0, x1, y1 in (arena.get("rects") or [arena["rect"]]):
                self.assertTrue(inside(sectors[arena["sector"]], (x0, y0)))
                self.assertTrue(inside(sectors[arena["sector"]], (x1, y1)))
        for collection, key in (
            (spec["objects"], "tiles"), (spec["spawns"], "tile"),
            (spec["entrances"], "tile"),
        ):
            for item in collection:
                if item["sector"] not in SOUTH:
                    continue
                points = item[key] if key == "tiles" else [item[key]]
                self.assertTrue(all(inside(sectors[item["sector"]], p) for p in points))

    def test_reference_entrances_are_the_emitted_top_facing_doors(self):
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        actual = {item["sector"]: tuple(item["tile"]) for item in spec["entrances"]}
        self.assertEqual(
            {sector: actual[sector] for sector in SOUTH},
            {sector: semantics.ENTRANCES[sector] for sector in SOUTH},
        )

    def test_all_nine_south_homes_have_individual_nonoverlapping_shells(self):
        rooms = []
        for sector in sorted(SOUTH - {"Town Hall"}):
            record = layout.BUILDINGS[sector]
            self.assertTrue(record["paint_shell"])
            self.assertEqual(record["door_side"], "top")
            rooms.append((sector, record["room"]))
        for index, (sector, (left, top, right, bottom)) in enumerate(rooms):
            for other, (o_left, o_top, o_right, o_bottom) in rooms[index + 1:]:
                overlaps = left < o_right and o_left < right and top < o_bottom and o_top < bottom
                self.assertFalse(overlaps, f"{sector} overlaps {other}")

    def test_every_home_has_one_complete_purposeful_program(self):
        by_home = defaultdict(list)
        for placement in homes.HOME_PLACEMENTS:
            by_home[placement[0]].append(placement)
        required = {
            "washstand", "toilet-fixture", "refrigerator", "cooking-area",
            "closet", "bed", "lounge-seating", "media-console", "plant",
            "resident-hobby",
        }
        for home in sorted(SOUTH - {"Town Hall"}):
            with self.subTest(home=home):
                placements = by_home[home]
                self.assertEqual(len(placements), 11)
                self.assertTrue(required <= {item[2] for item in placements})
                room = layout.BUILDINGS[home]["room"]
                self.assertTrue(all(
                    room[0] < item[5] < room[2] and room[1] < item[6] < room[3]
                    for item in placements
                ))

    def test_internal_partitions_and_door_gaps_stay_inside_each_home(self):
        south_partitions = [item for item in partitions.PARTITIONS if item[0] in SOUTH]
        self.assertEqual({item[0] for item in south_partitions}, SOUTH - {"Town Hall"})
        for sector, orientation, fixed, start, end, gaps in south_partitions:
            left, top, right, bottom = layout.BUILDINGS[sector]["room"]
            if orientation == "horizontal":
                self.assertTrue(top < fixed < bottom and left <= start < end <= right)
                self.assertTrue(all(start <= gap <= end for gap in gaps))
            else:
                self.assertTrue(left < fixed < right and top <= start < end <= bottom)
                self.assertTrue(all(start <= gap <= end for gap in gaps))

    def test_residential_frontages_are_distinct_native_exteriors_compositions(self):
        specs = {
            spec["sector"]: spec for spec in facades.RESIDENTIAL_SPECS
            if spec["sector"] in SOUTH
        }
        self.assertEqual(set(specs), SOUTH - {"Town Hall"})
        signatures = [tuple(spec["source_keys"]) for spec in specs.values()]
        self.assertEqual(len(signatures), len(set(signatures)))
        self.assertTrue(all(spec["output_size"][1] == 48 for spec in specs.values()))

    def test_town_hall_has_records_council_service_and_administration_clusters(self):
        roles = {item[2] for item in town_hall.PLACEMENTS}
        self.assertTrue({
            "records", "council-table", "council-chair", "counter-wing",
            "service-terminal", "admin-desk", "waiting-seat",
        } <= roles)
        town_hall.validate()

    def test_active_south_authoring_preserves_collision_and_connectivity(self):
        source = json.loads(TARGET_SOURCE.read_text(encoding="utf-8"))
        spec = json.loads(SPEC.read_text(encoding="utf-8"))
        collision = semantic_graph.read_collision(compiler.COLLISION_PATH)
        compiled = authoring.compile_authoring(source, spec, collision)
        self.assertEqual(compiled.stats["collision_mismatches"], 0)
        self.assertEqual(compiled.stats["connectivity_pct"], 100)
        self.assertEqual(compiled.stats["stances"], compiled.stats["objects"])


if __name__ == "__main__":
    unittest.main()
