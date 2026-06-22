"""Render structural metrics (and optional judge scores) to JSON + Markdown."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .metrics import gini

OUT_DIR = Path(__file__).resolve().parent / "out"


def out_paths(sim_code: str) -> tuple[Path, Path]:
    """Return (metrics_json_path, report_md_path) for a sim_code."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return (
        OUT_DIR / f"{sim_code}.metrics.json",
        OUT_DIR / f"{sim_code}.report.md",
    )


def write_metrics_json(sim_code: str, metrics: dict[str, Any]) -> Path:
    """Write the metrics payload to out/<sim_code>.metrics.json."""
    json_path, _ = out_paths(sim_code)
    json_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return json_path


def load_metrics_json(sim_code: str) -> dict[str, Any] | None:
    """Load a previously written metrics file if present."""
    json_path, _ = out_paths(sim_code)
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _h(level: int, text: str) -> str:
    return f"{'#' * level} {text}\n"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_(none)_\n"
    out = ["| " + " | ".join(headers) + " |"]
    out.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out) + "\n"


def render_markdown(metrics: dict[str, Any]) -> str:
    """Render the metrics payload (plus any embedded judge block) to Markdown."""
    parts: list[str] = []
    sc = metrics.get("scenario", {})
    parts.append(_h(1, f"Evaluation report — {metrics.get('sim_code', '?')}"))
    parts.append(
        f"**Scenario:** {sc.get('name', '?')} (`{sc.get('id', '?')}`)  \n"
        f"**Objective:** {sc.get('objective', '?')}  \n"
        f"**Personas:** {sc.get('persona_count', 0)}\n"
    )

    parts.append(_render_activity(metrics.get("activity", {})))
    parts.append(_render_specialization(metrics.get("role_specialization", {})))
    parts.append(_render_approval(metrics.get("approval_rates", {})))
    parts.append(_render_coherence(metrics.get("request_coherence", {})))
    parts.append(_render_contribution(metrics.get("contribution", {})))
    parts.append(_render_network(metrics.get("social_network", {})))

    if "believability_judge" in metrics:
        parts.append(_render_judge(metrics["believability_judge"]))

    return "\n".join(parts)


def _render_activity(a: dict[str, Any]) -> str:
    out = [_h(2, "Activity & Memory Growth")]
    out.append(
        f"- Simulation steps: **{a.get('simulation_steps', 0)}** "
        f"(active: {a.get('active_steps', 0)}, "
        f"ratio {a.get('active_step_ratio', 0)})\n"
        f"- Total events: {a.get('total_events', 0)} | "
        f"movement snapshots: {a.get('movement_snapshot_count', 0)} "
        f"range {a.get('movement_step_range', [])}\n"
        f"- Total memory nodes: **{a.get('total_memory_nodes', 0)}**\n"
    )
    timing = a.get("step_timing", {})
    if timing.get("samples"):
        means = timing.get("mean_ms", {})
        out.append(
            f"- Step timing (mean over {timing['samples']} samples): "
            f"perceive {means.get('perceive_ms', 0)}ms | "
            f"move {means.get('move_ms', 0)}ms | "
            f"serialize {means.get('serialize_ms', 0)}ms | "
            f"total {means.get('total_ms', 0)}ms\n"
        )
    mem = a.get("memory_node_counts", {})
    if mem:
        out.append(
            _table(
                ["Persona", "Memory nodes"],
                [[k, v] for k, v in sorted(mem.items())],
            )
        )
    return "\n".join(out)


def _render_specialization(s: dict[str, Any]) -> str:
    out = [_h(2, "Role Specialization")]
    out.append(
        f"Mean type-concentration (HHI, 1=focused, 0=diffuse): "
        f"**{s.get('mean_concentration', 0)}** "
        f"across {s.get('actors_with_requests', 0)} requesting actors.\n"
    )
    rows = []
    for actor, info in sorted(s.get("per_actor", {}).items()):
        types = ", ".join(
            f"{k}:{v}" for k, v in info.get("type_distribution", {}).items()
        )
        rows.append(
            [
                actor,
                info.get("role", ""),
                info.get("request_count", 0),
                info.get("concentration", 0),
                types,
            ]
        )
    out.append(
        _table(["Actor", "Role", "#Req", "Concentration", "Request types"], rows)
    )
    return "\n".join(out)


def _render_approval(ap: dict[str, Any]) -> str:
    out = [_h(2, "Request Approval Rates")]
    rows = []
    for actor, info in sorted(ap.get("per_actor", {}).items()):
        rows.append(
            [
                actor,
                info.get("submitted", 0),
                info.get("approved", 0),
                info.get("rejected", 0),
                info.get("pending", 0),
                info.get("approval_rate"),
            ]
        )
    out.append(
        _table(
            ["Actor", "Submitted", "Approved", "Rejected", "Pending", "Rate"],
            rows,
        )
    )
    return "\n".join(out)


