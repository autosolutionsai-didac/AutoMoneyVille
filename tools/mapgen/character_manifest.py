"""Validate resident assets and build the deterministic fallback contact sheet."""

from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Union

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

PathLike = Union[str, Path]
CONTACT_SHEET_LABEL = "CLAUDEVILLE FALLBACK - EXISTING 96x128 SHEETS"
CONTACT_SHEET_SIZE = (800, 410)
DIRECTIONS = ("down", "left", "right", "up")
ACTIVE_RESIDENTS = (
    "Nora Vale",
    "Milo Chen",
    "Iris Morgan",
    "Theo Grant",
    "Lena Ortiz",
    "Ravi Singh",
    "June Park",
    "Amara Cole",
    "Felix Reed",
    "Sofia Lane",
)
PAID_FULL_PACK = {
    "paid_root": "moderninteriors-win",
    "license": "moderninteriors-win/Modern_Interiors_License.pdf",
    "provenance": "moderninteriors-win/READ_ME.txt",
    "interiors_tileset": (
        "moderninteriors-win/Modern_Interiors_32x32/"
        "Modern_Interiors_Complete_Tileset_32x32.png"
    ),
    "character_generator": (
        "moderninteriors-win/Modern_Interiors_32x32/Character_Generator_32x32"
    ),
}


class ManifestError(ValueError):
    """Raised when resident assets do not satisfy the runtime contract."""


def _positive_integer(value, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ManifestError(f"{label} must be a positive integer")
    return value


def _safe_static_asset(static_root: Path, value, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label} must be a safe contained static asset URL")
    relative = Path(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "\\" in value
        or value.startswith("//")
        or ":" in value
    ):
        raise ManifestError(f"{label} must be a safe contained static asset URL")
    candidate = (static_root / relative).resolve(strict=False)
    if static_root not in candidate.parents or not candidate.is_file():
        raise ManifestError(f"{label} must be a safe contained existing static asset URL")
    if candidate.suffix.lower() != ".png":
        raise ManifestError(f"{label} must reference a PNG")
    return candidate


def _png_size(path: Path, label: str) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            image_format = image.format
            size = image.size
            image.verify()
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError) as exc:
        raise ManifestError(f"{label} must be a valid PNG") from exc
    if image_format != "PNG":
        raise ManifestError(f"{label} must be a valid PNG")
    return size


def _validate_frames(values, frame_count: int, label: str) -> None:
    if not isinstance(values, list) or not values:
        raise ManifestError(f"{label} must be a non-empty frame array")
    if any(
        not isinstance(value, int)
        or isinstance(value, bool)
        or not 0 <= value < frame_count
        for value in values
    ):
        raise ManifestError(f"{label} contains an invalid frame index")


def _validate_animation_group(group, frame_count: int, label: str) -> None:
    if not isinstance(group, dict) or set(group) != set(DIRECTIONS):
        raise ManifestError(f"{label} must define exactly four directions")
    for direction in DIRECTIONS:
        _validate_frames(group[direction], frame_count, f"{label}.{direction}")


