import json
from pathlib import Path
from unittest import mock

from django.test import Client, RequestFactory, SimpleTestCase

from translator import views


class HealthProxyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch("translator.views.requests.get")
    def test_api_health_reports_django_and_backend_status(self, mock_get):
        backend_response = mock.Mock()
        backend_response.json.return_value = {
            "ok": True,
            "sim_code": "run_one",
            "step": 3,
            "backend_busy": True,
            "backend_busy_reason": "simulate 1 step(s)",
            "backend_busy_seconds": 1.2,
        }
        backend_response.raise_for_status.return_value = None
        mock_get.return_value = backend_response

        response = views.api_health(self.factory.get("/api/health/"))
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["django"]["ok"])
        self.assertTrue(data["backend"]["ok"])
        self.assertEqual(data["backend"]["sim_code"], "run_one")
        self.assertEqual(data["backend"]["backend_busy_reason"], "simulate 1 step(s)")

    @mock.patch("translator.views.requests.get")
    def test_api_health_keeps_page_consumable_when_backend_is_down(self, mock_get):
        mock_get.side_effect = views.requests.ConnectionError("backend offline")

        response = views.api_health(self.factory.get("/api/health/"))
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["django"]["ok"])
        self.assertFalse(data["backend"]["ok"])
        self.assertIn("backend offline", data["backend"]["error"])


class MovementProxyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch("translator.views.requests.get")
    def test_api_movements_forwards_after_step_cursor(self, mock_get):
        backend_response = mock.Mock()
        backend_response.json.return_value = {"empty": True, "step": 4}
        backend_response.raise_for_status.return_value = None
        mock_get.return_value = backend_response

        response = views.api_movements(
            self.factory.get(
                "/api/movements/",
                {"after_step": "3"},
                HTTP_X_CLAUDEVILLE_CLIENT=views.CLIENT_VERSION,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_args.kwargs["params"], {"after_step": "3"})

    @mock.patch("translator.views.requests.get")
    def test_api_movements_blocks_stale_uncursored_clients(self, mock_get):
        response = views.api_movements(self.factory.get("/api/movements/"))
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(data["status"], "stale_client")
        mock_get.assert_not_called()


class HomeViewLiveBackendTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch("translator.views.requests.get")
    @mock.patch("translator.views.open", new_callable=mock.mock_open)
    @mock.patch("translator.views.os.listdir")
    @mock.patch("translator.views.os.path.exists")
    def test_home_uses_live_backend_positions_when_available(
        self, mock_exists, mock_listdir, mock_open_file, mock_get
    ):
        mock_exists.return_value = True
        mock_listdir.return_value = ["Nora Vale", "Milo Chen"]
        mock_open_file.return_value.read.side_effect = [
            json.dumps({"sim_code": "run_one"}),
            json.dumps({"step": 1}),
        ]
        backend_response = mock.Mock()
        backend_response.json.return_value = {
            "ok": True,
            "sim_code": "run_one",
            "step": 7,
            "curr_time": "February 13, 2023, 09:01:10",
            "personas": [
                {"name": "Nora Vale", "tile": [24, 25]},
                {"name": "Milo Chen", "tile": [25, 18]},
            ],
        }
        backend_response.raise_for_status.return_value = None
        mock_get.return_value = backend_response

        with mock.patch("translator.views.render") as mock_render:
            views.home(self.factory.get("/simulator_home"))

        context = mock_render.call_args.args[2]
        self.assertEqual(context["step"], 7)
        self.assertEqual(context["initial_curr_time"], "February 13, 2023, 09:01:10")
        self.assertIn(["Nora Vale", 24, 25], context["persona_init_pos"])

    @mock.patch("translator.views.requests.get")
    @mock.patch("translator.views.open")
    @mock.patch("translator.views.os.listdir")
    @mock.patch("translator.views.os.path.exists")
    def test_home_does_not_read_step_file_when_backend_health_is_current(
        self, mock_exists, mock_listdir, mock_open_file, mock_get
    ):
        mock_exists.return_value = True
        mock_listdir.return_value = ["Nora Vale"]
        mock_open_file.side_effect = json.JSONDecodeError("empty", "", 0)
        backend_response = mock.Mock()
        backend_response.json.return_value = {
            "ok": True,
            "sim_code": "run_one",
            "step": 12,
            "curr_time": "February 13, 2023, 09:02:00",
            "personas": [{"name": "Nora Vale", "tile": [24, 25]}],
        }
        backend_response.raise_for_status.return_value = None
        mock_get.return_value = backend_response

        with mock.patch("translator.views.render") as mock_render:
            views.home(self.factory.get("/simulator_home"))

        context = mock_render.call_args.args[2]
        self.assertEqual(context["step"], 12)
        self.assertEqual(context["initial_curr_time"], "February 13, 2023, 09:02:00")
        mock_open_file.assert_not_called()


class TownCenterProxyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch("translator.views.requests.get")
    def test_api_town_center_proxies_backend_snapshot(self, mock_get):
        backend_response = mock.Mock()
        backend_response.json.return_value = {
            "scenario": {"id": "startup_team_v1"},
            "requests": [],
            "team_score": {"points": 0, "revenue_cents": 0},
        }
        backend_response.raise_for_status.return_value = None
        mock_get.return_value = backend_response

        response = views.api_town_center(self.factory.get("/api/town-center/"))
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["scenario"]["id"], "startup_team_v1")

    @mock.patch("translator.views.requests.post")
    def test_api_town_center_request_forwards_json_body(self, mock_post):
        backend_response = mock.Mock()
        backend_response.json.return_value = {
            "id": "req_1",
            "state": "proposed",
            "title": "Need research",
        }
        backend_response.raise_for_status.return_value = None
        mock_post.return_value = backend_response

        response = views.api_town_center_request(
            self.factory.post(
                "/api/town-center/requests/",
                data=json.dumps({"title": "Need research"}),
                content_type="application/json",
            )
        )
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["id"], "req_1")
        mock_post.assert_called_once()

    @mock.patch("translator.views.requests.post")
    def test_api_town_center_transition_forwards_state(self, mock_post):
        backend_response = mock.Mock()
        backend_response.json.return_value = {
            "id": "req_1",
            "state": "approved",
            "reviewer": "human",
        }
        backend_response.raise_for_status.return_value = None
        mock_post.return_value = backend_response

        response = views.api_town_center_request_transition(
            self.factory.post(
                "/api/town-center/requests/req_1/transition/",
                data=json.dumps({"state": "approved"}),
                content_type="application/json",
            ),
            "req_1",
        )
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["state"], "approved")
        mock_post.assert_called_once()

    @mock.patch("translator.views.requests.post")
    def test_api_town_center_reward_forwards_reward_event(self, mock_post):
        backend_response = mock.Mock()
        backend_response.json.return_value = {
            "id": "rew_1",
            "actor": "Milo Chen",
            "points": 3,
        }
        backend_response.raise_for_status.return_value = None
        mock_post.return_value = backend_response

        response = views.api_town_center_reward(
            self.factory.post(
                "/api/town-center/rewards/",
                data=json.dumps({"actor": "Milo Chen", "points": 3}),
                content_type="application/json",
            )
        )
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["id"], "rew_1")
        mock_post.assert_called_once()


class SimulationProxyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @mock.patch("translator.views.requests.post")
    def test_api_simulate_uses_long_timeout_for_llm_steps(self, mock_post):
        backend_response = mock.Mock()
        backend_response.json.return_value = {"status": "ok", "current_step": 1}
        backend_response.raise_for_status.return_value = None
        mock_post.return_value = backend_response

        response = views.api_simulate(
            self.factory.post(
                "/api/simulate/",
                data=json.dumps({"steps": 1}),
                content_type="application/json",
                HTTP_X_CLAUDEVILLE_CLIENT=views.CLIENT_VERSION,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(mock_post.call_args.kwargs["timeout"], 180)

    @mock.patch("translator.views.requests.post")
    def test_api_simulate_timeout_reports_backend_busy_without_stopping_playback(
        self, mock_post
    ):
        mock_post.side_effect = views.requests.Timeout("slow simulation")

        response = views.api_simulate(
            self.factory.post(
                "/api/simulate/",
                data=json.dumps({"steps": 1}),
                content_type="application/json",
                HTTP_X_CLAUDEVILLE_CLIENT=views.CLIENT_VERSION,
            )
        )
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "busy")
        self.assertIn("still running", data["message"])

    @mock.patch("translator.views.requests.post")
    def test_api_simulate_blocks_stale_clients(self, mock_post):
        response = views.api_simulate(
            self.factory.post(
                "/api/simulate/",
                data=json.dumps({"steps": 1}),
                content_type="application/json",
            )
        )
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(data["status"], "stale_client")
        mock_post.assert_not_called()


class RuntimeStatusTemplateTests(SimpleTestCase):
    def test_base_template_declares_local_favicon(self):
        frontend_root = Path(__file__).resolve().parents[1]
        base_template = frontend_root / "templates" / "base.html"
        source = base_template.read_text(encoding="utf-8")

        self.assertIn('rel="icon"', source)
        self.assertIn("static 'img/atlas.png'", source)

    def test_home_template_contains_runtime_status_fields(self):
        frontend_root = Path(__file__).resolve().parents[1]
        home_template = frontend_root / "templates" / "home" / "home.html"
        source = home_template.read_text(encoding="utf-8")

        self.assertIn("runtime-status-panel", source)
        self.assertIn("backend-time-content", source)
        self.assertIn("queue-depth-content", source)
        self.assertIn("playback-state-content", source)
        self.assertIn("backend-busy-content", source)
        self.assertIn("town-center-panel", source)
        self.assertIn("town-approval-actions", source)
        self.assertIn("town-approve-request", source)
        self.assertIn("town-reject-request", source)
        self.assertIn("town-complete-request", source)
        self.assertIn("town-fail-request", source)

    def test_home_script_updates_health_and_playback_state(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("api_health", source)
        self.assertIn("updateRuntimePanel", source)
        self.assertIn("setPlaybackState", source)
        self.assertIn("backend_busy_seconds", source)
        self.assertIn("refreshTownCenter", source)
        self.assertIn("api_town_center", source)
        self.assertIn("transitionTownCenterRequest", source)
        self.assertIn("api_town_center_request_transition", source)
        self.assertIn("approval_queue", source)

    def test_home_script_stops_auto_simulation_after_backend_error(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("handleSimulationError", source)
        self.assertIn("simulationActive = false", source)
        self.assertIn("updateSimStatus('Simulation error", source)

    def test_home_script_keeps_play_button_available_while_playing(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn(
            "} else {\n"
            "\t\t\tplayBtn.disabled = false;\n"
            "\t\t\tpauseBtn.disabled = false;",
            source,
        )

    def test_home_script_uses_visible_movement_animation(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("let movement_speed = 4;", source)
        self.assertIn("function calculateMovementFrameCount", source)
        self.assertIn("Math.ceil(maxDistance / movement_speed)", source)
        self.assertIn("function focusMovementTarget", source)
        self.assertIn("mainCamera.pan(targetX, targetY", source)

    def test_home_script_syncs_backend_snapshot_to_visible_ui(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("function syncBackendSnapshot", source)
        self.assertIn("updatePersonaCardFromSnapshot", source)
        self.assertIn("New backend run detected - reloading page", source)
        self.assertIn("window.location.reload()", source)

    def test_home_script_throttles_simulation_while_backend_is_busy(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("let backendBusy = false;", source)
        self.assertIn("backendBusy = Boolean(backend.backend_busy);", source)
        self.assertIn("backendBusy = true;", source)
        self.assertIn("!backendBusy", source)

    def test_home_script_treats_simulation_timeout_as_backend_busy(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("response.status === 504", source)
        self.assertIn("Backend timeout - waiting for completion", source)
        self.assertIn("} else if (result.status === 'ok')", source)

    def test_home_script_requests_single_step_batches_for_responsive_playback(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("const TARGET_BUFFER = 1;", source)
        self.assertIn("const BATCH_SIZE = 1;", source)
        self.assertIn("requestSimulation(BATCH_SIZE", source)
        self.assertIn("let isPaused = true;", source)
        self.assertIn("let simulationActive = false;", source)
        self.assertIn("The simulation starts only after Play is pressed", source)
        self.assertNotIn("requestSimulation(TARGET_BUFFER);", source)

    def test_home_script_play_button_kicks_playback_pipeline(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("async function kickPlaybackPipeline", source)
        self.assertIn("kickPlaybackPipeline(true);", source)
        self.assertIn("setInterval(() => kickPlaybackPipeline(false), 1000);", source)
        self.assertIn("requestSimulation(BATCH_SIZE, forceRequest);", source)

    def test_home_script_sends_current_client_version_header(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn('const CLIENT_VERSION = "stream-v2";', source)
        self.assertIn("'X-Claudeville-Client': CLIENT_VERSION", source)

    def test_home_script_uses_local_phaser_atlas_assets(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertNotIn("mikewesthad.github.io", source)
        self.assertNotIn("misa-", source)
        self.assertIn("static 'img/atlas.png'", source)
        self.assertIn("static 'assets/characters/atlas.json'", source)
        self.assertIn("fallback-front-walk", source)

    def test_home_script_polls_movements_with_step_cursor(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("let lastAppliedMovementStep = step - 1;", source)
        self.assertIn("after_step=${lastAppliedMovementStep}", source)
        self.assertIn("lastAppliedMovementStep = Math.max(", source)

    def test_home_script_guards_against_incomplete_movement_packets(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("const movementData = execute_movement", source)
        self.assertIn("if (!movementData)", source)

    def test_home_script_keeps_paused_state_above_backend_busy_status(self):
        frontend_root = Path(__file__).resolve().parents[1]
        script_template = frontend_root / "templates" / "home" / "main_script.html"
        source = script_template.read_text(encoding="utf-8")

        self.assertIn("if (isPaused && !isSkipping)", source)
        self.assertIn("simulationActive = false;", source)


class CsrfProtectionTests(SimpleTestCase):
    """OPS-1: CSRF is enforced at runtime and the cookie is primed for the JS.

    The other suites use RequestFactory, which bypasses middleware and therefore
    gives no CSRF coverage. These use the real test Client so CsrfViewMiddleware
    actually runs.
    """

    def test_untokened_post_to_mutating_api_is_blocked(self):
        # api_save is POST-only and no longer @csrf_exempt; a tokenless POST must
        # be rejected by CsrfViewMiddleware before the view (or any backend call).
        client = Client(enforce_csrf_checks=True)
        response = client.post("/api/save/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 403)

    @mock.patch("translator.views.os.path.exists", return_value=False)
    @mock.patch(
        "translator.views.requests.get",
        side_effect=views.requests.ConnectionError("backend offline"),
    )
    def test_home_page_primes_csrf_cookie(self, _mock_get, _mock_exists):
        # @ensure_csrf_cookie on home must set the csrftoken cookie so the JS can
        # echo it in X-CSRFToken. Backend + filesystem are stubbed so the view
        # returns the "start backend" page (200) without external dependencies.
        response = Client().get("/simulator_home")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    @mock.patch(
        "translator.views.open",
        new_callable=mock.mock_open,
        read_data='{"Nora Vale": {"x": 1, "y": 2}}',
    )
    @mock.patch("translator.views.os.listdir")
    def test_replay_page_primes_csrf_cookie(self, mock_listdir, _mock_open):
        # The replay view renders the same home.html (with Save/Simulate/Town-Center
        # POST controls), so it must also prime the csrftoken cookie. Regression
        # caught in adversarial review: it was missing @ensure_csrf_cookie.
        mock_listdir.side_effect = [["Nora Vale"], ["0.json"]]
        response = Client().get("/replay/run_one/5/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    def test_get_movements_does_not_require_csrf(self):
        # Safe methods (GET) are never CSRF-checked; the movements poll must still
        # work without a token. Stale-client guard returns 409 (not a CSRF 403).
        client = Client(enforce_csrf_checks=True)
        response = client.get("/api/movements/")
        self.assertNotEqual(response.status_code, 403)
