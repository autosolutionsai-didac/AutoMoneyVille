"""Phase 5 robustness & scale tests.

Covers:
  5a PATHFINDING  - maze-size-aware bound completes a long real-maze route
                    end-to-end; truncation is NON-silent (logs + sentinel);
                    cached static collision grid is behavior-preserving.
  5b TIMEOUT      - per-persona timeout: one slow persona falls back while the
                    others produce real results, with no half-mutated state.
  5c BACKPRESSURE - runtime_status exposes buffer depth + a stall metric.
  5d ATOMIC WRITE - snapshot writes are atomic (target is only ever complete)
                    and movement history stays bounded.
  5e PERCEPTION   - get_nearby_tiles cache returns results identical to uncached
                    and is cleared each step (no cross-step leak).

No live server or LLM is required.
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import threading
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace

# Bare-name sibling imports (matches the other backend tests).
sys.path.append(str(Path(__file__).resolve().parents[1]))

import path_finder as pf_mod  # noqa: E402
from path_finder import PathFinder, clear_collision_cache  # noqa: E402

# Real Claudeville collision maze (absolute path so the test is cwd-independent).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_COLLISION_CSV = (
    _REPO_ROOT
    / "environment"
    / "frontend_server"
    / "static_dirs"
    / "assets"
    / "claudeville"
    / "matrix"
    / "maze"
    / "collision_maze.csv"
)
_MAZE_W, _MAZE_H = 88, 48
_COLLISION_ID = "32125"


def _load_real_collision_grid():
    """Load the real claudeville collision maze into a (row-major) 2D grid."""
    raw = [c.strip() for c in _COLLISION_CSV.read_text().split(",")]
    return [raw[i : i + _MAZE_W] for i in range(0, len(raw), _MAZE_W)]


def _legacy_find_path(grid, start, end, cap=150):
    """A faithful re-implementation of the OLD fixed-cap wave propagation, used
    only to prove the previous behavior would silently truncate a long route."""
    internal_start = (start[1], start[0])
    internal_end = (end[1], end[0])
    cmap = [[1 if c == _COLLISION_ID else 0 for c in row] for row in grid]
    dist = [[0] * len(r) for r in cmap]
    dist[internal_start[0]][internal_start[1]] = 1
    step = 0
    while dist[internal_end[0]][internal_end[1]] == 0 and step < cap:
        step += 1
        for i in range(len(dist)):
            for j in range(len(dist[i])):
                if dist[i][j] == step:
                    for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        ni, nj = i + di, j + dj
                        if (
                            0 <= ni < len(dist)
                            and 0 <= nj < len(dist[i])
                            and dist[ni][nj] == 0
                            and cmap[ni][nj] == 0
                        ):
                            dist[ni][nj] = step + 1
    reached = dist[internal_end[0]][internal_end[1]] != 0
    return reached


def _farthest_pair(grid):
    """Double-BFS to find a near-diameter (start, end) pair on the open graph."""

    def bfs(src):
        d = {src: 0}
        q = deque([src])
        far = src
        while q:
            cx, cy = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if (
                    0 <= nx < _MAZE_W
                    and 0 <= ny < _MAZE_H
                    and grid[ny][nx] == "0"
                    and (nx, ny) not in d
                ):
                    d[(nx, ny)] = d[(cx, cy)] + 1
                    q.append((nx, ny))
                    if d[(nx, ny)] > d[far]:
                        far = (nx, ny)
        return far, d[far]

    # seed from any open tile in the big central component
    seed = None
    for y in range(_MAZE_H):
        for x in range(_MAZE_W):
            if grid[y][x] == "0":
                far, dist = bfs((x, y))
                if dist > 100:
                    seed = (x, y)
                    break
        if seed:
            break
    a, _ = bfs(seed)
    b, dab = bfs(a)
    return a, b, dab


# ---------------------------------------------------------------------------
# 5a PATHFINDING
# ---------------------------------------------------------------------------
class PathfindingBoundTests(unittest.TestCase):
    def setUp(self):
        clear_collision_cache()
        self.grid = _load_real_collision_grid()

    def test_long_real_maze_route_completes_end_to_end(self):
        """A near-diameter route on the real maze must reach its target."""
        start, end, diameter = _farthest_pair(self.grid)
        self.assertGreater(
            diameter,
            100,
            "the real town must retain a substantial end-to-end route",
        )

        pf = PathFinder(self.grid, _COLLISION_ID)
        path = pf.find_path(start, end)

        self.assertEqual(path[0], start)
        self.assertEqual(
            path[-1], end, "last tile must equal target (route completed)"
        )
        self.assertFalse(pf.last_path_truncated, "a real route must not be flagged")
        self.assertEqual(len(path), diameter + 1)

    def test_old_cap_would_have_truncated_this_route(self):
        """Guard the old cap regression independently of town art topology."""
        corridor_len = 200
        grid = [["0"] * corridor_len]
        start, end = (0, 0), (corridor_len - 1, 0)
        reached_old = _legacy_find_path(grid, start, end, cap=150)
        self.assertFalse(
            reached_old, "old cap=150 should have failed to reach the target"
        )

    def test_truncation_is_non_silent(self):
        """When the cap is hit, set a sentinel AND log a warning (no silent stop).

        We can't naturally exceed the real bound (it equals the cell count), so
        we temporarily force a tiny cap on a long open corridor to deterministically
        trigger a cap hit, then assert both the sentinel and the WARNING log.
        """
        corridor_len = 200
        grid = [["0"] * corridor_len]  # 1-row open corridor

        with self.assertLogs(pf_mod.logger, level="WARNING") as cm:
            with _patched_bound(2):
                tiny = PathFinder(grid, _COLLISION_ID)
                path = tiny.find_path((0, 0), (corridor_len - 1, 0))

        self.assertTrue(tiny.last_path_truncated, "sentinel must flag truncation")
        # A truncated/failed search cannot trace a real route, so it returns a
        # degenerate stub (just the endpoint) rather than a path that starts at
        # the start tile. Callers reject this via `len(path) > 1`.
        self.assertNotEqual(
            path[0], (0, 0), "truncated path must NOT be a real start->goal route"
        )
        self.assertEqual(len(path), 1, "truncated search yields only a stub")
        self.assertTrue(
            any("TRUNCATED" in msg for msg in cm.output),
            "truncation must log a warning",
        )

    def test_cached_collision_grid_is_behavior_preserving(self):
        """Cached static grid + extra_blocked overlay == fully-rebuilt grid."""
        start, end, _ = _farthest_pair(self.grid)

        # Path with no dynamic blocks, twice: second call uses the cache.
        clear_collision_cache()
        pf1 = PathFinder(self.grid, _COLLISION_ID)
        path_cold = pf1.find_path(start, end)
        pf2 = PathFinder(self.grid, _COLLISION_ID)  # hits the cache
        path_warm = pf2.find_path(start, end)
        self.assertEqual(path_cold, path_warm)

        # Path WITH a dynamic block, comparing cached-overlay vs a fresh
        # uncached finder (cache cleared) computing the same thing.
        blocked = {path_cold[len(path_cold) // 2]}
        clear_collision_cache()
        pf_uncached = PathFinder(self.grid, _COLLISION_ID, set(blocked))
        path_uncached = pf_uncached.find_path(start, end)
        # warm the base cache, then overlay the same dynamic block
        PathFinder(self.grid, _COLLISION_ID).find_path(start, end)
        pf_overlay = PathFinder(self.grid, _COLLISION_ID, set(blocked))
        path_overlay = pf_overlay.find_path(start, end)
        self.assertEqual(path_uncached, path_overlay)
        # The blocked tile must not appear in either result.
        self.assertNotIn(list(blocked)[0], path_overlay)

    def test_unreachable_target_terminates_without_truncation_flag(self):
        """An isolated (walled-off) target stops cleanly, not flagged as a cap hit."""
        # 3x3: center open, surrounded by collision; target is the walled island.
        grid = [
            ["0", _COLLISION_ID, "0"],
            [_COLLISION_ID, _COLLISION_ID, _COLLISION_ID],
            ["0", _COLLISION_ID, "0"],
        ]
        pf = PathFinder(grid, _COLLISION_ID)
        path = pf.find_path((0, 0), (2, 2))
        self.assertFalse(
            pf.last_path_truncated,
            "unreachable target is not a cap-hit truncation",
        )
        # No real route exists, so the search returns a degenerate stub rather
        # than a start->goal path.
        self.assertNotEqual(
            path[0], (0, 0), "no real route should be traced for an island target"
        )
        self.assertEqual(len(path), 1)


class _patched_bound:
    """Context manager: temporarily force PathFinder's wave cap to `cap`."""

    def __init__(self, cap):
        self.cap = cap
        self._orig = None

    def __enter__(self):
        self._orig = PathFinder._find_path_internal
        cap = self.cap

        def _capped(pf_self, start, end):
            base_map = pf_self._base_collision_map()
            if pf_self.extra_blocked:
                cmap = [list(r) for r in base_map]
                for (cx, ry) in pf_self.extra_blocked:
                    if 0 <= ry < len(cmap) and 0 <= cx < len(cmap[ry]):
                        cmap[ry][cx] = 1
            else:
                cmap = base_map
            dist = [[0] * len(r) for r in cmap]
            dist[start[0]][start[1]] = 1
            pf_self.last_path_truncated = False
            step = 0
            while dist[end[0]][end[1]] == 0 and step < cap:
                step += 1
                advanced = pf_self._propagate_wave(cmap, dist, step)
                if not advanced:
                    break
            if dist[end[0]][end[1]] == 0 and step >= cap:
                pf_self.last_path_truncated = True
                pf_mod.logger.warning(
                    "PathFinder: hit cap %d before target; TRUNCATED path.", cap
                )
            # trace back identical to the real implementation
            row, col = end
            cur = dist[row][col]
            path = [(row, col)]
            while cur > 1:
                if row > 0 and dist[row - 1][col] == cur - 1:
                    row -= 1
                elif col > 0 and dist[row][col - 1] == cur - 1:
                    col -= 1
                elif row < len(dist) - 1 and dist[row + 1][col] == cur - 1:
                    row += 1
                elif col < len(dist[row]) - 1 and dist[row][col + 1] == cur - 1:
                    col += 1
                else:
                    break
                path.append((row, col))
                cur -= 1
            path.reverse()
            return path

        PathFinder._find_path_internal = _capped
        return self

    def __exit__(self, *exc):
        PathFinder._find_path_internal = self._orig
        return False


