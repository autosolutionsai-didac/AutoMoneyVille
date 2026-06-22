"""Pure structural metrics over a loaded run (no LLM, deterministic).

Each function takes a ``RunData`` and returns a JSON-serializable dict. The top
level ``compute_metrics`` assembles them into one report payload. These metrics
make emergent behavior measurable:

- role_specialization: concentration of each persona's requests vs. its role.
- request_coherence:   ordered request sequence + plausible handoff detection.
- contribution:        per-agent points / revenue from rewards.jsonl.
- social_network:      conversation edges, frequencies, group sizes, centrality.
- activity:            events-per-step + memory node growth.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .run_loader import RunData

# Ordered pipeline stages for the cooperative-startup scenario. A request whose
# type/title/role maps to a later stage that follows an earlier-stage request is
# counted as a plausible handoff (research -> offer -> outreach/sales).
_STAGE_ORDER = [
    "research",
    "offer",
    "outreach",
    "delivery",
    "finance",
]

# Keyword cues used to classify a request into a pipeline stage. Checked against
# the request type, title, and the submitting actor's scenario role.
_STAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "research": ("research", "market", "analysis", "niche", "lead", "prospect"),
    "offer": ("offer", "package", "design", "proposal", "pricing", "guarantee"),
    "outreach": ("outreach", "email", "contact", "sales", "send", "campaign"),
    "delivery": ("delivery", "fulfil", "fulfill", "onboarding", "deliver"),
    "finance": ("finance", "revenue", "budget", "cost", "spend", "points"),
}


def _classify_stage(text: str) -> str | None:
    """Return the first pipeline stage whose keywords appear in text."""
    low = text.lower()
    for stage in _STAGE_ORDER:
        if any(kw in low for kw in _STAGE_KEYWORDS[stage]):
            return stage
    return None


def _herfindahl(counts: list[int]) -> float:
    """Normalized Herfindahl-Hirschman concentration index in [0, 1].

    1.0 = fully concentrated (all activity in one category), ~0 = evenly diffuse.
    A single category is full concentration (1.0); no activity is 0.0.
    """
    total = sum(counts)
    if total <= 0:
        return 0.0
    n = len(counts)
    if n <= 1:
        # One observed category == maximal specialization.
        return 1.0
    shares_sq = sum((c / total) ** 2 for c in counts)
    # Normalize so an even split maps to 0 regardless of category count.
    return round((shares_sq - 1 / n) / (1 - 1 / n), 4)


def _submitted_requests(run: RunData) -> list[dict[str, Any]]:
    """Return only the original 'submit' request rows (state == proposed).

    requests.jsonl interleaves submit rows (with actor/type/title) and
    transition rows (with state/reviewer but no actor). Submit rows are the ones
    carrying the authoring metadata.
    """
    return [r for r in run.requests if r.get("actor") and r.get("title")]


def _request_states(run: RunData) -> dict[str, str]:
    """Map request id -> final state from transition rows (latest wins)."""
    states: dict[str, str] = {}
    for r in run.requests:
        rid = r.get("id")
        state = r.get("state")
        if rid and state and not r.get("actor"):
            states[rid] = state
    return states


def role_specialization(run: RunData) -> dict[str, Any]:
    """Per-persona request-type concentration vs. scenario role.

    Concentration is the Herfindahl index over each actor's request *types*;
    a focused specialist scores high, a generalist low. Also reports each
    actor's request types and titles next to its assigned role/mission.
    """
    roles = run.scenario_roles()
    submitted = _submitted_requests(run)
    by_actor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in submitted:
        by_actor[r["actor"]].append(r)

    per_actor: dict[str, Any] = {}
    for actor, reqs in by_actor.items():
        type_counts = Counter(r.get("type", "unknown") for r in reqs)
        per_actor[actor] = {
            "role": roles.get(actor, {}).get("role", ""),
            "mission": roles.get(actor, {}).get("mission", ""),
            "request_count": len(reqs),
            "type_distribution": dict(type_counts),
            "titles": [r.get("title", "") for r in reqs],
            "concentration": _herfindahl(list(type_counts.values())),
        }

    concentrations = [v["concentration"] for v in per_actor.values()]
    return {
        "per_actor": per_actor,
        "mean_concentration": round(
            sum(concentrations) / len(concentrations), 4
        )
        if concentrations
        else 0.0,
        "actors_with_requests": len(per_actor),
    }


def approval_rates(run: RunData) -> dict[str, Any]:
    """Per-actor request approval / rejection rates."""
    submitted = _submitted_requests(run)
    states = _request_states(run)
    per_actor: dict[str, dict[str, Any]] = {}
    for r in submitted:
        actor = r["actor"]
        rid = r.get("id")
        final = states.get(rid, "proposed")
        bucket = per_actor.setdefault(
            actor,
            {"submitted": 0, "approved": 0, "rejected": 0, "pending": 0},
        )
        bucket["submitted"] += 1
        if final == "approved":
            bucket["approved"] += 1
        elif final in ("rejected", "denied"):
            bucket["rejected"] += 1
        else:
            bucket["pending"] += 1

    for bucket in per_actor.values():
        decided = bucket["approved"] + bucket["rejected"]
        bucket["approval_rate"] = (
            round(bucket["approved"] / decided, 4) if decided else None
        )
    return {"per_actor": per_actor}


def request_coherence(run: RunData) -> dict[str, Any]:
    """Order requests over time and detect plausible cross-stage handoffs.

    Builds a stage-tagged, time-ordered sequence of submitted requests and counts
    adjacent (and near) transitions that move forward through the canonical
    research -> offer -> outreach -> delivery -> finance pipeline. A high forward
    ratio suggests coherent, dependency-respecting collaboration.
    """
    roles = run.scenario_roles()
    submitted = sorted(
        _submitted_requests(run), key=lambda r: r.get("created_at", "")
    )

    sequence: list[dict[str, Any]] = []
    for r in submitted:
        actor = r["actor"]
        role = roles.get(actor, {}).get("role", "")
        text = " ".join(
            [str(r.get("type", "")), str(r.get("title", "")), role]
        )
        sequence.append(
            {
                "actor": actor,
                "type": r.get("type", ""),
                "title": r.get("title", ""),
                "stage": _classify_stage(text),
                "created_at": r.get("created_at", ""),
            }
        )

    stages = [s["stage"] for s in sequence if s["stage"]]
    stage_index = {name: i for i, name in enumerate(_STAGE_ORDER)}
    forward = backward = same = 0
    handoffs: list[dict[str, str]] = []
    prev = None
    prev_item = None
    for item in sequence:
        cur = item["stage"]
        if cur is None:
            continue
        if prev is not None:
            di = stage_index[cur] - stage_index[prev]
            if di > 0:
                forward += 1
                handoffs.append(
                    {
                        "from_stage": prev,
                        "to_stage": cur,
                        "from_actor": prev_item["actor"],
                        "to_actor": item["actor"],
                        "to_title": item["title"],
                    }
                )
            elif di < 0:
                backward += 1
            else:
                same += 1
        prev = cur
        prev_item = item

    transitions = forward + backward + same
    return {
        "sequence": sequence,
        "stage_distribution": dict(Counter(stages)),
        "transitions": transitions,
        "forward_handoffs": forward,
        "backward_steps": backward,
        "same_stage": same,
        "forward_ratio": round(forward / transitions, 4) if transitions else 0.0,
        "handoffs": handoffs,
    }


def contribution(run: RunData) -> dict[str, Any]:
    """Per-agent points and revenue from rewards.jsonl (not just team total)."""
    per_actor: dict[str, dict[str, Any]] = {}
    source_breakdown: dict[str, Counter] = defaultdict(Counter)
    for rw in run.rewards:
        actor = rw.get("actor", "unknown")
        bucket = per_actor.setdefault(
            actor,
            {
                "points": 0,
                "revenue_cents": 0,
                "reward_count": 0,
                "valence_sum": 0,
            },
        )
        bucket["points"] += int(rw.get("points", 0) or 0)
        bucket["revenue_cents"] += int(rw.get("revenue_cents", 0) or 0)
        bucket["reward_count"] += 1
        bucket["valence_sum"] += int(rw.get("outcome_valence", 0) or 0)
        source_breakdown[actor][str(rw.get("source", "unknown"))] += 1

    for actor, bucket in per_actor.items():
        bucket["sources"] = dict(source_breakdown[actor])
        n = bucket["reward_count"]
        bucket["mean_valence"] = round(bucket["valence_sum"] / n, 3) if n else 0.0
        del bucket["valence_sum"]

    team_points = sum(b["points"] for b in per_actor.values())
    team_revenue = sum(b["revenue_cents"] for b in per_actor.values())
    return {
        "per_actor": per_actor,
        "team_points": team_points,
        "team_revenue_cents": team_revenue,
        "contributing_actors": len(per_actor),
    }


def _iter_chat_pairs(chat: Any) -> list[str]:
    """Extract speaker names from a persona scratch.chat value.

    chat is a list of [speaker, utterance] pairs (or None / empty).
    """
    speakers: list[str] = []
    if not isinstance(chat, list):
        return speakers
    for line in chat:
        if isinstance(line, (list, tuple)) and line:
            speakers.append(str(line[0]))
    return speakers


def social_network(run: RunData) -> dict[str, Any]:
    """Build an undirected conversation graph from movement metadata + chats.

    Edges come from two sources per step: (a) meta.conversations group
    participants (the authoritative grouping), and (b) co-speakers within a
    persona's chat transcript. Edge weight = number of steps the pair shared a
    conversation. Reports degree centrality and group-size stats.
    """
    edge_weights: Counter = Counter()
    node_degree: Counter = Counter()
    group_sizes: list[int] = []
    talk_steps = 0

    for _step, packet in sorted(run.movement.items()):
        meta = packet.get("meta", {}) if isinstance(packet, dict) else {}
        convs = meta.get("conversations", {}) if isinstance(meta, dict) else {}
        if not isinstance(convs, dict):
            convs = {}
        step_pairs: set[tuple[str, str]] = set()

        for group in convs.values():
            if not isinstance(group, dict):
                continue
            participants = [str(p) for p in group.get("participants", []) if p]
            if len(participants) >= 2:
                group_sizes.append(len(participants))
            for pair in _unordered_pairs(participants):
                step_pairs.add(pair)

        # Augment from per-persona chat transcripts (covers runs where
        # conversations metadata is sparse but chat lines exist).
        persona_map = packet.get("persona", {}) if isinstance(packet, dict) else {}
        if not isinstance(persona_map, dict):
            persona_map = {}
        for name, pdata in persona_map.items():
            if not isinstance(pdata, dict):
                continue
            speakers = set(_iter_chat_pairs(pdata.get("chat")))
            speakers.add(name)
            speakers.discard("")
            for pair in _unordered_pairs(sorted(speakers)):
                step_pairs.add(pair)

        if step_pairs:
            talk_steps += 1
        for pair in step_pairs:
            edge_weights[pair] += 1

    edges = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in sorted(edge_weights.items())
    ]
    for (a, b), w in edge_weights.items():
        node_degree[a] += w
        node_degree[b] += w

    n_nodes = len(run.persona_names) or len(node_degree)
    denom = max(n_nodes - 1, 1)
    centrality = {
        node: round(deg / denom, 4) for node, deg in node_degree.items()
    }
    return {
        "edges": edges,
        "edge_count": len(edges),
        "degree_centrality": centrality,
        "talk_steps": talk_steps,
        "group_size_mean": round(sum(group_sizes) / len(group_sizes), 3)
        if group_sizes
        else 0.0,
        "group_size_max": max(group_sizes) if group_sizes else 0,
        "conversation_instances": len(group_sizes),
    }


def _unordered_pairs(items: list[str]) -> list[tuple[str, str]]:
    """Return sorted unique unordered pairs from items."""
    uniq = sorted(set(i for i in items if i))
    pairs: list[tuple[str, str]] = []
    for i in range(len(uniq)):
        for j in range(i + 1, len(uniq)):
            pairs.append((uniq[i], uniq[j]))
    return pairs


def activity(run: RunData) -> dict[str, Any]:
    """Events-per-step, active-step ratio, memory growth, and step timing."""
    active_steps = 0
    total_steps = 0
    type_counts: Counter = Counter()
    timing_sums: dict[str, float] = defaultdict(float)
    timing_n = 0
    for ev in run.events:
        etype = ev.get("type", "unknown")
        type_counts[etype] += 1
        if etype == "simulation_step":
            total_steps += 1
            payload = ev.get("payload", {}) or {}
            if payload.get("had_new_action"):
                active_steps += 1
        elif etype == "step_timing":
            payload = ev.get("payload", {}) or {}
            timing_n += 1
            for key in ("perceive_ms", "move_ms", "serialize_ms", "total_ms"):
                val = payload.get(key)
                if isinstance(val, (int, float)):
                    timing_sums[key] += val

    movement_steps = sorted(run.movement.keys())
    timing: dict[str, Any] = {}
    if timing_n:
        timing = {
            "samples": timing_n,
            "mean_ms": {
                k: round(v / timing_n, 2) for k, v in sorted(timing_sums.items())
            },
        }
    return {
        "event_type_counts": dict(type_counts),
        "total_events": len(run.events),
        "simulation_steps": total_steps,
        "active_steps": active_steps,
        "active_step_ratio": round(active_steps / total_steps, 4)
        if total_steps
        else 0.0,
        "movement_step_range": (
            [movement_steps[0], movement_steps[-1]] if movement_steps else []
        ),
        "movement_snapshot_count": len(movement_steps),
        "memory_node_counts": dict(run.memory_counts),
        "total_memory_nodes": sum(run.memory_counts.values()),
        "step_timing": timing,
    }


def identity_drift(run: RunData) -> dict[str, Any]:
    """Per-persona identity-drift trajectory from `identity_drift` ledger events.

    Phase 4e emits an `identity_drift` event at each day boundary carrying a
    drift score in [0, 1] (0 = behavior fully consistent with the persona's
    ORIGINAL innate/learned traits, 1 = completely off-character) plus a note.
    This summarizes those checkpoints so the harness can flag personas whose
    behavior has drifted from who they started as.
    """
    per_actor: dict[str, dict[str, Any]] = {}
    for ev in run.events:
        if ev.get("type") != "identity_drift":
            continue
        actor = ev.get("actor") or "unknown"
        payload = ev.get("payload", {}) or {}
        score = payload.get("drift_score")
        try:
            score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            continue
        bucket = per_actor.setdefault(
            actor, {"checkpoints": [], "notes": []}
        )
        bucket["checkpoints"].append(score)
        note = payload.get("drift_note")
        if note:
            bucket["notes"].append(str(note))

    summary: dict[str, Any] = {}
    all_latest: list[float] = []
    for actor, bucket in per_actor.items():
        scores = bucket["checkpoints"]
        latest = scores[-1] if scores else 0.0
        all_latest.append(latest)
        summary[actor] = {
            "checkpoint_count": len(scores),
            "latest_drift": round(latest, 4),
            "mean_drift": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "max_drift": round(max(scores), 4) if scores else 0.0,
            "latest_note": bucket["notes"][-1] if bucket["notes"] else "",
        }

    return {
        "per_actor": summary,
        "actors_with_checkpoints": len(summary),
        "mean_latest_drift": round(sum(all_latest) / len(all_latest), 4)
        if all_latest
        else 0.0,
    }


def compute_metrics(run: RunData) -> dict[str, Any]:
    """Assemble the full structural-metrics payload for a run."""
    return {
        "schema_version": 1,
        "sim_code": run.sim_code,
        "scenario": {
            "id": run.meta.get("scenario_id") or run.scenario.get("id", ""),
            "name": run.meta.get("scenario_name") or run.scenario.get("name", ""),
            "objective": run.meta.get("scenario_objective")
            or run.scenario.get("objective", ""),
            "persona_count": len(run.persona_names),
        },
        "role_specialization": role_specialization(run),
        "approval_rates": approval_rates(run),
        "request_coherence": request_coherence(run),
        "contribution": contribution(run),
        "social_network": social_network(run),
        "activity": activity(run),
        "identity_drift": identity_drift(run),
    }


def gini(values: list[float]) -> float:
    """Gini coefficient of a list of non-negative values (0 = equal).

    Exposed as a small helper for contribution-equality framing in reports.
    """
    vals = sorted(v for v in values if v is not None)
    n = len(vals)
    if n == 0 or sum(vals) == 0:
        return 0.0
    cum = 0.0
    for i, v in enumerate(vals, start=1):
        cum += i * v
    return round((2 * cum) / (n * sum(vals)) - (n + 1) / n, 4)
