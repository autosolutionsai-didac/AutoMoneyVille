"""Extract licensed, vendor-authored native-16 Claudeville design stamps."""
from __future__ import annotations

import json
import struct
import zlib
from hashlib import sha256
from pathlib import Path

from PIL import Image

try:
    from tools.mapgen import claudeville_reference_facade_assets as facade_assets
    from tools.mapgen.tilemap_prop_atlas import APPROVED_PACK_CREDITS
except ModuleNotFoundError:  # Direct ``python tools/mapgen/curate_*.py``.
    import claudeville_reference_facade_assets as facade_assets
    from tilemap_prop_atlas import APPROVED_PACK_CREDITS

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT.parents[1] / "Modern Pixels"
OUTPUT_ROOT = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/stamps"
)
OFFICE_ROOT = SOURCE_ROOT / "Modern_Office_Revamped_v1.2/6_Office_Designs"
INTERIORS_ROOT = SOURCE_ROOT / "moderninteriors-win/6_Home_Designs"
EXTERIORS_ROOT = (
    SOURCE_ROOT
    / "modernexteriors-win/Modern_Exteriors_16x16/ME_Theme_Sorter_16x16"
)
MAX_DECOMPRESSED_BYTES = 4 * 1024 * 1024

OFFICE_STAMPS = (
    {
        "asset_key": "prop.design.bank_suite",
        "file": "bank_suite.png",
        "source": OFFICE_ROOT / "Office_Design_1.aseprite",
        "sha256": "bff7b0206aceb2b7db0680ec00eb2719ac2aba60ab0287f0ecece5ad1352596e",
        "size": (208, 192),
        "layers": (0, 1),
        "pack": "Modern Office Revamped",
    },
    {
        "asset_key": "prop.design.bank_office",
        "file": "bank_office.png",
        "source": OFFICE_ROOT / "Office_Design_1.aseprite",
        "sha256": "bff7b0206aceb2b7db0680ec00eb2719ac2aba60ab0287f0ecece5ad1352596e",
        "size": (208, 192),
        "layers": (1,),
        "pack": "Modern Office Revamped",
    },
    {
        "asset_key": "prop.design.bank_operations_east",
        "file": "bank_operations_east.png",
        "source": OFFICE_ROOT / "Office_Design_2.aseprite",
        "sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "size": (256, 400),
        "layers": (1,),
        "crop": (112, 0, 256, 160),
        "trim": False,
        "pack": "Modern Office Revamped",
    },
    {
        "asset_key": "prop.design.university_lab",
        "file": "university_lab.png",
        "source": OFFICE_ROOT / "Office_Design_2.aseprite",
        "sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "size": (256, 400),
        "layers": (1,),
        "pack": "Modern Office Revamped",
    },
    {
        "asset_key": "prop.design.university_floor",
        "file": "university_floor.png",
        "source": OFFICE_ROOT / "Office_Design_2.aseprite",
        "sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "size": (256, 400),
        "layers": (0, 1),
        "crop": (0, 0, 256, 272),
        "pack": "Modern Office Revamped",
    },
    {
        "asset_key": "prop.design.university_lab_main",
        "file": "university_lab_main.png",
        "source": OFFICE_ROOT / "Office_Design_2.aseprite",
        "sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "size": (256, 400),
        "layers": (1,),
        "crop": (0, 0, 256, 160),
        "pack": "Modern Office Revamped",
    },
    {
        "asset_key": "prop.design.university_lounge",
        "file": "university_lounge.png",
        "source": OFFICE_ROOT / "Office_Design_2.aseprite",
        "sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "size": (256, 400),
        "layers": (1,),
        "crop": (56, 160, 256, 272),
        "pack": "Modern Office Revamped",
    },
    {
        "asset_key": "prop.design.academy_lab",
        "file": "academy_lab.png",
        "source": OFFICE_ROOT / "Office_Design_2.aseprite",
        "sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "size": (256, 400),
        "layers": (0, 1),
        "crop": (0, 0, 160, 160),
        "pack": "Modern Office Revamped",
    },
)
JAPANESE_HOME_ROOT = INTERIORS_ROOT / "Japanese_Interiors_Home_Designs/16x16"
GENERIC_HOME_ROOT = INTERIORS_ROOT / "Generic_Home_Designs/16x16"
GYM_ROOT = INTERIORS_ROOT / "Gym_Designs/16x16"
ICE_CREAM_ROOT = INTERIORS_ROOT / "Ice-Cream_Shop_Designs/16x16"
TV_STUDIO_ROOT = INTERIORS_ROOT / "TV_Studio_Designs/16x16"
CONDO_ROOT = INTERIORS_ROOT / "Condominium_Designs/16x16"

