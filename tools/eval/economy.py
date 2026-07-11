"""Economy analyzer — measures what the society's REQUEST ECONOMY actually did
in a finished run, honestly separating agent-claimed value from confirmed value.

Where ``emergence.py`` measures social phenomena, this module measures the
business pipeline the money direction depends on:

1. funnel: request counts by final state (proposed -> ... -> completed) and how
   many died waiting for human approval — the throughput of the economy.
2. tool_mix: which tools agents ask for (send_email vs web_research ...), their
   risk labels and request types.
3. actor_economy: per-actor submissions + reward-ledger contribution.
4. claimed_vs_real: the sum agents SAY their work is worth (`expected_payoff`,
   parsed like town_center._payoff_cents) vs. revenue actually confirmed by a
   human via record_delivery (`source == "revenue_confirmed"`). These are never
   conflated: claimed is fiction until a human records evidence.
5. pending_queue: every request still awaiting review, with its draft preview —
   the exact backlog a transaction console must let a human clear.

Pure + deterministic (no LLM, no embeddings — D-002). Builds on ``run_loader``
and reuses ``metrics.contribution``. Output: JSON + Markdown, mirroring
emergence.py.

Usage:
    python -m tools.eval.economy <sim_code>
    python tools/eval/economy.py latest:claudeville_v1
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.eval import metrics as metrics_mod
    from tools.eval.run_loader import RunData, load_run
else:
    from . import metrics as metrics_mod
    from .run_loader import RunData, load_run

# States a request can end in (mirrors economy.RequestState values; kept local so
# this analyzer stays importable without the backend package).
_STATES = ("proposed", "under_review", "approved", "rejected", "completed", "failed")
_PENDING_STATES = {"proposed", "under_review"}
_PREVIEW_MAX = 200


def _claimed_cents(payload: dict[str, Any]) -> int:
    """Parse the agent-CLAIMED payoff (dollars -> cents). Same semantics as
    town_center._payoff_cents; duplicated so tools/eval stays backend-free."""
    val = payload.get("expected_payoff", payload.get("payoff"))
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return max(0, int(round(float(val) * 100)))
    match = re.search(r"(\d+(?:\.\d+)?)", str(val).replace(",", ""))
    return int(round(float(match.group(1)) * 100)) if match else 0


def _request_tool(row: dict[str, Any]) -> str:
    payload = row.get("payload") or {}
    return str(payload.get("tool") or payload.get("requested_tool") or "none")


def _current_view(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold the requests.jsonl event stream (submit rows carry a title;
    transition rows don't) into one row per request with its final state.
    Mirrors TownCenterStore._current_requests."""
    by_id: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for event in events:
        request_id = event.get("id")
        if not request_id:
            continue
        if "title" in event:
            item = dict(event)
            item["current_state"] = event.get("state", "proposed")
            item["transitions"] = 0
            by_id[request_id] = item
        elif request_id in by_id:
            by_id[request_id]["current_state"] = event.get("state")
            by_id[request_id]["last_reviewer"] = event.get("reviewer")
            by_id[request_id]["last_note"] = event.get("note")
            by_id[request_id]["updated_at"] = event.get("created_at")
            by_id[request_id]["transitions"] += 1
    return list(by_id.values())


def funnel(run: RunData) -> dict[str, Any]:
    """Request counts by final state + the approval-gate bottleneck numbers."""
    view = _current_view(run.requests)
    by_state = Counter(str(r.get("current_state", "proposed")) for r in view)
    pending = [r for r in view if str(r.get("current_state")) in _PENDING_STATES]
    stuck_at_gate = [r for r in pending if r.get("approval_required")]
    executed = by_state.get("completed", 0)  # tool runs only on COMPLETED
    return {
        "submitted": len(view),
        "by_state": {s: by_state.get(s, 0) for s in _STATES if by_state.get(s, 0)},
        "transitions_total": sum(int(r.get("transitions", 0)) for r in view),
        "pending": len(pending),
        "stuck_at_approval_gate": len(stuck_at_gate),
        "tools_executed": executed,
        "throughput": round(executed / len(view), 4) if view else 0.0,
    }


