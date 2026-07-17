"""Apply explicit, reviewable Modern Pixels district passes to Claudeville v3."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from tools.mapgen import claudeville_north_placements as north
    from tools.mapgen import claudeville_tiled_authoring as authoring
    from tools.mapgen.curate_modern_interiors_v3 import DEFAULT_OUTPUT_ROOT as V3_ROOT
    from tools.mapgen.curate_modern_pixels_v2 import DEFAULT_OUTPUT_ROOT as V2_ROOT
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_north_placements as north
    import claudeville_tiled_authoring as authoring
    from curate_modern_interiors_v3 import DEFAULT_OUTPUT_ROOT as V3_ROOT
    from curate_modern_pixels_v2 import DEFAULT_OUTPUT_ROOT as V2_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
    / "claudeville_modern_interiors_v3.tmj"
)
DISTRICTS = {"north": north}
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
        for left, top, right, bottom in module.TARGET_BOUNDS.values():
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
    if values.get("vertical_slice_revision") != 3:
        raise DistrictAuthoringError("district passes require approved revision-three slices")
    revision_key = f"{district}_district_revision"
    revision = values.get(revision_key)
    if revision == module.REVISION:
        raise DistrictAuthoringError(f"{district} district revision is already authored")
    if revision is not None and (
        not isinstance(revision, int) or revision > module.REVISION
    ):
        raise DistrictAuthoringError(f"unsupported {district} revision: {revision}")
    layers = _clear(tmj, module)
    patched_tiles = _patch_structure(tmj, layers, module)
    created = _add_props(
        tmj, layers, module, district, _collection_firstgid(tmj, path)
    )
    relinked = _relink(tmj, created, module.TARGETS)
    tmj["properties"] = [
        item for item in tmj["properties"] if item.get("name") != revision_key
    ]
    tmj["properties"].append(_property(revision_key, module.REVISION))
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(tmj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {
        "created_props": len(created),
        "patched_tiles": patched_tiles,
        "relinked_interactions": relinked,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("district", choices=sorted(DISTRICTS))
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    args = parser.parse_args(argv)
    try:
        result = author_district(args.district, args.map)
    except (OSError, json.JSONDecodeError, DistrictAuthoringError) as exc:
        parser.error(str(exc))
    print(
        f"Authored {result['created_props']} props, patched "
        f"{result['patched_tiles']} tiles, and relinked "
        f"{result['relinked_interactions']} {args.district} interactions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
