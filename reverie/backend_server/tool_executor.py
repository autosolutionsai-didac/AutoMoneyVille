"""Tool execution layer — Stage 1 toward real-world actions.

When a Town Center request is approved (or auto-completed for safe tools), it is
dispatched here to a handler that ACTUALLY does work. The result feeds back into
the requesting persona's memory and the ledger so agents ground decisions in real
outcomes instead of narrating fictional ones.

SAFETY MODEL (this stage):
  - Read-only research (`web_research`, `market_analysis`) executes for real IFF a
    search backend is configured (CLAUDEVILLE_SEARCH_BACKEND + a wired client);
    otherwise it returns an HONEST stub ("no live search configured") — it never
    fabricates findings.
  - Outbound / spend tools (`send_email`, `post_content`, `spend_money`,
    `account_change`, `purchase`, `contact_person`) NEVER really execute here.
    They produce a reviewable DRY-RUN artifact only. Real execution is gated to a
    later stage behind explicit env flags + allow-lists + per-action human confirm.
  - All tool output is sanitized (LLM-1) before it can re-enter any prompt.

The module is dependency-free and side-effect-free except the optional, explicitly
configured search client; handlers never raise (errors become a failed ToolResult).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    from text_safety import sanitize_external as _sanitize_external
except ImportError:  # package-path import context
    from reverie.backend_server.text_safety import (
        sanitize_external as _sanitize_external,
    )

# Tools that must never really execute in this stage — always dry-run.
OUTBOUND_TOOLS = (
    "send_email",
    "post_content",
    "spend_money",
    "account_change",
    "purchase",
    "contact_person",
    "scrape_at_scale",
)
RESEARCH_TOOLS = ("web_research", "market_analysis")
_SUMMARY_MAX = 240


@dataclass
class ToolResult:
    """Outcome of executing a tool for an approved/auto-completed request."""

    ok: bool
    tool: str
    summary: str  # short, sanitized, persona-facing one-liner
    detail: str = ""  # longer sanitized text (e.g., research findings)
    evidence: dict[str, Any] = field(default_factory=dict)  # structured artifact
    dry_run: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "summary": self.summary,
            "detail": self.detail,
            "evidence": self.evidence,
            "dry_run": self.dry_run,
            "error": self.error,
        }

    def memory_line(self) -> str:
        """Persona-facing observation text to store in associative memory."""
        return self.summary


# --- search backend (pluggable; real only when explicitly configured) ----------

def _run_search(query: str) -> list[dict[str, str]]:
    """Return search hits as [{title,url,snippet}], or [] if no backend is wired.

    Real providers are intentionally NOT hardcoded — set CLAUDEVILLE_SEARCH_BACKEND
    and implement the call for your provider/key here. Kept empty by default so the
    research handler returns an honest 'no live search' stub rather than fiction.
    """
    backend = os.environ.get("CLAUDEVILLE_SEARCH_BACKEND", "").strip().lower()
    if not backend or not query:
        return []
    # Placeholder for a wired provider (e.g., Exa/SerpAPI/Bing). Until one is
    # implemented for `backend`, return [] so the caller emits the honest stub.
    return []


def _format_results(results: list[dict[str, str]]) -> str:
    lines = []
    for r in results[:5]:
        title = str(r.get("title", "")).strip()
        url = str(r.get("url", "")).strip()
        snippet = str(r.get("snippet", "")).strip()
        lines.append(f"- {title} ({url}): {snippet}")
    return "\n".join(lines)


# --- handlers ------------------------------------------------------------------

def _handle_research(tool: str, payload: dict[str, Any], ctx: dict[str, Any]) -> ToolResult:
    query = str(payload.get("query") or payload.get("title") or "").strip()
    results = _run_search(query)
    if results:
        detail = _sanitize_external(_format_results(results))
        return ToolResult(
            ok=True,
            tool=tool,
            summary=_sanitize_external(f"{tool}: {len(results)} sources on '{query}'")[:_SUMMARY_MAX],
            detail=detail,
            evidence={"query": query, "sources": results[:5], "live": True},
        )
    return ToolResult(
        ok=True,
        tool=tool,
        summary=_sanitize_external(
            f"[no live search configured] {tool} request logged: '{query}'"
        )[:_SUMMARY_MAX],
        evidence={"query": query, "stub": True, "live": False},
    )


def _handle_outbound_dry_run(
    tool: str, payload: dict[str, Any], ctx: dict[str, Any]
) -> ToolResult:
    # Build a reviewable artifact WITHOUT performing the action.
    target = payload.get("recipient") or payload.get("target") or payload.get("vendor")
    preview = payload.get("preview") or payload.get("body") or payload.get("text") or ""
    amount = payload.get("amount") or payload.get("amount_cents")
    bits = [f"DRY-RUN {tool}: would NOT-send (no real action this stage)"]
    if target:
        bits.append(f"to={target}")
    if amount is not None:
        bits.append(f"amount={amount}")
    summary = _sanitize_external(" | ".join(bits))[:_SUMMARY_MAX]
    return ToolResult(
        ok=True,
        tool=tool,
        summary=summary,
        detail=_sanitize_external(str(preview)),
        evidence={
            "dry_run": True,
            "target": target,
            "amount": amount,
            "preview": _sanitize_external(str(preview)),
        },
        dry_run=True,
    )


_HANDLERS: dict[str, Callable[[str, dict, dict], ToolResult]] = {}
for _t in RESEARCH_TOOLS:
    _HANDLERS[_t] = _handle_research
for _t in OUTBOUND_TOOLS:
    _HANDLERS[_t] = _handle_outbound_dry_run


def execute(tool: str | None, payload: dict[str, Any] | None, *, persona_name: str | None = None) -> ToolResult:
    """Dispatch a tool to its handler. Never raises — failures become a ToolResult.

    Unknown tools (e.g. internal_planning / drafting that need no real action) are
    recorded as a benign no-op so the request lifecycle is unaffected.
    """
    name = (tool or "").strip()
    payload = payload or {}
    ctx = {"persona_name": persona_name}
    handler = _HANDLERS.get(name)
    if handler is None:
        return ToolResult(
            ok=True,
            tool=name or "unknown",
            summary=_sanitize_external(
                f"{name or 'tool'}: completed (no external executor; recorded only)"
            )[:_SUMMARY_MAX],
            evidence={"executor": None},
        )
    try:
        return handler(name, payload, ctx)
    except Exception as e:  # handlers should not raise, but never break a step
        return ToolResult(
            ok=False,
            tool=name,
            summary=_sanitize_external(f"{name}: execution failed")[:_SUMMARY_MAX],
            error=str(e),
        )
