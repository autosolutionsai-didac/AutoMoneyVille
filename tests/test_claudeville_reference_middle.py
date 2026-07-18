"""Focused composition contracts for the active target-photo middle district."""

from __future__ import annotations

import unittest
from collections import Counter, defaultdict

from tools.mapgen import claudeville_reference_middle as middle
from tools.mapgen import claudeville_reference_stamps as stamps


class ClaudevilleReferenceMiddleTests(unittest.TestCase):
    def placements(self, sector: str) -> tuple[middle.Placement, ...]:
        return tuple(item for item in middle.PLACEMENTS if item[0] == sector)

    def test_community_and_cafe_have_separate_purposeful_wings(self):
        community = self.placements("Community Center")
        cafe = self.placements("Claudeville Cafe")
        self.assertTrue(all(67 <= item[5] < 79 for item in community))
        self.assertTrue(all(79 <= item[5] < 91 for item in cafe))

        event_groups: dict[str, Counter[str]] = defaultdict(Counter)
        for _sector, _zone, role, cluster, _key, _x, _y in community:
            if cluster.endswith("event table"):
                event_groups[cluster][role] += 1
        self.assertEqual(set(event_groups), {"north event table", "south event table"})
        self.assertTrue(all(
            counts == {"event-table": 3, "event-seat": 2}
            for counts in event_groups.values()
        ))

        dining: dict[str, Counter[str]] = defaultdict(Counter)
        for _sector, _zone, role, cluster, _key, _x, _y in cafe:
            if cluster.startswith("window table"):
                dining[cluster][role] += 1
        self.assertEqual(
            set(dining),
            {"window table one", "window table two", "window table three"},
        )
        self.assertTrue(all(
            counts == {"dining-table": 1, "dining-chair": 2}
            for counts in dining.values()
        ))

    def test_library_has_a_continuous_book_wall_and_central_reading_field(self):
        library = self.placements("Library")
        top_shelves = [
            item for item in library
            if item[3] == "library perimeter" and item[6] == 48
        ]
        self.assertEqual([item[5] for item in top_shelves], list(range(144, 170, 2)))
        self.assertGreaterEqual(
            sum(item[2] in {"bookshelf", "east-bookshelf"} for item in library), 16,
        )
        reading = [item for item in library if item[2] == "reading-table"]
        self.assertEqual(
            {(item[5], item[6]) for item in reading},
            {
                (148, 55), (150, 55), (152, 55),
                (158, 56), (160, 56), (162, 56),
            },
        )

    def test_post_office_has_a_joined_counter_and_full_sorting_wall(self):
        post = self.placements("Post Office")
        counters = [item for item in post if item[2] == "postal-counter"]
        self.assertEqual(
            [(item[5], item[6]) for item in counters],
            [(159, 28), (161, 28), (163, 28), (165, 28)],
        )
        racks = [item for item in post if item[2] == "parcel-sorting-rack"]
        self.assertEqual([(item[5], item[6]) for item in racks], [
            (159, 15), (161, 15), (163, 15), (165, 15),
            (167, 15), (169, 15), (171, 15), (173, 15),
        ])
        self.assertTrue(all(11 < item[6] < 36 for item in post))

    def test_only_reviewed_cafe_and_facade_compositions_are_active(self):
        keys = {item[2] for item in stamps.PLACEMENTS}
        self.assertIn("prop.design.community_cafe", keys)
        self.assertIn("prop.design.community_studio", keys)
        self.assertIn("prop.design.frontage.library_graystone", keys)
        self.assertNotIn("prop.design.cafe_complete", keys)
        self.assertNotIn("prop.design.bank_suite", keys)
        middle.validate()
        middle.validate_catalogs()


if __name__ == "__main__":
    unittest.main()
