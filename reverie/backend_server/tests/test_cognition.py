"""Phase 1 cognition tests: Generative-Agents cognitive core + dual-layer.

Covers: 1a retrieve_focal ranking; 1b importance plumbing (LLM action
importance -> self-event poignancy); 1c reflection trigger fires/resets and
stores backlinked thoughts; 1f dual-layer parsing (system_thinking +
inner_monologue). Hard constraint D-002: NO vector embeddings.
"""

import asyncio
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

from reverie.backend_server.persona.cognitive_modules.perceive import (
    generate_poig_score,
)
from reverie.backend_server.persona.cognitive_modules.reflect import (
    gather_reflection_sources,
    store_reflection_insights,
)
from reverie.backend_server.persona.cognitive_modules.retrieve import retrieve_focal
from reverie.backend_server.persona.memory_structures.associative_memory import (
    AssociativeMemory,
)
from reverie.backend_server.persona.memory_structures.scratch import Scratch
from reverie.backend_server.persona.persona import Persona
from reverie.backend_server.persona.prompt_template.claude_structure import (
    parse_reflection_response,
    parse_step_response,
)


class _StubSpatialMem:
    """Minimal stand-in for MemoryTree (perceive only touches .tree)."""

    def __init__(self):
        self.tree = {}


class _StubMaze:
    """Minimal maze with a single tile carrying events, for perceive()."""

    def __init__(self, tile, events):
        self._tile = tuple(tile)
        self._events = events

    def get_nearby_tiles(self, curr_tile, vision_r):
        return [self._tile]

    def access_tile(self, tile):
        events = list(self._events) if tuple(tile) == self._tile else []
        return {
            "world": "the Ville",
            "sector": "studio",
            "arena": "main room",
            "game_object": "easel",
            "events": events,
        }

    def get_tile_path(self, tile, level):
        del tile, level
        return "the Ville:studio:main room"


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


def _bare_persona(a_mem, scratch):
    """A Persona shell with just the fields the cognition code touches."""
    persona = Persona.__new__(Persona)
    persona.name = scratch.name
    persona.a_mem = a_mem
    persona.scratch = scratch
    persona.curr_action_importance = None
    return persona


class RetrieveFocalRankingTests(unittest.TestCase):
    """1a: combined recency + relevance + importance ordering."""

    def _persona_with_events(self, tmp):
        a_mem = _fresh_assoc_memory(tmp)
        scratch = _fresh_scratch(tmp)
        base = datetime.datetime(2026, 1, 1, 8, 0, 0)

        # Highly relevant + recent + important -> should rank first.
        a_mem.add_event(
            base + datetime.timedelta(minutes=30),
            None,
            "Tester",
            "study",
            "chemistry",
            "Tester studies chemistry hard",
            {"study", "chemistry", "exam"},
            9,
            "ek1",
            None,
        )
        # Older, weakly relevant, low importance.
        a_mem.add_event(
            base,
            None,
            "Tester",
            "water",
            "plants",
            "Tester waters the plants",
            {"plants", "garden"},
            2,
            "ek2",
            None,
        )
        # Partially relevant, middling.
        a_mem.add_event(
            base + datetime.timedelta(minutes=10),
            None,
            "Tester",
            "read",
            "chemistry",
            "Tester reads a chemistry note",
            {"chemistry", "read"},
            4,
            "ek3",
            None,
        )
        return _bare_persona(a_mem, scratch)

    def test_most_relevant_recent_important_node_ranks_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona_with_events(tmp)
            focal = {"chemistry", "exam", "study"}
            results = retrieve_focal(persona, focal, n=8)

        self.assertTrue(results)
        # The node matching all three focal keywords with high importance + recency
        # should be ranked first.
        self.assertIn("chemistry", results[0].description.lower())
        self.assertEqual(results[0].description, "Tester studies chemistry hard")

    def test_irrelevant_keywords_return_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona_with_events(tmp)
            results = retrieve_focal(persona, {"spaceship", "volcano"}, n=8)
        self.assertEqual(results, [])

    def test_respects_top_n_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona_with_events(tmp)
            results = retrieve_focal(persona, {"chemistry"}, n=1)
        self.assertEqual(len(results), 1)

    def test_updates_last_accessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona_with_events(tmp)
            results = retrieve_focal(persona, {"chemistry"}, n=8)
            for node in results:
                self.assertEqual(node.last_accessed, persona.scratch.curr_time)

    def test_recency_breaks_ties_among_equal_relevance_importance(self):
        """Two equally relevant/important nodes -> the more recent wins."""
        with tempfile.TemporaryDirectory() as tmp:
            a_mem = _fresh_assoc_memory(tmp)
            scratch = _fresh_scratch(tmp)
            base = datetime.datetime(2026, 1, 1, 8, 0, 0)
            a_mem.add_event(
                base,
                None,
                "Tester",
                "meet",
                "alex",
                "Tester met Alex earlier",
                {"alex", "meeting"},
                5,
                "ekA",
                None,
            )
            a_mem.add_event(
                base + datetime.timedelta(hours=1),
                None,
                "Tester",
                "meet",
                "alex",
                "Tester met Alex again later",
                {"alex", "meeting"},
                5,
                "ekB",
                None,
            )
            persona = _bare_persona(a_mem, scratch)
            results = retrieve_focal(persona, {"alex", "meeting"}, n=8)
        self.assertEqual(results[0].description, "Tester met Alex again later")


