"""Phase 4 tests: multi-day goals, structured compaction, and identity drift.

Covers:
- GoalMemory add / update_progress / mark / get_active / to_prompt_block.
- Carry-over across a simulated day rollover: unfinished goals & promises
  survive, done ones don't resurface.
- Promise capture from a conversation (heuristic, keyword-only).
- Sub-goal decomposition (4b) and save/load round-trip.
- Structured-compaction dataclass round-trip preserving a promise + goal +
  relationship (4c), tolerating a free-text fallback.
- Identity-drift score parsing + clamping into [0, 1] (4e), plus the eval
  metric over a synthetic ledger.

Hard constraint D-002: NO vector embeddings (this is heuristic + text only).
"""

import datetime
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

# claude_structure.py imports sibling modules with bare names, so
# backend_server must be on sys.path (matches the other backend tests).
sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.persona.memory_structures.goal_memory import (
    GoalMemory,
    looks_like_promise,
)
from reverie.backend_server.persona.prompt_template.claude_structure import (
    CompactionSummary,
    parse_compaction_summary,
    parse_day_planning_response,
    parse_identity_update_response,
)

_WHEN = datetime.datetime(2026, 6, 22, 9, 0, 0)
_NEXT_DAY = datetime.datetime(2026, 6, 23, 7, 0, 0)


class Phase4VerifyRegressionTests(unittest.TestCase):
    """Locks in the fixes for the 7 defects the Phase-4 verification found."""

    def test_completed_goal_does_not_block_restatement(self):
        # #1: a goal finished on a previous day must NOT swallow today's identical
        # daily requirement via dedupe — it should resurface as a fresh active goal.
        g = GoalMemory()
        first = g.add("Work on the mural", when=_WHEN)
        g.mark(first["id"], "done", when=_WHEN)
        again = g.add("Work on the mural", when=_NEXT_DAY)  # dedupe=True default
        self.assertNotEqual(again["id"], first["id"])
        self.assertEqual(again["status"], "active")
        self.assertEqual(g.get(first["id"])["status"], "done")
        self.assertIn(again, g.get_active())

    def test_persist_flushes_to_remembered_dir(self):
        # #6: goals folded in mid-session (compaction) must reach disk without the
        # caller knowing the path.
        with tempfile.TemporaryDirectory() as tmp:
            g = GoalMemory(tmp)  # binds tmp as the save dir (no file yet)
            g.add("Ship the prototype", kind="promise", when=_WHEN)
            self.assertTrue(g.persist())
            self.assertTrue(os.path.exists(os.path.join(tmp, "goals.json")))
            reloaded = GoalMemory(tmp)
            self.assertEqual(len(reloaded.get_active()), 1)

    def test_persist_noop_without_dir(self):
        self.assertFalse(GoalMemory().persist())

    def test_apply_goal_updates_completion_not_reverted(self):
        # #4: progress >= 1.0 auto-marks done; a contradictory explicit status
        # must not revert it to active (which would resurface forever).
        from reverie.backend_server.persona.persona import Persona
        from reverie.backend_server.persona.prompt_template.claude_structure import (
            GoalUpdate,
        )

        g = GoalMemory()
        rec = g.add("Finish the report", when=_WHEN)
        p = Persona.__new__(Persona)
        p.g_mem = g
        p.scratch = types.SimpleNamespace(curr_time=_WHEN)
        upd = GoalUpdate(goal_id=rec["id"], progress=1.0, status="active")
        p._apply_goal_updates([upd])
        self.assertEqual(g.get(rec["id"])["status"], "done")
        self.assertEqual(g.get(rec["id"])["progress"], 1.0)
        # An explicit non-completing status is still honored.
        rec2 = g.add("Outline chapter 2", when=_WHEN)
        p._apply_goal_updates([GoalUpdate(goal_id=rec2["id"], status="blocked")])
        self.assertEqual(g.get(rec2["id"])["status"], "blocked")

    def test_initial_traits_persist_across_reload(self):
        # #2: the drift baseline (initial innate/learned) must survive save/load so
        # day-2+ drift measures against the ORIGINAL character, not an evolved one.
        from reverie.backend_server.persona.memory_structures.scratch import Scratch

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scratch.json")
            s = Scratch(path)  # file absent -> defaults
            s.name = "Tester"
            s.innate = "curious, blunt"
            s.learned = "is a baker"
            s.initial_innate = s.innate
            s.initial_learned = s.learned
            s.save(path)
            # Simulate identity evolution overwriting the live traits, then reload.
            s.learned = "is a baker turned poet"
            s.save(path)
            reloaded = Scratch(path)
            self.assertEqual(reloaded.initial_innate, "curious, blunt")
            self.assertEqual(reloaded.initial_learned, "is a baker")
            self.assertEqual(reloaded.learned, "is a baker turned poet")


