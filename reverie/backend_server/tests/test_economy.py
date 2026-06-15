import tempfile
import unittest
from pathlib import Path

from reverie.backend_server.economy import (
    RequestLedger,
    RequestState,
    RewardLedger,
    ToolRegistry,
)


class ToolRegistryTests(unittest.TestCase):
    def test_default_tools_separate_safe_drafts_from_external_actions(self):
        registry = ToolRegistry.default()

        self.assertFalse(registry.get("web_research").requires_approval)
        self.assertFalse(registry.get("offer_draft").requires_approval)
        self.assertTrue(registry.get("send_email").requires_approval)
        self.assertTrue(registry.get("spend_money").requires_approval)

    def test_unknown_tools_are_not_auto_allowed(self):
        registry = ToolRegistry.default()

        self.assertTrue(registry.requires_approval("unknown_new_tool"))


class RequestLedgerTests(unittest.TestCase):
    def test_requests_start_proposed_and_can_be_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RequestLedger(Path(tmp) / "requests.jsonl")

            request = ledger.submit(
                actor="Tool Advocate",
                request_type="tool_access",
                title="Use lead research",
                rationale="Find service prospects",
                payload={"tool": "web_research"},
            )
            approved = ledger.transition(
                request["id"],
                RequestState.APPROVED,
                reviewer="human",
                note="Safe read-only research.",
            )

            self.assertEqual(request["state"], RequestState.PROPOSED.value)
            self.assertEqual(approved["state"], RequestState.APPROVED.value)
            self.assertEqual(approved["reviewer"], "human")
            self.assertEqual(len(ledger.read_all()), 2)


class RewardLedgerTests(unittest.TestCase):
    def test_rewards_track_mixed_points_and_revenue_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = RewardLedger(Path(tmp) / "rewards.jsonl")

            reward = ledger.award(
                actor="Market Researcher",
                points=5,
                source="validated_lead",
                evidence="Found a reachable niche with clear pain.",
                revenue_cents=0,
            )

            self.assertEqual(reward["actor"], "Market Researcher")
            self.assertEqual(reward["points"], 5)
            self.assertEqual(reward["revenue_cents"], 0)
            self.assertEqual(ledger.team_score()["points"], 5)


if __name__ == "__main__":
    unittest.main()