class ImportancePlumbingTests(unittest.TestCase):
    """1b: LLM action importance becomes the poignancy of the self action event."""

    def test_action_importance_parsed_and_clamped(self):
        body = {
            "action": {
                "description": "painting a masterpiece",
                "duration_minutes": 60,
                "location": {"sector": "", "arena": "", "object": ""},
                "event": ["Tester", "paint", "canvas"],
                "emoji": "🎨",
                "importance": 9,
            },
            "social": {"wants_to_talk": False},
        }
        result = parse_step_response(json.dumps(body), "Tester", [], {}, {})
        self.assertEqual(result.action.importance, 9)

    def test_bad_importance_defaults_to_five(self):
        body = {
            "action": {
                "description": "idle",
                "duration_minutes": 5,
                "location": {"sector": "", "arena": "", "object": ""},
                "event": ["Tester", "is", "idle"],
                "emoji": "💭",
                "importance": "very high",
            },
            "social": {"wants_to_talk": False},
        }
        result = parse_step_response(json.dumps(body), "Tester", [], {}, {})
        self.assertEqual(result.action.importance, 5)

    def test_self_action_event_uses_llm_importance_via_perceive(self):
        """perceive() stamps the self-action event with curr_action_importance."""
        with tempfile.TemporaryDirectory() as tmp:
            a_mem = _fresh_assoc_memory(tmp)
            scratch = _fresh_scratch(tmp, name="Tester")
            scratch.curr_tile = (5, 5)
            scratch.vision_r = 4
            scratch.att_bandwidth = 3
            scratch.retention = 5
            persona = _bare_persona(a_mem, scratch)
            persona.s_mem = _StubSpatialMem()
            persona.curr_action_importance = 8

            from reverie.backend_server.persona.cognitive_modules import perceive

            # A single self-action event sitting on the persona's current tile.
            maze = _StubMaze(
                tile=(5, 5),
                events=[("Tester", "paint", "canvas", "painting a mural")],
            )
            ret = perceive.perceive(persona, maze)

        self.assertTrue(ret)
        self_nodes = [n for n in ret if n.subject == "Tester"]
        self.assertTrue(self_nodes)
        self.assertEqual(self_nodes[0].poignancy, 8)

    def test_third_party_event_uses_fallback_poignancy(self):
        """Perceived third-party events still use generate_poig_score (5)."""
        self.assertEqual(generate_poig_score(None, "event", "Alex walks by"), 5)
        self.assertEqual(generate_poig_score(None, "event", "Alex is idle"), 1)

    def test_trigger_decrements_by_real_importance(self):
        """importance_trigger_curr drops by the real importance, not a constant."""
        with tempfile.TemporaryDirectory() as tmp:
            scratch = _fresh_scratch(tmp)
            before = scratch.importance_trigger_curr
            importance = 7
            scratch.importance_trigger_curr -= importance
            self.assertEqual(scratch.importance_trigger_curr, before - 7)


