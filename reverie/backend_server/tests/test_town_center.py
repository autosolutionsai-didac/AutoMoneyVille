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

    def test_revenue_requires_human_evidence_not_self_report(self):
        # Stage 1 de-fiction: completing a request earns effort points but does
        # NOT credit revenue from the agent's self-reported expected_payoff.
        # Revenue is credited ONLY via human-confirmed record_delivery evidence.
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            req = store.submit_request(
                actor="Felix Reed",
                request_type="external_action",
                title="Send signed proposal",
                rationale="Client asked for the proposal in writing.",
                payload={"tool": "send_email", "expected_payoff": "$50"},
            )
            store.transition_request(req["id"], RequestState.APPROVED, reviewer="human", note="ok")
            store.transition_request(req["id"], RequestState.COMPLETED, reviewer="human", note="sent")

            score = store.snapshot()["team_score"]
            self.assertEqual(score["points"], 4)  # +1 approved, +3 completed
            self.assertEqual(score["revenue_cents"], 0)  # no self-reported revenue

            # Human confirms delivery with evidence -> the ONLY revenue path.
            store.record_delivery(
                req["id"], revenue_cents=5000, evidence="client paid invoice #12"
            )
            self.assertEqual(store.snapshot()["team_score"]["revenue_cents"], 5000)
            # Idempotent: re-recording the same delivery does not double-credit.
            store.record_delivery(req["id"], revenue_cents=5000, evidence="dup")
            self.assertEqual(store.snapshot()["team_score"]["revenue_cents"], 5000)

    def test_completed_request_executes_tool_and_attaches_result(self):
        # Stage 1: completing a request runs its tool via the execution layer and
        # attaches the (sanitized) result + actor to the transition for grounding.
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            req = store.submit_request(
                actor="Milo Chen",
                request_type="research",
                title="market scan",
                rationale="find niches",
                payload={"tool": "web_research", "query": "agency onboarding pain"},
            )
            t = store.transition_request(
                req["id"], RequestState.COMPLETED, reviewer="auto", note="done"
            )
            self.assertIn("tool_result", t)
            self.assertEqual(t["tool_result"]["tool"], "web_research")
            self.assertTrue(t["tool_result"]["ok"])
            self.assertEqual(t.get("actor"), "Milo Chen")

    def test_outbound_completion_is_dry_run(self):
        # An approved outbound action executes only as a dry-run (nothing sent).
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            req = store.submit_request(
                actor="Theo Grant",
                request_type="external_action",
                title="email a lead",
                rationale="follow up",
                payload={"tool": "send_email", "recipient": "lead@acme.com"},
            )
            store.transition_request(req["id"], RequestState.APPROVED, reviewer="human", note="ok")
            t = store.transition_request(req["id"], RequestState.COMPLETED, reviewer="human", note="sent")
            self.assertTrue(t["tool_result"]["dry_run"])

    def test_completed_request_persists_artifact_to_disk(self):
        # Stage 1.5: the executed ToolResult (incl. a dry-run draft) must survive
        # the HTTP response — it is appended to town_center/artifacts.jsonl and
        # surfaced in snapshot() so a human can audit what WOULD have been sent.
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            req = store.submit_request(
                actor="Theo Grant",
                request_type="external_action",
                title="email a lead",
                rationale="follow up",
                payload={"tool": "send_email", "recipient": "lead@acme.com",
                         "preview": "Hi — quick question about onboarding."},
            )
            store.transition_request(
                req["id"], RequestState.COMPLETED, reviewer="human", note="ok"
            )

            artifacts_path = Path(tmp) / "town_center" / "artifacts.jsonl"
            self.assertTrue(artifacts_path.exists())
            rows = store.artifacts.read_all()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["request_id"], req["id"])
            self.assertEqual(row["actor"], "Theo Grant")
            self.assertEqual(row["tool"], "send_email")
            self.assertTrue(row["dry_run"])
            self.assertEqual(
                row["tool_result"]["evidence"]["target"], "lead@acme.com"
            )
            # Snapshot exposes the persisted artifact for the console.
            snap = store.snapshot()
            self.assertEqual(snap["artifacts"][-1]["request_id"], req["id"])

    def test_find_request_public_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            req = store.submit_request(
                actor="Milo Chen", request_type="research", title="scan",
                rationale="x", payload={"tool": "web_research"},
            )
            found = store.find_request(req["id"])
            self.assertIsNotNone(found)
            self.assertEqual(found["title"], "scan")
            self.assertIsNone(store.find_request("req_does_not_exist"))

    def test_recent_team_deliverables_excludes_self(self):
        # Coordination: a persona sees teammates' deliverables, not its own, so
        # work can pipeline (research -> offer -> outreach).
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            a = store.submit_request(
                actor="Milo Chen", request_type="research", title="market scan",
                rationale="x", payload={"tool": "web_research"},
            )
            store.transition_request(a["id"], RequestState.COMPLETED, reviewer="auto", note="done")
            store.submit_request(
                actor="Iris Morgan", request_type="offer", title="offer draft",
                rationale="y", payload={"tool": "offer_draft"},
            )
            team = store.recent_team_deliverables("Iris Morgan")
            titles = [r["title"] for r in team]
            self.assertIn("market scan", titles)
            self.assertNotIn("offer draft", titles)  # excludes self
            self.assertTrue(all(r["actor"] != "Iris Morgan" for r in team))

    def test_recent_requests_for_returns_actor_requests_with_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            req = store.submit_request(
                actor="Iris Morgan",
                request_type="external_action",
                title="Post launch announcement",
                rationale="Wants to publish to the company account.",
                payload={"tool": "post_content"},
            )
            store.transition_request(req["id"], RequestState.REJECTED, reviewer="human", note="too early")
            # a different actor's request must not leak in
            store.submit_request(
                actor="Theo Grant", request_type="tool", title="Other", rationale="x",
                payload={"tool": "web_research"},
            )

            recent = store.recent_requests_for("Iris Morgan")
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0]["title"], "Post launch announcement")
            self.assertEqual(recent[0]["current_state"], "rejected")

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
