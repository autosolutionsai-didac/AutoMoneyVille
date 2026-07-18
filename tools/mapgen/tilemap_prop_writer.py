"""Used-only runtime prop atlas writer for Claudeville tilemaps."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from tools.mapgen import modern_interiors_v3_source
from tools.mapgen import tilemap_prop_atlas as atlas


def _load_images(
    authoring: Path,
    v3_source: Path | None,
    requested: list[str],
    frames: dict,
    v3: dict[str, dict],
    design_stamps: dict[str, dict],
) -> list[tuple[str, Image.Image]]:
    source_image = None
    if any(key in frames for key in requested):
        source_image = atlas._open_rgba(authoring / "props.png", "authoring prop atlas")
    images = []
    try:
        for key in requested:
            if key in frames:
                images.append((key, atlas._v2_image(source_image, key, frames)))
            elif key in design_stamps:
                images.append((key, atlas._open_rgba(design_stamps[key]["path"], key)))
            else:
                if v3_source is None:
                    raise atlas.PropAtlasError(
                        "Modern Interiors v3 prop source was not preflighted"
                    )
                record = v3[key]
                source = modern_interiors_v3_source
                path = source.validate_source_path(v3_source, record.get("source"))
                if source.file_sha256(path) != record.get("source_sha256"):
                    raise atlas.PropAtlasError(
                        f"Modern Interiors v3 prop hash changed: {key}"
                    )
                images.append((key, source.open_png(path)))
    finally:
        if source_image is not None:
            source_image.close()
    return images


def write_runtime_props(
    output: Path,
    authoring: Path,
    v3_source: Path | None,
    requested: list[str],
    frames: dict,
    v3: dict[str, dict],
    design_stamps: dict[str, dict],
):
    """Write the deterministic used-only prop atlas and Phaser metadata."""
    images = _load_images(
        authoring, v3_source, requested, frames, v3, design_stamps
    )
    if not images:
        return None
    try:
        width, height, placements = atlas.pack_props(images)
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        frames_out = {}
        for key, prop, x, y in placements:
            image.alpha_composite(prop, (x, y))
            size = {"h": prop.height, "w": prop.width}
            frames_out[key] = {
                "frame": {**size, "x": x, "y": y},
                "rotated": False,
                "spriteSourceSize": {**size, "x": 0, "y": 0},
                "sourceSize": size,
                "trimmed": False,
            }
        atlas._write_png(output / "props.png", image)
        atlas._write_json(
            output / "props.json",
            {
                "frames": frames_out,
                "meta": {
                    "app": "Claudeville Modern Pixels v3 runtime",
                    "format": "RGBA8888",
                    "image": "props.png",
                    "scale": "1",
                    "size": {"h": height, "w": width},
                },
            },
        )
        image.close()
    finally:
        for _, prop in images:
            prop.close()
    return {
        "asset_keys": requested,
        "data": "props.json",
        "image": "props.png",
        "key": "claudeville-v2-props",
    }
