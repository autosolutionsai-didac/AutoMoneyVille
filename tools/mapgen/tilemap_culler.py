"""Cull the Claudeville v2 authoring palette into runtime-only tile and prop atlases."""

from __future__ import annotations

import argparse
import bisect
import json
from hashlib import sha256
from pathlib import Path

from PIL import Image

try:
    from tools.mapgen import tiled_gid
    from tools.mapgen.curate_modern_pixels_v2 import (
        DEFAULT_OUTPUT_ROOT,
        MAX_ATLAS_SIZE,
        TILE_SIZE,
        CurationError,
        atlas_dimensions,
    )
except ModuleNotFoundError:  # Direct ``python tools/mapgen/cull_modern_pixels_v2.py``.
    import tiled_gid
    from curate_modern_pixels_v2 import (
        DEFAULT_OUTPUT_ROOT,
        MAX_ATLAS_SIZE,
        TILE_SIZE,
        CurationError,
        atlas_dimensions,
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SIZE = (176, 96)
FLIP_MASK = tiled_gid.GID_MASK


class CullError(CurationError):
    """Raised when a Tiled source cannot be reduced safely."""


def stable_source_sha256(path: Path) -> str:
    """Hash a Tiled source consistently across Git line-ending policies."""
    return sha256(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()


def _read_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise CullError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CullError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise CullError(f"{label} root must be an object")
    return value


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_png(path: Path, image: Image.Image) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    image.save(temporary, format="PNG", compress_level=9, optimize=False)
    temporary.replace(path)


def _contained_file(root: Path, relative: object, label: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise CullError(f"{label} path is malformed")
    boundary = root.resolve()
    path = (boundary / relative).resolve(strict=False)
    if path == boundary or boundary not in path.parents or not path.is_file():
        raise CullError(f"{label} escapes the authoring root")
    return path


def _map_tilesets(source: dict) -> list[tuple[int, str]]:
    tilesets = source.get("tilesets")
    if not isinstance(tilesets, list) or not tilesets:
        raise CullError("TMJ must declare at least one tileset")
    result = []
    for entry in tilesets:
        if not isinstance(entry, dict) or not isinstance(entry.get("firstgid"), int):
            raise CullError("TMJ tilesets need integer firstgid values")
        source_path = entry.get("source")
        key = Path(str(source_path)).stem if isinstance(source_path, str) else None
        if key not in {"terrain", "town", "office", "interiors"}:
            raise CullError(
                "TMJ may reference only curated terrain, town, office, or interiors TSJs"
            )
        result.append((entry["firstgid"], key))
    if len({firstgid for firstgid, _ in result}) != len(result):
        raise CullError("TMJ tileset firstgid values must be unique")
    return sorted(result)


def _walk_layers(layers: list[dict]):
    for layer in layers:
        if not isinstance(layer, dict):
            raise CullError("TMJ layers must be objects")
        yield layer
        nested = layer.get("layers")
        if nested is not None:
            if not isinstance(nested, list):
                raise CullError("TMJ group layers must contain a layer list")
            yield from _walk_layers(nested)


def _object_asset_key(properties) -> str | None:
    if isinstance(properties, dict):
        value = properties.get("asset_key")
        return value if isinstance(value, str) and value else None
    if isinstance(properties, list):
        for item in properties:
            if isinstance(item, dict) and item.get("name") == "asset_key":
                value = item.get("value")
                return value if isinstance(value, str) and value else None
    return None


def _source_gid(firstgids: list[int], tilesets: dict[int, str], gid: int) -> tuple[str, int]:
    firstgid = firstgids[bisect.bisect_right(firstgids, gid) - 1]
    return tilesets[firstgid], gid - firstgid


def _selected_assets(source: dict, tile_catalog: dict[tuple[str, int], dict]):
    tilesets = _map_tilesets(source)
    by_firstgid = dict(tilesets)
    firstgids = [entry[0] for entry in tilesets]
    selected_tiles, source_gids, props = {}, set(), set()
    layers = source.get("layers")
    if not isinstance(layers, list):
        raise CullError("TMJ must contain a layer list")
    for layer in _walk_layers(layers):
        if layer.get("type") == "tilelayer":
            data = layer.get("data")
            if not isinstance(data, list):
                raise CullError("finite TMJ tile layers must use a data array")
            if len(data) != EXPECTED_SIZE[0] * EXPECTED_SIZE[1]:
                raise CullError("finite TMJ tile layers must contain 16,896 tile values")
            for raw_gid in data:
                if not isinstance(raw_gid, int):
                    raise CullError("TMJ tile data must contain integers")
                gid = raw_gid & FLIP_MASK
                if not gid:
                    continue
                atlas, tile_id = _source_gid(firstgids, by_firstgid, gid)
                record = tile_catalog.get((atlas, tile_id))
                if record is None:
                    raise CullError(f"TMJ references unknown curated tile {atlas}#{tile_id}")
                selected_tiles[record["asset_key"]] = record
                source_gids.add(gid)
        if layer.get("type") == "objectgroup":
            objects = layer.get("objects", [])
            if not isinstance(objects, list):
                raise CullError("TMJ object layers must contain an object list")
            for obj in objects:
                if not isinstance(obj, dict):
                    raise CullError("TMJ objects must be objects")
                key = _object_asset_key(obj.get("properties"))
                if key is not None:
                    props.add(key)
    return selected_tiles, sorted(source_gids), sorted(props)


def _pack_props(images: list[tuple[str, Image.Image]]):
    for width in (256, 512, 1024, 2048, 4096):
        # The authoring palette includes complete civic façades such as the
        # school.  A narrow first candidate page must not reject an otherwise
        # valid sprite that fits on a later bounded runtime page.
        if any(image.width + 4 > width for _, image in images):
            continue
        x = y = row_height = 2
        placements = []
        for key, image in images:
            if x + image.width + 2 > width:
                x, y, row_height = 2, y + row_height + 2, 0
            placements.append((key, image, x, y))
            x += image.width + 2
            row_height = max(row_height, image.height)
        height = y + row_height + 2
        if height <= width and height <= MAX_ATLAS_SIZE:
            return width, height, placements
    raise CullError("runtime prop atlas would exceed 4096x4096")


def _validate_requested_props(authoring: Path, requested: list[str]) -> None:
    frames = _read_json(authoring / "props.json", "authoring props metadata").get("frames")
    if not isinstance(frames, dict):
        raise CullError("authoring props metadata is missing frames")
    missing = sorted(set(requested) - set(frames))
    if missing:
        raise CullError(f"TMJ object assets are missing from props catalog: {missing}")


def _write_runtime_tiles(output: Path, authoring: Path, selected: dict[str, dict]):
    atlas_meta = _read_json(authoring / "atlas.json", "authoring atlas metadata")
    pages = {page.get("key"): page for page in atlas_meta.get("atlases", []) if isinstance(page, dict)}
    groups = {"terrain": [], "town": [], "office": [], "interiors": []}
    for record in selected.values():
        groups[record["atlas"]].append(record)
    runtime_pages, asset_remap, firstgid = [], {}, 1
    for key in ("terrain", "town", "office", "interiors"):
        records = sorted(groups[key], key=lambda item: item["atlas_index"])
        if not records:
            continue
        source_page = pages.get(key)
        if source_page is None:
            raise CullError(f"authoring atlas page is missing: {key}")
        with Image.open(
            _contained_file(authoring, source_page.get("image"), f"authoring {key} atlas")
        ) as opened:
            source_image = opened.convert("RGBA")
        width, height, columns = atlas_dimensions(len(records))
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for new_id, record in enumerate(records):
            old_id = record["atlas_index"]
            old_x = (old_id % source_page["columns"]) * TILE_SIZE
            old_y = (old_id // source_page["columns"]) * TILE_SIZE
            image.paste(source_image.crop((old_x, old_y, old_x + TILE_SIZE, old_y + TILE_SIZE)), ((new_id % columns) * TILE_SIZE, (new_id // columns) * TILE_SIZE))
            asset_remap[record["asset_key"]] = {"atlas": key, "runtime_gid": firstgid + new_id, "tile_id": new_id}
        tile_dir = output / "tiles"
        tile_dir.mkdir(parents=True, exist_ok=True)
        image_path = tile_dir / f"{key}.png"
        tileset_path = tile_dir / f"{key}.tsj"
        _write_png(image_path, image)
        _write_json(tileset_path, {"columns": columns, "image": image_path.name, "imageheight": height, "imagewidth": width, "name": f"claudeville_v2_runtime_{key}", "tilecount": len(records), "tileheight": TILE_SIZE, "tilewidth": TILE_SIZE, "type": "tileset", "version": "1.10"})
        runtime_pages.append({"firstgid": firstgid, "image": f"tiles/{image_path.name}", "key": key, "tile_count": len(records), "tileset": f"tiles/{tileset_path.name}"})
        firstgid += len(records)
    return runtime_pages, asset_remap


def _write_runtime_props(output: Path, authoring: Path, requested: list[str]):
    source_meta = _read_json(authoring / "props.json", "authoring props metadata")
    frames = source_meta.get("frames")
    if not isinstance(frames, dict):
        raise CullError("authoring props metadata is missing frames")
    missing = sorted(set(requested) - set(frames))
    if missing:
        raise CullError(f"TMJ object assets are missing from props catalog: {missing}")
    with Image.open(authoring / "props.png") as opened:
        source_image = opened.convert("RGBA")
    images = []
    for key in requested:
        frame = frames[key].get("frame") if isinstance(frames[key], dict) else None
        if not isinstance(frame, dict) or not all(isinstance(frame.get(axis), int) for axis in ("x", "y", "w", "h")):
            raise CullError(f"authoring prop frame is malformed: {key}")
        images.append((key, source_image.crop((frame["x"], frame["y"], frame["x"] + frame["w"], frame["y"] + frame["h"]))))
    if not images:
        return None
    width, height, placements = _pack_props(images)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    frames_out = {}
    for key, prop, x, y in placements:
        image.alpha_composite(prop, (x, y))
        frames_out[key] = {"frame": {"h": prop.height, "w": prop.width, "x": x, "y": y}, "rotated": False, "spriteSourceSize": {"h": prop.height, "w": prop.width, "x": 0, "y": 0}, "sourceSize": {"h": prop.height, "w": prop.width}, "trimmed": False}
    _write_png(output / "props.png", image)
    _write_json(output / "props.json", {"frames": frames_out, "meta": {"app": "Claudeville Modern Pixels v2 runtime", "format": "RGBA8888", "image": "props.png", "scale": "1", "size": {"h": height, "w": width}}})
    return {"asset_keys": requested, "data": "props.json", "image": "props.png", "key": "claudeville-v2-props"}


def cull_runtime_tilesets(source_tmj: Path, output_root: Path, *, authoring_root: Path = DEFAULT_OUTPUT_ROOT) -> dict:
    """Return a deterministic compact runtime asset manifest for one hand-authored TMJ."""
    source_path = Path(source_tmj).expanduser().resolve(strict=True)
    authoring = Path(authoring_root).expanduser().resolve(strict=True)
    output = Path(output_root).expanduser().resolve(strict=False)
    if source_path.suffix.lower() != ".tmj" or not authoring.is_dir() or output == authoring or authoring in output.parents or output in authoring.parents:
        raise CullError("TMJ source and runtime output must be separate valid paths")
    source = _read_json(source_path, "TMJ source")
    if (source.get("width"), source.get("height"), source.get("tilewidth"), source.get("tileheight"), source.get("infinite")) != (*EXPECTED_SIZE, TILE_SIZE, TILE_SIZE, False):
        raise CullError("TMJ must be a finite 176x96 native-16px map")
    tile_records = _read_json(authoring / "tiles.json", "authoring tile catalog").get("tiles")
    if not isinstance(tile_records, list):
        raise CullError("authoring tile catalog is missing tiles")
    tile_catalog = {(record.get("atlas"), record.get("atlas_index")): record for record in tile_records if isinstance(record, dict)}
    selected, source_gids, props = _selected_assets(source, tile_catalog)
    if not selected:
        raise CullError("TMJ must reference at least one curated tile")
    _validate_requested_props(authoring, props)
    output.mkdir(parents=True, exist_ok=True)
    pages, asset_remap = _write_runtime_tiles(output, authoring, selected)
    remap = {}
    tilesets = _map_tilesets(source)
    firstgids, by_firstgid = [item[0] for item in tilesets], dict(tilesets)
    for gid in source_gids:
        atlas, tile_id = _source_gid(firstgids, by_firstgid, gid)
        record = tile_catalog[(atlas, tile_id)]
        remap[str(gid)] = asset_remap[record["asset_key"]]["runtime_gid"]
    props_manifest = _write_runtime_props(output, authoring, props)
    source_credits = _read_json(authoring / "credits.json", "authoring credits")
    packs = source_credits.get("packs")
    if not isinstance(packs, list) or not packs:
        raise CullError("authoring credits must declare licensed packs")
    _write_json(output / "credits.json", {
        "distribution_scope": "Only tiles and props referenced by this Claudeville map.",
        "generated_by": "tools/mapgen/tilemap_culler.py", "packs": packs, "schema_version": 1,
    })
    manifest = {
        "authoring_root_sha256": sha256((authoring / "atlas.json").read_bytes()).hexdigest(),
        "credits": "credits.json",
        "props": props_manifest, "schema_version": 1, "source_tmj_sha256": stable_source_sha256(source_path),
        "tile_asset_remap": asset_remap,
        "tile_gid_clear_mask": tiled_gid.ALL_FLAG_MASK,
        "tile_gid_flip_mask": tiled_gid.ORTHOGONAL_FLIP_MASK,
        "tile_gid_remap": remap, "tile_size": TILE_SIZE, "tilesets": pages,
    }
    _write_json(output / "runtime_manifest.json", manifest)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_tmj", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--authoring-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)
    try:
        manifest = cull_runtime_tilesets(args.source_tmj, args.output_root, authoring_root=args.authoring_root)
    except (OSError, CullError) as exc:
        parser.error(str(exc))
    print(f"Culled {len(manifest['tile_asset_remap'])} tiles into {args.output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
