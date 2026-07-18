"""Licensed native-16 facade stamps used by the strict reference map."""

from __future__ import annotations


def _spec(
    sector: str,
    key: str,
    file: str,
    source: str,
    digest: str,
    source_size: tuple[int, int],
    crop: tuple[int, int, int, int] | None,
    output_size: tuple[int, int],
    placement: tuple[int, int],
    *,
    pieces: tuple[tuple[tuple[int, int, int, int], tuple[int, int]], ...] = (),
) -> dict:
    return {
        "sector": sector, "asset_key": key, "file": file, "source": source,
        "sha256": digest, "source_size": source_size, "crop": crop,
        "output_size": output_size, "placement": placement, "pieces": pieces,
    }


MODULAR_BUILDING_ROOT = "5_Floor_Modular_Building_Singles_16x16"


def _source(file: str, digest: str, size: tuple[int, int]) -> dict:
    return {
        "source": f"{MODULAR_BUILDING_ROOT}/{file}",
        "sha256": digest,
        "source_size": size,
    }


RESIDENTIAL_SOURCES = {
    "condo_9": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_9.png",
        "6884fcb12f368c0987529bf0a35ce9e40c217444b76bf36c75830cc6386df47d",
        (112, 48),
    ),
    "condo_11": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_11.png",
        "52df46e8dfcc0213ef46dbd0664665b74a245438107b706570cf7504f598cebf",
        (112, 48),
    ),
    "condo_12": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_12.png",
        "2b6600be628fcfccfd78927ae23ec130065df525e34bda7279f64739e1c6845b",
        (112, 48),
    ),
    "module_17": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_Modular_17.png",
        "f99d7c3101d7a8bb82e3036f22f08ad3407126f0839189c1ae109fc6334466fa",
        (16, 48),
    ),
    "module_18": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_Modular_18.png",
        "8d305b09e8554cc5a9c2194a2f5599551325a9da8c664cc1b6455ce0ecae952b",
        (16, 48),
    ),
    "module_20": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_Modular_20.png",
        "f80dc0d979b789c5923dd3639f185ab4a83ac44f3ac312d656ffdd1fb2b4af7a",
        (16, 48),
    ),
    "module_21": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_Modular_21.png",
        "94583c628c7ba6c7f0893806d67a67c9eb895d5687b5c6a5d265d64faf9adcd0",
        (16, 48),
    ),
    "module_22": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_Modular_22.png",
        "53d030a694b642874cbfb435e70c26bfbe8b1ed69499d49dc5f1c2eeba60b015",
        (16, 48),
    ),
    "module_23": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_Modular_23.png",
        "df1f2a7e108369ee3355c5ef1765ebec398622b39a53deb0bd75dcee12e8c957",
        (16, 48),
    ),
    "module_24": _source(
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_Modular_24.png",
        "4cbdfa91774e4cd0191254140450431944773a39774e43e5249d224ebd922232",
        (16, 48),
    ),
}


def _graystone_spec(
    sector: str,
    source_keys: tuple[str, ...],
    placement: tuple[int, int],
) -> dict:
    pieces = []
    cursor = 0
    for source_key in source_keys:
        source = RESIDENTIAL_SOURCES[source_key]
        width, height = source["source_size"]
        pieces.append((source_key, (0, 0, width, height), (cursor, 0)))
        cursor += width
    slug = sector.lower().replace(" ", "_")
    return {
        "sector": sector,
        "asset_key": f"prop.design.frontage.{slug}_graystone",
        "file": f"frontage_{slug}_graystone.png",
        "output_size": (cursor, 48),
        "placement": placement,
        "source_keys": source_keys,
        "source_pieces": tuple(pieces),
    }


def _curated_spec(
    key: str,
    file: str,
    source: str,
    digest: str,
    source_size: tuple[int, int],
    crop: tuple[int, int, int, int] | None,
) -> dict:
    return {
        "asset_key": key, "file": file, "source": source,
        "sha256": digest, "source_size": source_size, "crop": crop,
    }