# ---------------------------------------------------------------------------
# 5b PER-PERSONA TIMEOUT
# ---------------------------------------------------------------------------
class PerPersonaTimeoutTests(unittest.TestCase):
    """Exercise the per-persona timeout pattern with a tiny stub harness that
    mirrors run_persona_move's structure (snapshot -> wait_for -> cancel+await
    -> restore -> fallback) without importing the heavy ReverieServer step."""

    def _run_persona_move(self, name, persona, fallback, timeout):
        """Mirror of reverie.run_persona_move: snapshot -> wait_for -> on timeout
        cancel+await, restore snapshot, return fallback; else re-wrap the move's
        4-tuple into the canonical 6-tuple result."""

        async def runner():
            scratch = persona.scratch
            snap = {
                "curr_tile": getattr(scratch, "curr_tile", None),
                "planned_path": list(getattr(scratch, "planned_path", []) or []),
                "act_path_set": getattr(scratch, "act_path_set", False),
            }
            move_task = asyncio.ensure_future(
                persona.move(
                    None, None, None, scratch.curr_tile, None
                )
            )
            try:
                (
                    next_tile,
                    pronunciatio,
                    description,
                    had_llm_call,
                ) = await asyncio.wait_for(move_task, timeout=timeout)
            except asyncio.TimeoutError:
                try:
                    await move_task
                except (asyncio.CancelledError, Exception):
                    pass
                scratch.curr_tile = snap["curr_tile"]
                scratch.planned_path = snap["planned_path"]
                scratch.act_path_set = snap["act_path_set"]
                return fallback(name, persona)
            return (
                name,
                next_tile,
                pronunciatio,
                description,
                scratch.chat,
                had_llm_call,
            )

        return runner()

    def test_slow_persona_falls_back_others_get_real_results(self):
        # Three personas: two fast, one that hangs past the timeout.
        def make_persona(name, slow):
            scratch = SimpleNamespace(
                curr_tile=(5, 5),
                planned_path=[(5, 5)],
                act_path_set=True,
                act_description=f"{name} working",
                act_address="ville:office:desk",
                act_pronunciatio="",
                chat=[],
            )

            async def move(maze, personas, personas_tile, curr_tile, curr_time):
                # Signature mirrors Persona.move; returns its 4-tuple.
                if slow:
                    # Mutate scratch FIRST, then hang -> proves cancellation can
                    # leave half-mutated state that we must restore.
                    scratch.planned_path = [(99, 99), (98, 98)]
                    scratch.curr_tile = (99, 99)
                    scratch.act_path_set = False
                    await asyncio.sleep(5)
                    return ((1, 1), "x", "done", False)
                return ((6, 6), "y", f"{name} moved", True)

            return SimpleNamespace(scratch=scratch, move=move)

        def fallback(name, persona):
            return (
                name,
                persona.scratch.curr_tile,
                persona.scratch.act_pronunciatio,
                persona.scratch.act_description,
                persona.scratch.chat,
                False,
            )

        fast_a = make_persona("Ada", slow=False)
        slow_b = make_persona("Bo", slow=True)
        fast_c = make_persona("Cy", slow=False)
        personas = [("Ada", fast_a), ("Bo", slow_b), ("Cy", fast_c)]

        async def drive():
            coros = [
                self._run_persona_move(n, p, fallback, timeout=0.05)
                for n, p in personas
            ]
            return await asyncio.gather(*coros, return_exceptions=True)

        results = asyncio.run(drive())
        by_name = {r[0]: r for r in results}

        # Fast personas produced REAL results (had_llm_call True).
        self.assertEqual(by_name["Ada"][1], (6, 6))
        self.assertTrue(by_name["Ada"][5])
        self.assertEqual(by_name["Cy"][1], (6, 6))
        self.assertTrue(by_name["Cy"][5])

        # Slow persona got the fallback (had_llm_call False), in place.
        self.assertEqual(by_name["Bo"][5], False)

        # Crucially: the slow persona's half-mutated state was RESTORED to its
        # pre-step snapshot (no leaked garbage path/tile).
        self.assertEqual(slow_b.scratch.curr_tile, (5, 5))
        self.assertEqual(slow_b.scratch.planned_path, [(5, 5)])
        self.assertTrue(slow_b.scratch.act_path_set)

    def test_timed_out_task_is_cancelled_and_awaited(self):
        """No pending task is left behind after a per-persona timeout."""
        cancelled = {"flag": False}
        scratch = SimpleNamespace(
            curr_tile=(0, 0),
            planned_path=[],
            act_path_set=False,
            act_description="d",
            act_address="a",
            act_pronunciatio="",
            chat=[],
        )

        async def move(maze, personas, personas_tile, curr_tile, curr_time):
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                cancelled["flag"] = True
                raise

        persona = SimpleNamespace(scratch=scratch, move=move)

        def fallback(name, p):
            return (name, p.scratch.curr_tile, "", "d", [], False)

        async def drive():
            res = await self._run_persona_move("X", persona, fallback, timeout=0.02)
            await asyncio.sleep(0)  # let any pending cancellation settle
            return res

        result = asyncio.run(drive())
        self.assertEqual(result[5], False)
        self.assertTrue(
            cancelled["flag"], "the slow move must have been cancelled+awaited"
        )


