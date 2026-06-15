import json
import tempfile
import unittest
from pathlib import Path

from reverie.backend_server.runtime_storage import RunStorage
from reverie.backend_server.scenario_config import load_scenario
from reverie.backend_server.scenario_runtime import (
    attach_scenario_to_personas,
    bind_scenario_to_run,
    build_scenario_brief,
)


class DummyPersona:
    def __init__(self, name):
        self.name = name


class ScenarioRuntimeTests(unittest.TestCase):
    def test_bind_scenario_to_run_writes_metadata_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = RunStorage(root)
            run_dir = storage.runs_dir / "run_one" / "reverie"
            run_dir.mkdir(parents=True)
            (run_dir / "meta.json").write_text(
                json.dumps({"step": 0, "persona_names": ["Nora Vale"]}),
                encoding="utf-8",
            )
            scenario = load_scenario("startup_team_v1")

            bind_scenario_to_run(storage, "run_one", scenario)

            meta = storage.read_run_meta("run_one")
            scenario_snapshot = json.loads(
                (run_dir / "scenario.json").read_text(encoding="utf-8")
            )
            self.assertEqual(meta["scenario_id"], "startup_team_v1")
            self.assertEqual(
                meta["scenario_objective"],
                "Generate real-world money through legal, human-approved business actions.",
            )
            self.assertEqual(scenario_snapshot["id"], "startup_team_v1")

    def test_build_scenario_brief_contains_objective_policy_and_team_roles(self):
        scenario = load_scenario("startup_team_v1")

        brief = build_scenario_brief(scenario)

        self.assertIn("Generate real-world money", brief)
        self.assertIn("human approval", brief)
        self.assertIn("send_email", brief)
        self.assertIn("Nora Vale: strategist", brief)
        self.assertIn("Visible movement routine", brief)
        self.assertIn("Hobbs Cafe", brief)

    def test_attach_scenario_to_personas_adds_persona_specific_brief(self):
        scenario = load_scenario("startup_team_v1")
        personas = {"Nora Vale": DummyPersona("Nora Vale")}

        attach_scenario_to_personas(personas, scenario)

        self.assertIn("Your startup role: strategist", personas["Nora Vale"].scenario_context)
        self.assertIn("Choose the most promising path", personas["Nora Vale"].scenario_context)


if __name__ == "__main__":
    unittest.main()