class GoalMemoryBasicsTests(unittest.TestCase):
    def test_add_assigns_ids_and_defaults(self):
        g = GoalMemory()
        rec = g.add("Finish the mural", kind="project", when=_WHEN)
        self.assertEqual(rec["id"], "g1")
        self.assertEqual(rec["kind"], "project")
        self.assertEqual(rec["status"], "active")
        self.assertEqual(rec["progress"], 0.0)
        self.assertEqual(rec["created_day"], "2026-06-22")
        # Second goal gets a fresh id.
        self.assertEqual(g.add("Read a book", when=_WHEN)["id"], "g2")

    def test_add_dedupes_identical_text(self):
        g = GoalMemory()
        a = g.add("Plant tomatoes", when=_WHEN)
        b = g.add("plant tomatoes", source="day plan", when=_WHEN)
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(len(g.goals), 1)
        # Newly-supplied source backfills onto the existing record.
        self.assertEqual(g.get("g1")["source"], "day plan")

    def test_empty_text_is_ignored(self):
        g = GoalMemory()
        self.assertIsNone(g.add("   "))
        self.assertEqual(len(g.goals), 0)

    def test_invalid_kind_and_status_coerced(self):
        g = GoalMemory()
        rec = g.add("X", kind="nonsense", status="weird", when=_WHEN)
        self.assertEqual(rec["kind"], "goal")
        self.assertEqual(rec["status"], "active")

    def test_update_progress_clamps_and_auto_completes(self):
        g = GoalMemory()
        rec = g.add("Train for race", when=_WHEN)
        g.update_progress(rec["id"], 0.4, note="ran 5k", when=_WHEN)
        self.assertEqual(g.get(rec["id"])["progress"], 0.4)
        self.assertIn("ran 5k", g.get(rec["id"])["notes"])
        # Over 1.0 clamps and auto-marks done.
        g.update_progress(rec["id"], 1.5, when=_WHEN)
        self.assertEqual(g.get(rec["id"])["progress"], 1.0)
        self.assertEqual(g.get(rec["id"])["status"], "done")
        # Below 0.0 clamps to 0.
        rec2 = g.add("Negative", when=_WHEN)
        g.update_progress(rec2["id"], -3, when=_WHEN)
        self.assertEqual(g.get(rec2["id"])["progress"], 0.0)

    def test_mark_status_and_unknown_id(self):
        g = GoalMemory()
        rec = g.add("Blocked thing", when=_WHEN)
        g.mark(rec["id"], "blocked", when=_WHEN)
        self.assertEqual(g.get(rec["id"])["status"], "blocked")
        self.assertIsNone(g.mark("nope", "done"))
        self.assertIsNone(g.update_progress("nope", 0.5))

    def test_get_active_filters_and_orders(self):
        g = GoalMemory()
        a = g.add("A", when=_WHEN)
        b = g.add("B", when=_WHEN)
        c = g.add("C", when=_WHEN)
        g.mark(b["id"], "done", when=_WHEN)
        active = g.get_active()
        ids = [r["id"] for r in active]
        # Done goal excluded; order preserved by creation (ascending id).
        self.assertEqual(ids, [a["id"], c["id"]])
        # Blocked counts as open unless excluded.
        g.mark(c["id"], "blocked", when=_WHEN)
        self.assertIn(c["id"], [r["id"] for r in g.get_active(include_blocked=True)])
        self.assertNotIn(
            c["id"], [r["id"] for r in g.get_active(include_blocked=False)]
        )


