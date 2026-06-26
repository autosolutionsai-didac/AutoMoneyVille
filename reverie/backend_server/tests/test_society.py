"""Phase 6 tests: society scale (6a), persona grounding (6b), world arbiter (6c).

6a SCALE: persona count is a clean knob — the scenario loader + persona factory
  produce N personas for several N (including scaling beyond the base roster),
  and the base generator writes exactly N persona dirs into a temp base.
6b GROUNDING: a generated persona has backstory-grounded identity fields, seeded
  identity_markers, seeded GoalMemory goals, and a valid scratch/relationships/
  goals trio that load via the real memory classes. Generation is deterministic.
6c ARBITER: the deterministic (no-LLM) rubric adjudicates approve/deny/partial
  with reward adjustments; it is OFF by default (TownCenterStore builds no arbiter
  and the legacy path is unchanged); and the LLM path falls back to the rubric
  without a network.

Hard constraint D-002: no embeddings; all of this is heuristic / text only.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Backend modules import siblings by bare name; put backend_server on sys.path
# (matches the other backend tests) and the repo root for tools.mapgen.
_BACKEND = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]
for p in (str(_BACKEND), str(_REPO_ROOT), str(_REPO_ROOT / "tools" / "mapgen")):
    if p not in sys.path:
        sys.path.insert(0, p)

import persona_factory as pf  # noqa: E402

from reverie.backend_server.economy import RequestState  # noqa: E402
from reverie.backend_server.persona.memory_structures.goal_memory import (  # noqa: E402
    GoalMemory,
)
from reverie.backend_server.persona.memory_structures.relationship_memory import (  # noqa: E402
    RelationshipMemory,
)
from reverie.backend_server.scenario_config import load_scenario  # noqa: E402
from reverie.backend_server.town_center import TownCenterStore  # noqa: E402
from reverie.backend_server.world_arbiter import (  # noqa: E402
    ArbiterVerdict,
    WorldArbiter,
    arbiter_enabled,
    build_arbiter,
    parse_arbiter_response,
)


class ScaleSupportTests(unittest.TestCase):
    """6a: persona count is a clean, documented knob."""

    def setUp(self):
        self.scenario = load_scenario("startup_team_v1")

    def test_factory_count_knob_for_several_n(self):
        # Full roster, a smaller subset, and scaling BEYOND the roster.
        full = pf.personas_for(self.scenario, None)
        self.assertEqual(len(full), 10)
        for n in (1, 4, 7, 10):
            self.assertEqual(len(pf.personas_for(self.scenario, n)), n)
        grown = pf.personas_for(self.scenario, 16)
        self.assertEqual(len(grown), 16)
        # Names stay unique even when synthesizing extra personas.
        names = [p["name"] for p in grown]
        self.assertEqual(len(names), len(set(names)))
        # Synthetic personas reuse a real role from the scenario.
        roles = {a["role"] for a in self.scenario["agents"]}
        self.assertIn(grown[12]["role"], roles)

    def test_scenario_loader_and_factory_agree_on_roster(self):
        full = pf.personas_for(self.scenario, None)
        self.assertEqual(
            [p["name"] for p in full],
            [a["name"] for a in self.scenario["agents"]],
        )

    def test_generator_writes_n_persona_dirs(self):
        # Drive the real generator but redirect its output into a temp base so
        # the committed claudeville_v1 base is never touched.
        import make_claudeville_base as gen

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dst = Path(tmp) / "claudeville_v1"
            orig_dst = gen.DST
            try:
                gen.DST = tmp_dst
                for n in (3, 6):
                    summary = gen.generate(count=n)
                    self.assertEqual(summary["personas"], n)
                    persona_dirs = [
                        d for d in (tmp_dst / "personas").iterdir() if d.is_dir()
                    ]
                    self.assertEqual(len(persona_dirs), n)
            finally:
                gen.DST = orig_dst


class PersonaGroundingTests(unittest.TestCase):
    """6b: personas are richer + their Phase 3-4 stores are seeded."""

    def setUp(self):
        self.scenario = load_scenario("startup_team_v1")
        self.roster = pf.personas_for(self.scenario, None)

    def test_identity_is_grounded_and_role_specific(self):
        nora = pf.build_scratch_identity(
            "Nora Vale", "strategist", "Keep the team focused."
        )
        # All grounded identity fields present and non-empty.
        for key in ("age", "innate", "learned", "currently", "lifestyle"):
            self.assertTrue(nora[key], f"{key} should be non-empty")
        # Backstory-grounded, not the generic fallback wording.
        self.assertIn("strategist", nora["learned"])
        self.assertIn("Keep the team focused.", nora["learned"])
        self.assertGreaterEqual(len(nora["identity_markers"]), 1)
        # Two different roles produce different innate traits (not generic clones).
        milo = pf.build_scratch_identity("Milo Chen", "market_researcher", "Find niches.")
        self.assertNotEqual(nora["innate"], milo["innate"])

    def test_seeded_goals_load_via_goal_memory(self):
        payload = pf.seed_goals("strategist", "Keep focused.", created_day="2023-02-13")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "goals.json").write_text(json.dumps(payload))
            gm = GoalMemory(tmp)
            active = gm.get_active()
            self.assertGreaterEqual(len(active), 2)
            # One goal anchors on the explicit mission text.
            self.assertTrue(any("Keep focused." in g["text"] for g in active))
            # Prompt block renders (proves records are well-formed).
            self.assertIn("ONGOING GOALS", gm.to_prompt_block())

    def test_seeded_relationships_load_via_relationship_memory(self):
        rels = pf.seed_relationships("Nora Vale", "strategist", self.roster)
        self.assertTrue(rels, "strategist should have seeded acquaintances")
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "relationships.json").write_text(json.dumps(rels))
            rm = RelationshipMemory(tmp)
            self.assertEqual(len(rm.relationships), len(rels))
            # A seeded acquaintance carries a positive affinity + belief.
            any_rec = next(iter(rm.relationships.values()))
            self.assertGreater(any_rec["affinity"], 0)
            self.assertTrue(any_rec["beliefs"])

    def test_generation_is_deterministic(self):
        # No random / no clock: identical inputs -> identical output.
        a = pf.build_scratch_identity("Nora Vale", "strategist", "m")
        b = pf.build_scratch_identity("Nora Vale", "strategist", "m")
        self.assertEqual(a, b)
        g1 = pf.seed_goals("analyst", "score", "2023-02-13")
        g2 = pf.seed_goals("analyst", "score", "2023-02-13")
        self.assertEqual(g1, g2)


class WorldArbiterDeterministicTests(unittest.TestCase):
    """6c: deterministic adjudication rubric (the unit-testable path)."""

    def setUp(self):
        policy = load_scenario("startup_team_v1")["real_world_policy"]
        self.arb = WorldArbiter(policy=policy)

    def test_approves_well_grounded_request(self):
        req = {
            "title": "Send approved follow-up to a warm lead",
            "rationale": "Buyer replied with interest; we have consent and evidence.",
            "type": "external_action",
            "payload": {"tool": "send_email"},
        }
        v = self.arb.adjudicate(req, risk_level="high")
        self.assertEqual(v.verdict, "approve")
        self.assertGreater(v.reward_adjustment, 0)
        self.assertEqual(v.source, "rubric")

    def test_denies_forbidden_behavior(self):
        req = {
            "title": "Mass spam cold blast to a purchased list",
            "rationale": "Send unsolicited bulk email to a scraped list.",
            "type": "external_action",
            "payload": {"tool": "send_email"},
        }
        v = self.arb.adjudicate(req, risk_level="high")
        self.assertEqual(v.verdict, "deny")
        self.assertLessEqual(v.reward_adjustment, 0)

    def test_partial_for_underjustified_request(self):
        req = {
            "title": "Try something",
            "rationale": "Not sure yet.",
            "type": "tool",
            "payload": {},
        }
        v = self.arb.adjudicate(req, risk_level="low")
        self.assertEqual(v.verdict, "partial")
        # Low-risk reward band caps the adjustment at 3.
        self.assertLessEqual(v.reward_adjustment, 3)

    def test_reward_is_clamped_to_risk_band(self):
        req = {
            "title": "Approved validated research draft with evidence proposal reply",
            "rationale": "consent opt-in warm lead follow-up evidence",
            "type": "tool",
            "payload": {},
        }
        v = self.arb.adjudicate(req, risk_level="low")
        # Many support cues, but the low-risk band ceiling is 3.
        self.assertLessEqual(v.reward_adjustment, 3)

    def test_determinism(self):
        req = {"title": "Draft a proposal with evidence", "rationale": "x", "type": "tool"}
        self.assertEqual(
            self.arb.adjudicate(req).to_dict(), self.arb.adjudicate(req).to_dict()
        )

    def test_parse_arbiter_response(self):
        parsed = parse_arbiter_response(
            'noise {"verdict": "approve", "reward_adjustment": 4, '
            '"rationale": "ok"} trailing'
        )
        self.assertEqual(parsed["verdict"], "approve")
        self.assertEqual(parsed["reward_adjustment"], 4)
        # Bad / missing verdict -> None so the caller can fall back.
        self.assertIsNone(parse_arbiter_response("no json here"))
        self.assertIsNone(parse_arbiter_response('{"verdict": "maybe"}'))

    def test_llm_path_falls_back_to_rubric_without_sdk(self):
        # No SDK / no network -> deterministic verdict tagged as a fallback.
        req = {"title": "Draft a proposal with evidence", "rationale": "x", "type": "tool"}
        v = self.arb.adjudicate_llm(req)
        self.assertIsInstance(v, ArbiterVerdict)
        self.assertIn(v.source, ("llm", "llm_fallback_rubric"))
        self.assertIn(v.verdict, ("approve", "deny", "partial"))


class ArbiterOffByDefaultTests(unittest.TestCase):
    """6c: the arbiter is OFF by default — no behavior change to the town center."""

    def test_build_arbiter_off_without_env_flag(self):
        # No env flag set in the default test environment.
        self.assertFalse(arbiter_enabled())
        self.assertIsNone(build_arbiter({"forbidden_behaviors": ["spam"]}))
        self.assertIsNotNone(
            build_arbiter({"forbidden_behaviors": ["spam"]}, force=True)
        )

    def test_town_center_builds_no_arbiter_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            self.assertIsNone(store.arbiter)
            # adjudicate_request is a no-op (returns None) with the arbiter off.
            req = store.submit_request(
                actor="Felix Reed",
                request_type="tool",
                title="Request outbound email approval",
                rationale="Need approval.",
                payload={"tool": "send_email"},
            )
            self.assertIsNone(store.adjudicate_request(req["id"]))

    def test_legacy_reward_path_unchanged_with_arbiter_off(self):
        # With the arbiter OFF, transitions follow the normal reward path: +1
        # approved, +3 completed (effort points). Revenue is NOT self-reported
        # (Stage 1 de-fiction) — it stays 0 until human-confirmed delivery.
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(Path(tmp), scenario_id="startup_team_v1")
            req = store.submit_request(
                actor="Felix Reed",
                request_type="external_action",
                title="Send signed proposal",
                rationale="Client asked for it.",
                payload={"tool": "send_email", "expected_payoff": "$50"},
            )
            store.transition_request(
                req["id"], RequestState.APPROVED, reviewer="human", note="ok"
            )
            store.transition_request(
                req["id"], RequestState.COMPLETED, reviewer="human", note="sent"
            )
            score = store.snapshot()["team_score"]
            self.assertEqual(score["points"], 4)
            self.assertEqual(score["revenue_cents"], 0)

    def test_explicit_arbiter_adjudicates_and_adjusts_reward(self):
        # When a caller explicitly opts in, adjudicate_request applies a reward.
        with tempfile.TemporaryDirectory() as tmp:
            store = TownCenterStore(
                Path(tmp),
                scenario_id="startup_team_v1",
                arbiter=build_arbiter(
                    load_scenario("startup_team_v1")["real_world_policy"], force=True
                ),
            )
            self.assertIsNotNone(store.arbiter)
            req = store.submit_request(
                actor="Theo Grant",
                request_type="external_action",
                title="Send approved follow-up to a warm lead with consent",
                rationale="Buyer replied; we have evidence and consent.",
                payload={"tool": "send_email"},
            )
            verdict = store.adjudicate_request(req["id"])
            self.assertIsNotNone(verdict)
            self.assertEqual(verdict["verdict"], "approve")
            # The reward adjustment was written to the ledger.
            contributions = {
                r["actor"]: r for r in store.rewards.read_all()
            }
            self.assertIn("Theo Grant", contributions)
            # Re-adjudicating the same verdict does not double-award.
            store.adjudicate_request(req["id"])
            arbiter_rewards = [
                r for r in store.rewards.read_all()
                if str(r.get("source", "")).startswith("arbiter_")
            ]
            self.assertEqual(len(arbiter_rewards), 1)


if __name__ == "__main__":
    unittest.main()
