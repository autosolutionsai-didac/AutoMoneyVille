"""Apply the deterministic Claudeville south-district v2 remap."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

SPEC_PATH = Path(__file__).resolve().parent / "town_spec.json"
COLLISION_PATH = Path(__file__).resolve().parent / "town_spec.collisions.json"
BASE_ENVIRONMENT_PATH = (
    Path(__file__).resolve().parents[2]
    / "environment/frontend_server/storage/base/claudeville_v2/environment/0.json"
)

SECTORS = {
    "Home 2": [2, 35, 8, 45], "Home 3": [10, 35, 16, 45],
    "Home 4": [18, 35, 24, 45], "Home 5": [26, 35, 32, 45],
    "Home 6": [34, 35, 41, 45], "Town Hall": [43, 34, 53, 45],
    "Home 7": [55, 35, 61, 45], "Home 8": [63, 35, 69, 45],
    "Home 9": [71, 35, 78, 45], "Home 10": [80, 35, 86, 45],
}

REPLACED = {"Home 6", "Town Hall", "Home 7", "Home 8", "Home 9", "Home 10"}

ARENAS = (
    {"sector": "Home 6", "name": "bedroom", "rect": [35, 36, 38, 44]},
    {"sector": "Home 6", "name": "bathroom", "rect": [39, 41, 40, 44]},
    {"sector": "Home 6", "name": "living room", "rect": [39, 36, 40, 39]},
    {"sector": "Town Hall", "name": "main", "rect": [44, 37, 52, 40]},
    {"sector": "Town Hall", "name": "room", "rect": [44, 42, 52, 44]},
    {"sector": "Home 7", "name": "bedroom", "rect": [56, 36, 60, 44]},
    {"sector": "Home 8", "name": "bedroom", "rect": [64, 36, 68, 44]},
    {"sector": "Home 9", "name": "bedroom", "rect": [74, 36, 77, 40]},
    {"sector": "Home 9", "name": "bathroom", "rect": [72, 41, 73, 44]},
    {"sector": "Home 10", "name": "bedroom", "rect": [81, 36, 85, 44]},
)

OBJECTS = (
    {"sector": "Home 6", "arena": "bedroom", "type": "bed", "tiles": [[35, 36]]},
    {"sector": "Home 6", "arena": "bedroom", "type": "desk", "tiles": [[35, 40]]},
    {"sector": "Home 6", "arena": "bathroom", "type": "toilet", "tiles": [[40, 43]]},
    {"sector": "Home 6", "arena": "bathroom", "type": "shower", "tiles": [[40, 41]]},
    {"sector": "Home 6", "arena": "living room", "type": "sofa", "tiles": [[39, 38]]},
    {"sector": "Town Hall", "arena": "main", "type": "counter", "tiles": [[48, 37]]},
    {"sector": "Town Hall", "arena": "room", "type": "table", "tiles": [[48, 43]]},
    {"sector": "Home 7", "arena": "bedroom", "type": "bed", "tiles": [[56, 36]]},
    {"sector": "Home 7", "arena": "bedroom", "type": "desk", "tiles": [[56, 42]]},
    {"sector": "Home 7", "arena": "bedroom", "type": "toilet", "tiles": [[60, 43]]},
    {"sector": "Home 7", "arena": "bedroom", "type": "shower", "tiles": [[60, 36]]},
    {"sector": "Home 8", "arena": "bedroom", "type": "bed", "tiles": [[64, 36]]},
    {"sector": "Home 8", "arena": "bedroom", "type": "desk", "tiles": [[64, 42]]},
    {"sector": "Home 8", "arena": "bedroom", "type": "toilet", "tiles": [[68, 43]]},
    {"sector": "Home 8", "arena": "bedroom", "type": "shower", "tiles": [[68, 36]]},
    {"sector": "Home 9", "arena": "bedroom", "type": "bed", "tiles": [[74, 36]]},
    {"sector": "Home 9", "arena": "bedroom", "type": "desk", "tiles": [[76, 39]]},
    {"sector": "Home 9", "arena": "bathroom", "type": "toilet", "tiles": [[73, 43]]},
    {"sector": "Home 9", "arena": "bathroom", "type": "shower", "tiles": [[72, 41]]},
    {"sector": "Home 10", "arena": "bedroom", "type": "bed", "tiles": [[81, 36]]},
    {"sector": "Home 10", "arena": "bedroom", "type": "desk", "tiles": [[81, 43]]},
    {"sector": "Home 10", "arena": "bedroom", "type": "toilet", "tiles": [[85, 43]]},
    {"sector": "Home 10", "arena": "bedroom", "type": "shower", "tiles": [[85, 36]]},
)

SPAWNS = {
    "Home 6": ("bedroom", [38, 43]), "Town Hall": ("main", [48, 39]),
    "Home 7": ("bedroom", [58, 42]), "Home 8": ("bedroom", [66, 42]),
    "Home 9": ("bedroom", [75, 39]), "Home 10": ("bedroom", [83, 42]),
}

BASE_SPAWNS = {"Amara Cole": (48, 33), "Sofia Lane": (17, 40)}

OLD_WALKABLE = {
    (44, 16),
    (43, 36), (45, 42), (44, 42), (40, 38), (62, 36), (64, 43),
    (64, 36), (72, 36), (74, 43), (74, 36), (84, 34), (81, 38),
    (81, 35), (79, 41), (82, 42), (82, 41),
}
NEW_WALKABLE = (
    (35, 36), (35, 40), (40, 43), (40, 41), (39, 38),
    (56, 36), (56, 42), (60, 43), (60, 36),
    (64, 36), (64, 42), (68, 43), (68, 36),
    (74, 36), (76, 39), (73, 43), (72, 41),
    (81, 36), (81, 43), (85, 43), (85, 36),
)


def remap_spec(value: dict) -> dict:
    spec = deepcopy(value)
    sectors = {entry.get("name"): entry for entry in spec.get("sectors", [])}
    if not set(SECTORS).issubset(sectors):
        raise ValueError("town spec is missing south district sectors")
    for name, rect in SECTORS.items():
        sectors[name]["rect"] = list(rect)
    spec["arenas"] = [entry for entry in spec["arenas"] if entry["sector"] not in REPLACED]
    spec["arenas"].extend(deepcopy(ARENAS))
    spec["objects"] = [entry for entry in spec["objects"] if entry["sector"] not in REPLACED]
    spec["objects"].extend(deepcopy(OBJECTS))
    for spawn in spec["spawns"]:
        replacement = SPAWNS.get(spawn["sector"])
        if replacement:
            spawn["arena"], spawn["tile"] = replacement[0], list(replacement[1])
    return spec


def write_remap(
    path: Path,
    collision_path: Path = COLLISION_PATH,
    base_environment_path: Path = BASE_ENVIRONMENT_PATH,
) -> None:
    resolved = path.expanduser().resolve(strict=True)
    value = json.loads(resolved.read_text(encoding="utf-8"))
    transformed = remap_spec(value)
    temporary = resolved.with_name(f".{resolved.name}.tmp")
    temporary.write_text(
        json.dumps(transformed, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(resolved)
    collision = collision_path.expanduser().resolve(strict=True)
    overrides = json.loads(collision.read_text(encoding="utf-8"))
    retained = [point for point in overrides.get("walkable", []) if tuple(point) not in OLD_WALKABLE]
    seen = {tuple(point) for point in retained}
    retained.extend([list(point) for point in NEW_WALKABLE if point not in seen])
    overrides["walkable"] = retained
    collision_temporary = collision.with_name(f".{collision.name}.tmp")
    collision_temporary.write_text(
        json.dumps(overrides, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    collision_temporary.replace(collision)
    base_environment = base_environment_path.expanduser().resolve(strict=True)
    residents = json.loads(base_environment.read_text(encoding="utf-8"))
    for resident_name, (x, y) in BASE_SPAWNS.items():
        resident = residents.get(resident_name)
        if not isinstance(resident, dict):
            raise ValueError(f"claudeville_v2 base is missing {resident_name}")
        resident.update({"maze": "claudeville", "x": x, "y": y})
    base_temporary = base_environment.with_name(f".{base_environment.name}.tmp")
    base_temporary.write_text(
        json.dumps(residents, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    base_temporary.replace(base_environment)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", nargs="?", type=Path, default=SPEC_PATH)
    parser.add_argument("--collision-overrides", type=Path, default=COLLISION_PATH)
    parser.add_argument("--base-environment", type=Path, default=BASE_ENVIRONMENT_PATH)
    args = parser.parse_args(argv)
    try:
        write_remap(args.spec, args.collision_overrides, args.base_environment)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f"Remapped south district in {args.spec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
