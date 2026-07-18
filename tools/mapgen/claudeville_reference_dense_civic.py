"""Purposeful native-sprite finishing clusters for target civic cutaways."""

from __future__ import annotations

try:
    from tools.mapgen import claudeville_north_placements as north
    from tools.mapgen import claudeville_reference_middle as middle
except ModuleNotFoundError:  # Direct mapgen execution.
    import claudeville_north_placements as north
    import claudeville_reference_middle as middle

TARGET_BOUNDS = {
    "Agent Academy": (123, 5, 133, 36),
    **middle.TARGET_BOUNDS,
}

# These are small supporting details around the larger program clusters in the
# primary modules. They never substitute for a room or duplicate its anchor.
PLACEMENTS = (
    ("Agent Academy", "academy.training_lab", "decor-equipment-storage",
     "training records wall", "prop.office.filing_cabinet", 125, 8),
    ("Agent Academy", "academy.training_lab", "decor-equipment-storage",
     "training records wall", "prop.office.display_cabinet", 128, 8),
    ("Agent Academy", "academy.classroom", "decor-reference-shelf",
     "classroom reference wall", "prop.interiors_v3.classroom_library.0043", 131, 19),
    ("Agent Academy", "academy.classroom", "decor-reference-shelf",
     "classroom reference wall", "prop.interiors_v3.classroom_library.0045", 128, 19),
    ("Agent Academy", "academy.lounge", "decor-lounge-seating",
     "academy lounge", "prop.office.armchair_mustard", 125, 34),
    ("Agent Academy", "academy.lounge", "decor-plant",
     "academy lounge", "prop.interiors_v3.living.0016", 131, 34),

    ("Workshop", "workshop.machine_bay", "decor-safety-chart",
     "east safety wall", "prop.office.wall_chart", 49, 45),
    ("Workshop", "workshop.machine_bay", "decor-safety-chart",
     "east safety wall", "prop.office.notice_board", 46, 45),
    ("Workshop", "workshop.machine_bay", "decor-parts-bench",
     "east parts bench", "prop.office.table_walnut_long", 46, 60),
    ("Workshop", "workshop.machine_bay", "decor-parts-bin",
     "east parts bench", "prop.post.package_small", 49, 60),
    ("Workshop", "workshop.intake", "decor-waiting-seat",
     "intake waiting pocket", "prop.office.armchair_ice", 35, 69),
    ("Workshop", "workshop.intake", "decor-side-table",
     "intake waiting pocket", "prop.office.side_table", 32, 69),

    ("Claudeville Cafe", "cafe.service", "decor-menu-board",
     "cafe information wall", "prop.office.notice_board", 81, 48),
    ("Claudeville Cafe", "cafe.service", "decor-menu-board",
     "cafe information wall", "prop.office.town_map", 84, 48),
    ("Claudeville Cafe", "cafe.dining", "decor-plant",
     "window dining support", "prop.interiors_v3.living.0015", 89, 48),
    ("Claudeville Cafe", "cafe.dining", "decor-side-table",
     "window dining support", "prop.office.side_table", 88, 57),

    ("Community Center", "community.reception", "decor-records",
     "community records wall", "prop.office.filing_cabinet", 75, 68),
    ("Community Center", "community.reception", "decor-records",
     "community records wall", "prop.office.display_cabinet", 78, 68),
    ("Community Center", "community.lounge", "decor-water-cooler",
     "east lounge support", "prop.office.water_cooler", 76, 64),
    ("Community Center", "community.lounge", "decor-plant",
     "east lounge support", "prop.interiors_v3.living.0017", 78, 64),

    ("Library", "library.circulation", "decor-returns-cart",
     "library checkout support", "prop.office.filing_cabinet", 153, 58),
    ("Library", "library.circulation", "decor-printer",
     "library checkout support", "prop.office.printer", 156, 58),
    ("Library", "library.reading", "decor-learning-globe",
     "reference support", "prop.interiors_v3.classroom_library.0034", 150, 58),
    ("Library", "library.reading", "decor-reference-map",
     "reference support", "prop.interiors_v3.classroom_library.0031", 156, 55),

    ("Post Office", "post.sorting", "decor-dispatch-board",
     "postal dispatch support", "prop.office.notice_board", 173, 18),
    ("Post Office", "post.sorting", "decor-sorted-parcel",
     "postal dispatch support", "prop.post.package_large", 170, 18),
    ("Post Office", "post.sorting", "decor-copy-station",
     "postal finishing station", "prop.office.copier", 170, 27),
    ("Post Office", "post.sorting", "decor-sorted-parcel",
     "postal finishing station", "prop.post.package_small", 173, 27),
)


def validate() -> None:
    existing = {(item[0], item[5], item[6]) for item in middle.PLACEMENTS}
    existing.update((item[0], item[5], item[6]) for item in north.ACADEMY_PLACEMENTS)
    occupied: set[tuple[str, int, int]] = set()
    clusters: dict[tuple[str, str], int] = {}
    for item in PLACEMENTS:
        sector, _zone, _role, cluster, key, x, y = item
        left, top, right, bottom = TARGET_BOUNDS[sector]
        point = (sector, x, y)
        if point in existing or point in occupied:
            raise ValueError(f"duplicate dense civic placement: {point}")
        if not (left < x < right and top < y < bottom):
            raise ValueError(f"dense civic placement left {sector}: {item}")
        if key.startswith("prop.design."):
            raise ValueError(f"dense civic placement cannot use design stamp: {key}")
        clusters[(sector, cluster)] = clusters.get((sector, cluster), 0) + 1
        occupied.add(point)
    if any(count < 2 for count in clusters.values()):
        raise ValueError("every finishing cluster needs at least two related props")


validate()
