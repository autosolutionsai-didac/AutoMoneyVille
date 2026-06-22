"""CLI: determinism / regression diff between two finished runs.

Compares two runs' movement traces step-by-step and reports the first divergence
plus a similarity summary. Reads, in order of preference per run:
    1. compressed_storage/<sim_code>/master_movement.json  ({step: {name: {...}}})
    2. runs/<sim_code>/movement/<step>.json               (per-step packets)

Usage:
    python -m tools.eval.replay_diff <sim_a> <sim_b>
    python tools/eval/replay_diff.py <sim_a> <sim_b>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.eval.run_loader import repo_root, resolve_run_dir
else:
    from .run_loader import repo_root, resolve_run_dir

# Position record per step: {persona_name: (x, y)}.
StepPositions = dict[str, tuple[int, int]]


def _compressed_path(sim_code: str) -> Path:
    return (
        repo_root()
        / "environment"
        / "frontend_server"
        / "compressed_storage"
        / sim_code
        / "master_movement.json"
    )


def _positions_from_persona_block(block: dict[str, Any]) -> StepPositions:
    """Extract {name: (x, y)} from a {name: {movement: [x, y], ...}} block."""
    out: StepPositions = {}
    for name, pdata in block.items():
        if not isinstance(pdata, dict):
            continue
        mv = pdata.get("movement")
        if isinstance(mv, (list, tuple)) and len(mv) >= 2:
            try:
                out[name] = (int(mv[0]), int(mv[1]))
            except (TypeError, ValueError):
                continue
    return out


def _carry_forward(trace: dict[int, StepPositions]) -> dict[int, StepPositions]:
    """Fill each step with last-known positions for personas it omits.

    The compressed master_movement.json is a *delta* format: a step only lists
    personas whose movement changed (and a step may be empty). To compare two
    runs meaningfully we materialize the full position set at every step by
    carrying the previous value forward. Harmless for the already-full per-step
    movement/<step>.json format.
    """
    filled: dict[int, StepPositions] = {}
    last: StepPositions = {}
    for step in sorted(trace):
        last = {**last, **trace[step]}
        filled[step] = dict(last)
    return filled


def load_trace(sim_code: str) -> dict[int, StepPositions]:
    """Load a run's movement trace as {step: {name: (x, y)}}.

    Tries the compressed master_movement.json first, then falls back to the
    per-step movement/<step>.json packets in the run directory. Positions are
    carried forward across steps that omit a persona (delta format).
    """
    trace: dict[int, StepPositions] = {}

    comp = _compressed_path(sim_code)
    if comp.exists():
        try:
            raw = json.loads(comp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw = {}
        for step_str, block in raw.items():
            if str(step_str).lstrip("-").isdigit() and isinstance(block, dict):
                trace[int(step_str)] = _positions_from_persona_block(block)
        if trace:
            return _carry_forward(trace)

    # Per-step fallback.
    try:
        run_dir = resolve_run_dir(sim_code)
    except (FileNotFoundError, ValueError):
        return trace
    move_dir = run_dir / "movement"
    if not move_dir.is_dir():
        return trace
    for path in move_dir.glob("*.json"):
        if not path.stem.isdigit():
            continue
        try:
            packet = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        block = packet.get("persona", packet) if isinstance(packet, dict) else {}
        trace[int(path.stem)] = _positions_from_persona_block(block)
    return _carry_forward(trace)


def diff_traces(
    trace_a: dict[int, StepPositions], trace_b: dict[int, StepPositions]
) -> dict[str, Any]:
    """Compare two traces and summarize divergence + similarity."""
    steps = sorted(set(trace_a) & set(trace_b))
    only_a = sorted(set(trace_a) - set(trace_b))
    only_b = sorted(set(trace_b) - set(trace_a))

    first_divergence: dict[str, Any] | None = None
    matching_cells = 0
    total_cells = 0
    diverged_steps = 0

    for step in steps:
        pa = trace_a[step]
        pb = trace_b[step]
        names = sorted(set(pa) | set(pb))
        step_diverged = False
        diffs: list[dict[str, Any]] = []
        for name in names:
            total_cells += 1
            a_pos = pa.get(name)
            b_pos = pb.get(name)
            if a_pos == b_pos and a_pos is not None:
                matching_cells += 1
            else:
                step_diverged = True
                diffs.append({"persona": name, "a": a_pos, "b": b_pos})
        if step_diverged:
            diverged_steps += 1
            if first_divergence is None:
                first_divergence = {"step": step, "diffs": diffs}

    similarity = round(matching_cells / total_cells, 4) if total_cells else 1.0
    return {
        "sim_a_steps": len(trace_a),
        "sim_b_steps": len(trace_b),
        "compared_steps": len(steps),
        "steps_only_in_a": only_a,
        "steps_only_in_b": only_b,
        "diverged_steps": diverged_steps,
        "position_similarity": similarity,
        "identical": first_divergence is None and not only_a and not only_b,
        "first_divergence": first_divergence,
    }


def compare(sim_a: str, sim_b: str) -> dict[str, Any]:
    """Load both traces and return a diff summary payload."""
    trace_a = load_trace(sim_a)
    trace_b = load_trace(sim_b)
    summary = diff_traces(trace_a, trace_b)
    summary["sim_a"] = sim_a
    summary["sim_b"] = sim_b
    return summary


def _print_summary(s: dict[str, Any]) -> None:
    print(f"replay diff: {s['sim_a']}  vs  {s['sim_b']}")
    print(
        f"  steps: a={s['sim_a_steps']} b={s['sim_b_steps']} "
        f"compared={s['compared_steps']}"
    )
    print(
        f"  position similarity: {s['position_similarity']} | "
        f"diverged steps: {s['diverged_steps']} | "
        f"identical: {s['identical']}"
    )
    if s["steps_only_in_a"] or s["steps_only_in_b"]:
        print(
            f"  step coverage mismatch: only_a={s['steps_only_in_a'][:5]} "
            f"only_b={s['steps_only_in_b'][:5]}"
        )
    fd = s["first_divergence"]
    if fd:
        print(f"  first divergence at step {fd['step']}:")
        for d in fd["diffs"][:6]:
            print(f"    {d['persona']}: a={d['a']} b={d['b']}")
    elif s["compared_steps"]:
        print("  no positional divergence across compared steps.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diff two runs' movement traces.")
    parser.add_argument("sim_a", help="First run sim_code or path.")
    parser.add_argument("sim_b", help="Second run sim_code or path.")
    parser.add_argument(
        "--json", action="store_true", help="Print the raw JSON summary."
    )
    args = parser.parse_args(argv)
    summary = compare(args.sim_a, args.sim_b)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