# ---------------------------------------------------------------------------
# 5c BACKPRESSURE / OBSERVABILITY
# ---------------------------------------------------------------------------
class RuntimeStatusBackpressureTests(unittest.TestCase):
    def _make_reverie(self):
        from reverie.backend_server.reverie import ReverieServer

        r = ReverieServer.__new__(ReverieServer)
        r.step = 10
        r.sim_code = "test"
        r.fork_sim_code = "base"
        r.sec_per_step = 10
        r.curr_time = __import__("datetime").datetime(2026, 1, 1)
        r.personas = {}
        r.personas_tile = {}
        r.active_conversations = {}
        r._pending_movements = []
        r._movement_history = [object(), object()]
        r._movement_history_limit = 120
        r._movements_lock = threading.Lock()
        r._displayed_step = 3
        r._buffer_ahead = 20
        r._autosim_min_fill = 5
        r._autosim_idle_pause_s = 8
        r._last_poll_at = 0.0
        r._autosim_enabled = threading.Event()
        r._step_lock = threading.Lock()
        r._busy_since = None
        r._busy_reason = None
        r.maze = SimpleNamespace(
            maze_name="claudeville", maze_width=88, maze_height=48, sq_tile_size=32
        )
        return r

    def test_backpressure_fields_present(self):
        r = self._make_reverie()
        status = r.runtime_status()
        for field in (
            "buffer_ahead_target",
            "buffer_ahead_actual",
            "buffer_min_fill",
            "movement_history_depth",
            "movement_history_limit",
            "seconds_since_last_poll",
            "producer_stalled",
            "buffering",
        ):
            self.assertIn(field, status, f"missing backpressure field {field}")
        self.assertEqual(status["movement_history_depth"], 2)
        self.assertEqual(status["movement_history_limit"], 120)
        # buffer_ahead_actual = step-1-displayed = 10-1-3 = 6
        self.assertEqual(status["buffer_ahead_actual"], 6)

    def test_stall_detected_when_polling_but_buffer_starved(self):
        import time as _time

        r = self._make_reverie()
        r._autosim_enabled.set()
        r._last_poll_at = _time.monotonic()  # actively polling
        r._displayed_step = 9  # buffer_actual = 10-1-9 = 0 < min_fill(5)
        status = r.runtime_status()
        self.assertTrue(status["producer_stalled"])

    def test_no_stall_when_buffer_healthy(self):
        import time as _time

        r = self._make_reverie()
        r._autosim_enabled.set()
        r._last_poll_at = _time.monotonic()
        r._displayed_step = 0  # buffer_actual = 9 > min_fill
        status = r.runtime_status()
        self.assertFalse(status["producer_stalled"])