def tool_mix(run: RunData) -> dict[str, Any]:
    """What agents ask for: tool, request type, and self-labeled risk."""
    view = _current_view(run.requests)
    tools = Counter(_request_tool(r) for r in view)
    types = Counter(str(r.get("type", "unknown")) for r in view)
    risks = Counter(
        str((r.get("payload") or {}).get("risk_label", "unlabeled")) for r in view
    )
    return {
        "tools": dict(tools.most_common()),
        "request_types": dict(types.most_common()),
        "risk_labels": dict(risks.most_common()),
    }


def actor_economy(run: RunData) -> dict[str, Any]:
    """Per-actor request activity merged with reward-ledger contribution."""
    view = _current_view(run.requests)
    per_actor: dict[str, dict[str, Any]] = {}
    tools_by_actor: dict[str, Counter] = defaultdict(Counter)
    for r in view:
        actor = str(r.get("actor") or "unknown")
        bucket = per_actor.setdefault(actor, {"submitted": 0, "by_state": Counter()})
        bucket["submitted"] += 1
        bucket["by_state"][str(r.get("current_state", "proposed"))] += 1
        tools_by_actor[actor][_request_tool(r)] += 1
    for actor, bucket in per_actor.items():
        bucket["by_state"] = dict(bucket["by_state"])
        bucket["tools"] = dict(tools_by_actor[actor].most_common())
    return {
        "per_actor": per_actor,
        "contribution": metrics_mod.contribution(run),
        "active_actors": len(per_actor),
    }


def claimed_vs_real(run: RunData) -> dict[str, Any]:
    """Agent-CLAIMED value vs human-CONFIRMED revenue. Kept strictly apart:
    claimed comes from agents' own `expected_payoff` text and is NOT money;
    real revenue exists only in reward rows with source == revenue_confirmed
    (written solely by record_delivery against typed human evidence)."""
    view = _current_view(run.requests)
    claims = []
    for r in view:
        cents = _claimed_cents(r.get("payload") or {})
        if cents > 0:
            claims.append(
                {
                    "request_id": r.get("id"),
                    "actor": r.get("actor"),
                    "title": str(r.get("title", ""))[:120],
                    "claimed_cents": cents,
                    "state": r.get("current_state"),
                }
            )
    claims.sort(key=lambda c: -c["claimed_cents"])
    confirmed = [
        rw for rw in run.rewards if str(rw.get("source")) == "revenue_confirmed"
    ]
    real_cents = sum(int(rw.get("revenue_cents", 0) or 0) for rw in confirmed)
    return {
        "claimed_total_cents": sum(c["claimed_cents"] for c in claims),
        "claims": claims[:20],
        "claim_count": len(claims),
        "real_revenue_cents": real_cents,
        "confirmed_deliveries": len(confirmed),
    }


def pending_queue(run: RunData) -> list[dict[str, Any]]:
    """Every request still awaiting review — the console backlog — with the
    draft preview a human would need to approve or reject it."""
    out = []
    for r in _current_view(run.requests):
        if str(r.get("current_state")) not in _PENDING_STATES:
            continue
        payload = r.get("payload") or {}
        preview = " ".join(str(payload.get("preview", "")).split())
        out.append(
            {
                "request_id": r.get("id"),
                "actor": r.get("actor"),
                "tool": _request_tool(r),
                "risk_label": str(payload.get("risk_label", "unlabeled")),
                "title": str(r.get("title", ""))[:120],
                "preview": preview[:_PREVIEW_MAX],
                "claimed_cents": _claimed_cents(payload),
                "created_at": r.get("created_at"),
            }
        )
    return out


def compute_economy(run: RunData) -> dict[str, Any]:
    """Assemble the full economy payload for a run."""
    return {
        "schema_version": 1,
        "sim_code": run.sim_code,
        "scenario": {
            "id": run.meta.get("scenario_id") or run.scenario.get("id", ""),
            "name": run.meta.get("scenario_name") or run.scenario.get("name", ""),
            "persona_count": len(run.persona_names),
            "step": run.meta.get("step", 0),
        },
        "funnel": funnel(run),
        "tool_mix": tool_mix(run),
        "actor_economy": actor_economy(run),
        "claimed_vs_real": claimed_vs_real(run),
        "pending_queue": pending_queue(run),
    }


# --------------------------------------------------------------------- rendering
def _cents(c: int) -> str:
    return f"${c / 100:,.2f}"