# Kept curated while the active map migrates from the rejected mixed frontages.
LEGACY_CURATED_SPECS = (
    _curated_spec(
        "prop.design.home_neutral_facade", "home_neutral_facade.png",
        f"{MODULAR_BUILDING_ROOT}/"
        "ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_12.png",
        "2b6600be628fcfccfd78927ae23ec130065df525e34bda7279f64739e1c6845b",
        (112, 48), None,
    ),
    *(
        _curated_spec(
            f"prop.design.frontage.home_{style}", f"frontage_home_{style}.png",
            f"24_Additional_Houses_Singles_16x16/{source}", digest, size, crop,
        )
        for style, source, digest, size, crop in (
            ("japanese", "24_Additional_Houses_Japanese_House_16x16.png", "fb4ecb7993483b9329b66e1c0ee469dda355703ae9f9e858d43df2058fb94c1e", (240, 224), (24, 144, 216, 224)),
            ("modern", "24_Additional_Houses_Modern_House_16x16.png", "152ec1020b696e9672d856510bfd5d93818b316baf375e78ca552379111acad7", (368, 224), (88, 144, 280, 224)),
            ("one_story", "24_Additional_Houses_One_Story_House_16x16.png", "22ec0a71329b0001123023339e01cf5b018e727848173370b2ab9ebe1b93593c", (256, 224), (32, 144, 224, 224)),
            ("terraced_1", "24_Additional_Houses_Terraced_House_1_16x16.png", "d7abe26b2f4830a2b0733cde164d9d8f27f03c1dcacf0959c372705211b32330", (192, 240), (0, 160, 192, 240)),
            ("terraced_3", "24_Additional_Houses_Terraced_House_3_16x16.png", "3508fbac644966d710b4203f5910bd886483d9b73213a252587e94494932158c", (192, 256), (0, 176, 192, 256)),
            ("terraced_4", "24_Additional_Houses_Terraced_House_4_16x16.png", "5f917c3a7b92baaf57b6cdcde42bb82e52fc12b001ce4c069fca249037392dfc", (192, 240), (0, 160, 192, 240)),
            ("terraced_5", "24_Additional_Houses_Terraced_House_5_16x16.png", "d3093475335f22d58648982c63cb07eee1c9f420de46a941a93af56c1d5aa109", (192, 240), (0, 160, 192, 240)),
        )
    ),
    *(
        _curated_spec(
            f"prop.design.frontage.home_villa_{number}",
            f"frontage_home_villa_{number}.png",
            f"7_Villas_Singles_16x16/ME_Singles_Villas_16x16_Villa_{number}.png",
            digest, (144, 208), (0, 128, 144, 208),
        )
        for number, digest in (
            (1, "0f553f6ec71d12a48a7003e3c0ff5888867ff6473498c26c3bf675e35afbdd6f"),
            (3, "ab4f50bc2f999864b96cb6dc2a1f765810a55135ef89c86a6cea3e364e17da45"),
        )
    ),
)


POST_PIECES = (
    ((0, 128, 16, 208), (0, 0)),
    *(((16, 128, 32, 208), (x, 0)) for x in range(16, 96, 16)),
    ((16, 128, 112, 208), (96, 0)),
    *(((96, 128, 112, 208), (x, 0)) for x in range(192, 272, 16)),
    ((112, 128, 128, 208), (272, 0)),
)
MARKET_PIECES = (
    ((0, 112, 16, 192), (0, 0)),
    *(((16, 112, 32, 192), (x, 0)) for x in range(16, 64, 16)),
    ((8, 112, 104, 192), (64, 0)),
    *(((80, 112, 96, 192), (x, 0)) for x in range(160, 208, 16)),
    ((96, 112, 112, 192), (208, 0)),
)

