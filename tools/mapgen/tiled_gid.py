"""Shared orthogonal-Tiled GID validation and preview transforms."""

from __future__ import annotations

import bisect

from PIL import Image

HORIZONTAL_FLIP = 0x80000000
VERTICAL_FLIP = 0x40000000
DIAGONAL_FLIP = 0x20000000
IGNORED_HEX_ROTATION = 0x10000000
ORTHOGONAL_FLIP_MASK = HORIZONTAL_FLIP | VERTICAL_FLIP | DIAGONAL_FLIP
ALL_FLAG_MASK = ORTHOGONAL_FLIP_MASK | IGNORED_HEX_ROTATION
GID_MASK = 0xFFFFFFFF ^ ALL_FLAG_MASK
UINT32_MAX = 0xFFFFFFFF


class TiledGidError(ValueError):
    """Raised when runtime Tiled tile references cannot be resolved safely."""


def transform_orthogonal_tile(image: Image.Image, raw_gid: int) -> Image.Image:
    """Apply Tiled's diagonal, horizontal, then vertical render transforms."""
    transformed = image
    if raw_gid & DIAGONAL_FLIP:
        transformed = transformed.transpose(Image.Transpose.TRANSPOSE)
    if raw_gid & HORIZONTAL_FLIP:
        transformed = transformed.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if raw_gid & VERTICAL_FLIP:
        transformed = transformed.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return transformed


def validate_runtime_gids(
    layers: dict[str, dict], tilesets: list[dict], layer_names: tuple[str, ...]
) -> None:
    """Require every nonempty orthogonal tile GID to resolve to one tile page."""
    ranges: list[tuple[int, int, str]] = []
    for tileset in tilesets:
        if not isinstance(tileset, dict):
            raise TiledGidError("runtime tilesets must be objects")
        firstgid, tilecount = tileset.get("firstgid"), tileset.get("tilecount")
        name = tileset.get("name")
        if (
            not isinstance(firstgid, int)
            or isinstance(firstgid, bool)
            or firstgid < 1
            or not isinstance(tilecount, int)
            or isinstance(tilecount, bool)
            or tilecount < 1
            or not isinstance(name, str)
            or not name
        ):
            raise TiledGidError("runtime tileset GID ranges are malformed")
        ranges.append((firstgid, firstgid + tilecount, name))
    ranges.sort()
    if not ranges:
        raise TiledGidError("runtime map has no tileset GID ranges")
    for previous, current in zip(ranges, ranges[1:]):
        if current[0] < previous[1]:
            raise TiledGidError("runtime tileset GID ranges overlap")
    starts = [item[0] for item in ranges]
    for layer_name in layer_names:
        layer = layers.get(layer_name)
        data = layer.get("data") if isinstance(layer, dict) else None
        if not isinstance(data, list):
            raise TiledGidError(f"runtime layer {layer_name} has no tile data")
        for index, raw_gid in enumerate(data):
            if (
                not isinstance(raw_gid, int)
                or isinstance(raw_gid, bool)
                or raw_gid < 0
                or raw_gid > UINT32_MAX
                or raw_gid & IGNORED_HEX_ROTATION
            ):
                raise TiledGidError(
                    f"runtime layer {layer_name} has an invalid orthogonal GID at {index}"
                )
            gid = raw_gid & GID_MASK
            if not gid:
                if raw_gid:
                    raise TiledGidError(
                        f"runtime layer {layer_name} has flags without a tile at {index}"
                    )
                continue
            range_index = bisect.bisect_right(starts, gid) - 1
            if range_index < 0 or gid >= ranges[range_index][1]:
                raise TiledGidError(
                    f"runtime layer {layer_name} has unresolved GID {gid} at {index}"
                )
