"""Regression tests for Phase A audit fixes.

Each test class is tagged with the finding ID it locks in (see
docs/PHASE-1-AUDIT.md and docs/IMPROVEMENT-LOG.md). These cover the
deterministic, network-free fixes landed in the first Quick Wins batch.
"""

import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# claude_structure.py imports sibling modules (e.g. `import cli_interface`) with
# bare names, so backend_server must be on sys.path. Matches the bootstrap used
# by test_encounter_tracking / test_async_runtime (see OPS-8 in the audit).
sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.persona.memory_structures.associative_memory import (
    AssociativeMemory,
)
from reverie.backend_server.persona.memory_structures.scratch import Scratch
from reverie.backend_server.persona.prompt_template.claude_structure import (
    parse_step_response,
)


def _fresh_assoc_memory(tmp):
    """An AssociativeMemory backed by empty on-disk stores."""
    with open(os.path.join(tmp, "nodes.json"), "w") as f:
        json.dump({}, f)
    with open(os.path.join(tmp, "kw_strength.json"), "w") as f:
        json.dump({"kw_strength_event": {}, "kw_strength_thought": {}}, f)
    return AssociativeMemory(tmp)


class ScratchSaveLoadTests(unittest.TestCase):
    """MEM-4: a fresh persona (None curr_time/act_start_time) must save/load."""

    def test_save_and_load_fresh_scratch_roundtrips_none_times(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "scratch.json")
            scratch = Scratch(out)  # path absent -> defaults, None times
            self.assertIsNone(scratch.curr_time)
            self.assertIsNone(scratch.act_start_time)

            scratch.save(out)  # previously raised AttributeError on None.strftime

            reloaded = Scratch(out)
            self.assertIsNone(reloaded.curr_time)
            self.assertIsNone(reloaded.act_start_time)


class ActCheckFinishedTests(unittest.TestCase):
    """MEM-9: finished check uses >= rather than exact-second equality."""

    def _scratch_with_action(self, start, duration, now):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Scratch(os.path.join(tmp, "x.json"))
        scratch.act_address = "world:sector:arena:obj"
        scratch.chatting_with = None
        scratch.act_start_time = start
        scratch.act_duration = duration
        scratch.curr_time = now
        return scratch

    def test_finished_when_curr_time_past_end(self):
        start = datetime.datetime(2026, 1, 1, 8, 0, 0)  # ends 08:30
        s = self._scratch_with_action(
            start, 30, datetime.datetime(2026, 1, 1, 8, 45, 0)
        )
        self.assertTrue(s.act_check_finished())

    def test_not_finished_before_end(self):
        start = datetime.datetime(2026, 1, 1, 8, 0, 0)
        s = self._scratch_with_action(
            start, 30, datetime.datetime(2026, 1, 1, 8, 10, 0)
        )
        self.assertFalse(s.act_check_finished())

    def test_none_curr_time_does_not_crash(self):
        start = datetime.datetime(2026, 1, 1, 8, 0, 0)
        s = self._scratch_with_action(start, 30, None)
        self.assertFalse(s.act_check_finished())

    def test_no_address_is_finished(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Scratch(os.path.join(tmp, "x.json"))
        s.act_address = None
        self.assertTrue(s.act_check_finished())


class AssociativeMemoryStrTests(unittest.TestCase):
    """MEM-6: get_str_seq_* must not emit a wrapped-tuple repr."""

    def test_get_str_seq_events_is_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            am = _fresh_assoc_memory(tmp)
            created = datetime.datetime(2026, 1, 1, 8, 0, 0)
            am.add_event(
                created,
                None,
                "Isabella",
                "is",
                "cooking",
                "Isabella is cooking",
                {"Isabella", "cooking"},
                5,
                "ek",
                None,
            )
            out = am.get_str_seq_events()
        self.assertIn("Event 1:", out)
        self.assertIn("Isabella is cooking", out)
        # The buggy version wrapped a literal tuple, leaking "'Event'" (quoted).
        self.assertNotIn("'Event'", out)


class AssociativeMemoryRetrievalTests(unittest.TestCase):
    """MEM-7: keyword lookup must match the lowercase-keyed index."""

    def test_retrieve_relevant_events_matches_capitalized_query(self):
        with tempfile.TemporaryDirectory() as tmp:
            am = _fresh_assoc_memory(tmp)
            created = datetime.datetime(2026, 1, 1, 8, 0, 0)
            am.add_event(
                created,
                None,
                "Isabella",
                "is",
                "cooking",
                "Isabella is cooking",
                {"Isabella", "Cooking"},
                5,
                "ek",
                None,
            )
            # Persona names / objects arrive capitalized; must still match.
            result = am.retrieve_relevant_events("Isabella", "is", "Cooking")
        self.assertEqual(len(result), 1)


class DurationClampTests(unittest.TestCase):
    """LLM-4: duration_minutes must be coerced + clamped (1..1440)."""

    def _parse(self, duration_value):
        body = {
            "action": {
                "description": "cooking",
                "duration_minutes": duration_value,
                "location": {"sector": "", "arena": "", "object": ""},
                "event": ["Isabella", "is", "cooking"],
                "emoji": "🍳",
            }
        }
        return parse_step_response(json.dumps(body), "Isabella", [], {}, {})

    def test_string_duration_defaults_to_30(self):
        self.assertEqual(self._parse("30 minutes").action.duration_minutes, 30)

    def test_null_duration_defaults_to_30(self):
        self.assertEqual(self._parse(None).action.duration_minutes, 30)

    def test_negative_duration_clamped_to_one(self):
        self.assertEqual(self._parse(-5).action.duration_minutes, 1)

    def test_huge_duration_clamped_to_max(self):
        self.assertEqual(self._parse(999999).action.duration_minutes, 1440)

    def test_valid_duration_preserved(self):
        self.assertEqual(self._parse(45).action.duration_minutes, 45)


if __name__ == "__main__":
    unittest.main()
