"""Compile target-photo Claudeville semantics from its placed sprite art."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

try:
    from tools.mapgen import claudeville_reference_collision as reference_collision
    from tools.mapgen import claudeville_tiled_authoring as authoring
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_reference_collision as reference_collision  # type: ignore[no-redef]
    import claudeville_tiled_authoring as authoring  # type: ignore[no-redef]


PIXEL_SIZE = 32
REPO_ROOT = Path(__file__).resolve().parents[2]
TOWN_SPEC_PATH = REPO_ROOT / "tools/mapgen/town_spec.json"
COLLISION_BLUEPRINT_PATH = REPO_ROOT / "tools/mapgen/town_spec.collisions.json"

EMBEDDED_SECTOR_RECTS = {
    "Bank": [13, 6, 25, 20], "Home 1": [33, 6, 45, 20],
    "University": [49, 2, 60, 20], "Agent Academy": [61, 2, 66, 20],
    "Market": [70, 5, 78, 20], "Post Office": [79, 5, 87, 20],
    "Workshop": [13, 22, 25, 39],
    "Community Center": [33, 22, 39, 39],
    "Claudeville Cafe": [40, 22, 45, 39],
    "Central Plaza": [47, 21, 68, 37], "Library": [71, 22, 84, 39],
    "Home 2": [13, 40, 19, 47],
    "Home 3": [20, 40, 25, 47], "Home 4": [33, 40, 37, 47],
    "Home 5": [38, 40, 41, 47], "Home 6": [42, 40, 45, 47],
    "Town Hall": [49, 40, 57, 47], "Home 7": [59, 40, 63, 47],
    "Home 8": [64, 40, 68, 47], "Home 9": [71, 40, 74, 47],
    "Home 10": [75, 40, 79, 47],
}

ROOMS = {
    "Bank": {"bank.archive": "archive", "bank.operations": "operations",
             "bank.teller": "teller", "bank.advisory": "advisory",
             "bank.waiting": "waiting", "bank.circulation": "circulation"},
    "University": {"university.lecture": "lecture",
                   "university.study_lab": "study-lab",
                   "university.cafeteria": "cafeteria"},
    "Agent Academy": {"academy.training_lab": "training-lab",
                      "academy.classroom": "classroom",
                      "academy.reception": "reception",
                      "academy.lounge": "lounge"},
    "Market": {"market.retail": "retail", "market.checkout": "checkout"},
    "Workshop": {"workshop.machine_bay": "machine-bay",
                 "workshop.intake": "intake",
                 "workshop.circulation": "circulation"},
    "Community Center": {"community.event_hall": "event-hall",
                         "community.lounge": "lounge",
                         "community.reception": "reception",
                         "community_center.circulation": "circulation"},
    "Claudeville Cafe": {"cafe.service": "service", "cafe.dining": "dining",
                         "cafe.restroom": "restroom", "cafe.terrace": "terrace"},
    "Central Plaza": {"plaza": "plaza"},
    "Library": {"library.stacks": "stacks", "library.reading": "reading",
                "library.circulation": "circulation"},
    "Post Office": {"post.service": "service", "post.sorting": "sorting",
                    "post.waiting": "waiting",
                    "post_office.circulation": "circulation"},
    "Town Hall": {"hall.public_service": "public-service",
                  "hall.administration": "administration",
                  "hall.council": "council",
                  "town_hall.circulation": "circulation"},
}
for number in range(1, 11):
    sector, prefix = f"Home {number}", f"home_{number}"
    if number in {2, 3, 4}:
        ROOMS[sector] = {f"{prefix}.main_room": "main-room",
                         f"{prefix}.bathroom": "bathroom"}
    else:
        ROOMS[sector] = {
            f"{prefix}.kitchen": "kitchen", f"{prefix}.living_room": "living-room",
            f"{prefix}.bedroom": "bedroom", f"{prefix}.bathroom": "bathroom",
        }
        if number == 1:
            ROOMS[sector][f"{prefix}.garden"] = "garden"

ENTRANCES = {
    "Bank": (19, 18), "Home 1": (39, 18), "University": (57, 18),
    "Agent Academy": (63, 18), "Market": (74, 18), "Workshop": (19, 36),
    "Community Center": (36, 36), "Claudeville Cafe": (43, 36),
    "Library": (74, 36), "Post Office": (83, 18), "Home 2": (16, 40),
    "Home 3": (23, 40), "Home 4": (35, 40), "Home 5": (39, 40),
    "Home 6": (43, 40), "Town Hall": (53, 40), "Home 7": (61, 40),
    "Home 8": (66, 40), "Home 9": (73, 40), "Home 10": (77, 40),
}

SPAWN_ZONES = {
    "Bank": "bank.circulation", "University": "university.cafeteria",
    "Agent Academy": "academy.reception", "Market": "market.retail",
    "Workshop": "workshop.circulation", "Community Center": "community.lounge",
    "Claudeville Cafe": "cafe.dining", "Central Plaza": "plaza",
    "Library": "library.circulation", "Post Office": "post_office.circulation",
    "Town Hall": "hall.public_service",
}
for number in range(1, 11):
    SPAWN_ZONES[f"Home {number}"] = (
        f"home_{number}.main_room" if number in {2, 3, 4}
        else f"home_{number}.living_room"
    )

SPECIAL_PREFERENCES = {
    "bank.archive": ("archive-cabinets",), "bank.operations": ("operations-desk",),
    "bank.teller": ("teller-counter",), "bank.advisory": ("advisory-desk",),
    "bank.waiting": ("waiting-seating",),
    "university.lecture": ("lecture-seating",),
    "university.study_lab": ("computer-station",),
    "university.cafeteria": ("service-counter", "dining-table"),
    "academy.training_lab": ("training-simulator",),
    "academy.classroom": ("classroom-seating",),
    "academy.reception": ("reception-desk",), "academy.lounge": ("lounge-seating",),
    "market.retail": ("stock-display",), "market.checkout": ("checkout-counter",),
    "workshop.machine_bay": ("work-machine", "workbench"),
    "workshop.intake": ("job-intake", "tool-storage"),
    "community.event_hall": ("event-table", "presentation-area"),
    "community.lounge": ("lounge-seating",),
    "community.reception": ("help-desk",), "cafe.service": ("service-counter",),
    "cafe.dining": ("dining-table",), "cafe.restroom": ("toilet-fixture", "toilet"),
    "cafe.terrace": ("terrace-table",), "library.stacks": ("bookshelf",),
    "library.reading": ("reading-table",), "library.circulation": ("circulation-desk",),
    "post.service": ("postal-counter",), "post.sorting": ("mail-sorting-table",),
    "post.waiting": ("waiting-seating",), "hall.public_service": ("counter-wing",),
    "hall.administration": ("admin-desk",), "hall.council": ("council-table",),
    "plaza": ("fountain", "bench", "notice-board"),
}

STANCE_OVERRIDES = {"home_1.bathroom": (44, 9)}
SPAWN_HINTS = {
    # Keep the Cafe spawn in the public dining floor, never in the screened
    # preparation pocket between the back wall and display counter.
    "Claudeville Cafe": (42, 31),
}


def _props(item: dict) -> dict:
    return authoring.properties(item.get("properties"))


def _layer(tmj: dict, name: str) -> dict:
    return next(layer for layer in tmj["layers"] if layer.get("name") == name)


def _cells(rect: list[int]) -> set[tuple[int, int]]:
    left, top, right, bottom = rect
    return {(x, y) for y in range(top, bottom + 1) for x in range(left, right + 1)}


def _foot(item: dict) -> tuple[int, int]:
    return int(item["x"] // PIXEL_SIZE), int(item["y"] // PIXEL_SIZE)


def _zone_partition(tmj: dict, blocked: set[tuple[int, int]]) -> dict[str, set[tuple[int, int]]]:
    depth = _layer(tmj, "Depth Props")["objects"]
    by_zone: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for item in depth:
        values = _props(item)
        sector, zone = values.get("sector"), values.get("zone")
        if sector in EMBEDDED_SECTOR_RECTS and zone in ROOMS[sector]:
            point = _foot(item)
            if point in _cells(EMBEDDED_SECTOR_RECTS[sector]):
                by_zone[zone].add(point)
    result: dict[str, set[tuple[int, int]]] = {}
    for sector, zone_rooms in ROOMS.items():
        owned = _cells(EMBEDDED_SECTOR_RECTS[sector])
        entrance = ENTRANCES.get(sector, tuple(map(round, _center(owned))))
        seeds = {}
        for index, zone in enumerate(zone_rooms):
            candidates = by_zone.get(zone)
            if candidates:
                seeds[zone] = candidates
            else:
                offset = (index % 3 - 1, index // 3)
                seeds[zone] = {_clamp((entrance[0] + offset[0], entrance[1] + offset[1]), owned)}
        representatives, reserved = {}, set()
        for zone in zone_rooms:
            center = _center(seeds[zone])
            choices = owned - reserved - blocked or owned - reserved
            representative = min(
                choices,
                key=lambda cell: (abs(cell[0] - center[0]) + abs(cell[1] - center[1]), cell),
            )
            representatives[zone] = representative
            reserved.add(representative)
        for point in owned:
            zone = min(
                seeds,
                key=lambda name: (min(abs(point[0] - x) + abs(point[1] - y)
                                      for x, y in seeds[name]), name),
            )
            result.setdefault(zone, set()).add(point)
        for zone, representative in representatives.items():
            for cells in result.values():
                cells.discard(representative)
            result.setdefault(zone, set()).add(representative)
    return result


def _center(cells: set[tuple[int, int]]) -> tuple[float, float]:
    return (sum(x for x, _ in cells) / len(cells), sum(y for _, y in cells) / len(cells))


def _clamp(point: tuple[int, int], cells: set[tuple[int, int]]) -> tuple[int, int]:
    return min(cells, key=lambda cell: (abs(cell[0] - point[0]) + abs(cell[1] - point[1]), cell))


def _runs(cells: set[tuple[int, int]]) -> list[tuple[int, int, int]]:
    result = []
    for y in sorted({point[1] for point in cells}):
        xs = sorted(x for x, row in cells if row == y)
        left = previous = xs[0]
        for x in xs[1:]:
            if x != previous + 1:
                result.append((left, y, previous))
                left = x
            previous = x
        result.append((left, y, previous))
    return result


def _preferred(zone: str) -> tuple[str, ...]:
    if zone in SPECIAL_PREFERENCES:
        return SPECIAL_PREFERENCES[zone]
    suffix = zone.rsplit(".", 1)[-1]
    return {
        "bathroom": ("washstand", "toilet-fixture"), "bedroom": ("bed",),
        "kitchen": ("cooking-area",), "living_room": ("resident-hobby", "side-table"),
        "main_room": ("resident-hobby", "bed"), "garden": ("garden-seat", "bench"),
    }.get(suffix, ())


def _interaction_candidates(tmj: dict, zone_cells: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for item in _layer(tmj, "Depth Props")["objects"]:
        values = _props(item)
        zone, point = values.get("zone"), _foot(item)
        if zone in zone_cells and point in zone_cells[zone]:
            result[zone].append(item)
    return result


def _force_preferred_cells(tmj: dict, zones: dict[str, set[tuple[int, int]]]) -> None:
    candidates: dict[str, list[dict]] = defaultdict(list)
    for item in _layer(tmj, "Depth Props")["objects"]:
        values, point = _props(item), _foot(item)
        zone, sector = values.get("zone"), values.get("sector")
        if (zone in zones and sector in EMBEDDED_SECTOR_RECTS
                and point in _cells(EMBEDDED_SECTOR_RECTS[sector])):
            candidates[zone].append(item)
    for sector, zone_rooms in ROOMS.items():
        for zone in zone_rooms:
            preferences = _preferred(zone)
            match = next(
                (item for kind in preferences for item in candidates.get(zone, [])
                 if _props(item).get("semantic_type") == kind),
                None,
            )
            if match is None:
                continue
            point = _foot(match)
            for other_zone in zone_rooms:
                zones[other_zone].discard(point)
            zones[zone].add(point)


def _choose_interactions(
    tmj: dict, zones: dict, blocked: set, solid_cells: set[tuple[int, int]],
) -> list[tuple]:
    candidates = _interaction_candidates(tmj, zones)
    result = []
    reserved_cells = {
        _foot(item)
        for zone, items in candidates.items()
        for item in items
        if _props(item).get("semantic_type") in _preferred(zone)
    }
    for sector, zone_rooms in ROOMS.items():
        owned = set().union(*(zones[zone] for zone in zone_rooms))
        for zone, room_type in zone_rooms.items():
            preferences = _preferred(zone)
            if not preferences:
                continue
            ordered = sorted(
                candidates.get(zone, []),
                key=lambda item: (
                    next((i for i, kind in enumerate(preferences)
                          if _props(item).get("semantic_type") == kind), 999),
                    item["id"],
                ),
            )
            requested = preferences if zone == "plaza" else (None,)
            for requested_kind in requested:
                for item in ordered:
                    kind, cell = str(_props(item).get("semantic_type")), _foot(item)
                    if kind not in preferences or (
                        requested_kind is not None and kind != requested_kind
                    ):
                        continue
                    stances = [point for point in ((cell[0], cell[1] + 1),
                               (cell[0] - 1, cell[1]), (cell[0] + 1, cell[1]),
                               (cell[0], cell[1] - 1)) if point in owned
                               and point not in blocked
                               and point not in reserved_cells
                               and point not in solid_cells]
                    override = STANCE_OVERRIDES.get(zone)
                    if (override in owned and override not in blocked
                            and override not in solid_cells
                            and abs(override[0] - cell[0]) + abs(override[1] - cell[1]) == 1):
                        stances.insert(0, override)
                    if stances:
                        stance = stances[0] if override == stances[0] else min(
                            stances, key=lambda point: (point not in zones[zone], point)
                        )
                        if stance not in zones[zone]:
                            for other_zone in zone_rooms:
                                zones[other_zone].discard(stance)
                            zones[zone].add(stance)
                        policy = (
                            "nonblocking"
                            if (
                                kind == "resident-hobby"
                                or not reference_collision._object_cells(item)
                            ) and cell not in blocked
                            else "require-blocked"
                        )
                        result.append((sector, zone, room_type, kind, item, cell, stance, policy))
                        if policy == "require-blocked":
                            blocked.update(reference_collision._object_cells(item))
                        break
    return result


def _next_id(tmj: dict) -> int:
    values = [0]
    for layer in tmj.get("layers", []):
        values.extend(item.get("id", 0) for item in layer.get("objects", []))
        for child in layer.get("layers", []):
            values.extend(item.get("id", 0) for item in child.get("objects", []))
    return max(values) + 1


def apply_reference_semantic_embeddings(tmj: dict, **_ignored) -> frozenset[int]:
    """Replace all legacy authoring objects with target-sprite-linked semantics."""
    group = _layer(tmj, authoring.GROUP_NAME)
    children = {layer["name"]: layer for layer in group["layers"]}
    if set(children) != set(authoring.AUTHORING_LAYERS):
        raise ValueError("reference map has an incomplete Authoring group")
    for child in children.values():
        child["objects"] = []
    blocked, next_id = reference_collision.base_blocked(tmj), _next_id(tmj)
    solid_cells = set(reference_collision._solid_prop_cells(tmj))
    zones = _zone_partition(tmj, blocked)
    _force_preferred_cells(tmj, zones)
    used: set[int] = set()

    def add(layer_name: str, semantic_id: str, x: int, y: int, **values) -> None:
        nonlocal next_id
        children[layer_name]["objects"].append(
            authoring.make_authoring_object(next_id, semantic_id, x, y, **values)
        )
        next_id += 1

    interactions = _choose_interactions(tmj, zones, blocked, solid_cells)
    for sector, zone_rooms in ROOMS.items():
        for zone, room_type in zone_rooms.items():
            for index, (left, y, right) in enumerate(_runs(zones[zone]), 1):
                add("Zones", f"{zone}.shape-{index:03d}", left * PIXEL_SIZE,
                    y * PIXEL_SIZE, width=(right - left + 1) * PIXEL_SIZE,
                    height=PIXEL_SIZE, sector=sector, zone=zone, room_type=room_type)
    for sector, zone, room_type, kind, item, cell, stance, policy in interactions:
        semantic_id = f"{zone}.{kind}-001"
        add("Interactions", f"{semantic_id}.shape-001", cell[0] * PIXEL_SIZE,
            cell[1] * PIXEL_SIZE, width=PIXEL_SIZE, height=PIXEL_SIZE,
            interaction=semantic_id, sector=sector, zone=zone,
            interaction_type=kind, art_layer="Depth Props", art_object_id=item["id"],
            allowed_room_types=room_type, blocker_policy=policy,
            stance_x=stance[0], stance_y=stance[1])
        used.add(item["id"])
    for sector, point in ENTRANCES.items():
        slug = sector.lower().replace(" ", "-")
        add("Entrances", f"{slug}.entrance", point[0] * PIXEL_SIZE,
            point[1] * PIXEL_SIZE, point=True, sector=sector)
    clear = (blocked | solid_cells) - set(ENTRANCES.values())
    for sector, zone in SPAWN_ZONES.items():
        hint = SPAWN_HINTS.get(sector, (44, 24))
        candidates = sorted(zones[zone] - clear,
                            key=lambda p: (
                                abs(p[0] - hint[0]) + abs(p[1] - hint[1]),
                                p[1], p[0],
                            ))
        if not candidates:
            raise ValueError(f"no clear spawn cell for {sector}")
        point = candidates[0]
        slug = sector.lower().replace(" ", "-")
        add("Spawns", f"{slug}.spawn", point[0] * PIXEL_SIZE,
            point[1] * PIXEL_SIZE, point=True, sector=sector, zone=zone,
            spawn_name="central-plaza" if sector == "Central Plaza" else "sp")
    tmj["nextobjectid"] = next_id
    return frozenset(used)


def apply_spec_sector_embeddings(spec: dict) -> None:
    sectors = {item.get("name"): item for item in spec.get("sectors", [])}
    if set(EMBEDDED_SECTOR_RECTS) != set(sectors):
        raise ValueError("town spec sectors do not match target Claudeville")
    for name, rect in EMBEDDED_SECTOR_RECTS.items():
        sectors[name]["rect"] = list(rect)


def collision_for_tmj(tmj: dict) -> list[list[bool]]:
    return reference_collision.compile_collision(tmj)


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def compile_world_inputs(tmj_path: Path, spec_path: Path = TOWN_SPEC_PATH) -> dict:
    source = Path(tmj_path).expanduser().resolve(strict=True)
    tmj = json.loads(source.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    apply_spec_sector_embeddings(spec)
    collision = collision_for_tmj(tmj)
    result = authoring.compile_authoring(tmj, spec, collision)
    _write_json(spec_path, result.town_spec)
    _write_json(COLLISION_BLUEPRINT_PATH, result.collision_overrides)
    return result.stats


def migrate_spec_sectors(path: Path = TOWN_SPEC_PATH) -> dict[str, list[int]]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    apply_spec_sector_embeddings(spec)
    _write_json(path, spec)
    return {name: list(rect) for name, rect in EMBEDDED_SECTOR_RECTS.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map", type=Path)
    parser.add_argument("--compile-world-inputs", action="store_true")
    args = parser.parse_args(argv)
    source = args.map.expanduser().resolve(strict=True)
    if args.compile_world_inputs:
        print(json.dumps(compile_world_inputs(source), sort_keys=True))
    else:
        tmj = json.loads(source.read_text(encoding="utf-8"))
        print(json.dumps({"retained_support_art_ids": sorted(
            apply_reference_semantic_embeddings(tmj))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
