import json
import subprocess
from pathlib import Path

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates/home"
STATIC = ROOT / "static_dirs"
HUD_HARNESS = Path(__file__).with_name("js_tests") / "hud_drawers_harness.js"
DEPTH_HARNESS = Path(__file__).with_name("js_tests") / "demo_depth_harness.js"
CAMERA_HARNESS = Path(__file__).with_name("js_tests") / "world_camera_harness.js"


class GameHudContractTests(SimpleTestCase):
    def test_gameplay_drawers_start_collapsed_and_are_accessible(self):
        home = (TEMPLATES / "home.html").read_text(encoding="utf-8")
        assert 'id="persona-panel" class="ui-overlay side-panel collapsed"' in home
        assert 'id="event-feed" class="ui-overlay event-feed collapsed"' in home
        assert home.count('aria-expanded="false"') >= 4
        assert 'aria-controls="persona-panel"' in home
        assert 'aria-controls="event-feed"' in home
        assert 'aria-controls="town-center-panel"' in home
        assert 'aria-controls="runtime-status-panel"' in home

    def test_replay_status_is_single_and_compact(self):
        home = (TEMPLATES / "home.html").read_text(encoding="utf-8")
        main = (TEMPLATES / "main_script.html").read_text(encoding="utf-8")
        assert home.count('id="sim-status"') == 1
        assert 'id="sim-status"' in home.split('id="control-bar"', 1)[1]
        assert 'id="replay-badge"' not in home
        assert "getElementById('replay-badge')" not in main
        assert "Replay · frozen step" in main

    def test_hud_helper_gates_camera_and_coordinates_drawers(self):
        helper = (STATIC / "js/hud_drawers.js").read_text(encoding="utf-8")
        main = (TEMPLATES / "main_script.html").read_text(encoding="utf-8")
        assert "closeDrawers(next ? name : null)" in helper
        assert "blocksCameraInput" in helper
        assert 'event.key !== "Escape"' in helper
        assert "ClaudevilleHUD?.blocksCameraInput" in main
        assert "window.ClaudevilleHUD?.inspectorOpened()" in (
            TEMPLATES / "inspector_script.html"
        ).read_text(encoding="utf-8")

    def test_hud_styles_protect_desktop_and_mobile_playfields(self):
        css = (STATIC / "css/game_hud.css").read_text(encoding="utf-8")
        assert "width: min(820px, calc(100vw - 220px))" in css
        assert ".hud-secondary-drawer.hud-open" in css
        assert "@media (max-width: 560px)" in css
        assert "max-height: 68vh" in css
        assert "prefers-reduced-motion" in css

    def test_demo_movement_depth_uses_the_logical_foot_position(self):
        result = subprocess.run(
            [
                "node",
                str(DEPTH_HARNESS),
                str(ROOT / "templates/demo/main_script.html"),
                str(STATIC / "js/character_renderer.js"),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "depth": 2200,
                "initialShadow": [100, 200],
                "movedDepth": 2232,
                "movingShadow": [132, 232],
                "ok": True,
            },
        )

    def test_every_closed_drawer_is_keyboard_inert_and_replay_safe(self):
        result = subprocess.run(
            [
                "node",
                str(HUD_HARNESS),
                str(STATIC / "js/hud_drawers.js"),
                str(STATIC / "js/replay_mode_guard.js"),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_finite_world_camera_centers_only_oversized_axes(self):
        home = (TEMPLATES / "home.html").read_text(encoding="utf-8")
        self.assertLess(home.index("js/world_camera.js"), home.index("main_script.html"))
        result = subprocess.run(
            [
                "node",
                str(CAMERA_HARNESS),
                str(STATIC / "js/world_camera.js"),
                str(TEMPLATES / "main_phaser_controls.html"),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})
