"""Transactional output and provenance helpers for Claudeville runtime assets."""

from __future__ import annotations

import math
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath


class RuntimeSupportError(ValueError):
    """Raised when runtime files or their provenance cannot be handled safely."""


def atlas_dimensions(
    tile_count: int, *, tile_size: int = 16, max_size: int = 4096,
    error_type: type[ValueError] = RuntimeSupportError,
) -> tuple[int, int, int]:
    """Return a square-ish, tile-aligned atlas layout within a fixed bound."""
    if not isinstance(tile_count, int) or isinstance(tile_count, bool) or tile_count < 1:
        raise error_type("atlas tile count must be a positive integer")
    if tile_count > (max_size // tile_size) ** 2:
        raise error_type(f"curated atlas would exceed the {max_size}x{max_size} limit")
    columns = math.isqrt(tile_count - 1) + 1
    rows = math.ceil(tile_count / columns)
    return columns * tile_size, rows * tile_size, columns


def _relative_paths(values) -> tuple[PurePosixPath, ...]:
    result = []
    for value in values:
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise RuntimeSupportError(f"generated runtime path is unsafe: {value}")
        result.append(path)
    if len(result) != len(set(result)):
        raise RuntimeSupportError("generated runtime paths contain duplicates")
    return tuple(result)


def _commit(staging: Path, output: Path, relative_paths) -> None:
    output.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=f".{output.name}-backup-", dir=output.parent))
    moved_old: list[PurePosixPath] = []
    installed: list[PurePosixPath] = []
    try:
        for relative in relative_paths:
            destination = output.joinpath(*relative.parts)
            if destination.is_file():
                saved = backup.joinpath(*relative.parts)
                saved.parent.mkdir(parents=True, exist_ok=True)
                destination.replace(saved)
                moved_old.append(relative)
            elif destination.exists():
                raise RuntimeSupportError(
                    f"generated runtime path is not a file: {destination}"
                )
        for relative in relative_paths:
            source = staging.joinpath(*relative.parts)
            if not source.exists():
                continue
            if not source.is_file():
                raise RuntimeSupportError(f"staged runtime path is not a file: {source}")
            destination = output.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.replace(destination)
            installed.append(relative)
    except Exception as exc:
        try:
            for relative in reversed(installed):
                destination = output.joinpath(*relative.parts)
                if destination.is_file():
                    destination.unlink()
            for relative in reversed(moved_old):
                saved = backup.joinpath(*relative.parts)
                destination = output.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                saved.replace(destination)
        except OSError as rollback_error:
            raise RuntimeSupportError("runtime transaction rollback failed") from rollback_error
        raise RuntimeSupportError("runtime transaction commit failed") from exc
    finally:
        shutil.rmtree(backup, ignore_errors=True)


@contextmanager
def staged_runtime(output_root: Path, generated_paths):
    """Yield an empty staging root and commit known outputs only after success."""
    output = Path(output_root).resolve(strict=False)
    relative_paths = _relative_paths(generated_paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-stage-", dir=output.parent))
    try:
        yield staging
        _commit(staging, output, relative_paths)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def used_pack_credits(
    source_credits: dict, atlas_metadata: dict, prop_catalog: dict,
    selected_tiles, requested_props: list[str], v3_pack: dict | None,
) -> list[dict]:
    """Return only pack credits that contributed selected runtime pixels."""
    sources = atlas_metadata.get("sources")
    props = prop_catalog.get("props")
    credits = source_credits.get("packs")
    if not isinstance(sources, list) or not isinstance(props, list):
        raise RuntimeSupportError("authoring provenance catalogs are malformed")
    if not isinstance(credits, list) or not credits:
        raise RuntimeSupportError("authoring credits must declare licensed packs")

    source_packs = {
        item.get("source_id"): item.get("pack") for item in sources
        if isinstance(item, dict) and isinstance(item.get("source_id"), str)
        and isinstance(item.get("pack"), str)
    }
    prop_packs = {
        item.get("asset_key"): item.get("pack") for item in props
        if isinstance(item, dict) and isinstance(item.get("asset_key"), str)
        and isinstance(item.get("pack"), str)
    }
    if len(source_packs) != len(sources) or len(prop_packs) != len(props):
        raise RuntimeSupportError("authoring provenance catalogs contain duplicates")

    used = set()
    uses_v3 = False
    for record in selected_tiles:
        if record.get("atlas") == "interiors_v3":
            uses_v3 = True
            continue
        pack = source_packs.get(record.get("source_id"))
        if pack is None:
            raise RuntimeSupportError(f"tile provenance is missing: {record.get('asset_key')}")
        used.add(pack)
    for key in requested_props:
        if key.startswith("prop.interiors_v3."):
            uses_v3 = True
            continue
        pack = prop_packs.get(key)
        if pack is None:
            raise RuntimeSupportError(f"prop provenance is missing: {key}")
        used.add(pack)

    by_name = {
        item.get("name"): item for item in credits
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if len(by_name) != len(credits) or not used <= by_name.keys():
        raise RuntimeSupportError("used asset packs have missing or duplicate credits")
    result = [by_name[name] for name in by_name if name in used]
    if uses_v3:
        if not isinstance(v3_pack, dict) or not isinstance(v3_pack.get("name"), str):
            raise RuntimeSupportError("Modern Interiors v3 credit evidence is missing")
        v3_name = v3_pack["name"]
        if any(item.get("name") == v3_name for item in result):
            result = [v3_pack if item.get("name") == v3_name else item for item in result]
        else:
            result.append(v3_pack)
    return result