SPECS = (
    _spec(
        "Post Office", "prop.design.frontage.post_office", "frontage_post_office.png",
        "22_Post_Office_Singles_16x16/22_Post_Office_16x16_Building_1.png",
        "7ddfb15ad5e0b68fe10077e5cf023c9ac9a3013dc282514d39832b7e17489401",
        (128, 208), None, (288, 80), (158, 31), pieces=POST_PIECES,
    ),
    _spec(
        "University", "prop.design.frontage.university_left",
        "frontage_university_left.png",
        "13_School_Singles_16x16/ME_Singles_School_16x16_School_1.png",
        "100fd970c099b59c98b2a65a5d1c8081b28e44dcb052f40a9abcd31ad4e9a86d",
        (384, 368), (32, 240, 208, 304), (176, 64), (71, 22),
    ),
    _spec(
        "University", "prop.design.frontage.university_right",
        "frontage_university_right.png",
        "13_School_Singles_16x16/ME_Singles_School_16x16_School_1.png",
        "100fd970c099b59c98b2a65a5d1c8081b28e44dcb052f40a9abcd31ad4e9a86d",
        (384, 368), (192, 240, 352, 304), (160, 64), (93, 22),
    ),
    _spec(
        "Market", "prop.design.frontage.market", "frontage_market.png",
        "9_Shopping_Center_and_Markets_Singles_16x16/"
        "ME_Singles_Shopping_Center_and_Markets_16x16_Market_Big_1.png",
        "29a57796ac58328a0861e4a0c60bcad8db59885f3ba0f7f3be67d0250b9bcde2",
        (112, 192), None, (224, 80), (147, 25), pieces=MARKET_PIECES,
    ),
    _spec(
        "Town Hall", "prop.design.frontage.town_hall", "frontage_town_hall.png",
        "17_Garden_Singles_16x16/ME_Singles_Garden_16x16_Palace_Example_1.png",
        "5ef609940283b5d07344bba9ca00e418928427ae331a323524c77961a07c60df",
        (400, 544), (64, 384, 336, 464), (272, 80), (78, 82),
    ),
)

RESIDENTIAL_SPECS = (
    _graystone_spec(
        "Home 1",
        (
            "module_23", "module_17", "module_20", "module_18",
            "module_21", "module_22", "condo_12", "module_18",
            "module_17", "module_20", "module_23", "module_21",
            "module_22", "module_18", "module_24",
        ),
        (44, 27),
    ),
    _graystone_spec(
        "Home 2",
        (
            "module_17", "module_20", "condo_12", "module_21",
            "module_22", "module_18", "module_24",
        ),
        (5, 84),
    ),
    _graystone_spec(
        "Home 3",
        (
            "module_18", "condo_11", "module_17", "module_20",
            "module_23", "module_24",
        ),
        (21, 84),
    ),
    _graystone_spec(
        "Home 4",
        (
            "module_21", "condo_12", "module_24",
        ),
        (41, 84),
    ),
    _graystone_spec(
        "Home 5",
        (
            "module_18", "condo_9", "module_23", "module_24",
        ),
        (50, 84),
    ),
    _graystone_spec(
        "Home 6",
        (
            "module_21", "condo_11", "module_22", "module_24",
        ),
        (60, 84),
    ),
    _graystone_spec(
        "Home 7",
        (
            "module_23", "condo_11", "module_21", "module_22",
            "module_18", "module_24",
        ),
        (106, 84),
    ),
    _graystone_spec(
        "Home 8",
        (
            "module_17", "module_20", "condo_12", "module_18",
            "module_21", "module_22", "module_24",
        ),
        (121, 84),
    ),
    _graystone_spec(
        "Home 9",
        (
            "condo_9", "module_21", "module_22", "module_18",
            "module_23", "module_24",
        ),
        (141, 84),
    ),
    _graystone_spec(
        "Home 10",
        (
            "condo_9", "module_17", "module_20", "module_18",
            "module_23", "module_24",
        ),
        (155, 84),
    ),
)