def _render_coherence(c: dict[str, Any]) -> str:
    out = [_h(2, "Request Coherence & Handoffs")]
    out.append(
        f"- Stage transitions: {c.get('transitions', 0)} | "
        f"forward handoffs: **{c.get('forward_handoffs', 0)}** | "
        f"backward: {c.get('backward_steps', 0)} | "
        f"same-stage: {c.get('same_stage', 0)}\n"
        f"- Forward ratio (higher = more pipeline-coherent): "
        f"**{c.get('forward_ratio', 0)}**\n"
        f"- Stage distribution: {c.get('stage_distribution', {})}\n"
    )
    handoffs = c.get("handoffs", [])
    if handoffs:
        rows = [
            [
                h.get("from_stage"),
                h.get("from_actor"),
                "->",
                h.get("to_stage"),
                h.get("to_actor"),
                (h.get("to_title", "")[:48]),
            ]
            for h in handoffs
        ]
        out.append(
            _table(
                ["From", "By", "", "To", "By", "Request"],
                rows,
            )
        )
    return "\n".join(out)


def _render_contribution(con: dict[str, Any]) -> str:
    out = [_h(2, "Per-Agent Contribution")]
    per = con.get("per_actor", {})
    out.append(
        f"- Team points: **{con.get('team_points', 0)}** | "
        f"team revenue: {con.get('team_revenue_cents', 0)} cents | "
        f"contributors: {con.get('contributing_actors', 0)}\n"
        f"- Points inequality (Gini, 0=equal): "
        f"**{gini([v.get('points', 0) for v in per.values()])}**\n"
    )
    rows = []
    for actor, info in sorted(
        per.items(), key=lambda kv: kv[1].get("points", 0), reverse=True
    ):
        rows.append(
            [
                actor,
                info.get("points", 0),
                info.get("revenue_cents", 0),
                info.get("reward_count", 0),
                info.get("mean_valence", 0),
            ]
        )
    out.append(
        _table(["Actor", "Points", "Revenue¢", "#Rewards", "MeanValence"], rows)
    )
    return "\n".join(out)


def _render_network(n: dict[str, Any]) -> str:
    out = [_h(2, "Social Network")]
    out.append(
        f"- Edges: **{n.get('edge_count', 0)}** | "
        f"talk steps: {n.get('talk_steps', 0)} | "
        f"conversation instances: {n.get('conversation_instances', 0)}\n"
        f"- Group size mean/max: {n.get('group_size_mean', 0)} / "
        f"{n.get('group_size_max', 0)}\n"
    )
    edges = n.get("edges", [])
    if edges:
        out.append(
            _table(
                ["Source", "Target", "Weight"],
                [[e["source"], e["target"], e["weight"]] for e in edges],
            )
        )
    cent = n.get("degree_centrality", {})
    if cent:
        out.append("\n**Degree centrality:**\n")
        out.append(
            _table(
                ["Persona", "Centrality"],
                [
                    [k, v]
                    for k, v in sorted(
                        cent.items(), key=lambda kv: kv[1], reverse=True
                    )
                ],
            )
        )
    return "\n".join(out)


def _render_judge(j: dict[str, Any]) -> str:
    out = [_h(2, "Believability Judge (LLM)")]
    if j.get("status") != "ok":
        out.append(
            f"_Judge skipped: {j.get('reason', 'unavailable')}_\n"
        )
        return "\n".join(out)

    out.append(
        f"Model: `{j.get('model', '?')}` | "
        f"personas scored: {len(j.get('scores', {}))}\n"
    )
    dims = [
        "goal_completion",
        "believability",
        "relationship",
        "social_rules",
        "role_alignment",
    ]
    rows = []
    for persona, sc in sorted(j.get("scores", {}).items()):
        rows.append([persona] + [sc.get(d, {}).get("score", "-") for d in dims])
    out.append(_table(["Persona"] + dims, rows))

    # Justifications appendix.
    for persona, sc in sorted(j.get("scores", {}).items()):
        out.append(f"\n**{persona}:**\n")
        for d in dims:
            entry = sc.get(d, {})
            out.append(
                f"- _{d}_ ({entry.get('score', '-')}): "
                f"{entry.get('justification', '')}\n"
            )
    return "\n".join(out)


def write_report_md(sim_code: str, metrics: dict[str, Any]) -> Path:
    """Render and write out/<sim_code>.report.md."""
    _, md_path = out_paths(sim_code)
    md_path.write_text(render_markdown(metrics), encoding="utf-8")
    return md_path