class GoalMemoryPromptRenderTests(unittest.TestCase):
    def test_to_prompt_block_shows_only_open_goals(self):
        g = GoalMemory()
        open_goal = g.add("Write a song", kind="goal", when=_WHEN)
        g.update_progress(open_goal["id"], 0.5, when=_WHEN)
        done = g.add("Old chore", when=_WHEN)
        g.mark(done["id"], "done", when=_WHEN)
        block = g.to_prompt_block()
        self.assertIn("ONGOING GOALS & COMMITMENTS", block)
        self.assertIn("Write a song", block)
        self.assertIn("50%", block)
        self.assertNotIn("Old chore", block)

    def test_prompt_block_empty_when_no_open_goals(self):
        g = GoalMemory()
        self.assertEqual(g.to_prompt_block(), "")
        rec = g.add("done already", when=_WHEN)
        g.mark(rec["id"], "abandoned", when=_WHEN)
        self.assertEqual(g.to_prompt_block(), "")

    def test_to_step_line_compact(self):
        g = GoalMemory()
        g.add("Goal one", when=_WHEN)
        line = g.to_step_line()
        self.assertTrue(line.startswith("Open goals:"))
        self.assertIn("Goal one", line)
        self.assertEqual(GoalMemory().to_step_line(), "")


class GoalMemorySubGoalsTests(unittest.TestCase):
    def test_set_sub_goals_normalizes_strings_and_dicts(self):
        g = GoalMemory()
        rec = g.add("Launch site", kind="project", when=_WHEN)
        g.set_sub_goals(
            rec["id"],
            [
                "design layout",
                {"text": "write copy", "status": "blocked", "progress": 0.2},
            ],
            when=_WHEN,
        )
        subs = g.get(rec["id"])["sub_goals"]
        self.assertEqual(len(subs), 2)
        self.assertEqual(subs[0], {"text": "design layout", "status": "active",
                                   "progress": 0.0})
        self.assertEqual(subs[1]["status"], "blocked")
        self.assertEqual(subs[1]["progress"], 0.2)
        # Sub-goals render into the prompt block.
        self.assertIn("design layout", g.to_prompt_block())


class PromiseCaptureTests(unittest.TestCase):
    def test_looks_like_promise_heuristic(self):
        self.assertTrue(looks_like_promise("I'll help you move tomorrow"))
        self.assertTrue(looks_like_promise("I promise to bring the book"))
        self.assertFalse(looks_like_promise("How are you doing today?"))
        self.assertFalse(looks_like_promise(""))

    def test_capture_promises_from_chat_only_self_lines(self):
        g = GoalMemory()
        chat = [
            ["Tester", "Hey Alice, how's it going?"],
            ["Alice", "Good! Can you help me Saturday?"],
            ["Tester", "I'll help you move on Saturday, for sure."],
            ["Alice", "I'll bake you cookies as thanks."],  # not Tester -> ignored
        ]
        made = g.capture_promises_from_chat(
            "Tester", chat, partner="Alice", when=_WHEN
        )
        self.assertEqual(len(made), 1)
        self.assertEqual(made[0]["kind"], "promise")
        self.assertEqual(made[0]["source"], "promised Alice")
        self.assertIn("Saturday", made[0]["text"])
        # The partner's promise was not captured into THIS persona's memory.
        texts = [r["text"] for r in g.goals.values()]
        self.assertNotIn("I'll bake you cookies as thanks.", texts)


