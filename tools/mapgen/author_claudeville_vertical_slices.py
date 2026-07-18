"""Apply the explicit Bank, Home 5, and Cafe art pass to the v3 Tiled source.

This is an authoring helper, not a build step. It writes only the requested TMJ and
refuses to run twice; the resulting map remains the visual source of truth.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

try:
    from tools.mapgen import author_claudeville_districts as district_authoring
    from tools.mapgen import claudeville_district_semantics as semantics
    from tools.mapgen import claudeville_tiled_authoring as authoring
    from tools.mapgen.claudeville_vertical_slice_layouts import (
        CLEAR_TILE_LAYERS,
        INTERACTION_STANCE_UPDATES,
        LEGACY_FACADE_CLEARS,
        PLACEMENTS,
        SLICE_REVISION,
        STRUCTURE_CONFIG,
        TARGET_BOUNDS,
        TARGETS,
    )
    from tools.mapgen.curate_modern_interiors_v3 import (
        DEFAULT_OUTPUT_ROOT as V3_ROOT,
    )
    from tools.mapgen.curate_modern_pixels_v2 import (
        DEFAULT_OUTPUT_ROOT as V2_ROOT,
    )
except ModuleNotFoundError:  # Direct script execution.
    import author_claudeville_districts as district_authoring
    import claudeville_district_semantics as semantics
    import claudeville_tiled_authoring as authoring
    from claudeville_vertical_slice_layouts import (
        CLEAR_TILE_LAYERS,
        INTERACTION_STANCE_UPDATES,
        LEGACY_FACADE_CLEARS,
        PLACEMENTS,
        SLICE_REVISION,
        STRUCTURE_CONFIG,
        TARGET_BOUNDS,
        TARGETS,
    )
    from curate_modern_interiors_v3 import DEFAULT_OUTPUT_ROOT as V3_ROOT
    from curate_modern_pixels_v2 import DEFAULT_OUTPUT_ROOT as V2_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
    / "claudeville_modern_interiors_v3.tmj"
)
class SliceAuthoringError(ValueError):
    """Raised when the explicit pass cannot be applied safely."""


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SliceAuthoringError(f"JSON root must be an object: {path}")
    return value


def _props(value) -> dict:
    return authoring.properties(value)


def _property(name: str, value: object) -> dict:
    kind = "bool" if isinstance(value, bool) else "int" if isinstance(value, int) \
        else "float" if isinstance(value, float) else "string"
    return {"name": name, "type": kind, "value": value}


def _contained_catalog(root: Path) -> dict[str, dict]:
    catalog = _read(root / "catalog.json")
    records = catalog.get("props")
    if not isinstance(records, list):
        raise SliceAuthoringError(f"prop catalog is malformed: {root}")
    return {item["asset_key"]: item for item in records}


def _collection_firstgid(tmj: dict, map_path: Path) -> int:
    for item in tmj["tilesets"]:
        if Path(str(item.get("source", ""))).stem == "interiors_props":
            return item["firstgid"]
    next_gid = 1
    for item in tmj["tilesets"]:
        path = (map_path.parent / item["source"]).resolve(strict=True)
        tileset = _read(path)
        next_gid = max(next_gid, item["firstgid"] + tileset["tilecount"])
    collection = V3_ROOT / "collections/interiors_props.tsj"
    source = os.path.relpath(collection, map_path.parent).replace("\\", "/")
    tmj["tilesets"].append({"firstgid": next_gid, "source": source})
    return next_gid


def _inside(obj: dict, sector: str) -> bool:
    values = _props(obj.get("properties"))
    if values.get("sector") == sector:
        return True
    x, y = obj.get("x"), obj.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return False
    left, top, right, bottom = TARGET_BOUNDS[sector]
    return left * 16 <= x < right * 16 and top * 16 <= y <= bottom * 16


def _clear_target_art(tmj: dict) -> dict[str, dict]:
    layers = {layer["name"]: layer for layer in tmj["layers"] if layer["name"] != "Authoring"}
    for name in CLEAR_TILE_LAYERS:
        data = layers[name]["data"]
        rects = (
            tuple(TARGET_BOUNDS.values())
            if name.startswith("Interior Furniture")
            else tuple(
                (left, top, right, bottom)
                for layer_name, left, top, right, bottom in LEGACY_FACADE_CLEARS
                if layer_name == name
            )
        )
        for left, top, right, bottom in rects:
            for y in range(top, bottom):
                data[y * 176 + left:y * 176 + right] = [0] * (right - left)
    for name in ("Depth Props", "Overhead Props"):
        layers[name]["objects"] = [
            obj for obj in layers[name]["objects"]
            if not any(_inside(obj, sector) for sector in TARGETS)
        ]
    return layers


def _add_props(tmj: dict, layers: dict[str, dict], firstgid: int) -> list[dict]:
    v2, v3 = _contained_catalog(V2_ROOT), _contained_catalog(V3_ROOT)
    created = []
    next_id = max(tmj.get("nextobjectid", 1), 1)
    for index, (sector, zone, role, cluster, key, vx, vy) in enumerate(PLACEMENTS, 1):
        record = v2.get(key) or v3.get(key)
        if record is None:
            raise SliceAuthoringError(f"unknown placement asset: {key}")
        width, height = record["native_size"]
        values = {
            "anchor_x": record["anchor"][0], "anchor_y": record["anchor"][1],
            "asset_key": key, "display_scale": record.get("display_scale", 1),
            "purpose_cluster": cluster, "sector": sector,
            "semantic_type": role, "zone": zone,
        }
        obj = {
            "id": next_id, "name": f"slice-{index:03d}-{role}", "type": "",
            "x": vx * 16, "y": vy * 16, "width": width, "height": height,
            "rotation": 0, "visible": True,
            "properties": [_property(name, values[name]) for name in sorted(values)],
        }
        if key in v3:
            obj["gid"] = firstgid + v3[key]["tiled_tile_id"]
        layers["Depth Props"]["objects"].append(obj)
        created.append(obj)
        next_id += 1
    tmj["nextobjectid"] = next_id
    return created


def _refine_home5_semantics(tmj: dict, created: list[dict]) -> None:
    group = next(layer for layer in tmj["layers"] if layer["name"] == "Authoring")
    children = {layer["name"]: layer for layer in group["layers"]}
    zones, interactions = children["Zones"], children["Interactions"]

    old_zone_count = len(zones["objects"])
    zones["objects"] = [
        item for item in zones["objects"]
        if not (
            _props(item.get("properties")).get("zone") == "home_5.bedroom"
            and item.get("x") == 1024 and item.get("y") == 1376
        )
    ]
    if len(zones["objects"]) != old_zone_count - 1:
        raise SliceAuthoringError("Home 5 bathroom migration needs one bedroom zone cell")

    old_interaction_count = len(interactions["objects"])
    interactions["objects"] = [
        item for item in interactions["objects"]
        if not (
            _props(item.get("properties")).get("interaction")
            == "home_5.bedroom.bed-001"
            and item.get("x") == 992 and item.get("y") == 1344
        )
    ]
    if len(interactions["objects"]) != old_interaction_count - 1:
        raise SliceAuthoringError("Home 5 bedroom migration needs one secondary bed cell")

    created_by_key = {
        _props(item["properties"])["asset_key"]: item for item in created
        if _props(item["properties"]).get("sector") == "Home 5"
    }
    wardrobe = created_by_key.get("prop.interiors_v3.bedroom.0384")
    if wardrobe is None:
        raise SliceAuthoringError("Home 5 wardrobe art is missing")

    next_id = tmj["nextobjectid"]
    zones["objects"].append(authoring.make_authoring_object(
        next_id, "home_5.bathroom.shape-001", 1024, 1344,
        width=32, height=64, sector="Home 5", zone="home_5.bathroom",
        room_type="bathroom",
    ))
    interactions["objects"].append(authoring.make_authoring_object(
        next_id + 1, "home_5.bathroom.toilet-001.shape-001", 1024, 1344,
        width=32, height=32, sector="Home 5", zone="home_5.bathroom",
        interaction="home_5.bathroom.toilet-001", interaction_type="toilet",
        art_layer="Depth Props", allowed_room_types="bathroom",
        blocker_policy="require-blocked", stance_x=32, stance_y=43,
    ))
    children["Blockers"]["objects"].append(authoring.make_authoring_object(
        next_id + 2, "home_5.bedroom.wardrobe-blocker.shape-001", 992, 1344,
        width=32, height=32, sector="Home 5", zone="home_5.bedroom",
        art_layer="Depth Props", art_object_id=wardrobe["id"],
        blocker_policy="require-blocked",
    ))
    tmj["nextobjectid"] = next_id + 3


def _refine_cafe_semantics(tmj: dict) -> None:
    group = next(layer for layer in tmj["layers"] if layer["name"] == "Authoring")
    children = {layer["name"]: layer for layer in group["layers"]}
    zones, interactions = children["Zones"], children["Interactions"]
    service_shapes = [
        item for item in zones["objects"]
        if _props(item.get("properties")).get("zone") == "cafe.service"
    ]
    expected = {
        (1568, 704, 160, 32): 96,
        (1536, 736, 192, 32): 128,
        (1536, 768, 192, 32): 128,
        (1536, 800, 192, 32): 192,
    }
    if len(service_shapes) != len(expected) or {
        (item["x"], item["y"], item["width"], item["height"])
        for item in service_shapes
    } != set(expected):
        raise SliceAuthoringError("Cafe restroom migration needs four service rows")
    for item in service_shapes:
        item["width"] = expected[(item["x"], item["y"], item["width"], item["height"])]

    next_id = tmj["nextobjectid"]
    zones["objects"].append(authoring.make_authoring_object(
        next_id, "cafe.restroom.shape-001", 1664, 704,
        width=64, height=96, sector="Claudeville Cafe",
        zone="cafe.restroom", room_type="restroom",
    ))
    interactions["objects"].append(authoring.make_authoring_object(
        next_id + 1, "cafe.restroom.toilet-001.shape-001", 1664, 768,
        width=32, height=32, sector="Claudeville Cafe", zone="cafe.restroom",
        interaction="cafe.restroom.toilet-001", interaction_type="toilet",
        art_layer="Depth Props", allowed_room_types="restroom",
        blocker_policy="require-blocked", stance_x=51, stance_y=24,
    ))
    tmj["nextobjectid"] = next_id + 2


def _normalize_cafe_counter_zone(tmj: dict) -> None:
    group = next(layer for layer in tmj["layers"] if layer["name"] == "Authoring")
    zones = next(layer for layer in group["layers"] if layer["name"] == "Zones")
    restroom = [
        item for item in zones["objects"]
        if _props(item.get("properties")).get("zone") == "cafe.restroom"
    ]
    counter_row = [
        item for item in zones["objects"]
        if _props(item.get("properties")).get("zone") == "cafe.service"
        and item.get("x") == 1536 and item.get("y") == 800
    ]
    if len(restroom) != 1 or len(counter_row) != 1:
        raise SliceAuthoringError("Cafe counter-zone normalization is incomplete")
    if restroom[0].get("height") not in {96, 128} \
            or counter_row[0].get("width") not in {128, 192}:
        raise SliceAuthoringError("Cafe counter-zone geometry is unexpected")
    restroom[0]["height"] = 96
    counter_row[0]["width"] = 192


def _update_interaction_stances(tmj: dict) -> None:
    group = next(layer for layer in tmj["layers"] if layer["name"] == "Authoring")
    interactions = next(
        layer for layer in group["layers"] if layer["name"] == "Interactions"
    )
    pending = {
        (sector, interaction): (stance_x, stance_y)
        for sector, interaction, stance_x, stance_y in INTERACTION_STANCE_UPDATES
    }
    matched = set()
    for item in interactions["objects"]:
        values = _props(item.get("properties"))
        key = values.get("sector"), values.get("interaction")
        if key not in pending:
            continue
        stance_x, stance_y = pending[key]
        for prop in item["properties"]:
            if prop["name"] == "stance_x":
                prop["value"] = stance_x
            elif prop["name"] == "stance_y":
                prop["value"] = stance_y
        matched.add(key)
    if matched != pending.keys():
        raise SliceAuthoringError("slice stance updates reference missing interactions")


def _relink(tmj: dict, created: list[dict]) -> None:
    by_role = {}
    for obj in created:
        values = _props(obj["properties"])
        by_role.setdefault(
            (values["sector"], values["zone"], values["semantic_type"]), []
        ).append(obj)
    group = next(layer for layer in tmj["layers"] if layer["name"] == "Authoring")
    interactions = next(layer for layer in group["layers"] if layer["name"] == "Interactions")
    for item in interactions["objects"]:
        values = _props(item["properties"])
        if values.get("sector") not in TARGETS:
            continue
        candidates = by_role.get(
            (values["sector"], values["zone"], values["interaction_type"]), []
        )
        if not candidates:
            raise SliceAuthoringError(
                f"no authored art for {values['semantic_id']} ({values['interaction_type']})"
            )
        cx = item["x"] + item.get("width", 0) / 2
        cy = item["y"] + item.get("height", 0) / 2
        linked = min(
            candidates,
            key=lambda obj: abs(obj["x"] - cx) + abs(obj["y"] - cy),
        )
        for prop in item["properties"]:
            if prop["name"] == "art_layer":
                prop["value"] = "Depth Props"
            elif prop["name"] == "art_object_id":
                prop["value"] = linked["id"]
        if not any(prop["name"] == "art_object_id" for prop in item["properties"]):
            item["properties"].append(_property("art_object_id", linked["id"]))
        item["properties"] = [
            prop for prop in item["properties"] if prop["name"] != "art_asset_key"
        ]

    wardrobe = next(
        (
            item for item in created
            if _props(item.get("properties")).get("asset_key")
            == "prop.interiors_v3.bedroom.0384"
        ),
        None,
    )
    blockers = next(layer for layer in group["layers"] if layer["name"] == "Blockers")
    wardrobe_shapes = [
        item for item in blockers["objects"]
        if _props(item.get("properties")).get("semantic_id")
        == "home_5.bedroom.wardrobe-blocker.shape-001"
    ]
    if wardrobe is None or len(wardrobe_shapes) != 1:
        raise SliceAuthoringError("Home 5 wardrobe blocker cannot be relinked")
    for prop in wardrobe_shapes[0]["properties"]:
        if prop["name"] == "art_object_id":
            prop["value"] = wardrobe["id"]


def author_slices(map_path: Path = DEFAULT_MAP) -> dict:
    """Apply the explicit placements once and atomically update the candidate TMJ."""
    path = Path(map_path).expanduser().resolve(strict=True)
    tmj = _read(path)
    if not authoring.is_tiled_first(tmj):
        raise SliceAuthoringError("vertical slices require the v3 Tiled-first profile")
    props = _props(tmj.get("properties"))
    revision = props.get("vertical_slice_revision")
    if revision == SLICE_REVISION:
        raise SliceAuthoringError(f"vertical slice revision {SLICE_REVISION} is already authored")
    if revision is not None and (not isinstance(revision, int) or revision > SLICE_REVISION):
        raise SliceAuthoringError(f"unsupported vertical slice revision: {revision}")
    try:
        legacy_tiles = semantics.clear_tileset_tiles_in_rects(
            tmj, path, "interiors", tuple(TARGET_BOUNDS.values()),
        )
        tile_sources = district_authoring._ensure_v3_tile_sources(
            tmj, path, STRUCTURE_CONFIG,
        )
    except ValueError as exc:
        raise SliceAuthoringError(str(exc)) from exc
    layers = _clear_target_art(tmj)
    created = _add_props(tmj, layers, _collection_firstgid(tmj, path))
    try:
        semantics.paint_visual_structure(layers, STRUCTURE_CONFIG, tile_sources)
    except ValueError as exc:
        raise SliceAuthoringError(str(exc)) from exc
    if revision is None or revision < 3:
        _refine_home5_semantics(tmj, created)
    if revision is None or revision < 7:
        _refine_cafe_semantics(tmj)
    if revision is None or revision < 10:
        _normalize_cafe_counter_zone(tmj)
    _update_interaction_stances(tmj)
    _relink(tmj, created)
    tmj["properties"] = [
        item for item in tmj["properties"] if item.get("name") != "vertical_slice_revision"
    ]
    tmj["properties"].append(_property("vertical_slice_revision", SLICE_REVISION))
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(tmj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {
        "created_props": len(created), "legacy_tiles_removed": legacy_tiles,
        "removed_targets": sorted(TARGETS),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    args = parser.parse_args(argv)
    try:
        result = author_slices(args.map)
    except (OSError, json.JSONDecodeError, SliceAuthoringError) as exc:
        parser.error(str(exc))
    print(f"Authored {result['created_props']} purposeful props in three approval slices")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
