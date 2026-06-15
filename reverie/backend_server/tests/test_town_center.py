import tempfile
import unittest
from pathlib import Path

from reverie.backend_server.economy import RequestState
from reverie.backend_server.scenario_config import load_scenario
from reverie.backend_server.town_center import TownCenterStore


class ScenarioConfigTests(unittest.TestCase):
    def test_startup_team_scenario_loads_validated_roster_and_policy(self):
        scenario = load_scenario("startup_team_v1")

        self.assertEqual(scenario["id"], "startup_team_v1")
        self.assertEqual(len(scenario["agents"]), 10)
        self.assertTrue(
            scenario["starting_resources"]["approval_required_for_external_actions"]
        )
        self.assertIn("send_email", scenario["real_world_policy"]["blocked_without_approval"])
        self.assertIn("strategist", {agent["role"] for agent in scenario["agents"]})


class TownCenterStoreTests(unittest.TestCase):
    def test_snapshot_combines_scenario_tools_requests_and_scores(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            request = store.submit_request(
                actor="Felix Reed",
                request_type="tool",
                title="Request outbound email approval",
                rationale="Need approval before any external contact.",
                payload={"tool": "send_email"},
            )
            store.award_reward(
                actor="Milo Chen",
                points=3,
                source="validated_opportunity",
                evidence="Niche research with buyer pain evidence.",
            )

            snapshot = store.snapshot()

            self.assertEqual(snapshot["scenario"]["id"], "startup_team_v1")
            self.assertEqual(snapshot["team_score"]["points"], 3)
            self.assertEqual(snapshot["requests"][0]["id"], request["id"])
            self.assertEqual(snapshot["requests"][0]["current_state"], "proposed")
            self.assertTrue(snapshot["requests"][0]["approval_required"])
            self.assertTrue(
                any(tool["name"] == "send_email" for tool in snapshot["tools"])
            )

    def test_agent_names_are_canonicalized_for_requests_and_rewards(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")

            store.submit_request(
                actor="felix_reed",
                request_type="tool",
                title="Draft offer page",
                rationale="Drafting is an internal safe action.",
                payload={"tool": "offer_draft"},
            )
            store.award_reward(
                actor="nora vale",
                points=2,
                source="validated_opportunity",
                evidence="Found a focused service wedge.",
            )

            snapshot = store.snapshot()
            self.assertEqual(snapshot["requests"][0]["actor"], "Felix Reed")
            self.assertEqual(snapshot["rewards"][0]["actor"], "Nora Vale")

    def test_request_transitions_update_current_state_without_mutating_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            request = store.submit_request(
                actor="Felix Reed",
                request_type="resource",
                title="Need a landing page draft",
                rationale="Drafting is safe and internal.",
                payload={"tool": "offer_draft"},
            )

            store.transition_request(
                request["id"],
                RequestState.APPROVED,
                reviewer="human",
                note="Approved for drafting only.",
            )

            snapshot = store.snapshot()
            self.assertEqual(len(snapshot["request_events"]), 2)
            self.assertEqual(snapshot["requests"][0]["current_state"], "approved")
            self.assertFalse(snapshot["requests"][0]["approval_required"])

    def test_external_action_requests_stay_in_approval_queue_until_reviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            request = store.submit_request(
                actor="Theo Grant",
                request_type="external_action",
                title="Send first outreach email",
                rationale="External contact requires explicit human approval.",
                payload={"tool": "send_email"},
            )

            proposed = store.snapshot()
            self.assertEqual(proposed["pending_approval_count"], 1)
            self.assertEqual(proposed["approval_queue"][0]["id"], request["id"])
            self.assertEqual(proposed["approval_queue"][0]["current_state"], "proposed")

            store.transition_request(
                request["id"],
                RequestState.APPROVED,
                reviewer="human",
                note="Approved after preview review.",
            )

            approved = store.snapshot()
            self.assertEqual(approved["pending_approval_count"], 0)
            self.assertEqual(approved["approval_queue"], [])
            self.assertEqual(approved["requests"][0]["current_state"], "approved")

    def test_request_approval_and_completion_award_auditable_points_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            request = store.submit_request(
                actor="Milo Chen",
                request_type="tool",
                title="Research payment operations niches",
                rationale="Read-only research can uncover service opportunities.",
                payload={"tool": "web_research"},
            )

            store.transition_request(
                request["id"],
                RequestState.APPROVED,
                reviewer="human",
                note="Useful safe research direction.",
            )
            store.transition_request(
                request["id"],
                RequestState.APPROVED,
                reviewer="human",
                note="Duplicate approval should not duplicate reward.",
            )
            store.transition_request(
                request["id"],
                RequestState.COMPLETED,
                reviewer="human",
                note="Research produced a shortlist of reachable niches.",
            )

            snapshot = store.snapshot()
            rewards = snapshot["rewards"]
            self.assertEqual(snapshot["team_score"]["points"], 4)
            self.assertEqual([reward["points"] for reward in rewards], [1, 3])
            self.assertEqual(
                [reward["source"] for reward in rewards],
                ["request_approved", "request_completed"],
            )
            self.assertEqual(rewards[0]["actor"], "Milo Chen")
            self.assertIn(request["id"], rewards[0]["reference_id"])
            self.assertIn("Useful safe research direction", rewards[0]["evidence"])
            self.assertIn(
                "Research produced a shortlist", rewards[1]["evidence"]
            )
            self.assertEqual([reward["outcome_valence"] for reward in rewards], [2, 6])

    def test_request_rejection_and_failure_create_negative_outcome_signals_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            first = store.submit_request(
                actor="Theo Grant",
                request_type="external_action",
                title="Send unreviewed outreach",
                rationale="Try outbound contact quickly.",
                payload={"tool": "send_email"},
            )
            second = store.submit_request(
                actor="Lena Ortiz",
                request_type="resource",
                title="Run delivery experiment",
                rationale="Test fulfillment workflow.",
                payload={"tool": "internal_planning"},
            )

            store.transition_request(
                first["id"],
                RequestState.REJECTED,
                reviewer="human",
                note="Too vague and risky.",
            )
            store.transition_request(
                first["id"],
                RequestState.REJECTED,
                reviewer="human",
                note="Duplicate rejection should not duplicate penalty.",
            )
            store.transition_request(
                second["id"],
                RequestState.FAILED,
                reviewer="human",
                note="Experiment did not produce useful evidence.",
            )

            snapshot = store.snapshot()
            rewards = snapshot["rewards"]
            self.assertEqual(snapshot["team_score"]["points"], -3)
            self.assertEqual([reward["points"] for reward in rewards], [-1, -2])
            self.assertEqual(
                [reward["source"] for reward in rewards],
                ["request_rejected", "request_failed"],
            )
            self.assertEqual(
                [reward["outcome_valence"] for reward in rewards], [-3, -6]
            )


if __name__ == "__main__":
    unittest.main()
