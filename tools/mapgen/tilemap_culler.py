"""Cull the Claudeville v2 authoring palette into runtime-only tile and prop atlases."""

from __future__ import annotations

import argparse
import bisect
import json
from hashlib import sha256
from pathlib import Path

from PIL import Image

try:
    from tools.mapgen import curate_modern_interiors_v3 as interiors_v3_curator
    from tools.mapgen import curate_modern_pixels_v2 as v2_curator
    from tools.mapgen import modern_interiors_v3_source, tiled_gid
    from tools.mapgen import tilemap_runtime_support as runtime_support
except ModuleNotFoundError:  # Direct ``python tools/mapgen/cull_modern_pixels_v2.py``.
    import curate_modern_interiors_v3 as interiors_v3_curator
    import curate_modern_pixels_v2 as v2_curator
    import modern_interiors_v3_source
    import tiled_gid
    import tilemap_runtime_support as runtime_support

INTERIORS_V3_OUTPUT_ROOT, DEFAULT_OUTPUT_ROOT, MAX_ATLAS_SIZE, TILE_SIZE = interiors_v3_curator.DEFAULT_OUTPUT_ROOT, v2_curator.DEFAULT_OUTPUT_ROOT, v2_curator.MAX_ATLAS_SIZE, v2_curator.TILE_SIZE
CurationError, atlas_dimensions = v2_curator.CurationError, v2_curator.atlas_dimensions

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SIZE = (176, 96)
FLIP_MASK = tiled_gid.GID_MASK
BASE_TILESETS = ("terrain", "town", "office", "interiors")
V3_TILESETS = {"room_arched_entryways", "room_floors", "room_walls"}
V3_PROFILE = "claudeville-modern-interiors-v3"
GENERATED_ROOT_FILES = ("credits.json", "props.json", "props.png", "runtime_manifest.json")
GENERATED_TILESETS = (*BASE_TILESETS, "interiors_v3")
GENERATED_PATHS = (*GENERATED_ROOT_FILES, *(f"tiles/{key}.{suffix}"
    for key in GENERATED_TILESETS for suffix in ("png", "tsj")))


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
        if key not in {*BASE_TILESETS, "interiors_props", *V3_TILESETS}:
            raise CullError("TMJ may reference only approved v2 and Modern Interiors v3 tilesets")
        result.append((entry["firstgid"], key))
    if len({firstgid for firstgid, _ in result}) != len(result):
        raise CullError("TMJ tileset firstgid values must be unique")
    keys = [key for _, key in result]
    if len(keys) != len(set(keys)):
        raise CullError("TMJ may reference each approved tileset only once")
    if _property_value(source.get("properties"), "authoring_profile") == V3_PROFILE \
            and "interiors" in keys:
        raise CullError("Modern Interiors v3 maps may not reference the legacy interiors tileset")
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


def _property_value(properties, name: str):
    if isinstance(properties, dict):
        return properties.get(name)
    if isinstance(properties, list):
        for item in properties:
            if isinstance(item, dict) and item.get("name") == name:
                return item.get("value")
    return None


def _object_asset_key(properties) -> str | None:
    value = _property_value(properties, "asset_key")
    return value if isinstance(value, str) and value else None


def _source_gid(firstgids: list[int], tilesets: dict[int, str], gid: int) -> tuple[str, int]:
    firstgid = firstgids[bisect.bisect_right(firstgids, gid) - 1]
    return tilesets[firstgid], gid - firstgid


def _uses_v3(source: dict) -> bool:
    if any(key in V3_TILESETS for _, key in _map_tilesets(source)):
        return True
    return any(
        (key := _object_asset_key(obj.get("properties"))) is not None
        and key.startswith("prop.interiors_v3.")
        for layer in _walk_layers(source.get("layers", []))
        if layer.get("type") == "objectgroup"
        for obj in (layer.get("objects") if isinstance(layer.get("objects"), list) else ()) if isinstance(obj, dict)
    )


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


def _v3_props(authoring: Path) -> dict[str, dict]:
    catalog = _read_json(authoring / "catalog.json", "Modern Interiors v3 catalog")
    if catalog.get("profile") != modern_interiors_v3_source.PROFILE or \
            catalog.get("schema_version") != 3:
        raise CullError("Modern Interiors v3 catalog has the wrong profile")
    records = catalog.get("props")
    if not isinstance(records, list):
        raise CullError("Modern Interiors v3 catalog is missing props")
    result = {
        item.get("asset_key"): item for item in records
        if isinstance(item, dict) and isinstance(item.get("asset_key"), str)
    }
    if len(result) != len(records):
        raise CullError("Modern Interiors v3 prop catalog contains malformed duplicates")
    return result


