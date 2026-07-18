"""Native-16 architecture painters for the Claudeville reference slice."""

from __future__ import annotations

try:
    from tools.mapgen import claudeville_reference_layout as reference_layout
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_reference_layout as reference_layout


WIDTH = 176

# These large public cutaways have enough clear perimeter to carry a second
# paid-Interiors return without covering their functional furniture clusters.
# The Bank intentionally stays single-rimmed because its secure cabinetry is
# authored directly against the north wall.
DEEP_RETURN_SECTORS = frozenset({
    "Bank",
    "Home 1",
    "Market",
    "Agent Academy",
    "Workshop",
    "Community Center",
    "Library",
    "Post Office",
    "Town Hall",
})
DEEP_RETURN_BOUNDS = frozenset(
    reference_layout.BUILDINGS[sector]["room"]
    for sector in DEEP_RETURN_SECTORS
)


class ArchitectureError(ValueError):
    """Raised when reference architecture input is malformed."""


def _set(data: list[int], x: int, y: int, gid: int) -> None:
    data[y * WIDTH + x] = gid


def _fill(
    data: list[int],
    left: int,
    top: int,
    right: int,
    bottom: int,
    gid: int,
) -> None:
    for y in range(top, bottom):
        start = y * WIDTH + left
        data[start : start + right - left] = [gid] * (right - left)


def paint_shell(
    floor: list[int],
    walls: list[int],
    bounds: tuple[int, int, int, int],
    door: range | set[int],
    floor_gid: int,
    style: dict[str, int],
    door_side: str = "bottom",
) -> None:
    left, top, right, bottom = bounds
    last_x, last_y = right - 1, bottom - 1
    if bottom - top < 4:
        raise ArchitectureError("reference shells need room for a two-row wall")
    _fill(floor, left + 1, top + 2, last_x, last_y, floor_gid)
    _set(walls, left, top, style["top_left"])
    _set(walls, last_x, top, style["top_right"])
    _set(walls, left, top + 1, style["top_face_left"])
    _set(walls, last_x, top + 1, style["top_face_right"])
    _set(walls, left, last_y, style["bottom_left"])
    _set(walls, last_x, last_y, style["bottom_right"])
    for x in range(left + 1, last_x):
        if door_side != "top" or x not in door:
            _set(walls, x, top, style["top_middle"])
            _set(walls, x, top + 1, style["top_face_middle"])
        if door_side != "bottom" or x not in door:
            _set(walls, x, last_y, style["bottom_middle"])
    for y in range(top + 2, last_y):
        _set(walls, left, y, style["side_left"])
        _set(walls, last_x, y, style["side_right"])


def paint_shell_border(
    data: list[int], resolve, bounds: tuple[int, int, int, int], door: range | set[int],
    door_side: str = "bottom",
) -> None:
    """Overlay one coherent dark-brown cutaway rim from paid Interiors."""
    left, top, right, bottom = bounds
    last_x, last_y = right - 1, bottom - 1
    _set(data, left, top, resolve(("room.borders", 1, 15)))
    _set(data, last_x, top, resolve(("room.borders", 1, 16)))
    _set(data, left, last_y, resolve(("room.borders", 3, 14)))
    _set(data, last_x, last_y, resolve(("room.borders", 3, 13)))
    for x in range(left + 1, last_x):
        if door_side != "top" or x not in door:
            _set(data, x, top, resolve(("room.borders", 1, 13)))
        if door_side != "bottom" or x not in door:
            _set(data, x, last_y, resolve(("room.borders", 3, 15)))
    for y in range(top + 1, last_y):
        _set(data, left, y, resolve(("room.borders", 0, 13)))
        _set(data, last_x, y, resolve(("room.borders", 0, 14)))
    if bounds in DEEP_RETURN_BOUNDS:
        occupied = {
            (x, y)
            for y in range(top, bottom)
            for x in range(left, right)
        }
        _paint_inner_cutaway_return(data, resolve, occupied)


