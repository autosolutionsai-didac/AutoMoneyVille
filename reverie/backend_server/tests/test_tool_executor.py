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
from unittest import mock

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

    def test_memory_line_includes_detail_for_research(self):
        """P2-A1: memory_line for research now carries compact content excerpt."""
        from tool_executor import ToolResult
        r = ToolResult(
            ok=True,
            tool="web_research",
            summary="web_research: 2 sources on 'x'",
            detail="Title A (u1): snippet one. Title B (u2): snippet two here.",
        )
        ml = r.memory_line()
        self.assertIn("2 sources on 'x'", ml)
        self.assertIn("Title A", ml)
        self.assertIn("snippet one", ml)
        # Still bounded
        self.assertLess(len(ml), 300)


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

    def test_tool_result_memory_includes_research_detail(self):
        """P2-A1: research detail (the actual content) is folded into the stored
        memory description so keyword retrieval and prompts see real findings."""
        rs = ReverieServer.__new__(ReverieServer)
        rs.curr_time = datetime.datetime(2026, 1, 1, 9, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            amem = _fresh_assoc_memory(tmp)
            persona = SimpleNamespace(name="Felix Reed", a_mem=amem)
            rs._feed_tool_result_to_persona(
                persona,
                {
                    "tool": "web_research",
                    "summary": "web_research: 2 sources on 'pricing'",
                    "detail": "Acme Pricing Guide https://ex.com : foo bar. BetaCo https://b.com : baz.",
                    "ok": True,
                },
            )
            newest = amem.seq_event[0]
            self.assertIn("pricing", newest.description)
            self.assertIn("Acme Pricing", newest.description)  # excerpt of detail is present
            self.assertIn("https://b.com", newest.description)

    def test_feed_is_noop_on_empty_result(self):
        rs = ReverieServer.__new__(ReverieServer)
        rs.curr_time = datetime.datetime(2026, 1, 1, 9, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            amem = _fresh_assoc_memory(tmp)
            persona = SimpleNamespace(name="Milo Chen", a_mem=amem)
            rs._feed_tool_result_to_persona(persona, None)
            rs._feed_tool_result_to_persona(persona, {"summary": ""})
            self.assertEqual(len(amem.id_to_node), 0)


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self._payload


_FIRECRAWL_PAYLOAD = {
    "success": True,
    "data": [
        {
            "title": "Agency client onboarding pain",
            "url": "https://example.com/a",
            "description": "Small agencies struggle with manual client onboarding workflows...",
        },
        {
            "title": "Done-for-you onboarding builds",
            "url": "https://example.com/b",
            "description": "Fast setup with a retainer upsell path.",
        },
    ],
}

_EXA_PAYLOAD = {
    "results": [
        {"title": "Exa hit", "url": "https://example.com/e", "highlights": ["niche signal"]},
    ]
}


class SearchProviderTests(unittest.TestCase):
    """web_research executes REAL search via the configured provider (Firecrawl is
    the default), else an honest stub. Mocked HTTP — no live key required."""

    def test_firecrawl_live_results_mapped_and_tagged(self):
        with mock.patch.dict(
            os.environ,
            {"CLAUDEVILLE_SEARCH_BACKEND": "firecrawl", "CLAUDEVILLE_SEARCH_API_KEY": "fc-x"},
            clear=False,
        ), mock.patch("requests.post", return_value=_FakeResp(_FIRECRAWL_PAYLOAD)):
            r = execute("web_research", {"query": "agency onboarding"})
        self.assertTrue(r.ok)
        self.assertTrue(r.evidence.get("live"))
        self.assertEqual(len(r.evidence.get("sources", [])), 2)
        self.assertIn("onboarding", r.detail.lower())

    def test_firecrawl_is_default_when_only_key_set(self):
        # No backend named -> defaults to firecrawl when a key is present.
        with mock.patch.dict(
            os.environ,
            {"CLAUDEVILLE_SEARCH_BACKEND": "", "CLAUDEVILLE_SEARCH_API_KEY": "fc-x"},
            clear=False,
        ), mock.patch("requests.post", return_value=_FakeResp(_FIRECRAWL_PAYLOAD)):
            r = execute("web_research", {"query": "agency onboarding"})
        self.assertTrue(r.evidence.get("live"))

    def test_exa_still_selectable_via_env(self):
        with mock.patch.dict(
            os.environ,
            {"CLAUDEVILLE_SEARCH_BACKEND": "exa", "CLAUDEVILLE_SEARCH_API_KEY": "k"},
            clear=False,
        ), mock.patch("requests.post", return_value=_FakeResp(_EXA_PAYLOAD)):
            r = execute("web_research", {"query": "x"})
        self.assertTrue(r.evidence.get("live"))
        self.assertEqual(len(r.evidence.get("sources", [])), 1)

    def test_http_error_falls_back_to_honest_stub(self):
        with mock.patch.dict(
            os.environ,
            {"CLAUDEVILLE_SEARCH_BACKEND": "firecrawl", "CLAUDEVILLE_SEARCH_API_KEY": "fc-x"},
            clear=False,
        ), mock.patch("requests.post", side_effect=RuntimeError("network down")):
            r = execute("web_research", {"query": "x"})
        self.assertTrue(r.ok)  # never raises
        self.assertFalse(r.evidence.get("live"))
        self.assertIn("no live search", r.summary)

    def test_missing_key_is_stub(self):
        with mock.patch.dict(
            os.environ,
            {"CLAUDEVILLE_SEARCH_BACKEND": "firecrawl", "CLAUDEVILLE_SEARCH_API_KEY": ""},
            clear=False,
        ):
            r = execute("web_research", {"query": "x"})
        self.assertFalse(r.evidence.get("live"))

    def test_unknown_backend_is_stub(self):
        with mock.patch.dict(
            os.environ,
            {"CLAUDEVILLE_SEARCH_BACKEND": "bogus", "CLAUDEVILLE_SEARCH_API_KEY": "k"},
            clear=False,
        ):
            r = execute("web_research", {"query": "x"})
        self.assertFalse(r.evidence.get("live"))


if __name__ == "__main__":
    unittest.main()
