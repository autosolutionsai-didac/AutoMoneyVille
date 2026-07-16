from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops

try:
    import tools.mapgen.claudeville_exterior_cleanup as exterior_cleanup
    import tools.mapgen.claudeville_purpose_layouts as purpose
    from tools.mapgen import modern_interiors_source, tiled_gid
    from tools.mapgen.claudeville_entry_paths import apply_entry_paths
    from tools.mapgen.claudeville_interior_layouts import (
        BUILDING_BOUNDS,
        FLOOR_THEMES,
        HOME_FLOOR_THEMES,
        HOMES,
        SOURCE_TEMPLATES,
        Rect,
        Stamp,
    )
except ModuleNotFoundError:  # Direct ``python tools/mapgen/compose_claudeville_interiors.py``.
    import claudeville_exterior_cleanup as exterior_cleanup  # type: ignore[no-redef]
    import claudeville_purpose_layouts as purpose  # type: ignore[no-redef]
    import modern_interiors_source  # type: ignore[no-redef]
    import tiled_gid  # type: ignore[no-redef]
    from claudeville_entry_paths import apply_entry_paths  # type: ignore[no-redef]
    from claudeville_interior_layouts import (  # type: ignore[no-redef]
        BUILDING_BOUNDS,
        FLOOR_THEMES,
        HOME_FLOOR_THEMES,
        HOMES,
        SOURCE_TEMPLATES,
        Rect,
        Stamp,
    )
REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORING_ROOT = REPO_ROOT / "output/claudeville/modern_pixels_v2"
SOURCE_MAP = REPO_ROOT / "environment/frontend_server/static_dirs/assets/claudeville/visuals/claudeville_full_town_v2.tmj"
OLD_MAP_ROOT = REPO_ROOT / "environment/frontend_server/static_dirs/assets/the_ville/visuals"
OLD_MAP = OLD_MAP_ROOT / "the_ville_jan7.json"
WIDTH, HEIGHT = 176, 96
FLIP_MASK = tiled_gid.GID_MASK
HORIZONTAL_FLIP = tiled_gid.HORIZONTAL_FLIP
INTERIORS_SOURCE = "../../../../../../output/claudeville/modern_pixels_v2/tiles/interiors.tsj"
TILESET_ROOT = "../../../../../../output/claudeville/modern_pixels_v2/tiles"
EXPECTED_TILESETS = ((1, f"{TILESET_ROOT}/terrain.tsj"), (5117, f"{TILESET_ROOT}/town.tsj"), (37398, f"{TILESET_ROOT}/office.tsj"), (38214, INTERIORS_SOURCE))
PUBLIC_LAYERS = ("Interior Furniture L1", "Interior Furniture L2 ", "Foreground L1", "Foreground L2")
HOME_LAYERS = ("Interior Ground", "Wall", *PUBLIC_LAYERS)
TARGET_LAYER = {"Interior Furniture L2 ": "Interior Furniture L2"}
ATLAS_FIRSTGIDS = {"terrain": 1, "town": 5117, "office": 37398, "interiors": 38214}
PURPOSE_OBJECT_ID_BASE = 10000
PURPOSE_ID_PREFIX = "claudeville-purpose/"
class CompositionError(ValueError): ...

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
        "Foreground L1", "Foreground L2", "Depth Props", "Collisions",
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


def _atlas_tile_gids() -> dict[tuple[str, int, int], int]:
    records = _read_json(AUTHORING_ROOT / "tiles.json").get("tiles")
    if not isinstance(records, list):
        raise CompositionError("curated tile catalog is malformed")
    result: dict[tuple[str, int, int], int] = {}
    for item in records:
        if not isinstance(item, dict):
            continue
        atlas = item.get("atlas")
        source_id = item.get("source_id")
        row, column = item.get("source_row"), item.get("source_col")
        atlas_index = item.get("atlas_index")
        if (
            atlas not in ATLAS_FIRSTGIDS
            or not isinstance(source_id, str)
            or not all(isinstance(value, int) for value in (row, column, atlas_index))
        ):
            continue
        result[source_id, column, row] = ATLAS_FIRSTGIDS[atlas] + atlas_index
    if not result:
        raise CompositionError("curated tile source index is empty")
    return result


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
                key = (
                    f"tile.interiors.room_builder.r{source_row:04}."
                    f"c{source_column:02}"
                )
                atlas_index = tile_keys.get(key)
                if atlas_index is None:
                    raise CompositionError(f"floor tile is missing: {key}")
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
    return _copy_legacy_rect(
        old_layers, target_layers, SOURCE_TEMPLATES[stamp.template], stamp.destination,
        source_layers, convert, bounds, support, allow_room_builder=allow_room_builder,
        mirror_x=stamp.mirror_x,
    )


