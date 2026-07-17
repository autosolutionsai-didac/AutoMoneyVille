"""Contracts for the explicit Claudeville district authoring passes."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

from tools.mapgen import author_claudeville_districts as districts
from tools.mapgen import claudeville_tiled_authoring as authoring


class DistrictAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(districts.DEFAULT_MAP.read_text(encoding="utf-8"))
        cls.model = authoring.validate_authoring_group(cls.source)
        cls.depth = next(
            layer for layer in cls.source["layers"] if layer["name"] == "Depth Props"
        )
        cls.authoring_group = next(
            layer for layer in cls.source["layers"]
            if layer["name"] == authoring.GROUP_NAME
        )

    def test_every_registered_district_matches_its_explicit_placement_table(self):
        source_properties = authoring.properties(self.source.get("properties"))
        for district, module in districts.DISTRICTS.items():
            with self.subTest(district=district):
                self.assertEqual(
                    source_properties[f"{district}_district_revision"],
                    module.REVISION,
                )
                actual = Counter()
                for item in self.depth["objects"]:
                    if not item.get("name", "").startswith(f"{district}-"):
                        continue
                    values = authoring.properties(item.get("properties"))
                    actual[(
                        values["sector"], values["zone"],
                        values["semantic_type"], values["purpose_cluster"],
                        values["asset_key"], item["x"], item["y"],
                    )] += 1
                expected = Counter(
                    (sector, zone, role, cluster, key, x * 16, y * 16)
                    for sector, zone, role, cluster, key, x, y in module.PLACEMENTS
                )
                self.assertEqual(actual, expected)

    def test_north_interactions_link_only_to_the_new_purposeful_objects(self):
        created_ids = {
            item["id"] for item in self.depth["objects"]
            if item.get("name", "").startswith("north-")
        }
        interactions = next(
            layer for layer in self.authoring_group["layers"]
            if layer["name"] == "Interactions"
        )
        north = []
        for item in interactions["objects"]:
            values = authoring.properties(item.get("properties"))
            if values.get("sector") not in districts.DISTRICTS["north"].TARGETS:
                continue
            north.append(values)
            self.assertEqual(values["art_layer"], "Depth Props")
            self.assertIn(values["art_object_id"], created_ids)
        self.assertEqual(len(north), 55)

    def test_north_uses_native_arches_and_removes_facade_door_objects(self):
        north = districts.DISTRICTS["north"]
        self.assertIn("room.arched_entryways", north.V3_TILE_SOURCES)
        self.assertFalse(any(
            placement[4].startswith("prop.facade.")
            for placement in north.PLACEMENTS
        ))

        arch_cells = {
            (x, y): tile
            for layer, x, y, tile in north.VISUAL_TILE_EDITS
            if layer == "Wall"
        }
        doors = {
            "Home 1": (52, 25),
            "University": (84, 31),
            "Agent Academy": (112, 31),
            "Market": (154, 31),
            "Post Office": (160, 61),
        }
        self.assertEqual(len(arch_cells), len(doors) * 4)
        for sector, (left, top) in doors.items():
            with self.subTest(sector=sector):
                self.assertEqual(
                    set(arch_cells) & {
                        (left, top), (left + 1, top),
                        (left, top + 1), (left + 1, top + 1),
                    },
                    {
                        (left, top), (left + 1, top),
                        (left, top + 1), (left + 1, top + 1),
                    },
                )

        self.assertIn(("Foreground L1", 73, 4, 100, 8, 0), north.TILE_FILLS)
        self.assertEqual(
            {(x, y) for layer, x, y, gid in north.TILE_EDITS
             if layer == "Wall" and gid == 0},
            set(north._UNIVERSITY_LEGACY_WALL_CELLS),
        )

    def test_north_rooms_have_purposeful_clusters_and_clear_entry_lanes(self):
        north = districts.DISTRICTS["north"]
        clusters = {
            sector: {placement[3] for placement in north.PLACEMENTS
                     if placement[0] == sector}
            for sector in north.TARGETS
        }
        expected = {
            "Home 1": {"media wall", "sink run", "washroom", "sleep", "potting garden"},
            "University": {"teaching wall", "research workstation", "service line", "west dining group"},
            "Agent Academy": {"simulator bay", "practical circuit", "front desk", "conversation set"},
            "Market": {"chilled wall", "dry-goods wall", "fresh produce", "west checkout"},
            "Post Office": {"service line", "continuous cubby wall", "label workstation", "waiting bay"},
        }
        for sector, required in expected.items():
            with self.subTest(sector=sector):
                self.assertTrue(required <= clusters[sector])

        reserved_lanes = {
            "Home 1": {(x, y) for x in (52, 53) for y in range(25, 27)},
            "University": {(x, y) for x in (84, 85) for y in range(24, 33)},
            "Agent Academy": {(x, y) for x in (112, 113) for y in range(25, 33)},
            "Market": {(x, y) for x in (154, 155) for y in range(29, 33)},
            "Post Office": {(x, y) for x in (160, 161) for y in range(55, 63)},
        }
        for sector, _zone, _role, _cluster, _key, x, y in north.PLACEMENTS:
            self.assertNotIn((x, y), reserved_lanes[sector])

        home_shell = next(shell for shell in north.VISUAL_SHELLS if shell[0] == "Home 1")
        self.assertEqual(home_shell[4], 26)
        self.assertTrue(all(
            placement[6] > home_shell[4]
            for placement in north.PLACEMENTS
            if placement[1] == "home_1.garden"
        ))

        role_counts = Counter(
            (sector, role) for sector, _zone, role, *_rest in north.PLACEMENTS
        )
        self.assertGreaterEqual(role_counts[("University", "lecture-seating")], 4)
        self.assertGreaterEqual(role_counts[("Agent Academy", "classroom-seating")], 4)
        self.assertGreaterEqual(role_counts[("Market", "stock-display")], 5)
        self.assertGreaterEqual(role_counts[("Post Office", "postal-counter")], 4)

    def test_north_structure_and_assets_validate_without_rewriting_the_map(self):
        north = districts.DISTRICTS["north"]
        catalog = json.loads(
            (districts.V3_ROOT / "catalog.json").read_text(encoding="utf-8")
        )
        records = {
            record["source_id"]: record
            for record in catalog["tilesets"]
            if record["source_id"] in north.V3_TILE_SOURCES
        }
        self.assertEqual(set(records), set(north.V3_TILE_SOURCES))

        firstgid = 1
        sources = {}
        for source_id in north.V3_TILE_SOURCES:
            record = records[source_id]
            sources[source_id] = {
                "columns": record["columns"], "firstgid": firstgid,
                "rows": record["rows"],
            }
            firstgid += record["columns"] * record["rows"]
        layers = {
            "Interior Ground": {"data": [0] * (176 * 96)},
            "Wall": {"data": [0] * (176 * 96)},
        }
        written = districts.semantics.paint_visual_structure(
            layers, north, sources,
        )
        self.assertGreater(written, 0)
        self.assertTrue(all(
            layers["Wall"]["data"][y * 176 + x]
            for _layer, x, y, _tile in north.VISUAL_TILE_EDITS
        ))

        available = {
            **districts._catalog(districts.V2_ROOT),
            **districts._catalog(districts.V3_ROOT),
        }
        requested = {placement[4] for placement in north.PLACEMENTS}
        self.assertTrue(requested <= available.keys())

    def test_north_removes_the_audited_legacy_office_shell_fragments(self):
        north = districts.DISTRICTS["north"]
        reference = next(
            item for item in self.source["tilesets"]
            if Path(item["source"]).stem == "office"
        )
        tileset = json.loads(
            (districts.DEFAULT_MAP.parent / reference["source"])
            .read_text(encoding="utf-8")
        )
        firstgid = reference["firstgid"]
        lastgid = firstgid + tileset["tilecount"]
        for layer in self.source["layers"]:
            if layer.get("type") != "tilelayer":
                continue
            for rects in north.SAFE_LEGACY_CLEAR_RECTS.values():
                for left, top, right, bottom in rects:
                    for y in range(top, bottom):
                        for x in range(left, right):
                            gid = (
                                layer["data"][y * self.source["width"] + x]
                                & 0x0FFFFFFF
                            )
                            self.assertFalse(firstgid <= gid < lastgid)

    def test_middle_workshop_uses_real_tiles_and_keeps_the_actor_lane_clear(self):
        middle = districts.DISTRICTS["middle"]
        furniture = next(
            layer for layer in self.source["layers"]
            if layer["name"] == "Interior Furniture L1"
        )
        left, top, right, bottom = middle.TARGET_BOUNDS["Workshop"]
        occupied = sum(
            bool(furniture["data"][y * self.source["width"] + x])
            for y in range(top, bottom) for x in range(left, right)
        )
        self.assertEqual(occupied, 85)
        self.assertTrue(all(
            not furniture["data"][y * self.source["width"] + x]
            for y in range(42, 48) for x in (18, 19)
        ))

    def test_middle_preserves_only_intentional_tile_backed_interactions(self):
        created_ids = {
            item["id"] for item in self.depth["objects"]
            if item.get("name", "").startswith("middle-")
        }
        interactions = next(
            layer for layer in self.authoring_group["layers"]
            if layer["name"] == "Interactions"
        )
        tile_backed = set()
        for item in interactions["objects"]:
            values = authoring.properties(item.get("properties"))
            if values.get("sector") not in districts.DISTRICTS["middle"].TARGETS:
                continue
            if values["art_layer"] == "Interior Furniture L1":
                tile_backed.add((values["sector"], values["interaction_type"]))
            else:
                self.assertEqual(values["art_layer"], "Depth Props")
                self.assertIn(values["art_object_id"], created_ids)
        self.assertEqual(tile_backed, {
            ("Workshop", "tool-storage"),
            ("Workshop", "work-machine"),
            ("Workshop", "workbench"),
        })

    def test_middle_layout_contract_uses_native_arches_and_safe_facade_clears(self):
        middle = districts.DISTRICTS["middle"]
        self.assertIn("room.arched_entryways", middle.V3_TILE_SOURCES)
        self.assertEqual(middle.TILE_FILLS, (
            ("Foreground L1", 48, 41, 64, 43, 0),
            ("Foreground L1", 116, 40, 127, 42, 0),
        ))
        self.assertFalse(any(
            placement[4].startswith("prop.facade.")
            for placement in middle.PLACEMENTS
        ))
        arches = {
            (layer, x, y, tile)
            for layer, x, y, tile in middle.VISUAL_TILE_EDITS
        }
        self.assertEqual({(x, y) for _layer, x, y, _tile in arches}, {
            (18, 61), (19, 61), (18, 62), (19, 62),
            (51, 61), (52, 61), (51, 62), (52, 62),
            (118, 62), (119, 62), (118, 63), (119, 63),
        })
        self.assertTrue(all(
            layer == "Wall" and tile[0] == "room.arched_entryways"
            for layer, _x, _y, tile in arches
        ))

    def test_district_clear_preserves_unowned_foreground_art(self):
        middle = districts.DISTRICTS["middle"]
        size = 176 * 96
        layers = [
            {"name": name, "type": "tilelayer", "data": [0] * size}
            for name in districts.CLEAR_TILE_LAYERS
        ]
        layers.extend((
            {"name": "Depth Props", "type": "objectgroup", "objects": []},
            {"name": "Overhead Props", "type": "objectgroup", "objects": []},
        ))
        by_name = {layer["name"]: layer for layer in layers}
        owned_facade = 41 * 176 + 48
        interior_cell = 50 * 176 + 46
        by_name["Foreground L1"]["data"][owned_facade] = 424242
        by_name["Foreground L1"]["data"][interior_cell] = 424242
        by_name["Foreground L2"]["data"][interior_cell] = 424242
        by_name["Interior Furniture L1"]["data"][interior_cell] = 424242

        cleared = districts._clear({"layers": layers}, middle)

        self.assertEqual(cleared["Foreground L1"]["data"][owned_facade], 0)
        self.assertEqual(cleared["Foreground L1"]["data"][interior_cell], 424242)
        self.assertEqual(cleared["Foreground L2"]["data"][interior_cell], 424242)
        self.assertEqual(cleared["Interior Furniture L1"]["data"][interior_cell], 0)

    def test_middle_layout_contract_insets_stage_and_builds_shelf_banks(self):
        middle = districts.DISTRICTS["middle"]
        stage = next(
            placement for placement in middle.PLACEMENTS
            if placement[4] == "prop.community.stage_small"
        )
        catalog = json.loads(
            (districts.V2_ROOT / "catalog.json").read_text(encoding="utf-8")
        )
        stage_record = next(
            item for item in catalog["props"]
            if item["asset_key"] == stage[4]
        )
        width, height = stage_record["native_size"]
        shell = next(
            item for item in middle.VISUAL_SHELLS
            if item[0] == "Community Center"
        )
        _sector, left, top, right, bottom, *_rest = shell
        stage_left = stage[5] - width / 32
        stage_right = stage[5] + width / 32
        stage_top = stage[6] - height / 16
        self.assertGreater(stage_left, left)
        self.assertLess(stage_right, right)
        self.assertGreater(stage_top, top)
        self.assertLess(stage[6], bottom)

        shelves = [
            placement for placement in middle.PLACEMENTS
            if placement[0] == "Library"
            and placement[2] in {"bookshelf", "east-bookshelf"}
        ]
        anchors = {(item[5], item[6]) for item in shelves}
        self.assertEqual(anchors, {
            (115, 47), (117, 47), (119, 47),
            (123, 47), (125, 47), (127, 47), (129, 47),
            (115, 53), (117, 53), (119, 53),
            (123, 53), (125, 53), (127, 53), (129, 53),
        })
        self.assertTrue(all(
            item[5] not in {120, 121} for item in middle.PLACEMENTS
            if item[0] == "Library" and item[6] <= 56
        ))
        self.assertEqual(
            next(run for run in middle.WALL_RUNS if run[0] == "Library"),
            ("Library", "horizontal", 56, 113, 130, (120, 121)),
        )

    def test_middle_layout_contract_preserves_the_functional_central_plaza(self):
        middle = districts.DISTRICTS["middle"]
        self.assertNotIn("Central Plaza", middle.TARGETS)
        left, top, right, bottom = middle.PRESERVED_PLAZA_BOUNDS
        actual = set()
        for item in self.depth["objects"]:
            x, y = item.get("x", -1) / 16, item.get("y", -1) / 16
            if not (left <= x < right and top <= y <= bottom):
                continue
            values = authoring.properties(item.get("properties"))
            key = values.get("asset_key")
            if isinstance(key, str):
                actual.add(key)
        self.assertTrue(middle.PRESERVED_PLAZA_ASSETS <= actual)

    def test_south_migrations_replace_only_the_declared_semantic_cells(self):
        south = districts.DISTRICTS["south"]
        created_ids = {
            item["id"] for item in self.depth["objects"]
            if item.get("name", "").startswith("south-")
        }
        interactions = self.model.by_layer["Interactions"]
        for sector, interaction_id, removed, retained in (
            south.INTERACTION_SHAPE_REMOVALS
        ):
            cells = set().union(*(
                item.cells for item in interactions
                if item.properties.get("sector") == sector
                and item.properties.get("interaction") == interaction_id
            ))
            self.assertNotIn(removed, cells)
            self.assertIn(retained, cells)

        for sector, zone, semantic_id, kind, cells, stance, _key, policy in (
            south.INTERACTION_ADDITIONS
        ):
            parts = [
                item for item in interactions
                if item.properties.get("interaction") == semantic_id
            ]
            self.assertEqual(set().union(*(item.cells for item in parts)), set(cells))
            for item in parts:
                self.assertEqual(item.properties["sector"], sector)
                self.assertEqual(item.properties["zone"], zone)
                self.assertEqual(item.properties["interaction_type"], kind)
                self.assertEqual(
                    (item.properties["stance_x"], item.properties["stance_y"]),
                    stance,
                )
                self.assertEqual(item.properties["blocker_policy"], policy)
                self.assertIn(item.properties["art_object_id"], created_ids)

        blockers = self.model.by_layer["Blockers"]
        expected_blockers = sum(
            len(cells) for _sector, _zone, _semantic_id, cells, _key, _policy
            in south.BLOCKER_ADDITIONS
        )
        migrated = [
            item for item in blockers if ".south-shape-" in item.semantic_id
        ]
        self.assertEqual(len(migrated), expected_blockers)
        self.assertTrue(all(
            item.properties["art_object_id"] in created_ids for item in migrated
        ))

    def test_south_zone_transfer_and_native_room_structure_are_exact(self):
        south = districts.DISTRICTS["south"]
        self.assertNotIn((65, 41), self.model.zones["home_8.living_room"].cells)
        self.assertIn((65, 41), self.model.zones["home_8.bathroom"].cells)
        self.assertEqual(south.FLOOR_STAMPS, ())
        floor = next(
            layer for layer in self.source["layers"]
            if layer["name"] == "Interior Ground"
        )["data"]
        walls = next(
            layer for layer in self.source["layers"] if layer["name"] == "Wall"
        )["data"]
        sources = {}
        for reference in self.source["tilesets"]:
            path = (districts.DEFAULT_MAP.parent / reference["source"]).resolve()
            tileset = json.loads(path.read_text(encoding="utf-8"))
            values = authoring.properties(tileset.get("properties"))
            if values.get("source_id") in south.V3_TILE_SOURCES:
                sources[values["source_id"]] = (
                    reference["firstgid"], tileset["columns"],
                )

        def gid(reference):
            source, row, column = reference
            firstgid, columns = sources[source]
            return firstgid + row * columns + column

        self.assertEqual(set(sources), set(south.V3_TILE_SOURCES))
        room_rects = {}
        for sector, left, top, right, bottom, reference in south.ROOM_FLOOR_RECTS:
            room_rects.setdefault(sector, []).append((left, top, right, bottom))
            expected = gid(reference)
            for y in range(top, bottom + 1):
                for x in range(left, right + 1):
                    self.assertEqual(floor[y * 176 + x], expected)

        style = {name: gid(reference) for name, reference in south.WALL_TILE_STYLE.items()}
        for sector, left, top, right, bottom, door_left, door_right, pattern in (
            south.VISUAL_SHELLS
        ):
            base = gid(south.FLOOR_PATTERNS[pattern][0][0])
            candidates = (
                (x, y) for y in range(top + 1, bottom)
                for x in range(left + 1, right)
                if not any(
                    rect_left <= x <= rect_right and rect_top <= y <= rect_bottom
                    for rect_left, rect_top, rect_right, rect_bottom
                    in room_rects.get(sector, ())
                )
            )
            x, y = next(candidates)
            self.assertEqual(floor[y * 176 + x], base)
            self.assertEqual(walls[top * 176 + left], style["top_left"])
            self.assertEqual(walls[top * 176 + right], style["top_right"])
            self.assertEqual(walls[(top + 1) * 176 + left], style["left"])
            self.assertEqual(walls[(top + 1) * 176 + right], style["right"])
            horizontal_x = next(
                value for value in range(left + 1, right)
                if not door_left <= value <= door_right
            )
            self.assertEqual(walls[top * 176 + horizontal_x], style["horizontal"])

if __name__ == "__main__":
    unittest.main()