def _v3_tiles(authoring: Path) -> dict[tuple[str, int], dict]:
    catalog = _read_json(authoring / "catalog.json", "Modern Interiors v3 catalog")
    if catalog.get("profile") != modern_interiors_v3_source.PROFILE or \
            catalog.get("schema_version") != 3:
        raise CullError("Modern Interiors v3 catalog has the wrong profile")
    sources = catalog.get("tilesets")
    tiles = catalog.get("tiles")
    if not isinstance(sources, list) or not isinstance(tiles, list):
        raise CullError("Modern Interiors v3 catalog is missing tiles")
    source_records = {
        item.get("source_id"): item for item in sources
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
    }
    result = {}
    for item in tiles:
        if not isinstance(item, dict) or item.get("source_id") not in source_records:
            raise CullError("Modern Interiors v3 tile record is malformed")
        source = source_records[item["source_id"]]
        tileset = Path(str(source.get("tileset", ""))).stem
        tile_id = item.get("source_tiled_id")
        if tileset not in V3_TILESETS or not isinstance(tile_id, int):
            continue
        record = dict(item)
        record.update({"atlas": "interiors_v3", "atlas_index": tile_id,
                       "source_columns": source.get("columns"),
                       "source_relative_path": source.get("relative_path"),
                       "source_sha256": source.get("sha256")})
        key = tileset, tile_id
        if key in result:
            raise CullError(f"duplicate Modern Interiors v3 tile: {key}")
        result[key] = record
    return result


def _validate_requested_props(
    authoring: Path, v3_authoring: Path | None, requested: list[str]
) -> tuple[dict, dict]:
    frames = _read_json(authoring / "props.json", "authoring props metadata").get("frames")
    if not isinstance(frames, dict):
        raise CullError("authoring props metadata is missing frames")
    v3 = _v3_props(v3_authoring) if v3_authoring is not None else {}
    missing = sorted(set(requested) - set(frames) - set(v3))
    if missing:
        raise CullError(f"TMJ object assets are missing from props in approved catalogs: {missing}")
    return frames, v3


