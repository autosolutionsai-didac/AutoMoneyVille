"""One-time, read-only migration from compiled v15 semantics to Tiled objects.

This helper never invokes the destructive interior composer. Normal candidate builds do
not call it; use it once with an explicit new output path, then edit the TMJ in Tiled.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path

try:
    from tools.mapgen import claudeville_tiled_authoring as authoring
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_tiled_authoring as authoring  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parents[2]
WORLD_ROOT = REPO_ROOT / "environment/frontend_server/static_dirs/assets/claudeville"
SOURCE_MAP = WORLD_ROOT / "visuals/claudeville_full_town_v2.tmj"
SPEC_PATH = Path(__file__).resolve().parent / "town_spec.json"
COLLISION_PATH = WORLD_ROOT / "matrix/maze/collision_maze.csv"
ART_PRIORITY = (
    "Depth Props", "Overhead Props", "Interior Furniture L2",
    "Interior Furniture L1", "Foreground L2", "Foreground L1", "Wall",
    "Exterior Decoration L2", "Exterior Decoration L1",
)
Point = tuple[int, int]


class MigrationError(ValueError):
    """Raised when the legacy semantics cannot be seeded truthfully."""


def _properties(value: object) -> dict:
    return authoring.properties(value)


def _slug(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")
    if not text:
        raise MigrationError("semantic names must contain letters or numbers")
    return text


def _room_type(arena: str) -> str:
    suffix = arena.rsplit(".", 1)[-1].replace("_", "-")
    aliases = {
        "living-room": "living-room", "main-room": "main-room",
        "public-service": "public-service", "event-hall": "event-hall",
        "study-lab": "study-lab", "training-lab": "training-lab",
        "machine-bay": "machine-bay",
    }
    return aliases.get(suffix, _slug(suffix))


def _rects(entry: dict) -> list[list[int]]:
    values = entry.get("rects", [entry.get("rect")])
    if not isinstance(values, list) or not values:
        raise MigrationError(f"arena has no rectangles: {entry.get('name')}")
    result = []
    for value in values:
        if not isinstance(value, list) or len(value) != 4 or any(
            not isinstance(item, int) or isinstance(item, bool) for item in value
        ):
            raise MigrationError(f"arena has invalid rectangles: {entry.get('name')}")
        x0, y0, x1, y1 = value
        if not (0 <= x0 <= x1 < 88 and 0 <= y0 <= y1 < 48):
            raise MigrationError(f"arena rectangle is outside the grid: {entry.get('name')}")
        result.append(value)
    return result


def _collision(tokens: str, block_id: str) -> list[list[bool]]:
    values = [token.strip() for token in tokens.split(",")]
    if len(values) != 88 * 48 or any(value not in {"0", block_id} for value in values):
        raise MigrationError("legacy collision is not an exact 88x48 matrix")
    return [[values[y * 88 + x] == block_id for x in range(88)] for y in range(48)]


def _tile_art(layer: dict, point: Point) -> bool:
    data = layer.get("data")
    if not isinstance(data, list) or len(data) != 176 * 96:
        return False
    x, y = point
    return any(
        0 <= x + dx < 88 and 0 <= y + dy < 48
        and any(data[(2 * (y + dy) + sy) * 176 + 2 * (x + dx) + sx]
                for sy in (0, 1) for sx in (0, 1))
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
    )


def _art_link(layers: dict[str, dict], point: Point, sector: str, zone: str, kind: str) -> dict:
    for name in ART_PRIORITY:
        layer = layers.get(name, {})
        if layer.get("type") == "objectgroup":
            for obj in layer.get("objects", []):
                values = _properties(obj.get("properties")) if isinstance(obj, dict) else {}
                x, y = obj.get("x"), obj.get("y")
                if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                    continue
                foot = int(x // 32), int(y // 32)
                semantic_match = (
                    values.get("sector") == sector and values.get("zone") == zone
                    and _slug(values.get("semantic_type", "unknown")) == kind
                )
                if abs(foot[0] - point[0]) + abs(foot[1] - point[1]) <= 1 \
                        and (semantic_match or foot == point):
                    if isinstance(obj.get("id"), int):
                        return {"art_layer": name, "art_object_id": obj["id"]}
                    if isinstance(values.get("asset_key"), str):
                        return {"art_layer": name, "art_asset_key": values["asset_key"]}
        elif _tile_art(layer, point):
            return {"art_layer": name}
    raise MigrationError(f"{sector}:{zone}:{kind} at {point} has no visible art")


def _zone_cells(arenas: list[dict]) -> dict[str, set[Point]]:
    result = {}
    for arena in arenas:
        name = arena.get("name")
        if not isinstance(name, str) or name in result:
            raise MigrationError("arena names must be unique strings")
        result[name] = {
            (x, y) for x0, y0, x1, y1 in _rects(arena)
            for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
        }
    return result


def _stance(
    points: tuple[Point, ...], cells: set[Point], collision: list[list[bool]], occupied: set[Point],
    fallback: set[Point],
) -> Point:
    candidates = tuple(dict.fromkeys(
        candidate for x, y in points
        for candidate in ((x, y + 1), (x - 1, y), (x + 1, y), (x, y - 1))
        if candidate not in points
    ))
    for floor in (cells, fallback):
        for candidate in candidates:
            if candidate in floor and candidate not in occupied and not collision[candidate[1]][candidate[0]]:
                return candidate
    raise MigrationError(f"interaction at {points} has no clear cardinal stance")


def seed_from_legacy_semantics(source: dict, spec: dict, collision: list[list[bool]]) -> dict:
    """Return a deterministic candidate copy seeded from compiled purpose/home data."""
    if authoring.is_tiled_first(source) or any(
        item.get("name") == authoring.GROUP_NAME
        for item in source.get("layers", []) if isinstance(item, dict)
    ):
        raise MigrationError("source already contains Tiled-first authoring semantics")
    root_layers = source.get("layers")
    if not isinstance(root_layers, list) or [item.get("name") for item in root_layers] != list(authoring.RUNTIME_LAYERS):
        raise MigrationError("legacy source must retain the exact 13-layer runtime contract")
    layers = {item["name"]: item for item in root_layers}
    arenas = spec.get("arenas")
    if not isinstance(arenas, list) or not arenas:
        raise MigrationError("town spec has no compiled arenas")
    zone_cells = _zone_cells(arenas)
    arena_sectors = {arena["name"]: arena["sector"] for arena in arenas}
    sector_floor = {
        sector: set().union(*(zone_cells[name] for name in zone_cells if arena_sectors[name] == sector))
        for sector in set(arena_sectors.values())
    }
    max_object_id = max(
        (obj.get("id", 0) for layer in root_layers if layer.get("type") == "objectgroup"
         for obj in layer.get("objects", []) if isinstance(obj, dict)), default=0,
    )
    object_id = max_object_id + 1
    zones = []
    for arena in sorted(arenas, key=lambda item: (item["sector"], item["name"])):
        for part, (x0, y0, x1, y1) in enumerate(_rects(arena), 1):
            semantic_id = f"{arena['name']}.shape-{part:03d}"
            zones.append(authoring.make_authoring_object(
                object_id, semantic_id, x0 * 32, y0 * 32,
                width=(x1 - x0 + 1) * 32, height=(y1 - y0 + 1) * 32,
                zone=arena["name"], sector=arena["sector"], room_type=_room_type(arena["name"]),
            ))
            object_id += 1
    all_object_cells = {
        tuple(point) for entry in spec.get("objects", []) if isinstance(entry, dict)
        for point in entry.get("tiles", []) if isinstance(point, list) and len(point) == 2
    }
    interactions = []
    ordinals = {}
    for entry in sorted(spec.get("objects", []), key=lambda item: (
        item.get("sector", ""), item.get("arena", ""), item.get("type", ""), item.get("tiles", [])
    )):
        sector, zone, kind = entry.get("sector"), entry.get("arena"), _slug(entry.get("type"))
        if zone not in zone_cells or not isinstance(sector, str):
            raise MigrationError(f"object references an unknown arena: {entry}")
        points = tuple(tuple(value) for value in entry.get("tiles", []))
        if not points or not set(points) <= zone_cells[zone]:
            raise MigrationError(f"object falls outside arena {zone}: {points}")
        key = zone, kind
        ordinals[key] = ordinals.get(key, 0) + 1
        interaction_id = f"{zone}.{kind}-{ordinals[key]:03d}"
        stance = _stance(
            points, zone_cells[zone], collision, all_object_cells, sector_floor[sector]
        )
        states = {collision[y][x] for x, y in points}
        policy = "require-blocked" if states == {True} else \
            "nonblocking" if states == {False} else "preserve-collision"
        for part, point in enumerate(points, 1):
            semantic_id = f"{interaction_id}.shape-{part:03d}"
            interactions.append(authoring.make_authoring_object(
                object_id, semantic_id, point[0] * 32, point[1] * 32,
                width=32, height=32, sector=sector, zone=zone, interaction=interaction_id,
                interaction_type=kind,
                allowed_room_types=_room_type(zone), blocker_policy=policy,
                stance_x=stance[0], stance_y=stance[1],
                **_art_link(layers, point, sector, zone, kind),
            ))
            object_id += 1
    entrances = []
    for entry in sorted(spec.get("entrances", []), key=lambda item: item.get("sector", "")):
        sector, point = entry.get("sector"), entry.get("tile")
        if not isinstance(sector, str) or not isinstance(point, list) or len(point) != 2:
            raise MigrationError("town entrance is malformed")
        entrances.append(authoring.make_authoring_object(
            object_id, f"{_slug(sector)}.entrance", point[0] * 32, point[1] * 32,
            point=True, sector=sector,
        ))
        object_id += 1
    spawns = []
    for entry in sorted(spec.get("spawns", []), key=lambda item: item.get("sector", "")):
        sector, zone, point = entry.get("sector"), entry.get("arena"), entry.get("tile")
        if not isinstance(sector, str) or zone not in zone_cells or not isinstance(point, list) or len(point) != 2:
            raise MigrationError("town spawn is malformed")
        spawns.append(authoring.make_authoring_object(
            object_id, f"{_slug(sector)}.spawn", point[0] * 32, point[1] * 32,
            point=True, sector=sector, zone=zone, spawn_name=entry.get("name", "sp"),
        ))
        object_id += 1
    result = deepcopy(source)
    properties = [item for item in result.get("properties", []) if item.get("name") != "authoring_profile"]
    properties.append({"name": "authoring_profile", "type": "string", "value": authoring.PROFILE})
    result["properties"] = properties
    group_id = max((item.get("id", 0) for item in root_layers if isinstance(item, dict)), default=0) + 1
    result["layers"].append(authoring.make_authoring_group(
        group_id, zones=zones, interactions=interactions, entrances=entrances, spawns=spawns,
    ))
    result["nextlayerid"] = group_id + len(authoring.AUTHORING_LAYERS) + 1
    result["nextobjectid"] = object_id
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_MAP)
    parser.add_argument("--spec", type=Path, default=SPEC_PATH)
    parser.add_argument("--collision", type=Path, default=COLLISION_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    source, spec = (json.loads(path.read_text(encoding="utf-8")) for path in (args.source, args.spec))
    collision = _collision(args.collision.read_text(encoding="utf-8"), str(spec.get("collision_block_id")))
    output = args.output.expanduser().resolve(strict=False)
    source_path, boundary = args.source.expanduser().resolve(strict=True), (WORLD_ROOT / "visuals").resolve()
    if output == source_path or boundary not in output.parents or output.exists():
        parser.error("one-time output must be a new TMJ inside Claudeville/visuals")
    payload = seed_from_legacy_semantics(source, spec, collision)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Seeded {output}; edit and review this candidate in Tiled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
