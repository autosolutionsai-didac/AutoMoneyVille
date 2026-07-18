"""Visible scenery cells that are intentionally non-navigable in Claudeville."""

from __future__ import annotations

Point = tuple[int, int]

PERIMETER_SCENERY_BLOCKS = frozenset(
    {
        (67, 0), (68, 0), (69, 0), (70, 0),
        (10, 1), (62, 1), (63, 1), (67, 1), (68, 1), (69, 1), (70, 1),
        (71, 1), (72, 1), (74, 1), (82, 1),
        (1, 2), (4, 2), (8, 2), (9, 2), (10, 2), (35, 2), (51, 2),
        (52, 2), (55, 2), (63, 2), (64, 2), (65, 2), (66, 2), (67, 2),
        (68, 2), (69, 2), (70, 2), (71, 2), (72, 2), (76, 2), (77, 2),
        (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (10, 3), (11, 3),
        (35, 3), (52, 3), (68, 3), (69, 3), (70, 3), (83, 3), (84, 3),
        (85, 3),
        (3, 4), (4, 4), (5, 4), (6, 4), (7, 4), (8, 4), (9, 4),
        (10, 4), (11, 4), (12, 4), (35, 4), (52, 4), (69, 4), (83, 4),
        (72, 5), (73, 5), (84, 5),
        (1, 6), (2, 6), (3, 6), (83, 6), (84, 6),
        (1, 7), (3, 7), (85, 7),
        (79, 8), (85, 8), (86, 8), (86, 9), (87, 10), (87, 11), (83, 13),
        (3, 23), (3, 24), (1, 25), (3, 25), (3, 26), (3, 27),
        (2, 29), (3, 29), (2, 30), (3, 30), (1, 40), (1, 43), (1, 46),
    }
)

LANDSCAPED_BUFFER_BLOCKS = frozenset(
    {
        (51, 5), (51, 6), (51, 7), (51, 8), (51, 9), (51, 10),
        (51, 11), (81, 11), (51, 12), (81, 12), (82, 12), (51, 13),
        (81, 13), (51, 14), (81, 14), (51, 15), (79, 41), (62, 43),
    }
)

RETIRED_PATH_BLOCKS = frozenset({(42, 42), (54, 42), (42, 43), (54, 44)})

SCENERY_BLOCK_CELLS = frozenset().union(
    PERIMETER_SCENERY_BLOCKS,
    LANDSCAPED_BUFFER_BLOCKS,
    RETIRED_PATH_BLOCKS,
)

RETIRED_PATH_VISUAL_RECTS = (
    (104, 8, 106, 10),
    (138, 8, 140, 10),
    (84, 84, 86, 86),
    (108, 84, 110, 86),
    (84, 86, 86, 88),
    (108, 88, 110, 90),
)


def validate_scenery_blocks() -> None:
    """Keep the reviewed manifest exact, unique, and inside the logical grid."""
    groups = (
        PERIMETER_SCENERY_BLOCKS,
        LANDSCAPED_BUFFER_BLOCKS,
        RETIRED_PATH_BLOCKS,
    )
    if tuple(map(len, groups)) != (96, 18, 4):
        raise ValueError("Claudeville scenery blocker counts changed")
    if sum(map(len, groups)) != len(SCENERY_BLOCK_CELLS):
        raise ValueError("Claudeville scenery blocker groups overlap")
    if any(not (0 <= x < 88 and 0 <= y < 48) for x, y in SCENERY_BLOCK_CELLS):
        raise ValueError("Claudeville scenery blocker is outside the logical grid")


validate_scenery_blocks()
