"""HTTP-route tests for the town-center control plane + live inspector
(Flask test client).

Exercises the actual route closures from ReverieServer._setup_flask_routes
without booting a simulation: a bare ReverieServer shell gets a fresh Flask app
and a temp-dir TownCenterStore. Covers the Stage 1.5 console surface:
- GET /town-center exposes persisted artifacts,
- POST record-delivery validates id + evidence, credits revenue once, and is
  idempotent on replay (the money-gate contract).
"""

import datetime
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from flask import Flask

from reverie.backend_server.reverie import ReverieServer
from reverie.backend_server.town_center import TownCenterStore


def _make_client(tmp):
    rs = ReverieServer.__new__(ReverieServer)
    rs.flask_app = Flask(__name__)
    rs.town_center = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
    rs.personas = {}
    rs.personas_tile = {}
    rs._setup_flask_routes()
    return rs, rs.flask_app.test_client()


def _stub_persona(name="Theo Grant"):
    """Minimal persona shell for the inspector snapshot (defensive reads)."""
    node = SimpleNamespace(
        description="drafted an outreach email",
        created=datetime.datetime(2026, 1, 1, 9, 30),
        poignancy=6,
    )
    return SimpleNamespace(
        name=name,
        scratch=SimpleNamespace(
            currently="pitching the onboarding audit",
            act_description="writing a draft",
            act_address="the Ville:office:desk",
            chatting_with=None,
            curr_time=datetime.datetime(2026, 1, 1, 9, 45),
            # Real schedules span the day from midnight (sleep blocks included).
            f_daily_schedule=[
                ["sleeping", 540],          # 00:00-09:00
                ["standup", 30],            # 09:00-09:30
                ["draft outreach", 60],     # 09:30-10:30  <- 09:45 is here
            ],
        ),
        a_mem=SimpleNamespace(seq_event=[node], seq_thought=[], seq_chat=[]),
        r_mem=SimpleNamespace(
            relationships={
                "milo chen": {
                    "name": "Milo Chen",
                    "familiarity": 3,
                    "affinity": 0.4,
                    "sentiment": "friendly",
                    "last_topics": ["research"],
                }
            }
        ),
        g_mem=SimpleNamespace(
            goals={"g1": {"title": "close first client", "status": "active"}}
        ),
    )


class RecordDeliveryRouteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rs, self.client = _make_client(self._tmp.name)
        self.req = self.rs.town_center.submit_request(
            actor="Theo Grant",
            request_type="external_action",
            title="email a lead",
            rationale="follow up",
            payload={"tool": "send_email", "recipient": "lead@acme.com",
                     "preview": "Hi there"},
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _complete(self):
        return self.client.post(
            f"/town-center/requests/{self.req['id']}/transition",
            json={"state": "completed", "reviewer": "human", "note": "ok"},
        )

    def test_unknown_request_is_404(self):
        resp = self.client.post(
            "/town-center/requests/req_nope/record-delivery",
            json={"revenue_cents": 100, "evidence": "x"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_evidence_is_required(self):
        resp = self.client.post(
            f"/town-center/requests/{self.req['id']}/record-delivery",
            json={"revenue_cents": 100, "evidence": "   "},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("evidence", resp.get_json()["error"])

    def test_bad_amount_is_400(self):
        resp = self.client.post(
            f"/town-center/requests/{self.req['id']}/record-delivery",
            json={"revenue_cents": "lots", "evidence": "invoice #1"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_delivery_credits_revenue_once(self):
        self._complete()
        resp = self.client.post(
            f"/town-center/requests/{self.req['id']}/record-delivery",
            json={"revenue_cents": 4200, "evidence": "invoice #1 paid"},
        )
        self.assertEqual(resp.status_code, 200)
        row = resp.get_json()
        self.assertEqual(row["revenue_cents"], 4200)
        self.assertEqual(row["source"], "revenue_confirmed")
        self.assertEqual(row["actor"], "Theo Grant")
        # Replay is idempotent — no double-credit.
        resp2 = self.client.post(
            f"/town-center/requests/{self.req['id']}/record-delivery",
            json={"revenue_cents": 4200, "evidence": "invoice #1 paid"},
        )
        self.assertTrue(resp2.get_json().get("already_recorded"))
        score = self.rs.town_center.rewards.team_score()
        self.assertEqual(score["revenue_cents"], 4200)

    def test_approve_with_execute_chains_to_completed(self):
        # One click = approve + run tool + artifact + reward. Previously an
        # 'approved' request was unreachable limbo (only 'completed' executes).
        resp = self.client.post(
            f"/town-center/requests/{self.req['id']}/transition",
            json={"state": "approved", "reviewer": "human",
                  "note": "good draft — send it", "execute": True},
        )
        self.assertEqual(resp.status_code, 200)
        entry = resp.get_json()
        self.assertEqual(entry["state"], "completed")
        self.assertTrue(entry["tool_result"]["dry_run"])
        # The request's current state really is completed (not parked).
        current = self.rs.town_center.find_request(self.req["id"])
        self.assertEqual(current["current_state"], "completed")
        # Both transition rewards exist exactly once (idempotent references).
        refs = [r.get("reference_id") for r in self.rs.town_center.rewards.read_all()]
        self.assertEqual(refs.count(f"{self.req['id']}:approved"), 1)
        self.assertEqual(refs.count(f"{self.req['id']}:completed"), 1)
        # Artifact persisted by the chained execution.
        self.assertEqual(
            self.rs.town_center.artifacts.read_all()[-1]["request_id"],
            self.req["id"],
        )

    def test_approve_without_execute_stays_approved(self):
        resp = self.client.post(
            f"/town-center/requests/{self.req['id']}/transition",
            json={"state": "approved", "reviewer": "human", "note": "hold"},
        )
        self.assertEqual(resp.status_code, 200)
        current = self.rs.town_center.find_request(self.req["id"])
        self.assertEqual(current["current_state"], "approved")
        self.assertEqual(self.rs.town_center.artifacts.read_all(), [])

    def test_snapshot_route_exposes_artifacts(self):
        self._complete()
        snap = self.client.get("/town-center").get_json()
        self.assertTrue(snap["artifacts"])
        artifact = snap["artifacts"][-1]
        self.assertEqual(artifact["request_id"], self.req["id"])
        self.assertTrue(artifact["dry_run"])
        self.assertEqual(
            artifact["tool_result"]["evidence"]["target"], "lead@acme.com"
        )


class EventFeedRouteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rs, self.client = _make_client(self._tmp.name)
        import collections
        import threading

        self.rs._feed_events = collections.deque(maxlen=500)
        self.rs._feed_next_id = 1
        self.rs._feed_lock = threading.Lock()

    def tearDown(self):
        self._tmp.cleanup()

    def test_feed_event_and_after_id_cursor(self):
        self.rs.feed_event("request_submitted", "Theo filed: email channel",
                           personas=["Theo Grant"], tile=(3, 4))
        self.rs.feed_event("new_day", "A new day begins")
        first = self.client.get("/events").get_json()
        self.assertEqual(len(first["events"]), 2)
        self.assertEqual(first["events"][0]["category"], "economy")
        self.assertEqual(first["events"][0]["tile"], [3, 4])
        self.assertEqual(first["events"][1]["category"], "sim")
        self.assertEqual(first["latest_id"], 2)
        # Cursor: only events after `after_id` come back.
        second = self.client.get("/events?after_id=1").get_json()
        self.assertEqual(len(second["events"]), 1)
        self.assertEqual(second["events"][0]["type"], "new_day")
        # Nothing new -> empty.
        third = self.client.get("/events?after_id=2").get_json()
        self.assertEqual(third["events"], [])

    def test_feed_event_never_raises(self):
        # Even a bad tile/personas payload must not raise (presentation-layer).
        self.rs.feed_event("conversation_started", "x", tile=object())
        resp = self.client.get("/events")
        self.assertEqual(resp.status_code, 200)


class PersonaStateRouteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rs, self.client = _make_client(self._tmp.name)
        self.rs.personas = {"Theo Grant": _stub_persona()}
        self.rs.personas_tile = {"Theo Grant": (12, 34)}

    def tearDown(self):
        self._tmp.cleanup()

    def test_unknown_persona_404(self):
        resp = self.client.get("/persona/Nobody/state")
        self.assertEqual(resp.status_code, 404)

    def test_live_state_snapshot(self):
        resp = self.client.get("/persona/Theo Grant/state")
        self.assertEqual(resp.status_code, 200)
        state = resp.get_json()
        self.assertEqual(state["name"], "Theo Grant")
        self.assertEqual(state["currently"], "pitching the onboarding audit")
        self.assertEqual(state["tile"], [12, 34])
        # Schedule with the current row resolved (09:45 -> "draft outreach").
        self.assertEqual(len(state["schedule"]), 3)
        self.assertEqual(state["schedule_current_index"], 2)
        self.assertEqual(state["memories"][0]["kind"], "event")
        self.assertEqual(state["relationships"][0]["name"], "Milo Chen")
        self.assertEqual(state["goals"][0]["title"], "close first client")

    def test_underscore_name_variant_resolves(self):
        resp = self.client.get("/persona/Theo_Grant/state")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["name"], "Theo Grant")


if __name__ == "__main__":
    unittest.main()