class CarryOverTests(unittest.TestCase):
    def test_unfinished_survive_done_does_not_resurface(self):
        """Simulate a day rollover: open goals carry over, done ones don't."""
        g = GoalMemory()
        ongoing = g.add("Finish the novel", kind="project", when=_WHEN)
        g.update_progress(ongoing["id"], 0.6, when=_WHEN)
        promise = g.add("I'll fix Bob's fence", kind="promise", when=_WHEN)
        finished = g.add("Buy groceries", when=_WHEN)
        g.mark(finished["id"], "done", when=_WHEN)

        # Day rollover: GoalMemory is NOT wiped (unlike daily_req).
        carried = g.carry_over(new_day=_NEXT_DAY)
        self.assertEqual(carried, 2)  # novel + fence promise

        active_after = {r["id"] for r in g.get_active()}
        self.assertIn(ongoing["id"], active_after)
        self.assertIn(promise["id"], active_after)
        self.assertNotIn(finished["id"], active_after)

        # The carried-over goal kept its progress across the rollover.
        self.assertEqual(g.get(ongoing["id"])["progress"], 0.6)
        # The finished goal remains stored as history but never resurfaces.
        self.assertEqual(g.get(finished["id"])["status"], "done")
        self.assertNotIn("Buy groceries", g.to_prompt_block())


class SaveLoadRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_goals_and_next_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = GoalMemory()
            rec = g.add(
                "Master the cello",
                kind="project",
                source="day plan",
                target_day="2026-07-01",
                when=_WHEN,
            )
            g.update_progress(rec["id"], 0.3, note="practiced scales", when=_WHEN)
            g.set_sub_goals(
                rec["id"], ["learn bowing", "learn vibrato"], when=_WHEN
            )
            promise = g.add("I'll call Mom", kind="promise", when=_WHEN)
            g.save(tmp)

            self.assertTrue(os.path.exists(os.path.join(tmp, "goals.json")))

            g2 = GoalMemory(tmp)
            self.assertEqual(len(g2.goals), 2)
            loaded = g2.get(rec["id"])
            self.assertEqual(loaded["progress"], 0.3)
            self.assertEqual(loaded["target_day"], "2026-07-01")
            self.assertIn("practiced scales", loaded["notes"])
            self.assertEqual(len(loaded["sub_goals"]), 2)
            self.assertEqual(g2.get(promise["id"])["kind"], "promise")
            # next_id continues past loaded ids (no collisions).
            new_rec = g2.add("Brand new goal", when=_WHEN)
            self.assertEqual(new_rec["id"], "g3")

    def test_missing_file_starts_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = GoalMemory(tmp)
            self.assertEqual(g.goals, {})
            self.assertEqual(g.add("first", when=_WHEN)["id"], "g1")

    def test_corrupt_file_tolerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "goals.json"), "w") as f:
                f.write("{not valid json")
            g = GoalMemory(tmp)
            self.assertEqual(g.goals, {})


