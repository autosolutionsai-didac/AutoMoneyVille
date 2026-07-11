"""Tests for the economy analyzer (tools/eval/economy.py).

Builds a synthetic run with a full request funnel (proposed / approved /
completed / rejected), agent-claimed payoffs, and one human-confirmed delivery,
then asserts the analyzer reports each honestly:
- funnel counts by final state + the approval-gate bottleneck,
- claimed value (agent self-reports) kept strictly apart from real revenue
  (only reward rows with source == revenue_confirmed),
- the pending queue exposes exactly the requests a console must clear,
- markdown rendering carries the headline numbers.

Reuses the tempfile + synthetic-run fixture pattern from test_emergence.

Run as a standalone unittest module:
    python -m unittest tests.test_economy_eval
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.eval import economy as economy_mod  # noqa: E402
from tools.eval.run_loader import load_run  # noqa: E402


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _submit(rid, actor, tool, title, *, payoff=None, risk="low", approval=True, t="00"):
    payload = {"tool": tool, "preview": f"draft for {title}", "risk_label": risk}
    if payoff is not None:
        payload["expected_payoff"] = payoff
    return {
        "id": rid,
        "state": "proposed",
        "actor": actor,
        "type": "external_action",
        "title": title,
        "rationale": "r",
        "payload": payload,
        "created_at": f"2026-01-01T09:{t}:00+00:00",
        "approval_required": approval,
    }


def _transition(rid, state, t="30"):
    return {
        "id": rid,
        "state": state,
        "reviewer": "human",
        "note": "n",
        "created_at": f"2026-01-01T09:{t}:00+00:00",
    }


def build_economy_run(root: Path) -> Path:
    run = root / "economy_run"
    names = ["Milo Chen", "Iris Morgan", "Theo Grant"]
    _write_json(
        run / "reverie" / "meta.json",
        {
            "maze_name": "claudeville",
            "persona_names": names,
            "step": 10,
            "scenario_id": "startup_team_v1",
            "scenario_name": "Startup Team V1",
        },
    )
    _write_json(run / "reverie" / "scenario.json", {"agents": []})
    _write_jsonl(
        run / "town_center" / "requests.jsonl",
        [
            # Completed research (tool executed) with a $50 claim.
            _submit("req_a", "Milo Chen", "web_research", "Niche scan",
                    payoff="$50", approval=False, t="00"),
            _transition("req_a", "approved", t="10"),
            _transition("req_a", "completed", t="20"),
            # Outbound email stuck at the approval gate ($1,200 claimed).
            _submit("req_b", "Iris Morgan", "send_email", "Outreach to leads",
                    payoff="$1,200", risk="medium", t="01"),
            # Rejected spend.
            _submit("req_c", "Theo Grant", "spend_money", "Buy ads",
                    payoff=25, risk="high", t="02"),
            _transition("req_c", "rejected", t="15"),
            # Second pending request from Milo, no claim.
            _submit("req_d", "Milo Chen", "post_content", "Publish landing page",
                    t="03"),
        ],
    )
    _write_jsonl(
        run / "town_center" / "rewards.jsonl",
        [
            {
                "id": "rew_1", "actor": "Milo Chen", "points": 3,
                "source": "request_completed", "evidence": "e",
                "revenue_cents": 0, "outcome_valence": 6,
                "created_at": "2026-01-01T09:20:00+00:00",
                "reference_id": "req_a:completed",
            },
            {
                "id": "rew_2", "actor": "Milo Chen", "points": 0,
                "source": "revenue_confirmed",
                "evidence": "delivered (human): client paid invoice #1",
                "revenue_cents": 4200, "outcome_valence": 8,
                "created_at": "2026-01-01T10:00:00+00:00",
                "reference_id": "req_a:delivered",
            },
        ],
    )
    return run


class EconomyAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = build_economy_run(Path(self._tmp.name))
        self.run = load_run(str(self.run_dir))
        self.payload = economy_mod.compute_economy(self.run)

    def tearDown(self):
        self._tmp.cleanup()

    def test_funnel_counts_states_and_gate(self):
        fu = self.payload["funnel"]
        self.assertEqual(fu["submitted"], 4)
        self.assertEqual(fu["by_state"]["completed"], 1)
        self.assertEqual(fu["by_state"]["rejected"], 1)
        self.assertEqual(fu["by_state"]["proposed"], 2)
        self.assertEqual(fu["pending"], 2)
        self.assertEqual(fu["stuck_at_approval_gate"], 2)
        self.assertEqual(fu["tools_executed"], 1)
        self.assertEqual(fu["transitions_total"], 3)

    def test_claimed_never_conflated_with_real(self):
        cr = self.payload["claimed_vs_real"]
        # $50 + $1,200 + $25 claimed — regardless of state.
        self.assertEqual(cr["claimed_total_cents"], 5000 + 120000 + 2500)
        self.assertEqual(cr["claim_count"], 3)
        # Real = only the revenue_confirmed row.
        self.assertEqual(cr["real_revenue_cents"], 4200)
        self.assertEqual(cr["confirmed_deliveries"], 1)
        # Biggest claim first.
        self.assertEqual(cr["claims"][0]["request_id"], "req_b")

    def test_pending_queue_is_the_console_backlog(self):
        pq = self.payload["pending_queue"]
        self.assertEqual({q["request_id"] for q in pq}, {"req_b", "req_d"})
        by_id = {q["request_id"]: q for q in pq}
        self.assertEqual(by_id["req_b"]["tool"], "send_email")
        self.assertEqual(by_id["req_b"]["risk_label"], "medium")
        self.assertIn("draft for Outreach", by_id["req_b"]["preview"])
        self.assertEqual(by_id["req_b"]["claimed_cents"], 120000)

    def test_tool_mix_and_actor_economy(self):
        tm = self.payload["tool_mix"]
        self.assertEqual(tm["tools"]["send_email"], 1)
        self.assertEqual(tm["risk_labels"]["high"], 1)
        ae = self.payload["actor_economy"]
        self.assertEqual(ae["per_actor"]["Milo Chen"]["submitted"], 2)
        self.assertEqual(
            ae["contribution"]["per_actor"]["Milo Chen"]["revenue_cents"], 4200
        )

    def test_markdown_carries_headlines(self):
        md = economy_mod.render_markdown(self.payload)
        self.assertIn("Economy report", md)
        self.assertIn("$1,275.00", md)  # claimed total
        self.assertIn("$42.00", md)  # real confirmed revenue
        self.assertIn("Pending Queue (2", md)
        self.assertIn("send_email", md)

    def test_empty_run_is_graceful(self):
        with tempfile.TemporaryDirectory() as tmp:
            bare = Path(tmp) / "bare_run"
            _write_json(bare / "reverie" / "meta.json", {"persona_names": []})
            payload = economy_mod.compute_economy(load_run(str(bare)))
        self.assertEqual(payload["funnel"]["submitted"], 0)
        self.assertEqual(payload["claimed_vs_real"]["real_revenue_cents"], 0)
        self.assertEqual(payload["pending_queue"], [])
        # Renders without raising.
        self.assertIn("Economy report", economy_mod.render_markdown(payload))


if __name__ == "__main__":
    unittest.main()