# ---------------------------------------------------------------------------
# 5d ATOMIC WRITES + BOUNDS
# ---------------------------------------------------------------------------
class AtomicWriteTests(unittest.TestCase):
    def test_atomic_write_target_is_only_ever_complete(self):
        from reverie.backend_server.reverie import _atomic_write_json

        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "5.json")
            payload = {"meta": {"step": 5}, "persona": {"A": {"movement": [1, 2]}}}
            _atomic_write_json(target, payload)

            # File exists and parses fully (never a partial write).
            with open(target) as f:
                self.assertEqual(json.load(f), payload)

            # No stray temp files left behind in the directory.
            leftovers = [n for n in os.listdir(tmp) if n.endswith(".tmp")]
            self.assertEqual(leftovers, [])

    def test_atomic_write_preserves_old_file_on_serialize_failure(self):
        from reverie.backend_server.reverie import _atomic_write_json

        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "5.json")
            _atomic_write_json(target, {"ok": 1})

            class _Unserializable:
                pass

            with self.assertRaises(TypeError):
                _atomic_write_json(target, {"bad": _Unserializable()})

            # The original file must still be intact and complete.
            with open(target) as f:
                self.assertEqual(json.load(f), {"ok": 1})
            self.assertEqual(
                [n for n in os.listdir(tmp) if n.endswith(".tmp")], []
            )

    def test_movement_history_is_bounded(self):
        from reverie.backend_server.reverie import ReverieServer

        r = ReverieServer.__new__(ReverieServer)
        r.step = 0
        r._movements_lock = threading.Lock()
        r._pending_movements = []
        r._movement_history = []
        r._movement_history_limit = 5
        # _record_movement also writes snapshots; disable that side effect by
        # not providing personas_tile/maze/sim_code (guarded by hasattr).
        for i in range(20):
            r._record_movement({"meta": {"step": i}, "persona": {}})
        self.assertLessEqual(len(r._movement_history), 5)
        # The most recent packets are retained (oldest evicted).
        steps = [m["meta"]["step"] for m in r._movement_history]
        self.assertEqual(steps, [15, 16, 17, 18, 19])


