"""Hand-configured rowhouses and licensed transparent sprite compositions."""

from __future__ import annotations

HOME_BOUNDS = {
    "Home 2": (27, 80, 39, 96), "Home 3": (39, 80, 51, 96),
    "Home 4": (67, 80, 75, 96), "Home 5": (75, 80, 83, 96),
    "Home 6": (83, 80, 91, 96), "Home 7": (118, 80, 128, 96),
    "Home 8": (128, 80, 137, 96), "Home 9": (143, 80, 150, 96),
    "Home 10": (150, 80, 158, 96),
}
HOME_TARGETS = frozenset(HOME_BOUNDS)

# sector, bath/kitchen/bed/living zones, bed, sofa, hobby, mirrored
HOME_CONFIGS = (
    ("Home 2", "home_2.bathroom", "home_2.main_room", "home_2.main_room",
     "home_2.main_room", "prop.interiors_v3.bedroom.0087",
     "prop.interiors_v3.living.0002", "prop.office.wall_chart", False),
    ("Home 3", "home_3.bathroom", "home_3.main_room", "home_3.main_room",
     "home_3.main_room", "prop.interiors_v3.bedroom.0088",
     "prop.interiors_v3.living.0003",
     "prop.interiors_v3.classroom_library.0031", True),
    ("Home 4", "home_4.bathroom", "home_4.main_room", "home_4.main_room",
     "home_4.main_room", "prop.interiors_v3.bedroom.0087",
     "prop.interiors_v3.living.0004", "prop.interiors_v3.bedroom.0302", False),
    ("Home 5", "home_5.bathroom", "home_5.kitchen", "home_5.bedroom",
     "home_5.living_room", "prop.interiors_v3.bedroom.0088",
     "prop.interiors_v3.living.0002", "prop.office.laptop", True),
    ("Home 6", "home_6.bathroom", "home_6.kitchen", "home_6.bedroom",
     "home_6.living_room", "prop.interiors_v3.bedroom.0087",
     "prop.interiors_v3.living.0003", "prop.interiors_v3.japanese.0039", False),
    ("Home 7", "home_7.bathroom", "home_7.kitchen", "home_7.bedroom",
     "home_7.living_room", "prop.interiors_v3.bedroom.0088",
     "prop.interiors_v3.living.0004", "prop.office.notice_board", True),
    ("Home 8", "home_8.bathroom", "home_8.kitchen", "home_8.bedroom",
     "home_8.living_room", "prop.interiors_v3.bedroom.0087",
     "prop.interiors_v3.living.0002", "prop.office.paper_stack", False),
    ("Home 9", "home_9.bathroom", "home_9.kitchen", "home_9.bedroom",
     "home_9.living_room", "prop.interiors_v3.bedroom.0088",
     "prop.interiors_v3.living.0003", "prop.office.printer", True),
    ("Home 10", "home_10.bathroom", "home_10.kitchen", "home_10.bedroom",
     "home_10.living_room", "prop.interiors_v3.bedroom.0087",
     "prop.interiors_v3.living.0004",
     "prop.interiors_v3.classroom_library.0043", False),
)


def _p(sector: str, zone: str, role: str, cluster: str, key: str,
       x: int, y: int) -> tuple:
    return sector, zone, role, cluster, key, x, y


