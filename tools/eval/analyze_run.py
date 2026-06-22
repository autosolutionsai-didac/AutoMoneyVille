"""CLI: compute structural metrics for a finished run and write JSON + Markdown.

Usage:
    python -m tools.eval.analyze_run <sim_code>
    python tools/eval/analyze_run.py <sim_code>
    python tools/eval/analyze_run.py latest:claudeville_v1_2026
    python tools/eval/analyze_run.py <sim_code> --emergence

Pure structural analysis only (no LLM). Writes:
    tools/eval/out/<sim_code>.metrics.json
    tools/eval/out/<sim_code>.report.md
With --emergence, also writes (Phase 6d):
    tools/eval/out/<sim_code>.emergence.json
    tools/eval/out/<sim_code>.emergence.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a bare script (python tools/eval/analyze_run.py) by ensuring
# the repo root is importable so the "tools.eval" package resolves.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.eval import emergence as emergence_mod
    from tools.eval import metrics as metrics_mod
    from tools.eval import report as report_mod
    from tools.eval.run_loader import load_run
else:
    from . import emergence as emergence_mod
    from . import metrics as metrics_mod
    from . import report as report_mod
    from .run_loader import load_run


def analyze(sim_code: str) -> dict:
    """Load a run, compute metrics, write JSON + Markdown, return the metrics."""
    run = load_run(sim_code)
    payload = metrics_mod.compute_metrics(run)
    json_path = report_mod.write_metrics_json(run.sim_code, payload)
    md_path = report_mod.write_report_md(run.sim_code, payload)
    payload["_outputs"] = {"metrics_json": str(json_path), "report_md": str(md_path)}
    return payload


def _print_summary(payload: dict) -> None:
    sc = payload.get("scenario", {})
    act = payload.get("activity", {})
    con = payload.get("contribution", {})
    net = payload.get("social_network", {})
    coh = payload.get("request_coherence", {})
    spec = payload.get("role_specialization", {})
    print(f"Analyzed run: {payload.get('sim_code')}")
    print(f"  scenario: {sc.get('name')} ({sc.get('persona_count')} personas)")
    print(
        f"  steps: {act.get('simulation_steps')} "
        f"(active {act.get('active_steps')}), "
        f"memory nodes: {act.get('total_memory_nodes')}"
    )
    print(
        f"  requests by specialists: {spec.get('actors_with_requests')} actors, "
        f"mean concentration {spec.get('mean_concentration')}"
    )
    print(
        f"  coherence: {coh.get('forward_handoffs')} forward handoffs / "
        f"{coh.get('transitions')} transitions "
        f"(ratio {coh.get('forward_ratio')})"
    )
    print(
        f"  contribution: team points {con.get('team_points')}, "
        f"revenue {con.get('team_revenue_cents')}c, "
        f"contributors {con.get('contributing_actors')}"
    )
    print(
        f"  social: {net.get('edge_count')} edges, "
        f"{net.get('conversation_instances')} conversation instances"
    )
    outputs = payload.get("_outputs", {})
    print(f"  wrote: {outputs.get('metrics_json')}")
    print(f"  wrote: {outputs.get('report_md')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Structural metrics for a run.")
    parser.add_argument(
        "sim_code",
        help="Run sim_code, run-dir path, or 'latest[:prefix]'.",
    )
    parser.add_argument(
        "--emergence",
        action="store_true",
        help="Also compute the Phase 6d emergence report (trajectories).",
    )
    args = parser.parse_args(argv)
    try:
        payload = analyze(args.sim_code)
        if args.emergence:
            emg = emergence_mod.analyze(args.sim_code)
            payload["_emergence_outputs"] = emg.get("_outputs", {})
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print_summary(payload)
    if args.emergence:
        eo = payload.get("_emergence_outputs", {})
        print(f"  wrote: {eo.get('emergence_json')}")
        print(f"  wrote: {eo.get('emergence_md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
