"""Tests for the immutable replay inspector state contract."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.test import Client, RequestFactory, SimpleTestCase

from translator import views

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
INSPECTOR_SOURCE = FRONTEND_ROOT / "static_dirs" / "js" / "inspector_state.js"
INSPECTOR_TEMPLATE = FRONTEND_ROOT / "templates" / "home" / "inspector_script.html"
HOME_TEMPLATE = FRONTEND_ROOT / "templates" / "home" / "home.html"


class ReplayInspectorStateTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.frontend_root = Path(self.temp_dir.name)
        self.memory_root = (
            self.frontend_root
            / "storage"
            / "runs"
            / "run_one"
            / "personas"
            / "Nora Vale"
            / "bootstrap_memory"
        )
        (self.memory_root / "associative_memory").mkdir(parents=True)
        environment_root = (
            self.frontend_root / "storage" / "runs" / "run_one" / "environment"
        )
        environment_root.mkdir(parents=True)
        (environment_root / "0.json").write_text(
            json.dumps(
                {
                    "Nora Vale": {
                        "x": 7,
                        "y": 8,
                        "action": "Recorded step action",
                        "address": "Claudeville:Bank:counter",
                    }
                }
            ),
            encoding="utf-8",
        )
        (environment_root / "5.json").write_text(
            json.dumps({"Nora Vale": {"x": 50, "y": 51}}), encoding="utf-8"
        )
        self._write_fixture()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_json(self, relative_path, value):
        path = self.memory_root / relative_path
        path.write_text(json.dumps(value), encoding="utf-8")

    def _write_fixture(self):
        self._write_json(
            "scratch.json",
            {
                "name": "Nora Vale",
                "currently": "building a public launch plan",
                "act_description": "Review launch milestones",
                "act_address": "Claudeville:Oficina de Gobierno:main",
                "chatting_with": None,
                "curr_tile": [12, 34],
                "curr_time": "February 13, 2023, 09:45:00",
                "f_daily_schedule": [
                    ["sleeping", 420],
                    ["morning routine", 60],
                    ["draft launch plan", 120],
                ],
            },
        )
        self._write_json(
            "goals.json",
            {
                "goals": {
                    "g1": {"text": "Ship the launch", "status": "active"},
                    "g2": {"text": "Old task", "status": "completed"},
                }
            },
        )
        self._write_json(
            "relationships.json",
            {
                "milo chen": {
                    "name": "Milo Chen",
                    "familiarity": 4,
                    "affinity": 0.2,
                    "sentiment": "friendly",
                    "last_topics": ["launch", "market", "extra", "more", "ignored"],
                }
            },
        )
        nodes = {}
        for number in range(25):
            nodes[f"node_{number + 1}"] = {
                "type": "thought" if number % 2 else "event",
                "description": f"memory {number:02d}",
                "created": f"2023-02-13 09:{number:02d}:00",
                "poignancy": number,
            }
        self._write_json("associative_memory/nodes.json", nodes)

    @mock.patch("translator.views.requests.get")
    def test_replay_state_uses_disk_only_and_matches_inspector_schema(self, backend_get):
        with self.settings(BASE_DIR=str(self.frontend_root)):
            response = Client().get(
                "/api/replay/run_one/4/persona/Nora%20Vale/state/"
            )

        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertEqual(state["name"], "Nora Vale")
        self.assertEqual(state["currently"], "building a public launch plan")
        self.assertEqual(state["action"], "Recorded step action")
        self.assertEqual(state["address"], "Claudeville:Bank:counter")
        self.assertEqual(state["tile"], [7, 8])
        self.assertEqual(state["requested_step"], 4)
        self.assertEqual(state["effective_step"], 0)
        self.assertEqual(state["state_scope"], "final-recorded-memory")
        self.assertEqual(state["position_scope"], "environment-step")
        self.assertEqual(state["currently_scope"], "final-recorded-memory")
        self.assertEqual(state["action_scope"], "environment-step")
        self.assertEqual(state["address_scope"], "environment-step")
        self.assertEqual(state["schedule"][2]["task"], "draft launch plan")
        self.assertEqual(state["schedule_current_index"], 2)
        self.assertEqual(state["goals"], [{"title": "Ship the launch", "status": "active"}])
        self.assertEqual(state["relationships"][0]["name"], "Milo Chen")
        self.assertEqual(state["relationships"][0]["last_topics"], ["launch", "market", "extra", "more"])
        self.assertEqual(len(state["memories"]), 20)
        self.assertEqual(state["memories"][0]["description"], "memory 24")
        self.assertEqual(state["memories"][-1]["description"], "memory 05")
        backend_get.assert_not_called()

    def test_coordinate_only_step_labels_all_other_now_fields_as_final(self):
        with self.settings(BASE_DIR=str(self.frontend_root)):
            response = Client().get(
                "/api/replay/run_one/5/persona/Nora%20Vale/state/"
            )

        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertEqual(state["tile"], [50, 51])
        self.assertEqual(state["currently"], "building a public launch plan")
        self.assertEqual(state["action"], "Review launch milestones")
        self.assertEqual(state["address"], "Claudeville:Oficina de Gobierno:main")
        self.assertEqual(state["position_scope"], "environment-step")
        self.assertEqual(state["currently_scope"], "final-recorded-memory")
        self.assertEqual(state["action_scope"], "final-recorded-memory")
        self.assertEqual(state["address_scope"], "final-recorded-memory")

    def test_unknown_run_and_persona_return_generic_not_found(self):
        with self.settings(BASE_DIR=str(self.frontend_root)):
            missing_run = Client().get(
                "/api/replay/missing/4/persona/Nora%20Vale/state/"
            )
            missing_persona = Client().get(
                "/api/replay/run_one/4/persona/Nobody/state/"
            )

        for response in (missing_run, missing_persona):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json(), {"error": "Replay state not found"})

    def test_invalid_boundary_values_are_rejected(self):
        request = RequestFactory().get("/api/replay/state/")
        huge_step = "9" * 5000
        with self.settings(BASE_DIR=str(self.frontend_root)):
            bad_run = views.api_replay_persona_state(
                request, "../run_one", 4, "Nora Vale"
            )
            bad_persona = views.api_replay_persona_state(
                request, "run_one", 4, "..\\Nora Vale"
            )
            bad_float_step = views.api_replay_persona_state(
                request, "run_one", 1.5, "Nora Vale"
            )
            bad_padded_step = views.api_replay_persona_state(
                request, "run_one", " 4", "Nora Vale"
            )
            bad_negative_step = views.api_replay_persona_state(
                request, "run_one", "-1", "Nora Vale"
            )
            bad_leading_zero_step = views.api_replay_persona_state(
                request, "run_one", "04", "Nora Vale"
            )
            bad_huge_step = views.api_replay_persona_state(
                request, "run_one", huge_step, "Nora Vale"
            )
            bad_large_int_step = views.api_replay_persona_state(
                request, "run_one", 100_000_000, "Nora Vale"
            )

        self.assertEqual(bad_run.status_code, 400)
        self.assertEqual(bad_persona.status_code, 400)
        self.assertEqual(bad_float_step.status_code, 400)
        self.assertEqual(bad_padded_step.status_code, 400)
        self.assertEqual(bad_negative_step.status_code, 400)
        self.assertEqual(bad_leading_zero_step.status_code, 400)
        self.assertEqual(bad_huge_step.status_code, 400)
        self.assertEqual(bad_large_int_step.status_code, 400)
        self.assertEqual(json.loads(bad_run.content), {"error": "Invalid replay request"})
        self.assertEqual(
            json.loads(bad_persona.content), {"error": "Invalid replay request"}
        )

    def test_invalid_json_is_clean_and_does_not_leak_paths(self):
        (self.memory_root / "scratch.json").write_text("{broken", encoding="utf-8")
        with self.settings(BASE_DIR=str(self.frontend_root)):
            response = Client().get(
                "/api/replay/run_one/4/persona/Nora%20Vale/state/"
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"error": "Replay state unavailable"})
        self.assertNotIn(self.temp_dir.name, response.content.decode("utf-8"))

    def test_missing_required_json_is_clean(self):
        (self.memory_root / "relationships.json").unlink()
        with self.settings(BASE_DIR=str(self.frontend_root)):
            response = Client().get(
                "/api/replay/run_one/4/persona/Nora%20Vale/state/"
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"error": "Replay state unavailable"})


class ReplayInspectorFrontendTests(SimpleTestCase):
    def test_inspector_controller_rejects_stale_responses_and_canonicalizes_focus(self):
        controller = FRONTEND_ROOT / "static_dirs" / "js" / "inspector_controller.js"
        harness = Path(__file__).with_name("js_tests") / "inspector_controller_harness.js"
        result = subprocess.run(
            ["node", str(harness), str(controller)],
            cwd=FRONTEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_source_selects_replay_without_live_url_or_polling(self):
        source = r"""
