import datetime
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.persona.prompt_template.claude_structure import (
    DEFAULT_CLAUDE_MODEL,
    build_day_planning_prompt,
    build_initial_prompt,
    build_step_prompt,
)


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


if __name__ == "__main__":
    unittest.main()
