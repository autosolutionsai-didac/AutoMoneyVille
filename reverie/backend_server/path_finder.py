"""
Original Author: Joon Sung Park (joonspk@stanford.edu)
Heavily modified for Claudeville (Claude CLI port)

File: path_finder.py
Description: Implements PathFinder class for generative agents path finding.
"""

# PEP 604 unions (`X | None`) appear in annotations below; defer evaluation so
# they remain valid on the Python 3.9 floor declared in environment.yaml.
from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

# Cache of the STATIC base collision grid (1 = blocked by the maze itself,
# 0 = passable) keyed by the identity of the maze list object. The maze
# collision map never changes during a run (only persona/object positions vary,
# and those are passed per-call via `extra_blocked`), so we build the base grid
# once and reuse it across PathFinder instances — persona.py constructs a fresh
# PathFinder every move, which previously rebuilt the full 88x48 grid each time.
# Keying by id() is safe here because the maze list lives for the whole run; we
# also store the row/col dimensions and verify them on hit so a recycled id()
# (after GC of a short-lived maze) can never silently return a stale grid.
_BASE_COLLISION_CACHE: dict = {}


def clear_collision_cache() -> None:
    """Drop the cached static collision grids (e.g. when a maze is reloaded)."""
    _BASE_COLLISION_CACHE.clear()