def _write_runtime_tiles(
    output: Path, authoring: Path, v3_source: Path | None, selected: dict[str, dict],
):
    atlas_meta = _read_json(authoring / "atlas.json", "authoring atlas metadata")
    pages = {page.get("key"): page for page in atlas_meta.get("atlases", []) if isinstance(page, dict)}
    page_order = (*BASE_TILESETS, "interiors_v3")
    groups = {key: [] for key in page_order}
    for record in selected.values():
        groups[record["atlas"]].append(record)
    runtime_pages, asset_remap, firstgid = [], {}, 1
    for key in page_order:
        records = sorted(groups[key], key=lambda item: (
            item["atlas_index"] if key != "interiors_v3" else item["asset_key"]
        ))
        if not records:
            continue
        width, height, columns = atlas_dimensions(len(records))
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        source_image = None
        v3_images = {}
        try:
            if key != "interiors_v3":
                source_page = pages.get(key)
                if source_page is None:
                    raise CullError(f"authoring atlas page is missing: {key}")
                with Image.open(_contained_file(authoring, source_page.get("image"), f"authoring {key} atlas")) as opened:
                    source_image = opened.convert("RGBA")
            for new_id, record in enumerate(records):
                if key == "interiors_v3":
                    if v3_source is None:
                        raise CullError("Modern Interiors v3 tile source was not preflighted")
                    relative = record.get("source_relative_path")
                    if relative not in v3_images:
                        path = modern_interiors_v3_source.validate_source_path(v3_source, relative)
                        if modern_interiors_v3_source.file_sha256(path) != record.get(
                            "source_sha256"
                        ):
                            raise CullError(
                                f"Modern Interiors v3 tile hash changed: {record['asset_key']}"
                            )
                        v3_images[relative] = modern_interiors_v3_source.open_png(path)
                    source = v3_images[relative]
                    old_x = record["source_col"] * TILE_SIZE
                    old_y = record["source_row"] * TILE_SIZE
                else:
                    source = source_image
                    old_id = record["atlas_index"]
                    old_x = (old_id % source_page["columns"]) * TILE_SIZE
                    old_y = (old_id // source_page["columns"]) * TILE_SIZE
                destination = (new_id % columns * TILE_SIZE, new_id // columns * TILE_SIZE)
                image.paste(
                    source.crop((old_x, old_y, old_x + TILE_SIZE, old_y + TILE_SIZE)),
                    destination,
                )
                asset_remap[record["asset_key"]] = {
                    "atlas": key, "runtime_gid": firstgid + new_id,
                    "tile_id": new_id,
                }
        finally:
            if source_image is not None:
                source_image.close()
            for opened in v3_images.values():
                opened.close()
        tile_dir = output / "tiles"
        tile_dir.mkdir(parents=True, exist_ok=True)
        image_path = tile_dir / f"{key}.png"
        tileset_path = tile_dir / f"{key}.tsj"
        _write_png(image_path, image)
        _write_json(tileset_path, {"columns": columns, "image": image_path.name, "imageheight": height, "imagewidth": width, "name": f"claudeville_v2_runtime_{key}", "tilecount": len(records), "tileheight": TILE_SIZE, "tilewidth": TILE_SIZE, "type": "tileset", "version": "1.10"})
        runtime_pages.append({"firstgid": firstgid, "image": f"tiles/{image_path.name}", "key": key, "tile_count": len(records), "tileset": f"tiles/{tileset_path.name}"})
        firstgid += len(records)
    return runtime_pages, asset_remap


def _write_runtime_props(
    output: Path, authoring: Path, v3_authoring: Path | None, v3_source: Path | None,
    requested: list[str],
):
    frames, v3 = _validate_requested_props(authoring, v3_authoring, requested)
    source_image = None
    if any(key in frames for key in requested):
        with Image.open(authoring / "props.png") as opened:
            source_image = opened.convert("RGBA")
    images = []
    try:
        for key in requested:
            if key in frames:
                frame = frames[key].get("frame") if isinstance(frames[key], dict) else None
                if not isinstance(frame, dict) or not all(
                    isinstance(frame.get(axis), int) for axis in ("x", "y", "w", "h")
                ):
                    raise CullError(f"authoring prop frame is malformed: {key}")
                images.append((key, source_image.crop((
                    frame["x"], frame["y"], frame["x"] + frame["w"],
                    frame["y"] + frame["h"],
                ))))
                continue
            record = v3[key]
            if v3_source is None:
                raise CullError("Modern Interiors v3 prop source was not preflighted")
            path = modern_interiors_v3_source.validate_source_path(
                v3_source, record.get("source")
            )
            if modern_interiors_v3_source.file_sha256(path) != record.get("source_sha256"):
                raise CullError(f"Modern Interiors v3 prop hash changed: {key}")
            images.append((key, modern_interiors_v3_source.open_png(path)))
    finally:
        if source_image is not None:
            source_image.close()
    if not images:
        return None
    try:
        width, height, placements = _pack_props(images)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        frames_out = {}
        for key, prop, x, y in placements:
            image.alpha_composite(prop, (x, y))
            frames_out[key] = {"frame": {"h": prop.height, "w": prop.width, "x": x, "y": y}, "rotated": False, "spriteSourceSize": {"h": prop.height, "w": prop.width, "x": 0, "y": 0}, "sourceSize": {"h": prop.height, "w": prop.width}, "trimmed": False}
        _write_png(output / "props.png", image)
        _write_json(output / "props.json", {"frames": frames_out, "meta": {"app": "Claudeville Modern Pixels v3 runtime", "format": "RGBA8888", "image": "props.png", "scale": "1", "size": {"h": height, "w": width}}})
        image.close()
    finally:
        for _, prop in images:
            prop.close()
    return {"asset_keys": requested, "data": "props.json", "image": "props.png", "key": "claudeville-v2-props"}


def cull_runtime_tilesets(
    source_tmj: Path, output_root: Path, *, authoring_root: Path = DEFAULT_OUTPUT_ROOT,
    interiors_v3_authoring_root: Path = INTERIORS_V3_OUTPUT_ROOT,
    interiors_v3_source_root: Path = modern_interiors_v3_source.DEFAULT_SOURCE_ROOT,
) -> dict:
    """Return a deterministic compact runtime asset manifest for one hand-authored TMJ."""
    source_path = Path(source_tmj).expanduser().resolve(strict=True)
    authoring = Path(authoring_root).expanduser().resolve(strict=True)
    output = Path(output_root).expanduser().resolve(strict=False)
    source = _read_json(source_path, "TMJ source")
    if (source.get("width"), source.get("height"), source.get("tilewidth"), source.get("tileheight"), source.get("infinite")) != (*EXPECTED_SIZE, TILE_SIZE, TILE_SIZE, False):
        raise CullError("TMJ must be a finite 176x96 native-16px map")
    v3_authoring = v3_source = v3_pack = None
    protected = [authoring]
    if _uses_v3(source):
        try:
            v3_authoring = Path(interiors_v3_authoring_root).expanduser().resolve(strict=True)
            v3_source = Path(interiors_v3_source_root).expanduser().resolve(strict=True)
            protected.extend((v3_authoring, v3_source))
            v3_pack = modern_interiors_v3_source.validate_pack(v3_source)
        except (OSError, modern_interiors_v3_source.ModernInteriorsV3Error) as exc:
            raise CullError(f"Modern Interiors v3 preflight failed: {exc}") from exc
    if source_path.suffix.lower() != ".tmj" or not all(path.is_dir() for path in protected) \
            or any(output == path or path in output.parents or output in path.parents for path in protected):
        raise CullError("TMJ source and runtime output must be separate valid paths")
    tile_records = _read_json(authoring / "tiles.json", "authoring tile catalog").get("tiles")
    if not isinstance(tile_records, list):
        raise CullError("authoring tile catalog is missing tiles")
    tile_catalog = {(record.get("atlas"), record.get("atlas_index")): record for record in tile_records if isinstance(record, dict)}
    if v3_authoring is not None:
        tile_catalog.update(_v3_tiles(v3_authoring))
    selected, source_gids, props = _selected_assets(source, tile_catalog)
    if not selected:
        raise CullError("TMJ must reference at least one curated tile")
    _validate_requested_props(authoring, v3_authoring, props)
    atlas_metadata = _read_json(authoring / "atlas.json", "authoring atlas metadata")
    prop_catalog = _read_json(authoring / "catalog.json", "authoring prop catalog")
    source_credits = _read_json(authoring / "credits.json", "authoring credits")
    try:
        packs = runtime_support.used_pack_credits(
            source_credits, atlas_metadata, prop_catalog, selected.values(), props, v3_pack,
        )
    except runtime_support.RuntimeSupportError as exc:
        raise CullError(str(exc)) from exc
    v3_catalog_sha = sha256((v3_authoring / "catalog.json").read_bytes()).hexdigest() \
        if v3_authoring is not None else None
    try:
        with runtime_support.staged_runtime(output, GENERATED_PATHS) as staging:
            pages, asset_remap = _write_runtime_tiles(staging, authoring, v3_source, selected)
            props_manifest = _write_runtime_props(staging, authoring, v3_authoring, v3_source, props)
            tilesets = _map_tilesets(source)
            firstgids, by_firstgid = [item[0] for item in tilesets], dict(tilesets)
            remap = {}
            for gid in source_gids:
                atlas, tile_id = _source_gid(firstgids, by_firstgid, gid)
                record = tile_catalog[(atlas, tile_id)]
                remap[str(gid)] = asset_remap[record["asset_key"]]["runtime_gid"]
            _write_json(staging / "credits.json", {
                "distribution_scope": "Only tiles and props referenced by this Claudeville map.",
                "generated_by": "tools/mapgen/tilemap_culler.py", "packs": packs,
                "schema_version": 1,
            })
            manifest = {
                "authoring_root_sha256": sha256((authoring / "atlas.json").read_bytes()).hexdigest(),
                "credits": "credits.json", "props": props_manifest, "schema_version": 1,
                "source_tmj_sha256": stable_source_sha256(source_path),
                "tile_asset_remap": asset_remap,
                "tile_gid_clear_mask": tiled_gid.ALL_FLAG_MASK,
                "tile_gid_flip_mask": tiled_gid.ORTHOGONAL_FLIP_MASK,
                "tile_gid_remap": remap, "tile_size": TILE_SIZE, "tilesets": pages,
            }
            if v3_catalog_sha is not None:
                manifest["interiors_v3_catalog_sha256"] = v3_catalog_sha
            _write_json(staging / "runtime_manifest.json", manifest)
    except modern_interiors_v3_source.ModernInteriorsV3Error as exc:
        raise CullError(f"Modern Interiors v3 source failed: {exc}") from exc
    except runtime_support.RuntimeSupportError as exc:
        raise CullError(f"runtime transaction failed: {exc}") from exc
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
