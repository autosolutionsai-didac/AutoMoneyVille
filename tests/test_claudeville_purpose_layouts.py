"""Focused invariants for Claudeville's purpose-first furnishing recipes."""

from __future__ import annotations

import json
import unittest
from dataclasses import fields
from pathlib import Path

from tools.mapgen import claudeville_purpose_layouts as layouts
from tools.mapgen.claudeville_interior_layouts import BUILDING_BOUNDS

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_BUILDINGS = {
    "Bank",
    "University",
    "Agent Academy",
    "Market",
    "Workshop",
    "Community Center",
    "Claudeville Cafe",
    "Library",
    "Post Office",
    "Town Hall",
}


class PurposeLayoutTests(unittest.TestCase):
    def test_data_contract_is_stable_and_complete(self):
        self.assertEqual(
            [field.name for field in fields(layouts.PurposeProp)],
            [
                "asset_key",
                "visual_x",
                "visual_y",
                "semantic_type",
                "zone",
                "blocks",
                "name",
            ],
        )
        self.assertEqual(
            [field.name for field in fields(layouts.SemanticObject)],
            ["zone", "type", "logical_tiles"],
        )
        self.assertEqual(
            [field.name for field in fields(layouts.AtlasStamp)],
            [
                "source_id",
                "source_rect",
                "destination",
                "target_layer",
                "blocker_policy",
            ],
        )
        self.assertEqual(set(layouts.PUBLIC_BUILDING_BOUNDS), PUBLIC_BUILDINGS)
        self.assertEqual(set(layouts.PURPOSE_PROPS), PUBLIC_BUILDINGS)
        self.assertEqual(set(layouts.SEMANTIC_OBJECTS), PUBLIC_BUILDINGS)
        self.assertTrue(all(layouts.PURPOSE_PROPS.values()))
        self.assertTrue(all(layouts.SEMANTIC_OBJECTS.values()))
        layouts.validate_layouts()

    def test_props_are_purposeful_unique_and_present_in_curated_atlas(self):
        props = [prop for values in layouts.PURPOSE_PROPS.values() for prop in values]
        identities = {(prop.asset_key, prop.visual_x, prop.visual_y) for prop in props}
        positions = {(prop.visual_x, prop.visual_y) for prop in props}
        self.assertEqual(len(identities), len(props))
        self.assertEqual(len(positions), len(props))
        forbidden_prefixes = ("prop.landscape.", "prop.garden.", "prop.street.")
        self.assertFalse(
            [
                prop.asset_key
                for prop in props
                if prop.asset_key.startswith(forbidden_prefixes)
            ]
        )
        self.assertNotIn("prop.post.truck", {prop.asset_key for prop in props})

        manifests = (
            REPO_ROOT / "output/claudeville/modern_pixels_v2/props.json",
            REPO_ROOT
            / "environment/frontend_server/static_dirs/assets/claudeville"
            / "visual_candidates/browser-full-town-v7/runtime/props.json",
        )
        manifest_path = next((path for path in manifests if path.is_file()), None)
        self.assertIsNotNone(manifest_path, "a curated prop manifest is required")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertFalse({prop.asset_key for prop in props} - set(payload["frames"]))

    def test_only_restricted_coherent_legacy_recipes_are_used(self):
        legacy = {
            stamp.source_rect
            for stamps in layouts.PURPOSE_STAMPS.values()
            for stamp in stamps
            if stamp.source_id == "legacy_the_ville"
        }
        self.assertEqual(
            legacy,
            {
                (108, 19, 8, 11),
                (118, 19, 7, 11),
                (72, 19, 12, 8),
                (78, 45, 14, 6),
                (53, 20, 10, 7),
                (56, 41, 4, 3),
                (56, 45, 8, 3),
                (110, 20, 6, 7),
            },
        )
        self.assertNotIn((56, 41, 16, 14), legacy)
        self.assertTrue(
            set(layouts.PURPOSE_STAMPS)
            <= {
                "University",
                "Agent Academy",
                "Market",
                "Bank",
                "Workshop",
                "Claudeville Cafe",
                "Library",
                "Post Office",
                "Town Hall",
            }
        )
        for stamps in layouts.PURPOSE_STAMPS.values():
            for stamp in stamps:
                if stamp.source_id == "legacy_the_ville":
                    self.assertEqual(stamp.target_layer, "source-layers")
                    self.assertEqual(stamp.blocker_policy, "preserve-collision")

    def test_workshop_and_cafe_have_specific_non_generic_furnishing(self):
        worksite = layouts.PURPOSE_STAMPS["Workshop"]
        self.assertEqual(
            [stamp.source_rect for stamp in worksite],
            [
                (8, 12, 2, 7),
                (3, 13, 5, 6),
                (28, 7, 4, 7),
                (14, 6, 3, 6),
                (7, 7, 2, 2),
            ],
        )
        self.assertTrue(
            all(stamp.source_id == "exteriors_worksite" for stamp in worksite)
        )
        self.assertTrue(
            all(stamp.target_layer == "Interior Furniture L1" for stamp in worksite)
        )
        self.assertTrue(
            all(stamp.blocker_policy == "preserve-collision" for stamp in worksite)
        )

        terrace = [
            prop
            for prop in layouts.PURPOSE_PROPS["Claudeville Cafe"]
            if prop.zone == "cafe.terrace"
        ]
        self.assertEqual(len(terrace), 6)
        self.assertEqual(
            sum("table" in (prop.semantic_type or "") for prop in terrace), 2
        )
        self.assertEqual(
            sum("chair" in (prop.semantic_type or "") for prop in terrace), 4
        )

    def test_high_value_civic_additions_replace_duplicate_or_generic_props(self):
        expected_stamps = {
            "Bank": {
                ("office_furniture", (0, 23, 2, 3), (16, 14)),
                ("office_furniture", (4, 23, 2, 3), (18, 14)),
            },
            "Post Office": {
                ("exteriors_post", (0, 13, 7, 4), (162, 45)),
            },
        }
        for building, expected in expected_stamps.items():
            actual = {
                (stamp.source_id, stamp.source_rect, stamp.destination)
                for stamp in layouts.PURPOSE_STAMPS[building]
            }
            self.assertEqual(actual, expected)
        self.assertNotIn("Town Hall", layouts.PURPOSE_STAMPS)

        library = layouts.PURPOSE_STAMPS["Library"]
        self.assertIn(
            ("legacy_the_ville", (56, 41, 4, 3), (122, 43)),
            {(stamp.source_id, stamp.source_rect, stamp.destination) for stamp in library},
        )
        self.assertIn(
            ("legacy_the_ville", (56, 45, 8, 3), (122, 48)),
            {(stamp.source_id, stamp.source_rect, stamp.destination) for stamp in library},
        )

        community = layouts.PURPOSE_PROPS["Community Center"]
        self.assertIn(
            ("prop.community.stage_small", 55, 49),
            {(prop.asset_key, prop.visual_x, prop.visual_y) for prop in community},
        )
        self.assertNotIn("prop.office.whiteboard", {prop.asset_key for prop in community})

        cafe_service = [
            prop for prop in layouts.PURPOSE_PROPS["Claudeville Cafe"]
            if prop.zone == "cafe.service"
        ]
        self.assertEqual([prop.asset_key for prop in cafe_service], ["prop.office.cash_register"])
        town_hall = layouts.PURPOSE_PROPS["Town Hall"]
        self.assertEqual(
            {
                (prop.asset_key, prop.visual_x, prop.visual_y)
                for prop in town_hall
                if prop.semantic_type == "council table"
            },
            {
                ("prop.office.table_walnut_long", 95, 88),
                ("prop.office.table_walnut_long", 99, 88),
            },
        )

        semantic_by_type = {
            (building, semantic.type): semantic.logical_tiles
            for building, entries in layouts.SEMANTIC_OBJECTS.items()
            for semantic in entries
        }
        self.assertEqual(semantic_by_type[("Bank", "archive cabinets")], ((8, 7), (9, 7)))
        self.assertEqual(semantic_by_type[("Workshop", "workbench")], ((10, 27),))
        self.assertEqual(
            semantic_by_type[("Post Office", "parcel sorting rack")],
            ((81, 23), (82, 23), (83, 23), (84, 23)),
        )
        self.assertEqual(
            semantic_by_type[("Town Hall", "council table")],
            ((47, 44), (49, 44)),
        )

    def test_civic_props_form_clear_functional_groups(self):
        academy = layouts.PURPOSE_PROPS["Agent Academy"]
        self.assertEqual(
            {
                (prop.visual_x, prop.visual_y)
                for prop in academy
                if prop.semantic_type == "student chair"
            },
            {(122, 18), (126, 18), (122, 23), (126, 23)},
        )
        self.assertEqual(
            {
                (prop.semantic_type, prop.visual_x, prop.visual_y)
                for prop in academy
                if prop.zone == "academy.lounge"
            },
            {
                ("lounge chair", 118, 29),
                ("lounge table", 120, 28),
                ("lounge sofa", 122, 29),
                ("water cooler", 124, 27),
            },
        )

        market = layouts.PURPOSE_PROPS["Market"]
        self.assertEqual(
            sum(prop.semantic_type == "checkout counter" for prop in market), 3
        )
        self.assertEqual(
            {
                (prop.visual_x, prop.visual_y)
                for prop in market
                if prop.semantic_type == "fresh food display"
            },
            {(153, 25), (154, 25), (157, 25), (158, 25)},
        )

        post = layouts.PURPOSE_PROPS["Post Office"]
        self.assertEqual(
            {
                (prop.asset_key, prop.visual_x, prop.visual_y, prop.blocks)
                for prop in post
                if prop.semantic_type in {"mail sorting table", "sorted mail"}
            },
            {
                ("prop.office.table_light", 164, 59, True),
                ("prop.office.table_light", 168, 59, True),
                ("prop.office.paper_stack", 164, 58, False),
                ("prop.office.paper_stack", 168, 58, False),
            },
        )

        self.assertEqual(layouts.ZONE_RECTS["academy.lounge"], (118, 24, 126, 32))
        self.assertEqual(layouts.ZONE_RECTS["hall.council"], (92, 83, 103, 91))

    def test_home_kitchens_stay_inside_their_distinct_home_shells(self):
        self.assertEqual(
            set(layouts.HOME_KITCHEN_STAMPS),
            {"Home 1", "Home 5", "Home 6", "Home 7", "Home 8", "Home 9", "Home 10"},
        )
        for home, stamps in layouts.HOME_KITCHEN_STAMPS.items():
            left, top, right, bottom = BUILDING_BOUNDS[home]
            for stamp in stamps:
                x, y = stamp.destination
                _sx, _sy, width, height = stamp.source_rect
                self.assertGreaterEqual(x, left)
                self.assertGreaterEqual(y, top)
                self.assertLessEqual(x + width, right)
                self.assertLessEqual(y + height, bottom)
                self.assertEqual(stamp.source_rect, (53, 18, 10, 3))
                self.assertEqual(stamp.blocker_policy, "preserve-collision")

    def test_front_approaches_and_clear_spawns_are_explicit(self):
        self.assertEqual(
            layouts.ENTRANCES,
            {
                "Bank": (9, 16),
                "University": (42, 16),
                "Agent Academy": (56, 16),
                "Market": (77, 16),
                "Workshop": (9, 31),
                "Community Center": (26, 31),
                "Claudeville Cafe": (50, 31),
                "Library": (59, 31),
                "Post Office": (80, 31),
                "Town Hall": (48, 37),
            },
        )
        self.assertEqual(
            layouts.SPAWNS,
            {
                "Bank": (9, 13),
                "University": (42, 12),
                "Agent Academy": (57, 12),
                "Market": (77, 13),
                "Workshop": (10, 28),
                "Community Center": (24, 30),
                "Claudeville Cafe": (49, 27),
                "Library": (60, 30),
                "Post Office": (80, 27),
                "Town Hall": (47, 39),
            },
        )
        blockers = {
            (prop.visual_x // 2, prop.visual_y // 2)
            for props in layouts.PURPOSE_PROPS.values()
            for prop in props
            if prop.blocks
        }
        self.assertFalse(set(layouts.ENTRANCES.values()) & blockers)
        self.assertFalse(set(layouts.SPAWNS.values()) & blockers)

    def test_semantic_objects_overlap_visible_prop_or_stamp_footprints(self):
        for building, semantic_objects in layouts.SEMANTIC_OBJECTS.items():
            visible = {
                (prop.visual_x // 2, prop.visual_y // 2)
                for prop in layouts.PURPOSE_PROPS[building]
            }
            for stamp in layouts.PURPOSE_STAMPS.get(building, ()):
                x, y = stamp.destination
                _sx, _sy, width, height = stamp.source_rect
                visible.update(
                    (tile_x // 2, tile_y // 2)
                    for tile_y in range(y, y + height)
                    for tile_x in range(x, x + width)
                )
            for semantic in semantic_objects:
                self.assertTrue(
                    set(semantic.logical_tiles) & visible,
                    f"{building}:{semantic.type} has no visible counterpart",
                )

    def test_data_module_remains_focused(self):
        root = Path(layouts.__file__).parent
        names = (
            "claudeville_purpose_layouts.py",
            "claudeville_purpose_types.py",
            "claudeville_purpose_props_north.py",
            "claudeville_purpose_props_south.py",
            "claudeville_purpose_semantics.py",
        )
        sources = [(root / name).read_text(encoding="utf-8") for name in names]
        for name, source in zip(names, sources, strict=True):
            self.assertLessEqual(len(source.splitlines()), 500, name)
        lowered = "\n".join(sources).lower()
        for legacy_name in (
            "banco",
            "universidad",
            "academia de agentes",
            "oficina de correos",
            "sala de acuerdos",
            "biblioteca",
            "oficina de gobierno",
        ):
            self.assertNotIn(legacy_name, lowered)


if __name__ == "__main__":
    unittest.main()