const assert = require("assert");
const inspector = require(process.argv[1]);
const options = {
  liveUrlTemplate: "/api/persona/PERSONA_NAME/state/",
  replayUrlTemplate: "/api/replay/run_one/4/persona/PERSONA_NAME/state/",
};
const replay = inspector.create({...options, mode: "replay"});
assert.strictEqual(
  replay.url("Nora Vale"),
  "/api/replay/run_one/4/persona/Nora%20Vale/state/"
);
assert.strictEqual(replay.url("Nora Vale").includes("/api/persona/"), false);
assert.strictEqual(replay.shouldPoll, false);

const live = inspector.create({...options, mode: "simulate"});
assert.strictEqual(live.url("Nora Vale"), "/api/persona/Nora%20Vale/state/");
assert.strictEqual(live.shouldPoll, true);
const provenance = inspector.scopeSummary({
  requested_step: 5,
  effective_step: 5,
  position_scope: "environment-step",
  currently_scope: "final-recorded-memory",
  action_scope: "final-recorded-memory",
  address_scope: "final-recorded-memory",
  state_scope: "final-recorded-memory",
});
assert.strictEqual(
  provenance,
  "Replay step 5 (requested 5). Step-local: position. " +
  "Final recorded persona state: current status, action, address, schedule, " +
  "goals, relationships, and memories."
);
process.stdout.write(JSON.stringify({ok: true}));
"""
        result = subprocess.run(
            ["node", "-e", source, str(INSPECTOR_SOURCE)],
            cwd=FRONTEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_home_uses_source_adapter_and_only_polls_live_inspector(self):
        home = HOME_TEMPLATE.read_text(encoding="utf-8")
        inspector = INSPECTOR_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("js/inspector_state.js", home)
        self.assertIn("js/inspector_controller.js", home)
        self.assertIn("ClaudevilleInspectorSource.create", inspector)
        self.assertIn("ClaudevilleInspectorController.create", inspector)
        self.assertIn("controller.refresh", inspector)
        self.assertIn("if (stateSource.shouldPoll)", inspector)
        self.assertIn("ClaudevilleAddresses.displayAddress", inspector)
        self.assertIn("ClaudevilleInspectorSource.scopeSummary(state)", inspector)