JAPANESE_LAYERS = (
    (
        JAPANESE_HOME_ROOT / "Japanese_Home_1_Layer_1_16x16.png",
        "1548c66a313b3c93968492c5ae8a98058758be82044be7d53dde2ddf2ce5aadf",
    ),
    (
        JAPANESE_HOME_ROOT / "Japanese_Home_1_Layer_2_16x16.png",
        "e021694541db0c4b36f8337a225f85cb7f8ce3b0dff8d93b33a7fc6b50b182c9",
    ),
)
GENERIC_LAYERS = (
    (
        GENERIC_HOME_ROOT / "Generic_Home_1_Layer_1.png",
        "24effc29867409ec5abfd946f0b731f5212637ff722729dd0d52d86e4c91761c",
    ),
    (
        GENERIC_HOME_ROOT / "Generic_Home_1_Layer_2_.png",
        "095ecd0fba6fbcf92dbcb2f71a3ea89af90bdedf81f8cde90cc53da67ad32332",
    ),
)
GYM_LAYERS = (
    (
        GYM_ROOT / "Gym_layer_1.png",
        "3145ea6bfe034b196a9e9d01a2d521b549e9712469643a3255b036ef200c99e1",
    ),
    (
        GYM_ROOT / "Gym_layer_2.png",
        "f839307e617272a8d696cb9efd4bae83493d0a1138fdb99c5534f7d3eebeba63",
    ),
)
COMPACT_GYM_LAYERS = (
    (
        GYM_ROOT / "Gym_2_layer_1.png",
        "d961b76ece1f72ac4d44b975470606d93c3f8e90e25d30aa5e34eac2148aebf1",
    ),
    (
        GYM_ROOT / "Gym_2_layer_2.png",
        "5dbe546cf03c71442cc5efed59644eb975ab248396e73bc568aff7c1a62ecbcb",
    ),
)
ICE_CREAM_LAYERS = tuple(
    (ICE_CREAM_ROOT / f"Ice_Cream_Shop_Design_layer_{index}.png", digest)
    for index, digest in (
        (1, "1bbba36a51727f3acb6eea3a6aaaf4a02ac167093df453f445c4980d99320038"),
        (2, "d6600b2fd9daf56e535dfb8c7e544e8170a5895b3b83e0847d2298c44748aa91"),
        (3, "21c1d36fddbc57726a83f7b6f9dd3dca078bfedb635bf11c5aa586e5c7aa652c"),
    )
)
TV_STUDIO_LAYERS = tuple(
    (TV_STUDIO_ROOT / f"Tv_Studio_Design_layer_{index}.png", digest)
    for index, digest in (
        (1, "f01894014c63373a08ff450662dc8a4711cf2a4571f29c197fa1bef885613b58"),
        (2, "88261200ed01900e7742b9a7f71d814744816bce69b6dda9b40a22485ebb8206"),
        (3, "7b1c1ef2d3d7ae6c042526cf0c41c54a2d1a49c691dc4b5d8bfc8eebf454382a"),
    )
)
CONDO_FOYER_LAYERS = (
    (
        CONDO_ROOT / "Condominium_Design_2_layer_1.png",
        "15e0579efa62a5cdbfa313ba3de65e16e461701405c96e2bcaef61fa254f3fd6",
    ),
    (
        CONDO_ROOT / "Condominium_Design_2_layer_2.png",
        "6a58df08e47c3dced8c745998ecf820a0f0309f0a1be503e052e1f5d32f7d62e",
    ),
)