def _home(config: tuple) -> tuple[tuple, ...]:
    sector, bath, kitchen, bed, living, bed_key, sofa_key, hobby, mirrored = config
    left, _top, right, _bottom = HOME_BOUNDS[sector]
    outer, inner = left + 1, left + 3
    if inner % 2 == 0:
        inner -= 1
    far = right - 2
    bath_x, kitchen_x = (far, outer) if mirrored else (outer, far)
    refrigerator_x = kitchen_x
    if refrigerator_x % 2 == 0:
        refrigerator_x += 1 if refrigerator_x - 1 <= left else -1
    if refrigerator_x == inner:
        refrigerator_x += 2 if refrigerator_x + 2 < right else -2
    return (
        _p(sector, bath, "bathroom-mirror", "compact washroom",
           "prop.interiors_v3.bathroom.0066", bath_x, 82),
        _p(sector, bath, "washstand", "compact washroom",
           "prop.interiors_v3.bathroom.0002", bath_x, 84),
        _p(sector, bath, "toilet-fixture", "compact washroom",
           "prop.interiors_v3.bathroom.0021", inner, 84),
        _p(sector, kitchen, "refrigerator", "fitted kitchen run",
           "prop.interiors_v3.kitchen.0160", refrigerator_x, 82),
        _p(sector, kitchen, "cooking-area", "fitted kitchen run",
           "prop.interiors_v3.kitchen.0148", kitchen_x, 88),
        _p(sector, bed, "closet", "sleeping nook",
           "prop.interiors_v3.bedroom.0386", inner, 82),
        _p(sector, bed, "bed", "sleeping nook", bed_key, bath_x, 89),
        _p(sector, living, "lounge-seating", "living group", sofa_key, far, 90),
        _p(sector, living, "media-console", "living group",
           "prop.interiors_v3.living.0019", far, 91),
        _p(sector, living, "plant", "living group",
           "prop.interiors_v3.living.0015", outer, 91),
        _p(sector, living, "resident-hobby", "resident detail", hobby, inner, 87),
    )


HOME_PLACEMENTS = tuple(item for config in HOME_CONFIGS for item in _home(config))
HOME_FRONTAGE_PLACEMENTS: tuple[tuple, ...] = ()
HOME_INTERIOR_STAMP_PLACEMENTS = (
    # Transparent furniture-only crops from the paid home designs. Individual
    # semantic props remain above them and retain the authoritative blockers.
    ("Home 1", "home_1.kitchen", "prop.design.home_cluster.generic_nw", 68, 14),
    ("Home 1", "home_1.bedroom", "prop.design.home_cluster.generic_ne", 82, 14),
    ("Home 1", "home_1.living_room", "prop.design.home_cluster.generic_south", 74, 26),
    ("Home 2", "home_2.main_room", "prop.design.home_cluster.generic_nw", 28, 82),
    ("Home 2", "home_2.main_room", "prop.design.home_cluster.generic_south", 28, 88),
    ("Home 3", "home_3.main_room", "prop.design.home_cluster.japanese_ne", 40, 82),
    ("Home 3", "home_3.main_room", "prop.design.home_cluster.japanese_sw", 40, 88),
    ("Home 4", "home_4.main_room", "prop.design.home_cluster.generic_ne", 68, 82),
    ("Home 5", "home_5.living_room", "prop.design.home_cluster.generic_nw", 76, 82),
    ("Home 6", "home_6.living_room", "prop.design.home_cluster.generic_ne", 84, 82),
    ("Home 7", "home_7.living_room", "prop.design.home_cluster.japanese_nw", 119, 82),
    ("Home 7", "home_7.bedroom", "prop.design.home_cluster.japanese_se", 119, 88),
    ("Home 8", "home_8.living_room", "prop.design.home_cluster.generic_ne", 129, 82),
    ("Home 9", "home_9.living_room", "prop.design.home_cluster.generic_nw", 143, 82),
    ("Home 10", "home_10.living_room", "prop.design.home_cluster.generic_ne", 151, 82),
    ("University", "university.study_lab", "prop.design.university_lounge", 110, 10),
    ("Agent Academy", "academy.classroom", "prop.design.academy_lab", 122, 20),
)
# These are transparent native-16 furniture compositions supplied by LimeZu.
# They sit behind individually addressable props, so interactions and blockers
# remain granular while the large civic rooms gain coherent visual density.
PLACEMENTS = (
    *HOME_INTERIOR_STAMP_PLACEMENTS,
    ("Agent Academy", "academy.training_lab",
     "prop.design.academy_gym_compact", 121, 6),
    ("Community Center", "community.event_hall",
     "prop.design.community_studio", 67, 47),
    ("Claudeville Cafe", "cafe.service", "prop.design.community_cafe", 79, 47),
    # Native Exteriors front-wall runs replace the repeated red storefront
    # strip with the restrained stone and purpose-specific facades in the
    # target image.  Shell collision remains authoritative beneath them.
    ("Bank", "bank.waiting", "prop.design.frontage.bank_graystone", 28, 33),
    ("Home 1", "home_1.living_room",
     "prop.design.frontage.home_1_graystone", 69, 33),
    ("University", "university.cafeteria",
     "prop.design.frontage.university_left", 99, 32),
    ("Agent Academy", "academy.reception",
     "prop.design.frontage.university_right", 122, 32),
    ("Market", "market.checkout", "prop.design.frontage.market", 142, 31),
    ("Workshop", "workshop.intake",
     "prop.design.frontage.workshop_graystone", 28, 69),
    ("Community Center", "community.reception",
     "prop.design.frontage.community_center_graystone", 67, 69),
    ("Claudeville Cafe", "cafe.terrace",
     "prop.design.frontage.claudeville_cafe_graystone", 79, 69),
    ("Library", "library.circulation",
     "prop.design.frontage.library_graystone", 144, 69),
    ("Post Office", "post.waiting",
     "prop.design.frontage.post_office", 158, 31),
)

