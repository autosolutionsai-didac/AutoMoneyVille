"""Security regressions for frozen replay and demo data boundaries."""

import io
import json
import re
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from django.template.loader import render_to_string
from django.test import Client, RequestFactory, SimpleTestCase

from translator import views

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
GUARD_SOURCE = FRONTEND_ROOT / "static_dirs" / "js" / "replay_mode_guard.js"
GUARD_HARNESS = Path(__file__).with_name("js_tests") / "replay_mode_guard_harness.js"
HOME_TEMPLATE = FRONTEND_ROOT / "templates" / "home" / "home.html"
MAIN_TEMPLATE = FRONTEND_ROOT / "templates" / "home" / "main_script.html"


class FrozenReplayBoundaryTests(SimpleTestCase):
    def test_play_space_and_skip_are_blocked_in_replay_but_work_live(self):
        result = subprocess.run(
            ["node", str(GUARD_HARNESS), str(GUARD_SOURCE)],
            cwd=FRONTEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_home_wires_all_live_boundaries_through_the_replay_guard(self):
        home = HOME_TEMPLATE.read_text(encoding="utf-8")
        main = MAIN_TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("js/replay_mode_guard.js", home)
        self.assertIn("ClaudevilleReplayGuard.create(SIM_MODE)", main)
        for function_name in (
            "requestSimulation",
            "kickPlaybackPipeline",
            "pollMovements",
            "startSkipMode",
            "saveGame",
        ):
            self.assertRegex(
                main,
                rf"(?:async )?function {function_name}\([^)]*\) \{{\s*"
                r"if \(!MODE_GUARD\.canMutate\(\)\)",
            )


class ReplayStepSelectionTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.frontend_root = Path(self.temp_dir.name)
        self.run_root = self.frontend_root / "storage" / "runs" / "run_one"
        (self.run_root / "reverie").mkdir(parents=True)
        (self.run_root / "personas" / "Nora Vale").mkdir(parents=True)
        (self.run_root / "reverie" / "meta.json").write_text(
            json.dumps({"maze_name": "claudeville"}), encoding="utf-8"
        )
        environment = self.run_root / "environment"
        environment.mkdir()
        (environment / "0.json").write_text(
            json.dumps({"Nora Vale": {"x": 1, "y": 2}}), encoding="utf-8"
        )
        (environment / "5.json").write_text(
            json.dumps({"Nora Vale": {"x": 9, "y": 10}}), encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_replay_uses_exact_or_nearest_prior_environment_step(self):
        with self.settings(BASE_DIR=str(self.frontend_root)):
            prior = Client().get("/replay/run_one/4/")
            exact = Client().get("/replay/run_one/5/")
            later = Client().get("/replay/run_one/99/")

        self.assertEqual(prior.status_code, 200)
        self.assertEqual(prior.context["requested_step"], 4)
        self.assertEqual(prior.context["effective_step"], 0)
        self.assertContains(prior, "Nora Vale,1,2")
        self.assertEqual(exact.context["effective_step"], 5)
        self.assertContains(exact, "Nora Vale,9,10")
        self.assertEqual(later.context["effective_step"], 5)

    def test_invalid_negative_and_too_low_steps_fail_cleanly(self):
        huge_step = "9" * 5000
        with self.settings(BASE_DIR=str(self.frontend_root)):
            unknown = Client().get("/replay/run_one/not-a-step/")
            negative = Client().get("/replay/run_one/-1/")
            leading_zero = Client().get("/replay/run_one/04/")
            signed_page = Client().get("/replay/run_one/+1/")
            signed_api = Client().get(
                "/api/replay/run_one/+1/persona/Nora%20Vale/state/"
            )
            slash_boundary = Client().get("/replay/run_one/+1/extra/")
            overlong = views.replay(
                RequestFactory().get("/replay/run_one/overlong/"),
                "run_one",
                huge_step,
            )
            (self.run_root / "environment" / "0.json").unlink()
            too_low = Client().get("/replay/run_one/4/")
            missing = Client().get("/replay/missing/4/")

        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(negative.status_code, 400)
        self.assertEqual(leading_zero.status_code, 400)
        self.assertEqual(signed_page.status_code, 400)
        self.assertEqual(signed_api.status_code, 400)
        self.assertEqual(slash_boundary.status_code, 404)
        self.assertEqual(overlong.status_code, 400)
        self.assertEqual(too_low.status_code, 404)
        self.assertEqual(missing.status_code, 404)
        for response in (
            unknown,
            negative,
            leading_zero,
            signed_page,
            signed_api,
            slash_boundary,
            overlong,
            too_low,
            missing,
        ):
            self.assertNotIn(self.temp_dir.name, response.content.decode("utf-8"))


class DemoJsonBoundaryTests(SimpleTestCase):
    def test_demo_context_keeps_recorded_data_as_python_objects(self):
        hostile_name = 'Nora </script><script id="owned">attack()</script>'
        movement = {
            "0": {
                hostile_name: {
                    "movement": [1, 2],
                    "pronunciatio": "</script><img onerror=attack()>",
                    "description": "line\u2028separator",
                    "chat": [[hostile_name, "hello"]],
                }
            }
        }
        meta = {
            "sec_per_step": 10,
            "start_date": "February 13, 2023",
            "maze_name": "claudeville",
        }

        def fake_open(path, *args, **kwargs):
            value = meta if str(path).endswith("meta.json") else movement
            return io.StringIO(json.dumps(value))

        with (
            mock.patch("translator.views.open", side_effect=fake_open),
            mock.patch("translator.views.render") as render,
        ):
            views.demo(RequestFactory().get("/demo/run/0/2/"), "run", 0, "2")

        context = render.call_args.args[2]
        self.assertIsInstance(context["persona_init_pos"], dict)
        self.assertIsInstance(context["all_movement"], dict)
        self.assertIn(hostile_name.replace(" ", "_"), context["persona_init_pos"])

    def test_hostile_demo_payload_is_non_executable_json_script_data(self):
        hostile = '</script><script id="owned">attack()</script><img onerror=attack()>\u2028'
        context = {
            "sim_code": "run_one",
            "step": 0,
            "persona_names": [
                {"original": hostile, "underscore": "Nora_Vale", "initial": "NV"}
            ],
            "persona_init_pos": {hostile: [1, 2]},
            "all_movement": {
                0: {
                    hostile: {
                        "movement": [1, 2],
                        "pronunciatio": hostile,
                        "description": hostile,
                        "chat": [[hostile, hostile]],
                    }
                }
            },
            "start_datetime": "2023-02-13T00:00:00",
            "sec_per_step": 10,
            "play_speed": 2,
            "mode": "demo",
            "world_manifest_path": "assets/claudeville/world.json",
        }

        rendered = render_to_string("demo/demo.html", context)

        self.assertNotIn('<script id="owned">', rendered)
        self.assertNotIn("<img onerror=attack()>", rendered)
        for element_id, expected in (
            ("demo-persona-init", context["persona_init_pos"]),
            ("demo-all-movement", {"0": context["all_movement"][0]}),
        ):
            match = re.search(
                rf'<script id="{element_id}" type="application/json">(.*?)</script>',
                rendered,
                re.DOTALL,
            )
            self.assertIsNotNone(match, element_id)
            self.assertEqual(json.loads(match.group(1)), expected)
            self.assertIn(r"\u003C/script\u003E", match.group(1))

        main = (FRONTEND_ROOT / "templates" / "demo" / "main_script.html").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("|safe", main)
        self.assertIn(
            'JSON.parse(document.getElementById("demo-persona-init").textContent)',
            main,
        )
        self.assertIn(
            'JSON.parse(document.getElementById("demo-all-movement").textContent)',
            main,
        )