def _validate_resident(
    resident: dict,
    static_root: Path,
    *,
    expected_source: str,
    require_fallback_layout: bool,
) -> tuple[Path, Path]:
    name = resident.get("name")
    if name not in ACTIVE_RESIDENTS:
        raise ManifestError(f"unexpected active resident: {name}")
    texture_key = resident.get("texture_key")
    if not isinstance(texture_key, str) or not re.fullmatch(r"[A-Za-z0-9_]+", texture_key):
        raise ManifestError(f"{name} texture_key is invalid")
    if resident.get("source") != expected_source:
        raise ManifestError(f"{name} must explicitly declare source: {expected_source}")

    sprite_path = _safe_static_asset(static_root, resident.get("sprite_url"), "sprite_url")
    portrait_path = _safe_static_asset(
        static_root, resident.get("portrait_url"), "portrait_url"
    )
    sheet = resident.get("sheet")
    frame = resident.get("frame")
    if not isinstance(sheet, dict) or not isinstance(frame, dict):
        raise ManifestError(f"{name} sheet and frame must be objects")
    sheet_size = (
        _positive_integer(sheet.get("width"), f"{name} sheet width"),
        _positive_integer(sheet.get("height"), f"{name} sheet height"),
    )
    frame_size = (
        _positive_integer(frame.get("width"), f"{name} frame width"),
        _positive_integer(frame.get("height"), f"{name} frame height"),
    )
    if require_fallback_layout and (
        sheet_size != (96, 128) or frame_size != (32, 32)
    ):
        raise ManifestError(f"{name} fallback must be a 96x128 sheet with 32x32 frames")
    if _png_size(sprite_path, f"{name} sprite") != sheet_size:
        raise ManifestError(f"{name} sprite dimensions do not match sheet metadata")
    portrait_size = _png_size(portrait_path, f"{name} portrait")
    if sheet_size[0] % frame_size[0] or sheet_size[1] % frame_size[1]:
        raise ManifestError(f"{name} frame dimensions do not divide the sheet")
    frame_count = (sheet_size[0] // frame_size[0]) * (
        sheet_size[1] // frame_size[1]
    )

    origin = resident.get("origin")
    if origin != {"x": 0.5, "y": 1}:
        raise ManifestError(f"{name} origin must use bottom-center anchoring")
    scale = resident.get("scale")
    if (
        not isinstance(scale, (int, float))
        or isinstance(scale, bool)
        or scale <= 0
    ):
        raise ManifestError(f"{name} scale must be positive")

    crop = resident.get("portrait_crop")
    if not isinstance(crop, dict) or set(crop) != {"x", "y", "width", "height"}:
        raise ManifestError(f"{name} portrait_crop is incomplete")
    for key in ("width", "height"):
        _positive_integer(crop.get(key), f"{name} portrait crop {key}")
    if any(
        not isinstance(crop.get(key), int)
        or isinstance(crop.get(key), bool)
        or crop[key] < 0
        for key in ("x", "y")
    ):
        raise ManifestError(f"{name} portrait crop offsets must be non-negative")
    if (
        crop["x"] + crop["width"] > portrait_size[0]
        or crop["y"] + crop["height"] > portrait_size[1]
    ):
        raise ManifestError(f"{name} portrait crop exceeds its PNG")

    animations = resident.get("animations")
    if not isinstance(animations, dict):
        raise ManifestError(f"{name} animations must be an object")
    _validate_animation_group(animations.get("idle"), frame_count, f"{name} idle")
    _validate_animation_group(animations.get("walk"), frame_count, f"{name} walk")
    actions = animations.get("actions", {})
    if not isinstance(actions, dict):
        raise ManifestError(f"{name} optional actions must be an object")
    for action, values in actions.items():
        if not isinstance(action, str) or not action.strip():
            raise ManifestError(f"{name} action names must be non-empty")
        _validate_frames(values, frame_count, f"{name} action {action}")
    return sprite_path, portrait_path


def _validate_manifest(
    manifest: dict,
    static_root: PathLike,
    *,
    expected_source: str,
    require_fallback_layout: bool,
) -> dict:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ManifestError("character manifest schema_version must be 1")
    root = Path(static_root).expanduser().resolve(strict=False)
    if not root.is_dir():
        raise ManifestError("static root must be an existing directory")
    active = manifest.get("active_residents")
    if active != list(ACTIVE_RESIDENTS):
        raise ManifestError("active_residents must contain the exact ten-resident roster")
    generation = manifest.get("generation")
    if (
        not isinstance(generation, dict)
        or generation.get("default_activation") is not False
        or generation.get("free_pack_allowed") is not False
    ):
        raise ManifestError(
            "character generation must not activate by default or allow Free pack"
        )
    residents = manifest.get("residents")
    if not isinstance(residents, list) or len(residents) != len(ACTIVE_RESIDENTS):
        raise ManifestError("character manifest must define exactly ten residents")
    if any(not isinstance(resident, dict) for resident in residents):
        raise ManifestError("each resident entry must be an object")
    for field in ("name", "texture_key", "sprite_url", "portrait_url"):
        values = [resident.get(field) for resident in residents]
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ManifestError(f"residents must define non-empty {field} values")
        if len(values) != len(set(values)):
            raise ManifestError(f"residents must use unique {field} values")
    if {resident.get("name") for resident in residents} != set(ACTIVE_RESIDENTS):
        raise ManifestError("resident entries must match active_residents")
    asset_paths = set()
    for resident in residents:
        paths = _validate_resident(
            resident,
            root,
            expected_source=expected_source,
            require_fallback_layout=require_fallback_layout,
        )
        if any(path in asset_paths for path in paths):
            raise ManifestError("residents must use unique contained asset URLs")
        asset_paths.update(paths)
    return manifest


