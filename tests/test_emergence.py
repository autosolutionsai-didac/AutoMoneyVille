"""Tests for the Phase 6d emergence analyzer (tools/eval/emergence.py).

Builds a synthetic run that exhibits each phenomenon the analyzer measures and
asserts they are detected over time:
- specialization trajectory rises as agents accumulate same-type requests,
- cooperation is detected from forward pipeline handoffs + reciprocity,
- the social network grows (cumulative edges/density) across steps,
- a convention (shared phrase used by multiple personas) emerges.

Reuses the tempfile + synthetic-run fixture pattern from test_eval_harness.

Run as a standalone unittest module:
    python -m unittest tests.test_emergence
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

from tools.eval import emergence as emergence_mod  # noqa: E402
from tools.eval.run_loader import load_run  # noqa: E402


def _write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _packet(step, positions, conversations=None, chats=None):
    persona = {}
    for name, pos in positions.items():
        persona[name] = {
            "movement": list(pos),
            "pronunciatio": "X",
            "description": f"{name} at step {step}",
            "chat": (chats or {}).get(name),
            "had_action": True,
        }
    return {
        "persona": persona,
        "meta": {
            "step": step,
            "had_new_action": True,
            "conversations": conversations or {},
        },
    }


def build_emergent_run(root: Path) -> Path:
    """Create a run that exhibits all four emergent phenomena over time."""
    run = root / "emergent_run"

    names = ["Milo Chen", "Iris Morgan", "Theo Grant"]
    _write_json(
        run / "reverie" / "meta.json",
        {
            "maze_name": "claudeville",
            "persona_names": names,
            "step": 4,
            "scenario_id": "startup_team_v1",
            "scenario_name": "Startup Team V1",
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

    # Requests: a research -> offer -> outreach pipeline, then a reciprocal
    # offer -> research handoff so a reciprocal pair (Milo+Iris) exists. Each
    # actor repeats its OWN type so specialization concentration stays high.
    requests = [
        {"id": "r1", "state": "proposed", "actor": "Milo Chen", "type": "research",
         "title": "Market research brief", "created_at": "2026-01-01T00:00"},
        {"id": "r2", "state": "proposed", "actor": "Iris Morgan", "type": "offer",
         "title": "Offer package design", "created_at": "2026-01-01T00:01"},
        {"id": "r3", "state": "proposed", "actor": "Theo Grant", "type": "outreach",
         "title": "Cold email outreach", "created_at": "2026-01-01T00:02"},
        {"id": "r4", "state": "proposed", "actor": "Milo Chen", "type": "research",
         "title": "More market research evidence", "created_at": "2026-01-01T00:03"},
        {"id": "r5", "state": "proposed", "actor": "Iris Morgan", "type": "offer",
         "title": "Offer guarantee redesign", "created_at": "2026-01-01T00:04"},
    ]
    _write_jsonl(run / "town_center" / "requests.jsonl", requests)

    rewards = [
        {"id": "w1", "actor": "Milo Chen", "points": 3, "source": "request_approved"},
        {"id": "w2", "actor": "Iris Morgan", "points": 2, "source": "request_approved"},
    ]
    _write_jsonl(run / "town_center" / "rewards.jsonl", rewards)

    # Movement: network grows step by step; a shared phrase "roadmap" recurs
    # across multiple personas (an emergent convention).
    _write_json(run / "movement" / "0.json",
                _packet(0, {"Milo Chen": (1, 1), "Iris Morgan": (5, 5), "Theo Grant": (9, 9)}))
    _write_json(
        run / "movement" / "1.json",
        _packet(
            1,
            {"Milo Chen": (3, 3), "Iris Morgan": (3, 4), "Theo Grant": (9, 9)},
            conversations={"g1": {"participants": ["Milo Chen", "Iris Morgan"]}},
            chats={
                "Milo Chen": [["Milo Chen", "Lets align the roadmap together"]],
                "Iris Morgan": [["Iris Morgan", "Agreed, the roadmap matters"]],
            },
        ),
    )
    _write_json(
        run / "movement" / "2.json",
        _packet(
            2,
            {"Milo Chen": (3, 3), "Iris Morgan": (3, 4), "Theo Grant": (3, 5)},
            conversations={
                "g2": {"participants": ["Milo Chen", "Iris Morgan", "Theo Grant"]}
            },
            chats={
                "Theo Grant": [["Theo Grant", "The roadmap looks solid to me"]],
            },
        ),
    )
    return run


class EmergenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.run_dir = build_emergent_run(Path(cls._tmp.name))
        cls.rundata = load_run(str(cls.run_dir))
        cls.payload = emergence_mod.compute_emergence(cls.rundata)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_payload_shape(self):
        for key in (
            "specialization_trajectory",
            "cooperation",
            "network_growth",
            "conventions",
        ):
            self.assertIn(key, self.payload)
        self.assertEqual(self.payload["scenario"]["persona_count"], 3)

    def test_specialization_trajectory_present(self):
        sp = self.payload["specialization_trajectory"]
        # One series point per submitted request (5).
        self.assertEqual(len(sp["series"]), 5)
        # Every actor repeats its own type -> all stay fully concentrated.
        self.assertEqual(sp["trend"]["last"], 1.0)
        self.assertIn("Milo Chen", sp["final_specialists"])
        self.assertIn("Iris Morgan", sp["final_specialists"])

    def test_cooperation_detects_handoffs_and_reciprocity(self):
        co = self.payload["cooperation"]
        self.assertGreaterEqual(co["forward_handoffs"], 2)
        self.assertTrue(co["cooperating"])
        # Directed pipeline handoffs: Milo (research) -> Iris (offer) etc.
        self.assertIn("Milo Chen->Iris Morgan", co["directed_handoff_pairs"])
        # Milo and Iris actually conversed (mutual, bidirectional cooperation).
        self.assertIn("Iris Morgan+Milo Chen", co["mutual_conversation_pairs"])
        self.assertGreaterEqual(co["mutual_conversation_count"], 1)
        # Both earned reward from the same source -> shared reward source.
        self.assertIn("request_approved", co["shared_reward_sources"])

    def test_network_grows_over_time(self):
        ng = self.payload["network_growth"]
        # Cumulative edge count is non-decreasing across steps.
        edges = ng["edge_series"]
        self.assertEqual(edges, sorted(edges))
        # Step 0: no edges; by the last step the triad is connected (3 edges).
        self.assertEqual(edges[0], 0)
        self.assertEqual(ng["final_edges"], 3)
        self.assertEqual(ng["final_nodes"], 3)
        self.assertTrue(ng["edge_trend"]["rising"])

    def test_convention_emerges(self):
        cv = self.payload["conventions"]
        self.assertTrue(cv["convention_emerged"])
        phrases = {p["phrase"]: p for p in cv["shared_phrases"]}
        self.assertIn("roadmap", phrases)
        # "roadmap" used by all three personas.
        self.assertEqual(phrases["roadmap"]["speakers"], 3)

    def test_trend_helper(self):
        self.assertTrue(emergence_mod._trend([1, 2, 3, 4, 5, 6])["rising"])
        self.assertFalse(emergence_mod._trend([5, 5, 5])["rising"])
        self.assertEqual(emergence_mod._trend([])["points"], 0)

    def test_analyze_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = build_emergent_run(Path(tmp))
            payload = emergence_mod.analyze(str(run_dir))
            outputs = payload["_outputs"]
            self.assertTrue(Path(outputs["emergence_json"]).exists())
            self.assertTrue(Path(outputs["emergence_md"]).exists())
            md = Path(outputs["emergence_md"]).read_text(encoding="utf-8")
            self.assertIn("Emergence report", md)
            self.assertIn("Convention Emergence", md)

    def test_render_markdown_smoke(self):
        md = emergence_mod.render_markdown(self.payload)
        self.assertIn("Specialization Trajectory", md)
        self.assertIn("Cooperation", md)
        self.assertIn("Social-Network Formation", md)


class MalformedRunToleranceTests(unittest.TestCase):
    """Phase-6 verify: the analyzers must not crash on malformed/non-dict run
    data (e.g. {"persona": {"X": null}} or {"meta": {"conversations": "boom"}}).
    A harness that chews arbitrary on-disk runs has to be defensive."""

    def _malformed_run(self, root: Path) -> Path:
        run = root / "malformed_run"
        _write_json(
            run / "reverie" / "meta.json",
            {"maze_name": "claudeville", "persona_names": ["X"], "step": 2,
             "scenario_id": "startup_team_v1", "scenario_name": "S"},
        )
        # persona value is None; conversations is a string (not a dict).
        _write_json(run / "movement" / "0.json",
                    {"persona": {"X": None}, "meta": {"step": 0, "conversations": "boom"}})
        # conversations holds a non-dict group; chat is a non-list.
        _write_json(run / "movement" / "1.json",
                    {"persona": {"X": {"chat": "nope"}},
                     "meta": {"step": 1, "conversations": {"g": ["not-a-dict"]}}})
        return run

    def test_emergence_and_metrics_survive_malformed_movement(self):
        from tools.eval import metrics as metrics_mod

        with tempfile.TemporaryDirectory() as tmp:
            run = self._malformed_run(Path(tmp))
            rundata = load_run(str(run))
            # Neither the emergence report nor the social-network metric should
            # raise on this garbage; they should degrade to empty/zero results.
            payload = emergence_mod.compute_emergence(rundata)
            self.assertIn("network_growth", payload)
            net = metrics_mod.social_network(rundata)
            self.assertIsInstance(net, dict)
            self.assertFalse(net.get("edges"))  # garbage -> no edges, no crash


if __name__ == "__main__":
    unittest.main()
