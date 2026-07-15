"""Compose Claudeville's interiors from licensed Modern Interiors assemblies."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

try:
    from tools.mapgen import modern_interiors_source, tiled_gid
    from tools.mapgen.claudeville_interior_layouts import (
        BUILDING_BOUNDS,
        FLOOR_THEMES,
        HOME_FLOOR_THEMES,
        HOMES,
        PUBLIC_STAMPS,
        SOURCE_TEMPLATES,
        Rect,
        Stamp,
    )
except ModuleNotFoundError:  # Direct ``python tools/mapgen/compose_claudeville_interiors.py``.
    import modern_interiors_source  # type: ignore[no-redef]
    import tiled_gid  # type: ignore[no-redef]
    from claudeville_interior_layouts import (  # type: ignore[no-redef]
        BUILDING_BOUNDS,
        FLOOR_THEMES,
        HOME_FLOOR_THEMES,
        HOMES,
        PUBLIC_STAMPS,
        SOURCE_TEMPLATES,
        Rect,
        Stamp,
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORING_ROOT = REPO_ROOT / "output/claudeville/modern_pixels_v2"
SOURCE_MAP = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals"
    / "claudeville_full_town_v2.tmj"
)
OLD_MAP_ROOT = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/the_ville/visuals"
)
OLD_MAP = OLD_MAP_ROOT / "the_ville_jan7.json"
WIDTH, HEIGHT = 176, 96
FLIP_MASK = tiled_gid.GID_MASK
HORIZONTAL_FLIP = tiled_gid.HORIZONTAL_FLIP
INTERIORS_SOURCE = "../../../../../../output/claudeville/modern_pixels_v2/tiles/interiors.tsj"
TILESET_ROOT = "../../../../../../output/claudeville/modern_pixels_v2/tiles"
EXPECTED_TILESETS = (
    (1, f"{TILESET_ROOT}/terrain.tsj"),
    (5117, f"{TILESET_ROOT}/town.tsj"),
    (37398, f"{TILESET_ROOT}/office.tsj"),
    (38214, INTERIORS_SOURCE),
)
PUBLIC_LAYERS = (
    "Interior Furniture L1",
    "Interior Furniture L2 ",
    "Foreground L1",
    "Foreground L2",
)
HOME_LAYERS = (
    "Interior Ground",
    "Wall",
    *PUBLIC_LAYERS,
)
TARGET_LAYER = {"Interior Furniture L2 ": "Interior Furniture L2"}
CLEARABLE_PROP_PREFIXES = ("prop.office.", "prop.cafe.", "prop.community.")
OUTDOOR_PROP_PREFIXES = ("prop.landscape.", "prop.garden.", "prop.street.")
KEEP_PROPS = {
    "University": {
        "prop.office.coffee_station",
        "prop.office.computer_desk",
        "prop.office.display_cabinet",
        "prop.office.vending_machine",
        "prop.office.whiteboard",
    },
    "Agent Academy": {
        "prop.office.dual_monitors",
        "prop.office.monitor_blue",
        "prop.office.town_map",
        "prop.office.training_station",
        "prop.office.wall_chart",
        "prop.office.water_cooler",
        "prop.office.whiteboard",
    },
}
PRESERVE_MIXED_PROPS = {"Workshop", "Post Office", "Town Hall"}


class CompositionError(ValueError):
    """Raised when a licensed source or map composition contract is invalid."""


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompositionError(f"invalid JSON source: {path}") from exc
    if not isinstance(value, dict):
        raise CompositionError(f"JSON source root must be an object: {path}")
    return value


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _properties(value: object) -> dict:
    if not isinstance(value, list):
        return {}
    return {
        item["name"]: item.get("value")
        for item in value
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _inside(rect: Rect, x: int | float, y: int | float) -> bool:
    left, top, right, bottom = rect
    return left <= x < right and top <= y < bottom


def _layers(map_data: dict) -> dict[str, dict]:
    layers = map_data.get("layers")
    if not isinstance(layers, list):
        raise CompositionError("map must contain root-level layers")
    result = {
        layer.get("name"): layer for layer in layers
        if isinstance(layer, dict) and isinstance(layer.get("name"), str)
    }
    required = {
        "Interior Ground", "Wall", "Interior Furniture L1", "Interior Furniture L2",
        "Foreground L1", "Foreground L2", "Depth Props",
    }
    if not required <= result.keys():
        raise CompositionError("map is missing required interior layers")
    return result


def _tile_catalog() -> tuple[dict[str, int], int]:
    atlas = _read_json(AUTHORING_ROOT / "atlas.json")
    pages = atlas.get("atlases")
    page = next(
        (item for item in pages or [] if isinstance(item, dict) and item.get("key") == "interiors"),
        None,
    )
    if not isinstance(page, dict) or page.get("tile_count") != 18711:
        raise CompositionError("curated Modern Interiors atlas is missing or incomplete")
    tiles = _read_json(AUTHORING_ROOT / "tiles.json").get("tiles")
    if not isinstance(tiles, list):
        raise CompositionError("curated tile catalog is malformed")
    lookup = {
        item["asset_key"]: item["atlas_index"]
        for item in tiles
        if isinstance(item, dict)
        and item.get("atlas") == "interiors"
        and isinstance(item.get("asset_key"), str)
        and isinstance(item.get("atlas_index"), int)
    }
    if len(lookup) != page["tile_count"]:
        raise CompositionError("curated Modern Interiors tile keys are incomplete")
    return lookup, page["tile_count"]


def _add_interiors_tileset(map_data: dict, tile_count: int) -> int:
    tilesets = map_data.get("tilesets")
    if not isinstance(tilesets, list):
        raise CompositionError("map tilesets are malformed")
    if len(tilesets) not in (3, 4) or any(not isinstance(item, dict) for item in tilesets):
        raise CompositionError("expected the curated terrain, town, office and interiors order")
    expected = EXPECTED_TILESETS[: len(tilesets)]
    actual = tuple((item.get("firstgid"), item.get("source")) for item in tilesets)
    if actual != expected:
        raise CompositionError("curated tileset paths, firstgids or order changed unexpectedly")
    firstgid = EXPECTED_TILESETS[-1][0]
    if firstgid + tile_count != 56925:
        raise CompositionError("curated atlas ordering changed unexpectedly")
    if len(tilesets) == 4:
        return firstgid
    tilesets.append({"firstgid": firstgid, "source": INTERIORS_SOURCE})
    return firstgid


def _normalized_hash(image: Image.Image) -> bytes:
    rgba = bytearray(image.convert("RGBA").tobytes())
    for offset in range(0, len(rgba), 4):
        if rgba[offset + 3] == 0:
            rgba[offset:offset + 4] = b"\0\0\0\0"
    return hashlib.sha256(rgba).digest()


def _full_hash_index() -> dict[bytes, int]:
    result: dict[bytes, int] = {}
    image, _record = modern_interiors_source.load_native_sheet("interiors.full")
    for tile_id in range(16 * (image.height // 16)):
        column, row = tile_id % 16, tile_id // 16
        crop = image.crop((column * 16, row * 16, column * 16 + 16, row * 16 + 16))
        if crop.getchannel("A").getbbox() is None:
            continue
        result.setdefault(_normalized_hash(crop), tile_id)
    image.close()
    return result


def _contained_old_image(relative: object) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise CompositionError("legacy Modern Interiors image path is malformed")
    root = OLD_MAP_ROOT.resolve()
    path = (root / relative).resolve(strict=False)
    if root not in path.parents or not path.is_file():
        raise CompositionError("legacy Modern Interiors image escapes its source root")
    return path


def _native_split_tile(crop: Image.Image, base_gid: int) -> Image.Image:
    native = crop.resize((16, 16), Image.Resampling.NEAREST)
    restored = native.resize((32, 32), Image.Resampling.NEAREST)
    if ImageChops.difference(crop, restored).getbbox() is not None:
        raise CompositionError(f"legacy Modern Interiors tile is not exact 2x: {base_gid}")
    return native


def _old_gid_converter(old: dict, tile_keys: dict[str, int], firstgid: int):
    tilesets = sorted(old.get("tilesets", []), key=lambda item: item.get("firstgid", 0))
    room_builder = next(
        item for item in tilesets if item.get("name") == "Room_Builder_32x32"
    )
    full_by_hash = _full_hash_index()
    split_images: dict[str, Image.Image] = {}
    cache: dict[int, tuple[int, str] | None] = {}

    def convert(raw_gid: int) -> tuple[int, str] | None:
        base_gid = raw_gid & FLIP_MASK
        if not base_gid:
            return None
        if base_gid in cache:
            cached = cache[base_gid]
            flags = raw_gid & tiled_gid.ORTHOGONAL_FLIP_MASK
            return None if cached is None else ((cached[0] | flags), cached[1])
        tileset = max(
            (item for item in tilesets if item.get("firstgid", 0) <= base_gid),
            key=lambda item: item["firstgid"],
        )
        name = str(tileset.get("name", ""))
        local_id = base_gid - tileset["firstgid"]
        if tileset is room_builder:
            row, column = divmod(local_id, 76)
            key = f"tile.interiors.room_builder.r{row:04}.c{column:02}"
            kind = "room_builder"
        elif name.startswith("interiors_pt"):
            image = split_images.get(name)
            if image is None:
                with Image.open(_contained_old_image(tileset.get("image"))) as opened:
                    image = opened.convert("RGBA")
                split_images[name] = image
            row, column = divmod(local_id, 16)
            crop = image.crop((column * 32, row * 32, column * 32 + 32, row * 32 + 32))
            if crop.getchannel("A").getbbox() is None:
                cache[base_gid] = None
                return None
            tile_hash = _normalized_hash(_native_split_tile(crop, base_gid))
            full_id = full_by_hash.get(tile_hash)
            if full_id is None:
                raise CompositionError(f"split Modern Interiors tile has no paid full-sheet match: {base_gid}")
            full_row, full_column = divmod(full_id, 16)
            key = f"tile.interiors.full.r{full_row:04}.c{full_column:02}"
            kind = "full"
        else:
            cache[base_gid] = None
            return None
        atlas_index = tile_keys.get(key)
        if atlas_index is None:
            raise CompositionError(f"curated Modern Interiors key is missing: {key}")
        mapped = firstgid + atlas_index
        cache[base_gid] = (mapped, kind)
        return mapped | (raw_gid & tiled_gid.ORTHOGONAL_FLIP_MASK), kind

    return convert, split_images


def _clear_rect(layer: dict, rect: Rect) -> None:
    left, top, right, bottom = rect
    data = layer["data"]
    for y in range(top, bottom):
        start = y * WIDTH + left
        data[start:start + right - left] = [0] * (right - left)


def _retile_floors(
    layers: dict[str, dict], tile_keys: dict[str, int], firstgid: int
) -> int:
    ground = layers["Interior Ground"]["data"]
    changed = 0
    themes = {**FLOOR_THEMES, **HOME_FLOOR_THEMES}
    for building, (source_row, source_column) in themes.items():
        left, top, right, bottom = BUILDING_BOUNDS[building]
        for y in range(top, bottom):
            for x in range(left, right):
                index = y * WIDTH + x
                if not ground[index]:
                    continue
                row = source_row + (y - top) % 2
                column = source_column + (x - left) % 4
                key = f"tile.interiors.room_builder.r{row:04}.c{column:02}"
                atlas_index = tile_keys.get(key)
                if atlas_index is None:
                    raise CompositionError(f"floor motif tile is missing: {key}")
                ground[index] = firstgid + atlas_index
                changed += 1
    return changed


def _stamp_rect(stamp: Stamp) -> Rect:
    _x, _y, width, height = SOURCE_TEMPLATES[stamp.template]
    return (*stamp.destination, stamp.destination[0] + width, stamp.destination[1] + height)


def _copy_stamp(
    old_layers: dict[str, dict], target_layers: dict[str, dict], stamp: Stamp,
    source_layers: tuple[str, ...], convert, bounds: Rect, support: list[bool] | None,
    *, allow_room_builder: bool,
) -> int:
    source_x, source_y, width, height = SOURCE_TEMPLATES[stamp.template]
    destination_x, destination_y = stamp.destination
    added = 0
    for old_name in source_layers:
        target_name = TARGET_LAYER.get(old_name, old_name)
        source_data = old_layers[old_name]["data"]
        target_data = target_layers[target_name]["data"]
        for offset_y in range(height):
            for offset_x in range(width):
                raw_gid = source_data[(source_y + offset_y) * 140 + source_x + offset_x]
                mapped = convert(raw_gid)
                if mapped is None or (mapped[1] == "room_builder" and not allow_room_builder):
                    continue
                target_x = destination_x + (width - 1 - offset_x if stamp.mirror_x else offset_x)
                target_y = destination_y + offset_y
                if not _inside(bounds, target_x, target_y):
                    continue
                index = target_y * WIDTH + target_x
                if support is not None and not support[index]:
                    continue
                gid = mapped[0] ^ (HORIZONTAL_FLIP if stamp.mirror_x else 0)
                target_data[index] = gid
                added += 1
    return added


def _clear_interior_props(layers: dict[str, dict], support: list[bool]) -> int:
    objects = layers["Depth Props"]["objects"]
    retained = []
    removed = 0
    for obj in objects:
        x, y = obj.get("x", -1) / 16, obj.get("y", -1) / 16
        key = _properties(obj.get("properties")).get("asset_key", "")
        building = next(
            (name for name, bounds in BUILDING_BOUNDS.items() if _inside(bounds, x, y)),
            None,
        )
        clearable = isinstance(key, str) and key.startswith(CLEARABLE_PROP_PREFIXES)
        keep = key in KEEP_PROPS.get(building, set()) or building in PRESERVE_MIXED_PROPS
        cell_x, cell_y = int(x), int(y)
        on_interior = 0 <= cell_x < WIDTH and 0 <= cell_y < HEIGHT and support[cell_y * WIDTH + cell_x]
        outdoor_inside = (
            isinstance(key, str)
            and (key.startswith(OUTDOOR_PROP_PREFIXES) or key == "prop.post.truck")
            and on_interior
        )
        if building and ((clearable and not keep) or outdoor_inside):
            removed += 1
        else:
            retained.append(obj)
    layers["Depth Props"]["objects"] = retained
    return removed


def compose(source: Path = SOURCE_MAP, output: Path | None = None) -> dict:
    source = Path(source).expanduser().resolve(strict=True)
    output = Path(output or source).expanduser().resolve(strict=False)
    map_data = _read_json(source)
    if (map_data.get("width"), map_data.get("height"), map_data.get("tilewidth")) != (176, 96, 16):
        raise CompositionError("Claudeville authoring map must remain 176x96 at native 16px")
    layers = _layers(map_data)
    tile_keys, tile_count = _tile_catalog()
    firstgid = _add_interiors_tileset(map_data, tile_count)
    old = _read_json(OLD_MAP)
    old_layers = {layer["name"]: layer for layer in old["layers"]}
    convert, split_images = _old_gid_converter(old, tile_keys, firstgid)
    support = [
        bool(ground or wall)
        for ground, wall in zip(layers["Interior Ground"]["data"], layers["Wall"]["data"])
    ]
    stats: dict[str, int] = {
        "retiled_floor_cells": _retile_floors(
            layers, tile_keys, firstgid
        )
    }
    try:
        for building, stamps in PUBLIC_STAMPS.items():
            bounds = BUILDING_BOUNDS[building]
            _clear_rect(layers["Interior Furniture L1"], bounds)
            _clear_rect(layers["Interior Furniture L2"], bounds)
            stats[building] = sum(
                _copy_stamp(
                    old_layers, layers, stamp, PUBLIC_LAYERS, convert, bounds, support,
                    allow_room_builder=False,
                )
                for stamp in stamps
            )
        for home in HOMES:
            stamp_rect = _stamp_rect(home.stamp)
            for name in ("Interior Furniture L1", "Interior Furniture L2"):
                _clear_rect(layers[name], home.bounds)
            for name in HOME_LAYERS:
                _clear_rect(layers[TARGET_LAYER.get(name, name)], stamp_rect)
            stats[home.name] = _copy_stamp(
                old_layers, layers, home.stamp, HOME_LAYERS, convert, home.bounds, None,
                allow_room_builder=True,
            )
    finally:
        for image in split_images.values():
            image.close()
    final_support = [
        bool(ground or wall)
        for ground, wall in zip(
            layers["Interior Ground"]["data"], layers["Wall"]["data"]
        )
    ]
    stats["removed_legacy_props"] = _clear_interior_props(layers, final_support)
    if any(stats.get(name, 0) < 12 for name in (*PUBLIC_STAMPS, *(home.name for home in HOMES))):
        raise CompositionError(f"one or more interiors were not populated: {stats}")
    if "modern_interiors_free" in json.dumps(map_data).casefold():
        raise CompositionError("Free Modern Interiors must never enter the runtime map")
    _write_json(output, map_data)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_MAP)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(compose(args.source, args.output), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
