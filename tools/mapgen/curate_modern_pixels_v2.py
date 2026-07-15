"""Build a local native-16px authoring cache for the Claudeville v2 map."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from PIL import __version__ as PILLOW_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ROOT = REPO_ROOT.parents[1] / "Modern Pixels"
DEFAULT_OUTPUT_ROOT = (
    REPO_ROOT
    / "output/claudeville/modern_pixels_v2"
)
TILE_SIZE = 16
MAX_ATLAS_SIZE = 4096
SUPPORTED_PILLOW_VERSION = "12.2.0"
FORBIDDEN_PART = re.compile(
    r"(?:^|[^a-z0-9])(free|rpg|preview|old|previous|zip|generator|exe)(?:$|[^a-z0-9])",
    re.IGNORECASE,
)


class CurationError(ValueError):
    """Raised when an input source or output target breaks the v2 asset contract."""


@dataclass(frozen=True)
class SourceSheet:
    """One entire approved native-16px source sheet."""

    source_id: str
    pack: str
    relative_path: str
    expected_size: tuple[int, int]
    atlas: str


@dataclass(frozen=True)
class PropSpec:
    """One complete source image packed as a depth-sortable runtime frame."""

    asset_key: str
    category: str
    pack: str
    relative_path: str


PACKS = {
    "Modern Exteriors": {
        "creator": "LimeZu",
        "license_file": "modernexteriors-win/Modern_Exteriors_License.pdf",
        "source_url": "https://limezu.itch.io/modernexteriors",
    },
    "Modern Office Revamped": {
        "creator": "LimeZu",
        "license_file": "Modern_Office_Revamped_v1.2/LICENSE.txt",
        "source_url": "https://limezu.itch.io/modernoffice",
    },
}
EXTERIOR_SORTER = "modernexteriors-win/Modern_Exteriors_16x16/ME_Theme_Sorter_16x16"
OFFICE_ROOT = "Modern_Office_Revamped_v1.2"

SOURCE_SHEETS = (
    SourceSheet("exteriors_terrain", "Modern Exteriors", f"{EXTERIOR_SORTER}/1_Terrains_and_Fences_16x16.png", (512, 1184), "terrain"),
    SourceSheet("exteriors_city", "Modern Exteriors", f"{EXTERIOR_SORTER}/2_City_Terrains_16x16.png", (944, 1648), "terrain"),
    SourceSheet("exteriors_city_props", "Modern Exteriors", f"{EXTERIOR_SORTER}/3_City_Props_16x16.png", (512, 3584), "town"),
    SourceSheet("exteriors_generic", "Modern Exteriors", f"{EXTERIOR_SORTER}/4_Generic_Buildings_16x16.png", (512, 3200), "town"),
    SourceSheet("exteriors_modular", "Modern Exteriors", f"{EXTERIOR_SORTER}/5_Floor_Modular_Buildings_16x16.png", (512, 4144), "town"),
    SourceSheet("exteriors_villas", "Modern Exteriors", f"{EXTERIOR_SORTER}/7_Villas_16x16.png", (512, 912), "town"),
    SourceSheet("exteriors_worksite", "Modern Exteriors", f"{EXTERIOR_SORTER}/8_Worksite_16x16.png", (512, 320), "town"),
    SourceSheet("exteriors_market", "Modern Exteriors", f"{EXTERIOR_SORTER}/9_Shopping_Center_and_Markets_16x16.png", (512, 1088), "town"),
    SourceSheet("exteriors_school", "Modern Exteriors", f"{EXTERIOR_SORTER}/13_School_16x16.png", (512, 1856), "town"),
    SourceSheet("exteriors_office", "Modern Exteriors", f"{EXTERIOR_SORTER}/16_Office_16x16.png", (512, 1520), "town"),
    SourceSheet("exteriors_garden", "Modern Exteriors", f"{EXTERIOR_SORTER}/17_Garden_16x16.png", (512, 3136), "town"),
    SourceSheet("exteriors_post", "Modern Exteriors", f"{EXTERIOR_SORTER}/22_Post_Office_16x16.png", (512, 480), "town"),
    SourceSheet("exteriors_houses", "Modern Exteriors", f"{EXTERIOR_SORTER}/24_Additional_Houses_16x16.png", (512, 4928), "town"),
    SourceSheet("office_furniture", "Modern Office Revamped", f"{OFFICE_ROOT}/Modern_Office_16x16.png", (256, 848), "office"),
    SourceSheet("office_room_builder", "Modern Office Revamped", f"{OFFICE_ROOT}/1_Room_Builder_Office/Room_Builder_Office_16x16.png", (256, 224), "office"),
)


def _exterior_prop(key: str, category: str, folder: str, filename: str) -> PropSpec:
    return PropSpec(key, category, "Modern Exteriors", f"{EXTERIOR_SORTER}/{folder}/{filename}")


def _office_prop(key: str, number: int) -> PropSpec:
    return PropSpec(
        key,
        "office",
        "Modern Office Revamped",
        f"{OFFICE_ROOT}/4_Modern_Office_singles/16x16/Modern_Office_Singles_{number}.png",
    )


PROP_SPECS = (
    # Complete building compositions give the town a readable exterior silhouette;
    # room-builder tiles are reserved for the roofless interior cutaways beneath them.
    _exterior_prop("prop.building.clock_tower", "building", "13_School_Singles_16x16", "ME_Singles_School_16x16_Clock_Tower_1.png"),
    _exterior_prop("prop.building.bakery", "building", "5_Floor_Modular_Building_Singles_16x16", "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Bakery_1.png"),
    _exterior_prop("prop.building.country_house", "building", "24_Additional_Houses_Singles_16x16", "24_Additional_Houses_Country_House_16x16.png"),
    _exterior_prop("prop.building.market_big", "building", "9_Shopping_Center_and_Markets_Singles_16x16", "ME_Singles_Shopping_Center_and_Markets_16x16_Market_Big_1.png"),
    _exterior_prop("prop.building.market_medium", "building", "9_Shopping_Center_and_Markets_Singles_16x16", "ME_Singles_Shopping_Center_and_Markets_16x16_Market_Medium_1.png"),
    _exterior_prop("prop.building.modern_house", "building", "24_Additional_Houses_Singles_16x16", "24_Additional_Houses_Modern_House_16x16.png"),
    _exterior_prop("prop.building.one_story_house", "building", "24_Additional_Houses_Singles_16x16", "24_Additional_Houses_One_Story_House_16x16.png"),
    _exterior_prop("prop.building.office_civic", "building", "16_Office_Singles_16x16", "ME_Singles_Office_16x16_Example_2.png"),
    _exterior_prop("prop.building.office_tower", "building", "16_Office_Singles_16x16", "ME_Singles_Office_16x16_Example_1.png"),
    _exterior_prop("prop.building.post_office", "building", "22_Post_Office_Singles_16x16", "22_Post_Office_16x16_Building_1.png"),
    _exterior_prop("prop.building.school", "building", "13_School_Singles_16x16", "ME_Singles_School_16x16_School_1.png"),
    _exterior_prop("prop.building.terraced_house", "building", "24_Additional_Houses_Singles_16x16", "24_Additional_Houses_Terraced_House_1_16x16.png"),
    _exterior_prop("prop.building.villa", "building", "7_Villas_Singles_16x16", "ME_Singles_Villas_16x16_Villa_1.png"),
    _exterior_prop("prop.building.villa_green", "building", "7_Villas_Singles_16x16", "ME_Singles_Villas_16x16_Villa_2.png"),
    _exterior_prop("prop.building.villa_rose", "building", "7_Villas_Singles_16x16", "ME_Singles_Villas_16x16_Villa_3.png"),
    _exterior_prop("prop.building.villa_blue", "building", "7_Villas_Singles_16x16", "ME_Singles_Villas_16x16_Villa_4.png"),
    _exterior_prop("prop.building.villa_red", "building", "7_Villas_Singles_16x16", "ME_Singles_Villas_16x16_Villa_5.png"),
    _exterior_prop("prop.building.victorian_house", "building", "24_Additional_Houses_Singles_16x16", "24_Additional_Houses_Victorian_House_1_16x16.png"),
    _exterior_prop("prop.building.wooden_house", "building", "24_Additional_Houses_Singles_16x16", "24_Additional_Houses_Japanese_House_16x16.png"),
    _exterior_prop("prop.plaza.fountain_blue", "plaza", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Fountain_1.png"),
    _exterior_prop("prop.plaza.fountain_city", "plaza", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Fountain_2.png"),
    _exterior_prop("prop.plaza.fountain_garden", "plaza", "17_Garden_Singles_16x16", "ME_Singles_Garden_16x16_Fountain_2_1.png"),
    _exterior_prop("prop.street.bench_01", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Bench_1.png"),
    _exterior_prop("prop.street.bench_02", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Bench_2.png"),
    _exterior_prop("prop.street.bench_03", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Bench_3.png"),
    _exterior_prop("prop.street.bench_05", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Bench_5.png"),
    _exterior_prop("prop.street.billboard", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Billboard_1.png"),
    _exterior_prop("prop.street.drinking_fountain", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Drinking_Fountain_1.png"),
    _exterior_prop("prop.street.hydrant", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Hydrant_1.png"),
    _exterior_prop("prop.street.lamp_01", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Street_Lamp_1.png"),
    _exterior_prop("prop.street.lamp_03", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Street_Lamp_3.png"),
    _exterior_prop("prop.street.mailbox", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Mailbox_1.png"),
    _exterior_prop("prop.street.parking_meter", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Parking_Meter_1.png"),
    _exterior_prop("prop.street.phone_booth", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Phone_Booth_1.png"),
    _exterior_prop("prop.street.trash_can", "street", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Black_Closed_Trash_Can.png"),
    _exterior_prop("prop.landscape.flower_bush_01", "landscape", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Flower_Bush_1.png"),
    _exterior_prop("prop.landscape.flower_bush_03", "landscape", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Flower_Bush_3.png"),
    _exterior_prop("prop.landscape.flower_bush_05", "landscape", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Flower_Bush_5.png"),
    _exterior_prop("prop.landscape.flower_bush_07", "landscape", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Flower_Bush_7.png"),
    _exterior_prop("prop.landscape.tree_03", "landscape", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Tree_3.png"),
    _exterior_prop("prop.landscape.tree_05", "landscape", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Tree_5.png"),
    _exterior_prop("prop.landscape.tree_07", "landscape", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Tree_7.png"),
    _exterior_prop("prop.landscape.tree_09", "landscape", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Tree_9.png"),
    _exterior_prop("prop.garden.bench_horizontal", "garden", "17_Garden_Singles_16x16", "ME_Singles_Garden_16x16_Medium_Bench_Horizontal.png"),
    _exterior_prop("prop.garden.bench_vertical", "garden", "17_Garden_Singles_16x16", "ME_Singles_Garden_16x16_Medium_Bench_Vertical.png"),
    _exterior_prop("prop.garden.cart", "garden", "17_Garden_Singles_16x16", "ME_Singles_Garden_16x16_Small_Wood_Cart_Full_1.png"),
    _exterior_prop("prop.garden.flower_pink", "garden", "17_Garden_Singles_16x16", "ME_Singles_Garden_16x16_Medium_Pink_Flower.png"),
    _exterior_prop("prop.garden.flower_white", "garden", "17_Garden_Singles_16x16", "ME_Singles_Garden_16x16_Small_White_Flower.png"),
    _exterior_prop("prop.garden.sunflower", "garden", "17_Garden_Singles_16x16", "ME_Singles_Garden_16x16_Medium_Sunflower.png"),
    _exterior_prop("prop.garden.square_bench", "garden", "17_Garden_Singles_16x16", "ME_Singles_Garden_16x16_Square_Bench.png"),
    _exterior_prop("prop.post.blue_mailbox", "post", "22_Post_Office_Singles_16x16", "22_Post_Office_16x16_Big_Blue_Mailbox.png"),
    _exterior_prop("prop.post.truck", "post", "22_Post_Office_Singles_16x16", "22_Post_Office_16x16_Truck_Right_Side.png"),
    _exterior_prop("prop.cafe.coffee_kiosk", "cafe", "3_City_Props_Singles_16x16", "ME_Singles_City_Props_16x16_Kiosk_Coffee_Cup_Example.png"),
    _exterior_prop("prop.cafe.food_display", "cafe", "10_Vehicles_Singles_16x16", "ME_Singles_Vehicles_16x16_Street_Food_Table_4.png"),
    _exterior_prop("prop.cafe.bar_counter", "cafe", "21_Beach_Singles_16x16", "21_Beach_16x16_Bamboo_Bar_Counter_1.png"),
    _exterior_prop("prop.library.shelf_dark_1", "library", "23_MIlitary_Base_Singles_16x16", "23_MIlitary_Base_16x16_Military_Tent_Shelf_1.png"),
    _exterior_prop("prop.library.shelf_dark_2", "library", "23_MIlitary_Base_Singles_16x16", "23_MIlitary_Base_16x16_Military_Tent_Shelf_2.png"),
    _exterior_prop("prop.library.shelf_dark_3", "library", "23_MIlitary_Base_Singles_16x16", "23_MIlitary_Base_16x16_Military_Tent_Shelf_3.png"),
    _exterior_prop("prop.library.shelf_warm", "library", "24_Additional_Houses_Singles_16x16", "24_Additional_Houses_Japanese_House_Shelf_16x16.png"),
    _exterior_prop("prop.community.stage_small", "community", "21_Beach_Singles_16x16", "21_Beach_16x16_Example_Small_Stage_1.png"),
    _exterior_prop("prop.community.loudspeaker", "community", "21_Beach_Singles_16x16", "21_Beach_16x16_Medium_Loudspeaker.png"),
    _exterior_prop("prop.facade.door_open", "facade", "24_Additional_Houses_Singles_16x16", "24_Additional_Houses_Modern_House_Door_Open_16x16.png"),
    _exterior_prop("prop.facade.window_shutter", "facade", "16_Office_Singles_16x16", "ME_Singles_Office_16x16_Window_With_Shutter_1_Modular.png"),
    _exterior_prop("prop.facade.window_office", "facade", "16_Office_Singles_16x16", "ME_Singles_Office_16x16_Building_1_Window_Modular.png"),
    _exterior_prop("prop.facade.wall_office", "facade", "16_Office_Singles_16x16", "ME_Singles_Office_16x16_Building_1_Middle_Modular.png"),
    _exterior_prop("prop.vehicle.bus_stop", "vehicle", "10_Vehicles_Singles_16x16", "ME_Singles_Vehicles_16x16_Bus_Stop_1.png"),
    _exterior_prop("prop.vehicle.bus_stop_sign", "vehicle", "10_Vehicles_Singles_16x16", "ME_Singles_Vehicles_16x16_Bus_Stop_Sign_1.png"),
    _exterior_prop("prop.vehicle.car_down_16", "vehicle", "10_Vehicles_Singles_16x16", "ME_Singles_Vehicles_16x16_Car_Down_16.png"),
    _exterior_prop("prop.vehicle.car_left_04", "vehicle", "10_Vehicles_Singles_16x16", "ME_Singles_Vehicles_16x16_Car_Left_4.png"),
    _exterior_prop("prop.vehicle.car_left_10", "vehicle", "10_Vehicles_Singles_16x16", "ME_Singles_Vehicles_16x16_Car_Left_10.png"),
    _exterior_prop("prop.vehicle.car_right_07", "vehicle", "10_Vehicles_Singles_16x16", "ME_Singles_Vehicles_16x16_Car_Right_7.png"),
    _exterior_prop("prop.vehicle.car_right_13", "vehicle", "10_Vehicles_Singles_16x16", "ME_Singles_Vehicles_16x16_Car_Right_13.png"),
    _office_prop("prop.office.chair_blue", 101), _office_prop("prop.office.chair_blue_side", 103),
    _office_prop("prop.office.chair_orange", 107), _office_prop("prop.office.chair_orange_side", 109),
    _office_prop("prop.office.notice_board", 116), _office_prop("prop.office.monitor_blue", 130),
    _office_prop("prop.office.laptop", 136), _office_prop("prop.office.printer", 147),
    _office_prop("prop.office.paper_stack", 154), _office_prop("prop.office.copier", 166),
    _office_prop("prop.office.town_map", 172), _office_prop("prop.office.whiteboard", 170),
    _office_prop("prop.office.wall_chart", 172), _office_prop("prop.office.water_cooler", 173),
    _office_prop("prop.office.display_cabinet", 174), _office_prop("prop.office.vending_machine", 175),
    _office_prop("prop.office.filing_cabinet", 176), _office_prop("prop.office.printer_station", 177),
    _office_prop("prop.office.table_light", 190), _office_prop("prop.office.table_walnut", 193),
    _office_prop("prop.office.sofa_corner", 201), _office_prop("prop.office.sofa_dark", 205),
    _office_prop("prop.office.side_table", 190), _office_prop("prop.office.computer_desk", 235),
    _office_prop("prop.office.dual_monitors", 134), _office_prop("prop.office.phone", 119),
    _office_prop("prop.office.reception_desk", 263), _office_prop("prop.office.reception_corner", 264),
    _office_prop("prop.office.training_station", 235), _office_prop("prop.office.manager_chair", 107),
    _office_prop("prop.office.conference_desk", 294), _office_prop("prop.office.conference_corner", 295),
    _office_prop("prop.office.cash_register", 121), _office_prop("prop.office.waste_bin", 329),
    _office_prop("prop.office.desk_lamp", 144), _office_prop("prop.office.vending_empty", 176),
    _office_prop("prop.office.counter_cream_left", 179), _office_prop("prop.office.counter_cream_middle", 180), _office_prop("prop.office.counter_cream_right", 181),
    _office_prop("prop.office.counter_walnut_left", 185), _office_prop("prop.office.counter_walnut_middle", 186), _office_prop("prop.office.counter_walnut_right", 187),
    _office_prop("prop.office.table_walnut_medium", 194), _office_prop("prop.office.table_walnut_long", 195),
    _office_prop("prop.office.armchair_ice", 196), _office_prop("prop.office.armchair_dark", 197), _office_prop("prop.office.armchair_lilac", 198), _office_prop("prop.office.armchair_mustard", 199),
    _office_prop("prop.office.sofa_vertical", 202), _office_prop("prop.office.sofa_corner_bottom_left", 203), _office_prop("prop.office.sofa_end_vertical", 206),
    _office_prop("prop.office.coffee_station", 318),
)

# The map author starts from these intentional, named choices.  The full sheet
# catalog remains available for variation, but these keys avoid a blind atlas hunt.
SEMANTIC_TILE_KEYS = {
    "terrain.grass": "tile.exteriors_terrain.0272.0112",
    "terrain.river_water": "tile.exteriors_terrain.0448.0080",
    "road.asphalt": "tile.exteriors_city.0064.0080",
    "path.sidewalk": "tile.exteriors_city.0016.0016",
    "plaza.paving": "tile.office_room_builder.0160.0080",
    "interior.floor_civic": "tile.office_room_builder.0160.0080",
    "interior.floor_university": "tile.office_room_builder.0176.0080",
    "interior.floor_market": "tile.office_room_builder.0208.0112",
    "interior.floor_home": "tile.office_room_builder.0160.0176",
    "interior.wall_horizontal": "tile.office_room_builder.0032.0016",
    "interior.wall_vertical_right": "tile.office_room_builder.0112.0016",
    "interior.wall_vertical_left": "tile.office_room_builder.0144.0016",
    "interior.wall_corner_right": "tile.office_room_builder.0080.0016",
    "interior.wall_corner_left": "tile.office_room_builder.0096.0016",
    "frontage.mid": "tile.exteriors_generic.0240.0160",
    "frontage.warm": "tile.exteriors_generic.0032.0160",
    "exterior.eave_office": "tile.exteriors_office.0016.0080",
    "exterior.wall_office": "tile.exteriors_office.0160.0064",
    "exterior.window_office": "tile.exteriors_office.0160.0080",
}


def _safe_source(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise CurationError(f"source path must be relative: {relative.as_posix()}")
    if relative.suffix.lower() != ".png" or any(FORBIDDEN_PART.search(part) for part in relative.parts):
        raise CurationError(f"forbidden source asset: {relative.as_posix()}")
    if not relative.parts or relative.parts[0] not in {"modernexteriors-win", OFFICE_ROOT}:
        raise CurationError(f"source path is outside approved packs: {relative.as_posix()}")
    candidate = (root / relative).resolve(strict=False)
    if root not in candidate.parents or not candidate.is_file():
        raise CurationError(f"required source PNG is missing: {relative.as_posix()}")
    return candidate


def validate_source_path(source_root: Path, relative_path: str) -> Path:
    """Resolve a v2 source only when it is beneath an approved licensed pack."""
    root = Path(source_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise CurationError(f"source root is not a directory: {root}")
    return _safe_source(root, relative_path)


def _open_png(path: Path, expected: tuple[int, int] | None = None) -> Image.Image:
    try:
        with Image.open(path) as source:
            if source.format != "PNG":
                raise CurationError(f"source is not a PNG: {path.name}")
            image = source.convert("RGBA")
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError) as exc:
        raise CurationError(f"source is not a valid PNG: {path.name}") from exc
    if expected is not None and image.size != expected:
        raise CurationError(f"source has unexpected dimensions: {path.name}")
    if image.width < TILE_SIZE or image.height < TILE_SIZE:
        raise CurationError(f"source is smaller than one native tile: {path.name}")
    return image


def atlas_dimensions(tile_count: int) -> tuple[int, int, int]:
    """Return a compact tile-aligned page layout bounded by 4096px."""
    if not isinstance(tile_count, int) or isinstance(tile_count, bool) or tile_count < 1:
        raise CurationError("atlas tile count must be a positive integer")
    if tile_count > (MAX_ATLAS_SIZE // TILE_SIZE) ** 2:
        raise CurationError("curated atlas would exceed the 4096x4096 limit")
    columns = math.isqrt(tile_count - 1) + 1
    rows = math.ceil(tile_count / columns)
    return columns * TILE_SIZE, rows * TILE_SIZE, columns


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_png(path: Path, image: Image.Image) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    image.save(temporary, format="PNG", compress_level=9, optimize=False)
    temporary.replace(path)


def _read_sheets(root: Path, sheets: Iterable[SourceSheet]):
    entries, source_records = [], []
    for sheet in sheets:
        if sheet.pack not in PACKS:
            raise CurationError(f"unapproved pack: {sheet.pack}")
        path = _safe_source(root, sheet.relative_path)
        image = _open_png(path, sheet.expected_size)
        if image.width % TILE_SIZE or image.height % TILE_SIZE:
            raise CurationError(f"source is not aligned to 16px: {sheet.relative_path}")
        count = 0
        for y in range(0, image.height, TILE_SIZE):
            for x in range(0, image.width, TILE_SIZE):
                tile = image.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
                if tile.getchannel("A").getbbox() is None:
                    continue
                entries.append((sheet.atlas, sheet.source_id, x, y, tile))
                count += 1
        source_records.append({
            "atlas": sheet.atlas, "expected_size": list(sheet.expected_size),
            "pack": sheet.pack, "relative_path": sheet.relative_path,
            "sha256": sha256(path.read_bytes()).hexdigest(), "source_id": sheet.source_id,
            "tile_count": count,
        })
    return entries, source_records


def _write_tiles(output: Path, entries: list[tuple], source_records: list[dict]) -> list[dict]:
    pages, catalog = [], []
    for atlas_key in ("terrain", "town", "office"):
        selected = [entry for entry in entries if entry[0] == atlas_key]
        width, height, columns = atlas_dimensions(len(selected))
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for index, (_, source_id, source_x, source_y, tile) in enumerate(selected):
            image.paste(tile, ((index % columns) * TILE_SIZE, (index // columns) * TILE_SIZE))
            catalog.append({
                "asset_key": f"tile.{source_id}.{source_x:04d}.{source_y:04d}",
                "atlas": atlas_key, "atlas_index": index, "source_id": source_id,
                "source_x": source_x, "source_y": source_y,
            })
        directory = output / "tiles"
        directory.mkdir(parents=True, exist_ok=True)
        image_path = directory / f"{atlas_key}.png"
        tileset_path = directory / f"{atlas_key}.tsj"
        _write_png(image_path, image)
        _write_json(tileset_path, {
            "columns": columns, "image": image_path.name, "imageheight": height,
            "imagewidth": width, "name": f"claudeville_v2_{atlas_key}", "tilecount": len(selected),
            "tiledversion": "1.10.2", "tileheight": TILE_SIZE, "tilewidth": TILE_SIZE,
            "type": "tileset", "version": "1.10",
        })
        pages.append({
            "columns": columns, "height": height, "image": f"tiles/{image_path.name}",
            "sha256": sha256(image_path.read_bytes()).hexdigest(), "tile_count": len(selected),
            "tile_size": TILE_SIZE, "tileset": f"tiles/{tileset_path.name}",
            "width": width, "key": atlas_key,
        })
    _write_json(output / "tiles.json", {"schema_version": 1, "tiles": catalog})
    by_key = {entry["asset_key"]: entry for entry in catalog}
    missing = sorted(set(SEMANTIC_TILE_KEYS.values()) - set(by_key))
    if missing:
        raise CurationError(f"semantic palette keys are missing from authoring tiles: {missing}")
    _write_json(output / "palette.json", {
        "schema_version": 1,
        "tiles": {name: {**by_key[key], "tile_id": by_key[key]["atlas_index"]}
                  for name, key in SEMANTIC_TILE_KEYS.items()},
    })
    return pages


def _pack_props(records: list[tuple[PropSpec, Path, Image.Image]]):
    records = sorted(records, key=lambda record: record[0].asset_key)
    for width in (256, 512, 1024, 2048, 4096):
        # Complete civic buildings can be wider than a small prop page.  Try
        # the next bounded runtime page instead of treating a 256px page as a
        # hard limit for every curated sprite.
        if any(image.width + 4 > width for _, _, image in records):
            continue
        x = y = row_height = 2
        placements = []
        for spec, path, image in records:
            if x + image.width + 2 > width:
                x, y, row_height = 2, y + row_height + 2, 0
            placements.append((spec, path, image, x, y))
            x += image.width + 2
            row_height = max(row_height, image.height)
        height = y + row_height + 2
        if height <= width and height <= MAX_ATLAS_SIZE:
            return width, height, placements
    raise CurationError("curated prop atlas would exceed the 4096x4096 limit")


def _write_props(output: Path, root: Path, props: Iterable[PropSpec]) -> list[dict]:
    seen, records = set(), []
    for spec in props:
        if spec.asset_key in seen or not spec.asset_key.startswith("prop."):
            raise CurationError(f"prop keys must be unique stable prop.* names: {spec.asset_key}")
        seen.add(spec.asset_key)
        if spec.pack not in PACKS:
            raise CurationError(f"unapproved prop pack: {spec.pack}")
        path = _safe_source(root, spec.relative_path)
        records.append((spec, path, _open_png(path)))
    width, height, placements = _pack_props(records)
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    frames, catalog = {}, []
    for spec, path, prop, x, y in placements:
        image.alpha_composite(prop, (x, y))
        frames[spec.asset_key] = {
            "frame": {"h": prop.height, "w": prop.width, "x": x, "y": y},
            "rotated": False, "spriteSourceSize": {"h": prop.height, "w": prop.width, "x": 0, "y": 0},
            "sourceSize": {"h": prop.height, "w": prop.width}, "trimmed": False,
        }
        catalog.append({
            "anchor": [0.5, 1.0], "asset_key": spec.asset_key, "atlas": "props",
            "category": spec.category, "display_scale": 1, "foot_offset": [prop.width / 2, prop.height],
            "native_size": [prop.width, prop.height], "pack": spec.pack,
            "source": spec.relative_path, "source_sha256": sha256(path.read_bytes()).hexdigest(),
        })
    image_path = output / "props.png"
    _write_png(image_path, image)
    _write_json(output / "props.json", {
        "frames": frames,
        "meta": {"app": "Claudeville Modern Pixels v2", "format": "RGBA8888", "image": image_path.name,
                 "scale": "1", "size": {"h": height, "w": width}},
    })
    return catalog


def _contact_sheet(output: Path, root: Path, source_records: list[dict], prop_records: list[dict]) -> None:
    font = ImageFont.load_default()
    cards = []
    for record in source_records:
        image = _open_png(_safe_source(root, record["relative_path"]))
        image.thumbnail((144, 96), Image.Resampling.NEAREST)
        cards.append((record["source_id"], image))
    prop_by_key = {record["asset_key"]: record for record in prop_records}
    for key in sorted(prop_by_key):
        record = prop_by_key[key]
        with Image.open(output / "props.png") as atlas:
            frame = json.loads((output / "props.json").read_text(encoding="utf-8"))["frames"][key]["frame"]
            image = atlas.crop((frame["x"], frame["y"], frame["x"] + frame["w"], frame["y"] + frame["h"]))
        image.thumbnail((144, 96), Image.Resampling.NEAREST)
        cards.append((key.removeprefix("prop."), image))
    columns, card_width, card_height, header = 5, 176, 132, 42
    rows = math.ceil(len(cards) / columns)
    sheet = Image.new("RGBA", (columns * card_width, header + rows * card_height), (31, 38, 35, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), "Claudeville v2 - Modern Exteriors + Modern Office (native 16px)", fill=(236, 226, 195, 255), font=font)
    for index, (label, image) in enumerate(cards):
        x = (index % columns) * card_width
        y = header + (index // columns) * card_height
        draw.rectangle((x + 4, y + 4, x + card_width - 5, y + card_height - 5), fill=(57, 66, 59, 255), outline=(144, 132, 102, 255))
        px = x + (card_width - image.width) // 2
        py = y + 12 + (88 - image.height) // 2
        sheet.alpha_composite(image, (px, py))
        draw.text((x + 8, y + 106), label[:27], fill=(238, 237, 223, 255), font=font)
    _write_png(output / "contact_sheet.png", sheet)


def curate_assets(source_root: Path = DEFAULT_SOURCE_ROOT, output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict:
    """Build reproducible Exteriors + Office v2 assets without copying vendor packs."""
    if PILLOW_VERSION != SUPPORTED_PILLOW_VERSION:
        raise CurationError(f"unsupported Pillow {PILLOW_VERSION}; expected {SUPPORTED_PILLOW_VERSION}")
    root = Path(source_root).expanduser().resolve(strict=True)
    output = Path(output_root).expanduser().resolve(strict=False)
    if not root.is_dir() or output == root or root in output.parents or output in root.parents:
        raise CurationError("source and output roots must be separate directories")
    output.mkdir(parents=True, exist_ok=True)
    entries, source_records = _read_sheets(root, SOURCE_SHEETS)
    pages = _write_tiles(output, entries, source_records)
    prop_records = _write_props(output, root, PROP_SPECS)
    _write_json(output / "atlas.json", {
        "atlases": pages, "mode": "exteriors-office-native-16", "schema_version": 2,
        "sources": source_records, "tile_catalog": "tiles.json", "tile_size": TILE_SIZE,
    })
    _write_json(output / "catalog.json", {
        "prop_atlas": {"data": "props.json", "image": "props.png", "key": "claudeville-v2-props"},
        "props": prop_records, "schema_version": 2, "tile_catalog": "tiles.json", "tile_size": TILE_SIZE,
    })
    licenses = []
    for name, details in PACKS.items():
        path = root / details["license_file"]
        if not path.is_file():
            raise CurationError(f"license evidence is missing: {details['license_file']}")
        licenses.append({"name": name, **details, "license_sha256": sha256(path.read_bytes()).hexdigest()})
    _write_json(output / "credits.json", {
        "distribution_allowed": False,
        "distribution_scope": "Local authoring cache only; ship the culled per-map runtime instead.",
        "generated_by": "tools/mapgen/curate_modern_pixels_v2.py", "packs": licenses,
        "schema_version": 2,
    })
    _contact_sheet(output, root, source_records, prop_records)
    return {"output_root": output, "tile_pages": pages, "prop_count": len(prop_records)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args(argv)
    try:
        result = curate_assets(args.source_root, args.output_root)
    except (OSError, CurationError) as exc:
        parser.error(str(exc))
    print(f"Curated {result['prop_count']} props into {result['output_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