def _copy_legacy_rect(
    old_layers: dict[str, dict], target_layers: dict[str, dict], source_rect: Rect,
    destination: tuple[int, int], source_layers: tuple[str, ...], convert, bounds: Rect,
    support: list[bool] | None, *, allow_room_builder: bool, mirror_x: bool = False,
) -> int:
    source_x, source_y, width, height = source_rect
    destination_x, destination_y = destination
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
                target_x = destination_x + (width - 1 - offset_x if mirror_x else offset_x)
                target_y = destination_y + offset_y
                if not _inside(bounds, target_x, target_y):
                    continue
                index = target_y * WIDTH + target_x
                if support is not None and not support[index]:
                    continue
                gid = mapped[0] ^ (HORIZONTAL_FLIP if mirror_x else 0)
                target_data[index] = gid
                added += 1
    return added


def _copy_atlas_stamp(
    layers: dict[str, dict], stamp, gids: dict[tuple[str, int, int], int], bounds: Rect,
) -> int:
    source_x, source_y, width, height = stamp.source_rect
    destination_x, destination_y = stamp.destination
    target = layers.get(stamp.target_layer)
    if not isinstance(target, dict) or not isinstance(target.get("data"), list):
        raise CompositionError(f"invalid purpose target layer: {stamp.target_layer}")
    added = 0
    for offset_y in range(height):
        for offset_x in range(width):
            gid = gids.get((stamp.source_id, source_x + offset_x, source_y + offset_y))
            x, y = destination_x + offset_x, destination_y + offset_y
            if not gid or not _inside(bounds, x, y):
                continue
            index = y * WIDTH + x
            if stamp.blocker_policy == "require-blocked" and not layers["Collisions"]["data"][index]:
                raise CompositionError(f"purpose blocker must occupy collision at {x},{y}")
            target["data"][index] = gid
            added += 1
    return added


def _rebuild_purpose_props(map_data: dict, layers: dict[str, dict]) -> tuple[int, int]:
    bounds = (*purpose.PUBLIC_BUILDING_BOUNDS.values(), *purpose.TERRACE_BOUNDS.values())
    objects, retained = layers["Depth Props"]["objects"], []
    for obj in objects:
        values = _properties(obj.get("properties"))
        x, y = obj.get("x", -16) / 16, obj.get("y", -16) / 16
        if obj.get("name") == "Town Hall open front door":
            entrance = purpose.ENTRANCES["Town Hall"]
            retained.append(obj | {"x": (2 * entrance[0] + 1) * 16, "y": (2 * entrance[1] + 4) * 16})
            continue
        if str(values.get("purpose_id", "")).startswith(PURPOSE_ID_PREFIX) or any(
            _inside(rect, x, y) for rect in bounds
        ):
            continue
        retained.append(obj)
    declared = sorted(
        ((sector, item) for sector, items in purpose.PURPOSE_PROPS.items() for item in items),
        key=lambda pair: (
            pair[0], pair[1].visual_y, pair[1].visual_x, pair[1].asset_key,
            pair[1].semantic_type, pair[1].zone,
        ),
    )
    missing = sorted({item.asset_key for _sector, item in declared} - set(_read_json(AUTHORING_ROOT / "props.json").get("frames", {})))
    if missing:
        raise CompositionError(f"purpose prop assets are missing: {missing}")
    if len(set(declared)) != len(declared):
        raise CompositionError("purpose props must be unique")
    for ordinal, (sector, item) in enumerate(declared):
        object_id = PURPOSE_OBJECT_ID_BASE + ordinal
        if object_id in {obj.get("id") for obj in retained}:
            raise CompositionError(f"purpose object id is already used: {object_id}")
        purpose_id = f"{PURPOSE_ID_PREFIX}{ordinal:03d}"
        properties = [
            {"name": name, "type": kind, "value": value} for name, kind, value in (
                ("asset_key", "string", item.asset_key), ("anchor_x", "float", 0.5), ("anchor_y", "float", 1),
                ("display_scale", "float", 1), ("sector", "string", sector), ("zone", "string", item.zone),
                ("semantic_type", "string", item.semantic_type), ("blocks", "bool", item.blocks), ("purpose_id", "string", purpose_id),
                ("depth_offset", "float", 0),
            )
        ]
        retained.append({"id": object_id, "name": item.name or (item.semantic_type or "purpose prop").title(),
                         "type": item.semantic_type or "purpose prop", "x": item.visual_x * 16, "y": item.visual_y * 16,
                         "width": 0, "height": 0, "rotation": 0, "visible": True, "properties": properties})
    layers["Depth Props"]["objects"] = retained
    map_data["nextobjectid"] = max(obj["id"] for obj in retained) + 1
    return len(objects) - len(retained) + len(declared), len(declared)