def validate_character_manifest(manifest: dict, static_root: PathLike) -> dict:
    """Validate the exact active roster and every referenced fallback image."""
    return _validate_manifest(
        manifest,
        static_root,
        expected_source="fallback",
        require_fallback_layout=True,
    )


def _full_pack_error(detail: str) -> ManifestError:
    return ManifestError(
        "paid Modern Interiors character assets are absent or unverified; "
        "full-pack NPC generation requires verified paid Modern Interiors evidence; "
        f"{detail}. Free pack is forbidden"
    )


def _required_paid_path(root: Path, key: str, *, directory=False) -> Path:
    candidate = (root / PAID_FULL_PACK[key]).resolve(strict=False)
    if root not in candidate.parents:
        raise _full_pack_error(f"unsafe {key} path")
    valid = candidate.is_dir() if directory else candidate.is_file()
    if not valid:
        raise _full_pack_error(f"missing required {key}: {PAID_FULL_PACK[key]}")
    return candidate


def _validate_paid_png(path: Path, label: str) -> None:
    try:
        with Image.open(path) as image:
            image_format, size = image.format, image.size
            image.verify()
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError) as exc:
        raise _full_pack_error(f"invalid {label} PNG: {path.name}") from exc
    if (
        image_format != "PNG"
        or min(size) < 32
        or size[0] % 32
        or size[1] % 32
    ):
        raise _full_pack_error(f"{label} is not a native 32px-grid PNG: {path.name}")


def _validate_full_pack_source(source_root: PathLike) -> None:
    try:
        root = Path(source_root).expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise _full_pack_error(f"source root is missing or inaccessible: {source_root}") from exc
    if not root.is_dir():
        raise _full_pack_error(f"source root is not a directory: {root}")
    paid_root = _required_paid_path(root, "paid_root", directory=True)
    license_path = _required_paid_path(root, "license")
    provenance_path = _required_paid_path(root, "provenance")
    interiors_path = _required_paid_path(root, "interiors_tileset")
    generator_root = _required_paid_path(root, "character_generator", directory=True)
    license_bytes = license_path.read_bytes()
    if len(license_bytes) < 16 or not license_bytes.startswith(b"%PDF"):
        raise _full_pack_error("license evidence is empty or not a PDF")
    try:
        provenance = provenance_path.read_text(encoding="utf-8").strip().lower()
    except (OSError, UnicodeError) as exc:
        raise _full_pack_error("provenance evidence is not readable UTF-8 text") from exc
    if len(provenance) < 10 or "modern" not in provenance or "interiors" not in provenance:
        raise _full_pack_error("provenance evidence does not identify Modern Interiors")
    _validate_paid_png(interiors_path, "Modern Interiors tileset")
    generator_pngs = sorted(generator_root.rglob("*.png"))
    if not generator_pngs:
        raise _full_pack_error("character generator contains no PNG content")
    for generator_png in generator_pngs:
        resolved = generator_png.resolve(strict=True)
        if paid_root not in resolved.parents:
            raise _full_pack_error("character generator PNG escapes the paid pack root")
        _validate_paid_png(resolved, "character generator")


