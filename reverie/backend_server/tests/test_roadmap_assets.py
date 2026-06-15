import json
import unittest
from datetime import datetime
from pathlib import Path


class RoadmapAssetTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[3]

    def test_windows_launcher_exposes_start_stop_restart_status(self):
        launcher = self.root / "tools" / "claudeville.ps1"
        source = launcher.read_text(encoding="utf-8")

        self.assertIn("ValidateSet('start', 'stop', 'restart', 'status')", source)
        self.assertIn("runtime_pids.json", source)
        self.assertIn("PYTHONUTF8", source)
        self.assertIn("--noreload", source)
        self.assertIn("/health", source)

    def test_startup_team_scenario_declares_10_safe_agents(self):
        scenario_path = (
            self.root
            / "reverie"
            / "backend_server"
            / "scenarios"
            / "startup_team_v1.json"
        )
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))

        self.assertEqual(scenario["id"], "startup_team_v1")
        self.assertEqual(len(scenario["agents"]), 10)
        self.assertEqual(
            scenario["real_world_policy"]["default_external_action"], "human_approval"
        )
        self.assertIn("digital_services", scenario["opportunity_paths"])
        self.assertIn("actual_revenue", scenario["reward_model"]["late_weights"])
        self.assertIn("Hobbs Cafe", " ".join(scenario["visible_morning_routine"]))

    def test_startup_team_base_matches_scenario_roster(self):
        scenario_path = (
            self.root
            / "reverie"
            / "backend_server"
            / "scenarios"
            / "startup_team_v1.json"
        )
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        expected_names = [agent["name"] for agent in scenario["agents"]]
        base_dir = (
            self.root
            / "environment"
            / "frontend_server"
            / "storage"
            / "base"
            / "startup_team_v1"
        )

        self.assertTrue(base_dir.exists(), "startup_team_v1 base is missing")
        meta = json.loads((base_dir / "reverie" / "meta.json").read_text())
        environment = json.loads((base_dir / "environment" / "0.json").read_text())

        self.assertEqual(meta["persona_names"], expected_names)
        self.assertEqual(list(environment.keys()), expected_names)
        for name in expected_names:
            scratch_path = (
                base_dir
                / "personas"
                / name
                / "bootstrap_memory"
                / "scratch.json"
            )
            scratch = json.loads(scratch_path.read_text(encoding="utf-8"))
            self.assertEqual(scratch["name"], name)
            self.assertIn("startup", scratch["currently"].lower())
            self.assertIn("Hobbs Cafe", scratch["daily_plan_req"])
            self.assertIn("startup standup", scratch["daily_plan_req"])
            sprite_path = (
                self.root
                / "environment"
                / "frontend_server"
                / "static_dirs"
                / "assets"
                / "characters"
                / f"{name.replace(' ', '_')}.png"
            )
            self.assertTrue(sprite_path.exists(), f"Missing sprite for {name}")

    def test_startup_team_base_starts_during_workday(self):
        base_dir = (
            self.root
            / "environment"
            / "frontend_server"
            / "storage"
            / "base"
            / "startup_team_v1"
        )
        meta = json.loads((base_dir / "reverie" / "meta.json").read_text())
        curr_time = datetime.strptime(meta["curr_time"], "%B %d, %Y, %H:%M:%S")

        self.assertGreaterEqual(curr_time.hour, 8)
        self.assertLess(curr_time.hour, 18)


if __name__ == "__main__":
    unittest.main()
