"""Apply data-driven semantic migrations for explicit district passes."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from tools.mapgen import claudeville_tiled_authoring as authoring
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_tiled_authoring as authoring

LOGICAL_TILE = 32
VISUAL_SCALE = 2
VISUAL_WIDTH = 176
VISUAL_HEIGHT = 96
WALL_HORIZONTAL = 38062
WALL_TOP_LEFT = 38066
WALL_TOP_RIGHT = 38065
WALL_LEFT = 38069
WALL_RIGHT = 38067


def clear_tileset_tiles_in_rects(
    tmj: dict, map_path: Path, source_stem: str,
    rects: tuple[tuple[int, int, int, int], ...],
) -> int:
    """Remove superseded-source tiles only inside explicit visual rectangles."""
    matches = [
        item for item in tmj.get("tilesets", [])
        if Path(str(item.get("source", ""))).stem == source_stem
    ]
    if not matches:
        return 0
    if len(matches) != 1:
        raise ValueError(f"expected at most one {source_stem} tileset reference")
    if not rects or any(
        not (0 <= left < right <= VISUAL_WIDTH and 0 <= top < bottom <= VISUAL_HEIGHT)
        for left, top, right, bottom in rects
    ):
        raise ValueError("legacy tile clear needs finite in-bounds rectangles")
    reference = matches[0]
    source_path = (map_path.parent / reference["source"]).resolve(strict=True)
    tileset = json.loads(source_path.read_text(encoding="utf-8"))
    firstgid, tilecount = reference.get("firstgid"), tileset.get("tilecount")
    if not isinstance(firstgid, int) or not isinstance(tilecount, int) or tilecount <= 0:
        raise ValueError(f"invalid {source_stem} tileset range")
    lastgid = firstgid + tilecount - 1
    cleared = 0
    for layer in tmj.get("layers", []):
        if layer.get("type") != "tilelayer":
            continue
        data = layer.get("data")
        if not isinstance(data, list) or not all(isinstance(value, int) for value in data):
            raise ValueError(f"invalid finite tile data: {layer.get('name')}")
        for left, top, right, bottom in rects:
            for y in range(top, bottom):
                for x in range(left, right):
                    index = y * VISUAL_WIDTH + x
                    gid = data[index] & 0x0FFFFFFF
                    if firstgid <= gid <= lastgid:
                        data[index] = 0
                        cleared += 1
    return cleared


def clear_tileset_tiles(tmj: dict, map_path: Path, source_stem: str) -> int:
    """Remove every active tile belonging to one superseded source tileset."""
    return clear_tileset_tiles_in_rects(
        tmj, map_path, source_stem, ((0, 0, VISUAL_WIDTH, VISUAL_HEIGHT),),
    )


def _resolve_gid(value, sources: dict[str, dict[str, int]]) -> int:
    if isinstance(value, int) and value > 0:
        return value
    if not isinstance(value, tuple) or len(value) != 3:
        raise ValueError(f"invalid tile reference: {value}")
    source_id, row, column = value
    source = sources.get(source_id)
    if (
        source is None or not isinstance(row, int) or not isinstance(column, int)
        or not 0 <= row < source["rows"]
        or not 0 <= column < source["columns"]
    ):
        raise ValueError(f"invalid source-aligned tile reference: {value}")
    return source["firstgid"] + row * source["columns"] + column


def _children(tmj: dict) -> dict[str, dict]:
    group = next(
        (layer for layer in tmj.get("layers", []) if layer.get("name") == "Authoring"),
        None,
    )
    if not isinstance(group, dict):
        raise ValueError("candidate map has no Authoring group")
    result = {layer.get("name"): layer for layer in group.get("layers", [])}
    if not set(authoring.AUTHORING_LAYERS) <= result.keys():
        raise ValueError("candidate map has an incomplete Authoring group")
    return result


def _cells(item: dict) -> set[tuple[int, int]]:
    values = (item.get("x"), item.get("y"), item.get("width"), item.get("height"))
    if not all(isinstance(value, int) and value % LOGICAL_TILE == 0 for value in values):
        raise ValueError(f"semantic object is not logical-grid aligned: {item.get('name')}")
    x, y, width, height = values
    return {
        (cell_x, cell_y)
        for cell_y in range(y // LOGICAL_TILE, (y + height) // LOGICAL_TILE)
        for cell_x in range(x // LOGICAL_TILE, (x + width) // LOGICAL_TILE)
    }


def _append_cell(
    layer: dict, object_id: int, semantic_id: str, cell: tuple[int, int], **values,
) -> None:
    layer["objects"].append(authoring.make_authoring_object(
        object_id, semantic_id, cell[0] * LOGICAL_TILE, cell[1] * LOGICAL_TILE,
        width=LOGICAL_TILE, height=LOGICAL_TILE, **values,
    ))


def prepare_semantics(tmj: dict, module) -> dict[str, int]:
    """Remove superseded shapes, then add zone and interaction shapes."""
    migrations = getattr(module, "SEMANTIC_MIGRATIONS", None)
    if not migrations:
        return {"added_interactions": 0, "added_zones": 0, "removed_shapes": 0}
    children = _children(tmj)
    zones, interactions = children["Zones"], children["Interactions"]

    removed = 0
    for sector, zone, remove_cell in migrations.get("zone_shape_removals", ()):
        matches = []
        for item in zones["objects"]:
            values = authoring.properties(item.get("properties"))
            if values.get("sector") == sector and values.get("zone") == zone \
                    and remove_cell in _cells(item):
                matches.append(item)
        if len(matches) != 1 or _cells(matches[0]) != {remove_cell}:
            raise ValueError(f"{zone} needs one single-cell shape at {remove_cell}")
        zones["objects"].remove(matches[0])
        removed += 1

    for sector, interaction_id, remove_cell, retained_cell in migrations[
        "interaction_shape_removals"
    ]:
        matches = []
        for item in interactions["objects"]:
            values = authoring.properties(item.get("properties"))
            if values.get("sector") == sector and values.get("interaction") == interaction_id \
                    and remove_cell in _cells(item):
                matches.append(item)
        if len(matches) != 1 or _cells(matches[0]) != {remove_cell}:
            raise ValueError(
                f"{interaction_id} needs one single-cell shape at {remove_cell}"
            )
        interactions["objects"].remove(matches[0])
        retained = [
            item for item in interactions["objects"]
            if authoring.properties(item.get("properties")).get("interaction")
            == interaction_id and retained_cell in _cells(item)
        ]
        if not retained:
            raise ValueError(f"{interaction_id} lost its retained shape at {retained_cell}")
        removed += 1

    occupied = {
        cell: authoring.properties(item.get("properties")).get("zone")
        for item in zones["objects"] for cell in _cells(item)
    }
    next_id = max(tmj.get("nextobjectid", 1), 1)
    added_zones = 0
    for sector, zone, room_type, cells in migrations["zone_additions"]:
        for index, cell in enumerate(cells, 1):
            if cell in occupied:
                raise ValueError(f"new zone {zone} overlaps {occupied[cell]} at {cell}")
            _append_cell(
                zones, next_id, f"{zone}.south-shape-{index:03d}", cell,
                sector=sector, zone=zone, room_type=room_type,
            )
            occupied[cell] = zone
            next_id += 1
            added_zones += 1

    room_types: dict[str, str] = {}
    for item in zones["objects"]:
        values = authoring.properties(item.get("properties"))
        zone, room_type = values.get("zone"), values.get("room_type")
        if isinstance(zone, str) and isinstance(room_type, str):
            if zone in room_types and room_types[zone] != room_type:
                raise ValueError(f"zone {zone} has conflicting room types")
            room_types[zone] = room_type

    added_interactions = 0
    for (
        sector, zone, semantic_id, interaction_type, cells, stance, art_key, policy,
    ) in migrations["interaction_additions"]:
        room_type = room_types.get(zone)
        if room_type is None:
            raise ValueError(f"interaction {semantic_id} uses unknown zone {zone}")
        for index, cell in enumerate(cells, 1):
            _append_cell(
                interactions, next_id, f"{semantic_id}.south-shape-{index:03d}", cell,
                sector=sector, zone=zone, interaction=semantic_id,
                interaction_type=interaction_type, art_layer="Depth Props",
                art_asset_key=art_key, allowed_room_types=room_type,
                blocker_policy=policy, stance_x=stance[0], stance_y=stance[1],
            )
            next_id += 1
            added_interactions += 1
    tmj["nextobjectid"] = next_id
    return {
        "added_interactions": added_interactions,
        "added_zones": added_zones,
        "removed_shapes": removed,
    }


def patch_zone_floors(tmj: dict, layers: dict[str, dict], module) -> int:
    """Apply one floor GID to every 2x2 visual tile block in a named zone."""
    patches = getattr(module, "FLOOR_PATCHES", ())
    if not patches:
        return 0
    zones = _children(tmj)["Zones"]["objects"]
    floor = layers.get("Interior Ground")
    data = None if floor is None else floor.get("data")
    if not isinstance(data, list) or len(data) != 176 * 96:
        raise ValueError("Interior Ground is not a finite 176x96 tile layer")
    written: set[tuple[int, int]] = set()
    patch_keys: set[tuple[str, str]] = set()
    for sector, zone, gid in patches:
        key = sector, zone
        if key in patch_keys or not isinstance(gid, int) or gid <= 0:
            raise ValueError(f"invalid or duplicate floor patch: {key}")
        patch_keys.add(key)
        cells = set()
        for item in zones:
            values = authoring.properties(item.get("properties"))
            if values.get("sector") == sector and values.get("zone") == zone:
                cells.update(_cells(item))
        if not cells:
            raise ValueError(f"floor patch uses empty zone: {sector}/{zone}")
        for logical_x, logical_y in cells:
            for offset_y in range(VISUAL_SCALE):
                for offset_x in range(VISUAL_SCALE):
                    visual = (
                        logical_x * VISUAL_SCALE + offset_x,
                        logical_y * VISUAL_SCALE + offset_y,
                    )
                    if visual in written:
                        raise ValueError(f"floor patches overlap at {visual}")
                    data[visual[1] * VISUAL_WIDTH + visual[0]] = gid
                    written.add(visual)
    return len(written)


def paint_visual_structure(
    layers: dict[str, dict], module, tile_sources: dict[str, dict[str, int]] | None = None,
) -> int:
    """Paint explicit continuous room shells without changing semantics or collision."""
    shells = getattr(module, "VISUAL_SHELLS", ())
    if not shells:
        return 0
    floor_layer, wall_layer = layers.get("Interior Ground"), layers.get("Wall")
    floor = None if floor_layer is None else floor_layer.get("data")
    walls = None if wall_layer is None else wall_layer.get("data")
    if not isinstance(floor, list) or len(floor) != VISUAL_WIDTH * VISUAL_HEIGHT \
            or not isinstance(walls, list) or len(walls) != VISUAL_WIDTH * VISUAL_HEIGHT:
        raise ValueError("visual structure needs finite Interior Ground and Wall layers")
    structure_targets = set(getattr(module, "STRUCTURE_TARGETS", module.TARGETS))
    if not structure_targets <= set(module.TARGETS) \
            or len(shells) != len(structure_targets) \
            or {shell[0] for shell in shells} != structure_targets:
        raise ValueError("every district target needs exactly one visual shell")

    for sector in structure_targets:
        left, top, right, bottom = module.TARGET_BOUNDS[sector]
        for y in range(top, bottom):
            start = y * VISUAL_WIDTH + left
            floor[start:start + right - left] = [0] * (right - left)
            walls[start:start + right - left] = [0] * (right - left)

    written = 0
    sources = tile_sources or {}
    shell_bounds = {}
    patterns = getattr(module, "FLOOR_PATTERNS", {})
    wall_style = getattr(module, "WALL_TILE_STYLE", {})
    wall_horizontal = _resolve_gid(
        wall_style.get("horizontal", WALL_HORIZONTAL), sources,
    )
    wall_top_left = _resolve_gid(
        wall_style.get("top_left", WALL_TOP_LEFT), sources,
    )
    wall_top_right = _resolve_gid(
        wall_style.get("top_right", WALL_TOP_RIGHT), sources,
    )
    wall_left = _resolve_gid(wall_style.get("left", WALL_LEFT), sources)
    wall_right = _resolve_gid(wall_style.get("right", WALL_RIGHT), sources)
    for shell in shells:
        if len(shell) not in (8, 9):
            raise ValueError(f"invalid visual shell record: {shell}")
        sector, left, top, right, bottom, door_left, door_right, floor_style = shell[:8]
        door_edge = shell[8] if len(shell) == 9 else "top"
        target_left, target_top, target_right, target_bottom = module.TARGET_BOUNDS[sector]
        if not (
            target_left <= left < door_left <= door_right < right < target_right
            and target_top <= top < bottom < target_bottom
            and door_edge in {"top", "bottom"}
        ):
            raise ValueError(f"invalid visual shell for {sector}")
        pattern = patterns.get(floor_style) if isinstance(floor_style, str) else None
        if isinstance(floor_style, (int, tuple)):
            pattern = ((floor_style,),)
        if not isinstance(pattern, tuple) or not pattern or not pattern[0] \
                or any(len(row) != len(pattern[0]) for row in pattern) \
                or any(
                    not isinstance(gid, (int, tuple)) for row in pattern for gid in row
                ):
            raise ValueError(f"invalid floor style for {sector}: {floor_style}")
        resolved_pattern = tuple(
            tuple(_resolve_gid(gid, sources) for gid in row) for row in pattern
        )
        shell_bounds[sector] = left, top, right, bottom
        for y in range(top + 1, bottom):
            for x in range(left + 1, right):
                row = resolved_pattern[(y - top - 1) % len(resolved_pattern)]
                floor[y * VISUAL_WIDTH + x] = row[(x - left - 1) % len(row)]
                written += 1
        for x in range(left + 1, right):
            if door_edge != "top" or not door_left <= x <= door_right:
                walls[top * VISUAL_WIDTH + x] = wall_horizontal
                written += 1
            if door_edge != "bottom" or not door_left <= x <= door_right:
                walls[bottom * VISUAL_WIDTH + x] = wall_horizontal
                written += 1
        walls[top * VISUAL_WIDTH + left] = wall_top_left
        walls[top * VISUAL_WIDTH + right] = wall_top_right
        walls[bottom * VISUAL_WIDTH + left] = wall_left
        walls[bottom * VISUAL_WIDTH + right] = wall_right
        written += 4
        for y in range(top + 1, bottom):
            walls[y * VISUAL_WIDTH + left] = wall_left
            walls[y * VISUAL_WIDTH + right] = wall_right
            written += 2

    for sector, pattern_key, left, top in getattr(module, "FLOOR_STAMPS", ()):
        pattern = patterns.get(pattern_key)
        shell_left, shell_top, shell_right, shell_bottom = shell_bounds.get(
            sector, (-1, -1, -1, -1)
        )
        if not isinstance(pattern, tuple) or not pattern or not pattern[0]:
            raise ValueError(f"floor stamp uses unknown pattern: {pattern_key}")
        height, width = len(pattern), len(pattern[0])
        if not (
            shell_left < left and left + width - 1 < shell_right
            and shell_top < top and top + height - 1 < shell_bottom
        ):
            raise ValueError(f"floor stamp is outside {sector}")
        for offset_y, row in enumerate(pattern):
            for offset_x, gid in enumerate(row):
                floor[(top + offset_y) * VISUAL_WIDTH + left + offset_x] = (
                    _resolve_gid(gid, sources)
                )
                written += 1

    for sector, left, top, right, bottom, gid in getattr(
        module, "ROOM_FLOOR_RECTS", ()
    ):
        shell_left, shell_top, shell_right, shell_bottom = shell_bounds.get(
            sector, (-1, -1, -1, -1)
        )
        if not (
            shell_left < left <= right < shell_right
            and shell_top < top <= bottom < shell_bottom
            and isinstance(gid, (int, tuple))
        ):
            raise ValueError(f"invalid room floor rectangle for {sector}")
        resolved_gid = _resolve_gid(gid, sources)
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                floor[y * VISUAL_WIDTH + x] = resolved_gid
                written += 1

    for sector, orientation, fixed, start, end, gaps in getattr(
        module, "WALL_RUNS", ()
    ):
        left, top, right, bottom = shell_bounds.get(sector, (-1, -1, -1, -1))
        if orientation == "horizontal":
            valid = top <= fixed <= bottom and left <= start <= end <= right
            points = ((x, fixed, wall_horizontal) for x in range(start, end + 1))
        elif orientation == "vertical":
            valid = left <= fixed <= right and top <= start <= end <= bottom
            points = ((fixed, y, wall_left) for y in range(start, end + 1))
        else:
            raise ValueError(f"unknown wall orientation for {sector}: {orientation}")
        if not valid or any(not start <= gap <= end for gap in gaps):
            raise ValueError(f"invalid wall run for {sector}")
        for x, y, gid in points:
            if (x if orientation == "horizontal" else y) in gaps:
                continue
            walls[y * VISUAL_WIDTH + x] = gid
            written += 1
    for layer_name, x, y, tile in getattr(module, "VISUAL_TILE_EDITS", ()):
        layer = layers.get(layer_name)
        data = None if layer is None else layer.get("data")
        if not (
            isinstance(data, list) and len(data) == VISUAL_WIDTH * VISUAL_HEIGHT
            and 0 <= x < VISUAL_WIDTH and 0 <= y < VISUAL_HEIGHT
        ):
            raise ValueError(f"invalid explicit visual tile edit: {(layer_name, x, y)}")
        data[y * VISUAL_WIDTH + x] = _resolve_gid(tile, sources)
        written += 1
    return written


def add_blockers(tmj: dict, module, created: list[dict]) -> int:
    """Add canonical blocker shapes linked to the nearest matching authored prop."""
    migrations = getattr(module, "SEMANTIC_MIGRATIONS", None)
    if not migrations:
        return 0
    blockers = _children(tmj)["Blockers"]
    existing = []
    for item in blockers["objects"]:
        values = authoring.properties(item.get("properties"))
        if values.get("sector") in module.TARGETS and \
                ".south-shape-" in str(values.get("semantic_id", "")):
            existing.append(item)
    expected = sum(
        len(cells) for _sector, _zone, _semantic_id, cells, _key, _policy
        in migrations["blocker_additions"]
    )
    if len(existing) not in {0, expected}:
        raise ValueError("district blocker migration is only partially authored")
    if existing:
        blockers["objects"] = [
            item for item in blockers["objects"] if item not in existing
        ]
    next_id = max(tmj.get("nextobjectid", 1), 1)
    count = 0
    for sector, zone, semantic_id, cells, art_key, policy in migrations[
        "blocker_additions"
    ]:
        candidates = [
            item for item in created
            if (values := authoring.properties(item.get("properties"))).get("sector")
            == sector and values.get("asset_key") == art_key
        ]
        if not candidates:
            raise ValueError(f"blocker {semantic_id} has no matching {art_key} art")
        for index, cell in enumerate(cells, 1):
            center_x = cell[0] * LOGICAL_TILE + LOGICAL_TILE / 2
            center_y = cell[1] * LOGICAL_TILE + LOGICAL_TILE / 2
            linked = min(
                candidates,
                key=lambda item: abs(item["x"] - center_x) + abs(item["y"] - center_y),
            )
            values = {
                "sector": sector, "art_layer": "Depth Props",
                "art_object_id": linked["id"], "blocker_policy": policy,
            }
            if zone is not None:
                values["zone"] = zone
            _append_cell(
                blockers, next_id, f"{semantic_id}.south-shape-{index:03d}",
                cell, **values,
            )
            next_id += 1
            count += 1
    tmj["nextobjectid"] = next_id
    return count


def update_interaction_stances(tmj: dict, module) -> int:
    raw_updates = getattr(module, "INTERACTION_STANCE_UPDATES", ())
    updates = {(sector, interaction): (x, y) for sector, interaction, x, y in raw_updates}
    if not updates:
        return 0
    interactions = _children(tmj)["Interactions"]["objects"]
    matched, count = set(), 0
    for item in interactions:
        values = authoring.properties(item.get("properties"))
        key = values.get("sector"), values.get("interaction")
        if key not in updates:
            continue
        stance_x, stance_y = updates[key]
        names = set()
        for prop in item["properties"]:
            if prop["name"] in {"stance_x", "stance_y"}:
                prop["value"] = stance_x if prop["name"] == "stance_x" else stance_y
                names.add(prop["name"])
        if names != {"stance_x", "stance_y"}:
            raise ValueError(f"interaction stance properties are incomplete: {key}")
        matched.add(key)
        count += 1
    if matched != set(updates):
        raise ValueError("stance migration references missing interactions")
    return count
