"""Focused contracts for Claudeville's Tiled-first semantic profile."""

from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from tools.mapgen import author_claudeville_vertical_slices as slices
from tools.mapgen import build_tilemap
from tools.mapgen import claudeville_tiled_authoring as authoring
from tools.mapgen import compile_claudeville_semantics as compiler
from tools.mapgen import compose_claudeville_interiors as composer
from tools.mapgen import seed_claudeville_tiled_authoring as migration


def _layers() -> tuple[list[dict], dict[str, dict]]:
    data = [0] * (176 * 96)
    tile_layers = {
        name: {
            "id": index + 1, "name": name, "type": "tilelayer",
            "width": 176, "height": 96, "data": list(data), "visible": name != "Collisions",
        }
        for index, name in enumerate(build_tilemap.TILE_LAYERS)
    }
    object_layers = {
        name: {"id": 20 + index, "name": name, "type": "objectgroup", "objects": []}
        for index, name in enumerate(build_tilemap.OBJECT_LAYERS)
    }
    ordered = [
        *(tile_layers[name] for name in build_tilemap.TILE_LAYERS[:-1]),
        *(object_layers[name] for name in build_tilemap.OBJECT_LAYERS),
        tile_layers["Collisions"],
    ]
    return ordered, {**tile_layers, **object_layers}


def _candidate() -> dict:
    layers, lookup = _layers()
    for logical_x, logical_y in ((2, 2), (3, 2)):
        lookup["Interior Furniture L1"]["data"][(logical_y * 2) * 176 + logical_x * 2] = 1
    zones = [authoring.make_authoring_object(
        100, "test.service", 32, 32, width=128, height=128,
        sector="Test Hall", room_type="service",
    )]
    interactions = [authoring.make_authoring_object(
        101, "test.service-counter", 64, 64, width=32, height=32,
        sector="Test Hall", zone="test.service", interaction_type="service-counter",
        art_layer="Interior Furniture L1", allowed_room_types="service",
        blocker_policy="nonblocking", stance_x=2, stance_y=3,
    )]
    entrances = [authoring.make_authoring_object(
        102, "test.entrance", 32, 32, point=True, sector="Test Hall",
    )]
    spawns = [authoring.make_authoring_object(
        103, "test.spawn", 96, 96, point=True, sector="Test Hall",
        zone="test.service", spawn_name="test-hall",
    )]
    blockers = [authoring.make_authoring_object(
        104, "test.wall-blocker", 96, 64, width=32, height=32,
        sector="Test Hall", zone="test.service", art_layer="Interior Furniture L1",
        blocker_policy="require-blocked",
    )]
    layers.append(authoring.make_authoring_group(
        30, zones=zones, interactions=interactions, entrances=entrances,
        spawns=spawns, blockers=blockers,
    ))
    return {
        "width": 176, "height": 96, "tilewidth": 16, "tileheight": 16,
        "infinite": False, "orientation": "orthogonal", "layers": layers,
        "properties": [
            {
                "name": "authoring_profile", "type": "string",
                "value": authoring.PROFILE,
            },
            *(
                {"name": name, "type": "int", "value": revision}
                for name, revision in build_tilemap.V3_AUTHORING_REVISIONS.items()
            ),
        ],
        "tilesets": [
            {"firstgid": 1, "source": "terrain.tsj"},
            {"firstgid": 2, "source": "town.tsj"},
            {"firstgid": 3, "source": "office.tsj"},
            {"firstgid": 4, "source": "interiors_props.tsj"},
            {"firstgid": 5, "source": "room_arched_entryways.tsj"},
            {"firstgid": 6, "source": "room_floors.tsj"},
            {"firstgid": 7, "source": "room_walls.tsj"},
        ],
    }


def _spec() -> dict:
    return {
        "world_name": "Claudeville", "collision_block_id": "32125",
        "grid": {"maze_width": 88, "maze_height": 48, "sq_tile_size": 32},
        "sectors": [{"name": "Test Hall", "rect": [1, 1, 4, 4]}],
        "arenas": [], "objects": [], "spawns": [],
    }


def _collision() -> list[list[bool]]:
    result = [
        [x in (0, 87) or y in (0, 47) for x in range(88)] for y in range(48)
    ]
    result[2][3] = True
    return result


def _collision_csv(collision: list[list[bool]]) -> str:
    return ", ".join(
        "32125" if collision[y][x] else "0" for y in range(48) for x in range(88)
    )


