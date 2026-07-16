"""Build the local source-aligned Modern Interiors v3 authoring profile."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL import __version__ as PILLOW_VERSION

try:
    from tools.mapgen import modern_interiors_v3_source as source
    from tools.mapgen.curate_modern_pixels_v2 import (
        DEFAULT_OUTPUT_ROOT as V2_OUTPUT_ROOT,
    )
except ModuleNotFoundError:  # Direct script execution.
    import modern_interiors_v3_source as source
    from curate_modern_pixels_v2 import DEFAULT_OUTPUT_ROOT as V2_OUTPUT_ROOT

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "output/claudeville/modern_interiors_v3"
MAX_ATLAS_SIZE = 4096
SUPPORTED_PILLOW_VERSION = "12.2.0"


class CurationV3Error(source.ModernInteriorsV3Error):
    """Raised when the v3 authoring profile cannot be built safely."""


OFFICE_GROUPS = {
    "counters_and_queue": [
        "prop.office.reception_desk", "prop.office.reception_corner",
        "prop.office.counter_cream_left", "prop.office.counter_cream_middle",
        "prop.office.counter_cream_right", "prop.office.counter_walnut_left",
        "prop.office.counter_walnut_middle", "prop.office.counter_walnut_right",
    ],
    "desks_and_tables": [
        "prop.office.computer_desk", "prop.office.conference_desk",
        "prop.office.conference_corner", "prop.office.table_light",
        "prop.office.table_walnut", "prop.office.table_walnut_medium",
        "prop.office.table_walnut_long",
    ],
    "chairs_and_seating": [
        "prop.office.chair_blue", "prop.office.chair_blue_side",
        "prop.office.chair_orange", "prop.office.chair_orange_side",
        "prop.office.manager_chair", "prop.office.armchair_ice",
        "prop.office.armchair_dark", "prop.office.sofa_dark",
    ],
    "storage_and_equipment": [
        "prop.office.filing_cabinet", "prop.office.display_cabinet",
        "prop.office.printer_station", "prop.office.copier",
        "prop.office.waste_bin", "prop.office.water_cooler",
    ],
    "computers_and_service": [
        "prop.office.monitor_blue", "prop.office.dual_monitors",
        "prop.office.laptop", "prop.office.phone", "prop.office.cash_register",
        "prop.office.printer", "prop.office.coffee_station",
    ],
}


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


def _tiled_relative(target: Path, start: Path) -> str:
    try:
        return os.path.relpath(target, start=start).replace("\\", "/")
    except ValueError:  # Windows cannot form a relative path across drive letters.
        return target.resolve().as_uri()


def _safe_name(source_id: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "_", source_id.casefold()).strip("_")
    if not value:
        raise CurationV3Error(f"unsafe source id: {source_id}")
    return value


def _properties(**values) -> list[dict]:
    result = []
    for name, value in values.items():
        item_type = "int" if isinstance(value, int) else "string"
        result.append({"name": name, "type": item_type, "value": value})
    return result


def _tile_contact_sheet(image: Image.Image, tile_source: source.TileSource) -> Image.Image:
    scale, left, top = 2, 48, 64
    width, height = image.width * scale + left, image.height * scale + top
    if width > MAX_ATLAS_SIZE or height > MAX_ATLAS_SIZE:
        raise CurationV3Error(f"coordinate sheet exceeds 4096px: {tile_source.source_id}")
    sheet = Image.new("RGBA", (width, height), (28, 30, 32, 255))
    enlarged = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    sheet.alpha_composite(enlarged, (left, top))
    font, draw = ImageFont.load_default(), ImageDraw.Draw(sheet)
    prefix = f"tile.interiors_v3.{tile_source.source_id}.rRRR.cCC"
    draw.text((8, 8), f"{tile_source.label} | {tile_source.source_id}", fill=(245, 230, 184, 255), font=font)
    draw.text((8, 26), prefix, fill=(182, 210, 206, 255), font=font)
    draw.text((8, 42), "Tiled ID = row * columns + column", fill=(180, 180, 180, 255), font=font)
    columns, rows = image.width // source.TILE_SIZE, image.height // source.TILE_SIZE
    cell = source.TILE_SIZE * scale
    for column in range(columns):
        draw.text((left + column * cell + 4, top - 15), f"c{column:02d}", fill=(224, 224, 216, 255), font=font)
    for row in range(rows):
        draw.text((4, top + row * cell + 11), f"r{row:03d}", fill=(224, 224, 216, 255), font=font)
    overlay = Image.new("RGBA", sheet.size, (0, 0, 0, 0))
    grid = ImageDraw.Draw(overlay)
    for column in range(columns + 1):
        x = left + column * cell
        grid.line((x, top, x, height - 1), fill=(250, 244, 220, 54))
    for row in range(rows + 1):
        y = top + row * cell
        grid.line((left, y, width - 1, y), fill=(250, 244, 220, 54))
    sheet.alpha_composite(overlay)
    enlarged.close()
    return sheet


def _read_tile_sources(root: Path, output: Path):
    records, tile_records, tiled_entries = [], [], []
    for tile_source in source.TILE_SOURCES:
        path = source.validate_source_path(root, tile_source.relative_path)
        image = source.open_png(path)
        source_size = image.size
        aligned_size = (
            math.ceil(image.width / source.TILE_SIZE) * source.TILE_SIZE,
            math.ceil(image.height / source.TILE_SIZE) * source.TILE_SIZE,
        )
        normalization = "none"
        tsj_image_path = path
        if image.size != aligned_size:
            aligned = Image.new("RGBA", aligned_size, (0, 0, 0, 0))
            aligned.alpha_composite(image)
            image.close()
            image = aligned
            normalization = "transparent-edge-padding-to-16px-grid"
        columns, rows = image.width // source.TILE_SIZE, image.height // source.TILE_SIZE
        source_digest = source.file_sha256(path)
        safe_name = _safe_name(tile_source.source_id)
        tsj_path = output / "tilesets" / f"{safe_name}.tsj"
        if normalization != "none":
            tsj_image_path = output / "derived/tiles" / f"{safe_name}.png"
            _write_png(tsj_image_path, image)
        contact_path = output / "contact_sheets/tiles" / f"{safe_name}.png"
        tiles = []
        for row in range(rows):
            for column in range(columns):
                crop = image.crop((column * 16, row * 16, column * 16 + 16, row * 16 + 16))
                if crop.getchannel("A").getbbox() is None:
                    crop.close()
                    continue
                asset_key = f"tile.interiors_v3.{tile_source.source_id}.r{row:03d}.c{column:02d}"
                tiled_id = row * columns + column
                record = {
                    "asset_key": asset_key, "group": tile_source.group,
                    "purposes": list(tile_source.purposes), "source_col": column,
                    "source_id": tile_source.source_id, "source_row": row,
                    "source_tiled_id": tiled_id,
                }
                tile_records.append(record)
                tiles.append({
                    "id": tiled_id,
                    "properties": _properties(asset_key=asset_key, source_col=column, source_row=row),
                })
                crop.close()
        contact = _tile_contact_sheet(image, tile_source)
        _write_png(contact_path, contact)
        contact.close()
        _write_json(tsj_path, {
            "columns": columns, "image": _tiled_relative(tsj_image_path, tsj_path.parent),
            "imageheight": image.height, "imagewidth": image.width,
            "name": f"claudeville_v3_{safe_name}",
            "properties": _properties(
                claudeville_asset_profile=source.PROFILE,
                shadow_variant=tile_source.shadow_variant,
                source_id=tile_source.source_id,
            ),
            "tilecount": columns * rows, "tiledversion": "1.10.2",
            "tileheight": 16, "tiles": tiles, "tilewidth": 16,
            "type": "tileset", "version": "1.10",
        })
        record = {
            "columns": columns, "contact_sheet": contact_path.relative_to(output).as_posix(),
            "group": tile_source.group, "label": tile_source.label,
            "nonempty_tile_count": len(tiles), "normalization": normalization,
            "purposes": list(tile_source.purposes),
            "relative_path": tile_source.relative_path, "rows": rows,
            "sha256": source_digest, "shadow_variant": tile_source.shadow_variant,
            "size": [image.width, image.height], "source_size": list(source_size),
            "source_id": tile_source.source_id,
            "tileset": tsj_path.relative_to(output).as_posix(),
        }
        records.append(record)
        tiled_entries.append(record["tileset"])
        image.close()
    return records, tile_records, tiled_entries


def _single_contact_sheet(root: Path, theme: source.ThemeSource, records: list[dict]) -> Image.Image:
    font, card_w, card_h, header = ImageFont.load_default(), 112, 160, 56
    columns = min(24, max(8, math.ceil(math.sqrt(len(records) * 1.5))))
    rows = math.ceil(len(records) / columns)
    width, height = columns * card_w, header + rows * card_h
    if width > MAX_ATLAS_SIZE or height > MAX_ATLAS_SIZE:
        raise CurationV3Error(f"singles contact sheet exceeds 4096px: {theme.key}")
    sheet = Image.new("RGBA", (width, height), (26, 29, 30, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((10, 8), f"{theme.label} singles | vendor number -> stable key", fill=(245, 230, 184, 255), font=font)
    draw.text((10, 27), f"prop.interiors_v3.{theme.key}.NNNN", fill=(182, 210, 206, 255), font=font)
    for index, record in enumerate(records):
        x, y = (index % columns) * card_w, header + (index // columns) * card_h
        draw.rectangle((x + 2, y + 2, x + card_w - 3, y + card_h - 3), fill=(47, 52, 52, 255), outline=(112, 108, 88, 255))
        path = source.validate_source_path(root, record["source"])
        image = source.open_png(path)
        sprite = image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST)
        sprite.thumbnail((104, 124), Image.Resampling.NEAREST)
        sheet.alpha_composite(sprite, (x + (card_w - sprite.width) // 2, y + 4 + (124 - sprite.height) // 2))
        draw.text((x + 6, y + 132), f"#{record['vendor_number']}  .{record['vendor_number']:04d}", fill=(235, 235, 226, 255), font=font)
        sprite.close()
        image.close()
    return sheet


def _read_props(root: Path, output: Path):
    records, tiled_tiles, by_theme = [], [], {theme.key: [] for theme in source.THEMES}
    max_width = max_height = 1
    omitted_empty = 0
    for theme, number, path in source.iter_prop_sources(root):
        image = source.open_png(path, allow_empty=True)
        if image.getchannel("A").getbbox() is None:
            image.close()
            omitted_empty += 1
            continue
        tiled_id = len(records)
        asset_key = f"prop.interiors_v3.{theme.key}.{number:04d}"
        relative = path.relative_to(root).as_posix()
        record = {
            "anchor": [0.5, 1.0], "asset_key": asset_key,
            "category": "interior_fixture", "depth_mode": "bottom_center",
            "display_scale": 1, "foot_offset": [image.width / 2, image.height],
            "native_size": [image.width, image.height], "pack": source.PACK_NAME,
            "purposes": list(theme.purposes), "shadow_variant": theme.shadow_variant,
            "source": relative, "source_sha256": source.file_sha256(path),
            "theme": theme.key, "tiled_tile_id": tiled_id, "vendor_number": number,
        }
        records.append(record)
        by_theme[theme.key].append(record)
        max_width, max_height = max(max_width, image.width), max(max_height, image.height)
        tiled_tiles.append({
            "id": tiled_id, "image": None, "imageheight": image.height, "imagewidth": image.width,
            "properties": _properties(
                asset_key=asset_key, shadow_variant=theme.shadow_variant,
                theme=theme.key, vendor_number=number,
            ),
        })
        image.close()
    collection_path = output / "collections/interiors_props.tsj"
    for item, record in zip(tiled_tiles, records, strict=True):
        item["image"] = _tiled_relative(root / Path(*Path(record["source"]).parts), collection_path.parent)
    _write_json(collection_path, {
        "columns": 0, "grid": {"height": 1, "orientation": "orthogonal", "width": 1},
        "margin": 0, "name": "claudeville_v3_interiors_props",
        "objectalignment": "bottom",
        "properties": _properties(claudeville_asset_profile=source.PROFILE),
        "spacing": 0, "tilecount": len(tiled_tiles), "tiledversion": "1.10.2",
        "tileheight": max_height, "tiles": tiled_tiles, "tilewidth": max_width,
        "type": "tileset", "version": "1.10",
    })
    contacts = {}
    for theme in source.THEMES:
        theme_records = by_theme[theme.key]
        if not theme_records:
            continue
        contact_path = output / "contact_sheets/singles" / f"{theme.key}.png"
        contact = _single_contact_sheet(root, theme, theme_records)
        _write_png(contact_path, contact)
        contact.close()
        contacts[theme.key] = contact_path.relative_to(output).as_posix()
    return records, collection_path.relative_to(output).as_posix(), contacts, omitted_empty


def _base_office_contact(output: Path) -> str | None:
    atlas_path, catalog_path = V2_OUTPUT_ROOT / "tiles/office.png", V2_OUTPUT_ROOT / "tiles.json"
    if not atlas_path.is_file() or not catalog_path.is_file():
        return None
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    records = sorted(
        (item for item in catalog.get("tiles", []) if item.get("atlas") == "office"),
        key=lambda item: item["atlas_index"],
    )
    if not records:
        return None
    card_w, card_h, columns, header = 80, 72, 24, 56
    rows = math.ceil(len(records) / columns)
    sheet = Image.new("RGBA", (columns * card_w, header + rows * card_h), (26, 29, 30, 255))
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default()
    draw.text((10, 8), "Base v15 Modern Office atlas | compact tile ID", fill=(245, 230, 184, 255), font=font)
    draw.text((10, 27), "Resolve IDs through ../modern_pixels_v2/tiles.json", fill=(182, 210, 206, 255), font=font)
    with Image.open(atlas_path) as atlas:
        atlas_columns = atlas.width // source.TILE_SIZE
        for index, record in enumerate(records):
            x, y = (index % columns) * card_w, header + (index // columns) * card_h
            draw.rectangle((x + 2, y + 2, x + card_w - 3, y + card_h - 3), fill=(47, 52, 52, 255), outline=(112, 108, 88, 255))
            tile_id = record["atlas_index"]
            source_x, source_y = (tile_id % atlas_columns) * 16, (tile_id // atlas_columns) * 16
            tile = atlas.crop((source_x, source_y, source_x + 16, source_y + 16))
            tile = tile.resize((32, 32), Image.Resampling.NEAREST)
            sheet.alpha_composite(tile, (x + 24, y + 4))
            kind = "F" if record["source_id"] == "office_furniture" else "R"
            draw.text((x + 5, y + 39), f"#{tile_id:03d} {kind}", fill=(235, 235, 226, 255), font=font)
            draw.text((x + 5, y + 54), f"{record['source_x']:03},{record['source_y']:03}", fill=(180, 202, 200, 255), font=font)
            tile.close()
    path = output / "contact_sheets/base_v15_office.png"
    _write_png(path, sheet)
    sheet.close()
    return path.relative_to(output).as_posix()


def _selection_index(output: Path, sources: list[dict], props: list[dict], contacts: dict) -> dict:
    by_theme = {}
    for theme in source.THEMES:
        source_record = next(item for item in sources if item["source_id"] == f"theme.{theme.key}")
        theme_props = [item for item in props if item["theme"] == theme.key]
        by_theme[theme.key] = {
            "contact_sheet": contacts.get(theme.key), "label": theme.label,
            "prop_count": len(theme_props), "prop_key_pattern": f"prop.interiors_v3.{theme.key}.NNNN",
            "purposes": list(theme.purposes), "tile_contact_sheet": source_record["contact_sheet"],
            "shadow_variant": theme.shadow_variant,
            "tile_key_pattern": f"tile.interiors_v3.theme.{theme.key}.rRRR.cCC",
            "tileset": source_record["tileset"],
        }
    room = {
        item["source_id"].removeprefix("room."): {
            "contact_sheet": item["contact_sheet"], "label": item["label"],
            "tile_key_pattern": f"tile.interiors_v3.{item['source_id']}.rRRR.cCC",
            "tileset": item["tileset"],
        }
        for item in sources if item["group"] == "room_builder"
    }
    base = _tiled_relative(V2_OUTPUT_ROOT, output)
    office_contact = _base_office_contact(output)
    return {
        "base_v15": {
            "catalog": f"{base}/catalog.json", "office_contact_sheet": office_contact,
            "office_groups": OFFICE_GROUPS,
            "office_tile_catalog": f"{base}/tiles.json",
            "office_tileset": f"{base}/tiles/office.tsj",
            "profile": "claudeville-modern-pixels-v2",
            "tile_browse_tags": ["plants", "queue", "counter", "desk", "chair", "cabinet", "computer"],
        },
        "profile": source.PROFILE, "room_builder": room, "schema_version": 3,
        "themes": by_theme,
        "tiled_map_property": {"name": "claudeville_asset_profile", "type": "string", "value": source.PROFILE},
    }


def curate_profile(source_root: Path = source.DEFAULT_SOURCE_ROOT,
                   output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict:
    """Write a deterministic local-only authoring profile without vendor copies."""
    if PILLOW_VERSION != SUPPORTED_PILLOW_VERSION:
        raise CurationV3Error(f"unsupported Pillow {PILLOW_VERSION}; expected {SUPPORTED_PILLOW_VERSION}")
    root = Path(source_root).expanduser().resolve(strict=True)
    output = Path(output_root).expanduser().resolve(strict=False)
    if output == root or root in output.parents or output in root.parents:
        raise CurationV3Error("source and output roots must be separate directories")
    evidence = source.validate_pack(root)
    output.mkdir(parents=True, exist_ok=True)
    sources, tiles, tilesets = _read_tile_sources(root, output)
    props, collection, contacts, omitted_empty = _read_props(root, output)
    index = _selection_index(output, sources, props, contacts)
    _write_json(output / "catalog.json", {
        "omitted_empty_prop_count": omitted_empty, "pack": evidence,
        "profile": source.PROFILE, "props": props,
        "schema_version": 3, "tile_size": 16, "tiles": tiles,
        "tilesets": sources,
    })
    _write_json(output / "selection_index.json", index)
    _write_json(output / "credits.json", {
        "distribution_allowed": False,
        "distribution_scope": "Local authoring references only; ship only used runtime atlases.",
        "generated_by": "tools/mapgen/curate_modern_interiors_v3.py",
        "packs": [evidence], "schema_version": 3,
    })
    profile = {
        "catalog": "catalog.json", "credits": "credits.json",
        "extends": index["base_v15"], "profile": source.PROFILE,
        "prop_collection": collection, "schema_version": 3,
        "selection_index": "selection_index.json", "tile_size": 16,
        "tilesets": tilesets,
        "used_assets_contract": {"prop_asset_keys": "string[]", "tile_asset_keys": "string[]"},
    }
    _write_json(output / "profile.json", profile)
    profile["profile_sha256"] = sha256((output / "profile.json").read_bytes()).hexdigest()
    return profile


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=source.DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)
    try:
        result = curate_profile(args.source_root, args.output_root)
    except (OSError, CurationV3Error, source.ModernInteriorsV3Error) as exc:
        parser.error(str(exc))
    print(f"Curated {result['profile']} into {args.output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
