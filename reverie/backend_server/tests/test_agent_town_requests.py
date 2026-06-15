import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.event_ledger import EventLedger
from reverie.backend_server.persona.prompt_template.claude_structure import (
    parse_step_response,
)
from reverie.backend_server.town_center import TownCenterStore


class AgentTownRequestParsingTests(unittest.TestCase):
    def test_parse_step_response_accepts_town_request_proposal(self):
        response = {
            "continuing": True,
            "social": {"wants_to_talk": False},
            "thoughts": [],
            "town_request": {
                "type": "external_action",
                "title": "Send first outreach email",
                "rationale": "A reviewed preview is needed before contacting prospects.",
                "payload": {
                    "tool": "send_email",
                    "preview": "Draft email body",
                    "expected_payoff": "Book one discovery call",
                },
            },
        }

        parsed = parse_step_response(json.dumps(response), "Theo Grant", [], {}, {})

        request = getattr(parsed, "town_request", None)
        self.assertEqual(parsed.parse_errors, [])
        self.assertIsNotNone(request)
        self.assertEqual(request.request_type, "external_action")
        self.assertEqual(request.title, "Send first outreach email")
        self.assertEqual(request.payload["tool"], "send_email")

    def test_parse_step_response_rejects_incomplete_town_request(self):
        response = {
            "continuing": True,
            "social": {"wants_to_talk": False},
            "town_request": {"title": "Need a tool"},
        }

        parsed = parse_step_response(json.dumps(response), "Theo Grant", [], {}, {})

        self.assertIsNone(getattr(parsed, "town_request", None))
        self.assertIn("town_request requires title and rationale", parsed.parse_errors)


class AgentTownRequestSubmissionTests(unittest.TestCase):
    def test_submit_agent_town_request_records_approval_requirement_and_event(self):
        try:
            from reverie.backend_server.agent_requests import (
                submit_town_request_from_step,
            )
        except ImportError:
            self.fail("submit_town_request_from_step helper is missing")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = TownCenterStore(root, scenario_id="startup_team_v1")
            ledger = EventLedger(root / "events.jsonl")
            step_response = SimpleNamespace(
                town_request=SimpleNamespace(
                    request_type="external_action",
                    title="Send first outreach email",
                    rationale="External contact requires human review first.",
                    payload={"tool": "send_email", "preview": "Draft email body"},
                )
            )

            request = submit_town_request_from_step(
                store,
                actor="Theo Grant",
                step_response=step_response,
                event_ledger=ledger,
                step=7,
                sim_time="June 15, 2026, 09:01:10",
            )

            snapshot = store.snapshot()
            events = ledger.read_all()
            self.assertEqual(request["state"], "proposed")
            self.assertTrue(request["approval_required"])
            self.assertEqual(snapshot["approval_queue"][0]["id"], request["id"])
            self.assertEqual(events[0]["type"], "town_request_submitted")
            self.assertEqual(events[0]["actor"], "Theo Grant")
            self.assertEqual(events[0]["payload"]["request_id"], request["id"])

    def test_submit_latest_town_request_clears_persona_response_after_recording(self):
        try:
            from reverie.backend_server.agent_requests import submit_latest_town_request
        except ImportError:
            self.fail("submit_latest_town_request helper is missing")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = TownCenterStore(root, scenario_id="startup_team_v1")
            ledger = EventLedger(root / "events.jsonl")
            step_response = SimpleNamespace(
                town_request=SimpleNamespace(
                    request_type="tool",
                    title="Research payment operations niches",
                    rationale="Read-only research can uncover service opportunities.",
                    payload={"tool": "web_research"},
                )
            )
            persona = SimpleNamespace(last_step_response=step_response)

            first = submit_latest_town_request(
                store,
                actor="Milo Chen",
                persona=persona,
                event_ledger=ledger,
                step=8,
                sim_time="June 15, 2026, 09:01:20",
            )
            second = submit_latest_town_request(
                store,
                actor="Milo Chen",
                persona=persona,
                event_ledger=ledger,
                step=8,
                sim_time="June 15, 2026, 09:01:20",
            )

            self.assertIsNotNone(first)
            self.assertIsNone(second)
            self.assertIsNone(persona.last_step_response)
            self.assertEqual(len(store.snapshot()["requests"]), 1)
            self.assertFalse(store.snapshot()["requests"][0]["approval_required"])


if __name__ == "__main__":
    unittest.main()