def _png_spec(
    asset_key: str, file: str, sources, size: tuple[int, int], *,
    crop: tuple[int, int, int, int] | None = None,
    pack: str = "Modern Interiors", trim: bool = True,
    output_size: tuple[int, int] | None = None, pieces: tuple = (),
) -> dict:
    return {
        "asset_key": asset_key, "file": file, "sources": tuple(sources),
        "size": size, "crop": crop, "pack": pack, "trim": trim,
        "output_size": output_size, "pieces": pieces,
    }


PNG_STAMPS = (
    _png_spec(
        "prop.design.home_japanese",
        "home_japanese.png",
        JAPANESE_LAYERS[1:],
        (304, 214),
    ),
    _png_spec("prop.design.home_generic", "home_generic.png", GENERIC_LAYERS, (224, 214)),
    _png_spec("prop.design.academy_gym", "academy_gym.png", GYM_LAYERS, (304, 240)),
    _png_spec(
        "prop.design.academy_gym_compact", "academy_gym_compact.png",
        COMPACT_GYM_LAYERS, (192, 112), trim=False,
    ),
    _png_spec(
        "prop.design.community_cafe", "community_cafe.png",
        ICE_CREAM_LAYERS[1:], (192, 160), trim=False,
    ),
    _png_spec(
        "prop.design.cafe_complete", "cafe_complete.png",
        ICE_CREAM_LAYERS, (192, 160), trim=False,
    ),
    _png_spec(
        "prop.design.community_studio", "community_studio.png",
        TV_STUDIO_LAYERS, (176, 160), trim=False,
    ),
    _png_spec(
        "prop.design.community_foyer", "community_foyer.png",
        CONDO_FOYER_LAYERS, (224, 96), crop=(16, 0, 208, 96), trim=False,
    ),
    *(
        _png_spec(
            spec["asset_key"], spec["file"],
            ((EXTERIORS_ROOT / spec["source"], spec["sha256"]),),
            spec["source_size"], crop=spec["crop"], output_size=spec["output_size"],
            pieces=spec["pieces"], pack="Modern Exteriors", trim=False,
        )
        for spec in facade_assets.SPECS
    ),
    *(
        _png_spec(
            spec["asset_key"], spec["file"],
            ((EXTERIORS_ROOT / spec["source"], spec["sha256"]),),
            spec["source_size"], crop=spec["crop"],
            pack="Modern Exteriors", trim=False,
        )
        for spec in facade_assets.LEGACY_CURATED_SPECS
    ),
    _png_spec(
        "prop.design.home_cluster.generic_nw", "home_cluster_generic_nw.png",
        GENERIC_LAYERS[1:], (224, 214), crop=(0, 0, 112, 112), trim=False,
    ),
    _png_spec(
        "prop.design.home_cluster.generic_ne", "home_cluster_generic_ne.png",
        GENERIC_LAYERS[1:], (224, 214), crop=(112, 0, 224, 112), trim=False,
    ),
    _png_spec(
        "prop.design.home_cluster.generic_south", "home_cluster_generic_south.png",
        GENERIC_LAYERS[1:], (224, 214), crop=(32, 96, 192, 214), trim=False,
    ),
    _png_spec(
        "prop.design.home_cluster.japanese_nw", "home_cluster_japanese_nw.png",
        JAPANESE_LAYERS[1:], (304, 214), crop=(16, 0, 144, 112), trim=False,
    ),
    _png_spec(
        "prop.design.home_cluster.japanese_ne", "home_cluster_japanese_ne.png",
        JAPANESE_LAYERS[1:], (304, 214), crop=(160, 0, 288, 112), trim=False,
    ),
    _png_spec(
        "prop.design.home_cluster.japanese_sw", "home_cluster_japanese_sw.png",
        JAPANESE_LAYERS[1:], (304, 214), crop=(16, 96, 160, 208), trim=False,
    ),
    _png_spec(
        "prop.design.home_cluster.japanese_se", "home_cluster_japanese_se.png",
        JAPANESE_LAYERS[1:], (304, 214), crop=(144, 96, 288, 208), trim=False,
    ),
)


