"""Emergence analyzer — aggregates the social phenomena the literature studies
from a finished run, *over time* (Phase 6d).

Where ``metrics.py`` reports end-state structural metrics, this module measures
TRAJECTORIES and emergent collective behavior:

1. specialization_trajectory: does per-role request concentration RISE over the
   run? (agents settling into specialists vs. staying generalists).
2. cooperation: mutual help / reciprocity in town requests + rewards (do pairs
   help each other; do forward handoffs accumulate).
3. network_growth: social-graph formation over time (cumulative edges / nodes /
   density growth from movement conversations).
4. conventions: repeated shared behaviors / phrases that recur across personas
   (an emergent shared vocabulary).

Pure + deterministic (no LLM, no embeddings — D-002). Builds on ``run_loader``
and reuses ``metrics`` helpers. Output: JSON + Markdown, mirroring report.py.

Usage:
    python -m tools.eval.emergence <sim_code>
    python tools/eval/emergence.py latest:claudeville_v1

Author: Claudeville Project
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.eval import metrics as metrics_mod
    from tools.eval.run_loader import RunData, load_run
else:
    from . import metrics as metrics_mod
    from .run_loader import RunData, load_run

# Stopwords for the convention (shared-phrase) detector. Aligned with the
# relationship-memory topic extraction so the vocabulary stays consistent.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on",
    "at", "and", "or", "with", "for", "you", "your", "i", "it", "this",
    "that", "be", "as", "from", "by", "has", "have", "had", "im", "ive",
    "hey", "hi", "hello", "yeah", "yes", "no", "ok", "okay", "so", "but",
    "we", "they", "he", "she", "my", "me", "do", "did", "what", "how",
    "about", "just", "like", "going", "good", "well", "thanks", "thank",
    "lets", "let", "get", "got", "will", "would", "can", "could", "should",
    "team", "work", "working", "today", "need", "want",
}


def _trend(series: list[float]) -> dict[str, Any]:
    """Summarize a time-series: first/last value, delta, and rising? flag.

    Uses the mean of the first vs. last third so a single noisy step does not
    dominate the verdict; falls back to endpoints for short series.
    """
    vals = [float(v) for v in series]
    n = len(vals)
    if n == 0:
        return {"first": 0.0, "last": 0.0, "delta": 0.0, "rising": False, "points": 0}
    if n < 3:
        first, last = vals[0], vals[-1]
    else:
        third = max(1, n // 3)
        first = sum(vals[:third]) / third
        last = sum(vals[-third:]) / third
    delta = last - first
    return {
        "first": round(first, 4),
        "last": round(last, 4),
        "delta": round(delta, 4),
        "rising": delta > 1e-9,
        "points": n,
    }


def _submitted(run: RunData) -> list[dict[str, Any]]:
    rows = [r for r in run.requests if r.get("actor") and r.get("title")]
    rows.sort(key=lambda r: r.get("created_at", ""))
    return rows


def specialization_trajectory(run: RunData) -> dict[str, Any]:
    """Mean per-actor request-type concentration as it grows over the run.

    Walks submitted requests in time order, and after each new request recomputes
    the mean Herfindahl concentration across all actors seen so far. A rising
    series means agents are settling into specialists (the GA emergence claim).
    """
    submitted = _submitted(run)
    per_actor_types: dict[str, Counter] = defaultdict(Counter)
    series: list[float] = []
    checkpoints: list[dict[str, Any]] = []
    for r in submitted:
        per_actor_types[r["actor"]][r.get("type", "unknown")] += 1
        concentrations = [
            metrics_mod._herfindahl(list(c.values()))
            for c in per_actor_types.values()
        ]
        mean_conc = sum(concentrations) / len(concentrations) if concentrations else 0.0
        series.append(round(mean_conc, 4))
        checkpoints.append(
            {
                "after_requests": len(series),
                "actors_active": len(per_actor_types),
                "mean_concentration": round(mean_conc, 4),
            }
        )
    return {
        "series": series,
        "checkpoints": checkpoints,
        "trend": _trend(series),
        "final_specialists": [
            actor
            for actor, c in per_actor_types.items()
            if metrics_mod._herfindahl(list(c.values())) >= 0.5
        ],
    }


def cooperation(run: RunData) -> dict[str, Any]:
    """Reciprocity / mutual help across the run.

    - forward_handoffs: forward pipeline handoffs accumulating over time
      (research -> offer -> outreach ...), a directed cooperation-flow signal.
    - directed_handoff_pairs: who handed work to whom (from -> to).
    - reciprocal_handoff_pairs: pairs that handed work to each other in BOTH
      directions (rare in a strict pipeline, but the strongest cooperation cue).
    - mutual_conversation_pairs: pairs that actually talked (conversation is
      inherently bidirectional — the canonical GA reciprocity signal).
    - shared_reward_sources: pairs that each earned reward on the same source.
    """
    coh = metrics_mod.request_coherence(run)
    handoffs = coh.get("handoffs", [])

    # Cumulative forward-handoff count over the handoff sequence.
    series = list(range(1, len(handoffs) + 1)) if handoffs else []

    directed: set[tuple[str, str]] = set()
    for h in handoffs:
        a, b = h.get("from_actor"), h.get("to_actor")
        if a and b and a != b:
            directed.add((a, b))
    reciprocal = sorted(
        {tuple(sorted((a, b))) for (a, b) in directed if (b, a) in directed}
    )

    # Mutual conversation pairs: reuse the social-network edges (each edge is an
    # undirected pair that shared a conversation — mutual by construction).
    net = metrics_mod.social_network(run)
    convo_pairs = sorted(
        (e["source"], e["target"]) for e in net.get("edges", [])
    )

    # Reward reciprocity: actors who both earned reward from a shared source.
    source_actors: dict[str, set[str]] = defaultdict(set)
    for rw in run.rewards:
        actor = rw.get("actor")
        src = rw.get("source")
        if actor and src and int(rw.get("points", 0) or 0) > 0:
            source_actors[src].add(actor)
    mutual_sources = {s: sorted(a) for s, a in source_actors.items() if len(a) >= 2}

    cooperating = (
        bool(reciprocal)
        or bool(convo_pairs)
        or coh.get("forward_handoffs", 0) > 0
    )
    return {
        "forward_handoffs": coh.get("forward_handoffs", 0),
        "forward_handoff_series": series,
        "forward_handoff_trend": _trend([float(x) for x in series]),
        "directed_handoff_pairs": ["->".join(p) for p in sorted(directed)],
        "reciprocal_handoff_pairs": ["+".join(p) for p in reciprocal],
        "reciprocal_pair_count": len(reciprocal),
        "mutual_conversation_pairs": ["+".join(p) for p in convo_pairs],
        "mutual_conversation_count": len(convo_pairs),
        "shared_reward_sources": mutual_sources,
        "cooperating": cooperating,
    }


def network_growth(run: RunData) -> dict[str, Any]:
    """Cumulative social-graph formation over movement steps.

    For each step (in order) accumulate conversation edges and report the running
    edge count, active-node count, and graph density so growth is visible as a
    trajectory rather than only as an end-state count.
    """
    cumulative_edges: set[tuple[str, str]] = set()
    cumulative_nodes: set[str] = set()
    edge_series: list[int] = []
    node_series: list[int] = []
    density_series: list[float] = []
    checkpoints: list[dict[str, Any]] = []

    n_total = len(run.persona_names) or 0

    for step in sorted(run.movement):
        packet = run.movement[step]
        if not isinstance(packet, dict):
            continue
        meta = packet.get("meta", {})
        convs = meta.get("conversations", {}) if isinstance(meta, dict) else {}
        if not isinstance(convs, dict):
            convs = {}
        for group in convs.values():
            if not isinstance(group, dict):
                continue
            parts = [str(p) for p in group.get("participants", []) if p]
            for pair in metrics_mod._unordered_pairs(parts):
                cumulative_edges.add(pair)
                cumulative_nodes.update(pair)
        persona_map = packet.get("persona", {})
        if not isinstance(persona_map, dict):
            persona_map = {}
        for name, pdata in persona_map.items():
            if not isinstance(pdata, dict):
                continue
            speakers = {
                str(s) for s in metrics_mod._iter_chat_pairs(pdata.get("chat"))
            }
            speakers.add(name)
            speakers.discard("")
            for pair in metrics_mod._unordered_pairs(sorted(speakers)):
                cumulative_edges.add(pair)
                cumulative_nodes.update(pair)

        e = len(cumulative_edges)
        v = len(cumulative_nodes)
        max_edges = v * (v - 1) / 2 if v >= 2 else 0
        density = round(e / max_edges, 4) if max_edges else 0.0
        edge_series.append(e)
        node_series.append(v)
        density_series.append(density)
        checkpoints.append(
            {"step": step, "edges": e, "nodes": v, "density": density}
        )

    return {
        "edge_series": edge_series,
        "node_series": node_series,
        "density_series": density_series,
        "checkpoints": checkpoints,
        "final_edges": edge_series[-1] if edge_series else 0,
        "final_nodes": node_series[-1] if node_series else 0,
        "final_density": density_series[-1] if density_series else 0.0,
        "total_personas": n_total,
        "edge_trend": _trend([float(x) for x in edge_series]),
        "density_trend": _trend(density_series),
    }


def _content_words(text: str) -> list[str]:
    out = []
    for raw in str(text).split():
        word = "".join(ch for ch in raw.lower() if ch.isalnum())
        if len(word) > 3 and word not in _STOPWORDS:
            out.append(word)
    return out


def conventions(run: RunData, min_speakers: int = 2, top: int = 12) -> dict[str, Any]:
    """Detect emergent shared vocabulary: content words used by MULTIPLE personas.

    A convention is a phrase/word that recurs across the population (not just one
    persona's tic). We count, per content word, how many distinct speakers used
    it and how often; words crossing ``min_speakers`` are candidate conventions.
    """
    word_speakers: dict[str, set[str]] = defaultdict(set)
    word_counts: Counter = Counter()

    for step in sorted(run.movement):
        packet = run.movement[step]
        if not isinstance(packet, dict):
            continue
        persona_map = packet.get("persona", {})
        if not isinstance(persona_map, dict):
            persona_map = {}
        for name, pdata in persona_map.items():
            if not isinstance(pdata, dict):
                continue
            chat = pdata.get("chat")
            if not isinstance(chat, list):
                continue
            for line in chat:
                if isinstance(line, (list, tuple)) and len(line) >= 2:
                    speaker, text = str(line[0]), line[1]
                else:
                    speaker, text = name, line
                for word in _content_words(text):
                    word_speakers[word].add(speaker)
                    word_counts[word] += 1

    shared = [
        {
            "phrase": w,
            "speakers": len(word_speakers[w]),
            "occurrences": word_counts[w],
        }
        for w in word_speakers
        if len(word_speakers[w]) >= min_speakers
    ]
    shared.sort(key=lambda d: (-d["speakers"], -d["occurrences"], d["phrase"]))
    return {
        "shared_phrases": shared[:top],
        "shared_phrase_count": len(shared),
        "distinct_words": len(word_counts),
        "convention_emerged": bool(shared),
    }


def compute_emergence(run: RunData) -> dict[str, Any]:
    """Assemble the full emergence payload for a run."""
    return {
        "schema_version": 1,
        "sim_code": run.sim_code,
        "scenario": {
            "id": run.meta.get("scenario_id") or run.scenario.get("id", ""),
            "name": run.meta.get("scenario_name") or run.scenario.get("name", ""),
            "persona_count": len(run.persona_names),
        },
        "specialization_trajectory": specialization_trajectory(run),
        "cooperation": cooperation(run),
        "network_growth": network_growth(run),
        "conventions": conventions(run),
    }


# --------------------------------------------------------------------- rendering
def render_markdown(payload: dict[str, Any]) -> str:
    """Render the emergence payload to a Markdown report."""
    sc = payload.get("scenario", {})
    lines: list[str] = [
        f"# Emergence report — {payload.get('sim_code', '?')}\n",
        f"**Scenario:** {sc.get('name', '?')} (`{sc.get('id', '?')}`)  ",
        f"**Personas:** {sc.get('persona_count', 0)}\n",
    ]

    sp = payload.get("specialization_trajectory", {})
    spt = sp.get("trend", {})
    lines.append("## 1. Specialization Trajectory\n")
    lines.append(
        f"- Mean role concentration {spt.get('first', 0)} -> {spt.get('last', 0)} "
        f"(delta {spt.get('delta', 0)}, "
        f"{'RISING' if spt.get('rising') else 'flat/falling'})\n"
        f"- Final specialists (concentration >= 0.5): "
        f"{', '.join(sp.get('final_specialists', [])) or '(none)'}\n"
    )

    co = payload.get("cooperation", {})
    lines.append("## 2. Cooperation & Reciprocity\n")
    lines.append(
        f"- Forward handoffs: **{co.get('forward_handoffs', 0)}**\n"
        f"- Directed handoff pairs: "
        f"{', '.join(co.get('directed_handoff_pairs', [])) or '(none)'}\n"
        f"- Reciprocal handoff pairs: "
        f"{', '.join(co.get('reciprocal_handoff_pairs', [])) or '(none)'}\n"
        f"- Mutual conversation pairs: "
        f"{', '.join(co.get('mutual_conversation_pairs', [])) or '(none)'}\n"
        f"- Shared reward sources: {co.get('shared_reward_sources', {})}\n"
        f"- Cooperating: **{co.get('cooperating', False)}**\n"
    )

    ng = payload.get("network_growth", {})
    et = ng.get("edge_trend", {})
    lines.append("## 3. Social-Network Formation\n")
    lines.append(
        f"- Edges {et.get('first', 0)} -> {et.get('last', 0)} "
        f"(final {ng.get('final_edges', 0)} edges over "
        f"{ng.get('final_nodes', 0)}/{ng.get('total_personas', 0)} nodes)\n"
        f"- Final density: **{ng.get('final_density', 0)}** "
        f"({'growing' if et.get('rising') else 'flat'})\n"
    )

    cv = payload.get("conventions", {})
    lines.append("## 4. Convention Emergence (shared vocabulary)\n")
    lines.append(
        f"- Shared phrases (used by >=2 personas): "
        f"**{cv.get('shared_phrase_count', 0)}**\n"
    )
    phrases = cv.get("shared_phrases", [])
    if phrases:
        lines.append("| Phrase | Speakers | Occurrences |")
        lines.append("| --- | --- | --- |")
        for p in phrases:
            lines.append(
                f"| {p['phrase']} | {p['speakers']} | {p['occurrences']} |"
            )
        lines.append("")
    return "\n".join(lines)


def out_paths(sim_code: str) -> tuple[Path, Path]:
    """Return (json, md) output paths under tools/eval/out/."""
    out_dir = Path(__file__).resolve().parent / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return (
        out_dir / f"{sim_code}.emergence.json",
        out_dir / f"{sim_code}.emergence.md",
    )


def analyze(sim_code: str) -> dict[str, Any]:
    """Load a run, compute emergence, write JSON + Markdown, return the payload."""
    import json

    run = load_run(sim_code)
    payload = compute_emergence(run)
    json_path, md_path = out_paths(run.sim_code)
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    payload["_outputs"] = {"emergence_json": str(json_path), "emergence_md": str(md_path)}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emergence analyzer for a run.")
    parser.add_argument(
        "sim_code", help="Run sim_code, run-dir path, or 'latest[:prefix]'."
    )
    args = parser.parse_args(argv)
    try:
        payload = analyze(args.sim_code)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    sp = payload["specialization_trajectory"]["trend"]
    ng = payload["network_growth"]
    cv = payload["conventions"]
    co = payload["cooperation"]
    print(f"Emergence: {payload['sim_code']}")
    print(
        f"  specialization: {sp['first']} -> {sp['last']} "
        f"({'rising' if sp['rising'] else 'flat'})"
    )
    print(
        f"  cooperation: {co['forward_handoffs']} handoffs, "
        f"{co['reciprocal_pair_count']} reciprocal pairs"
    )
    print(
        f"  network: {ng['final_edges']} edges, density {ng['final_density']}"
    )
    print(f"  conventions: {cv['shared_phrase_count']} shared phrases")
    outputs = payload.get("_outputs", {})
    print(f"  wrote: {outputs.get('emergence_json')}")
    print(f"  wrote: {outputs.get('emergence_md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