class PathFinder:
    """
    A path finding utility class for navigating maze environments.

    Uses a breadth-first wave propagation algorithm to find shortest paths
    between points while avoiding collision blocks.
    """

    def __init__(self, maze: list, collision_block_id: str, extra_blocked: set = None):
        """
        Initialize PathFinder with a maze and collision block identifier.

        Args:
            maze: 2D list representing the maze grid
            collision_block_id: Character/value identifying impassable blocks
            extra_blocked: Optional set of (x, y) tiles to treat as blocked
        """
        self.maze = maze
        self.collision_block_id = collision_block_id
        self.extra_blocked = extra_blocked or set()
        # Set by _find_path_internal: True when the wave-propagation cap was hit
        # before the target was reached (i.e. the returned path is a truncated
        # best-effort, not a complete route). Callers can inspect this to avoid
        # treating a truncated path as a real one.
        self.last_path_truncated = False

    def _base_collision_map(self) -> list:
        """
        Return the static base collision grid (1 = blocked maze tile, 0 = open),
        built once per maze object and cached. `extra_blocked` is NOT applied
        here — it is overlaid per-call so the cache stays purely static.

        The returned grid is shared/cached and MUST NOT be mutated by callers.
        """
        key = id(self.maze)
        rows = len(self.maze)
        cols = len(self.maze[0]) if rows else 0
        cached = _BASE_COLLISION_CACHE.get(key)
        if cached is not None and cached[0] == (rows, cols):
            return cached[1]

        base_map = []
        for row in self.maze:
            base_map.append([1 if cell == self.collision_block_id else 0 for cell in row])
        _BASE_COLLISION_CACHE[key] = ((rows, cols), base_map)
        return base_map

    def find_path(self, start: tuple, end: tuple) -> list:
        """
        Find the shortest path from start to end coordinates.

        Uses wave propagation (BFS) algorithm for shortest path.
        Coordinates are in (x, y) format and internally converted.

        Args:
            start: Starting coordinate as (x, y) tuple
            end: Ending coordinate as (x, y) tuple

        Returns:
            List of (x, y) coordinate tuples forming the path from start to end.
            Returns path with just the start if no path exists.
        """
        # Convert from (x, y) to internal (row, col) format
        internal_start = (start[1], start[0])
        internal_end = (end[1], end[0])

        path = self._find_path_internal(internal_start, internal_end)

        # Convert back to (x, y) format
        return [(coord[1], coord[0]) for coord in path]

    def find_path_to_nearest(self, start: tuple, targets: list) -> tuple:
        """
        Find the path to the nearest target from a list of targets.

        Args:
            start: Starting coordinate as (x, y) tuple
            targets: List of potential target coordinates as (x, y) tuples

        Returns:
            Tuple of (path, target_reached) where path is the list of coordinates
            and target_reached is the coordinate that was reached.
            Returns ([], None) if no valid targets.
        """
        if not targets:
            return ([], None)

        closest_target = None
        shortest_path = None

        for target in targets:
            path = self.find_path(start, target)
            if shortest_path is None or len(path) < len(shortest_path):
                shortest_path = path
                closest_target = target

        return (shortest_path, closest_target)

    def _is_valid_position(self, row: int, col: int) -> bool:
        """
        Check if a position is valid (within bounds and not a collision block).

        Args:
            row: Row index in the maze
            col: Column index in the maze

        Returns:
            True if position is valid for traversal, False otherwise
        """
        if row < 0 or col < 0:
            return False
        if row >= len(self.maze) or col >= len(self.maze[0]):
            return False
        return self.maze[row][col] != self.collision_block_id

    def _find_path_internal(self, start: tuple, end: tuple) -> list:
        """
        Internal path finding using wave propagation algorithm.

        Args:
            start: Starting coordinate as (row, col) tuple
            end: Ending coordinate as (row, col) tuple

        Returns:
            List of (row, col) coordinate tuples forming the path
        """
        # Build collision map (1 = blocked, 0 = passable) by overlaying the
        # dynamic extra_blocked tiles onto the cached STATIC base grid. We copy
        # each row only when overlaying so the cached base grid is never mutated.
        # Note: extra_blocked uses (x, y) format, maze uses (row, col) = (y, x).
        base_map = self._base_collision_map()
        if self.extra_blocked:
            collision_map = [list(row) for row in base_map]
            for (col_idx, row_idx) in self.extra_blocked:
                if 0 <= row_idx < len(collision_map) and 0 <= col_idx < len(
                    collision_map[row_idx]
                ):
                    collision_map[row_idx][col_idx] = 1
        else:
            # No dynamic blocks: the base grid already equals the final grid.
            # The wave propagation below only READS collision_map, so sharing
            # the cached grid is safe and avoids an O(rows*cols) copy per call.
            collision_map = base_map

        # Initialize distance map
        distance_map = []
        for i in range(len(collision_map)):
            distance_map.append([0] * len(collision_map[i]))

        # Set starting position
        start_row, start_col = start
        distance_map[start_row][start_col] = 1

        # Wave propagation with a maze-size-aware iteration cap.
        #
        # Each wave step assigns distance d+1 to all tiles exactly d edges from
        # the start, so the BFS frontier reaches a target at most `cells` steps
        # away (every passable tile gets a finite distance within `cells`
        # iterations, since no tile can be farther than the number of cells).
        # The old fixed cap of 150 silently truncated any legitimate route
        # longer than 150 tiles on the 88x48 (=4224-tile) Claudeville maze, so
        # distant targets were never reached. Bounding by the total tile count
        # (with a small floor for tiny test mazes) guarantees every reachable
        # target is found while still terminating on unreachable ones.
        self.last_path_truncated = False
        rows = len(collision_map)
        cols = len(collision_map[0]) if rows else 0
        max_iterations = max(150, rows * cols)
        step = 0
        while distance_map[end[0]][end[1]] == 0 and step < max_iterations:
            step += 1
            advanced = self._propagate_wave(collision_map, distance_map, step)
            if not advanced:
                # Wave stagnated: every tile reachable from the start has been
                # assigned and the target is among the unreachable. Stopping now
                # yields the identical (frozen) distance_map the old fixed-cap
                # loop would have produced, so the traced result is unchanged —
                # we just skip the wasteful no-op passes and, crucially, do NOT
                # flag this as a cap-hit truncation (the target is unreachable,
                # not merely too far).
                break

        # NON-SILENT truncation: if we exhausted the cap without reaching the
        # target, the returned path will stop short. Flag it and warn loudly so
        # a truncated route is never mistaken for a completed one. (A genuinely
        # unreachable target stops earlier — when no wave can advance — so this
        # only fires on a real cap hit.)
        if distance_map[end[0]][end[1]] == 0 and step >= max_iterations:
            self.last_path_truncated = True
            logger.warning(
                "PathFinder: wave propagation hit the %d-iteration cap before "
                "reaching target (start=%s end=%s); returning a TRUNCATED path. "
                "The route is incomplete, not a real path.",
                max_iterations,
                (start[1], start[0]),
                (end[1], end[0]),
            )

        # Trace path back from end to start
        row, col = end
        current_distance = distance_map[row][col]
        path = [(row, col)]

        while current_distance > 1:
            # Check all four directions for the previous step
            if row > 0 and distance_map[row - 1][col] == current_distance - 1:
                row = row - 1
                path.append((row, col))
                current_distance -= 1
            elif col > 0 and distance_map[row][col - 1] == current_distance - 1:
                col = col - 1
                path.append((row, col))
                current_distance -= 1
            elif (
                row < len(distance_map) - 1
                and distance_map[row + 1][col] == current_distance - 1
            ):
                row = row + 1
                path.append((row, col))
                current_distance -= 1
            elif (
                col < len(distance_map[row]) - 1
                and distance_map[row][col + 1] == current_distance - 1
            ):
                col = col + 1
                path.append((row, col))
                current_distance -= 1
            else:
                # No valid path found
                break

        path.reverse()
        return path

    def _propagate_wave(
        self, collision_map: list, distance_map: list, step: int
    ) -> bool:
        """
        Propagate the distance wave one step outward.

        Args:
            collision_map: 2D list where 1 = blocked, 0 = passable
            distance_map: 2D list of distances from start
            step: Current step number in wave propagation

        Returns:
            True if at least one new tile was assigned this step, False if the
            wave stagnated (no frontier left to expand). This is purely a
            termination signal; the distances written are identical regardless.
        """
        advanced = False
        for i in range(len(distance_map)):
            for j in range(len(distance_map[i])):
                if distance_map[i][j] == step:
                    # Propagate to adjacent unvisited, passable cells
                    if (
                        i > 0
                        and distance_map[i - 1][j] == 0
                        and collision_map[i - 1][j] == 0
                    ):
                        distance_map[i - 1][j] = step + 1
                        advanced = True
                    if (
                        j > 0
                        and distance_map[i][j - 1] == 0
                        and collision_map[i][j - 1] == 0
                    ):
                        distance_map[i][j - 1] = step + 1
                        advanced = True
                    if (
                        i < len(distance_map) - 1
                        and distance_map[i + 1][j] == 0
                        and collision_map[i + 1][j] == 0
                    ):
                        distance_map[i + 1][j] = step + 1
                        advanced = True
                    if (
                        j < len(distance_map[i]) - 1
                        and distance_map[i][j + 1] == 0
                        and collision_map[i][j + 1] == 0
                    ):
                        distance_map[i][j + 1] = step + 1
                        advanced = True
        return advanced

    @staticmethod
    def closest_coordinate(curr: tuple, target_list: list) -> tuple | None:
        """
        Find the closest coordinate from a list of targets using Euclidean distance.

        Args:
            curr: Current coordinate as (x, y) tuple
            target_list: List of target coordinates as (x, y) tuples

        Returns:
            The closest coordinate tuple, or None if target_list is empty
        """
        if not target_list:
            return None

        min_dist = None
        closest = None

        for coordinate in target_list:
            a = np.array(coordinate)
            b = np.array(curr)
            dist = float(np.linalg.norm(a - b))
            if closest is None or dist < min_dist:
                min_dist = dist
                closest = coordinate

        return closest


