"""Reviewed logical cells that connect Claudeville rooms without moving objects."""

from __future__ import annotations

Point = tuple[int, int]

PUBLIC_CIRCULATION_CELLS: dict[str, tuple[Point, ...]] = {
    "Bank": ((8, 9), (6, 9)),
    "Agent Academy": ((59, 10), (60, 12)),
    "Library": ((58, 25), (58, 24)),
    "Market": ((76, 13), (75, 13)),
    "Post Office": ((79, 22), (79, 27)),
    "Town Hall": ((47, 37), (46, 37)),
}

HOME_CIRCULATION_CELLS: dict[str, tuple[Point, ...]] = {
    "Home 1": ((30, 13), (30, 8), (26, 9), (25, 9)),
    "Home 2": ((6, 44), (6, 41)),
    "Home 3": ((14, 44), (14, 41), (11, 37), (11, 38)),
    "Home 4": ((19, 41), (20, 41), (22, 42), (22, 43)),
    "Home 5": ((27, 43), (27, 42), (27, 41), (30, 41)),
    "Home 6": ((34, 37), (37, 37)),
    "Home 7": ((57, 37), (59, 39), (58, 41), (57, 41)),
    "Home 8": ((68, 39), (68, 40), (68, 41), (65, 41)),
    "Home 9": ((78, 37), (72, 41), (73, 40)),
    "Home 10": ((84, 37),),
}

CIRCULATION_CELLS: dict[str, tuple[Point, ...]] = {
    **PUBLIC_CIRCULATION_CELLS,
    **HOME_CIRCULATION_CELLS,
}


def validate_circulation_cells() -> None:
    """Keep the reviewed bridge recipe exact, disjoint, and on the logical grid."""
    if set(PUBLIC_CIRCULATION_CELLS) != {
        "Bank",
        "Agent Academy",
        "Library",
        "Market",
        "Post Office",
        "Town Hall",
    }:
        raise ValueError("Claudeville public circulation sectors changed")
    if set(HOME_CIRCULATION_CELLS) != {f"Home {index}" for index in range(1, 11)}:
        raise ValueError("Claudeville home circulation sectors changed")
    flattened = [point for cells in CIRCULATION_CELLS.values() for point in cells]
    if len(flattened) != 44 or len(set(flattened)) != len(flattened):
        raise ValueError("Claudeville circulation cells must be 44 unique points")
    if any(not (0 <= x < 88 and 0 <= y < 48) for x, y in flattened):
        raise ValueError("Claudeville circulation cell is outside the logical grid")


validate_circulation_cells()
