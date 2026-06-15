import threading
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

from flask import Flask

sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.reverie import PERSONA_MOVE_TIMEOUT_SECONDS, ReverieServer


class MovementStreamTests(unittest.TestCase):
    def make_reverie(self):
        reverie = ReverieServer.__new__(ReverieServer)
        reverie.step = 3
        reverie._movements_lock = threading.Lock()
        reverie._pending_movements = []
        reverie._movement_history = []
        reverie._movement_history_limit = 100
        reverie.flask_app = Flask(__name__)
        reverie._setup_flask_routes()
        return reverie

    def test_movements_after_step_cursor_does_not_consume_history(self):
        reverie = self.make_reverie()
        first = {"meta": {"step": 1}, "persona": {}}
        second = {"meta": {"step": 2}, "persona": {}}

        reverie._record_movement(first)
        reverie._record_movement(second)

        client = reverie.flask_app.test_client()
        response_one = client.get("/movements?after_step=1")
        response_two = client.get("/movements?after_step=1")

        self.assertEqual(response_one.get_json()["meta"]["step"], 2)
        self.assertEqual(response_two.get_json()["meta"]["step"], 2)
        self.assertEqual(len(reverie._movement_history), 2)

    def test_legacy_movements_endpoint_still_pops_pending_queue(self):
        reverie = self.make_reverie()
        reverie._record_movement({"meta": {"step": 1}, "persona": {}})

        client = reverie.flask_app.test_client()
        first = client.get("/movements").get_json()
        second = client.get("/movements").get_json()

        self.assertEqual(first["meta"]["step"], 1)
        self.assertTrue(second["empty"])

    def test_fallback_persona_move_result_keeps_persona_in_place(self):
        reverie = self.make_reverie()
        reverie.personas_tile = {"Nora Vale": (24, 25)}
        persona = SimpleNamespace(
            scratch=SimpleNamespace(
                act_description="Reviewing market notes",
                act_address="the Ville:studio:desk",
                act_pronunciatio="",
                chat=[],
            )
        )

        result = reverie._fallback_persona_move_result("Nora Vale", persona)

        self.assertEqual(result[0], "Nora Vale")
        self.assertEqual(result[1], (24, 25))
        self.assertIn("Reviewing market notes", result[3])
        self.assertFalse(result[5])

    def test_persona_move_timeout_keeps_playback_responsive(self):
        self.assertLessEqual(PERSONA_MOVE_TIMEOUT_SECONDS, 15)


if __name__ == "__main__":
    unittest.main()
