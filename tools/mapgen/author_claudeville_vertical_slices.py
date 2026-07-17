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
    from tools.mapgen import claudeville_tiled_authoring as authoring
    from tools.mapgen.curate_modern_interiors_v3 import (
        DEFAULT_OUTPUT_ROOT as V3_ROOT,
    )
    from tools.mapgen.curate_modern_pixels_v2 import (
        DEFAULT_OUTPUT_ROOT as V2_ROOT,
    )
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_tiled_authoring as authoring
    from curate_modern_interiors_v3 import DEFAULT_OUTPUT_ROOT as V3_ROOT
    from curate_modern_pixels_v2 import DEFAULT_OUTPUT_ROOT as V2_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
    / "claudeville_modern_interiors_v3.tmj"
)
TARGETS = {"Bank", "Home 5", "Claudeville Cafe"}
SLICE_REVISION = 3
TARGET_BOUNDS = {
    "Bank": (10, 12, 29, 32),
    "Home 5": (52, 70, 67, 92),
    "Claudeville Cafe": (92, 43, 109, 64),
}
CLEAR_TILE_LAYERS = (
    "Interior Furniture L1", "Interior Furniture L2", "Foreground L1", "Foreground L2",
)

# sector, zone, semantic role, cluster, stable asset key, visual x, visual y
PLACEMENTS = (
    # Bank archive: wall-aligned secure storage and one working surface.
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.filing_cabinet", 12, 16),
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.display_cabinet", 14, 16),
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.filing_cabinet", 16, 16),
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.copier", 12, 17),
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.paper_stack", 14, 17),
    ("Bank", "bank.archive", "archive-cabinets", "secure archive", "prop.office.table_walnut_medium", 16, 17),
    # Bank operations: two intact workstation pairs with a central aisle.
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.printer_station", 19, 16),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.computer_desk", 21, 16),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.manager_chair", 21, 17),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.computer_desk", 24, 16),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.manager_chair", 24, 17),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.computer_desk", 27, 16),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.manager_chair", 27, 17),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.dual_monitors", 24, 15),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.phone", 27, 15),
    ("Bank", "bank.operations", "operations-desk", "staff operations", "prop.office.notice_board", 26, 14),
    # Bank teller: one uninterrupted staff/customer boundary.
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_walnut_left", 19, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_walnut_middle", 21, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_walnut_middle", 23, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_walnut_middle", 25, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.counter_walnut_right", 27, 23),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.cash_register", 21, 21),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.cash_register", 25, 21),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.chair_blue", 21, 22),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.chair_orange", 25, 22),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.printer", 19, 20),
    ("Bank", "bank.teller", "teller-counter", "teller line", "prop.office.filing_cabinet", 27, 20),
    # Bank advisory: two private, complete adviser-and-guest groupings.
    ("Bank", "bank.advisory", "advisory-desk", "advisory west", "prop.office.computer_desk", 12, 23),
    ("Bank", "bank.advisory", "advisory-desk", "advisory west", "prop.office.manager_chair", 12, 24),
    ("Bank", "bank.advisory", "advisory-desk", "advisory west", "prop.office.chair_blue_side", 15, 23),
    ("Bank", "bank.advisory", "advisory-desk", "advisory east", "prop.office.computer_desk", 12, 28),
    ("Bank", "bank.advisory", "advisory-desk", "advisory east", "prop.office.manager_chair", 12, 29),
    ("Bank", "bank.advisory", "advisory-desk", "advisory east", "prop.office.chair_orange_side", 15, 28),
    ("Bank", "bank.advisory", "advisory-desk", "advisory support", "prop.office.filing_cabinet", 15, 20),
    ("Bank", "bank.advisory", "advisory-desk", "advisory support", "prop.office.wall_chart", 12, 20),
    ("Bank", "bank.advisory", "advisory-desk", "advisory support", "prop.office.water_cooler", 15, 30),
    # Bank waiting: one coherent seating bay; the entrance aisle stays clear.
    ("Bank", "bank.waiting", "waiting-seating", "waiting", "prop.office.sofa_dark", 22, 29),
    ("Bank", "bank.waiting", "waiting-seating", "waiting", "prop.office.side_table", 24, 29),
    ("Bank", "bank.waiting", "waiting-seating", "waiting", "prop.office.armchair_dark", 26, 29),
    ("Bank", "bank.waiting", "waiting-seating", "waiting", "prop.office.notice_board", 27, 27),
    ("Bank", "bank.waiting", "waiting-seating", "waiting", "prop.office.waste_bin", 20, 29),
    ("Bank", "bank.waiting", "entrance", "front threshold", "prop.facade.door_open", 19, 32),

    # Home 5 living: sofa, coffee table, TV console, storage and lighting.
    ("Home 5", "home_5.living_room", "entrance", "front threshold", "prop.facade.door_open", 58, 76),
    ("Home 5", "home_5.living_room", "shelf", "media", "prop.interiors_v3.living.0023", 56, 78),
    ("Home 5", "home_5.living_room", "shelf", "media", "prop.interiors_v3.living.0017", 55, 78),
    ("Home 5", "home_5.living_room", "common-room-table", "media", "prop.interiors_v3.living.0003", 56, 81),
    ("Home 5", "home_5.living_room", "common-room-table", "media", "prop.interiors_v3.living.0029", 58, 81),
    ("Home 5", "home_5.living_room", "common-room-table", "media", "prop.interiors_v3.living.0065", 55, 81),
    ("Home 5", "home_5.living_room", "shelf", "media", "prop.interiors_v3.living.0079", 59, 81),
    # Home 5 kitchen: a compact north/east-wall workflow.
    ("Home 5", "home_5.kitchen", "cooking-area", "kitchen", "prop.interiors_v3.kitchen.0121", 61, 78),
    ("Home 5", "home_5.kitchen", "cooking-area", "kitchen", "prop.interiors_v3.kitchen.0127", 63, 78),
    ("Home 5", "home_5.kitchen", "cooking-area", "kitchen", "prop.interiors_v3.kitchen.0142", 61, 76),
    ("Home 5", "home_5.kitchen", "refrigerator", "kitchen", "prop.interiors_v3.kitchen.0160", 63, 81),
    ("Home 5", "home_5.kitchen", "cooking-area", "kitchen", "prop.interiors_v3.kitchen.0195", 61, 81),
    ("Home 5", "home_5.kitchen", "cooking-area", "kitchen", "prop.interiors_v3.kitchen.0208", 62, 81),
    # Home 5 bedroom: resident planning desk, one bed and a blocked wardrobe.
    ("Home 5", "home_5.bedroom", "desk", "planning", "prop.interiors_v3.bedroom.0262", 56, 85),
    ("Home 5", "home_5.bedroom", "desk", "planning", "prop.office.notice_board", 56, 83),
    ("Home 5", "home_5.bedroom", "bed", "sleep", "prop.interiors_v3.bedroom.0012", 58, 86),
    ("Home 5", "home_5.bedroom", "storage", "storage", "prop.interiors_v3.living.0037", 60, 86),
    ("Home 5", "home_5.bedroom", "storage", "storage", "prop.interiors_v3.bedroom.0384", 62, 86),
    # Home 5 bathroom: a separate east bay aligned to canonical blocked cells.
    ("Home 5", "home_5.bathroom", "wash", "bathroom", "prop.interiors_v3.bathroom.0151", 64, 84),
    ("Home 5", "home_5.bathroom", "toilet", "bathroom", "prop.interiors_v3.bathroom.0035", 65, 86),
    ("Home 5", "home_5.bathroom", "shower", "bathroom", "prop.interiors_v3.bathroom.0064", 64, 86),

    # Cafe back bar: refrigeration, sink/prep, espresso and storage in workflow order.
    ("Claudeville Cafe", "cafe.service", "prep", "prep kitchen", "prop.interiors_v3.kitchen.0160", 96, 49),
    ("Claudeville Cafe", "cafe.service", "prep", "prep kitchen", "prop.interiors_v3.kitchen.0121", 98, 49),
    ("Claudeville Cafe", "cafe.service", "prep", "prep kitchen", "prop.interiors_v3.kitchen.0142", 100, 47),
    ("Claudeville Cafe", "cafe.service", "prep", "prep kitchen", "prop.office.coffee_station", 102, 49),
    ("Claudeville Cafe", "cafe.service", "storage", "prep kitchen", "prop.interiors_v3.kitchen.0195", 104, 49),
    ("Claudeville Cafe", "cafe.service", "prep", "menu", "prop.interiors_v3.ice_cream.0020", 98, 46),
    ("Claudeville Cafe", "cafe.service", "prep", "menu", "prop.interiors_v3.ice_cream.0023", 101, 46),
    ("Claudeville Cafe", "cafe.service", "prep", "menu", "prop.interiors_v3.ice_cream.0026", 104, 46),
    # Cafe restroom is a compact rear-right cluster, never beside customer seating.
    ("Claudeville Cafe", "cafe.service", "wash", "restroom", "prop.interiors_v3.bathroom.0151", 106, 47),
    ("Claudeville Cafe", "cafe.service", "toilet", "restroom", "prop.interiors_v3.bathroom.0035", 107, 50),
    # Cafe front counter: five touching display cases, register and product displays.
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0001", 97, 51),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0002", 99, 51),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0003", 101, 51),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0004", 103, 51),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.interiors_v3.ice_cream.0102", 105, 51),
    ("Claudeville Cafe", "cafe.service", "service-counter", "service line", "prop.office.cash_register", 104, 49),
    # Cafe dining: two complete table-and-chair groups with a central circulation lane.
    ("Claudeville Cafe", "cafe.dining", "dining-table", "west table", "prop.office.table_light", 97, 55),
    ("Claudeville Cafe", "cafe.dining", "dining-table", "west table", "prop.interiors_v3.ice_cream.0080", 96, 54),
    ("Claudeville Cafe", "cafe.dining", "dining-table", "west table", "prop.interiors_v3.ice_cream.0082", 98, 56),
    ("Claudeville Cafe", "cafe.dining", "dining-table", "east table", "prop.office.table_light", 102, 55),
    ("Claudeville Cafe", "cafe.dining", "dining-table", "east table", "prop.interiors_v3.ice_cream.0084", 101, 54),
    ("Claudeville Cafe", "cafe.dining", "dining-table", "east table", "prop.interiors_v3.ice_cream.0086", 103, 56),
    # Cafe terrace: exactly two contained sets; the south approach remains clear.
    ("Claudeville Cafe", "cafe.terrace", "terrace-table", "west terrace", "prop.office.table_light", 95, 59),
    ("Claudeville Cafe", "cafe.terrace", "terrace-table", "west terrace", "prop.interiors_v3.ice_cream.0090", 94, 58),
    ("Claudeville Cafe", "cafe.terrace", "terrace-table", "west terrace", "prop.interiors_v3.ice_cream.0092", 96, 60),
    ("Claudeville Cafe", "cafe.terrace", "terrace-table", "east terrace", "prop.office.table_light", 105, 59),
    ("Claudeville Cafe", "cafe.terrace", "terrace-table", "east terrace", "prop.interiors_v3.ice_cream.0094", 104, 58),
    ("Claudeville Cafe", "cafe.terrace", "terrace-table", "east terrace", "prop.interiors_v3.ice_cream.0096", 106, 60),
    ("Claudeville Cafe", "cafe.terrace", "entrance", "south threshold", "prop.facade.door_open", 100, 57),
    ("Claudeville Cafe", "cafe.terrace", "planter", "terrace boundary", "prop.landscape.flower_bush_01", 93, 58),
    ("Claudeville Cafe", "cafe.terrace", "planter", "terrace boundary", "prop.landscape.flower_bush_03", 107, 58),
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
        for left, top, right, bottom in TARGET_BOUNDS.values():
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


