"""Focused contracts for deterministic Claudeville semantic compilation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from tests.claudeville_composition_support import legacy_v2_sector_cells
from tools.mapgen import claudeville_home_semantics as homes
from tools.mapgen import claudeville_home_stances as home_stances
from tools.mapgen import claudeville_purpose_layouts as real_layout
from tools.mapgen import claudeville_scenery_blocks as scenery
from tools.mapgen import claudeville_semantic_graph as semantic_graph
from tools.mapgen import compile_claudeville_semantics as compiler
from tools.mapgen.claudeville_interior_layouts import SOURCE_TEMPLATES, Stamp

LEGACY_TMJ = compiler.WORLD_ROOT / "visuals/claudeville_full_town_v2.tmj"


def _tile_layers() -> dict[str, dict]:
    names = ("Interior Ground", "Exterior Ground", *compiler.VISIBLE_BLOCKER_LAYERS)
    return {
        name: {
            "name": name,
            "type": "tilelayer",
            "width": 176,
            "height": 96,
            "data": [0] * (176 * 96),
        }
        for name in names
    }


def _tmj() -> dict:
    layers = _tile_layers()
    ground = layers["Interior Ground"]["data"]
    for y in range(2, 10):
        for x in range(2, 10):
            ground[y * 176 + x] = 1
    return {
        "width": 176,
        "height": 96,
        "tilewidth": 16,
        "tileheight": 16,
        "layers": list(layers.values()),
    }


def _layout(**changes):
    zone = "test.service"
    values = {
        "ZONE_RECTS": {zone: (2, 2, 10, 10)},
        "PUBLIC_BUILDING_BOUNDS": {"Test Hall": (2, 2, 10, 10)},
        "PURPOSE_PROPS": {
            "Test Hall": (
                SimpleNamespace(zone=zone, blocks=True, visual_x=4, visual_y=4),
                SimpleNamespace(zone=zone, blocks=True, visual_x=6, visual_y=6),
            )
        },
        "PURPOSE_STAMPS": {"Test Hall": ()},
        "HOME_KITCHEN_STAMPS": {},
        "SEMANTIC_OBJECTS": {
            "Test Hall": (
                SimpleNamespace(zone=zone, type="counter", logical_tiles=((2, 2),)),
            )
        },
        "ENTRANCES": {"Test Hall": (1, 4)},
        "SPAWNS": {"Test Hall": (2, 3)},
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _spec() -> dict:
    return {
        "_generated_by": "obsolete",
        "world_name": "Claudeville",
        "address_alias_manifest": "legacy_address_aliases.v1.json",
        "collision_block_id": "32125",
        "grid": {"maze_width": 88, "maze_height": 48, "sq_tile_size": 32},
        "sectors": [{"name": "Test Hall", "rect": [1, 1, 4, 4]}],
        "arenas": [{"sector": "Test Hall", "name": "old", "rect": [1, 1, 1, 1]}],
        "objects": [],
        "spawns": [],
        "auto_connect": True,
    }


def _overrides() -> dict:
    return {
        "blocked_regions": [
            [0, 0, 87, 0],
            [0, 47, 87, 47],
            [0, 1, 0, 46],
            [87, 1, 87, 46],
        ],
        "blocked": [[20, 20]],
        "walkable": [[17, 0]],
    }


def _collision(*, isolate: tuple[int, int] | None = None) -> str:
    blocked = {
        (x, y) for y in range(48) for x in range(88) if x in (0, 87) or y in (0, 47)
    }
    if isolate:
        x, y = isolate
        blocked.update(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return ", ".join(
        "32125" if (x, y) in blocked else "0" for y in range(48) for x in range(88)
    )


def _old_map() -> dict:
    return {
        "width": 140,
        "height": 100,
        "layers": [{"name": "Collisions", "data": [0] * 14000}],
    }


class SemanticCompilerTests(unittest.TestCase):
    def _inputs(self, root: Path, *, tmj=None, collision=None):
        values = {
            "tmj_path": root / "town.tmj",
            "spec_path": root / "town_spec.json",
            "overrides_path": root / "town_spec.collisions.json",
            "collision_path": root / "collision_maze.csv",
            "old_map_path": root / "old.json",
        }
        payloads = (
            (values["tmj_path"], tmj or _tmj()),
            (values["spec_path"], _spec()),
            (values["overrides_path"], _overrides()),
            (values["old_map_path"], _old_map()),
        )
        for path, payload in payloads:
            path.write_text(json.dumps(payload), encoding="utf-8")
        values["collision_path"].write_text(collision or _collision(), encoding="utf-8")
        return values

    def test_compiles_deterministically_without_implicit_writes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = self._inputs(root)
            first = compiler.compile_semantics(**inputs, layout=_layout())
            second = compiler.compile_semantics(**inputs, layout=_layout())
            self.assertEqual(first, second)
            self.assertEqual(
                first.town_spec["_generated_by"], "compile_claudeville_semantics.py"
            )
            self.assertFalse(first.town_spec["auto_connect"])
            self.assertEqual(
                first.town_spec["required_zones"],
                [{"sector": "Test Hall", "arena": "test.service"}],
            )
            self.assertEqual(len(first.town_spec["arenas"][0]["rects"]), 4)
            self.assertTrue(first.collision[2][2])
            self.assertTrue(first.collision[3][3])
            self.assertFalse(first.collision[3][2])
            self.assertFalse((root / "compiled.json").exists())

    def test_explicit_atomic_write_uses_compact_json(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = compiler.compile_semantics(**self._inputs(root), layout=_layout())
            spec_output = root / "nested/spec.json"
            collision_output = root / "nested/collisions.json"
            compiler.write_compilation(result, spec_output, collision_output)
            self.assertEqual(json.loads(spec_output.read_text()), result.town_spec)
            self.assertEqual(
                json.loads(collision_output.read_text()), result.collision_overrides
            )
            self.assertEqual(spec_output.read_text().count("\n"), 1)

    def test_rejects_spawn_on_a_purpose_prop_blocker(self):
        prop = SimpleNamespace(zone="test.service", blocks=True, visual_x=4, visual_y=6)
        object_prop = SimpleNamespace(
            zone="test.service", blocks=True, visual_x=4, visual_y=4
        )
        layout = _layout(PURPOSE_PROPS={"Test Hall": (object_prop, prop)})
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(compiler.SemanticCompileError, "blocked"):
                compiler.compile_semantics(
                    **self._inputs(Path(temporary)), layout=layout
                )

    def test_assigns_unclaimed_clear_floor_to_circulation(self):
        layout = _layout(ZONE_RECTS={"test.service": (2, 2, 8, 10)})
        with TemporaryDirectory() as temporary:
            result = compiler.compile_semantics(
                **self._inputs(Path(temporary)), layout=layout
            )
            names = {arena["name"] for arena in result.town_spec["arenas"]}
            self.assertIn("test_hall.circulation", names)
            self.assertFalse(result.collision[3][4])

    def test_visible_authored_path_can_replace_stale_base_collision(self):
        values = _collision().split(", ")
        values[3 * 88 + 4] = "32125"
        layout = _layout(
            authored_walkable_cells=lambda _layers, _blocks: {(4, 3)}
        )
        with TemporaryDirectory() as temporary:
            result = compiler.compile_semantics(
                **self._inputs(Path(temporary), collision=", ".join(values)),
                layout=layout,
            )
        self.assertFalse(result.collision[3][4])
        self.assertIn([4, 3], result.collision_overrides["walkable"])
        self.assertEqual(result.stats["authored_walkable"], 1)

    def test_authored_scenery_block_wins_over_stale_walkable_override(self):
        layout = _layout(SCENERY_BLOCK_CELLS=((10, 10),))
        with TemporaryDirectory() as temporary:
            inputs = self._inputs(Path(temporary))
            overrides = json.loads(inputs["overrides_path"].read_text())
            overrides["walkable"].append([10, 10])
            inputs["overrides_path"].write_text(json.dumps(overrides))
            result = compiler.compile_semantics(**inputs, layout=layout)
        self.assertTrue(result.collision[10][10])
        self.assertIn([10, 10], result.collision_overrides["blocked"])
        self.assertNotIn([10, 10], result.collision_overrides["walkable"])

    def test_object_stance_prefers_its_own_zone(self):
        service = "test.service"
        lounge = "test.lounge"
        layout = _layout(
            ZONE_RECTS={service: (2, 2, 6, 10), lounge: (6, 2, 10, 10)},
            PURPOSE_PROPS={
                "Test Hall": (
                    SimpleNamespace(
                        zone=service, blocks=True, visual_x=4, visual_y=4
                    ),
                    SimpleNamespace(
                        zone=lounge, blocks=False, visual_x=8, visual_y=8
                    ),
                )
            },
        )
        with TemporaryDirectory() as temporary:
            result = compiler.compile_semantics(
                **self._inputs(Path(temporary)), layout=layout
            )
        self.assertEqual(result.object_stances, ((2, 1),))

    def test_object_stance_can_use_clear_same_sector_floor(self):
        service = "test.service"
        lounge = "test.lounge"
        layout = _layout(
            ZONE_RECTS={service: (2, 2, 6, 10), lounge: (6, 2, 10, 10)},
            PURPOSE_PROPS={
                "Test Hall": (
                    *(
                        SimpleNamespace(
                            zone=service,
                            blocks=True,
                            visual_x=x * 2,
                            visual_y=y * 2,
                        )
                        for x, y in ((2, 2), (2, 3), (1, 2), (2, 1))
                    ),
                    SimpleNamespace(
                        zone=lounge, blocks=False, visual_x=8, visual_y=8
                    ),
                )
            },
            SPAWNS={"Test Hall": (3, 3)},
        )
        with TemporaryDirectory() as temporary:
            result = compiler.compile_semantics(
                **self._inputs(Path(temporary)), layout=layout
            )
        self.assertEqual(result.object_stances, ((3, 2),))

    def test_stance_helper_reports_every_unusable_object(self):
        collision = [[True] * 88 for _ in range(48)]
        records = [
            ("Home", "home.room", "desk", ((2, 2),), None),
            ("Home", "home.room", "sink", ((4, 4),), None),
        ]
        stances, failures = semantic_graph.select_object_stances(
            records,
            {"home.room": {(2, 2), (4, 4)}},
            {"home.room": "Home"},
            collision,
        )
        self.assertEqual(stances, [])
        self.assertEqual([item["type"] for item in failures], ["desk", "sink"])
        self.assertTrue(
            all(
                neighbor["state"] == "blocked"
                for item in failures
                for neighbor in item["nearby"]
            )
        )

    def test_rejects_an_isolated_door_even_when_connectivity_stays_above_98(self):
        layout = _layout(
            ENTRANCES={"Test Hall": (10, 10)},
        )
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = self._inputs(root, collision=_collision(isolate=(10, 10)))
            with self.assertRaisesRegex(compiler.SemanticCompileError, "disconnected"):
                compiler.compile_semantics(**inputs, layout=layout)

    def test_rejects_an_entrance_drawn_over_a_structural_wall(self):
        tmj = _tmj()
        wall = next(layer for layer in tmj["layers"] if layer["name"] == "Wall")
        wall["data"][8 * 176 + 2] = 1
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                compiler.SemanticCompileError, "entrance overlaps"
            ):
                compiler.compile_semantics(
                    **self._inputs(Path(temporary), tmj=tmj), layout=_layout()
                )

    def test_rejects_a_semantic_object_without_aligned_visible_art(self):
        ghost_layout = _layout(
            PURPOSE_PROPS={
                "Test Hall": (
                    SimpleNamespace(
                        zone="test.service", blocks=True, visual_x=6, visual_y=6
                    ),
                )
            }
        )
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                compiler.SemanticCompileError, "has no visible art"
            ):
                compiler.compile_semantics(
                    **self._inputs(Path(temporary)), layout=ghost_layout
                )

    def test_physical_depth_prop_blocks_its_bottom_centre_foot_cell(self):
        tmj = _tmj()
        tmj["layers"].append(
            {
                "name": "Depth Props",
                "type": "objectgroup",
                "objects": [
                    {
                        "x": 128,
                        "y": 96,
                        "properties": [
                            {
                                "name": "asset_key",
                                "type": "string",
                                "value": "prop.landscape.tree_07",
                            }
                        ],
                    }
                ],
            }
        )
        with TemporaryDirectory() as temporary:
            result = compiler.compile_semantics(
                **self._inputs(Path(temporary), tmj=tmj), layout=_layout()
            )
            self.assertTrue(result.collision[3][4])
            self.assertIn([4, 3], result.collision_overrides["blocked"])

    def test_old_stamp_blockers_respect_mirroring_and_building_crop(self):
        layers = compiler._layers(_tmj())
        layers["Interior Furniture L1"]["data"][2 * 176 + 2] = 1
        old = _old_map()
        source_x, source_y, width, _height = SOURCE_TEMPLATES["cafe"]
        old["layers"][0]["data"][source_y * 140 + source_x + width - 1] = 1
        layout = _layout(PURPOSE_STAMPS={"Test Hall": (Stamp("cafe", (2, 2), True),)})
        self.assertEqual(
            homes.old_stamp_blocks(
                layers, old, layout, compiler.VISIBLE_BLOCKER_LAYERS
            ),
            {(1, 1)},
        )

    def test_atlas_stamp_requires_only_occupied_destination_cells(self):
        layers = compiler._layers(_tmj())
        layers["Interior Furniture L1"]["data"][5 * 176 + 5] = 1
        required = SimpleNamespace(
            source_rect=(0, 0, 2, 2),
            destination=(4, 4),
            target_layer="Interior Furniture L1",
            blocker_policy="require-blocked",
        )
        layout = _layout(PURPOSE_STAMPS={"Test Hall": (required,)})
        self.assertEqual(homes.atlas_blocks(layers, layout), {(2, 2)})

    def test_real_home_templates_map_to_distinct_english_room_semantics(self):
        tmj = compiler._read_json(LEGACY_TMJ)
        sectors = legacy_v2_sector_cells()
        result = homes.derive_home_semantics(
            compiler._layers(tmj), real_layout, sector_cells=sectors
        )
        self.assertEqual(set(result.entrances), set(homes.HOME_ENTRANCES))
        self.assertTrue(all(result.objects[sector] for sector in result.entrances))
        for sector, entries in result.objects.items():
            occupied = [point for entry in entries for point in entry.logical_tiles]
            self.assertEqual(len(occupied), len(set(occupied)), sector)
            self.assertFalse(any(entry.type == "house garden" for entry in entries))
            cooking_zones = {entry.zone for entry in entries if entry.type == "cooking area"}
            refrigerator_zones = {entry.zone for entry in entries if entry.type == "refrigerator"}
            self.assertLessEqual(refrigerator_zones, cooking_zones, sector)
        for sector in real_layout.HOME_KITCHEN_STAMPS:
            self.assertTrue(
                any(
                    entry.zone.endswith(".kitchen")
                    and entry.type in homes.KITCHEN_TYPES
                    for entry in result.objects[sector]
                ),
                sector,
            )

    def test_scenery_blocks_do_not_overlap_active_world_cells(self):
        layers = compiler._layers(compiler._read_json(LEGACY_TMJ))
        sectors = legacy_v2_sector_cells()
        public_zones, _owners, _clear = homes.partition_public_zones(
            layers, real_layout, sectors
        )
        home_data = homes.derive_home_semantics(
            layers, real_layout, sector_cells=sectors
        )
        active = set().union(
            *public_zones.values(),
            *home_data.zones.values(),
            sectors["Central Plaza"],
        )
        active.update(real_layout.ENTRANCES.values())
        active.update(real_layout.SPAWNS.values())
        active.update(homes.HOME_ENTRANCES.values())
        active.update(
            point
            for entries in real_layout.SEMANTIC_OBJECTS.values()
            for entry in entries
            for point in entry.logical_tiles
        )
        active.update(
            point
            for entries in home_data.objects.values()
            for entry in entries
            for point in entry.logical_tiles
        )
        active.update(
            recipe.point
            for entries in home_stances.HOME_STANCE_CELLS.values()
            for recipe in entries
        )
        self.assertFalse(scenery.SCENERY_BLOCK_CELLS & active)

    def test_central_plaza_uses_reachable_south_fountain_stance(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = self._inputs(root)
            spec = json.loads(inputs["spec_path"].read_text())
            spec["sectors"].append({"name": "Central Plaza", "rect": [33, 20, 45, 31]})
            inputs["spec_path"].write_text(json.dumps(spec), encoding="utf-8")
            result = compiler.compile_semantics(**inputs, layout=_layout())
            fountain = next(
                item
                for item in result.town_spec["objects"]
                if item["sector"] == "Central Plaza" and item["type"] == "fountain"
            )
            self.assertEqual(fountain["tiles"], [[39, 27]])
            self.assertIn((39, 28), result.object_stances)
            self.assertFalse(result.collision[28][39])


if __name__ == "__main__":
    unittest.main()
