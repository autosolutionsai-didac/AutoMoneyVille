"""Regression contracts for Claudeville's paid Modern Interiors composition."""

from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.claudeville_composition_support import (
    cells_in,
    derive_homes,
    layer_lookup,
    load_map,
    logical_clear_cells,
    reachable,
)
from tools.mapgen import claudeville_circulation_cells as circulation
from tools.mapgen import claudeville_entry_paths as entry_paths
from tools.mapgen import claudeville_home_stances as home_stances
from tools.mapgen import claudeville_purpose_layouts as purpose
from tools.mapgen import compile_claudeville_semantics as semantic_compiler
from tools.mapgen import compose_claudeville_interiors as composer
from tools.mapgen.claudeville_home_semantics import HOME_ENTRANCES
from tools.mapgen.claudeville_interior_layouts import HOMES, SOURCE_TEMPLATES

INTERIOR_TILE_LAYERS = (
    "Interior Ground",
    "Wall",
    "Interior Furniture L1",
    "Interior Furniture L2",
    "Foreground L1",
    "Foreground L2",
)
FURNITURE_LAYERS = INTERIOR_TILE_LAYERS[2:]
EXTERIOR_LAYERS = (
    "Bottom Ground",
    "Exterior Ground",
    "Exterior Decoration L1",
    "Exterior Decoration L2",
    "Overhead Props",
)
PRESERVED_LAYERS = (*EXTERIOR_LAYERS, "Interior Ground", "Wall")
ENTRY_MUTATED_LAYERS = {
    "Exterior Ground",
    "Interior Ground",
    "Wall",
    *entry_paths.PUBLIC_TILE_LAYERS,
}
ENTRY_PATH_INDICES = frozenset(
    y * composer.WIDTH + x
    for entry in entry_paths.ENTRY_PATHS.values()
    for rect in (*entry.interior, *entry.exterior, *entry.floor)
    for x, y in entry_paths.cells(rect)
) | frozenset(
    (2 * item.point[1] + dy) * composer.WIDTH + 2 * item.point[0] + dx
    for items in home_stances.HOME_STANCE_CELLS.values()
    for item in items
    for dy in (0, 1)
    for dx in (0, 1)
) | frozenset(
    (2 * point[1] + dy) * composer.WIDTH + 2 * point[0] + dx
    for points in circulation.CIRCULATION_CELLS.values()
    for point in points
    for dy in (0, 1)
    for dx in (0, 1)
)

