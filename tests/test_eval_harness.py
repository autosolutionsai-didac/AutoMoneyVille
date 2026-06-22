"""Tests for the offline evaluation harness (tools/eval).

Builds a tiny synthetic run directory in a tempdir with a few movement, event,
request, and reward files, then asserts the structural metrics compute correctly:
role specialization, per-agent contribution, social-network edges, and request
coherence/handoffs. No LLM is exercised here (the judge is graceful and tested
only for its skip path).

Run as a standalone unittest module:
    python -m unittest tests.test_eval_harness
    python -m unittest discover -s tests
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Make the repo root importable so "tools.eval" resolves regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.eval import metrics as metrics_mod  # noqa: E402
from tools.eval import replay_diff  # noqa: E402
from tools.eval.believability_judge import (  # noqa: E402
    build_day_traces,
    parse_judge_response,
    run_judge,
)
from tools.eval.run_loader import load_run  # noqa: E402


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _movement_packet(step: int, positions: dict, conversations=None, chats=None):
    persona = {}
    for name, pos in positions.items():
        persona[name] = {
            "movement": list(pos),
            "pronunciatio": "X",
            "description": f"{name} working at step {step}",
            "chat": (chats or {}).get(name),
            "had_action": True,
        }
    return {
        "persona": persona,
        "meta": {
            "curr_time": "February 13, 2023, 09:00:00",
            "step": step,
            "had_new_action": True,
            "active_personas": list(positions),
            "town_requests": [],
            "town_request_count": 0,
            "conversations": conversations or {},
        },
    }


def build_synthetic_run(root: Path) -> Path:
    """Create a minimal but representative run dir; return its path."""
    run = root / "synthetic_run"

    _write_json(
        run / "reverie" / "meta.json",
        {
            "start_date": "February 13, 2023",
            "curr_time": "February 13, 2023, 09:01:00",
            "sec_per_step": 10,
            "maze_name": "claudeville",
            "persona_names": ["Milo Chen", "Iris Morgan", "Theo Grant"],
            "step": 6,
            "scenario_id": "startup_team_v1",
            "scenario_name": "Startup Team V1",
            "scenario_objective": "Generate real-world money.",
        },
    )
    _write_json(
        run / "reverie" / "scenario.json",
        {
            "id": "startup_team_v1",
            "name": "Startup Team V1",
            "objective": "Generate real-world money.",
            "agents": [
                {"name": "Milo Chen", "role": "market_researcher", "mission": "Find niches."},
                {"name": "Iris Morgan", "role": "offer_designer", "mission": "Design offers."},
                {"name": "Theo Grant", "role": "sales_drafter", "mission": "Draft outreach."},
            ],
        },
    )

    # Events: 3 sim steps (2 active) + 3 town_request_submitted.
    events = [
        {"id": "e0", "type": "simulation_step", "actor": "runtime", "step": 0,
         "payload": {"had_new_action": True, "active_personas": ["Milo Chen"]}},
        {"id": "e1", "type": "simulation_step", "actor": "runtime", "step": 1,
         "payload": {"had_new_action": True, "active_personas": ["Iris Morgan"]}},
        {"id": "e2", "type": "simulation_step", "actor": "runtime", "step": 2,
         "payload": {"had_new_action": False, "active_personas": []}},
        {"id": "e3", "type": "town_request_submitted", "actor": "Milo Chen", "step": 0,
         "payload": {"request_id": "req_research"}},
        {"id": "e4", "type": "town_request_submitted", "actor": "Iris Morgan", "step": 1,
         "payload": {"request_id": "req_offer"}},
        {"id": "e5", "type": "town_request_submitted", "actor": "Theo Grant", "step": 2,
         "payload": {"request_id": "req_email"}},
        # Phase 4e: two identity-drift checkpoints for Milo across day boundaries.
        {"id": "e6", "type": "identity_drift", "actor": "Milo Chen", "step": 3,
         "payload": {"drift_score": 0.2, "drift_note": "mostly in character"}},
        {"id": "e7", "type": "identity_drift", "actor": "Milo Chen", "step": 5,
         "payload": {"drift_score": 0.5, "drift_note": "drifting toward sales"}},
    ]
    _write_jsonl(run / "events.jsonl", events)

    # Requests: 3 submits forming research -> offer -> outreach, + transitions.
    requests = [
        {"id": "req_research", "state": "proposed", "actor": "Milo Chen",
         "type": "research", "title": "Market research brief for niche",
         "rationale": "r", "created_at": "2026-01-01T00:00:00"},
        {"id": "req_offer", "state": "proposed", "actor": "Iris Morgan",
         "type": "documentation", "title": "Offer package design v1",
         "rationale": "r", "created_at": "2026-01-01T00:01:00"},
        {"id": "req_email", "state": "proposed", "actor": "Theo Grant",
         "type": "external_action", "title": "Cold email outreach approval",
         "rationale": "r", "created_at": "2026-01-01T00:02:00"},
        {"id": "req_research", "state": "approved", "reviewer": "human",
         "created_at": "2026-01-01T01:00:00"},
        {"id": "req_offer", "state": "approved", "reviewer": "human",
         "created_at": "2026-01-01T01:01:00"},
        {"id": "req_email", "state": "rejected", "reviewer": "human",
         "created_at": "2026-01-01T01:02:00"},
    ]
    _write_jsonl(run / "town_center" / "requests.jsonl", requests)

    rewards = [
        {"id": "rw0", "actor": "Milo Chen", "points": 3, "source": "request_approved",
         "revenue_cents": 0, "outcome_valence": 2},
        {"id": "rw1", "actor": "Iris Morgan", "points": 2, "source": "request_approved",
         "revenue_cents": 0, "outcome_valence": 1},
        {"id": "rw2", "actor": "Milo Chen", "points": 5, "source": "actual_revenue",
         "revenue_cents": 5000, "outcome_valence": 3},
    ]
    _write_jsonl(run / "town_center" / "rewards.jsonl", rewards)

    # Movement: 3 steps. Step 1 has a conversation between Milo and Iris.
    _write_json(
        run / "movement" / "0.json",
        _movement_packet(0, {"Milo Chen": (1, 1), "Iris Morgan": (2, 2), "Theo Grant": (9, 9)}),
    )
    _write_json(
        run / "movement" / "1.json",
        _movement_packet(
            1,
            {"Milo Chen": (3, 3), "Iris Morgan": (3, 4), "Theo Grant": (9, 9)},
            conversations={"g1": {"participants": ["Milo Chen", "Iris Morgan"], "line_count": 2}},
            chats={"Milo Chen": [["Milo Chen", "Hi Iris"], ["Iris Morgan", "Hey Milo"]]},
        ),
    )
    _write_json(
        run / "movement" / "2.json",
        _movement_packet(2, {"Milo Chen": (3, 3), "Iris Morgan": (3, 4), "Theo Grant": (9, 9)}),
    )

    # Persona memory nodes for one persona.
    _write_json(
        run / "personas" / "Milo Chen" / "bootstrap_memory"
        / "associative_memory" / "nodes.json",
        {"node_1": {"type": "event"}, "node_2": {"type": "thought"}},
    )
    return run


class EvalHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.run_dir = build_synthetic_run(Path(cls._tmp.name))
        cls.rundata = load_run(str(cls.run_dir))
        cls.metrics = metrics_mod.compute_metrics(cls.rundata)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_run_loads_all_artifacts(self):
        self.assertEqual(self.rundata.sim_code, "synthetic_run")
        self.assertEqual(len(self.rundata.events), 8)
        self.assertEqual(len(self.rundata.movement), 3)
        self.assertEqual(self.rundata.memory_counts.get("Milo Chen"), 2)
        self.assertEqual(set(self.rundata.persona_names), {"Milo Chen", "Iris Morgan", "Theo Grant"})

    def test_role_specialization(self):
        spec = self.metrics["role_specialization"]
        self.assertEqual(spec["actors_with_requests"], 3)
        milo = spec["per_actor"]["Milo Chen"]
        self.assertEqual(milo["role"], "market_researcher")
        self.assertEqual(milo["request_count"], 1)
        # Single request type -> fully concentrated.
        self.assertEqual(milo["concentration"], 1.0)
        self.assertIn("research", milo["type_distribution"])

    def test_approval_rates(self):
        ap = self.metrics["approval_rates"]["per_actor"]
        self.assertEqual(ap["Milo Chen"]["approved"], 1)
        self.assertEqual(ap["Milo Chen"]["approval_rate"], 1.0)
        self.assertEqual(ap["Theo Grant"]["rejected"], 1)
        self.assertEqual(ap["Theo Grant"]["approval_rate"], 0.0)

    def test_request_coherence_detects_forward_handoffs(self):
        coh = self.metrics["request_coherence"]
        # research -> offer -> outreach: two forward transitions.
        self.assertEqual(coh["forward_handoffs"], 2)
        self.assertEqual(coh["backward_steps"], 0)
        self.assertEqual(coh["forward_ratio"], 1.0)
        stages = [s["stage"] for s in coh["sequence"]]
        self.assertEqual(stages, ["research", "offer", "outreach"])

    def test_contribution_per_agent(self):
        con = self.metrics["contribution"]
        self.assertEqual(con["team_points"], 10)
        self.assertEqual(con["team_revenue_cents"], 5000)
        milo = con["per_actor"]["Milo Chen"]
        self.assertEqual(milo["points"], 8)
        self.assertEqual(milo["revenue_cents"], 5000)
        self.assertEqual(milo["reward_count"], 2)
        self.assertIn("actual_revenue", milo["sources"])

    def test_social_network_edges(self):
        net = self.metrics["social_network"]
        edges = {(e["source"], e["target"]): e["weight"] for e in net["edges"]}
        # Milo<->Iris talked at step 1 (via conversation + chat) -> one edge.
        self.assertIn(("Iris Morgan", "Milo Chen"), edges)
        self.assertGreaterEqual(edges[("Iris Morgan", "Milo Chen")], 1)
        # Theo never talked -> no edges touching Theo.
        self.assertNotIn("Theo Grant", net["degree_centrality"])
        self.assertEqual(net["group_size_max"], 2)

    def test_activity_and_memory_growth(self):
        act = self.metrics["activity"]
        self.assertEqual(act["simulation_steps"], 3)
        self.assertEqual(act["active_steps"], 2)
        self.assertEqual(act["total_memory_nodes"], 2)
        self.assertEqual(act["event_type_counts"]["town_request_submitted"], 3)

    def test_gini_helper(self):
        self.assertEqual(metrics_mod.gini([5, 5, 5]), 0.0)
        self.assertGreater(metrics_mod.gini([0, 0, 10]), 0.0)

    def test_identity_drift_metric(self):
        drift = self.metrics["identity_drift"]
        self.assertEqual(drift["actors_with_checkpoints"], 1)
        milo = drift["per_actor"]["Milo Chen"]
        self.assertEqual(milo["checkpoint_count"], 2)
        # Latest checkpoint wins for "latest_drift"; max/mean over both.
        self.assertEqual(milo["latest_drift"], 0.5)
        self.assertEqual(milo["max_drift"], 0.5)
        self.assertEqual(milo["mean_drift"], 0.35)
        self.assertEqual(milo["latest_note"], "drifting toward sales")
        # Mean-latest summarized across personas with checkpoints.
        self.assertEqual(drift["mean_latest_drift"], 0.5)

    def test_day_traces_and_judge_parse(self):
        traces = build_day_traces(self.rundata)
        self.assertIn("Milo Chen", traces)
        self.assertTrue(traces["Milo Chen"]["descriptions"])
        self.assertTrue(any("Hi Iris" in c for c in traces["Milo Chen"]["chat_lines"]))
        parsed = parse_judge_response(
            '{"goal_completion": {"score": 12, "justification": "x"},'
            ' "believability": {"score": 0, "justification": "y"}}'
        )
        # Scores clamp into [1, 10].
        self.assertEqual(parsed["goal_completion"]["score"], 10)
        self.assertEqual(parsed["believability"]["score"], 1)

    def test_judge_graceful_skip_without_network(self):
        # max_personas=0 path / empty prompts -> graceful skip (no LLM call).
        result = run_judge(self.rundata, max_personas=0)
        self.assertEqual(result["status"], "skipped")
        self.assertIn("reason", result)


class ReplayDiffTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.run_a = build_synthetic_run(self.root / "a")
        # Build a second run identical except one persona diverges at step 2.
        self.run_b = build_synthetic_run(self.root / "b")
        b_step2 = self.run_b / "movement" / "2.json"
        packet = json.loads(b_step2.read_text(encoding="utf-8"))
        packet["persona"]["Theo Grant"]["movement"] = [10, 10]
        b_step2.write_text(json.dumps(packet), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_identical_traces(self):
        trace = replay_diff.load_trace(str(self.run_a))
        summary = replay_diff.diff_traces(trace, trace)
        self.assertTrue(summary["identical"])
        self.assertEqual(summary["position_similarity"], 1.0)

    def test_first_divergence_detected(self):
        ta = replay_diff.load_trace(str(self.run_a))
        tb = replay_diff.load_trace(str(self.run_b))
        summary = replay_diff.diff_traces(ta, tb)
        self.assertFalse(summary["identical"])
        self.assertEqual(summary["first_divergence"]["step"], 2)
        diff = summary["first_divergence"]["diffs"][0]
        self.assertEqual(diff["persona"], "Theo Grant")
        self.assertEqual(diff["a"], (9, 9))
        self.assertEqual(diff["b"], (10, 10))


if __name__ == "__main__":
    unittest.main()