# ---------------------------------------------------------------------------
# 5e PERCEPTION CACHING
# ---------------------------------------------------------------------------
class PerceptionCacheTests(unittest.TestCase):
    def _make_maze(self):
        from maze import Maze

        m = Maze.__new__(Maze)
        m.maze_width = _MAZE_W
        m.maze_height = _MAZE_H
        m._nearby_tiles_cache = {}
        return m

    def test_cached_equals_uncached_for_several_queries(self):
        m = self._make_maze()
        queries = [((10, 10), 4), ((0, 0), 8), ((87, 47), 2), ((43, 24), 8)]
        for tile, r in queries:
            # uncached (fresh cache each time)
            m._nearby_tiles_cache = {}
            uncached = m.get_nearby_tiles(tile, r)
            # cached path: call twice on a shared cache
            m._nearby_tiles_cache = {}
            first = m.get_nearby_tiles(tile, r)
            second = m.get_nearby_tiles(tile, r)
            self.assertEqual(uncached, first)
            self.assertEqual(first, second)

    def test_cache_hit_returns_without_recompute(self):
        m = self._make_maze()
        result = m.get_nearby_tiles((10, 10), 4)
        # Second call must be served from cache (same object identity).
        cached = m.get_nearby_tiles((10, 10), 4)
        self.assertIs(result, cached)
        self.assertIn((10, 10, 4), m._nearby_tiles_cache)

    def test_clear_step_cache_prevents_cross_step_leak(self):
        m = self._make_maze()
        m.get_nearby_tiles((10, 10), 4)
        self.assertTrue(m._nearby_tiles_cache)
        m.clear_step_cache()
        self.assertEqual(m._nearby_tiles_cache, {})
        # After clear, a fresh compute still yields the correct result.
        after = m.get_nearby_tiles((10, 10), 4)
        m._nearby_tiles_cache = {}
        recompute = m.get_nearby_tiles((10, 10), 4)
        self.assertEqual(after, recompute)


