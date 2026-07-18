"""Warm native-16 facade overlay matching the accepted town silhouette."""

from __future__ import annotations

try:
    from tools.mapgen import claudeville_reference_facade_assets as facade_assets
    from tools.mapgen import claudeville_reference_layout as layout
except ModuleNotFoundError:  # Direct script execution.
    import claudeville_reference_facade_assets as facade_assets
    import claudeville_reference_layout as layout


WIDTH = layout.VISUAL_WIDTH
MODULE_COLUMNS = (21, 22, 24, 25)
LEFT_EDGE_COLUMN = 20
RIGHT_EDGE_COLUMN = 26
SOURCE_TOP_ROW = 41


def _set(data: list[int], x: int, y: int, gid: int) -> None:
    data[y * WIDTH + x] = gid


def _spans(
    facade: tuple[int, int, int, int], entry: tuple[int, int, int, int] | None,
) -> tuple[tuple[int, int], ...]:
    left, _top, right, _bottom = facade
    if entry is None or entry[2] <= left or entry[0] >= right:
        return ((left, right),)
    return tuple(
        span
        for span in ((left, max(left, entry[0])), (min(right, entry[2]), right))
        if span[0] < span[1]
    )


def _column(offset: int, width: int) -> int:
    if width == 1:
        return 24
    if offset == 0:
        return LEFT_EDGE_COLUMN
    if offset == width - 1:
        return RIGHT_EDGE_COLUMN
    return MODULE_COLUMNS[(offset - 1) % len(MODULE_COLUMNS)]


def paint_all(data: list[int], exterior_gids: dict[tuple[str, int, int], int]) -> None:
    """Overlay coherent stone-and-timber fronts while preserving door courts."""
    if len(data) != layout.VISUAL_WIDTH * layout.VISUAL_HEIGHT:
        raise ValueError("Claudeville facade layer has the wrong dimensions")
    for sector, record in layout.BUILDINGS.items():
        if (
            sector in facade_assets.STAMPED_SECTORS
            or record.get("door_side") == "top"
        ):
            continue
        facades = (
            (record["facade"],)
            if "facade" in record
            else tuple(record.get("facade_union", ()))
        )
        entry = record.get("entry")
        for facade in facades:
            _left, top, _right, bottom = facade
            height = bottom - top
            if height not in {3, 4, 5}:
                raise ValueError("reference facades must be three to five tiles deep")
            for left, right in _spans(facade, entry):
                width = right - left
                for x in range(left, right):
                    source_column = _column(x - left, width)
                    for row_offset in range(3):
                        _set(
                            data, x, bottom - 3 + row_offset,
                            exterior_gids[
                                (
                                    "exteriors_modular",
                                    source_column,
                                    SOURCE_TOP_ROW + row_offset,
                                )
                            ],
                        )


def validate() -> None:
    if tuple(_column(index, 6) for index in range(6)) != (20, 21, 22, 24, 25, 26):
        raise ValueError("native facade module cadence changed")


validate()
