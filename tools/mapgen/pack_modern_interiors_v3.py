"""Pack only the Modern Interiors v3 assets selected by a Claudeville map."""

from __future__ import annotations

import argparse
import json
import math
from hashlib import sha256
from pathlib import Path

from PIL import Image

try:
    from tools.mapgen import modern_interiors_v3_source as source
    from tools.mapgen.curate_modern_interiors_v3 import (
        DEFAULT_OUTPUT_ROOT as AUTHORING_ROOT,
    )
except ModuleNotFoundError:  # Direct script execution.
    import modern_interiors_v3_source as source
    from curate_modern_interiors_v3 import DEFAULT_OUTPUT_ROOT as AUTHORING_ROOT

MAX_ATLAS_SIZE = 4096
TILE_SIZE = 16
MAX_TILES_PER_PAGE = (MAX_ATLAS_SIZE // TILE_SIZE) ** 2


class RuntimePackError(source.ModernInteriorsV3Error):
    """Raised when a used-assets request cannot be packed safely."""


def _read_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise RuntimePackError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimePackError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise RuntimePackError(f"{label} root must be an object")
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_png(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    image.save(temporary, format="PNG", compress_level=9, optimize=False)
    temporary.replace(path)


def _asset_list(request: dict, name: str) -> list[str]:
    values = request.get(name)
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        raise RuntimePackError(f"{name} must be a string array")
    if len(values) != len(set(values)):
        raise RuntimePackError(f"{name} must not contain duplicates")
    return sorted(values)


def _atlas_dimensions(count: int) -> tuple[int, int, int]:
    if not isinstance(count, int) or isinstance(count, bool) or count < 1 or count > MAX_TILES_PER_PAGE:
        raise RuntimePackError("runtime tile page must contain 1..65,536 tiles")
    columns = math.isqrt(count - 1) + 1
    rows = math.ceil(count / columns)
    return columns * TILE_SIZE, rows * TILE_SIZE, columns


def _validate_catalog(catalog: dict, evidence: dict) -> tuple[dict, dict, dict]:
    if catalog.get("profile") != source.PROFILE or catalog.get("schema_version") != 3:
        raise RuntimePackError("authoring catalog is not the v3 Modern Interiors profile")
    pack = catalog.get("pack")
    if not isinstance(pack, dict) or pack.get("selected_fingerprints") != evidence["selected_fingerprints"]:
        raise RuntimePackError("authoring catalog source fingerprint does not match the paid pack")
    sources = catalog.get("tilesets")
    tiles, props = catalog.get("tiles"), catalog.get("props")
    if not isinstance(sources, list) or not isinstance(tiles, list) or not isinstance(props, list):
        raise RuntimePackError("authoring catalog asset arrays are malformed")
    source_by_id = {item.get("source_id"): item for item in sources if isinstance(item, dict)}
    tile_by_key = {item.get("asset_key"): item for item in tiles if isinstance(item, dict)}
    prop_by_key = {item.get("asset_key"): item for item in props if isinstance(item, dict)}
    if len(source_by_id) != len(sources) or len(tile_by_key) != len(tiles) or len(prop_by_key) != len(props):
        raise RuntimePackError("authoring catalog contains duplicate or malformed asset records")
    return source_by_id, tile_by_key, prop_by_key


def _load_selected_tiles(root: Path, keys: list[str], by_key: dict, sources: dict):
    missing = sorted(set(keys) - set(by_key))
    if missing:
        raise RuntimePackError(f"unknown tile asset keys: {missing}")
    opened, source_images = [], {}
    for key in keys:
        record = by_key[key]
        source_record = sources.get(record.get("source_id"))
        if not isinstance(source_record, dict):
            raise RuntimePackError(f"tile source is missing for {key}")
        source_id = record["source_id"]
        if source_id not in source_images:
            path = source.validate_source_path(root, source_record.get("relative_path"))
            if source.file_sha256(path) != source_record.get("sha256"):
                raise RuntimePackError(f"tile source hash changed: {source_id}")
            source_images[source_id] = source.open_png(path)
        image = source_images[source_id]
        x, y = record.get("source_col"), record.get("source_row")
        if not isinstance(x, int) or not isinstance(y, int) or x < 0 or y < 0:
            raise RuntimePackError(f"tile coordinates are malformed: {key}")
        tile = image.crop((x * TILE_SIZE, y * TILE_SIZE, x * TILE_SIZE + TILE_SIZE, y * TILE_SIZE + TILE_SIZE))
        if tile.getchannel("A").getbbox() is None:
            tile.close()
            raise RuntimePackError(f"selected tile is empty: {key}")
        opened.append((key, tile, source_id, x, y))
    for image in source_images.values():
        image.close()
    return opened


def _load_selected_props(root: Path, keys: list[str], by_key: dict):
    missing = sorted(set(keys) - set(by_key))
    if missing:
        raise RuntimePackError(f"unknown prop asset keys: {missing}")
    opened = []
    for key in keys:
        record = by_key[key]
        path = source.validate_source_path(root, record.get("source"))
        if source.file_sha256(path) != record.get("source_sha256"):
            raise RuntimePackError(f"prop source hash changed: {key}")
        image = source.open_png(path)
        if image.width + 4 > MAX_ATLAS_SIZE or image.height + 4 > MAX_ATLAS_SIZE:
            image.close()
            raise RuntimePackError(f"prop exceeds 4096px runtime limit: {key}")
        opened.append((key, image, record))
    return opened


def _write_tiles(output: Path, selected: list[tuple]):
    pages, remap = [], {}
    for page_number, start in enumerate(range(0, len(selected), MAX_TILES_PER_PAGE)):
        records = selected[start:start + MAX_TILES_PER_PAGE]
        width, height, columns = _atlas_dimensions(len(records))
        atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        tiled_tiles = []
        for tile_id, (key, tile, source_id, column, row) in enumerate(records):
            atlas.alpha_composite(tile, ((tile_id % columns) * 16, (tile_id // columns) * 16))
            remap[key] = {
                "page": page_number, "runtime_tile_id": tile_id,
                "source_col": column, "source_id": source_id, "source_row": row,
            }
            tiled_tiles.append({
                "id": tile_id,
                "properties": [{"name": "asset_key", "type": "string", "value": key}],
            })
        page_key = f"interiors_v3_tiles_{page_number:02d}"
        image_path = output / "tiles" / f"{page_key}.png"
        tsj_path = output / "tiles" / f"{page_key}.tsj"
        _write_png(image_path, atlas)
        _write_json(tsj_path, {
            "columns": columns, "image": image_path.name,
            "imageheight": height, "imagewidth": width, "name": page_key,
            "properties": [{"name": "claudeville_asset_profile", "type": "string", "value": source.PROFILE}],
            "tilecount": len(records), "tiledversion": "1.10.2",
            "tileheight": 16, "tiles": tiled_tiles, "tilewidth": 16,
            "type": "tileset", "version": "1.10",
        })
        pages.append({
            "height": height, "image": image_path.relative_to(output).as_posix(),
            "key": page_key, "sha256": sha256(image_path.read_bytes()).hexdigest(),
            "tile_count": len(records), "tileset": tsj_path.relative_to(output).as_posix(),
            "width": width,
        })
        atlas.close()
    return pages, remap


def _fit_props(records: list[tuple], width: int):
    x = y = 2
    row_height, placements = 0, []
    for key, image, record in records:
        if image.width + 4 > width:
            return None
        if x + image.width + 2 > width:
            x, y, row_height = 2, y + row_height + 2, 0
        if y + image.height + 2 > MAX_ATLAS_SIZE:
            return None
        placements.append((key, image, record, x, y))
        x += image.width + 2
        row_height = max(row_height, image.height)
    return y + row_height + 2, placements


def _prop_pages(records: list[tuple]):
    if not records:
        return []
    for width in (256, 512, 1024, 2048, 4096):
        fitted = _fit_props(records, width)
        if fitted is not None:
            height, placements = fitted
            return [(width, height, placements)]
    pages, remaining = [], list(records)
    while remaining:
        x = y = 2
        row_height, placements, consumed = 0, [], 0
        for key, image, record in remaining:
            if x + image.width + 2 > MAX_ATLAS_SIZE:
                x, y, row_height = 2, y + row_height + 2, 0
            if y + image.height + 2 > MAX_ATLAS_SIZE:
                break
            placements.append((key, image, record, x, y))
            x += image.width + 2
            row_height = max(row_height, image.height)
            consumed += 1
        if not consumed:
            raise RuntimePackError("prop atlas cannot make progress within 4096px")
        pages.append((MAX_ATLAS_SIZE, y + row_height + 2, placements))
        remaining = remaining[consumed:]
    return pages


def _write_props(output: Path, selected: list[tuple]):
    pages, remap = [], {}
    for page_number, (width, height, placements) in enumerate(_prop_pages(selected)):
        atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        frames = {}
        for key, image, record, x, y in placements:
            atlas.alpha_composite(image, (x, y))
            frame = {"h": image.height, "w": image.width, "x": x, "y": y}
            frames[key] = {
                "frame": frame, "rotated": False,
                "sourceSize": {"h": image.height, "w": image.width}, "trimmed": False,
            }
            remap[key] = {
                "anchor": record["anchor"], "frame": frame,
                "foot_offset": record["foot_offset"], "page": page_number,
            }
        page_key = f"interiors_v3_props_{page_number:02d}"
        image_path = output / "props" / f"{page_key}.png"
        data_path = output / "props" / f"{page_key}.json"
        _write_png(image_path, atlas)
        _write_json(data_path, {
            "frames": frames,
            "meta": {"format": "RGBA8888", "image": image_path.name,
                     "profile": source.PROFILE, "scale": "1", "size": {"h": height, "w": width}},
        })
        pages.append({
            "asset_count": len(placements), "data": data_path.relative_to(output).as_posix(),
            "height": height, "image": image_path.relative_to(output).as_posix(),
            "key": page_key, "sha256": sha256(image_path.read_bytes()).hexdigest(), "width": width,
        })
        atlas.close()
    return pages, remap


def pack_runtime(used_assets: Path, output_root: Path, *,
                 source_root: Path = source.DEFAULT_SOURCE_ROOT,
                 authoring_root: Path = AUTHORING_ROOT) -> dict:
    """Create deterministic, used-only runtime pages bounded by 4096px."""
    root = Path(source_root).expanduser().resolve(strict=True)
    authoring = Path(authoring_root).expanduser().resolve(strict=True)
    output = Path(output_root).expanduser().resolve(strict=False)
    if output in (root, authoring) or root in output.parents or authoring in output.parents or output in root.parents or output in authoring.parents:
        raise RuntimePackError("source, authoring, and runtime roots must be separate")
    request_path = Path(used_assets).expanduser().resolve(strict=True)
    request = _read_json(request_path, "used-assets request")
    if request.get("profile") != source.PROFILE:
        raise RuntimePackError(f"used-assets profile must be {source.PROFILE}")
    tile_keys = _asset_list(request, "tile_asset_keys")
    prop_keys = _asset_list(request, "prop_asset_keys")
    if not tile_keys and not prop_keys:
        raise RuntimePackError("used-assets request must select at least one asset")
    evidence = source.validate_pack(root)
    catalog_path = authoring / "catalog.json"
    catalog = _read_json(catalog_path, "authoring catalog")
    sources, tile_by_key, prop_by_key = _validate_catalog(catalog, evidence)
    selected_tiles = _load_selected_tiles(root, tile_keys, tile_by_key, sources)
    selected_props = _load_selected_props(root, prop_keys, prop_by_key)
    output.mkdir(parents=True, exist_ok=True)
    tile_pages, tile_remap = _write_tiles(output, selected_tiles) if selected_tiles else ([], {})
    prop_pages, prop_remap = _write_props(output, selected_props)
    for _, image, *_ in selected_tiles:
        image.close()
    for _, image, _ in selected_props:
        image.close()
    credits = {
        "distribution_scope": "Only Modern Interiors pixels selected by this Claudeville map.",
        "generated_by": "tools/mapgen/pack_modern_interiors_v3.py",
        "packs": [evidence], "schema_version": 3,
    }
    _write_json(output / "credits.json", credits)
    manifest = {
        "authoring_catalog_sha256": sha256(catalog_path.read_bytes()).hexdigest(),
        "credits": "credits.json", "profile": source.PROFILE,
        "prop_asset_remap": prop_remap, "prop_pages": prop_pages,
        "schema_version": 3, "tile_asset_remap": tile_remap,
        "tile_pages": tile_pages, "tile_size": TILE_SIZE,
        "used_assets_sha256": sha256(request_path.read_bytes()).hexdigest(),
    }
    _write_json(output / "runtime_manifest.json", manifest)
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("used_assets", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--source-root", type=Path, default=source.DEFAULT_SOURCE_ROOT)
    parser.add_argument("--authoring-root", type=Path, default=AUTHORING_ROOT)
    args = parser.parse_args(argv)
    try:
        result = pack_runtime(args.used_assets, args.output_root,
                              source_root=args.source_root, authoring_root=args.authoring_root)
    except (OSError, RuntimePackError, source.ModernInteriorsV3Error) as exc:
        parser.error(str(exc))
    count = len(result["tile_asset_remap"]) + len(result["prop_asset_remap"])
    print(f"Packed {count} used Modern Interiors assets into {args.output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