def _graystone_frontage_spec(spec: dict) -> dict:
    return {
        "asset_key": spec["asset_key"],
        "file": spec["file"],
        "output_size": spec["output_size"],
        "pack": "Modern Exteriors",
        "source_pieces": tuple(
            (
                EXTERIORS_ROOT / facade_assets.RESIDENTIAL_SOURCES[key]["source"],
                facade_assets.RESIDENTIAL_SOURCES[key]["sha256"],
                facade_assets.RESIDENTIAL_SOURCES[key]["source_size"], crop, destination,
            )
            for key, crop, destination in spec["source_pieces"]
        ),
    }


GRAYSTONE_FRONTAGE_STAMPS = tuple(map(
    _graystone_frontage_spec, facade_assets.GRAYSTONE_SPECS,
))
COMMUNITY_PRESENTATION_STAMPS = ({
    "asset_key": "prop.design.community_presentation_room",
    "file": "community_presentation_room.png",
    "output_size": (176, 160),
    "pack": "Modern Interiors",
    "source_pieces": (
        (TV_STUDIO_LAYERS[0][0], TV_STUDIO_LAYERS[0][1], (176, 160),
         (0, 0, 176, 160), (0, 0)),
        (TV_STUDIO_LAYERS[2][0], TV_STUDIO_LAYERS[2][1], (176, 160),
         (0, 0, 176, 160), (0, 0)),
        *((TV_STUDIO_LAYERS[1][0], TV_STUDIO_LAYERS[1][1], (176, 160),
           crop, (crop[0], crop[1])) for crop in (
            (53, 39, 76, 63), (101, 39, 124, 63),
            (49, 97, 64, 129), (81, 97, 96, 129), (113, 97, 128, 129),
        )),
    ),
},)
ALL_STAMPS = (
    *OFFICE_STAMPS, *PNG_STAMPS, *COMMUNITY_PRESENTATION_STAMPS,
    *GRAYSTONE_FRONTAGE_STAMPS,
)
APPROVED_OUTPUT_FILES = frozenset(spec["file"] for spec in ALL_STAMPS)
RETIRED_OUTPUT_FILES = frozenset(
    {"library_shell.png", "post_office.png", "town_hall_shell.png"}
)


class StampCurationError(ValueError):
    """Raised when a licensed stamp source is missing or changed."""


def resolve_output(relative_path: Path) -> Path:
    """Resolve one generated stamp through its fixed project alias."""
    if (
        relative_path.is_absolute()
        or relative_path.parts[:1] != ("claudeville-curated",)
        or len(relative_path.parts) != 2
        or relative_path.name not in APPROVED_OUTPUT_FILES
    ):
        raise StampCurationError(f"unapproved curated stamp: {relative_path.as_posix()}")
    candidate = (OUTPUT_ROOT / relative_path.name).resolve(strict=False)
    if OUTPUT_ROOT.resolve() not in candidate.parents or not candidate.is_file():
        raise StampCurationError(f"required curated stamp is missing: {relative_path.name}")
    return candidate


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _pack_credits() -> list[dict]:
    credits = []
    for name in sorted(APPROVED_PACK_CREDITS):
        record = APPROVED_PACK_CREDITS[name]
        license_path = SOURCE_ROOT / record["license_file"]
        if not license_path.is_file() or _digest(license_path) != record["license_sha256"]:
            raise StampCurationError(f"licensed pack evidence changed: {name}")
        credits.append(dict(record))
    return credits


def _write_png(path: Path, image: Image.Image) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    image.save(temporary, format="PNG", compress_level=9, optimize=False)
    temporary.replace(path)


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _take(data: bytes, offset: int, count: int) -> tuple[bytes, int]:
    end = offset + count
    if end > len(data):
        raise StampCurationError("Aseprite source ended unexpectedly")
    return data[offset:end], end


