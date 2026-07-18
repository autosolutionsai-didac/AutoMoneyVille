"""Validate and pack curated object art for the Claudeville runtime atlas."""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from PIL import Image

try:
    from tools.mapgen import claudeville_reference_facade_assets
except ModuleNotFoundError:  # Direct mapgen script execution.
    import claudeville_reference_facade_assets

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DESIGN_STAMP_ROOT = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/visuals/stamps"
)
MAX_ATLAS_SIZE = 4096
CATALOG_GENERATOR = "tools/mapgen/curate_claudeville_design_stamps.py"
LICENSE_SCOPE = "Curated derivatives only; vendor sources are not shipped."
APPROVED_DESIGN_STAMPS = {
    "prop.design.bank_suite": {
        "file": "bank_suite.png",
        "native_size": [199, 182],
        "output_sha256": "a3adf34a5f84af2fa2ec3339f5c314112c920a0f1e59994074835cc2e2e596d6",
        "pack": "Modern Office Revamped",
        "source_sha256": "bff7b0206aceb2b7db0680ec00eb2719ac2aba60ab0287f0ecece5ad1352596e",
        "trim_offset": [0, 0],
    },
    "prop.design.bank_operations_east": {
        "file": "bank_operations_east.png",
        "native_size": [144, 160],
        "output_sha256": "08f78260ca993bae492bc19786b06dab6133a708710ec228b2c3a584853abc7f",
        "pack": "Modern Office Revamped",
        "source_sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "trim_offset": [0, 0],
    },
    "prop.design.academy_lab": {
        "file": "academy_lab.png",
        "native_size": [160, 160],
        "output_sha256": "abedd34a9cc000d76dfc7e46a0aa3dabd60e0a43c8b04c51dc497b0465742640",
        "pack": "Modern Office Revamped",
        "source_sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "trim_offset": [0, 0],
    },
    "prop.design.bank_office": {
        "file": "bank_office.png",
        "native_size": [192, 173],
        "output_sha256": "d2708c1d339bf9c673d4e4a6eb16125f45e84987b1373f283a616d21462a3eb3",
        "pack": "Modern Office Revamped",
        "source_sha256": "bff7b0206aceb2b7db0680ec00eb2719ac2aba60ab0287f0ecece5ad1352596e",
        "trim_offset": [0, 3],
    },
    "prop.design.home_japanese": {
        "file": "home_japanese.png",
        "native_size": [272, 202],
        "output_sha256": "e50806b7b3d601779acb75fac4f6859f3f15ab04aab2203b3ab71f53eeb4007b",
        "pack": "Modern Interiors",
        "sources": [
            {
                "name": "Japanese_Home_1_Layer_2_16x16.png",
                "sha256": "e021694541db0c4b36f8337a225f85cb7f8ce3b0dff8d93b33a7fc6b50b182c9",
            },
        ],
        "trim_offset": [16, 6],
    },
    "prop.design.university_lab": {
        "file": "university_lab.png",
        "native_size": [221, 253],
        "output_sha256": "80f4a936cba115225f77ccf72a0fb9f79f876cf4b437dbe9ecfe550fee89cf4f",
        "pack": "Modern Office Revamped",
        "source_sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "trim_offset": [19, 3],
    },
    "prop.design.university_floor": {
        "file": "university_floor.png",
        "native_size": [247, 262],
        "output_sha256": "370c0d0eda5f17c6f1a75abc1637bd2a3a60bb1d7203696b5bc42a62785e91b5",
        "pack": "Modern Office Revamped",
        "source_sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "trim_offset": [0, 0],
    },
    "prop.design.university_lab_main": {
        "file": "university_lab_main.png",
        "native_size": [221, 157],
        "output_sha256": "dc500b4197e3d5375e968a857e8659e4d1ed9432a486e5d4e795487528da40cd",
        "pack": "Modern Office Revamped",
        "source_sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "trim_offset": [19, 3],
    },
    "prop.design.university_lounge": {
        "file": "university_lounge.png",
        "native_size": [176, 80],
        "output_sha256": "2167bc19221c64dbd37496c43d1a34eee5df357e8e63da49e80212f61735e9be",
        "pack": "Modern Office Revamped",
        "source_sha256": "cac42f25c080f57313e7cb25e3a2d309bee6ba390a8ba4abc8986b8c119adfdd",
        "trim_offset": [8, 16],
    },
}
_ADDITIONAL_DESIGN_STAMPS = (
    ('prop.design.community_presentation_room', 'community_presentation_room.png', (176, 160), 'a6244f5f652721bcc12ecd52c51948bff30be400549389072e7e6f19a216257f', 'Modern Interiors', (('Tv_Studio_Design_layer_1.png', 'f01894014c63373a08ff450662dc8a4711cf2a4571f29c197fa1bef885613b58'), ('Tv_Studio_Design_layer_3.png', '7b1c1ef2d3d7ae6c042526cf0c41c54a2d1a49c691dc4b5d8bfc8eebf454382a'), ('Tv_Studio_Design_layer_2.png', '88261200ed01900e7742b9a7f71d814744816bce69b6dda9b40a22485ebb8206'))),
    ('prop.design.community_studio', 'community_studio.png', (176, 160),
     'abc40a6037505c29fafdbead8e12ee3f94085553940c5f05f58a82d2133da2b7', 'Modern Interiors', (('Tv_Studio_Design_layer_1.png', 'f01894014c63373a08ff450662dc8a4711cf2a4571f29c197fa1bef885613b58'), ('Tv_Studio_Design_layer_2.png', '88261200ed01900e7742b9a7f71d814744816bce69b6dda9b40a22485ebb8206'), ('Tv_Studio_Design_layer_3.png', '7b1c1ef2d3d7ae6c042526cf0c41c54a2d1a49c691dc4b5d8bfc8eebf454382a'))),
    ('prop.design.community_foyer', 'community_foyer.png', (192, 96),
     '3ff332ab2b17e83ce314e25d12b1676aba66af5be445ba14f16b73e9dbbd5049', 'Modern Interiors', (('Condominium_Design_2_layer_1.png', '15e0579efa62a5cdbfa313ba3de65e16e461701405c96e2bcaef61fa254f3fd6'), ('Condominium_Design_2_layer_2.png', '6a58df08e47c3dced8c745998ecf820a0f0309f0a1be503e052e1f5d32f7d62e'))),
    ('prop.design.academy_gym_compact', 'academy_gym_compact.png', (192, 112),
     '3f41f818fec084f40d880b1aed5bc76c9caf3d8d1deeee83184b7d0b1c54a374', 'Modern Interiors', (('Gym_2_layer_1.png', 'd961b76ece1f72ac4d44b975470606d93c3f8e90e25d30aa5e34eac2148aebf1'), ('Gym_2_layer_2.png', '5dbe546cf03c71442cc5efed59644eb975ab248396e73bc568aff7c1a62ecbcb'))),
    ('prop.design.academy_gym', 'academy_gym.png', (304, 240),
     '5c7ce03ce92e1ead90fdf2f073e7f527eab5153373dca8c1237fbeb0e5b25889', 'Modern Interiors', (('Gym_layer_1.png', '3145ea6bfe034b196a9e9d01a2d521b549e9712469643a3255b036ef200c99e1'), ('Gym_layer_2.png', 'f839307e617272a8d696cb9efd4bae83493d0a1138fdb99c5534f7d3eebeba63'))),
    ('prop.design.community_cafe', 'community_cafe.png', (192, 160),
     '83dfbc149612af86892aeb711f0afaff736f8873f64e704c2822cab8ecb0794b', 'Modern Interiors', (('Ice_Cream_Shop_Design_layer_2.png', 'd6600b2fd9daf56e535dfb8c7e544e8170a5895b3b83e0847d2298c44748aa91'), ('Ice_Cream_Shop_Design_layer_3.png', '21c1d36fddbc57726a83f7b6f9dd3dca078bfedb635bf11c5aa586e5c7aa652c'))),
    ('prop.design.cafe_complete', 'cafe_complete.png', (192, 160),
     '91d1fff67017d75d7d9a3d17b0af4c85ba873459bdaa008c936cf21bcb2f657f', 'Modern Interiors', (('Ice_Cream_Shop_Design_layer_1.png', '1bbba36a51727f3acb6eea3a6aaaf4a02ac167093df453f445c4980d99320038'), ('Ice_Cream_Shop_Design_layer_2.png', 'd6600b2fd9daf56e535dfb8c7e544e8170a5895b3b83e0847d2298c44748aa91'), ('Ice_Cream_Shop_Design_layer_3.png', '21c1d36fddbc57726a83f7b6f9dd3dca078bfedb635bf11c5aa586e5c7aa652c'))),
    ('prop.design.frontage.post_office', 'frontage_post_office.png', (288, 80),
     'f4d0cf5fd1300112047a1d73f43ff82e3e108eff74f16f4b16c18172a39ce70e', 'Modern Exteriors', (('22_Post_Office_16x16_Building_1.png', '7ddfb15ad5e0b68fe10077e5cf023c9ac9a3013dc282514d39832b7e17489401'),)),
    ('prop.design.frontage.university_left', 'frontage_university_left.png', (176, 64),
     '3e2b969545103504a09d8349eb8233f967c354c2347d4bf8132e861ca377349b', 'Modern Exteriors', (('ME_Singles_School_16x16_School_1.png', '100fd970c099b59c98b2a65a5d1c8081b28e44dcb052f40a9abcd31ad4e9a86d'),)),
    ('prop.design.frontage.university_right', 'frontage_university_right.png', (160, 64),
     '5a2fdc35ac5661766abe8d7c4bb30811ae42473f3fe32a6c412b3040f93527ea', 'Modern Exteriors', (('ME_Singles_School_16x16_School_1.png', '100fd970c099b59c98b2a65a5d1c8081b28e44dcb052f40a9abcd31ad4e9a86d'),)),
    ('prop.design.frontage.market', 'frontage_market.png', (224, 80),
     'ac82e529522ebfbf88771ec21df2ee54dadb9899500d53c04bd6f91174149717', 'Modern Exteriors', (('ME_Singles_Shopping_Center_and_Markets_16x16_Market_Big_1.png', '29a57796ac58328a0861e4a0c60bcad8db59885f3ba0f7f3be67d0250b9bcde2'),)),
    ('prop.design.frontage.town_hall', 'frontage_town_hall.png', (272, 80),
     'ff1b6bfa3ce2ffd711ef1753966f8ca93009f4e46c9d90f270fca146d950772e', 'Modern Exteriors', (('ME_Singles_Garden_16x16_Palace_Example_1.png', '5ef609940283b5d07344bba9ca00e418928427ae331a323524c77961a07c60df'),)),
    ('prop.design.frontage.home_japanese', 'frontage_home_japanese.png', (192, 80),
     '3623449ebd31842c87c94ed8fedcdd2347dc4dd1e3336f896194c6e763a08c2a', 'Modern Exteriors', (('24_Additional_Houses_Japanese_House_16x16.png', 'fb4ecb7993483b9329b66e1c0ee469dda355703ae9f9e858d43df2058fb94c1e'),)),
    ('prop.design.frontage.home_modern', 'frontage_home_modern.png', (192, 80),
     'bfa30f59dd8879340974c619b53c953bd0278cf022d8b9c075188767de76699e', 'Modern Exteriors', (('24_Additional_Houses_Modern_House_16x16.png', '152ec1020b696e9672d856510bfd5d93818b316baf375e78ca552379111acad7'),)),
    ('prop.design.frontage.home_one_story', 'frontage_home_one_story.png', (192, 80),
     '669c0f97bc1c9357a5be6a10697b3fd900f632b9f5d148c371de731f3e969059', 'Modern Exteriors', (('24_Additional_Houses_One_Story_House_16x16.png', '22ec0a71329b0001123023339e01cf5b018e727848173370b2ab9ebe1b93593c'),)),
    ('prop.design.frontage.home_terraced_1', 'frontage_home_terraced_1.png', (192, 80),
     '833287ad6ae5ea43b2fbf071bb1c80e948c53200a97a1ee02943efdcd6373316', 'Modern Exteriors', (('24_Additional_Houses_Terraced_House_1_16x16.png', 'd7abe26b2f4830a2b0733cde164d9d8f27f03c1dcacf0959c372705211b32330'),)),
    ('prop.design.frontage.home_terraced_3', 'frontage_home_terraced_3.png', (192, 80),
     '5ade884ebcd08abe9b6fb9f4406dcea20f25a3c016741b8d78437219b5e012f6', 'Modern Exteriors', (('24_Additional_Houses_Terraced_House_3_16x16.png', '3508fbac644966d710b4203f5910bd886483d9b73213a252587e94494932158c'),)),
    ('prop.design.frontage.home_terraced_4', 'frontage_home_terraced_4.png', (192, 80),
     'a20d2352495e62405fe13abba31f151e55b658921fedab4a238db5428180ccfa', 'Modern Exteriors', (('24_Additional_Houses_Terraced_House_4_16x16.png', '5f917c3a7b92baaf57b6cdcde42bb82e52fc12b001ce4c069fca249037392dfc'),)),
    ('prop.design.frontage.home_terraced_5', 'frontage_home_terraced_5.png', (192, 80),
     'd7a5918a57427f095d899c903cbdefec9e90ce89820602c993ea372e4a58289e', 'Modern Exteriors', (('24_Additional_Houses_Terraced_House_5_16x16.png', 'd3093475335f22d58648982c63cb07eee1c9f420de46a941a93af56c1d5aa109'),)),
    ('prop.design.frontage.home_villa_1', 'frontage_home_villa_1.png', (144, 80),
     'fd000638bc767be86d73869db0e8cbca648152f1f0d36acd22e45d4541af3eb1', 'Modern Exteriors', (('ME_Singles_Villas_16x16_Villa_1.png', '0f553f6ec71d12a48a7003e3c0ff5888867ff6473498c26c3bf675e35afbdd6f'),)),
    ('prop.design.frontage.home_villa_3', 'frontage_home_villa_3.png', (144, 80),
     'e34f6560225d085d43e301ba3d2f95f731ddb3f3f234f3fd6a0168774ec9fa02', 'Modern Exteriors', (('ME_Singles_Villas_16x16_Villa_3.png', 'ab4f50bc2f999864b96cb6dc2a1f765810a55135ef89c86a6cea3e364e17da45'),)),
    ('prop.design.home_neutral_facade', 'home_neutral_facade.png', (112, 48),
     '5d7e038ce7f586619f2bfedf5521fb4bc8fde719e66ddc5448d6d8ba2d38af77', 'Modern Exteriors', (('ME_Singles_Floor_Modular_Building_16x16_Ground_Floor_Condo_12.png', '2b6600be628fcfccfd78927ae23ec130065df525e34bda7279f64739e1c6845b'),)),
    ('prop.design.home_cluster.generic_ne', 'home_cluster_generic_ne.png', (112, 112),
     'c7064a51ebf7ee1849a9c85be5b5c4d51407648ca5af7111d6f417a7c0460067', 'Modern Interiors', (('Generic_Home_1_Layer_2_.png', '095ecd0fba6fbcf92dbcb2f71a3ea89af90bdedf81f8cde90cc53da67ad32332'),)),
    ('prop.design.home_cluster.generic_nw', 'home_cluster_generic_nw.png', (112, 112),
     '3cbfb785fdd1c9516ac5c416b5028d944f318fe04c459fa20870db96cc158a34', 'Modern Interiors', (('Generic_Home_1_Layer_2_.png', '095ecd0fba6fbcf92dbcb2f71a3ea89af90bdedf81f8cde90cc53da67ad32332'),)),
    ('prop.design.home_cluster.generic_south', 'home_cluster_generic_south.png', (160, 118),
     'c0e24ae48fe3125027a29e05577ab64a0b808b885d383aec3249cef20300b201', 'Modern Interiors', (('Generic_Home_1_Layer_2_.png', '095ecd0fba6fbcf92dbcb2f71a3ea89af90bdedf81f8cde90cc53da67ad32332'),)),
    ('prop.design.home_cluster.japanese_ne', 'home_cluster_japanese_ne.png', (128, 112),
     '9a020a272001b409e3696144b3ae93e3fe29279026c9d13df06d6a2fafc6b733', 'Modern Interiors', (('Japanese_Home_1_Layer_2_16x16.png', 'e021694541db0c4b36f8337a225f85cb7f8ce3b0dff8d93b33a7fc6b50b182c9'),)),
    ('prop.design.home_cluster.japanese_nw', 'home_cluster_japanese_nw.png', (128, 112),
     'f9087afd10b984f880d0994754e300f06fb761858f7a3dbb6fbc26f90851c0a3', 'Modern Interiors', (('Japanese_Home_1_Layer_2_16x16.png', 'e021694541db0c4b36f8337a225f85cb7f8ce3b0dff8d93b33a7fc6b50b182c9'),)),
    ('prop.design.home_cluster.japanese_se', 'home_cluster_japanese_se.png', (144, 112),
     '30dca855d4ed63b4ab55bd2530776cf98763a2e1d9fcfeb0ad4524c43c5521e4', 'Modern Interiors', (('Japanese_Home_1_Layer_2_16x16.png', 'e021694541db0c4b36f8337a225f85cb7f8ce3b0dff8d93b33a7fc6b50b182c9'),)),
    ('prop.design.home_cluster.japanese_sw', 'home_cluster_japanese_sw.png', (144, 112),
     '0115fc6bb6f6cfe1c9b2466aee8cc0b3ebf378b0c5755f452dc9b3292bd0d0e1', 'Modern Interiors', (('Japanese_Home_1_Layer_2_16x16.png', 'e021694541db0c4b36f8337a225f85cb7f8ce3b0dff8d93b33a7fc6b50b182c9'),)),
    ('prop.design.home_generic', 'home_generic.png', (224, 214),
     'e099bb9d41cf6e337ee379559cefd568e44ca63068506f58e3451356aa98f916', 'Modern Interiors', (('Generic_Home_1_Layer_1.png', '24effc29867409ec5abfd946f0b731f5212637ff722729dd0d52d86e4c91761c'), ('Generic_Home_1_Layer_2_.png', '095ecd0fba6fbcf92dbcb2f71a3ea89af90bdedf81f8cde90cc53da67ad32332'))),
)
APPROVED_DESIGN_STAMPS.update({
    key: {
        "file": file, "native_size": list(size), "output_sha256": output_sha256,
        "pack": pack, "sources": [
            {"name": name, "sha256": digest} for name, digest in sources
        ], "trim_offset": [0, 0],
    }
    for key, file, size, output_sha256, pack, sources in _ADDITIONAL_DESIGN_STAMPS
})
_GRAYSTONE_OUTPUT_SHA256 = {
    "Bank": "5f2f7c7e4bf5b0391b72c52366d2068e8f513924a6ca034f88501acdfadd73a4",
    "Agent Academy": "811a61ef4295de0acb064526bda5b22a595a918757c75906d09f5cf6a0402ba7",
    "Workshop": "0b86adde4a9bb1ed69e29dfbbcbbb61876ccb609f32fbd18cf8fd3aeea8f6dd7",
    "Community Center": "714188bd07b74f1dd0a1850c9b6c854e15b092b80758b6c0eac70ab0f40de93c",
    "Claudeville Cafe": "3d0d630d0017767be9e730b21b89ab2a1cb61b072a14ccf6da6db39609c26516",
    "Library": "69387f6e3b4495c5c9408f743839e6ac5a0e416dd00020c348f222a71f332244",
    "Home 1": "e4a277b97087c91d353dabbc84d3485dffdf246e34a815484d2d267d8d269ba2",
    "Home 2": "3032972ae82e21d53d596ffa8d04350c0a0fa2988a398e7ec20abf9518368b39",
    "Home 3": "f19c55e3faa768a717901b01fc437075b7e16f2a1d5d1fdcd8e4da2cb79d047d",
    "Home 4": "e5c20a545cd78d8922a70a5bbaace419f1fdac9f3f1f1b72d9286b57a42f21b1",
    "Home 5": "06f7e5a7482f0d55695256418769eadc5a4c49289da99405f944ff130a9b359f",
    "Home 6": "7974fa18e3662203de21921694e735ce117f4014253b54af6665dc6e93ce5830",
    "Home 7": "5c1d266805c22eb8771e6d184a0b018997600dc1714ae468e361870a2a9352b7",
    "Home 8": "87308cd0db258418f659ecf5814579cc320d9b5dd566d5335f5ea9043e695a8a",
    "Home 9": "c5f295b2480c4faff1e0eb0fcafdf85fb89411bf3c76bb91c31c7957b366e3ea",
    "Home 10": "32d97b79b61c37f4718b9cbeb11f3e3dd828457ac772069e621d848b1a3a2bf5",
}
APPROVED_DESIGN_STAMPS.update({
    spec["asset_key"]: {
        "file": spec["file"], "native_size": list(spec["output_size"]),
        "output_sha256": _GRAYSTONE_OUTPUT_SHA256[spec["sector"]],
        "pack": "Modern Exteriors",
        "sources": [
            {"name": Path(source["source"]).name, "sha256": source["sha256"]}
            for source in {
                key: claudeville_reference_facade_assets.RESIDENTIAL_SOURCES[key]
                for key in spec["source_keys"]
            }.values()
        ],
        "trim_offset": [0, 0],
    }
    for spec in claudeville_reference_facade_assets.GRAYSTONE_SPECS
})
APPROVED_PACK_CREDITS = {
    "Modern Exteriors": {
        "name": "Modern Exteriors",
        "creator": "LimeZu",
        "license_file": "modernexteriors-win/Modern_Exteriors_License.pdf",
        "license_sha256": "64aae67044ccfc7e1e059a49b4a30de438e7834bbf7efdcd59bc9902457b6ec1",
        "source_url": "https://limezu.itch.io/modernexteriors",
    },
    "Modern Office Revamped": {
        "name": "Modern Office Revamped",
        "creator": "LimeZu",
        "license_file": "Modern_Office_Revamped_v1.2/LICENSE.txt",
        "license_sha256": "ac9ae86ccbdb3a1e28433e8f6516968c18a1ad55bfea089de423afa4027a689f",
        "source_url": "https://limezu.itch.io/modernoffice",
    },
    "Modern Interiors": {
        "name": "Modern Interiors",
        "creator": "LimeZu",
        "license_file": "moderninteriors-win/LICENSE.txt",
        "license_sha256": "e33effd51253bb90c0d83fb555405f300273e9772d5eb84105327b6fa3eab4c5",
        "source_url": "https://limezu.itch.io/moderninteriors",
    },
}


