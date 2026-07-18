"""Author the final reference-matched Claudeville native-16 town map.

The coordinates are a hand-authored trace of the approved town composition,
using curated Modern Pixels tiles and props rather than procedural room
templates or a flat generated background.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

try:
    from tools.mapgen import author_claudeville_districts as district_authoring
    from tools.mapgen import claudeville_district_semantics as district_semantics
    from tools.mapgen import claudeville_north_placements as north_placements
    from tools.mapgen import claudeville_reference_architecture as architecture
    from tools.mapgen import claudeville_reference_bank as reference_bank
    from tools.mapgen import claudeville_reference_dense_civic as dense_civic
    from tools.mapgen import claudeville_reference_facades as reference_facades
    from tools.mapgen import claudeville_reference_home1 as reference_home
    from tools.mapgen import claudeville_reference_layout as reference_layout
    from tools.mapgen import claudeville_reference_middle as reference_middle
    from tools.mapgen import claudeville_reference_public_realm as public_realm
    from tools.mapgen import claudeville_reference_semantics as reference_semantics
    from tools.mapgen import claudeville_reference_shared_civic as shared_civic
    from tools.mapgen import claudeville_reference_stamps as reference_stamps
    from tools.mapgen import claudeville_reference_university as reference_university
    from tools.mapgen import claudeville_tiled_authoring as authoring
except ModuleNotFoundError:  # Direct script execution.
    import author_claudeville_districts as district_authoring
    import claudeville_district_semantics as district_semantics
    import claudeville_north_placements as north_placements
    import claudeville_reference_architecture as architecture
    import claudeville_reference_bank as reference_bank
    import claudeville_reference_dense_civic as dense_civic
    import claudeville_reference_facades as reference_facades
    import claudeville_reference_home1 as reference_home
    import claudeville_reference_layout as reference_layout
    import claudeville_reference_middle as reference_middle
    import claudeville_reference_public_realm as public_realm
    import claudeville_reference_semantics as reference_semantics
    import claudeville_reference_shared_civic as shared_civic
    import claudeville_reference_stamps as reference_stamps
    import claudeville_reference_university as reference_university
    import claudeville_tiled_authoring as authoring


REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_MAP = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/"
    / "claudeville_modern_interiors_v3.tmj"
)
OUTPUT_MAP = BASE_MAP.with_name("claudeville_target_v45.tmj")
STAMPS_ROOT = BASE_MAP.parent / "stamps"
WIDTH, HEIGHT = 176, 96
TARGETS = frozenset({"Bank", "Home 1", "University", "Agent Academy", "Market"})
REPLACED_PROP_SECTORS = frozenset(reference_layout.BUILDINGS) | frozenset(
    {"Central Plaza"}
)
BUILDING_PARCELS = tuple(
    record["parcel"] for record in reference_layout.BUILDINGS.values()
)
VISUAL_RESET_RECTS = ((0, 0, WIDTH, HEIGHT),)
V3_TILE_SOURCES = (
    "room.borders",
    "room.floors",
    "room.walls",
    "room.arched_entryways",
    "theme.generic",
    "theme.kitchen",
)

CIVIC_ROLE_SCALES = {
    "event-table": 1.35,
    "event-seat": 1.15,
    "dining-table": 1.25,
    "dining-chair": 1.1,
    "decor-reading-table": 1.35,
    "decor-reading-chair": 1.15,
    "postal-counter": 1.15,
    "decor-sorting-table": 1.3,
    "decor-sorting-seat": 1.15,
    "council-table": 1.25,
    "council-chair": 1.1,
}
SECTOR_PROP_SCALES = {
    "Bank": 1.1,
    "Home 1": 1.15,
    "University": 1.12,
    "Agent Academy": 1.08,
    "Market": 1.08,
    "Workshop": 1.15,
    "Claudeville Cafe": 1.12,
    "Library": 1.2,
    "Post Office": 1.18,
    "Town Hall": 1.18,
    **{f"Home {number}": 1.15 for number in range(2, 11)},
}
PLACEMENTS = (
    *reference_bank.PLACEMENTS,
    *reference_home.PLACEMENTS,
    *reference_university.PLACEMENTS,
    *(item for item in north_placements.PLACEMENTS if item[0] == "Agent Academy"),
    *north_placements.MARKET_PLACEMENTS,
    *reference_middle.PLACEMENTS,
    *dense_civic.PLACEMENTS,
    *shared_civic.PLACEMENTS,
    *reference_stamps.HOME_PLACEMENTS,
    *public_realm.PLACEMENTS,
)


class ReferenceSliceError(ValueError):
    """Raised when the reference proof cannot be authored safely."""


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReferenceSliceError(f"JSON root must be an object: {path}")
    return value


def _property(name: str, value: object) -> dict:
    kind = (
        "bool" if isinstance(value, bool)
        else "int" if isinstance(value, int)
        else "float" if isinstance(value, float)
        else "string"
    )
    return {"name": name, "type": kind, "value": value}


def _set_property(item: dict, name: str, value: object) -> None:
    properties = [
        prop for prop in item.get("properties", []) if prop.get("name") != name
    ]
    properties.append(_property(name, value))
    item["properties"] = sorted(properties, key=lambda prop: prop["name"])


def _align_plaza_interactions(tmj: dict) -> None:
    """Move the fountain semantic onto the exact-reference blocked footprint."""
    group = next(layer for layer in tmj["layers"] if layer["name"] == "Authoring")
    interactions = next(
        layer for layer in group["layers"] if layer["name"] == "Interactions"
    )
    for item in interactions["objects"]:
        values = authoring.properties(item.get("properties"))
        if values.get("semantic_id") != "plaza.fountain-001.shape-001":
            continue
        item.update({"x": 58 * 32, "y": 28 * 32, "width": 32, "height": 32})
        _set_property(item, "stance_x", 56)
        _set_property(item, "stance_y", 28)
        return
    raise ReferenceSliceError("Central Plaza fountain interaction is missing")


def _clear_rect(data: list[int], rect: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = rect
    for y in range(top, bottom):
        start = y * WIDTH + left
        data[start:start + right - left] = [0] * (right - left)


def _fill_rect(data: list[int], rect: tuple[int, int, int, int], gid: int) -> None:
    left, top, right, bottom = rect
    for y in range(top, bottom):
        start = y * WIDTH + left
        data[start:start + right - left] = [gid] * (right - left)


def _catalogs() -> tuple[dict[str, dict], dict[str, dict]]:
    return (
        district_authoring._catalog(district_authoring.V2_ROOT),
        district_authoring._catalog(district_authoring.V3_ROOT),
    )


def _add_props(tmj: dict, layers: dict[str, dict], firstgid: int) -> list[dict]:
    v2, v3 = _catalogs()
    next_id = max(tmj.get("nextobjectid", 1), 1)
    created = []
    for index, placement in enumerate(PLACEMENTS, 1):
        sector, zone, role, cluster, key, visual_x, visual_y = placement
        record = v2.get(key) or v3.get(key)
        if record is None:
            raise ReferenceSliceError(f"unknown proof asset: {key}")
        width, height = record["native_size"]
        display_scale = record.get("display_scale", 1)
        if key == public_realm.FOUNTAIN:
            display_scale = 1.75
        elif sector == "Central Plaza" and role == "plaza-tree":
            display_scale = 1.25
        else:
            display_scale = max(
                display_scale,
                CIVIC_ROLE_SCALES.get(role, 1),
                SECTOR_PROP_SCALES.get(sector, 1),
            )
        values = {
            "anchor_x": record["anchor"][0],
            "anchor_y": record["anchor"][1],
            "asset_key": key,
            "display_scale": display_scale,
            "purpose_cluster": cluster,
            "sector": sector,
            "semantic_type": role,
            "zone": zone,
        }
        item = {
            "id": next_id,
            "name": f"reference-{index:03d}-{role}",
            "type": "",
            "x": visual_x * 16,
            "y": visual_y * 16,
            "width": width,
            "height": height,
            "rotation": 0,
            "visible": True,
            "properties": [
                _property(name, values[name]) for name in sorted(values)
            ],
        }
        if key in v3:
            item["gid"] = firstgid + v3[key]["tiled_tile_id"]
        layers["Depth Props"]["objects"].append(item)
        created.append(item)
        next_id += 1
    tmj["nextobjectid"] = next_id
    return created


def _add_design_stamps(tmj: dict, layers: dict[str, dict]) -> list[dict]:
    catalog = _read(STAMPS_ROOT / "catalog.json")
    records = {
        item.get("asset_key"): item for item in catalog.get("records", [])
        if isinstance(item, dict) and isinstance(item.get("asset_key"), str)
    }
    if catalog.get("schema_version") != 1:
        raise ReferenceSliceError("design stamp catalog is malformed")
    next_id = max(tmj.get("nextobjectid", 1), 1)
    created = []
    for sector, zone, key, visual_x, visual_y in reference_stamps.PLACEMENTS:
        record = records.get(key)
        if record is None or not all(
            isinstance(value, int) and value > 0
            for value in record.get("native_size", [])
        ):
            raise ReferenceSliceError(f"design stamp is missing: {key}")
        width, height = record["native_size"]
        is_frontage = key.startswith("prop.design.frontage.")
        values = {
            "anchor_x": 0, "anchor_y": 0, "asset_key": key,
            "depth_offset": 0 if is_frontage else -1000, "display_scale": 1,
            "purpose_cluster": (
                "licensed native facade" if is_frontage
                else "licensed room composition"
            ),
            "sector": sector,
            "semantic_type": (
                "design-facade" if is_frontage else "decor-sprite-composition"
            ),
            "zone": zone,
        }
        if is_frontage:
            values["foot_y"] = visual_y * 16 + height
        item = {
            "id": next_id,
            "name": (
                f"design-{sector.lower().replace(' ', '-')}-"
                f"{key.rsplit('.', 1)[-1].replace('_', '-')}"
            ),
            "type": "", "x": visual_x * 16, "y": visual_y * 16,
            "width": width, "height": height, "rotation": 0, "visible": True,
            "properties": [_property(name, values[name]) for name in sorted(values)],
        }
        layers["Depth Props"]["objects"].append(item)
        created.append(item)
        next_id += 1
    tmj["nextobjectid"] = next_id
    return created


def author_reference_slice(
    base_path: Path = BASE_MAP, output_path: Path = OUTPUT_MAP,
) -> dict[str, int]:
    """Write a new, non-promoted v18 proof source from the immutable v16 map."""
    base = Path(base_path).expanduser().resolve(strict=True)
    output = Path(output_path).expanduser().resolve()
    if output == base:
        raise ReferenceSliceError("reference proof must not overwrite its v16 base")
    tmj = _read(base)
    if not authoring.is_tiled_first(tmj):
        raise ReferenceSliceError("reference proof requires the v3 Tiled-first source")
    layers = {layer["name"]: layer for layer in tmj["layers"] if layer["name"] != "Authoring"}

    bottom = layers["Bottom Ground"]["data"]
    exterior = layers["Exterior Ground"]["data"]
    _clear_rect(exterior, (0, 0, WIDTH, HEIGHT))
    for name in ("Exterior Decoration L1", "Exterior Decoration L2"):
        _clear_rect(layers[name]["data"], (0, 0, WIDTH, HEIGHT))

    tile_layer_names = (
        "Exterior Ground", "Exterior Decoration L1", "Exterior Decoration L2",
        "Interior Ground", "Wall", "Interior Furniture L1", "Interior Furniture L2",
        "Foreground L1", "Foreground L2",
    )
    for name in tile_layer_names:
        data = layers[name]["data"]
        for rect in VISUAL_RESET_RECTS:
            _clear_rect(data, rect)

    module = SimpleNamespace(V3_TILE_SOURCES=V3_TILE_SOURCES)
    sources = district_authoring._ensure_v3_tile_sources(tmj, output, module)
    exterior_gids = district_authoring._source_tile_gids(
        tmj, output,
        {
            "exteriors_city", "exteriors_generic", "exteriors_modular",
            "exteriors_office", "exteriors_terrain",
        },
    )

    def resolve_public_key(asset_key: str) -> int:
        prefix, source_id, source_x, source_y = asset_key.split(".")
        if prefix != "tile":
            raise ReferenceSliceError(f"public tile key is malformed: {asset_key}")
        return exterior_gids[(source_id, int(source_x) // 16, int(source_y) // 16)]

    public_realm.paint_public_realm(bottom, exterior, resolve_public_key)

    def resolve(tile: tuple[str, int, int]) -> int:
        return district_semantics._resolve_gid(tile, sources)

    floor = layers["Interior Ground"]["data"]
    walls = layers["Wall"]["data"]
    # The target uses warm timber cutaways with a dark outline.  This is the
    # complete paid-Interiors timber family in the middle wall palette; the
    # previous beige family made each building look like an office partition.
    wall_row = 16
    wall_col = 11
    dark = {
        "top_left": resolve(("room.walls", wall_row, wall_col)),
        "top_middle": resolve(("room.walls", wall_row, wall_col + 1)),
        "top_right": resolve(("room.walls", wall_row, wall_col + 2)),
        "top_face_left": resolve(("room.walls", wall_row + 1, wall_col)),
        "top_face_middle": resolve(("room.walls", wall_row + 1, wall_col + 1)),
        "top_face_right": resolve(("room.walls", wall_row + 1, wall_col + 2)),
        "side_left": resolve(("room.walls", wall_row, wall_col + 4)),
        "partition_left": resolve(("room.walls", wall_row, wall_col + 4)),
        "partition_right": resolve(("room.walls", wall_row, wall_col + 6)),
        "side_right": resolve(("room.walls", wall_row, wall_col + 6)),
        "bottom_left": resolve(("room.walls", wall_row, wall_col + 7)),
        "bottom_middle": resolve(("room.walls", wall_row, wall_col + 8)),
        "bottom_right": resolve(("room.walls", wall_row, wall_col + 9)),
    }
    floor_tiles = {
        "Bank": resolve(("room.floors", 25, 12)),
        "Home 1": resolve(("room.floors", 12, 5)),
        "University": resolve(("room.floors", 27, 12)),
        "Agent Academy": resolve(("room.floors", 25, 12)),
        "Market": resolve(("room.floors", 12, 5)),
        "Workshop": resolve(("room.floors", 16, 13)),
        "Community Center": resolve(("room.floors", 36, 0)),
        "Claudeville Cafe": resolve(("room.floors", 12, 5)),
        "Library": resolve(("room.floors", 27, 12)),
        "Post Office": resolve(("room.floors", 25, 12)),
        "Home 2": resolve(("room.floors", 10, 1)),
        "Home 3": resolve(("room.floors", 12, 1)),
        "Home 4": resolve(("room.floors", 14, 1)),
        "Home 5": resolve(("room.floors", 22, 1)),
        "Home 6": resolve(("room.floors", 24, 1)),
        "Town Hall": resolve(("room.floors", 27, 12)),
        "Home 7": resolve(("room.floors", 10, 5)),
        "Home 8": resolve(("room.floors", 22, 5)),
        "Home 9": resolve(("room.floors", 24, 5)),
        "Home 10": resolve(("room.floors", 28, 5)),
    }
    if set(floor_tiles) != set(reference_layout.BUILDINGS):
        raise ReferenceSliceError("every traced building requires an explicit floor")

    def compound_doors(sector: str, record: dict) -> set[int]:
        group = record.get("shared_compound")
        members = (
            [candidate for candidate in reference_layout.BUILDINGS.values()
             if candidate.get("shared_compound") == group]
            if group else [record]
        )
        return {x for candidate in members
                for x in range(candidate["entry"][0], candidate["entry"][2])}

    for sector, record in reference_layout.BUILDINGS.items():
        if sector == "University" or not record.get("paint_shell", True):
            continue
        architecture.paint_shell(
            floor,
            walls,
            record["room"],
            compound_doors(sector, record),
            floor_tiles[sector],
            dark,
            record.get("door_side", "bottom"),
        )
    architecture.paint_partitions(walls, reference_home.PARTITIONS, dark)
    architecture.paint_university(floor, walls, floor_tiles["University"], dark)
    district_authoring._apply_tile_stamps(tmj, layers, reference_middle, output)
    architecture.paint_slim_partitions(
        walls,
        (
            ("middle-social", "vertical", 78, 47, 69, {61, 62, 63}),
            ("workshop-service", "horizontal", 63, 28, 50, {38, 39, 40, 41}),
        ),
        dark,
    )
    for doorway in ((40, 43), (44, 43), (77, 43)):
        architecture.clear_logical_door(walls, *doorway)
    furniture = layers["Interior Furniture L1"]["data"]
    architecture.paint_bank_assemblies(furniture, resolve)

    lower = layers["Foreground L1"]["data"]
    for sector, record in reference_layout.BUILDINGS.items():
        if sector == "University" or not record.get("paint_shell", True):
            continue
        architecture.paint_shell_border(
            lower,
            resolve,
            record["room"],
            compound_doors(sector, record),
            record.get("door_side", "bottom"),
        )
    architecture.paint_university_border(lower, resolve)
    reference_facades.paint_all(lower, exterior_gids)

    depth = layers["Depth Props"]
    depth["objects"] = [
        item for item in depth["objects"]
        if (
            authoring.properties(item.get("properties")).get("sector")
            not in REPLACED_PROP_SECTORS
            and not str(
                authoring.properties(item.get("properties")).get("asset_key", "")
            ).startswith(("prop.landscape.", "prop.garden.bench", "prop.street.lamp"))
            and authoring.properties(item.get("properties")).get("asset_key")
            != public_realm.FOUNTAIN
        )
    ]
    firstgid = district_authoring._collection_firstgid(tmj, output)
    created = _add_props(tmj, layers, firstgid)
    created.extend(_add_design_stamps(tmj, layers))
    retained = reference_semantics.apply_reference_semantic_embeddings(tmj)
    depth["objects"] = [
        item for item in depth["objects"]
        if authoring.properties(item.get("properties")).get("purpose_cluster")
        != "semantic bridge"
    ]
    tmj["properties"] = [
        item for item in tmj.get("properties", [])
        if item.get("name") not in {"reference_trace_revision", "north_district_revision"}
    ]
    tmj["properties"].append(
        _property("north_district_revision", north_placements.REVISION)
    )
    tmj["properties"].append(_property("reference_trace_revision", 2))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(json.dumps(tmj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return {"props_added": len(created), "relinked_interactions": len(retained)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE_MAP)
    parser.add_argument("--output", type=Path, default=OUTPUT_MAP)
    args = parser.parse_args(argv)
    try:
        result = author_reference_slice(args.base, args.output)
    except (OSError, json.JSONDecodeError, ReferenceSliceError, ValueError) as exc:
        parser.error(str(exc))
    print(
        "Authored reference proof with "
        f"{result['props_added']} traced props and "
        f"{result['relinked_interactions']} relinked interactions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