def _first_frame_cels(path: Path, expected_size: tuple[int, int]) -> dict[int, Image.Image]:
    data = path.read_bytes()
    if len(data) < 144:
        raise StampCurationError(f"Aseprite source is truncated: {path.name}")
    file_size, magic, frames, width, height, depth = struct.unpack_from(
        "<IHHHHH", data, 0
    )
    if (
        file_size != len(data)
        or magic != 0xA5E0
        or frames < 1
        or (width, height) != expected_size
        or depth != 32
    ):
        raise StampCurationError(f"Aseprite header changed: {path.name}")
    frame_size, frame_magic, old_chunks = struct.unpack_from("<IHH", data, 128)
    new_chunks = struct.unpack_from("<I", data, 140)[0]
    if frame_magic != 0xF1FA or frame_size < 16:
        raise StampCurationError(f"Aseprite first frame is invalid: {path.name}")
    chunk_count = new_chunks if old_chunks == 0xFFFF or new_chunks else old_chunks
    offset, cels = 144, {}
    for _ in range(chunk_count):
        header, offset = _take(data, offset, 6)
        chunk_size, chunk_type = struct.unpack("<IH", header)
        payload, offset = _take(data, offset, chunk_size - 6)
        if chunk_type != 0x2005:
            continue
        if len(payload) < 20:
            raise StampCurationError(f"Aseprite cel is truncated: {path.name}")
        layer, x, y, opacity, cel_type = struct.unpack_from("<HhhBH", payload, 0)
        if cel_type != 2:
            raise StampCurationError(f"Aseprite design cel is not compressed RGBA: {path.name}")
        cel_width, cel_height = struct.unpack_from("<HH", payload, 16)
        raw = zlib.decompress(payload[20:])
        expected = cel_width * cel_height * 4
        if expected > MAX_DECOMPRESSED_BYTES or len(raw) != expected:
            raise StampCurationError(f"Aseprite cel size is invalid: {path.name}")
        cel = Image.frombytes("RGBA", (cel_width, cel_height), raw)
        if opacity != 255:
            alpha = cel.getchannel("A").point(lambda value: value * opacity // 255)
            cel.putalpha(alpha)
        canvas = Image.new("RGBA", expected_size, (0, 0, 0, 0))
        canvas.alpha_composite(cel, (x, y))
        cel.close()
        cels[layer] = canvas
    return cels


def _trim(image: Image.Image) -> tuple[Image.Image, tuple[int, int]]:
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise StampCurationError("design stamp rendered empty")
    return image.crop(bounds), (bounds[0], bounds[1])


def _office_stamp(spec: dict) -> tuple[Image.Image, tuple[int, int]]:
    source = Path(spec["source"])
    if not source.is_file() or _digest(source) != spec["sha256"]:
        raise StampCurationError(f"licensed office design changed: {source.name}")
    cels = _first_frame_cels(source, spec["size"])
    if any(index not in cels for index in spec["layers"]):
        raise StampCurationError(f"office design layers changed: {source.name}")
    result = Image.new("RGBA", spec["size"], (0, 0, 0, 0))
    working = result
    try:
        for index in spec["layers"]:
            result.alpha_composite(cels[index])
        if "crop" in spec:
            working = result.crop(spec["crop"])
        if spec.get("trim", True):
            return _trim(working)
        return working.copy(), (0, 0)
    finally:
        if working is not result:
            working.close()
        result.close()
        for cel in cels.values():
            cel.close()


def _verified_png(path: Path, digest: str, size: tuple[int, int]) -> Image.Image:
    if not path.is_file() or _digest(path) != digest:
        raise StampCurationError(f"licensed PNG design changed: {path.name}")
    with Image.open(path) as opened:
        if opened.format != "PNG":
            raise StampCurationError(f"design source is not PNG: {path.name}")
        image = opened.convert("RGBA")
    if image.size != size:
        image.close()
        raise StampCurationError(f"PNG design dimensions changed: {path.name}")
    return image


def _png_stamp(spec: dict) -> tuple[Image.Image, tuple[int, int], list[dict]]:
    from tools.mapgen.claudeville_design_stamp_runner import png_stamp

    return png_stamp(spec)


def _composite_png_stamp(spec: dict) -> tuple[Image.Image, tuple[int, int], list[dict]]:
    from tools.mapgen.claudeville_design_stamp_runner import composite_png_stamp

    return composite_png_stamp(spec)


def curate(output_root: Path = OUTPUT_ROOT) -> dict:
    from tools.mapgen.claudeville_design_stamp_runner import curate as run

    return run(output_root)


def main() -> int:
    from tools.mapgen.claudeville_design_stamp_runner import main as run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