class PropAtlasError(ValueError):
    """Raised when curated object art cannot be trusted or packed safely."""


def _read_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise PropAtlasError(f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PropAtlasError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise PropAtlasError(f"{label} root must be an object")
    return value


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _write_png(path: Path, image: Image.Image) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    image.save(temporary, format="PNG", compress_level=9, optimize=False)
    temporary.replace(path)


def _contained_file(root: Path, filename: object, label: str) -> Path:
    if not isinstance(filename, str) or Path(filename).name != filename:
        raise PropAtlasError(f"{label} path is malformed")
    boundary = root.resolve()
    path = (boundary / filename).resolve(strict=False)
    if boundary not in path.parents or not path.is_file():
        raise PropAtlasError(f"{label} escapes the curated stamp root")
    return path


def _validate_stamp_image(path: Path, expected: dict) -> None:
    digest = sha256(path.read_bytes()).hexdigest()
    if digest != expected["output_sha256"]:
        raise PropAtlasError(f"curated design stamp hash changed: {path.name}")
    try:
        with Image.open(path) as image:
            if image.format != "PNG" or list(image.size) != expected["native_size"]:
                raise PropAtlasError(f"curated design stamp image changed: {path.name}")
            if image.width > MAX_ATLAS_SIZE or image.height > MAX_ATLAS_SIZE:
                raise PropAtlasError(f"curated design stamp is oversized: {path.name}")
            image.verify()
    except (OSError, SyntaxError) as exc:
        raise PropAtlasError(f"curated design stamp PNG is invalid: {path.name}") from exc


def load_design_stamps(
    root: Path, requested: list[str]
) -> tuple[dict[str, dict], str | None, dict[str, dict]]:
    """Return verified records for requested allow-listed design-stamp keys."""
    design_keys = sorted({key for key in requested if key.startswith("prop.design.")})
    if not design_keys:
        return {}, None, {}
    unknown = sorted(set(design_keys) - APPROVED_DESIGN_STAMPS.keys())
    if unknown:
        raise PropAtlasError(f"unapproved curated design stamps: {unknown}")
    try:
        boundary = Path(root).expanduser().resolve(strict=True)
    except OSError as exc:
        raise PropAtlasError(f"curated design stamp root is missing: {root}") from exc
    if not boundary.is_dir():
        raise PropAtlasError(f"curated design stamp root is not a directory: {root}")
    catalog_path = boundary / "catalog.json"
    catalog = _read_json(catalog_path, "curated design stamp catalog")
    if (
        catalog.get("schema_version") != 1
        or catalog.get("generated_by") != CATALOG_GENERATOR
        or catalog.get("license_scope") != LICENSE_SCOPE
    ):
        raise PropAtlasError("curated design stamp catalog contract changed")
    records = catalog.get("records")
    if not isinstance(records, list):
        raise PropAtlasError("curated design stamp catalog records are missing")
    by_key = {
        item.get("asset_key"): item
        for item in records
        if isinstance(item, dict) and isinstance(item.get("asset_key"), str)
    }
    if len(by_key) != len(records):
        raise PropAtlasError("curated design stamp catalog contains malformed duplicates")
    credits = catalog.get("pack_credits")
    expected_credits = [APPROVED_PACK_CREDITS[key] for key in sorted(APPROVED_PACK_CREDITS)]
    if credits != expected_credits:
        raise PropAtlasError("curated design stamp license evidence changed")
    selected = {}
    for key in design_keys:
        record, expected = by_key[key], APPROVED_DESIGN_STAMPS[key]
        if record != {"asset_key": key, **expected}:
            raise PropAtlasError(f"curated design stamp catalog record changed: {key}")
        path = _contained_file(boundary, record.get("file"), f"design stamp {key}")
        _validate_stamp_image(path, expected)
        selected[key] = {**record, "path": path}
    catalog_bytes = catalog_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return (
        selected,
        sha256(catalog_bytes).hexdigest(),
        {record["name"]: record for record in credits},
    )


def merge_pack_credits(
    source_credits: dict, stamp_credits: dict[str, dict], design_stamps: dict[str, dict]
) -> dict:
    """Replace selected stamp-pack credits with catalog-verified license evidence."""
    records = source_credits.get("packs")
    if not isinstance(records, list):
        raise PropAtlasError("design stamp pack credits are missing")
    by_name = {
        item.get("name"): item
        for item in records
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    if len(by_name) != len(records):
        raise PropAtlasError("design stamp pack credits contain malformed duplicates")
    selected_packs = sorted({record["pack"] for record in design_stamps.values()})
    if any(pack not in stamp_credits for pack in selected_packs):
        raise PropAtlasError("used design stamp packs have missing verified credits")
    merged_records = [stamp_credits.get(item["name"], item) for item in records]
    merged_names = {record["name"] for record in merged_records}
    merged_records.extend(
        stamp_credits[pack] for pack in selected_packs if pack not in merged_names
    )
    merged = dict(source_credits)
    merged["packs"] = merged_records
    return merged


def merge_prop_provenance(prop_catalog: dict, design_stamps: dict[str, dict]) -> dict:
    """Add verified stamp pack records to a copy of the V2 prop catalog."""
    records = prop_catalog.get("props")
    if not isinstance(records, list):
        raise PropAtlasError("authoring prop catalog is malformed")
    merged = dict(prop_catalog)
    merged["props"] = [
        *records,
        *(
            {"asset_key": key, "pack": record["pack"]}
            for key, record in sorted(design_stamps.items())
        ),
    ]
    return merged


def validate_requested_props(
    authoring: Path, v3: dict[str, dict], design_stamps: dict[str, dict],
    requested: list[str],
) -> dict:
    """Validate that each requested key resolves in exactly one approved catalog."""
    frames = _read_json(authoring / "props.json", "authoring props metadata").get("frames")
    if not isinstance(frames, dict):
        raise PropAtlasError("authoring props metadata is missing frames")
    catalogs = (set(frames), set(v3), set(design_stamps))
    missing = sorted(
        key for key in requested if not any(key in catalog for catalog in catalogs)
    )
    if missing:
        raise PropAtlasError(
            f"TMJ object assets are missing from props in approved catalogs: {missing}"
        )
    duplicate = sorted(key for key in requested if sum(
        key in catalog for catalog in catalogs
    ) > 1)
    if duplicate:
        raise PropAtlasError(
            f"TMJ object assets are duplicated in approved prop catalogs: {duplicate}"
        )
    return frames


def pack_props(images: list[tuple[str, Image.Image]]):
    """Pack requested images in stable key order into one bounded square-ish page."""
    for width in (256, 512, 1024, 2048, MAX_ATLAS_SIZE):
        if any(image.width + 4 > width for _, image in images):
            continue
        x = y = row_height = 2
        placements = []
        for key, image in images:
            if x + image.width + 2 > width:
                x, y, row_height = 2, y + row_height + 2, 0
            placements.append((key, image, x, y))
            x += image.width + 2
            row_height = max(row_height, image.height)
        height = y + row_height + 2
        if height <= width and height <= MAX_ATLAS_SIZE:
            return width, height, placements
    raise PropAtlasError("runtime prop atlas would exceed 4096x4096")


def _v2_image(source: Image.Image, key: str, frames: dict) -> Image.Image:
    record = frames.get(key)
    frame = record.get("frame") if isinstance(record, dict) else None
    if not isinstance(frame, dict) or not all(
        isinstance(frame.get(axis), int) and not isinstance(frame.get(axis), bool)
        for axis in ("x", "y", "w", "h")
    ):
        raise PropAtlasError(f"authoring prop frame is malformed: {key}")
    x, y, width, height = (frame[axis] for axis in ("x", "y", "w", "h"))
    if min(x, y) < 0 or min(width, height) < 1 or x + width > source.width or \
            y + height > source.height:
        raise PropAtlasError(f"authoring prop frame escapes its atlas: {key}")
    return source.crop((x, y, x + width, y + height))


def _open_rgba(path: Path, label: str) -> Image.Image:
    try:
        with Image.open(path) as opened:
            return opened.convert("RGBA")
    except (OSError, SyntaxError) as exc:
        raise PropAtlasError(f"{label} is not a valid image") from exc


def write_runtime_props(
    output: Path, authoring: Path, v3_source: Path | None, requested: list[str],
    frames: dict, v3: dict[str, dict], design_stamps: dict[str, dict],
):
    from tools.mapgen.tilemap_prop_writer import write_runtime_props as write

    return write(
        output, authoring, v3_source, requested, frames, v3, design_stamps
    )
