"""Compile Claudeville's hand-authored Tiled source into a safe visual candidate."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import NamedTuple

try:
    from tools.mapgen import (
        claudeville_tiled_authoring as tiled_authoring,
    )
    from tools.mapgen import (
        tiled_gid,
    )
    from tools.mapgen.claudeville_tilemap_preview import (
        render_preview as _render_preview,
    )
    from tools.mapgen.tilemap_culler import (
        CullError,
        cull_runtime_tilesets,
        stable_source_sha256,
    )
except ModuleNotFoundError:  # Direct ``python tools/mapgen/build_tilemap.py``.
    import claudeville_tiled_authoring as tiled_authoring
    import tiled_gid
    from claudeville_tilemap_preview import render_preview as _render_preview
    from tilemap_culler import CullError, cull_runtime_tilesets, stable_source_sha256

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_ROOT = REPO_ROOT / "environment/frontend_server/static_dirs"
WORLD_ROOT = STATIC_ROOT / "assets/claudeville"
AUTHORING_MAP = WORLD_ROOT / "visuals/claudeville_full_town_v2.tmj"
AUTHORING_ROOT = REPO_ROOT / "output/claudeville/modern_pixels_v2"
SPEC_PATH = Path(__file__).resolve().parent / "town_spec.json"
COLLISION_PATH = WORLD_ROOT / "matrix/maze/collision_maze.csv"
WORLD_MANIFEST_PATH = WORLD_ROOT / "world.json"
ALIAS_MANIFEST_PATH = WORLD_ROOT / "legacy_address_aliases.v1.json"
VISUAL_CANDIDATES_ROOT = WORLD_ROOT / "visual_candidates"
LOGICAL_SIZE, VISUAL_SIZE = (88, 48, 32), (176, 96, 16)
TILE_LAYERS = (
    "Bottom Ground", "Exterior Ground", "Exterior Decoration L1",
    "Exterior Decoration L2", "Interior Ground", "Wall",
    "Interior Furniture L1", "Interior Furniture L2", "Foreground L1", "Foreground L2", "Collisions",
)
OBJECT_LAYERS = ("Depth Props", "Overhead Props")
MAP_LAYER_ORDER = (*TILE_LAYERS[:-1], *OBJECT_LAYERS, TILE_LAYERS[-1])


class TilemapError(ValueError): ...


class BuildResult(NamedTuple):
    candidate_root: Path
    map_path: Path
    preview_path: Path
    manifest_path: Path
    source_sha256: str


def _read_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise TilemapError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TilemapError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise TilemapError(f"{label} root must be an object")
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def _properties(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, list):
        return {}
    return {
        item["name"]: item.get("value") for item in value
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _static_url(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(STATIC_ROOT.resolve())
    except ValueError as exc:
        raise TilemapError(f"runtime output must remain below static root: {path}") from exc
    return relative.as_posix()


def _static_path(url: object, label: str, *, container: Path | None = None) -> Path:
    if not isinstance(url, str) or not url or "\\" in url or url.startswith("/") or "://" in url:
        raise TilemapError(f"{label} must be a contained static asset URL")
    path = (STATIC_ROOT / url).resolve(strict=False)
    boundary = (container or STATIC_ROOT).resolve()
    if path != boundary and boundary not in path.parents:
        raise TilemapError(f"{label} escapes its allowed asset directory")
    if not path.is_file():
        raise TilemapError(f"{label} is missing: {path}")
    return path


def _layer_index(source: dict) -> dict[str, dict]:
    layers = source.get("layers")
    if not isinstance(layers, list) or any(not isinstance(layer, dict) for layer in layers):
        raise TilemapError("TMJ must contain root-level layers")
    names = [layer.get("name") for layer in layers]
    allowed = (list(MAP_LAYER_ORDER), [*MAP_LAYER_ORDER, tiled_authoring.GROUP_NAME])
    if names not in allowed:
        raise TilemapError("TMJ layers must follow the declared render and collision order")
    return {layer["name"]: layer for layer in layers if layer.get("name") in MAP_LAYER_ORDER}


def _validate_map_layers(source: dict) -> dict[str, dict]:
    if (source.get("width"), source.get("height"), source.get("tilewidth"),
            source.get("tileheight"), source.get("infinite"), source.get("orientation")) != (
                *VISUAL_SIZE[:2], VISUAL_SIZE[2], VISUAL_SIZE[2], False, "orthogonal"
            ):
        raise TilemapError("TMJ must be a finite 176x96 orthogonal map at 16px")
    layers = _layer_index(source)
    for name in TILE_LAYERS:
        layer = layers[name]
        data = layer.get("data")
        if layer.get("type") != "tilelayer" or layer.get("width") != VISUAL_SIZE[0] or \
                layer.get("height") != VISUAL_SIZE[1] or not isinstance(data, list) or \
                len(data) != VISUAL_SIZE[0] * VISUAL_SIZE[1] or \
                any(not isinstance(gid, int) or gid < 0 for gid in data):
            raise TilemapError(f"TMJ layer {name} must be a finite 176x96 tile layer")
    for name in OBJECT_LAYERS:
        layer = layers[name]
        if layer.get("type") != "objectgroup" or not isinstance(layer.get("objects"), list):
            raise TilemapError(f"TMJ layer {name} must be an object layer")
        for obj in layer["objects"]:
            properties = _properties(obj.get("properties") if isinstance(obj, dict) else None)
            if not isinstance(obj, dict) or not isinstance(properties.get("asset_key"), str):
                raise TilemapError(f"every {name} object needs a stable asset_key")
            x, y = obj.get("x"), obj.get("y")
            if (not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                        and math.isfinite(value) for value in (x, y)) or
                    not 0 <= x <= VISUAL_SIZE[0] * VISUAL_SIZE[2] or
                    not 0 <= y <= VISUAL_SIZE[1] * VISUAL_SIZE[2]):
                raise TilemapError(f"every {name} object needs an in-bounds position")
            for key, default in (("anchor_x", 0.5), ("anchor_y", 1), ("display_scale", 1)):
                value = properties.get(key, default)
                if (not isinstance(value, (int, float)) or isinstance(value, bool)
                        or not math.isfinite(value)):
                    raise TilemapError(f"object {properties['asset_key']} has invalid {key}")
                if key.startswith("anchor") and not 0 <= value <= 1:
                    raise TilemapError(f"object {properties['asset_key']} has invalid {key}")
                if key == "display_scale" and not 0 < value <= 4:
                    raise TilemapError(f"object {properties['asset_key']} has invalid {key}")
    return layers


def _validate_source(source: dict) -> dict[str, dict]:
    layers = _validate_map_layers(source)
    has_authoring = any(
        item.get("name") == tiled_authoring.GROUP_NAME
        for item in source.get("layers", []) if isinstance(item, dict)
    )
    if has_authoring != tiled_authoring.is_tiled_first(source):
        raise TilemapError("Tiled-first profile and hidden Authoring group must be declared together")
    if has_authoring:
        try:
            tiled_authoring.validate_authoring_group(source)
        except tiled_authoring.TiledAuthoringError as exc:
            raise TilemapError(str(exc)) from exc
    tilesets = source.get("tilesets")
    if not isinstance(tilesets, list) or len(tilesets) not in {4, 5}:
        raise TilemapError(
            "TMJ must reference four base tilesets and at most the v3 prop collection"
        )
    names = {Path(str(entry.get("source", ""))).stem for entry in tilesets if isinstance(entry, dict)}
    firstgids = [entry.get("firstgid") for entry in tilesets if isinstance(entry, dict)]
    required = {"terrain", "town", "office", "interiors"}
    expected = required | ({"interiors_props"} if len(tilesets) == 5 else set())
    if names != expected or (len(tilesets) == 5 and not has_authoring) or \
            len(firstgids) != len(tilesets) or \
            any(not isinstance(value, int) or value < 1 for value in firstgids) or \
            len(firstgids) != len(set(firstgids)):
        raise TilemapError("TMJ must use unique approved base TSJs and the optional v3 prop TSJ")
    return layers


def _load_collision() -> tuple[list[bool], dict]:
    spec = _read_json(SPEC_PATH, "town spec")
    grid = spec.get("grid")
    if not isinstance(grid, dict) or (
            grid.get("maze_width"), grid.get("maze_height"), grid.get("sq_tile_size")
    ) != LOGICAL_SIZE:
        raise TilemapError("town spec must retain the 88x48 logical simulation grid")
    tokens = [token.strip() for token in COLLISION_PATH.read_text(encoding="utf-8").split(",")]
    block_id = str(spec.get("collision_block_id"))
    if len(tokens) != LOGICAL_SIZE[0] * LOGICAL_SIZE[1] or \
            any(token not in {"0", block_id} for token in tokens):
        raise TilemapError("collision_maze.csv must contain canonical collision tokens")
    blocked = [token == block_id for token in tokens]
    for spawn in spec.get("spawns", []):
        tile = spawn.get("tile") if isinstance(spawn, dict) else None
        if not isinstance(tile, list) or len(tile) != 2 or not all(isinstance(value, int) for value in tile):
            raise TilemapError("town spec spawn tiles must be integer pairs")
        x, y = tile
        if not (0 <= x < LOGICAL_SIZE[0] and 0 <= y < LOGICAL_SIZE[1]) or blocked[y * LOGICAL_SIZE[0] + x]:
            raise TilemapError(f"spawn is blocked by canonical collision: {spawn.get('name')}")
    return blocked, spec


def _collision_data(blocked: list[bool], collision_gid: int) -> list[int]:
    return [collision_gid if blocked[(y // 2) * LOGICAL_SIZE[0] + (x // 2)] else 0
            for y in range(VISUAL_SIZE[1]) for x in range(VISUAL_SIZE[0])]


def _embed_tilesets(runtime_root: Path, runtime: dict) -> tuple[list[dict], list[dict], int, str]:
    pages = runtime.get("tilesets")
    if not isinstance(pages, list) or not pages:
        raise TilemapError("runtime culler emitted no tile pages")
    embedded, manifest_tilesets, collision_gid, collision_tileset = [], [], None, None
    for page in pages:
        if not isinstance(page, dict):
            raise TilemapError("runtime tileset page is malformed")
        tsj = _read_json(runtime_root / str(page.get("tileset", "")), "runtime TSJ")
        firstgid = page.get("firstgid")
        name, key, image = tsj.get("name"), page.get("key"), page.get("image")
        if not isinstance(firstgid, int) or not isinstance(name, str) or not isinstance(key, str) or \
                not isinstance(image, str):
            raise TilemapError("runtime tileset page metadata is incomplete")
        inline = dict(tsj)
        inline["firstgid"] = firstgid
        inline["image"] = f"runtime/{image}"
        if key == "terrain":
            collision_gid = firstgid
            collision_tileset = name
            inline["tiles"] = [{"id": 0, "properties": [
                {"name": "collide", "type": "bool", "value": True}
            ]}]
        embedded.append(inline)
        manifest_tilesets.append({
            "name": name,
            "key": f"claudeville-v2-{key}",
            "image_url": _static_url(runtime_root / image),
        })
    if collision_gid is None or collision_tileset is None:
        raise TilemapError("runtime culler omitted the terrain page used for collision")
    return embedded, manifest_tilesets, collision_gid, collision_tileset


def _remap_layers(source: dict, layers: dict[str, dict], runtime: dict, blocked: list[bool],
                  collision_gid: int) -> list[dict]:
    remap = runtime.get("tile_gid_remap")
    flip_bits_mask = runtime.get("tile_gid_flip_mask", tiled_gid.ORTHOGONAL_FLIP_MASK)
    clear_bits_mask = runtime.get("tile_gid_clear_mask", tiled_gid.ALL_FLAG_MASK)
    if not isinstance(remap, dict) or not all(
        isinstance(mask, int) for mask in (flip_bits_mask, clear_bits_mask)
    ):
        raise TilemapError("runtime culler remap is malformed")
    result = []
    for source_layer in source["layers"]:
        name = source_layer["name"]
        if name == tiled_authoring.GROUP_NAME:
            continue
        layer = dict(source_layer)
        if name == "Collisions":
            layer["data"] = _collision_data(blocked, collision_gid)
            layer["visible"] = False
            layer["opacity"] = 0
        elif name in TILE_LAYERS:
            values = []
            for raw_gid in source_layer["data"]:
                source_gid = raw_gid & ~clear_bits_mask
                if not source_gid:
                    values.append(0)
                    continue
                replacement = remap.get(str(source_gid))
                if not isinstance(replacement, int) or replacement < 1:
                    raise TilemapError(f"runtime culler omitted source gid {source_gid}")
                values.append((raw_gid & flip_bits_mask) | replacement)
            layer["data"] = values
        elif name in OBJECT_LAYERS:
            objects = []
            for source_object in source_layer["objects"]:
                item = dict(source_object)
                item.pop("gid", None)
                objects.append(item)
            layer["objects"] = objects
        result.append(layer)
    expected = _collision_data(blocked, collision_gid)
    actual = next(layer["data"] for layer in result if layer["name"] == "Collisions")
    mismatch_count = sum(left != right for left, right in zip(expected, actual))
    if mismatch_count:
        raise TilemapError(f"compiled collision has {mismatch_count} canonical mismatches")
    return result


def build_candidate(source_path: Path = AUTHORING_MAP, *, candidate_root: Path | None = None) -> BuildResult:
    source_path = Path(source_path).expanduser().resolve(strict=True)
    source_sha = stable_source_sha256(source_path)
    source = _read_json(source_path, "Tiled source map")
    layers = _validate_source(source)
    blocked, spec = _load_collision()
    if tiled_authoring.is_tiled_first(source):
        collision = [blocked[y * LOGICAL_SIZE[0]:(y + 1) * LOGICAL_SIZE[0]]
                     for y in range(LOGICAL_SIZE[1])]
        try:
            tiled_authoring.compile_authoring(source, spec, collision)
        except tiled_authoring.TiledAuthoringError as exc:
            raise TilemapError(str(exc)) from exc
    root = (Path(candidate_root).expanduser().resolve(strict=False) if candidate_root else
            WORLD_ROOT / "visual_candidates" / source_sha[:16])
    root = root.resolve(strict=False)
    if WORLD_ROOT.resolve() not in root.parents:
        raise TilemapError("candidate output must remain inside Claudeville assets")
    runtime_root = root / "runtime"
    try:
        runtime = cull_runtime_tilesets(source_path, runtime_root, authoring_root=AUTHORING_ROOT)
    except (OSError, CullError) as exc:
        raise TilemapError(f"could not cull Tiled source: {exc}") from exc
    embedded_tilesets, manifest_tilesets, collision_gid, collision_tileset = _embed_tilesets(
        runtime_root, runtime)
    compiled_layers = _remap_layers(source, layers, runtime, blocked, collision_gid)
    map_data = dict(source)
    map_data.update({"layers": compiled_layers,
                     "nextlayerid": max(layer.get("id", 0) for layer in compiled_layers) + 1,
                     "tilesets": embedded_tilesets, "tiledversion": "1.10.2", "version": "1.10"})
    map_path = root / "claudeville_v2.json"
    preview_path = root / "claudeville_v2_preview.png"
    _write_json(map_path, map_data)
    _render_preview(map_data, runtime_root, preview_path)
    candidate_manifest = dict(_read_json(WORLD_MANIFEST_PATH, "current world manifest"))
    candidate_manifest.update({
        "version": 2,
        "tilemap_url": _static_url(map_path),
        "layer_order": list(MAP_LAYER_ORDER),
        "tilesets": manifest_tilesets,
        "collision_tileset": collision_tileset,
        "tile_layers": list(TILE_LAYERS),
        "object_layers": [{"name": "Depth Props", "atlas": "claudeville-v2-props", "depth_mode": "foot-y"},
            {"name": "Overhead Props", "atlas": "claudeville-v2-props", "depth_mode": "fixed", "depth": 90000},
        ],
        "atlases": ([{"key": "claudeville-v2-props",
            "image_url": _static_url(runtime_root / "props.png"),
            "data_url": _static_url(runtime_root / "props.json")}] if runtime.get("props") else []),
        "rendering": {"texture_filter": "nearest"},
        "depth_model": {"actor_base": 2000, "overhead_depth": 90000},
        "visual_dimensions": {"width": 176, "height": 96, "tile_size": 16},
        "candidate_source_sha256": source_sha,
        "candidate_source_url": _static_url(source_path),
        "credits_url": _static_url(runtime_root / runtime["credits"]),
        "address_alias_manifest_url": _static_url(ALIAS_MANIFEST_PATH),
    })
    candidate_manifest.pop("scene_image_url", None)
    candidate_manifest.pop("aliases", None)
    manifest_path = root / "world.json"
    _write_json(manifest_path, candidate_manifest)
    return BuildResult(root, map_path, preview_path, manifest_path, source_sha)


def promote_candidate(candidate_manifest_path: Path, *, approved_source_sha256: str) -> Path:
    manifest_path = Path(candidate_manifest_path).expanduser().resolve(strict=True)
    root = manifest_path.parent
    if root != VISUAL_CANDIDATES_ROOT and VISUAL_CANDIDATES_ROOT.resolve() not in root.parents:
        raise TilemapError("promotion input must remain inside visual_candidates")
    candidate = _read_json(manifest_path, "candidate world manifest")
    source_hash = candidate.get("candidate_source_sha256")
    if source_hash != approved_source_sha256:
        raise TilemapError("approval hash does not match the candidate world manifest")
    identity = (candidate.get("version"), candidate.get("world"), candidate.get("dimensions"),
                candidate.get("visual_dimensions"))
    expected_identity = (2, "claudeville", {"width": 88, "height": 48, "tile_size": 32},
                         {"width": 176, "height": 96, "tile_size": 16})
    if identity != expected_identity or "scene_image_url" in candidate:
        raise TilemapError("only a completed Claudeville v2 candidate may be promoted")
    object_layers = candidate.get("object_layers", [])
    object_names = [entry.get("name") for entry in object_layers if isinstance(entry, dict)]
    if (candidate.get("layer_order") != list(MAP_LAYER_ORDER) or candidate.get("tile_layers") != list(TILE_LAYERS) or
            object_names != list(OBJECT_LAYERS) or candidate.get("collision_layer") != "Collisions" or
            any(entry.get("atlas") != "claudeville-v2-props" for entry in object_layers)):
        raise TilemapError("candidate manifest does not declare the required 13-layer contract")
    source_path = _static_path(candidate.get("candidate_source_url"), "candidate source", container=WORLD_ROOT / "visuals")
    if stable_source_sha256(source_path) != source_hash:
        raise TilemapError("candidate source no longer matches its reviewed hash")
    alias_path = _static_path(candidate.get("address_alias_manifest_url"), "alias manifest")
    aliases = _read_json(alias_path, "alias manifest")
    if (alias_path != ALIAS_MANIFEST_PATH.resolve() or "aliases" in candidate or aliases.get("schema_version") != 1
            or not isinstance(aliases.get("aliases"), dict)):
        raise TilemapError("candidate must use the approved external alias manifest")
    map_path = _static_path(candidate.get("tilemap_url"), "candidate tilemap", container=root)
    runtime_map = _read_json(map_path, "candidate tilemap")
    layers = _validate_map_layers(runtime_map)
    embedded = runtime_map.get("tilesets")
    manifest_tilesets = candidate.get("tilesets")
    if not isinstance(embedded, list) or not embedded or not isinstance(manifest_tilesets, list):
        raise TilemapError("candidate runtime tilesets are malformed")
    try:
        tiled_gid.validate_runtime_gids(layers, embedded, TILE_LAYERS)
    except tiled_gid.TiledGidError as exc:
        raise TilemapError(str(exc)) from exc
    embedded_names = {item.get("name") for item in embedded if isinstance(item, dict)}
    declared_names = {item.get("name") for item in manifest_tilesets if isinstance(item, dict)}
    if embedded_names != declared_names or candidate.get("collision_tileset") not in embedded_names:
        raise TilemapError("candidate runtime tilesets do not match the manifest")
    for item in embedded:
        image = item.get("image") if isinstance(item, dict) else None
        if not isinstance(image, str) or "://" in image or "\\" in image:
            raise TilemapError("embedded tileset image path is malformed")
        image_path = (map_path.parent / image).resolve(strict=False)
        if root not in image_path.parents or not image_path.is_file():
            raise TilemapError("embedded tileset image escapes the candidate")
    asset_urls = [(item, "image_url") for item in manifest_tilesets]
    atlases = candidate.get("atlases", [])
    if not isinstance(atlases, list):
        raise TilemapError("candidate atlases are malformed")
    asset_urls.extend((item, key) for item in atlases for key in ("image_url", "data_url"))
    asset_urls.append((candidate, "credits_url"))
    for item, key in asset_urls:
        if not isinstance(item, dict):
            raise TilemapError("candidate asset declaration is malformed")
        _static_path(item.get(key), f"candidate {key}", container=root)
    frames = {}
    for atlas in atlases:
        path = _static_path(atlas.get("data_url"), "candidate atlas metadata", container=root)
        metadata = _read_json(path, "candidate atlas metadata").get("frames")
        if not isinstance(metadata, dict):
            raise TilemapError("candidate atlas frames are malformed")
        frames.update(metadata)
    requested = {_properties(obj.get("properties")).get("asset_key")
                 for name in OBJECT_LAYERS for obj in layers[name]["objects"]}
    if not requested or None in requested or not requested.issubset(frames):
        raise TilemapError("candidate object asset keys do not resolve in the runtime atlas")
    blocked, _spec = _load_collision()
    expected = _collision_data(blocked, 1)
    mismatches = sum(bool(actual & tiled_gid.GID_MASK) != bool(wanted) for actual, wanted in
                     zip(layers["Collisions"]["data"], expected))
    if mismatches:
        raise TilemapError(f"candidate collision has {mismatches} canonical mismatches")
    _write_json(WORLD_MANIFEST_PATH, candidate)
    return WORLD_MANIFEST_PATH


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=AUTHORING_MAP)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--promote", type=Path, metavar="CANDIDATE_WORLD_JSON")
    parser.add_argument("--approved-source-sha256")
    args = parser.parse_args(argv)
    try:
        if args.promote:
            if not args.approved_source_sha256:
                parser.error("--promote requires --approved-source-sha256")
            path = promote_candidate(args.promote, approved_source_sha256=args.approved_source_sha256)
            print(f"Promoted {path}")
            return 0
        result = build_candidate(args.source, candidate_root=args.candidate_root)
    except (OSError, TilemapError) as exc:
        parser.error(str(exc))
    print(f"Built {result.map_path} and {result.preview_path}; collision mismatches=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
