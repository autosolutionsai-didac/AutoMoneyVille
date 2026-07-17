"""Focused visual contract for the authored Community Center."""

from __future__ import annotations

import json
import unittest

from tools.mapgen import author_claudeville_districts as authoring
from tools.mapgen import claudeville_middle_placements as middle


class CommunityCenterLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.placements = tuple(
            placement
            for placement in middle.PLACEMENTS
            if placement[0] == "Community Center"
        )

    def test_stage_support_sorts_in_front_of_the_stage(self):
        stage = next(item for item in self.placements if item[2] == "presentation-area")
        support = tuple(
            item
            for item in self.placements
            if item[2] in {"stage-speaker", "stage-podium", "presentation-display"}
        )
        self.assertEqual(len(support), 4)
        self.assertTrue(all(item[3] == "stage" for item in support))
        self.assertTrue(all(item[6] > stage[6] for item in support))
        self.assertEqual(
            {item[4] for item in support},
            {
                "prop.interiors_v3.conference.0028",
                "prop.interiors_v3.conference.0030",
                "prop.interiors_v3.music_sport.0043",
            },
        )

    def test_audience_forms_two_rows_with_a_two_tile_central_aisle(self):
        chairs = tuple(item for item in self.placements if item[2] == "audience-seat")
        self.assertEqual(len(chairs), 10)
        self.assertEqual({item[6] for item in chairs}, {53, 55})
        self.assertEqual(
            {(item[5], item[6]) for item in chairs},
            {(48, 53), (50, 53), (60, 53), (62, 53)}
            | {(x, 55) for x in (48, 50, 52, 58, 60, 62)},
        )
        self.assertFalse(any(54 <= item[5] <= 57 for item in chairs))

        event_tables = tuple(item for item in self.placements if item[2] == "event-table")
        self.assertEqual(
            {(item[5], item[6]) for item in event_tables},
            {(52, 53), (58, 53)},
        )

    def test_lower_rooms_have_distinct_lounge_activity_and_reception_clusters(self):
        clusters = {item[3] for item in self.placements if item[6] >= 57}
        self.assertTrue({"west-lounge", "community-workshop", "help-point"} <= clusters)
        lower_entrance_anchors = {
            (item[5], item[6])
            for item in self.placements
            if item[6] >= 57 and item[2] != "community-notice"
        }
        self.assertFalse(any(x in {51, 52} and y >= 59 for x, y in lower_entrance_anchors))
        counters = tuple(
            item for item in self.placements
            if item[2] == "help-desk" and item[3] == "help-point"
        )
        self.assertEqual(len(counters), 2)
        self.assertEqual({item[4] for item in counters}, {
            "prop.office.counter_walnut_left",
            "prop.office.counter_walnut_right",
        })

    def test_every_community_asset_is_in_a_curated_catalog(self):
        catalogs = []
        for root in (authoring.V2_ROOT, authoring.V3_ROOT):
            payload = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
            catalogs.extend(payload["props"])
        curated = {item["asset_key"] for item in catalogs}
        self.assertTrue({item[4] for item in self.placements} <= curated)


if __name__ == "__main__":
    unittest.main()
