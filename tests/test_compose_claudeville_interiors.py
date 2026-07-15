"""Regression contracts for Claudeville's paid Modern Interiors composition."""

from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.mapgen import compose_claudeville_interiors as composer
from tools.mapgen.claudeville_interior_layouts import (
    BUILDING_BOUNDS,
    HOMES,
    PUBLIC_STAMPS,
)

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


def load_map(path: Path = composer.SOURCE_MAP) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def layer_lookup(map_data: dict) -> dict[str, dict]:
    return {layer["name"]: layer for layer in map_data["layers"]}


def cells_in(bounds: tuple[int, int, int, int]):
    left, top, right, bottom = bounds
    for y in range(top, bottom):
        for x in range(left, right):
            yield x, y, y * composer.WIDTH + x


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
            for name in EXTERIOR_LAYERS:
                with self.subTest(layer=name):
                    self.assertEqual(composed_layers[name], before_layers[name])
        self.assertEqual(composer.SOURCE_MAP.read_bytes(), before_bytes)

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
                self.assertGreaterEqual(len(occupied), 35)
            signatures[home.name] = hashlib.sha256(
                json.dumps(payload, separators=(",", ":")).encode()
            ).hexdigest()
        self.assertEqual(len(signatures), 10)
        self.assertEqual(len(set(signatures.values())), 10, signatures)

    def test_public_interiors_have_no_large_density_regressions(self):
        layers = layer_lookup(load_map())
        ratios: dict[str, float] = {}
        for building in PUBLIC_STAMPS:
            occupied: set[tuple[int, int]] = set()
            supported = 0
            for x, y, index in cells_in(BUILDING_BOUNDS[building]):
                if (
                    layers["Interior Ground"]["data"][index]
                    or layers["Wall"]["data"][index]
                ):
                    supported += 1
                if any(layers[name]["data"][index] for name in FURNITURE_LAYERS):
                    occupied.add((x, y))
            self.assertGreater(supported, 0, building)
            ratios[building] = len(occupied) / supported
            with self.subTest(building=building):
                self.assertGreaterEqual(ratios[building], 0.22)
        self.assertGreaterEqual(sum(ratios.values()) / len(ratios), 0.32, ratios)


if __name__ == "__main__":
    unittest.main()
