"""Render a deterministic review PNG from a compiled Claudeville tilemap."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

try:
    from tools.mapgen import tiled_gid
except ModuleNotFoundError:  # Direct script imports.
    import tiled_gid  # type: ignore[no-redef]

VISUAL_WIDTH, VISUAL_HEIGHT, TILE_SIZE = 176, 96, 16


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid preview metadata: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"preview metadata root must be an object: {path}")
    return value


def _properties(value) -> dict:
    if isinstance(value, dict):
        return value
    if not isinstance(value, list):
        return {}
    return {
        item["name"]: item.get("value") for item in value
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _write_png(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    image.save(temporary, format="PNG", compress_level=9, optimize=False)
    temporary.replace(path)


def render_preview(map_data: dict, runtime_root: Path, output: Path) -> None:
    """Composite runtime tiles and depth props at exact native pixel scale."""
    tilesets = sorted(map_data["tilesets"], key=lambda item: item["firstgid"])
    images = {}
    for tileset in tilesets:
        image_path = runtime_root / "tiles" / Path(str(tileset["image"])).name
        with Image.open(image_path) as opened:
            images[tileset["firstgid"]] = opened.convert("RGBA")
    props_path, props_meta = runtime_root / "props.png", runtime_root / "props.json"
    props = _json(props_meta) if props_meta.is_file() else {"frames": {}}
    frames = props.get("frames", {}) if isinstance(props, dict) else {}
    prop_image = Image.open(props_path).convert("RGBA") if props_path.is_file() else None
    preview = Image.new("RGBA", (VISUAL_WIDTH * TILE_SIZE, VISUAL_HEIGHT * TILE_SIZE))
    try:
        for layer in map_data["layers"]:
            if layer["name"] == "Collisions" or layer.get("visible") is False:
                continue
            if layer["type"] == "tilelayer":
                for index, raw_gid in enumerate(layer["data"]):
                    gid = raw_gid & tiled_gid.GID_MASK
                    if not gid:
                        continue
                    tileset = max(
                        (item for item in tilesets if item["firstgid"] <= gid),
                        key=lambda item: item["firstgid"],
                    )
                    tile_id, columns = gid - tileset["firstgid"], tileset["columns"]
                    source = images[tileset["firstgid"]]
                    sx, sy = (tile_id % columns) * TILE_SIZE, (tile_id // columns) * TILE_SIZE
                    tile = tiled_gid.transform_orthogonal_tile(
                        source.crop((sx, sy, sx + TILE_SIZE, sy + TILE_SIZE)), raw_gid
                    )
                    preview.alpha_composite(
                        tile, ((index % VISUAL_WIDTH) * TILE_SIZE,
                               (index // VISUAL_WIDTH) * TILE_SIZE),
                    )
            elif layer["type"] == "objectgroup" and prop_image is not None:
                for obj in layer["objects"]:
                    values = _properties(obj.get("properties"))
                    frame = frames.get(values.get("asset_key"), {}).get("frame", {})
                    if not all(isinstance(frame.get(axis), int) for axis in ("x", "y", "w", "h")):
                        continue
                    anchor_x, anchor_y = values.get("anchor_x", 0.5), values.get("anchor_y", 1)
                    if not all(isinstance(value, (int, float))
                               for value in (anchor_x, anchor_y, obj.get("x"), obj.get("y"))):
                        continue
                    scale = values.get("display_scale", 1)
                    if not isinstance(scale, (int, float)) or isinstance(scale, bool) or not 0 < scale <= 4:
                        continue
                    sprite = prop_image.crop(
                        (frame["x"], frame["y"], frame["x"] + frame["w"], frame["y"] + frame["h"])
                    )
                    if scale != 1:
                        sprite = sprite.resize(
                            (round(frame["w"] * scale), round(frame["h"] * scale)),
                            Image.Resampling.NEAREST,
                        )
                    preview.alpha_composite(
                        sprite, (round(obj["x"] - anchor_x * sprite.width),
                                 round(obj["y"] - anchor_y * sprite.height)),
                    )
        _write_png(output, preview)
    finally:
        if prop_image is not None:
            prop_image.close()