# Logical 32px footprints for the solid furniture/walls inside the reviewed
# transparent compositions.  Open aisles and presentation-room door gaps are
# intentionally omitted so residents can circulate around, but never through,
# the visible sprites.
COLLISION_BLOCKS = frozenset({
    # Academy gym machines and central training equipment.
    (62, 4), (63, 4), (64, 4), (62, 5), (65, 5),
    # Community presentation-room rim, desk and audience seating.
    *((x, 23) for x in range(33, 39)),
    *((33, y) for y in range(24, 29)),
    *((38, y) for y in range(24, 29)),
    (34, 28), (35, 28), (38, 28),
    (35, 25), (36, 25), (37, 25),
    (34, 27), (35, 27), (37, 27),
    # Cafe production wall, display counter and side seating pockets.
    *((x, 24) for x in range(40, 45)),
    *((x, 26) for x in range(40, 45)),
    (40, 27), (45, 27), (40, 28), (45, 28),
})


def validate() -> None:
    if HOME_FRONTAGE_PLACEMENTS:
        raise ValueError("target map must not activate opaque home facades")
    allowed = {
        "prop.design.home_cluster.generic_ne",
        "prop.design.home_cluster.generic_nw",
        "prop.design.home_cluster.generic_south",
        "prop.design.home_cluster.japanese_ne",
        "prop.design.home_cluster.japanese_nw",
        "prop.design.home_cluster.japanese_se",
        "prop.design.home_cluster.japanese_sw",
        "prop.design.university_lounge", "prop.design.academy_lab",
        "prop.design.academy_gym_compact", "prop.design.community_cafe",
        "prop.design.community_studio",
        "prop.design.frontage.bank_graystone",
        "prop.design.frontage.home_1_graystone",
        "prop.design.frontage.university_left",
        "prop.design.frontage.university_right",
        "prop.design.frontage.market",
        "prop.design.frontage.workshop_graystone",
        "prop.design.frontage.community_center_graystone",
        "prop.design.frontage.claudeville_cafe_graystone",
        "prop.design.frontage.library_graystone",
        "prop.design.frontage.post_office",
    }
    if {item[2] for item in PLACEMENTS} != allowed:
        raise ValueError("only reviewed transparent sprite compositions are allowed")
    if any(not (0 <= x < 88 and 0 <= y < 48) for x, y in COLLISION_BLOCKS):
        raise ValueError("sprite-composition collision escaped the logical world")
    if len(HOME_PLACEMENTS) != len(HOME_TARGETS) * 11:
        raise ValueError("every home needs eleven purposeful semantic props")
    occupied: set[tuple[str, int, int]] = set()
    for item in HOME_PLACEMENTS:
        sector, _zone, _role, _cluster, key, x, y = item
        left, top, right, bottom = HOME_BOUNDS[sector]
        point = (sector, x, y)
        if not (left < x < right and top < y < bottom) or point in occupied:
            raise ValueError(f"invalid rowhouse placement: {item}")
        if key.startswith("prop.design."):
            raise ValueError("rowhouses must use native semantic sprites")
        occupied.add(point)


validate()