# Backwards compatibility wrapper for existing code
def path_finder(maze, start, end, collision_block_char, verbose=False):
    """
    Legacy wrapper function for backwards compatibility.

    Args:
        maze: 2D list representing the maze grid
        start: Starting coordinate as (x, y) tuple
        end: Ending coordinate as (x, y) tuple
        collision_block_char: Character identifying impassable blocks
        verbose: Unused, kept for API compatibility

    Returns:
        List of (x, y) coordinate tuples forming the path
    """
    pf = PathFinder(maze, collision_block_char)
    return pf.find_path(start, end)


def closest_coordinate(curr_coordinate, target_coordinates):
    """
    Legacy wrapper function for backwards compatibility.

    Args:
        curr_coordinate: Current coordinate as (x, y) tuple
        target_coordinates: List of target coordinates as (x, y) tuples

    Returns:
        The closest coordinate tuple, or None if empty
    """
    return PathFinder.closest_coordinate(curr_coordinate, target_coordinates)


if __name__ == "__main__":
    maze = [
        ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
        [" ", " ", "#", " ", " ", " ", " ", " ", "#", " ", " ", " ", "#"],
        ["#", " ", "#", " ", " ", "#", "#", " ", " ", " ", "#", " ", "#"],
        ["#", " ", "#", " ", " ", "#", "#", " ", "#", " ", "#", " ", "#"],
        ["#", " ", " ", " ", " ", " ", " ", " ", "#", " ", " ", " ", "#"],
        ["#", "#", "#", " ", "#", " ", "#", "#", "#", " ", "#", " ", "#"],
        ["#", " ", " ", " ", " ", " ", " ", " ", " ", " ", "#", " ", " "],
        ["#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#", "#"],
    ]

    # Test PathFinder class
    pf = PathFinder(maze, "#")

    print("Test 1: Same start and end")
    start = (0, 1)
    end = (0, 1)
    print(pf.find_path(start, end))

    print("\nTest 2: Path finding")
    start = (0, 1)
    end = (11, 4)
    print(pf.find_path(start, end))

    print("\nTest 3: Find path to nearest")
    start = (0, 1)
    targets = [(11, 4), (12, 6), (5, 3)]
    path, target = pf.find_path_to_nearest(start, targets)
    print(f"Path: {path}")
    print(f"Target reached: {target}")

    print("\nTest 4: Closest coordinate")
    curr = (0, 1)
    coords = [(11, 4), (12, 6), (5, 3)]
    print(PathFinder.closest_coordinate(curr, coords))

    print("\nTest 5: Legacy wrapper compatibility")
    print(path_finder(maze, (0, 1), (11, 4), "#"))
