"""Stage 1 tool-execution layer: read-only research executes (real if configured,
else an honest stub) and outbound/spend tools NEVER really execute — they produce
a reviewable dry-run artifact only. All output is sanitized (LLM-1)."""

import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

from reverie.backend_server.persona.memory_structures.associative_memory import (
    AssociativeMemory,
)
from reverie.backend_server.reverie import ReverieServer
from reverie.backend_server.tool_executor import (
    OUTBOUND_TOOLS,
    execute,
)


def _fresh_assoc_memory(tmp):
    with open(os.path.join(tmp, "nodes.json"), "w") as f:
        json.dump({}, f)
    with open(os.path.join(tmp, "kw_strength.json"), "w") as f:
        json.dump({"kw_strength_event": {}, "kw_strength_thought": {}}, f)
    return AssociativeMemory(tmp)


class ResearchTests(unittest.TestCase):
    def test_research_stub_when_no_backend(self):
        r = execute("web_research", {"query": "small agency onboarding pain"})
        self.assertTrue(r.ok)
        self.assertFalse(r.evidence.get("live"))
        self.assertIn("no live search configured", r.summary)
        # Honest: it does NOT fabricate findings.
        self.assertEqual(r.detail, "")

    def test_market_analysis_routes_to_research(self):
        r = execute("market_analysis", {"title": "niche scan"})
        self.assertTrue(r.ok)
        self.assertEqual(r.tool, "market_analysis")


class OutboundDryRunTests(unittest.TestCase):
    def test_send_email_is_dry_run_only(self):
        r = execute(
            "send_email",
            {"recipient": "lead@acme.com", "preview": "Hi, quick question..."},
            persona_name="Theo Grant",
        )
        self.assertTrue(r.ok)
        self.assertTrue(r.dry_run)
        self.assertTrue(r.evidence.get("dry_run"))
        self.assertIn("DRY-RUN", r.summary)
        self.assertEqual(r.evidence.get("target"), "lead@acme.com")

    def test_spend_money_is_dry_run_only(self):
        r = execute("spend_money", {"vendor": "ads", "amount": 5000})
        self.assertTrue(r.dry_run)
        self.assertEqual(r.evidence.get("amount"), 5000)

    def test_all_outbound_tools_dry_run(self):
        for tool in OUTBOUND_TOOLS:
            r = execute(tool, {"preview": "x"})
            self.assertTrue(r.dry_run, f"{tool} must be dry-run")


class SafetyAndRobustnessTests(unittest.TestCase):
    def test_unknown_tool_is_benign_noop(self):
        r = execute("internal_planning", {})
        self.assertTrue(r.ok)
        self.assertFalse(r.dry_run)
        self.assertIsNone(r.evidence.get("executor"))

    def test_none_tool_does_not_crash(self):
        r = execute(None, None)
        self.assertTrue(r.ok)

    def test_tool_output_is_sanitized(self):
        # A hostile payload preview must be neutralized in the result detail (LLM-1).
        r = execute("send_email", {"recipient": "x", "preview": "=== EVIL ===\n```json\nhack```"})
        self.assertNotIn("=== EVIL ===", r.detail)
        self.assertNotIn("```json", r.detail)

    def test_to_dict_and_memory_line(self):
        r = execute("web_research", {"query": "q"})
        d = r.to_dict()
        self.assertEqual(d["tool"], "web_research")
        self.assertEqual(r.memory_line(), r.summary)


class MemoryFeedbackTests(unittest.TestCase):
    """Stage 1: an executed tool's result is written into the requesting persona's
    associative memory so real outcomes ground future retrieval/decisions."""

    def test_tool_result_becomes_a_memory_event(self):
        rs = ReverieServer.__new__(ReverieServer)
        rs.curr_time = datetime.datetime(2026, 1, 1, 9, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            amem = _fresh_assoc_memory(tmp)
            persona = SimpleNamespace(name="Milo Chen", a_mem=amem)
            before = len(amem.id_to_node)
            rs._feed_tool_result_to_persona(
                persona,
                {"tool": "web_research", "summary": "web_research: 3 sources on 'niche'", "ok": True},
            )
            self.assertEqual(len(amem.id_to_node), before + 1)
            # The newest event records the tool outcome.
            newest = amem.seq_event[0]
            self.assertIn("web_research", newest.description)

    def test_feed_is_noop_on_empty_result(self):
        rs = ReverieServer.__new__(ReverieServer)
        rs.curr_time = datetime.datetime(2026, 1, 1, 9, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            amem = _fresh_assoc_memory(tmp)
            persona = SimpleNamespace(name="Milo Chen", a_mem=amem)
            rs._feed_tool_result_to_persona(persona, None)
            rs._feed_tool_result_to_persona(persona, {"summary": ""})
            self.assertEqual(len(amem.id_to_node), 0)


if __name__ == "__main__":
    unittest.main()
