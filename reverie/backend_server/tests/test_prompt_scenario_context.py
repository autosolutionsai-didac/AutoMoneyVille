import datetime
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.persona.prompt_template.claude_structure import (
    DEFAULT_CLAUDE_MODEL,
    MAIN_MODEL,
    StepResponse,
    _extract_json_object,
    build_day_planning_prompt,
    build_initial_prompt,
    build_step_prompt,
    get_model_for_tier,
    parse_step_response,
)
from reverie.backend_server.tool_executor import ToolResult


class PromptScenarioContextTests(unittest.TestCase):
    def _persona(self):
        scratch = SimpleNamespace(
            name="Nora Vale",
            age=32,
            innate="focused, cooperative",
            learned="startup strategist",
            lifestyle="works with the team",
            living_area="startup office",
            currently="building a revenue plan",
            daily_plan_req="Walk to Hobbs Cafe for the startup standup.",
            curr_time=datetime.datetime(2026, 6, 15, 9, 0),
            act_address="the Ville:startup office:town center:desk",
            act_description="reviewing opportunities",
            act_start_time=datetime.datetime(2026, 6, 15, 8, 45),
            act_duration=30,
            f_daily_schedule=[["review opportunities", 60]],
            f_daily_schedule_hourly_org=[["review opportunities", 60]],
        )
        return SimpleNamespace(
            name="Nora Vale",
            scratch=scratch,
            scenario_context=(
                "=== STARTUP SCENARIO ===\n"
                "Objective: Generate real-world money through legal, human-approved business actions.\n"
                "Your startup role: strategist.\n"
                "External actions require human approval."
            ),
            a_mem=None,
        )

    def test_initial_prompt_includes_startup_scenario_context(self):
        prompt = build_initial_prompt(self._persona(), compaction_summary="No memories yet.")

        self.assertIn("=== STARTUP SCENARIO ===", prompt)
        self.assertIn("Generate real-world money", prompt)
        self.assertIn("External actions require human approval", prompt)
        self.assertIn('"town_request"', prompt)

    def test_step_prompt_includes_startup_scenario_context(self):
        prompt = build_step_prompt(
            self._persona(),
            perceptions=["The team board has a new opportunity."],
            nearby_personas=[],
            accessible_locations={"startup office": {"town center": ["desk"]}},
        )

        self.assertIn("=== STARTUP SCENARIO ===", prompt)
        self.assertIn("Your startup role: strategist", prompt)
        self.assertIn("Town Center request", prompt)

    def test_persona_client_defaults_to_sonnet_46_model(self):
        self.assertEqual(DEFAULT_CLAUDE_MODEL, "claude-sonnet-4-6")

    def test_day_planning_prompt_includes_daily_plan_requirement(self):
        prompt = build_day_planning_prompt(self._persona(), "Monday, June 15, 2026")

        self.assertIn("Daily plan requirement", prompt)
        self.assertIn("Walk to Hobbs Cafe", prompt)
        self.assertIn("Honor any explicit daily plan requirement", prompt)

    def test_get_model_for_tier(self):
        # Defaults and fallbacks
        self.assertEqual(get_model_for_tier(None), MAIN_MODEL)
        self.assertEqual(get_model_for_tier("main"), MAIN_MODEL)
        self.assertEqual(get_model_for_tier("fast"), MAIN_MODEL)  # no FAST set, falls to MAIN
        self.assertEqual(get_model_for_tier("reflect"), MAIN_MODEL)

    def test_step_prompt_location_delta(self):
        persona = self._persona()
        prev = {"startup office": {"town center": ["desk", "chair"]}}
        curr = {"startup office": {"town center": ["desk"]}}  # removed chair

        prompt = build_step_prompt(
            persona,
            perceptions=[],
            nearby_personas=[],
            accessible_locations=curr,
            previous_locations=prev,
        )

        self.assertIn("LOCATION DELTA", prompt)
        self.assertIn("-chair", prompt)
        # The delta should be compact and not repeat the full old list unnecessarily
        self.assertNotIn("desk, chair", prompt)

    def test_step_prompt_location_unchanged(self):
        persona = self._persona()
        locs = {"startup office": {"town center": ["desk"]}}

        prompt = build_step_prompt(
            persona,
            perceptions=[],
            nearby_personas=[],
            accessible_locations=locs,
            previous_locations=locs,
        )

        self.assertIn("(locations unchanged since last step)", prompt)

    def test_a1_memory_line_unaffected(self):
        # Verify A1 behavior is intact: research includes detail excerpt, outbound does not bloat
        r_research = ToolResult(
            ok=True,
            tool="web_research",
            summary="web_research: 2 sources on 'x'",
            detail="Title A (u1): snippet. Title B (u2): more.",
        )
        self.assertIn("Title A", r_research.memory_line())
        self.assertIn("snippet", r_research.memory_line())

        r_outbound = ToolResult(
            ok=True,
            tool="send_email",
            summary="draft email to foo",
            detail="Full long draft body here that should not leak into memory",
        )
        self.assertEqual(r_outbound.memory_line(), "draft email to foo")
        self.assertNotIn("Full long draft", r_outbound.memory_line())

    def test_model_tier_fallbacks(self):
        # When no specific tier env, fast/reflect fall back to main
        self.assertEqual(get_model_for_tier("fast"), MAIN_MODEL)
        self.assertEqual(get_model_for_tier("reflect"), MAIN_MODEL)
        self.assertEqual(get_model_for_tier("unknown"), MAIN_MODEL)

    # --- A4 structured JSON robustness tests ---

    def test_a4_extract_json_object_clean_and_fallback(self):
        # Clean whole-object case (ideal structured output)
        self.assertEqual(
            _extract_json_object('  {"continuing": true}  '),
            '{"continuing": true}',
        )
        # Tolerates extra prose (old model behavior) via fallback
        messy = 'Here is my thought.\n{"action": {"description": "work"}, "continuing": false}'
        extracted = _extract_json_object(messy)
        self.assertTrue(extracted is not None and extracted.startswith("{"))
        self.assertIn("action", extracted)

    def test_a4_parse_step_happy_path_minimal(self):
        # Minimal valid step JSON (continuing) should parse with zero errors
        valid_sectors = ["the Ville"]
        valid_arenas = {"the Ville": ["startup office"]}
        valid_objects = {"the Ville": {"startup office": ["desk"]}}

        resp = parse_step_response(
            '{"continuing": true, "social": {"wants_to_talk": false}, "thoughts": []}',
            "Test Persona",
            valid_sectors,
            valid_arenas,
            valid_objects,
        )
        self.assertIsInstance(resp, StepResponse)
        self.assertEqual(resp.parse_errors, [])
        self.assertTrue(resp.continuing)
        self.assertIsNone(resp.action)

    def test_a4_parse_step_with_action_and_thought(self):
        valid_sectors = ["the Ville"]
        valid_arenas = {"the Ville": ["town center"]}
        valid_objects = {"the Ville": {"town center": ["cafe"]}}

        json_text = (
            '{"continuing": false, "social": {"wants_to_talk": false}, '
            '"thoughts": [{"content": "feeling focused", "importance": 4}], '
            '"action": {"description": "grab coffee", "duration_minutes": 10, '
            '"location": {"sector": "the Ville", "arena": "town center", "object": "cafe"}, '
            '"emoji": "☕", "event": ["Test", "grabs", "coffee"], "importance": 3}}'
        )
        resp = parse_step_response(
            json_text, "Test Persona", valid_sectors, valid_arenas, valid_objects
        )
        self.assertEqual(resp.parse_errors, [])
        self.assertFalse(resp.continuing)
        self.assertIsNotNone(resp.action)
        self.assertEqual(len(resp.thoughts), 1)
        self.assertIn("focused", resp.thoughts[0].content)

if __name__ == "__main__":
    unittest.main()
