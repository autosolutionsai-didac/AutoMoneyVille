"""Phase 3 tests: relationship & theory-of-mind memory.

Covers: RelationshipMemory.observe_interaction / note_from_chat update
familiarity + affinity + topics; to_prompt_block renders only nearby known
people; save/load round-trip; and build_step_prompt injects the
"PEOPLE YOU KNOW (nearby)" section when a known nearby persona exists.

Hard constraint D-002: NO vector embeddings (this module is heuristic +
keyword-keyed text only).
"""

import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# claude_structure.py imports sibling modules with bare names, so
# backend_server must be on sys.path (matches the other backend tests).
sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.persona.memory_structures.associative_memory import (
    AssociativeMemory,
)
from reverie.backend_server.persona.memory_structures.relationship_memory import (
    RelationshipMemory,
)
from reverie.backend_server.persona.memory_structures.scratch import Scratch
from reverie.backend_server.persona.prompt_template.claude_structure import (
    build_step_prompt,
)


def _fresh_assoc_memory(tmp):
    """An AssociativeMemory backed by empty on-disk stores."""
    with open(os.path.join(tmp, "nodes.json"), "w") as f:
        json.dump({}, f)
    with open(os.path.join(tmp, "kw_strength.json"), "w") as f:
        json.dump({"kw_strength_event": {}, "kw_strength_thought": {}}, f)
    return AssociativeMemory(tmp)


def _fresh_scratch(tmp, name="Tester"):
    scratch = Scratch(os.path.join(tmp, "scratch.json"))
    scratch.name = name
    scratch.curr_time = datetime.datetime(2026, 1, 1, 9, 0, 0)
    return scratch


class _StubPersona:
    """Minimal persona shell for build_step_prompt (Phase 3 fields only)."""

    def __init__(self, scratch, r_mem):
        self.name = scratch.name
        self.scratch = scratch
        self.r_mem = r_mem


class ObserveInteractionTests(unittest.TestCase):
    def test_observe_bumps_familiarity_and_applies_affinity(self):
        r = RelationshipMemory()
        r.observe_interaction("Alex", affinity_delta=0.3)
        r.observe_interaction("Alex", affinity_delta=0.2, topics=["coffee"])
        rec = r.get("Alex")
        self.assertEqual(rec["familiarity"], 2)
        self.assertAlmostEqual(rec["affinity"], 0.5)
        self.assertIn("coffee", rec["last_topics"])
        # Sentiment label tracks affinity.
        self.assertEqual(rec["sentiment"], "friendly")

    def test_affinity_clamped_to_unit_range(self):
        r = RelationshipMemory()
        for _ in range(50):
            r.observe_interaction("Bea", affinity_delta=0.9)
        self.assertLessEqual(r.get("Bea")["affinity"], 1.0)
        for _ in range(100):
            r.observe_interaction("Bea", affinity_delta=-0.9)
        self.assertGreaterEqual(r.get("Bea")["affinity"], -1.0)

    def test_get_is_case_insensitive(self):
        r = RelationshipMemory()
        r.observe_interaction("Maria Lopez")
        self.assertIsNotNone(r.get("maria lopez"))
        self.assertIsNotNone(r.get("MARIA LOPEZ"))

    def test_belief_is_bounded_and_dedup(self):
        r = RelationshipMemory()
        for i in range(10):
            r.observe_interaction("Cara", belief=f"belief {i}")
        beliefs = r.get("Cara")["beliefs"]
        self.assertLessEqual(len(beliefs), 6)
        # Most recent belief is first (move-to-front semantics).
        self.assertEqual(beliefs[0], "belief 9")
        # Re-adding an existing belief moves it to front without duplicating.
        r.add_belief("Cara", "belief 5")
        self.assertEqual(r.get("Cara")["beliefs"][0], "belief 5")
        self.assertEqual(r.get("Cara")["beliefs"].count("belief 5"), 1)


class NoteFromChatTests(unittest.TestCase):
    def test_note_from_chat_updates_familiarity_affinity_topics(self):
        r = RelationshipMemory()
        chat = [
            ["Tester", "Hey Alex, how is the chemistry exam prep going?"],
            ["Alex", "Stressful! Studying chemistry all week for the exam."],
        ]
        when = datetime.datetime(2026, 1, 1, 10, 0, 0)
        r.note_from_chat("Alex", chat, when=when)
        rec = r.get("Alex")
        self.assertEqual(rec["familiarity"], 1)
        self.assertEqual(rec["times_talked"], 1)
        self.assertGreater(rec["affinity"], 0.0)
        # Topic gist extracts content words (stopwords/short tokens dropped).
        self.assertIn("chemistry", rec["last_topics"])
        self.assertEqual(rec["last_interaction"], "2026-01-01 10:00:00")

    def test_repeated_chats_build_rapport(self):
        r = RelationshipMemory()
        chat = [["Tester", "Good to see you again friend."]]
        for _ in range(3):
            r.note_from_chat("Dana", chat)
        rec = r.get("Dana")
        self.assertEqual(rec["familiarity"], 3)
        self.assertEqual(rec["times_talked"], 3)
        self.assertGreater(rec["affinity"], 0.1)