class ClaudevilleInteriorCompositionTests(unittest.TestCase):
    @unittest.skipUnless(
        composer.AUTHORING_ROOT.is_dir(),
        "licensed Modern Interiors authoring cache not generated",
    )
    def test_composition_is_deterministic_and_preserves_exterior_layers(self):
        before_bytes = composer.SOURCE_MAP.read_bytes()
        before = load_map()
        before_layers = layer_lookup(before)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first, second = root / "first.tmj", root / "second.tmj"
            first_stats = composer.compose(composer.SOURCE_MAP, first)
            second_stats = composer.compose(composer.SOURCE_MAP, second)
            self.assertEqual(first_stats, second_stats)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            composed_once = first.read_bytes()
            composer.compose(first, first)
            self.assertEqual(first.read_bytes(), composed_once)
            composed_layers = layer_lookup(load_map(first))
            for name in PRESERVED_LAYERS:
                with self.subTest(layer=name):
                    if name not in ENTRY_MUTATED_LAYERS:
                        self.assertEqual(composed_layers[name], before_layers[name])
                        continue
                    self.assertEqual(
                        [
                            value
                            for index, value in enumerate(composed_layers[name]["data"])
                            if index not in ENTRY_PATH_INDICES
                        ],
                        [
                            value
                            for index, value in enumerate(before_layers[name]["data"])
                            if index not in ENTRY_PATH_INDICES
                        ],
                    )
        self.assertEqual(composer.SOURCE_MAP.read_bytes(), before_bytes)

    @unittest.skipUnless(composer.AUTHORING_ROOT.is_dir(), "authoring cache missing")
    def test_entry_paths_are_clear_ground_and_connect_public_spawns(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "entries.tmj"
            composer.compose(composer.SOURCE_MAP, output)
            layers = layer_lookup(load_map(output))
        for sector, entry in entry_paths.ENTRY_PATHS.items():
            for layer_name, rects in (
                ("Interior Ground", (*entry.interior, *entry.floor)),
                ("Exterior Ground", entry.exterior),
            ):
                for rect in rects:
                    for x, y in entry_paths.cells(rect):
                        index = y * composer.WIDTH + x
                        with self.subTest(sector=sector, cell=(x, y)):
                            self.assertTrue(layers[layer_name]["data"][index])
                            self.assertFalse(layers["Wall"]["data"][index])
                            self.assertFalse(any(
                                layers[name]["data"][index]
                                for name in entry_paths.PUBLIC_TILE_LAYERS
                            ))
        for sector, points in circulation.CIRCULATION_CELLS.items():
            for logical_x, logical_y in points:
                for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                    index = (2 * logical_y + dy) * composer.WIDTH + 2 * logical_x + dx
                    with self.subTest(sector=sector, circulation=(logical_x, logical_y)):
                        self.assertTrue(layers["Interior Ground"]["data"][index])
                        self.assertFalse(layers["Wall"]["data"][index])
                        self.assertFalse(any(
                            layers[name]["data"][index]
                            for name in entry_paths.PUBLIC_TILE_LAYERS
                        ))
        entrances = {**purpose.ENTRANCES, **HOME_ENTRANCES}
        self.assertEqual(set(entry_paths.ENTRY_PATHS), set(entrances))
        for sector, (x, y) in entrances.items():
            clear = logical_clear_cells(
                layers, entry_paths.ENTRY_PATHS[sector].bounds
            )
            with self.subTest(sector=sector, entrance=(x, y)):
                self.assertIn((x, y), clear)
                if sector in purpose.SPAWNS:
                    self.assertIn(purpose.SPAWNS[sector], reachable((x, y), clear))
        academy_clear = logical_clear_cells(
            layers, entry_paths.ENTRY_PATHS["Agent Academy"].bounds
        )
        academy_clear -= {
            point
            for item in purpose.SEMANTIC_OBJECTS["Agent Academy"]
            for point in item.logical_tiles
        }
        academy_reachable = reachable(purpose.ENTRANCES["Agent Academy"], academy_clear)
        self.assertTrue(
            academy_reachable
            & {(58, 14), (60, 14), (59, 13), (59, 15)}
        )
        homes = derive_homes(layers)
        for sector, entrance in HOME_ENTRANCES.items():
            clear = logical_clear_cells(
                layers, entry_paths.ENTRY_PATHS[sector].bounds
            )
            functional = {
                point
                for item in homes.objects[sector]
                for point in item.logical_tiles
            }
            clear -= functional
            primary = {
                point
                for zone, points in homes.zones.items()
                if homes.owners[zone] == sector
                and zone.rsplit(".", 1)[-1] in {
                    "bedroom", "living_room", "main_room"
                }
                for point in points
            }
            candidates = dict.fromkeys((
                *homes.spawn_candidates[sector],
                *homes.preferred_spawn_cells[sector],
            ))
            valid = set(candidates) & primary & clear
            with self.subTest(sector=sector, entrance=entrance):
                self.assertTrue(valid & reachable(entrance, clear))

    @unittest.skipUnless(composer.AUTHORING_ROOT.is_dir(), "authoring cache missing")
    def test_south_entries_face_the_street_and_rear_doors_are_closed(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "north-facing.tmj"
            composer.compose(composer.SOURCE_MAP, output)
            layers = layer_lookup(load_map(output))
        entrances = {**purpose.ENTRANCES, **HOME_ENTRANCES}
        for sector, point in entry_paths.SOUTH_FRONT_ENTRANCES.items():
            visual_x = 2 * point[0]
            entry = entry_paths.ENTRY_PATHS[sector]
            with self.subTest(sector=sector):
                self.assertEqual(entrances[sector], point)
                self.assertEqual(point[1], 37)
                self.assertEqual(entry.exterior, ((visual_x, 71, visual_x + 2, 75),))
                self.assertTrue(any(
                    left <= visual_x and visual_x + 2 <= right and top <= 75 < bottom
                    for left, top, right, bottom in entry.interior
                ))
                for y in (74, 75):
                    for x in (visual_x, visual_x + 1):
                        index = y * composer.WIDTH + x
                        self.assertTrue(any(
                            layers[name]["data"][index]
                            for name in (
                                "Bottom Ground", "Exterior Ground", "Interior Ground"
                            )
                        ))
                        self.assertFalse(any(
                            layers[name]["data"][index]
                            for name in ("Wall", *entry_paths.PUBLIC_TILE_LAYERS)
                        ))
        for rect in entry_paths.SOUTH_REAR_PATHS.values():
            self.assertFalse(any(
                layers["Exterior Ground"]["data"][y * composer.WIDTH + x]
                for x, y in entry_paths.cells(rect)
            ))
        for rect, _source in entry_paths.SOUTH_REAR_WALL_REPAIRS:
            self.assertTrue(all(
                layers["Wall"]["data"][y * composer.WIDTH + x]
                for x, y in entry_paths.cells(rect)
            ))

    @unittest.skipUnless(composer.AUTHORING_ROOT.is_dir(), "authoring cache missing")
    def test_every_home_object_has_one_reachable_cardinal_stance(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "stances.tmj"
            composer.compose(composer.SOURCE_MAP, output)
            layers = layer_lookup(load_map(output))
            compilation = semantic_compiler.compile_semantics(tmj_path=output)
        homes = derive_homes(layers)
        recipes = [
            (sector, item)
            for sector, items in home_stances.HOME_STANCE_CELLS.items()
            for item in items
        ]
        keys = [(sector, item.zone, item.object_type) for sector, item in recipes]
        self.assertEqual(len(keys), len(set(keys)))
        object_cells = {
            point
            for objects in homes.objects.values()
            for item in objects
            for point in item.logical_tiles
        }
        for sector, recipe in recipes:
            matches = [
                item
                for item in homes.objects[sector]
                if (item.zone, item.type) == (recipe.zone, recipe.object_type)
            ]
            with self.subTest(sector=sector, object=recipe.object_type):
                self.assertEqual(len(matches), 1)
                self.assertNotIn(recipe.point, object_cells)
                self.assertTrue(any(
                    abs(recipe.point[0] - x) + abs(recipe.point[1] - y) == 1
                    for x, y in matches[0].logical_tiles
                ))
                self.assertIn(recipe.point, set().union(*(
                    points
                    for zone, points in homes.zones.items()
                    if homes.owners[zone] == sector
                )))
        self.assertEqual(
            compilation.stats["stances"], compilation.stats["objects"]
        )

    def test_entry_corridors_do_not_contain_blocking_purpose_props(self):
        corridor_cells = {
            point
            for entry in entry_paths.ENTRY_PATHS.values()
            for rect in (*entry.interior, *entry.exterior)
            for point in entry_paths.cells(rect)
        }
        blockers = {
            (item.visual_x, item.visual_y)
            for items in purpose.PURPOSE_PROPS.values()
            for item in items
            if item.blocks
        }
        self.assertFalse(corridor_cells & blockers)
        self.assertNotIn(
            (113, 45, 12, 10),
            {
                stamp.source_rect
                for stamp in purpose.PURPOSE_STAMPS["Agent Academy"]
            },
        )
        lounge = purpose.ZONE_RECTS["academy.lounge"]
        self.assertTrue(all(
            lounge[0] <= item.visual_x < lounge[2]
            and lounge[1] <= item.visual_y < lounge[3]
            for item in purpose.PURPOSE_PROPS["Agent Academy"]
            if item.zone == "academy.lounge"
        ))

    def test_source_uses_a_fourth_paid_interiors_atlas_and_no_free_assets(self):
        map_data = load_map()
        tilesets = [
            (entry["firstgid"], Path(entry["source"]).stem)
            for entry in map_data["tilesets"]
        ]
        self.assertEqual(
            [name for _firstgid, name in tilesets],
            ["terrain", "town", "office", "interiors"],
        )
        self.assertEqual(tilesets[-1][0], 38214)
        serialized = json.dumps(map_data, ensure_ascii=False).casefold()
        self.assertNotIn("modern_interiors_free", serialized)
        self.assertNotIn("interiors_free", serialized)

    def test_existing_interiors_tileset_path_firstgid_and_order_are_pinned(self):
        source = load_map()
        mutations = (
            ("path", lambda value: value["tilesets"][-1].update({"source": "../interiors.tsj"})),
            ("firstgid", lambda value: value["tilesets"][-1].update({"firstgid": 38213})),
            ("order", lambda value: value["tilesets"].reverse()),
        )
        for label, mutate in mutations:
            tampered = deepcopy(source)
            mutate(tampered)
            with self.subTest(label=label), self.assertRaisesRegex(
                composer.CompositionError, "paths, firstgids or order"
            ):
                composer._add_interiors_tileset(tampered, 18711)

    def test_legacy_split_image_paths_are_contained(self):
        with self.assertRaisesRegex(composer.CompositionError, "escapes"):
            composer._contained_old_image("../claudeville_full_town_v2.tmj")

    def test_all_ten_homes_have_distinct_composed_signatures(self):
        layers = layer_lookup(load_map())
        signatures: dict[str, str] = {}
        for home in HOMES:
            left, top, right, bottom = home.bounds
            payload: list[object] = [right - left, bottom - top]
            occupied: set[tuple[int, int]] = set()
            for name in INTERIOR_TILE_LAYERS:
                values = []
                for x, y, index in cells_in(home.bounds):
                    gid = layers[name]["data"][index]
                    values.append(gid)
                    if name in FURNITURE_LAYERS and gid:
                        occupied.add((x - left, y - top))
                payload.append(values)
            with self.subTest(home=home.name):
                self.assertGreaterEqual(len(occupied), 34)
            signatures[home.name] = hashlib.sha256(
                json.dumps(payload, separators=(",", ":")).encode()
            ).hexdigest()
        self.assertEqual(len(signatures), 10)
        self.assertEqual(len(set(signatures.values())), 10, signatures)

    @unittest.skipUnless(composer.AUTHORING_ROOT.is_dir(), "authoring cache missing")
    def test_declared_purpose_props_are_rebuilt_exactly_once(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "purpose.tmj"
            composer.compose(composer.SOURCE_MAP, output)
            objects = layer_lookup(load_map(output))["Depth Props"]["objects"]
        rebuilt = []
        purpose_ids = []
        for obj in objects:
            values = composer._properties(obj.get("properties"))
            if not str(values.get("purpose_id", "")).startswith(composer.PURPOSE_ID_PREFIX):
                continue
            purpose_ids.append((values["purpose_id"], obj["id"]))
            rebuilt.append((
                values["sector"], values["asset_key"], obj["x"] // 16, obj["y"] // 16,
                values["semantic_type"], values["zone"], values["blocks"],
            ))
        expected = [
            (sector, item.asset_key, item.visual_x, item.visual_y, item.semantic_type,
             item.zone, item.blocks)
            for sector, items in purpose.PURPOSE_PROPS.items() for item in items
        ]
        self.assertCountEqual(rebuilt, expected)
        self.assertEqual(len(purpose_ids), len({value for value, _id in purpose_ids}))
        self.assertEqual(
            {object_id for _value, object_id in purpose_ids},
            set(range(composer.PURPOSE_OBJECT_ID_BASE,
                      composer.PURPOSE_OBJECT_ID_BASE + len(expected))),
        )

    @unittest.skipUnless(composer.AUTHORING_ROOT.is_dir(), "authoring cache missing")
    def test_public_rebuild_clears_all_legacy_tiles_and_depth_props(self):
        source = load_map()
        layers = layer_lookup(source)
        sentinel = 999_999
        for bounds in purpose.PUBLIC_BUILDING_BOUNDS.values():
            x, y = bounds[:2]
            for name in FURNITURE_LAYERS:
                layers[name]["data"][y * composer.WIDTH + x] = sentinel
        fake_id = 9000
        for bounds in (*purpose.PUBLIC_BUILDING_BOUNDS.values(),
                       *purpose.TERRACE_BOUNDS.values()):
            x, y = bounds[:2]
            layers["Depth Props"]["objects"].append({
                "id": fake_id, "name": "Static heart figure", "type": "",
                "x": x * 16, "y": y * 16, "properties": [{
                    "name": "asset_key", "type": "string", "value": "prop.bad.static_heart"
                }],
            })
            fake_id += 1
        with TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            mutated, output = temporary / "mutated.tmj", temporary / "output.tmj"
            mutated.write_text(json.dumps(source), encoding="utf-8")
            composer.compose(mutated, output)
            composed = layer_lookup(load_map(output))
        for bounds in purpose.PUBLIC_BUILDING_BOUNDS.values():
            for name in FURNITURE_LAYERS:
                self.assertNotIn(sentinel, (
                    composed[name]["data"][index] for _x, _y, index in cells_in(bounds)
                ))
        serialized_props = json.dumps(composed["Depth Props"], ensure_ascii=False).casefold()
        self.assertNotIn("static_heart", serialized_props)

    def test_only_restricted_legacy_templates_and_declared_kitchens_are_used(self):
        approved_public_rects = {
            (108, 19, 8, 11), (118, 19, 7, 11), (72, 19, 12, 8),
            (113, 45, 12, 10), (78, 45, 14, 6), (53, 20, 10, 7),
            (56, 41, 4, 3), (56, 45, 8, 3), (110, 20, 6, 7),
        }
        purpose_stamps = [
            stamp for stamps in purpose.PURPOSE_STAMPS.values() for stamp in stamps
            if stamp.source_id == "legacy_the_ville"
        ]
        self.assertTrue(purpose_stamps)
        self.assertTrue(purpose.FORBIDDEN_TEMPLATE_NAMES.isdisjoint(SOURCE_TEMPLATES))
        self.assertLessEqual(
            {stamp.source_rect for stamp in purpose_stamps}, approved_public_rects
        )
        for home, stamps in purpose.HOME_KITCHEN_STAMPS.items():
            with self.subTest(home=home):
                self.assertIn(home, {item.name for item in HOMES})
                self.assertTrue(stamps)
                self.assertTrue(all(
                    stamp.source_id == "legacy_the_ville"
                    and stamp.target_layer == "source-layers"
                    for stamp in stamps
                ))

if __name__ == "__main__":
    unittest.main()
