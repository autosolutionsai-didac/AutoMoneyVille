"""Semantic identity checks for hand-authored Claudeville furniture."""

from __future__ import annotations

import unittest

from tools.mapgen import (
    claudeville_north_placements as north,
)
from tools.mapgen import (
    claudeville_south_placements as south,
)
from tools.mapgen import (
    claudeville_vertical_slice_layouts as slices,
)

TABLE_ROLES = {"common-room-table", "dining-table", "terrace-table"}
KNOWN_SEATING = {
    "prop.interiors_v3.bedroom.0424",
    "prop.interiors_v3.living.0003",
    "prop.interiors_v3.living.0004",
    "prop.interiors_v3.living.0006",
}


class ClaudevilleAssetRoleTests(unittest.TestCase):
    def test_table_semantics_never_use_known_seating_art(self):
        placements = slices.PLACEMENTS + north.PLACEMENTS + south.PLACEMENTS
        offenders = [
            item for item in placements
            if item[2] in TABLE_ROLES and item[4] in KNOWN_SEATING
        ]
        self.assertEqual(offenders, [])

    def test_cafe_service_line_uses_the_real_modern_interiors_counter(self):
        counters = [
            item for item in slices.PLACEMENTS
            if item[0] == "Claudeville Cafe" and item[2] == "service-counter"
        ]
        self.assertEqual(len(counters), 4)
        self.assertEqual(
            {item[4] for item in counters},
            {
                "prop.interiors_v3.ice_cream.0100",
                "prop.interiors_v3.ice_cream.0101",
                "prop.interiors_v3.ice_cream.0102",
            },
        )

    def test_bank_waiting_seats_are_seats_and_side_table_is_support(self):
        waiting = [
            item for item in slices.PLACEMENTS
            if item[0] == "Bank" and item[3] == "waiting"
        ]
        seats = [item for item in waiting if item[2] == "waiting-seating"]
        support = [item for item in waiting if item[2] == "side-table"]
        self.assertEqual(len(seats), 2)
        self.assertNotIn("prop.office.side_table", {item[4] for item in seats})
        self.assertEqual([item[4] for item in support], ["prop.office.side_table"])

    def test_cafe_staff_stance_and_prep_cluster_do_not_compete_for_floor(self):
        self.assertEqual(
            slices.INTERACTION_STANCE_UPDATES,
            (("Claudeville Cafe", "cafe.service.service-counter-001", 49, 24),),
        )
        cafe = [item for item in slices.PLACEMENTS if item[0] == "Claudeville Cafe"]
        self.assertIn(
            ("cooking-area", "prep island", 100, 48),
            {(item[2], item[3], item[5], item[6]) for item in cafe},
        )
        coffee = next(item for item in cafe if item[4] == "prop.office.coffee_station")
        support = next(item for item in cafe if item[4] == "prop.interiors_v3.kitchen.0195")
        self.assertEqual((coffee[5], coffee[6]), (support[5], support[6] - 1))


if __name__ == "__main__":
    unittest.main()