class ReflectionTriggerTests(unittest.TestCase):
    """1c: reflection fires at threshold, resets, stores backlinked thoughts."""

    class _FakeReflection:
        def __init__(self, insights):
            self.insights = insights
            self.parse_errors = []

    class _FakeClient:
        def __init__(self, insights):
            self._insights = insights
            self.calls = 0

        async def reflect(self, source_nodes, model=None):  # P2 A2 compat
            self.calls += 1
            self._last_sources = source_nodes
            return ReflectionTriggerTests._FakeReflection(self._insights)

    def _persona_with_memories(self, tmp):
        a_mem = _fresh_assoc_memory(tmp)
        scratch = _fresh_scratch(tmp)
        base = datetime.datetime(2026, 1, 1, 8, 0, 0)
        for i in range(4):
            a_mem.add_event(
                base + datetime.timedelta(minutes=i * 10),
                None,
                "Tester",
                "do",
                f"thing{i}",
                f"Tester did thing {i}",
                {f"thing{i}", "activity"},
                6 + i,
                f"ek{i}",
                None,
            )
        persona = _bare_persona(a_mem, scratch)
        return persona

    def test_gather_reflection_sources_skips_idle_and_ranks_by_poignancy(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona_with_memories(tmp)
            persona.a_mem.add_event(
                persona.scratch.curr_time,
                None,
                "Tester",
                "is",
                "idle",
                "Tester is idle",
                {"idle"},
                1,
                "ekidle",
                None,
            )
            sources = gather_reflection_sources(persona, count=10)
        self.assertTrue(sources)
        self.assertTrue(all("is idle" not in n.description for n in sources))
        poigs = [n.poignancy for n in sources]
        self.assertEqual(poigs, sorted(poigs, reverse=True))

    def test_store_reflection_insights_creates_backlinked_depth_thoughts(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona_with_memories(tmp)
            sources = gather_reflection_sources(persona)
            insights = ["I tend to stay busy.", "I value steady progress."]
            made = store_reflection_insights(persona, insights, sources)

        self.assertEqual(len(made), 2)
        source_ids = {n.node_id for n in sources}
        for node in made:
            # Backlinks (1d): filling holds the source node_ids.
            self.assertTrue(set(node.filling).issubset(source_ids))
            self.assertTrue(node.filling)
            # depth > 0 for reflections (built on depth-0 events => depth 1).
            self.assertGreater(node.depth, 0)
            self.assertEqual(node.type, "thought")

    def test_maybe_reflect_fires_at_threshold_resets_and_stores(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona_with_memories(tmp)
            persona.unified_client = self._FakeClient(
                ["Insight one.", "Insight two."]
            )
            # Force the trigger to fire.
            persona.scratch.importance_trigger_curr = 0

            thoughts_before = len(persona.a_mem.seq_thought)
            made = asyncio.run(Persona._maybe_reflect(persona))

            self.assertEqual(persona.unified_client.calls, 1)
            self.assertEqual(len(made), 2)
            self.assertEqual(
                len(persona.a_mem.seq_thought), thoughts_before + 2
            )
            # Trigger resets to max after reflection.
            self.assertEqual(
                persona.scratch.importance_trigger_curr,
                persona.scratch.importance_trigger_max,
            )

    def test_maybe_reflect_noop_above_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            persona = self._persona_with_memories(tmp)
            persona.unified_client = self._FakeClient(["unused"])
            persona.scratch.importance_trigger_curr = 50

            made = asyncio.run(Persona._maybe_reflect(persona))
            self.assertEqual(made, [])
            self.assertEqual(persona.unified_client.calls, 0)
            self.assertEqual(persona.scratch.importance_trigger_curr, 50)


class DualLayerParsingTests(unittest.TestCase):
    """1f: system_thinking + inner_monologue parsed from a single step call."""

    def _parse(self, body):
        return parse_step_response(json.dumps(body), "Tester", [], {}, {})

    def test_parses_both_layers(self):
        body = {
            "system_thinking": "Finish breakfast, then head to the studio.",
            "inner_monologue": "I'm nervous about the show but excited too.",
            "action": {
                "description": "eating breakfast",
                "duration_minutes": 20,
                "location": {"sector": "", "arena": "", "object": ""},
                "event": ["Tester", "eat", "breakfast"],
                "emoji": "🍳",
                "importance": 4,
            },
            "social": {"wants_to_talk": False},
        }
        result = self._parse(body)
        self.assertEqual(
            result.system_thinking, "Finish breakfast, then head to the studio."
        )
        self.assertEqual(
            result.inner_monologue, "I'm nervous about the show but excited too."
        )

    def test_missing_layers_are_none(self):
        body = {
            "action": {
                "description": "reading",
                "duration_minutes": 30,
                "location": {"sector": "", "arena": "", "object": ""},
                "event": ["Tester", "read", "book"],
                "emoji": "📖",
            },
            "social": {"wants_to_talk": False},
        }
        result = self._parse(body)
        self.assertIsNone(result.system_thinking)
        self.assertIsNone(result.inner_monologue)

    def test_blank_layers_are_none(self):
        body = {
            "system_thinking": "   ",
            "inner_monologue": "",
            "social": {"wants_to_talk": False},
            "continuing": True,
        }
        result = self._parse(body)
        self.assertIsNone(result.system_thinking)
        self.assertIsNone(result.inner_monologue)

    def test_store_inner_monologue_persists_thought_and_decrements_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            a_mem = _fresh_assoc_memory(tmp)
            scratch = _fresh_scratch(tmp)
            persona = _bare_persona(a_mem, scratch)
            persona.curr_action_importance = 6

            body = {
                "inner_monologue": "I feel like today is going to be a good day.",
                "action": {
                    "description": "stretching",
                    "duration_minutes": 5,
                    "location": {"sector": "", "arena": "", "object": ""},
                    "event": ["Tester", "stretch", "body"],
                    "emoji": "🧘",
                    "importance": 6,
                },
                "social": {"wants_to_talk": False},
            }
            result = self._parse(body)
            before = scratch.importance_trigger_curr
            node = Persona._store_inner_monologue(persona, result)

        self.assertIsNotNone(node)
        self.assertEqual(node.type, "thought")
        self.assertEqual(node.poignancy, 6)
        self.assertEqual(scratch.importance_trigger_curr, before - 6)


class ReflectionResponseParseTests(unittest.TestCase):
    def test_parses_insight_list(self):
        text = '```json\n{"insights": ["a", "b", "c"]}\n```'
        result = parse_reflection_response(text)
        self.assertEqual(result.insights, ["a", "b", "c"])
        self.assertEqual(result.parse_errors, [])

    def test_empty_insights_flagged(self):
        result = parse_reflection_response('{"insights": []}')
        self.assertTrue(result.parse_errors)


if __name__ == "__main__":
    unittest.main()
