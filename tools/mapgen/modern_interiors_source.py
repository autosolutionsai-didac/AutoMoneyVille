"""Validate Claudeville's project-licensed Modern Interiors source sheets."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageChops, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ROOT = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/the_ville/visuals/map_assets/v1"
)
TILE_SIZE = 16
PACK_NAME = "Modern Interiors"
PACK_CREDIT = {
    "creator": "LimeZu",
    "name": PACK_NAME,
    "license_evidence": "Project-licensed source provided by the user",
    "source_url": "https://limezu.itch.io/moderninteriors",
}


class ModernInteriorsSourceError(ValueError):
    """Raised when a paid Modern Interiors source is absent or modified."""


@dataclass(frozen=True)
class InteriorSheet:
    """One exact 2x source that normalizes to a native-16px sheet."""

    source_id: str
    filename: str
    expected_size: tuple[int, int]
    expected_sha256: str
    native_size: tuple[int, int]


SHEETS = (
    InteriorSheet(
        "interiors.full",
        "Interiors_32x32_full.png",
        (512, 34048),
        "ec056b502696ca7989c9b072cc513192498e9f2c96486160cd45d2605bf3e582",
        (256, 17024),
    ),
    InteriorSheet(
        "interiors.room_builder",
        "Room_Builder_32x32.png",
        (2432, 3488),
        "a6bd5690110f94d8a431803b910423d2dd834ab5c9b42f04815d6ba2e056aa6f",
        (1216, 1744),
    ),
)
SHEET_BY_ID = {sheet.source_id: sheet for sheet in SHEETS}
ALLOWED_FILENAMES = {sheet.filename for sheet in SHEETS}


def validate_source_path(source_root: Path, relative_path: str) -> Path:
    """Resolve only one of the two exact paid project source filenames."""
    root = Path(source_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ModernInteriorsSourceError(f"source root is not a directory: {root}")
    if not isinstance(relative_path, str) or not relative_path or "\\" in relative_path:
        raise ModernInteriorsSourceError("Modern Interiors source path is malformed")
    relative = Path(relative_path)
    if (
        relative.is_absolute()
        or len(relative.parts) != 1
        or ".." in relative.parts
        or "free" in relative_path.casefold()
        or relative.name not in ALLOWED_FILENAMES
    ):
        raise ModernInteriorsSourceError(
            f"unapproved Modern Interiors source: {relative.as_posix()}"
        )
    path = (root / relative).resolve(strict=False)
    if root not in path.parents or not path.is_file():
        raise ModernInteriorsSourceError(
            f"required Modern Interiors source is missing: {relative.name}"
        )
    return path


def _open_exact_source(root: Path, sheet: InteriorSheet) -> tuple[Path, Image.Image]:
    path = validate_source_path(root, sheet.filename)
    digest = sha256(path.read_bytes()).hexdigest()
    if digest != sheet.expected_sha256:
        raise ModernInteriorsSourceError(
            f"Modern Interiors source hash changed: {sheet.filename}"
        )
    try:
        with Image.open(path) as source:
            if source.format != "PNG" or source.size != sheet.expected_size:
                raise ModernInteriorsSourceError(
                    f"Modern Interiors source dimensions changed: {sheet.filename}"
                )
            image = source.convert("RGBA")
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError) as exc:
        if isinstance(exc, ModernInteriorsSourceError):
            raise
        raise ModernInteriorsSourceError(
            f"Modern Interiors source is not a valid PNG: {sheet.filename}"
        ) from exc
    return path, image


def load_native_sheet(
    source_id: str, source_root: Path = DEFAULT_SOURCE_ROOT
) -> tuple[Image.Image, dict]:
    """Return a verified native-16 image and its immutable provenance record."""
    sheet = SHEET_BY_ID.get(source_id)
    if sheet is None:
        raise ModernInteriorsSourceError(f"unknown Modern Interiors source: {source_id}")
    root = Path(source_root).expanduser().resolve(strict=True)
    path, source = _open_exact_source(root, sheet)
    native = source.resize(sheet.native_size, Image.Resampling.NEAREST)
    restored = native.resize(sheet.expected_size, Image.Resampling.NEAREST)
    if ImageChops.difference(source, restored).getbbox() is not None:
        raise ModernInteriorsSourceError(
            f"Modern Interiors source is not an exact nearest-neighbour 2x sheet: {sheet.filename}"
        )
    record = {
        "atlas": "interiors",
        "expected_size": list(sheet.expected_size),
        "native_size": list(sheet.native_size),
        "normalization": "lossless-nearest-neighbour-2x-to-native-16",
        "pack": PACK_NAME,
        "relative_path": (
            "environment/frontend_server/static_dirs/assets/the_ville/visuals/"
            f"map_assets/v1/{sheet.filename}"
        ),
        "sha256": sheet.expected_sha256,
        "source_id": sheet.source_id,
        "source_scope": "project",
    }
    source.close()
    return native, record


def read_source_tiles(source_root: Path = DEFAULT_SOURCE_ROOT) -> tuple[list[tuple], list[dict]]:
    """Return nonempty native tiles in immutable sheet and row-major order."""
    entries: list[tuple] = []
    records: list[dict] = []
    for sheet in SHEETS:
        image, record = load_native_sheet(sheet.source_id, source_root)
        count = 0
        for row, y in enumerate(range(0, image.height, TILE_SIZE)):
            for column, x in enumerate(range(0, image.width, TILE_SIZE)):
                tile = image.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
                if tile.getchannel("A").getbbox() is None:
                    continue
                entries.append(("interiors", sheet.source_id, x, y, tile))
                count += 1
        image.close()
        records.append({**record, "tile_count": count})
    return entries, records


def credit_record(source_root: Path = DEFAULT_SOURCE_ROOT) -> dict:
    """Return credits tied to the exact project source hashes."""
    root = Path(source_root).expanduser().resolve(strict=True)
    sources = []
    for sheet in SHEETS:
        path = validate_source_path(root, sheet.filename)
        digest = sha256(path.read_bytes()).hexdigest()
        if digest != sheet.expected_sha256:
            raise ModernInteriorsSourceError(
                f"Modern Interiors source hash changed: {sheet.filename}"
            )
        sources.append({"filename": sheet.filename, "sha256": digest})
    return {**PACK_CREDIT, "sources": sources}