def require_full_pack(
    manifest: dict,
    static_root: PathLike | None = None,
    paid_source_root: PathLike | None = None,
) -> dict:
    """Require complete paid resident assets plus verified vendor evidence."""
    if (
        not isinstance(manifest, dict)
        or manifest.get("asset_pack") != "modern-interiors-paid"
    ):
        raise _full_pack_error("the manifest does not declare the paid asset pack")
    if static_root is None or paid_source_root is None:
        raise _full_pack_error("static assets and paid source evidence are both required")
    try:
        validated = _validate_manifest(
            manifest,
            static_root,
            expected_source="modern-interiors-paid",
            require_fallback_layout=False,
        )
    except ManifestError as exc:
        raise _full_pack_error(str(exc)) from exc
    _validate_full_pack_source(paid_source_root)
    return validated


def _contact_sheet_metadata(manifest: dict, output_path: Path) -> dict:
    return {
        "image": output_path.name,
        "image_sha256": sha256(output_path.read_bytes()).hexdigest(),
        "label": CONTACT_SHEET_LABEL,
        "residents": manifest["active_residents"],
        "schema_version": 1,
        "size": list(CONTACT_SHEET_SIZE),
        "source": "fallback",
    }


def build_contact_sheet(
    manifest: dict,
    static_root: PathLike,
    output_path: PathLike,
    *,
    metadata_path: PathLike | None = None,
) -> Path:
    """Render the exact ten existing sheets into a deterministic labeled PNG."""
    root = Path(static_root).expanduser().resolve(strict=False)
    validated = validate_character_manifest(manifest, root)
    output = Path(output_path).expanduser().resolve(strict=False)
    if output.suffix.lower() != ".png":
        raise ManifestError("contact sheet output must be a PNG")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", CONTACT_SHEET_SIZE, (18, 22, 30, 255))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    draw.text((12, 15), CONTACT_SHEET_LABEL, fill=(255, 220, 96, 255), font=font)
    by_name = {resident["name"]: resident for resident in validated["residents"]}
    cell_width, row_height, top = 160, 180, 50
    for index, name in enumerate(validated["active_residents"]):
        resident = by_name[name]
        column, row = index % 5, index // 5
        cell_x, cell_y = column * cell_width, top + row * row_height
        with Image.open(root / resident["sprite_url"]) as opened:
            sheet = opened.convert("RGBA")
        canvas.alpha_composite(sheet, (cell_x + 32, cell_y + 4))
        text_box = draw.textbbox((0, 0), name, font=font)
        text_width = text_box[2] - text_box[0]
        draw.text(
            (cell_x + (cell_width - text_width) // 2, cell_y + 140),
            name,
            fill=(235, 240, 248, 255),
            font=font,
        )
    canvas.save(output, format="PNG", compress_level=9, optimize=False)
    if metadata_path is not None:
        metadata = Path(metadata_path).expanduser().resolve(strict=False)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(
            json.dumps(
                _contact_sheet_metadata(validated, output),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    return output


def main(argv=None) -> int:
    repo_root = Path(__file__).resolve().parents[2]
    static_root = repo_root / "environment/frontend_server/static_dirs"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=static_root / "assets/characters/manifest.json",
    )
    parser.add_argument("--static-root", type=Path, default=static_root)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--require-full-pack", action="store_true")
    parser.add_argument("--paid-source-root", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if args.require_full_pack:
            require_full_pack(manifest, args.static_root, args.paid_source_root)
            if args.contact_sheet:
                raise ManifestError("contact-sheet output is available only in fallback mode")
            mode = "paid"
        else:
            validate_character_manifest(manifest, args.static_root)
            mode = "fallback"
        if args.contact_sheet:
            build_contact_sheet(
                manifest,
                args.static_root,
                args.contact_sheet,
                metadata_path=args.metadata,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ManifestError) as exc:
        parser.error(str(exc))
    print(f"Validated {len(manifest['residents'])} {mode} resident assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