def _paint_inner_cutaway_return(
    data: list[int], resolve, occupied: set[tuple[int, int]],
) -> None:
    """Add a north-and-side inner return while leaving the frontage open."""
    inner = {
        (x, y)
        for x, y in occupied
        if all(
            point in occupied
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
        )
    }
    for x, y in sorted(inner, key=lambda point: (point[1], point[0])):
        top_edge = (x, y - 1) not in inner
        left_edge = (x - 1, y) not in inner
        right_edge = (x + 1, y) not in inner
        tile = None
        if top_edge:
            tile = (1, 15) if left_edge else (1, 16) if right_edge else (1, 13)
        elif left_edge:
            tile = (0, 13)
        elif right_edge:
            tile = (0, 14)
        if tile is not None:
            _set(data, x, y, resolve(("room.borders", *tile)))


def _university_cells() -> set[tuple[int, int]]:
    return {
        (x, y)
        for left, top, right, bottom in reference_layout.BUILDINGS["University"][
            "room_union"
        ]
        for y in range(top, bottom)
        for x in range(left, right)
    }


def paint_university(
    floor: list[int], walls: list[int], floor_gid: int, style: dict[str, int]
) -> None:
    """Paint the exact traced U with two wings and a northern library bridge."""
    occupied = _university_cells()
    entry_gaps = set(range(103, 107)) | set(range(125, 129))
    for x, y in occupied:
        _set(floor, x, y, floor_gid)
        top_edge = (x, y - 1) not in occupied
        bottom_edge = (x, y + 1) not in occupied
        left_edge = (x - 1, y) not in occupied
        right_edge = (x + 1, y) not in occupied
        if top_edge:
            key = (
                "top_left" if left_edge else "top_right" if right_edge else "top_middle"
            )
        elif bottom_edge and x not in entry_gaps:
            key = (
                "bottom_left"
                if left_edge
                else "bottom_right"
                if right_edge
                else "bottom_middle"
            )
        elif left_edge:
            key = "side_left"
        elif right_edge:
            key = "side_right"
        else:
            continue
        _set(walls, x, y, style[key])


def paint_university_border(data: list[int], resolve) -> None:
    """Trace the U-shaped university with the paid cutaway rim."""
    occupied = _university_cells()
    entry_gaps = set(range(103, 107)) | set(range(125, 129))
    for x, y in occupied:
        top_edge = (x, y - 1) not in occupied
        bottom_edge = (x, y + 1) not in occupied
        left_edge = (x - 1, y) not in occupied
        right_edge = (x + 1, y) not in occupied
        tile = None
        if top_edge and left_edge:
            tile = (1, 15)
        elif top_edge and right_edge:
            tile = (1, 16)
        elif top_edge:
            tile = (1, 13)
        elif bottom_edge and x not in entry_gaps:
            tile = (3, 14) if left_edge else (3, 13) if right_edge else (3, 15)
        elif left_edge:
            tile = (0, 13)
        elif right_edge:
            tile = (0, 14)
        if tile is not None:
            _set(data, x, y, resolve(("room.borders", *tile)))
    _paint_inner_cutaway_return(data, resolve, occupied)


def paint_partitions(
    walls: list[int], partitions: tuple[tuple, ...], style: dict[str, int]
) -> None:
    for _sector, orientation, fixed, start, end, gaps in partitions:
        if orientation == "vertical":
            for position in range(start, end):
                if position not in gaps:
                    _set(walls, fixed, position, style["partition_left"])
                    _set(walls, fixed + 1, position, style["partition_right"])
        elif orientation == "horizontal":
            for position in range(start, end):
                if position not in gaps:
                    _set(walls, position, fixed, style["top_middle"])
                    _set(walls, position, fixed + 1, style["top_face_middle"])
        else:
            raise ArchitectureError(f"unknown partition orientation: {orientation}")


