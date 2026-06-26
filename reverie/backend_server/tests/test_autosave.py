"""Tests for periodic auto-save (the durable fix that makes long runs measurable).

Persona memory (associative/relationships/goals) only reaches disk on save(); a
long/unattended run that is never manually saved loses everything and the eval
harness then reads empty memory/social metrics. _maybe_autosave closes that gap.

These tests exercise the pure cadence predicate and the best-effort wrapper
without a live server or LLM (ReverieServer is built via __new__, matching the
pattern in test_robustness.py).
"""

import sys
import threading
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.reverie import ReverieServer  # noqa: E402


def _server(step=0, every=250, last=0):
    r = ReverieServer.__new__(ReverieServer)
    r.step = step
    r._autosave_every_steps = every
    r._last_autosave_step = last
    r._step_lock = threading.Lock()
    return r


class ShouldAutosaveTests(unittest.TestCase):
    def test_fires_once_interval_elapsed(self):
        r = _server(every=250, last=0)
        self.assertFalse(r._should_autosave(249))
        self.assertTrue(r._should_autosave(250))
        self.assertTrue(r._should_autosave(251))

    def test_respects_last_autosave_marker(self):
        r = _server(every=250, last=250)
        self.assertFalse(r._should_autosave(499))
        self.assertTrue(r._should_autosave(500))

    def test_zero_disables(self):
        r = _server(every=0, last=0)
        self.assertFalse(r._should_autosave(1000))

    def test_no_save_at_fresh_resume(self):
        # A run resumed at step N should not immediately save (last seeded to N).
        r = _server(step=4342, every=250, last=4342)
        self.assertFalse(r._should_autosave(4342))


class MaybeAutosaveTests(unittest.TestCase):
    def _patch_save(self, r):
        calls = {"n": 0}

        def fake_save():
            calls["n"] += 1

        r.save = fake_save
        return calls

    def test_saves_when_due_and_advances_marker(self):
        r = _server(step=300, every=250, last=0)
        calls = self._patch_save(r)
        r._maybe_autosave()
        self.assertEqual(calls["n"], 1)
        self.assertEqual(r._last_autosave_step, 300)
        # Immediately calling again is a no-op (marker advanced).
        r._maybe_autosave()
        self.assertEqual(calls["n"], 1)

    def test_skips_when_not_due(self):
        r = _server(step=100, every=250, last=0)
        calls = self._patch_save(r)
        r._maybe_autosave()
        self.assertEqual(calls["n"], 0)
        self.assertEqual(r._last_autosave_step, 0)

    def test_force_saves_even_when_not_due(self):
        r = _server(step=100, every=250, last=0)
        calls = self._patch_save(r)
        r._maybe_autosave(force=True)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(r._last_autosave_step, 100)

    def test_save_exception_is_swallowed(self):
        r = _server(step=300, every=250, last=0)

        def boom():
            raise RuntimeError("disk full")

        r.save = boom
        # Must not raise; marker stays put so a later save can retry.
        r._maybe_autosave()
        self.assertEqual(r._last_autosave_step, 0)


if __name__ == "__main__":
    unittest.main()