class TiledAuthoringTests(unittest.TestCase):
    def test_candidate_contains_the_complete_revision_three_vertical_slices(self):
        source = json.loads(slices.DEFAULT_MAP.read_text(encoding="utf-8"))
        self.assertEqual(
            authoring.properties(source.get("properties")).get(
                "vertical_slice_revision"
            ),
            slices.SLICE_REVISION,
        )

        depth = next(
            layer for layer in source["layers"] if layer["name"] == "Depth Props"
        )
        actual = Counter()
        for item in depth["objects"]:
            values = authoring.properties(item.get("properties"))
            if values.get("sector") not in slices.TARGETS:
                continue
            actual[(
                values["sector"], values["zone"], values["asset_key"],
                item["x"], item["y"],
            )] += 1
        expected = Counter(
            (sector, zone, key, x * 16, y * 16)
            for sector, zone, _role, _cluster, key, x, y in slices.PLACEMENTS
        )
        self.assertEqual(actual, expected)

        group = next(
            layer for layer in source["layers"] if layer["name"] == authoring.GROUP_NAME
        )
        children = {layer["name"]: layer for layer in group["layers"]}
        zones = {
            authoring.properties(item.get("properties")).get("zone")
            for item in children["Zones"]["objects"]
        }
        self.assertIn("home_5.bathroom", zones)

        interactions = {
            authoring.properties(item.get("properties")).get("interaction"): (
                authoring.properties(item.get("properties"))
            )
            for item in children["Interactions"]["objects"]
        }
        bed_shapes = [
            item for item in children["Interactions"]["objects"]
            if authoring.properties(item.get("properties")).get("interaction")
            == "home_5.bedroom.bed-001"
        ]
        self.assertEqual(len(bed_shapes), 1)
        self.assertEqual(
            authoring.properties(bed_shapes[0].get("properties"))["semantic_id"],
            "home_5.bedroom.bed-001.shape-001",
        )
        toilet = interactions["home_5.bathroom.toilet-001"]
        self.assertEqual((toilet["stance_x"], toilet["stance_y"]), (32, 43))
        self.assertEqual(toilet["blocker_policy"], "require-blocked")
        cafe_counter = interactions["cafe.service.service-counter-001"]
        self.assertEqual(
            (cafe_counter["stance_x"], cafe_counter["stance_y"]),
            (49, 24),
        )
        blocker_ids = {
            authoring.properties(item.get("properties")).get("semantic_id")
            for item in children["Blockers"]["objects"]
        }
        self.assertIn("home_5.bedroom.wardrobe-blocker.shape-001", blocker_ids)

        compiled = compiler.compile_semantics(tmj_path=slices.DEFAULT_MAP)
        self.assertEqual(compiled.stats["collision_mismatches"], 0)
        self.assertGreaterEqual(compiled.stats["connectivity_pct"], 98)

    def test_compiles_without_changing_authoritative_collision(self):
        collision = _collision()
        result = authoring.compile_authoring(_candidate(), _spec(), collision)
        self.assertEqual(result.collision, tuple(tuple(row) for row in collision))
        self.assertEqual(result.stats["collision_mismatches"], 0)
        self.assertEqual(result.town_spec["_authoring_profile"], authoring.PROFILE)
        self.assertEqual(result.town_spec["objects"][0]["semantic_id"], "test.service-counter")
        self.assertFalse(result.town_spec["objects"][0]["blocks"])
        self.assertEqual(result.object_stances, ((2, 3),))
        self.assertEqual(
            len(result.collision_overrides["blocked"]) + len(result.collision_overrides["walkable"]),
            88 * 48,
        )

    def test_main_compiler_bypasses_legacy_layout_and_old_map_inputs(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            tmj, spec, collision = root / "town.tmj", root / "spec.json", root / "collision.csv"
            tmj.write_text(json.dumps(_candidate()), encoding="utf-8")
            spec.write_text(json.dumps(_spec()), encoding="utf-8")
            collision.write_text(_collision_csv(_collision()), encoding="utf-8")
            result = compiler.compile_semantics(
                tmj_path=tmj, spec_path=spec, collision_path=collision,
                overrides_path=root / "must-not-be-read.json",
                old_map_path=root / "must-not-be-read-either.json",
                layout=SimpleNamespace(),
            )
        self.assertEqual(result.stats["collision_mismatches"], 0)
        self.assertEqual(result.town_spec["required_zones"], [
            {"sector": "Test Hall", "arena": "test.service"},
        ])

    def test_rejects_off_grid_geometry_wrong_rooms_and_missing_art(self):
        off_grid = _candidate()
        off_grid["layers"][-1]["layers"][1]["objects"][0]["x"] = 65
        with self.assertRaisesRegex(authoring.TiledAuthoringError, "32px"):
            authoring.validate_authoring_group(off_grid)

        wrong_room = _candidate()
        properties = wrong_room["layers"][-1]["layers"][1]["objects"][0]["properties"]
        next(item for item in properties if item["name"] == "interaction_type")["value"] = "bed"
        with self.assertRaisesRegex(authoring.TiledAuthoringError, "not allowed"):
            authoring.validate_authoring_group(wrong_room)

        missing_art = _candidate()
        furniture = next(
            layer for layer in missing_art["layers"] if layer["name"] == "Interior Furniture L1"
        )
        furniture["data"] = [0] * (176 * 96)
        with self.assertRaisesRegex(authoring.TiledAuthoringError, "no linked visible art"):
            authoring.validate_authoring_group(missing_art)

    def test_builder_accepts_source_group_but_strips_it_from_runtime_layers(self):
        source = _candidate()
        layers = build_tilemap._validate_source(source)
        runtime = {
            "tile_gid_remap": {"1": 7},
            "tile_gid_flip_mask": 0xE0000000,
            "tile_gid_clear_mask": 0xF0000000,
        }
        compiled = build_tilemap._remap_layers(source, layers, runtime, [False] * (88 * 48), 9)
        self.assertEqual([layer["name"] for layer in compiled], list(build_tilemap.MAP_LAYER_ORDER))
        self.assertNotIn(authoring.GROUP_NAME, {layer["name"] for layer in compiled})

    def test_builder_accepts_v3_prop_collection_and_strips_authoring_gid(self):
        source = _candidate()
        depth = next(layer for layer in source["layers"] if layer["name"] == "Depth Props")
        depth["objects"].append({
            "id": 40,
            "gid": 4,
            "name": "test-prop",
            "type": "",
            "x": 64,
            "y": 64,
            "width": 16,
            "height": 16,
            "rotation": 0,
            "visible": True,
            "properties": [{
                "name": "asset_key",
                "type": "string",
                "value": "prop.interiors_v3.living.0001",
            }],
        })
        layers = build_tilemap._validate_source(source)
        runtime = {
            "tile_gid_remap": {"1": 7},
            "tile_gid_flip_mask": 0xE0000000,
            "tile_gid_clear_mask": 0xF0000000,
        }
        compiled = build_tilemap._remap_layers(
            source, layers, runtime, [False] * (88 * 48), 9
        )
        runtime_depth = next(layer for layer in compiled if layer["name"] == "Depth Props")
        self.assertNotIn("gid", runtime_depth["objects"][0])

    def test_legacy_composer_refuses_profile_before_writing(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "candidate.tmj", root / "output.tmj"
            source.write_text(json.dumps({
                "properties": [{"name": "authoring_profile", "value": authoring.PROFILE}],
            }), encoding="utf-8")
            with self.assertRaisesRegex(composer.CompositionError, "cannot use"):
                composer.compose(source, output)
            self.assertFalse(output.exists())

    def test_multiple_zone_rectangles_compile_as_one_canonical_arena(self):
        source = _candidate()
        group = source["layers"][-1]
        zones = group["layers"][0]["objects"]
        zones[0]["width"] = 64
        zones.append(authoring.make_authoring_object(
            105, "test.service.shape-002", 96, 32, width=64, height=128,
            zone="test.service", sector="Test Hall", room_type="service",
        ))
        result = authoring.compile_authoring(source, _spec(), _collision())
        self.assertEqual(len(result.town_spec["arenas"]), 1)
        self.assertEqual(result.town_spec["arenas"][0]["name"], "test.service")

    def test_one_time_migration_seeds_a_deterministic_valid_group(self):
        legacy = _candidate()
        legacy["layers"].pop()
        legacy["properties"] = []
        spec = _spec()
        spec.update({
            "arenas": [{
                "sector": "Test Hall", "name": "test.service", "rects": [[1, 1, 4, 4]],
            }],
            "objects": [{
                "sector": "Test Hall", "arena": "test.service",
                "type": "service counter", "tiles": [[2, 2]],
            }],
            "entrances": [{"sector": "Test Hall", "tile": [1, 1]}],
            "spawns": [{
                "sector": "Test Hall", "arena": "test.service",
                "name": "test-hall", "tile": [3, 3],
            }],
        })
        first = migration.seed_from_legacy_semantics(legacy, spec, _collision())
        second = migration.seed_from_legacy_semantics(legacy, spec, _collision())
        self.assertEqual(first, second)
        self.assertEqual(first["layers"][-1]["name"], authoring.GROUP_NAME)
        result = authoring.compile_authoring(first, spec, _collision())
        self.assertEqual(result.stats["objects"], 1)


if __name__ == "__main__":
    unittest.main()