def paint_slim_partitions(
    walls: list[int], partitions: tuple[tuple, ...], style: dict[str, int]
) -> None:
    """Paint native-16 room dividers without a doubled beige wall face.

    The normal two-cell wall is appropriate for enclosed bedrooms and wet
    rooms.  Shared civic cutaways need the thinner divider visible in the
    reference: one sprite cell, a real doorway, and no 32px blank strip.
    """
    for _sector, orientation, fixed, start, end, gaps in partitions:
        if orientation == "vertical":
            for position in range(start, end):
                if position not in gaps:
                    _set(walls, fixed, position, style["partition_left"])
        elif orientation == "horizontal":
            for position in range(start, end):
                if position not in gaps:
                    _set(walls, position, fixed, style["top_middle"])
        else:
            raise ArchitectureError(f"unknown partition orientation: {orientation}")


def clear_logical_door(data: list[int], x: int, y: int) -> None:
    """Open one visible 32px doorway through a native-16 partition."""
    for visual_y in (2 * y, 2 * y + 1):
        for visual_x in (2 * x, 2 * x + 1):
            _set(data, visual_x, visual_y, 0)


def paint_cafe_restroom(
    floor: list[int], walls: list[int], floor_gid: int, style: dict[str, int],
) -> None:
    """Attach one screened wet room to the complete licensed Cafe module."""
    _fill(floor, 64, 51, 67, 56, floor_gid)
    for x in range(63, 68):
        _set(walls, x, 49, style[
            "top_left" if x == 63 else "top_right" if x == 67 else "top_middle"
        ])
        _set(walls, x, 50, style[
            "top_face_left" if x == 63
            else "top_face_right" if x == 67 else "top_face_middle"
        ])
        _set(walls, x, 56, style[
            "bottom_left" if x == 63
            else "bottom_right" if x == 67 else "bottom_middle"
        ])
    for y in range(51, 56):
        _set(walls, 67, y, style["side_right"])
        if y not in {53, 54}:
            _set(walls, 63, y, style["side_left"])


def _paint_repeatable_table(
    data: list[int],
    resolve,
    bounds: tuple[int, int, int, int],
    source: str,
    rows: tuple[int, int, int],
    columns: tuple[int, int, int],
) -> None:
    left, top, right, bottom = bounds
    for y in range(top, bottom):
        source_row = rows[0] if y == top else rows[2] if y == bottom - 1 else rows[1]
        for x in range(left, right):
            source_column = (
                columns[0]
                if x == left
                else columns[2]
                if x == right - 1
                else columns[1]
            )
            _set(data, x, y, resolve((source, source_row, source_column)))


def paint_bank_assemblies(data: list[int], resolve) -> None:
    """Paint one joined operations table instead of four floating desks."""
    _paint_repeatable_table(
        data,
        resolve,
        (34, 18, 42, 22),
        "theme.generic",
        (34, 35, 36),
        (1, 2, 3),
    )


def paint_university_assemblies(data: list[int], resolve) -> None:
    """Paint the east seminar's continuous north-south boardroom table."""
    _paint_repeatable_table(
        data,
        resolve,
        (96, 11, 100, 21),
        "theme.generic",
        (34, 35, 36),
        (1, 2, 3),
    )


def paint_facade(
    lower: list[int],
    _upper: list[int],
    spans: tuple[tuple[int, int], ...],
    top: int,
    bottom: int,
    door: range,
    window_centers: tuple[int, ...],
    exterior_gids: dict[tuple[str, int, int], int],
) -> None:
    """Build a four- or five-tile frontage from one Exteriors family."""
    height = bottom - top
    if height not in {4, 5}:
        raise ArchitectureError("reference facades must be four or five tiles deep")
    source_rows = tuple(range(110, 110 + height))
    for left, right in spans:
        for x in range(left, right):
            column = 7 + (x - left) % 4
            for center in window_centers:
                if center - 1 <= x <= center + 1:
                    column = 8 + x - (center - 1)
                    break
            if x in door:
                width = max(door.stop - door.start - 1, 1)
                column = round((x - door.start) * 5 / width)
            for offset, source_row in enumerate(source_rows):
                _set(
                    lower,
                    x,
                    top + offset,
                    exterior_gids[("exteriors_generic", column, source_row)],
                )
