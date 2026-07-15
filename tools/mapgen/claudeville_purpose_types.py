"""Shared types and zone geometry for Claudeville purpose layouts."""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[int, int]
Rect = tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class PurposeProp:
    """One visible prop with an explicit gameplay purpose."""

    asset_key: str
    visual_x: int
    visual_y: int
    semantic_type: str | None
    zone: str
    blocks: bool
    name: str | None = None


@dataclass(frozen=True, slots=True)
class SemanticObject:
    """Backend interaction target expressed on the authoritative logical grid."""

    zone: str
    type: str
    logical_tiles: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class AtlasStamp:
    """A source tile rectangle placed at an absolute visual-grid destination."""

    source_id: str
    source_rect: Rect
    destination: Point
    target_layer: str
    blocker_policy: str


BLOCKER_POLICIES = frozenset({"preserve-collision", "require-blocked"})
FORBIDDEN_TEMPLATE_NAMES = frozenset({"book_library"})
PUBLIC_BUILDING_BOUNDS: dict[str, Rect] = {
    "Bank": (10, 12, 29, 32),
    "University": (73, 8, 100, 32),
    "Agent Academy": (109, 10, 130, 32),
    "Market": (147, 22, 161, 30),
    "Workshop": (8, 40, 29, 63),
    "Community Center": (45, 43, 65, 63),
    "Claudeville Cafe": (94, 43, 109, 57),
    "Library": (112, 42, 131, 64),
    "Post Office": (149, 43, 172, 64),
    "Town Hall": (88, 75, 107, 91),
}
TERRACE_BOUNDS: dict[str, Rect] = {"Claudeville Cafe": (92, 57, 109, 64)}
ZONE_RECTS: dict[str, Rect] = {
    "bank.archive": (16, 12, 20, 20),
    "bank.teller": (19, 19, 28, 25),
    "bank.advisory": (10, 21, 18, 31),
    "bank.waiting": (19, 25, 29, 31),
    "university.lecture": (73, 8, 86, 22),
    "university.study_lab": (86, 8, 100, 22),
    "university.cafeteria": (80, 21, 100, 32),
    "academy.training_lab": (109, 10, 120, 24),
    "academy.classroom": (120, 10, 130, 24),
    "academy.reception": (109, 24, 118, 32),
    "academy.lounge": (118, 24, 126, 32),
    "market.retail": (147, 22, 161, 28),
    "market.checkout": (147, 25, 161, 30),
    "workshop.machine_bay": (8, 40, 29, 56),
    "workshop.intake": (8, 54, 20, 63),
    "community.event_hall": (45, 43, 65, 56),
    "community.lounge": (45, 56, 57, 63),
    "community.reception": (57, 56, 65, 63),
    "cafe.service": (94, 43, 109, 52),
    "cafe.dining": (94, 50, 109, 57),
    "cafe.terrace": TERRACE_BOUNDS["Claudeville Cafe"],
    "library.stacks": (112, 42, 131, 54),
    "library.reading": (112, 53, 131, 61),
    "library.circulation": (112, 56, 121, 64),
    "post.service": (149, 43, 161, 56),
    "post.waiting": (149, 55, 160, 63),
    "post.sorting": (160, 43, 172, 62),
    "hall.public_service": (88, 75, 98, 83),
    "hall.administration": (98, 75, 107, 83),
    "hall.council": (92, 83, 103, 91),
}


def _p(
    asset_key: str,
    x: int,
    y: int,
    zone: str,
    semantic_type: str | None = None,
    blocks: bool = True,
    name: str | None = None,
) -> PurposeProp:
    return PurposeProp(asset_key, x, y, semantic_type, zone, blocks, name)