CIVIC_GRAYSTONE_SPECS = (
    _graystone_spec(
        "Bank",
        (
            "module_23", "module_17", "module_20", "module_18",
            "module_21", "module_22", "module_18", "condo_12",
            "module_17", "module_20", "module_23", "module_21",
            "module_22", "module_18", "module_23", "module_24",
        ),
        (8, 27),
    ),
    _graystone_spec(
        "Agent Academy",
        (
            "module_18", "module_21", "module_22", "module_23",
            "module_17", "module_20", "module_18", "condo_9",
            "module_21", "module_22", "module_18", "module_17",
            "module_20", "module_23", "module_18", "module_23", "module_24",
        ),
        (109, 27),
    ),
    _graystone_spec(
        "Workshop",
        (
            "module_23", "module_21", "module_22", "module_18",
            "module_17", "module_20", "condo_11", "module_18",
            "module_21", "module_22", "module_23", "module_17",
            "module_20", "module_18", "module_23", "module_24",
        ),
        (8, 57),
    ),
    _graystone_spec(
        "Community Center",
        (
            "module_17", "module_20", "condo_12", "module_18",
            "module_23", "module_24",
        ),
        (44, 57),
    ),
    _graystone_spec(
        "Claudeville Cafe",
        (
            "module_21", "condo_9", "module_22", "module_18",
            "module_23", "module_24",
        ),
        (56, 57),
    ),
    _graystone_spec(
        "Library",
        (
            "module_23", "module_17", "module_20", "module_18",
            "module_21", "module_22", "module_18", "module_17",
            "module_20", "condo_11", "module_17", "module_20",
            "module_21", "module_22", "module_18", "module_23",
            "module_21", "module_22", "module_24",
        ),
        (144, 69),
    ),
)
GRAYSTONE_SPECS = (*RESIDENTIAL_SPECS, *CIVIC_GRAYSTONE_SPECS)
ALL_SPECS = (*SPECS, *GRAYSTONE_SPECS)
RESIDENTIAL_STAMPED_SECTORS: frozenset[str] = frozenset({"Home 1"})
STAMPED_SECTORS: frozenset[str] = frozenset({
    "Bank",
    "Home 1",
    "University",
    "Agent Academy",
    "Market",
    "Post Office",
    "Workshop",
    "Community Center",
    "Claudeville Cafe",
    "Library",
})
PLACEMENTS: tuple[tuple, ...] = ()
RESIDENTIAL_PLACEMENTS: tuple[tuple, ...] = ()
CIVIC_GRAYSTONE_PLACEMENTS: tuple[tuple, ...] = ()


def validate() -> None:
    if len({spec["asset_key"] for spec in ALL_SPECS}) != len(ALL_SPECS):
        raise ValueError("duplicate reference facade stamp key")
    if PLACEMENTS:
        raise ValueError("facade placement belongs to the reference stamp manifest")
    if not RESIDENTIAL_STAMPED_SECTORS <= STAMPED_SECTORS:
        raise ValueError("residential stamped sectors must be active stamped sectors")
    for spec in GRAYSTONE_SPECS:
        width, height = spec["output_size"]
        if width <= 0 or height != 48:
            raise ValueError(f"{spec['sector']} archived graystone source is malformed")
        cursor = 0
        core_count = 0
        for source_key, crop, destination in spec["source_pieces"]:
            source = RESIDENTIAL_SOURCES[source_key]
            source_width, source_height = source["source_size"]
            if crop != (0, 0, source_width, source_height):
                raise ValueError("graystone frontage source crop changed")
            if destination != (cursor, 0):
                raise ValueError("graystone frontage pieces must be contiguous")
            cursor += source_width
            core_count += int(source_key.startswith("condo_"))
        if cursor != width or core_count != 1:
            raise ValueError(f"{spec['sector']} graystone frontage is malformed")


validate()
