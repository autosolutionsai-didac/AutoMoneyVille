"""Apply explicit, reviewable Modern Pixels district passes to Claudeville v3."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from tools.mapgen import claudeville_district_semantics as semantics
    from tools.mapgen import claudeville_middle_placements as middle
    from tools.mapgen import claudeville_north_placements as north
    from tools.mapgen import claudeville_south_placements as south
    from tools.mapgen import claudeville_tiled_authoring as authoring
    from tools.mapgen.curate_modern_interiors_v3 import DEFAULT_OUTPUT_ROOT as V3_ROOT
    from tools.mapgen.curate_modern_pixels_v2 import DEFAULT_OUTPUT_ROOT as V2_ROOT
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_district_semantics as semantics
    import claudeville_middle_placements as middle
    import claudeville_north_placements as north
    import claudeville_south_placements as south
    import claudeville_tiled_authoring as authoring
    from curate_modern_interiors_v3 import DEFAULT_OUTPUT_ROOT as V3_ROOT
    from curate_modern_pixels_v2 import DEFAULT_OUTPUT_ROOT as V2_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
    / "claudeville_modern_interiors_v3.tmj"
)
DISTRICTS = {"middle": middle, "north": north, "south": south}
CLEAR_TILE_LAYERS = (
    "Interior Furniture L1", "Interior Furniture L2", "Foreground L1", "Foreground L2",
)


class DistrictAuthoringError(ValueError):
    """Raised when a district pass is incomplete or unsafe."""


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DistrictAuthoringError(f"JSON root must be an object: {path}")
    return value


def _property(name: str, value: object) -> dict:
    kind = "bool" if isinstance(value, bool) else "int" if isinstance(value, int) \
        else "float" if isinstance(value, float) else "string"
    return {"name": name, "type": kind, "value": value}


def _catalog(root: Path) -> dict[str, dict]:
    records = _read(root / "catalog.json").get("props")
    if not isinstance(records, list):
        raise DistrictAuthoringError(f"prop catalog is malformed: {root}")
    result = {
        item.get("asset_key"): item for item in records
        if isinstance(item, dict) and isinstance(item.get("asset_key"), str)
    }
    if len(result) != len(records):
        raise DistrictAuthoringError(f"prop catalog has malformed duplicates: {root}")
    return result


def _collection_firstgid(tmj: dict, map_path: Path) -> int:
    for item in tmj.get("tilesets", []):
        if Path(str(item.get("source", ""))).stem == "interiors_props":
            return item["firstgid"]
    next_gid = 1
    for item in tmj.get("tilesets", []):
        path = (map_path.parent / item["source"]).resolve(strict=True)
        tileset = _read(path)
        next_gid = max(next_gid, item["firstgid"] + tileset["tilecount"])
    collection = V3_ROOT / "collections/interiors_props.tsj"
    tmj["tilesets"].append({
        "firstgid": next_gid,
        "source": os.path.relpath(collection, map_path.parent).replace("\\", "/"),
    })
    return next_gid


def _ensure_v3_tile_sources(
    tmj: dict, map_path: Path, module,
) -> dict[str, dict[str, int]]:
    requested = tuple(getattr(module, "V3_TILE_SOURCES", ()))
    if not requested:
        return {}
    catalog = _read(V3_ROOT / "catalog.json")
    records = catalog.get("tilesets")
    if catalog.get("schema_version") != 3 or not isinstance(records, list):
        raise DistrictAuthoringError("Modern Interiors v3 tile catalog is malformed")
    by_source = {
        item.get("source_id"): item for item in records
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    }
    if len(set(requested)) != len(requested) or not set(requested) <= by_source.keys():
        raise DistrictAuthoringError("district references unknown v3 tile sources")

    existing = {}
    next_gid = 1
    for reference in tmj.get("tilesets", []):
        path = (map_path.parent / reference["source"]).resolve(strict=True)
        tileset = _read(path)
        next_gid = max(next_gid, reference["firstgid"] + tileset["tilecount"])
        values = authoring.properties(tileset.get("properties"))
        source_id = values.get("source_id")
        if isinstance(source_id, str):
            existing[source_id] = reference["firstgid"], path, tileset

    result = {}
    for source_id in requested:
        record = by_source[source_id]
        source_path = (V3_ROOT / record["tileset"]).resolve(strict=True)
        if source_id in existing:
            firstgid, path, tileset = existing[source_id]
            if path != source_path:
                raise DistrictAuthoringError(f"v3 tile source path changed: {source_id}")
        else:
            tileset = _read(source_path)
            firstgid = next_gid
            tmj["tilesets"].append({
                "firstgid": firstgid,
                "source": os.path.relpath(source_path, map_path.parent).replace("\\", "/"),
            })
            next_gid += tileset["tilecount"]
        if (
            tileset.get("columns") != record.get("columns")
            or tileset.get("tilecount") != record.get("columns") * record.get("rows")
        ):
            raise DistrictAuthoringError(f"v3 tile source changed: {source_id}")
        result[source_id] = {
            "columns": record["columns"], "firstgid": firstgid,
            "rows": record["rows"],
        }
    return result


def _inside(obj: dict, sector: str, bounds: dict[str, tuple[int, ...]]) -> bool:
    values = authoring.properties(obj.get("properties"))
    if values.get("sector") == sector:
        return True
    x, y = obj.get("x"), obj.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return False
    left, top, right, bottom = bounds[sector]
    return left * 16 <= x < right * 16 and top * 16 <= y <= bottom * 16


def _clear(tmj: dict, module) -> dict[str, dict]:
    layers = {layer["name"]: layer for layer in tmj["layers"] if layer["name"] != "Authoring"}
    for name in CLEAR_TILE_LAYERS:
        data = layers[name]["data"]
        if name.startswith("Interior Furniture"):
            rects = tuple(module.TARGET_BOUNDS.values())
        else:
            # Foreground layers also carry hand-authored facades and overhead
            # detail. A district migration may only erase the explicit legacy
            # rectangles it declares with a zero-valued tile fill.
            rects = tuple(
                (left, top, right, bottom)
                for layer_name, left, top, right, bottom, gid
                in getattr(module, "TILE_FILLS", ())
                if layer_name == name and gid == 0
            )
        for left, top, right, bottom in rects:
            for y in range(top, bottom):
                data[y * 176 + left:y * 176 + right] = [0] * (right - left)
    for name in ("Depth Props", "Overhead Props"):
        layers[name]["objects"] = [
            obj for obj in layers[name]["objects"]
            if not any(_inside(obj, sector, module.TARGET_BOUNDS) for sector in module.TARGETS)
        ]
    return layers


def _patch_structure(tmj: dict, layers: dict[str, dict], module) -> int:
    """Apply explicit tile edits without changing the authoritative collision layer."""
    width, height = tmj.get("width"), tmj.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        raise DistrictAuthoringError("map dimensions must be integers")
    changed = 0
    for name, left, top, right, bottom, gid in getattr(module, "TILE_FILLS", ()):
        layer = layers.get(name)
        if layer is None or layer.get("type") != "tilelayer":
            raise DistrictAuthoringError(f"tile fill uses unknown layer: {name}")
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise DistrictAuthoringError(f"tile fill is outside the map: {(name, left, top)}")
        data = layer.get("data")
        if not isinstance(data, list) or len(data) != width * height:
            raise DistrictAuthoringError(f"tile layer has invalid data: {name}")
        for y in range(top, bottom):
            start = y * width + left
            data[start:start + right - left] = [gid] * (right - left)
            changed += right - left
    for name, x, y, gid in getattr(module, "TILE_EDITS", ()):
        layer = layers.get(name)
        if layer is None or layer.get("type") != "tilelayer":
            raise DistrictAuthoringError(f"tile edit uses unknown layer: {name}")
        if not (0 <= x < width and 0 <= y < height):
            raise DistrictAuthoringError(f"tile edit is outside the map: {(name, x, y)}")
        data = layer.get("data")
        if not isinstance(data, list) or len(data) != width * height:
            raise DistrictAuthoringError(f"tile layer has invalid data: {name}")
        data[y * width + x] = gid
        changed += 1
    return changed


def _source_tile_gids(
    tmj: dict, map_path: Path, source_ids: set[str],
) -> dict[tuple[str, int, int], int]:
    atlas_data = _read(V2_ROOT / "atlas.json")
    if atlas_data.get("schema_version") != 2:
        raise DistrictAuthoringError("curated atlas schema is not version two")
    atlases = {
        item.get("key"): item for item in atlas_data.get("atlases", [])
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    sources = {
        item.get("source_id"): item for item in atlas_data.get("sources", [])
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    }
    if not source_ids <= sources.keys():
        raise DistrictAuthoringError("tile stamp references an unknown curated source")
    firstgids: dict[str, int] = {}
    tiles_root = (V2_ROOT / "tiles").resolve(strict=True)
    for reference in tmj.get("tilesets", []):
        source = (map_path.parent / str(reference.get("source", ""))).resolve(strict=True)
        if source.parent != tiles_root or source.stem not in atlases:
            continue
        tileset = _read(source)
        record = atlases[source.stem]
        if (
            tileset.get("tilewidth") != 16 or tileset.get("tileheight") != 16
            or tileset.get("tilecount") != record.get("tile_count")
        ):
            raise DistrictAuthoringError(f"curated tileset changed: {source.name}")
        firstgids[source.stem] = reference.get("firstgid")
    required_atlases = {sources[source_id].get("atlas") for source_id in source_ids}
    if not required_atlases <= firstgids.keys():
        raise DistrictAuthoringError("candidate map is missing a stamp atlas")

    tile_data = _read(V2_ROOT / "tiles.json")
    if tile_data.get("schema_version") != 1:
        raise DistrictAuthoringError("curated tile index schema is not version one")
    result, counts = {}, {source_id: 0 for source_id in source_ids}
    occupied: set[tuple[str, int]] = set()
    for item in tile_data.get("tiles", []):
        if not isinstance(item, dict) or item.get("source_id") not in source_ids:
            continue
        source_id, atlas = item["source_id"], item.get("atlas")
        column, row, index = item.get("source_col"), item.get("source_row"), item.get("atlas_index")
        if (
            atlas != sources[source_id].get("atlas")
            or not all(isinstance(value, int) for value in (column, row, index))
            or not 0 <= index < atlases[atlas].get("tile_count", -1)
        ):
            raise DistrictAuthoringError(f"malformed curated tile record: {source_id}")
        key, atlas_slot = (source_id, column, row), (atlas, index)
        if key in result or atlas_slot in occupied:
            raise DistrictAuthoringError(f"duplicate curated tile record: {key}")
        result[key] = firstgids[atlas] + index
        occupied.add(atlas_slot)
        counts[source_id] += 1
    for source_id, count in counts.items():
        if count != sources[source_id].get("tile_count"):
            raise DistrictAuthoringError(f"curated tile source is incomplete: {source_id}")
    return result


def _apply_tile_stamps(
    tmj: dict, layers: dict[str, dict], module, map_path: Path,
) -> int:
    stamps = getattr(module, "WORKSHOP_TILE_STAMPS", ())
    if not stamps:
        return 0
    gids = _source_tile_gids(tmj, map_path, {stamp[0] for stamp in stamps})
    width, height = tmj["width"], tmj["height"]
    written: set[tuple[str, int, int]] = set()
    total = 0
    for source_id, source_rect, destination, layer_name in stamps:
        sx, sy, stamp_width, stamp_height = source_rect
        dx, dy = destination
        values = (sx, sy, stamp_width, stamp_height, dx, dy)
        if not all(isinstance(value, int) for value in values) or min(stamp_width, stamp_height) <= 0:
            raise DistrictAuthoringError(f"malformed tile stamp: {source_rect}")
        if not any(
            left <= dx and top <= dy and dx + stamp_width <= right
            and dy + stamp_height <= bottom
            for left, top, right, bottom in module.TARGET_BOUNDS.values()
        ):
            raise DistrictAuthoringError(f"tile stamp is outside its parcel: {destination}")
        layer = layers.get(layer_name)
        data = None if layer is None else layer.get("data")
        if layer is None or layer.get("type") != "tilelayer" or not isinstance(data, list):
            raise DistrictAuthoringError(f"tile stamp uses an invalid layer: {layer_name}")
        if len(data) != width * height:
            raise DistrictAuthoringError(f"tile layer has invalid data: {layer_name}")
        stamp_total = 0
        for offset_y in range(stamp_height):
            for offset_x in range(stamp_width):
                gid = gids.get((source_id, sx + offset_x, sy + offset_y))
                if gid is None:  # Transparent source tile.
                    continue
                x, y = dx + offset_x, dy + offset_y
                slot = (layer_name, x, y)
                if slot in written or data[y * width + x]:
                    raise DistrictAuthoringError(f"tile stamps overlap at {x},{y}")
                data[y * width + x] = gid
                written.add(slot)
                stamp_total += 1
        if not stamp_total:
            raise DistrictAuthoringError(f"tile stamp is empty: {source_rect}")
        total += stamp_total
    return total


def _add_props(
    tmj: dict, layers: dict[str, dict], module, district: str, firstgid: int,
) -> list[dict]:
    v2, v3 = _catalog(V2_ROOT), _catalog(V3_ROOT)
    created, next_id = [], max(tmj.get("nextobjectid", 1), 1)
    for index, placement in enumerate(module.PLACEMENTS, 1):
        sector, zone, role, cluster, key, visual_x, visual_y = placement
        if sector not in module.TARGETS:
            raise DistrictAuthoringError(f"{district} placement uses another sector: {sector}")
        left, top, right, bottom = module.TARGET_BOUNDS[sector]
        if not (left <= visual_x < right and top <= visual_y <= bottom):
            raise DistrictAuthoringError(f"{sector} placement is outside its parcel: {placement}")
        record = v2.get(key) or v3.get(key)
        if record is None:
            raise DistrictAuthoringError(f"unknown placement asset: {key}")
        width, height = record["native_size"]
        values = {
            "anchor_x": record["anchor"][0], "anchor_y": record["anchor"][1],
            "asset_key": key, "display_scale": record.get("display_scale", 1),
            "purpose_cluster": cluster, "sector": sector,
            "semantic_type": role, "zone": zone,
        }
        item = {
            "id": next_id, "name": f"{district}-{index:03d}-{role}", "type": "",
            "x": visual_x * 16, "y": visual_y * 16, "width": width, "height": height,
            "rotation": 0, "visible": True,
            "properties": [_property(name, values[name]) for name in sorted(values)],
        }
        if key in v3:
            item["gid"] = firstgid + v3[key]["tiled_tile_id"]
        layers["Depth Props"]["objects"].append(item)
        created.append(item)
        next_id += 1
    tmj["nextobjectid"] = next_id
    return created


def _relink(tmj: dict, created: list[dict], targets: frozenset[str]) -> int:
    candidates: dict[tuple[str, str, str], list[dict]] = {}
    for item in created:
        values = authoring.properties(item["properties"])
        candidates.setdefault(
            (values["sector"], values["zone"], values["semantic_type"]), []
        ).append(item)
    group = next(layer for layer in tmj["layers"] if layer["name"] == "Authoring")
    interactions = next(layer for layer in group["layers"] if layer["name"] == "Interactions")
    count = 0
    for item in interactions["objects"]:
        values = authoring.properties(item.get("properties"))
        if values.get("sector") not in targets:
            continue
        matching = candidates.get(
            (values["sector"], values["zone"], values["interaction_type"]), []
        )
        if not matching:
            if values.get("art_layer") in CLEAR_TILE_LAYERS:
                continue
            raise DistrictAuthoringError(
                f"no {values['interaction_type']} art for {values['semantic_id']}"
            )
        center_x = item["x"] + item.get("width", 0) / 2
        center_y = item["y"] + item.get("height", 0) / 2
        linked = min(
            matching,
            key=lambda prop: abs(prop["x"] - center_x) + abs(prop["y"] - center_y),
        )
        properties = [
            prop for prop in item["properties"]
            if prop["name"] not in {"art_asset_key", "art_layer", "art_object_id"}
        ]
        properties.extend((
            _property("art_layer", "Depth Props"),
            _property("art_object_id", linked["id"]),
        ))
        item["properties"] = sorted(properties, key=lambda prop: prop["name"])
        count += 1
    return count


def author_district(district: str, map_path: Path = DEFAULT_MAP) -> dict:
    """Replace one district's procedural furniture and preserve all navigation."""
    if district not in DISTRICTS:
        raise DistrictAuthoringError(f"unsupported district: {district}")
    module = DISTRICTS[district]
    path = Path(map_path).expanduser().resolve(strict=True)
    tmj = _read(path)
    if not authoring.is_tiled_first(tmj):
        raise DistrictAuthoringError("district passes require the v3 Tiled-first profile")
    values = authoring.properties(tmj.get("properties"))
    slice_revision = values.get("vertical_slice_revision")
    if not isinstance(slice_revision, int) or slice_revision < 3:
        raise DistrictAuthoringError("district passes require revision-three or newer slices")
    revision_key = f"{district}_district_revision"
    revision = values.get(revision_key)
    if revision == module.REVISION:
        raise DistrictAuthoringError(f"{district} district revision is already authored")
    if revision is not None and (
        not isinstance(revision, int) or revision > module.REVISION
    ):
        raise DistrictAuthoringError(f"unsupported {district} revision: {revision}")
    prop_firstgid = _collection_firstgid(tmj, path)
    v3_tile_sources = _ensure_v3_tile_sources(tmj, path, module)
    legacy_tiles = semantics.clear_tileset_tiles_in_rects(
        tmj, path, "interiors", tuple(module.TARGET_BOUNDS.values()),
    )
    for source_stem, rects in getattr(module, "LEGACY_TILESET_CLEARS", ()):
        legacy_tiles += semantics.clear_tileset_tiles_in_rects(
            tmj, path, source_stem, tuple(rects),
        )
    layers = _clear(tmj, module)
    try:
        semantic_changes = (
            semantics.prepare_semantics(tmj, module)
            if revision is None
            else {"added_interactions": 0, "added_zones": 0, "removed_shapes": 0}
        )
        semantics.update_interaction_stances(tmj, module)
        structured_tiles = semantics.paint_visual_structure(
            layers, module, v3_tile_sources,
        )
        floor_tiles = semantics.patch_zone_floors(tmj, layers, module)
        stamped_tiles = _apply_tile_stamps(tmj, layers, module, path)
        patched_tiles = _patch_structure(tmj, layers, module)
        created = _add_props(
            tmj, layers, module, district, prop_firstgid
        )
        blocker_shapes = semantics.add_blockers(tmj, module, created)
    except ValueError as exc:
        raise DistrictAuthoringError(str(exc)) from exc
    relinked = _relink(tmj, created, module.TARGETS)
    tmj["properties"] = [
        item for item in tmj["properties"] if item.get("name") != revision_key
    ]
    tmj["properties"].append(_property(revision_key, module.REVISION))
    authoring.validate_authoring_group(tmj)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(tmj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {
        "created_props": len(created),
        "legacy_tiles_removed": legacy_tiles,
        "floor_tiles": floor_tiles,
        "patched_tiles": patched_tiles,
        "relinked_interactions": relinked,
        "semantic_shapes": sum(semantic_changes.values()) + blocker_shapes,
        "stamped_tiles": stamped_tiles,
        "structured_tiles": structured_tiles,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("district", choices=sorted(DISTRICTS))
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    args = parser.parse_args(argv)
    try:
        result = author_district(args.district, args.map)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"Authored {result['created_props']} props, patched "
        f"{result['patched_tiles'] + result['floor_tiles'] + result['structured_tiles']} "
        "tiles, stamped "
        f"{result['stamped_tiles']} tiles, migrated {result['semantic_shapes']} shapes, "
        "and relinked "
        f"{result['relinked_interactions']} {args.district} interactions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