def render_markdown(payload: dict[str, Any]) -> str:
    """Render the economy payload to a Markdown report."""
    sc = payload.get("scenario", {})
    fu = payload.get("funnel", {})
    lines: list[str] = [
        f"# Economy report — {payload.get('sim_code', '?')}\n",
        f"**Scenario:** {sc.get('name', '?')} (`{sc.get('id', '?')}`)  ",
        f"**Personas:** {sc.get('persona_count', 0)} — **steps:** {sc.get('step', 0)}\n",
        "## 1. Request Funnel\n",
        f"- Submitted: **{fu.get('submitted', 0)}** — transitions: "
        f"{fu.get('transitions_total', 0)} — tools executed: "
        f"**{fu.get('tools_executed', 0)}** "
        f"(throughput {fu.get('throughput', 0.0):.0%})",
        f"- By state: {fu.get('by_state', {}) or '(none)'}",
        f"- Pending review: **{fu.get('pending', 0)}** "
        f"(stuck at the human-approval gate: {fu.get('stuck_at_approval_gate', 0)})\n",
    ]

    tm = payload.get("tool_mix", {})
    lines.append("## 2. Tool Mix\n")
    lines.append(f"- Tools requested: {tm.get('tools', {})}")
    lines.append(f"- Request types: {tm.get('request_types', {})}")
    lines.append(f"- Risk labels (agent-assigned): {tm.get('risk_labels', {})}\n")

    cr = payload.get("claimed_vs_real", {})
    lines.append("## 3. Claimed vs Real Value\n")
    lines.append(
        f"- Agent-CLAIMED payoff (unverified self-reports): "
        f"**{_cents(cr.get('claimed_total_cents', 0))}** across "
        f"{cr.get('claim_count', 0)} requests",
    )
    lines.append(
        f"- REAL confirmed revenue (record_delivery only): "
        f"**{_cents(cr.get('real_revenue_cents', 0))}** from "
        f"{cr.get('confirmed_deliveries', 0)} deliveries\n"
    )

    ae = payload.get("actor_economy", {})
    lines.append("## 4. Per-Actor Activity\n")
    per = ae.get("per_actor", {})
    if per:
        lines.append("| Actor | Submitted | States | Tools |")
        lines.append("| --- | --- | --- | --- |")
        for actor in sorted(per, key=lambda a: -per[a]["submitted"]):
            b = per[actor]
            lines.append(
                f"| {actor} | {b['submitted']} | {b['by_state']} | {b['tools']} |"
            )
        lines.append("")

    pq = payload.get("pending_queue", [])
    lines.append(f"## 5. Pending Queue ({len(pq)} awaiting human review)\n")
    if pq:
        lines.append("| Actor | Tool | Risk | Title | Claimed | Preview |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for q in pq:
            lines.append(
                f"| {q['actor']} | {q['tool']} | {q['risk_label']} | {q['title']} "
                f"| {_cents(q['claimed_cents'])} | {q['preview'][:100]} |"
            )
        lines.append("")
    return "\n".join(lines)


def out_paths(sim_code: str) -> tuple[Path, Path]:
    """Return (json, md) output paths under tools/eval/out/."""
    out_dir = Path(__file__).resolve().parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return (out_dir / f"{sim_code}.economy.json", out_dir / f"{sim_code}.economy.md")


def analyze(sim_code: str) -> dict[str, Any]:
    """Load a run, compute the economy, write JSON + Markdown, return payload."""
    import json

    run = load_run(sim_code)
    payload = compute_economy(run)
    json_path, md_path = out_paths(run.sim_code)
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    payload["_outputs"] = {"economy_json": str(json_path), "economy_md": str(md_path)}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Economy analyzer for a run.")
    parser.add_argument(
        "sim_code", help="Run sim_code, run-dir path, or 'latest[:prefix]'."
    )
    args = parser.parse_args(argv)
    try:
        payload = analyze(args.sim_code)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    fu = payload["funnel"]
    cr = payload["claimed_vs_real"]
    print(f"Economy: {payload['sim_code']}")
    print(
        f"  funnel: {fu['submitted']} submitted -> {fu['tools_executed']} executed "
        f"({fu['pending']} pending, {fu['stuck_at_approval_gate']} stuck at gate)"
    )
    print(
        f"  value: claimed {_cents(cr['claimed_total_cents'])} vs real "
        f"{_cents(cr['real_revenue_cents'])} "
        f"({cr['confirmed_deliveries']} confirmed deliveries)"
    )
    outputs = payload.get("_outputs", {})
    print(f"  wrote: {outputs.get('economy_json')}")
    print(f"  wrote: {outputs.get('economy_md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