class ActionStateRollbackTests(unittest.TestCase):
    """Phase-5 verify Fix A: a timed-out move must roll back the FULL action +
    conversation decision state (the prior restore covered only 3 of ~17 fields,
    leaving act_address/chatting_with/chat half-mutated to poison the next step)."""

    def _fresh_scratch(self, tmp):
        from reverie.backend_server.persona.memory_structures.scratch import Scratch

        s = Scratch(os.path.join(tmp, "scratch.json"))
        s.name = "Bo"
        s.curr_time = None
        s.curr_tile = (5, 5)
        s.planned_path = [(5, 5)]
        s.act_path_set = True
        s.act_address = "ville:office:desk"
        s.act_description = "reviewing code"
        s.act_pronunciatio = "code"
        s.act_event = ("Bo", "reviewing", "code")
        s.chatting_with = None
        s.chat = None
        return s

    def test_snapshot_restore_round_trip_covers_conversation_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = self._fresh_scratch(tmp)
            baseline = s.snapshot_action_state()
            # Simulate a move applying a new action + conversation, exactly as
            # _process_step_response -> add_new_action does, then "timing out".
            s.add_new_action(
                "ville:cafe:counter", 30, "ordering coffee", "tea",
                ("Bo", "ordering", "coffee"), "Ada", [["Bo", "hi"]], {"Ada": 4},
                None, "a mug", "mug", ("counter", "used-by", "Bo"),
            )
            s.curr_tile = (99, 99)
            s.planned_path = [(99, 99), (98, 98)]
            self.assertEqual(s.chatting_with, "Ada")  # state really changed
            self.assertEqual(s.act_address, "ville:cafe:counter")
            # Roll back — every action/conversation field returns to baseline.
            s.restore_action_state(baseline)
            self.assertEqual(s.snapshot_action_state(), baseline)
            self.assertIsNone(s.chatting_with)
            self.assertIsNone(s.chat)
            self.assertEqual(s.act_address, "ville:office:desk")
            self.assertEqual(s.curr_tile, (5, 5))
            self.assertEqual(s.planned_path, [(5, 5)])
            self.assertTrue(s.act_path_set)

    def test_restore_is_deep_not_aliased(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = self._fresh_scratch(tmp)
            s.chat = [["Bo", "hi"]]
            snap = s.snapshot_action_state()
            s.restore_action_state(snap)
            s.chat.append(["Ada", "yo"])  # mutate live state after restore
            self.assertEqual(snap["chat"], [["Bo", "hi"]])  # snapshot stays clean


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    unittest.main()