class StructuredCompactionTests(unittest.TestCase):
    def test_round_trip_preserves_promise_goal_relationship(self):
        text = """Here is my memory:
        {
          "narrative": "A busy day at the studio.",
          "commitments": ["I promised Alice I'd help her move Saturday"],
          "relationships": [
            {"name": "Alice", "sentiment": "close", "note": "trusts me"}
          ],
          "open_goals": [
            {"text": "finish the commission", "progress": 0.7}
          ],
          "identity_markers": ["I am a dependable friend"],
          "mood": "tired but content"
        }
        """
        summary = parse_compaction_summary(text)
        self.assertEqual(summary.commitments,
                         ["I promised Alice I'd help her move Saturday"])
        self.assertEqual(summary.relationships[0]["name"], "Alice")
        self.assertEqual(summary.relationships[0]["sentiment"], "close")
        self.assertEqual(summary.open_goals[0]["text"], "finish the commission")
        self.assertEqual(summary.open_goals[0]["progress"], 0.7)
        self.assertIn("dependable friend", summary.identity_markers[0])
        self.assertEqual(summary.mood, "tired but content")

        # Human-readable rendering carries every preserved field forward.
        rendered = summary.to_prompt_text()
        self.assertIn("promised Alice", rendered)
        self.assertIn("Alice", rendered)
        self.assertIn("finish the commission", rendered)
        self.assertIn("dependable friend", rendered)

    def test_free_text_fallback_when_not_json(self):
        summary = parse_compaction_summary("Just some free-text thoughts.")
        self.assertTrue(summary.parse_errors)
        self.assertEqual(summary.narrative, "Just some free-text thoughts.")
        # Rendering still returns the narrative so nothing is lost.
        self.assertIn("free-text", summary.to_prompt_text())

    def test_progress_clamped_in_open_goals(self):
        summary = parse_compaction_summary(
            '{"open_goals": [{"text": "g", "progress": 5}]}'
        )
        self.assertEqual(summary.open_goals[0]["progress"], 1.0)

    def test_empty_compaction_renders_empty(self):
        self.assertEqual(CompactionSummary().to_prompt_text(), "")


class IdentityDriftParsingTests(unittest.TestCase):
    def test_drift_score_parsed_and_clamped(self):
        r = parse_identity_update_response(
            '{"drift_score": 0.35, "drift_note": "mostly in character",'
            ' "currently": "now a baker", "learned": "loves bread",'
            ' "identity_markers": ["I bake daily"]}'
        )
        self.assertEqual(r.drift_score, 0.35)
        self.assertEqual(r.drift_note, "mostly in character")
        self.assertEqual(r.currently, "now a baker")
        self.assertEqual(r.learned, "loves bread")
        self.assertEqual(r.identity_markers, ["I bake daily"])
        self.assertEqual(r.parse_errors, [])

    def test_drift_score_clamped_high_and_low(self):
        self.assertEqual(
            parse_identity_update_response('{"drift_score": 9}').drift_score, 1.0
        )
        self.assertEqual(
            parse_identity_update_response('{"drift_score": -4}').drift_score, 0.0
        )

    def test_bad_drift_score_defaults_to_zero(self):
        r = parse_identity_update_response('{"drift_score": "lots"}')
        self.assertEqual(r.drift_score, 0.0)
        self.assertTrue(r.parse_errors)

    def test_no_json_yields_parse_error(self):
        r = parse_identity_update_response("no json here")
        self.assertTrue(r.parse_errors)
        self.assertEqual(r.drift_score, 0.0)


class DayPlanGoalUpdatesTests(unittest.TestCase):
    def test_goal_updates_parsed_from_day_plan(self):
        text = """{
          "wake_up_hour": 7,
          "daily_goals": ["work on the mural"],
          "schedule": [{"activity": "sleeping", "duration_minutes": 1440}],
          "goal_updates": [
            {"goal_text": "work on the mural", "progress": 0.5, "status": "active",
             "note": "half done",
             "sub_goals": [
               {"text": "sketch", "status": "done", "progress": 1.0},
               {"text": "paint", "status": "active"}
             ]}
          ]
        }"""
        plan = parse_day_planning_response(text)
        self.assertEqual(len(plan.goal_updates), 1)
        upd = plan.goal_updates[0]
        self.assertEqual(upd.goal_text, "work on the mural")
        self.assertEqual(upd.progress, 0.5)
        self.assertEqual(upd.status, "active")
        self.assertEqual(len(upd.sub_goals), 2)
        self.assertEqual(upd.sub_goals[0]["text"], "sketch")

    def test_goal_updates_absent_is_empty_list(self):
        text = """{
          "wake_up_hour": 7,
          "daily_goals": [],
          "schedule": [{"activity": "sleeping", "duration_minutes": 1440}]
        }"""
        plan = parse_day_planning_response(text)
        self.assertEqual(plan.goal_updates, [])


if __name__ == "__main__":
    unittest.main()