def _refine_structure(layers: dict[str, dict]) -> None:
    ground = layers["Interior Ground"]["data"]
    wall = layers["Wall"]["data"]

    # Give the cafe a hygienic service floor while preserving its warm dining floor.
    for y in range(43, 51):
        for x in range(94, 109):
            index = y * 176 + x
            if ground[index]:
                ground[index] = 55219

    # Extend Home 5 by one collision-aligned bay for a real bathroom.
    for y in range(82, 87):
        for x in (64, 65):
            ground[y * 176 + x] = 55413 if (x + y) % 2 else 55416
        wall[y * 176 + 64] = 0
        wall[y * 176 + 66] = 38067
    for x, y in ((62, 82), (62, 83), (60, 84), (60, 85), (60, 86)):
        wall[y * 176 + x] = 0
    for y, gid in ((82, 55647), (83, 55699), (85, 55600), (86, 55600)):
        wall[y * 176 + 63] = gid
    wall[84 * 176 + 63] = 0  # Bathroom doorway.
    for x, gid in ((64, 55755), (65, 55755), (66, 56298)):
        wall[87 * 176 + x] = gid


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
    layers = _clear_target_art(tmj)
    created = _add_props(tmj, layers, _collection_firstgid(tmj, path))
    _refine_structure(layers)
    _refine_home5_semantics(tmj, created)
    _relink(tmj, created)
    tmj["properties"] = [
        item for item in tmj["properties"] if item.get("name") != "vertical_slice_revision"
    ]
    tmj["properties"].append(_property("vertical_slice_revision", SLICE_REVISION))
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(tmj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {"created_props": len(created), "removed_targets": sorted(TARGETS)}


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
