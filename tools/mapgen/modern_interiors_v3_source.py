"""Validate the paid native-16 Modern Interiors source used by Claudeville v3."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath

from PIL import Image, UnidentifiedImageError

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_FOLDER = "moderninteriors-win"
PACK_NAME = "Modern Interiors"
PACK_RELEASE = "41.4"
PROFILE = "claudeville-modern-interiors-v3"
TILE_SIZE = 16
LICENSE_SHA256 = "e33effd51253bb90c0d83fb555405f300273e9772d5eb84105327b6fa3eab4c5"
READ_ME_SHA256 = "50f0651cbf6ba303a7e351efb218507bcb65cc6a22cff67bc984301200a25dcc"
EXPECTED_ROOM_COUNT = 9
EXPECTED_THEME_COUNT = 16
EXPECTED_PROP_COUNT = 2726
EXPECTED_ROOM_TREE_SHA256 = "163877d468cf4c543d9d1443e9adfd430e97b14b3db0ea87e112959bc6bcd178"
EXPECTED_THEME_TREE_SHA256 = "b03f4a08dd7da6750efed60272807c91a99168e15ab29cebf31f39511c226baf"
EXPECTED_PROP_TREE_SHA256 = "9bcad6efab4369046d913a3cd183737e23f9374b94b0b220980106e61a5c2851"
FORBIDDEN_SOURCE = re.compile(
    r"(?:^|[^a-z0-9])(free|old|previous|preview|rpg|32x32|48x48|gif|zip|generator|exe)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)


def _default_source_root() -> Path:
    candidates = (
        REPO_ROOT / "Modern Pixels" / PACK_FOLDER,
        REPO_ROOT.parent / "Modern Pixels" / PACK_FOLDER,
        REPO_ROOT.parents[1] / "Modern Pixels" / PACK_FOLDER,
    )
    return next((path for path in candidates if path.is_dir()), candidates[0])


DEFAULT_SOURCE_ROOT = _default_source_root()
NATIVE_ROOT = PurePosixPath("1_Interiors/16x16")
ROOM_ROOT = NATIVE_ROOT / "Room_Builder_subfiles"
THEME_ROOT = NATIVE_ROOT / "Theme_Sorter_Black_Shadow"
PROP_ROOT = NATIVE_ROOT / "Theme_Sorter_Black_Shadow_Singles"


class ModernInteriorsV3Error(ValueError):
    """Raised when the paid v3 source inventory is unsafe or modified."""


@dataclass(frozen=True)
class TileSource:
    source_id: str
    label: str
    relative_path: str
    group: str
    purposes: tuple[str, ...]
    shadow_variant: str


@dataclass(frozen=True)
class ThemeSource:
    key: str
    label: str
    sheet_filename: str
    prop_directory: str | None
    purposes: tuple[str, ...]
    shadow_variant: str = "black"


ROOM_SOURCES = (
    TileSource("room.3d_walls", "3D Walls", f"{ROOM_ROOT}/Room_Builder_3d_walls_16x16.png", "room_builder", ("walls", "cutaways"), "room_builder"),
    TileSource("room.arched_entryways", "Arched Entryways", f"{ROOM_ROOT}/Room_Builder_Arched_Entryways_16x16.png", "room_builder", ("doors", "thresholds"), "room_builder"),
    TileSource("room.baseboards", "Baseboards", f"{ROOM_ROOT}/Room_Builder_Baseboards_16x16.png", "room_builder", ("walls", "trim"), "room_builder"),
    TileSource("room.borders", "Borders", f"{ROOM_ROOT}/Room_Builder_borders_16x16.png", "room_builder", ("rugs", "borders"), "room_builder"),
    TileSource("room.floor_connectors", "Floor Connectors", f"{ROOM_ROOT}/Room_Builder_Floor_Connectors_16x16.png", "room_builder", ("floors", "thresholds"), "room_builder"),
    TileSource("room.floor_paths", "Floor Paths", f"{ROOM_ROOT}/Room_Builder_Floor_Paths_16x16.png", "room_builder", ("floors", "rugs"), "room_builder"),
    TileSource("room.floor_shadows", "Floor Shadows", f"{ROOM_ROOT}/Room_Builder_Floor_Shadows_16x16.png", "room_builder", ("depth", "cutaways"), "room_builder"),
    TileSource("room.floors", "Floors", f"{ROOM_ROOT}/Room_Builder_Floors_16x16.png", "room_builder", ("floors",), "room_builder"),
    TileSource("room.walls", "Walls", f"{ROOM_ROOT}/Room_Builder_Walls_16x16.png", "room_builder", ("walls", "doors"), "room_builder"),
)

THEMES = (
    ThemeSource("generic", "Generic", "1_Generic_Black_Shadow_16x16.png", None, ("bank", "town_hall", "workshop", "post_office")),
    ThemeSource("living", "Living Room", "2_LivingRoom_Black_Shadow_16x16.png", "2_LivingRoom_Black_Shadow_Singles_16x16", ("homes", "community_center", "lounge")),
    ThemeSource("bathroom", "Bathroom", "3_Bathroom_Black_Shadow_16x16.png", "3_Bathroom_Black_Shadow_Singles_16x16", ("homes", "public_facilities")),
    ThemeSource("bedroom", "Bedroom", "4_Bedroom_Black_Shadow_16x16.png", "4_Bedroom_Black_Shadow_SIngles_16x16", ("homes",)),
    ThemeSource("classroom_library", "Classroom and Library", "5_Classroom_and_library_Black_Shadow_16x16.png", "5_Classroom_and_Library_Black_Shadow_Singles_16x16", ("university", "agent_academy", "library")),
    ThemeSource("music_sport", "Music and Sport", "6_Music_and_sport_Black_Shadow_16x16.png", "6_Music_and_Sport_Black_Shadow_Singles_16x16", ("community_center", "agent_academy")),
    ThemeSource("art", "Art", "7_Art_Black_Shadow_16x16.png", "7_Art_Black_Shadow_Singles_16x16", ("community_center", "homes")),
    ThemeSource("gym", "Gym", "8_Gym_Black_Shadow_16x16.png", "8_Gym_Black_Shadow_Singles_16x16", ("agent_academy", "community_center")),
    ThemeSource("kitchen", "Kitchen", "12_Kitchen_Black_Shadow_16x16.png", "12_Kitchen_Black_Shadow_Singles_16x16", ("homes", "cafe", "cafeteria")),
    ThemeSource("conference", "Conference Hall", "13_Conference_Hall_Black_Shadow_16x16.png", "13_Conference_Hall_Black_Shadow_Singles_16x16", ("bank", "town_hall", "community_center")),
    ThemeSource("grocery", "Grocery Store", "16_Grocery_store_Black_Shadow_16x16.png", "16_Grocery_Store_Black_Shadow_Singles_16x16", ("market",)),
    ThemeSource("upstairs", "Visible Upstairs", "17_Visibile_Upstairs_System_Black_Shadow_16x16.png", None, ("homes", "cutaways")),
    ThemeSource("japanese", "Japanese Interiors", "20_Japanese_interiors_Black_Shadow_16x16.png", "20_Japanese_Interiors_Black_Shadow_Singles_16x16", ("homes", "cafe")),
    ThemeSource("ice_cream", "Ice Cream Shop", "24_Ice_Cream_Shop_Black_Shadow_16x16.png", "24_Ice_Cream_Shop_Black_Shadow_Singles_16x16", ("cafe", "cafeteria")),
    ThemeSource("shooting_range", "Shooting Range", "25_Shooting_Range_Black_Shadow_16x16.png", "25_Shooting_Range_Black_Shadow_Singles_16x16", ("agent_academy",)),
    ThemeSource("condominium", "Condominium", "26_Condominium_Black_Shadow_16x16.png", "26_Condominium_Black_Shadow_Singles_16x16", ("homes",)),
)

THEME_TILE_SOURCES = tuple(
    TileSource(
        f"theme.{theme.key}", theme.label, f"{THEME_ROOT}/{theme.sheet_filename}",
        "theme", theme.purposes, theme.shadow_variant,
    )
    for theme in THEMES
)
TILE_SOURCES = ROOM_SOURCES + THEME_TILE_SOURCES
THEME_BY_KEY = {theme.key: theme for theme in THEMES}

MASTER_SOURCES = {
    f"{NATIVE_ROOT}/Interiors_16x16.png": ((256, 17024), "a35b8ed8ef392657a9339e1ce0831a3efe7b4631bfff69835bb5ef3bc738550b"),
    f"{NATIVE_ROOT}/Room_Builder_16x16.png": ((1216, 1808), "f53d7cd04f275dfa4b3e1f410569d491275105e2710a0f86ec46edeff3ab576f"),
}


def _normalized_relative(relative_path: str) -> PurePosixPath:
    if not isinstance(relative_path, str) or not relative_path or "\\" in relative_path:
        raise ModernInteriorsV3Error("Modern Interiors source path is malformed")
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or ".." in relative.parts or FORBIDDEN_SOURCE.search(relative_path):
        raise ModernInteriorsV3Error(f"forbidden Modern Interiors source: {relative_path}")
    return relative


def _approved_relative(relative: PurePosixPath) -> bool:
    value = relative.as_posix()
    if value in MASTER_SOURCES or value in {source.relative_path for source in TILE_SOURCES}:
        return True
    if len(relative.parts) != 5 or relative.parts[:3] != PROP_ROOT.parts:
        return False
    directory, filename = relative.parts[-2:]
    approved_directories = {theme.prop_directory for theme in THEMES if theme.prop_directory}
    return directory in approved_directories and filename.lower().endswith(".png")


def validate_source_path(source_root: Path, relative_path: str) -> Path:
    """Resolve one exact approved native-16 source without following an escape."""
    root = Path(source_root).expanduser().resolve(strict=True)
    if not root.is_dir() or root.name != PACK_FOLDER:
        raise ModernInteriorsV3Error(f"source root must be the paid {PACK_FOLDER} folder")
    relative = _normalized_relative(relative_path)
    if not _approved_relative(relative):
        raise ModernInteriorsV3Error(f"unapproved Modern Interiors source: {relative}")
    path = (root / Path(*relative.parts)).resolve(strict=False)
    if root not in path.parents or not path.is_file() or path.suffix.lower() != ".png":
        raise ModernInteriorsV3Error(f"required Modern Interiors PNG is missing: {relative}")
    return path


def open_png(path: Path, expected_size: tuple[int, int] | None = None,
             *, allow_empty: bool = False) -> Image.Image:
    """Load a valid nonempty PNG, optionally enforcing its exact dimensions."""
    try:
        with Image.open(path) as source:
            if source.format != "PNG":
                raise ModernInteriorsV3Error(f"source is not PNG: {path.name}")
            image = source.convert("RGBA")
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise ModernInteriorsV3Error(f"source is not a valid PNG: {path.name}") from exc
    if expected_size is not None and image.size != expected_size:
        image.close()
        raise ModernInteriorsV3Error(f"source dimensions changed: {path.name}")
    if image.width < 1 or image.height < 1 or (
        not allow_empty and image.getchannel("A").getbbox() is None
    ):
        image.close()
        raise ModernInteriorsV3Error(f"source is empty: {path.name}")
    return image


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _tree_sha256(root: Path, paths: list[Path]) -> str:
    payload = bytearray()
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        payload.extend(path.relative_to(root).as_posix().encode("utf-8"))
        payload.append(0)
        payload.extend(file_sha256(path).encode("ascii"))
        payload.append(10)
    return sha256(payload).hexdigest()


def _selected_paths(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    room = [validate_source_path(root, source.relative_path) for source in ROOM_SOURCES]
    themes = [validate_source_path(root, source.relative_path) for source in THEME_TILE_SOURCES]
    props = []
    for theme in THEMES:
        if theme.prop_directory is None:
            continue
        directory = root / Path(*PROP_ROOT.parts) / theme.prop_directory
        if not directory.is_dir():
            raise ModernInteriorsV3Error(f"required prop directory is missing: {theme.prop_directory}")
        for path in directory.glob("*.png"):
            relative = path.relative_to(root).as_posix()
            props.append(validate_source_path(root, relative))
    return room, themes, props


def validate_pack(source_root: Path = DEFAULT_SOURCE_ROOT) -> dict:
    """Validate license, master sheets, and the complete selected source inventory."""
    root = Path(source_root).expanduser().resolve(strict=True)
    if not root.is_dir() or root.name != PACK_FOLDER:
        raise ModernInteriorsV3Error(f"source root must be the paid {PACK_FOLDER} folder")
    license_path, read_me_path = root / "LICENSE.txt", root / "READ_ME.txt"
    if not license_path.is_file() or file_sha256(license_path) != LICENSE_SHA256:
        raise ModernInteriorsV3Error("Modern Interiors license evidence changed or is missing")
    if not read_me_path.is_file() or file_sha256(read_me_path) != READ_ME_SHA256:
        raise ModernInteriorsV3Error("Modern Interiors read-me evidence changed or is missing")
    license_text = license_path.read_text(encoding="utf-8")
    for phrase in ("FULL VERSION LICENSE", "commercial", "Credits required"):
        if phrase.casefold() not in license_text.casefold():
            raise ModernInteriorsV3Error("Modern Interiors license evidence is incomplete")
    masters = []
    for relative, (size, digest) in MASTER_SOURCES.items():
        path = validate_source_path(root, relative)
        if file_sha256(path) != digest:
            raise ModernInteriorsV3Error(f"Modern Interiors master hash changed: {path.name}")
        image = open_png(path, size)
        image.close()
        masters.append({"relative_path": relative, "sha256": digest, "size": list(size)})
    room, themes, props = _selected_paths(root)
    expected = (
        (room, EXPECTED_ROOM_COUNT, EXPECTED_ROOM_TREE_SHA256, "room-builder"),
        (themes, EXPECTED_THEME_COUNT, EXPECTED_THEME_TREE_SHA256, "theme"),
        (props, EXPECTED_PROP_COUNT, EXPECTED_PROP_TREE_SHA256, "prop"),
    )
    fingerprints = {}
    for paths, count, digest, label in expected:
        actual = _tree_sha256(root, paths)
        if len(paths) != count or actual != digest:
            raise ModernInteriorsV3Error(f"Modern Interiors {label} inventory changed")
        fingerprints[label] = {"file_count": count, "tree_sha256": digest}
    return {
        "creator": "LimeZu", "license_file": "LICENSE.txt",
        "license_sha256": LICENSE_SHA256, "master_sources": masters,
        "name": PACK_NAME, "pack_release": PACK_RELEASE,
        "profile": PROFILE, "selected_fingerprints": fingerprints,
        "source_url": "https://limezu.itch.io/moderninteriors",
    }


def iter_prop_sources(source_root: Path = DEFAULT_SOURCE_ROOT):
    """Yield selected singles as (theme, vendor number, path) in stable order."""
    root = Path(source_root).expanduser().resolve(strict=True)
    for theme in THEMES:
        if theme.prop_directory is None:
            continue
        directory = root / Path(*PROP_ROOT.parts) / theme.prop_directory
        candidates = []
        for path in directory.glob("*.png"):
            match = re.search(r"_(\d+)\.png$", path.name, re.IGNORECASE)
            if match is None:
                raise ModernInteriorsV3Error(f"single has no vendor number: {path.name}")
            candidates.append((int(match.group(1)), path))
        numbers = [number for number, _ in candidates]
        if len(numbers) != len(set(numbers)):
            raise ModernInteriorsV3Error(f"duplicate vendor number in {theme.prop_directory}")
        for number, path in sorted(candidates):
            yield theme, number, validate_source_path(root, path.relative_to(root).as_posix())
