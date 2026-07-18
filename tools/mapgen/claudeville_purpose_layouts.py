"""Purpose-first furnishing contract for Claudeville's public buildings."""

from __future__ import annotations

try:
    from tools.mapgen.claudeville_entry_paths import authored_walkable_cells
    from tools.mapgen.claudeville_purpose_props_north import NORTH_PURPOSE_PROPS
    from tools.mapgen.claudeville_purpose_props_south import SOUTH_PURPOSE_PROPS
    from tools.mapgen.claudeville_purpose_semantics import (
        ENTRANCES,
        HOME_KITCHEN_STAMPS,
        PURPOSE_STAMPS,
        SEMANTIC_OBJECTS,
        SPAWNS,
    )
    from tools.mapgen.claudeville_purpose_types import (
        BLOCKER_POLICIES,
        FORBIDDEN_TEMPLATE_NAMES,
        PUBLIC_BUILDING_BOUNDS,
        TERRACE_BOUNDS,
        ZONE_RECTS,
        AtlasStamp,
        Point,
        PurposeProp,
        Rect,
        SemanticObject,
    )
    from tools.mapgen.claudeville_scenery_blocks import SCENERY_BLOCK_CELLS
except ModuleNotFoundError:
    from claudeville_entry_paths import (
        authored_walkable_cells,  # type: ignore[no-redef]
    )
    from claudeville_purpose_props_north import (
        NORTH_PURPOSE_PROPS,  # type: ignore[no-redef]
    )
    from claudeville_purpose_props_south import (
        SOUTH_PURPOSE_PROPS,  # type: ignore[no-redef]
    )
    from claudeville_purpose_semantics import (  # type: ignore[no-redef]
        ENTRANCES,
        HOME_KITCHEN_STAMPS,
        PURPOSE_STAMPS,
        SEMANTIC_OBJECTS,
        SPAWNS,
    )
    from claudeville_purpose_types import (  # type: ignore[no-redef]
        BLOCKER_POLICIES,
        FORBIDDEN_TEMPLATE_NAMES,
        PUBLIC_BUILDING_BOUNDS,
        TERRACE_BOUNDS,
        ZONE_RECTS,
        AtlasStamp,
        Point,
        PurposeProp,
        Rect,
        SemanticObject,
    )
    from claudeville_scenery_blocks import (  # type: ignore[no-redef]
        SCENERY_BLOCK_CELLS,
    )

__all__ = (
    "AtlasStamp",
    "BLOCKER_POLICIES",
    "ENTRANCES",
    "FORBIDDEN_TEMPLATE_NAMES",
    "HOME_KITCHEN_STAMPS",
    "PUBLIC_BUILDING_BOUNDS",
    "PURPOSE_PROPS",
    "PURPOSE_STAMPS",
    "Point",
    "PurposeProp",
    "Rect",
    "SEMANTIC_OBJECTS",
    "SPAWNS",
    "SCENERY_BLOCK_CELLS",
    "SemanticObject",
    "TERRACE_BOUNDS",
    "ZONE_RECTS",
    "authored_walkable_cells",
    "validate_layouts",
)

PURPOSE_PROPS: dict[str, tuple[PurposeProp, ...]] = {
    **NORTH_PURPOSE_PROPS,
    **SOUTH_PURPOSE_PROPS,
}


def _contains(rect: Rect, x: int, y: int) -> bool:
    return rect[0] <= x < rect[2] and rect[1] <= y < rect[3]


def validate_layouts() -> None:
    """Reject purpose data that could drift outside its authored visual footprint."""
    public = set(PUBLIC_BUILDING_BOUNDS)
    if set(PURPOSE_PROPS) != public or set(SEMANTIC_OBJECTS) != public:
        raise ValueError(
            "purpose props and semantic objects must cover every public building"
        )
    if set(PURPOSE_STAMPS) - public:
        raise ValueError("purpose stamp references an unknown public building")
    if set(ENTRANCES) != public or set(SPAWNS) != public:
        raise ValueError("entrances and spawns must cover every public building")
    identities: set[tuple[str, int, int]] = set()
    positions: set[Point] = set()
    for building, props in PURPOSE_PROPS.items():
        building_bounds = PUBLIC_BUILDING_BOUNDS[building]
        terrace = TERRACE_BOUNDS.get(building)
        for prop in props:
            zone_bounds = ZONE_RECTS.get(prop.zone)
            if zone_bounds is None or not _contains(
                zone_bounds, prop.visual_x, prop.visual_y
            ):
                raise ValueError(
                    f"prop outside semantic zone: {building}:{prop.asset_key}"
                )
            if not _contains(building_bounds, prop.visual_x, prop.visual_y) and (
                not (terrace and _contains(terrace, prop.visual_x, prop.visual_y))
            ):
                raise ValueError(
                    f"prop outside building or terrace: {building}:{prop.asset_key}"
                )
            identity = (prop.asset_key, prop.visual_x, prop.visual_y)
            position = (prop.visual_x, prop.visual_y)
            if identity in identities or position in positions:
                raise ValueError(f"duplicate purpose prop at {position}")
            identities.add(identity)
            positions.add(position)
    visible: dict[str, set[Point]] = {
        building: {(prop.visual_x // 2, prop.visual_y // 2) for prop in props}
        for building, props in PURPOSE_PROPS.items()
    }
    for building, stamps in PURPOSE_STAMPS.items():
        bounds = PUBLIC_BUILDING_BOUNDS[building]
        for stamp in stamps:
            sx, sy, width, height = stamp.source_rect
            dx, dy = stamp.destination
            if min(sx, sy) < 0 or width <= 0 or height <= 0:
                raise ValueError(f"invalid source rectangle for {building}")
            if stamp.blocker_policy not in BLOCKER_POLICIES:
                raise ValueError(f"invalid blocker policy for {building}")
            if not (
                _contains(bounds, dx, dy)
                and dx + width <= bounds[2]
                and (dy + height <= bounds[3])
            ):
                raise ValueError(f"purpose stamp outside building: {building}")
            visible[building].update(
                (x // 2, y // 2)
                for y in range(dy, dy + height)
                for x in range(dx, dx + width)
            )
    for building, objects in SEMANTIC_OBJECTS.items():
        for semantic in objects:
            zone_bounds = ZONE_RECTS.get(semantic.zone)
            if zone_bounds is None or not semantic.logical_tiles:
                raise ValueError(
                    f"invalid semantic object zone: {building}:{semantic.type}"
                )
            if any(
                (
                    not (0 <= x < 88 and 0 <= y < 48)
                    or not _contains(zone_bounds, 2 * x, 2 * y)
                    for x, y in semantic.logical_tiles
                )
            ):
                raise ValueError(
                    f"semantic object outside zone: {building}:{semantic.type}"
                )
            if not set(semantic.logical_tiles) & visible[building]:
                raise ValueError(
                    f"semantic object has no visible prop: {building}:{semantic.type}"
                )
    for mapping_name, mapping in (("entrance", ENTRANCES), ("spawn", SPAWNS)):
        for building, (x, y) in mapping.items():
            if not (0 <= x < 88 and 0 <= y < 48):
                raise ValueError(f"{mapping_name} outside grid: {building}")


validate_layouts()