def compose(source: Path = SOURCE_MAP, output: Path | None = None) -> dict:
    output = Path(output or source).expanduser().resolve(strict=False)
    map_data = _read_json(Path(source).expanduser().resolve(strict=True))
    if (map_data.get("width"), map_data.get("height"), map_data.get("tilewidth")) != (176, 96, 16):
        raise CompositionError("Claudeville authoring map must remain 176x96 at native 16px")
    layers = _layers(map_data)
    tile_keys, tile_count = _tile_catalog()
    atlas_gids = _atlas_tile_gids()
    firstgid = _add_interiors_tileset(map_data, tile_count)
    old = _read_json(OLD_MAP)
    old_layers = {layer["name"]: layer for layer in old["layers"]}
    convert, split_images = _old_gid_converter(old, tile_keys, firstgid)
    support = [bool(ground or wall) for ground, wall in zip(layers["Interior Ground"]["data"], layers["Wall"]["data"])]
    stats: dict[str, int] = {"retiled_floor_cells": _retile_floors(layers, tile_keys, firstgid)}
    try:
        for building, bounds in purpose.PUBLIC_BUILDING_BOUNDS.items():
            for name in ("Interior Furniture L1", "Interior Furniture L2", *PUBLIC_LAYERS[2:]):
                _clear_rect(layers[name], bounds)
            stats[building] = len(purpose.PURPOSE_PROPS.get(building, ()))
            for stamp in purpose.PURPOSE_STAMPS.get(building, ()):
                if stamp.blocker_policy not in purpose.BLOCKER_POLICIES:
                    raise CompositionError(f"invalid blocker policy: {stamp.blocker_policy}")
                if stamp.source_id == "legacy_the_ville":
                    if stamp.target_layer != "source-layers":
                        raise CompositionError("legacy purpose stamps must use source-layers")
                    stats[building] += _copy_legacy_rect(
                        old_layers, layers, stamp.source_rect, stamp.destination,
                        PUBLIC_LAYERS, convert, bounds, support, allow_room_builder=False,
                    )
                else:
                    stats[building] += _copy_atlas_stamp(layers, stamp, atlas_gids, bounds)
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
            for stamp in purpose.HOME_KITCHEN_STAMPS.get(home.name, ()):
                rect = (*stamp.destination, stamp.destination[0] + stamp.source_rect[2],
                        stamp.destination[1] + stamp.source_rect[3])
                for name in PUBLIC_LAYERS:
                    _clear_rect(layers[TARGET_LAYER.get(name, name)], rect)
                if stamp.source_id != "legacy_the_ville" or stamp.target_layer != "source-layers":
                    raise CompositionError("home kitchens must use restricted legacy furniture")
                stats[home.name] += _copy_legacy_rect(
                    old_layers, layers, stamp.source_rect, stamp.destination,
                    PUBLIC_LAYERS, convert, home.bounds, None, allow_room_builder=False,
                )
        stats["entry_path_cells"] = apply_entry_paths(layers, atlas_gids, WIDTH)
    finally:
        for image in split_images.values():
            image.close()
    removed, added = _rebuild_purpose_props(map_data, layers)
    stats.update({"removed_legacy_props": removed, "purpose_props": added})
    stats.update(exterior_cleanup.apply_exterior_cleanup(
        map_data, _read_json(AUTHORING_ROOT / "props.json").get("frames", {})
    ))
    names = (*purpose.PUBLIC_BUILDING_BOUNDS, *(home.name for home in HOMES))
    if any(stats.get(name, 0) < 1 for name in names):
        raise CompositionError(f"one or more interiors were not populated: {stats}")
    if "modern_interiors_free" in json.dumps(map_data).casefold():
        raise CompositionError("Free Modern Interiors must never enter the runtime map")
    _write_json(output, map_data)
    return stats

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_MAP)
    parser.add_argument("--output", type=Path)
    print(json.dumps(compose(**vars(parser.parse_args())), indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