class ToPromptBlockTests(unittest.TestCase):
    def test_renders_only_nearby_known_people(self):
        r = RelationshipMemory()
        r.observe_interaction("Alex", affinity_delta=0.4, topics=["coffee"])
        r.observe_interaction("Maria", affinity_delta=-0.4)
        # Only Alex is "nearby" -> Maria and an unknown stranger must not appear.
        block = r.to_prompt_block(["Alex", "Stranger"])
        self.assertIn("PEOPLE YOU KNOW (nearby)", block)
        self.assertIn("Alex", block)
        self.assertNotIn("Maria", block)
        self.assertNotIn("Stranger", block)

    def test_empty_when_no_known_nearby(self):
        r = RelationshipMemory()
        r.observe_interaction("Alex")
        self.assertEqual(r.to_prompt_block(["Bob", "Carol"]), "")
        self.assertEqual(r.to_prompt_block([]), "")


class SaveLoadRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = RelationshipMemory()
            when = datetime.datetime(2026, 1, 1, 12, 0, 0)
            r.observe_interaction(
                "Alex",
                affinity_delta=0.5,
                topics=["coffee", "exam"],
                belief="Alex is dependable.",
                when=when,
            )
            r.note_from_chat("Alex", [["Tester", "see you tomorrow"]], when=when)
            r.save(tmp)

            self.assertTrue(os.path.exists(os.path.join(tmp, "relationships.json")))

            r2 = RelationshipMemory(tmp)
            rec = r2.get("Alex")
            self.assertIsNotNone(rec)
            self.assertEqual(rec["familiarity"], 2)
            self.assertAlmostEqual(rec["affinity"], 0.55)
            self.assertIn("coffee", rec["last_topics"])
            self.assertIn("Alex is dependable.", rec["beliefs"])
            self.assertEqual(rec["times_talked"], 1)

    def test_missing_file_loads_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = RelationshipMemory(tmp)  # no relationships.json present
            self.assertEqual(r.relationships, {})
            self.assertIsNone(r.get("anyone"))

    def test_corrupt_file_tolerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "relationships.json"), "w") as f:
                f.write("{not valid json")
            r = RelationshipMemory(tmp)
            self.assertEqual(r.relationships, {})


class BuildStepPromptIntegrationTests(unittest.TestCase):
    """build_step_prompt injects PEOPLE YOU KNOW for a known nearby persona."""

    def _persona(self, tmp):
        scratch = _fresh_scratch(tmp, name="Tester")
        scratch.act_address = "the Ville:studio:main room:easel"
        scratch.act_description = "painting"
        r_mem = RelationshipMemory()
        return _StubPersona(scratch, r_mem)

    def test_people_you_know_section_present_for_known_nearby(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona(tmp)
            persona.r_mem.observe_interaction(
                "Alex", affinity_delta=0.4, topics=["coffee"]
            )
            # Nearby personas: (name, activity, distance) -> Alex within range.
            nearby = [("Alex", "reading a book", 2)]
            block = persona.r_mem.to_prompt_block(["Alex"])
            prompt = build_step_prompt(
                persona,
                perceptions=["You are in main room"],
                nearby_personas=nearby,
                accessible_locations={"studio": {"main room": ["easel"]}},
                relationship_block=block,
                recall_snippets=["Last talk with Alex (Jan 01 09:00): Alex: hi"],
            )
        self.assertIn("=== PEOPLE YOU KNOW (nearby) ===", prompt)
        self.assertIn("Alex", prompt)
        self.assertIn("RECALL (prior conversations)", prompt)
        # Phase 3c: social-readiness annotation reaches the NEARBY PEOPLE line.
        self.assertIn("familiarity 1", prompt)

    def test_no_people_you_know_section_for_strangers(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona(tmp)
            nearby = [("Bob", "idle", 2)]
            block = persona.r_mem.to_prompt_block(["Bob"])
            prompt = build_step_prompt(
                persona,
                perceptions=["You are in main room"],
                nearby_personas=nearby,
                accessible_locations={"studio": {"main room": ["easel"]}},
                relationship_block=block,
            )
        self.assertNotIn("=== PEOPLE YOU KNOW (nearby) ===", prompt)
        # Strangers are still flagged as such in the NEARBY PEOPLE annotation.
        self.assertIn("a stranger to you", prompt)

    def test_sleeping_person_flagged_dont_disturb(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona(tmp)
            nearby = [("Cleo", "sleeping in bed", 2)]
            prompt = build_step_prompt(
                persona,
                perceptions=[],
                nearby_personas=nearby,
                accessible_locations={"studio": {"main room": ["easel"]}},
            )
        self.assertIn("don't disturb", prompt)

    def test_tuple_activity_from_get_nearby_personas_does_not_crash(self):
        # Regression: _get_nearby_personas supplies activity as a
        # (predicate, object) tuple, not a string. The Phase-3 readiness logic
        # lowercases the activity, so the tuple must be normalized first.
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona(tmp)
            persona.r_mem.observe_interaction("Dana", affinity_delta=0.2)
            nearby = [("Dana", ("walking to", "the cafe"), 3)]
            block = persona.r_mem.to_prompt_block(["Dana"])
            prompt = build_step_prompt(
                persona,
                perceptions=[],
                nearby_personas=nearby,
                accessible_locations={"studio": {"main room": ["easel"]}},
                relationship_block=block,
            )
        # Activity tuple rendered readably (not as a Python tuple repr).
        self.assertIn("walking to the cafe", prompt)
        self.assertNotIn("('walking to'", prompt)


if __name__ == "__main__":
    unittest.main()
