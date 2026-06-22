"""
Original Author: Joon Sung Park (joonspk@stanford.edu)
Heavily modified for Claudeville (Claude CLI port)

File: reflect.py
Description: Reflection module for generative agents (Gen Agents + RMM).

When the persona's importance_trigger_curr drops to <= 0, the persona reflects:
it gathers its most salient recent memories, asks the model (one OCCASIONAL extra
LLM call) for a few higher-level insight statements, and stores each insight as a
thought node whose `filling` backlinks the source nodes (depth > 0).

Claudeville hard constraint (D-002): retrieval here is recency + importance only,
no vector embeddings.
"""

import datetime

# How many salient recent nodes to feed the reflection prompt.
REFLECTION_SOURCE_COUNT = 15
# Insight thought nodes get a long shelf life like other reflections.
REFLECTION_EXPIRATION_DAYS = 30


def gather_reflection_sources(persona, count=REFLECTION_SOURCE_COUNT):
    """Return the most salient recent event+thought nodes for reflection.

    Salience = poignancy, recency-tie-broken. We pull from the most recent slice
    of memory (seq_* are newest-first) then rank by poignancy so insights are
    grounded in what mattered lately.
    """
    a_mem = persona.a_mem
    pool = []
    pool.extend(a_mem.seq_event[: count * 2])
    pool.extend(a_mem.seq_thought[: count * 2])

    # Skip idle filler that carries no insight value.
    pool = [n for n in pool if "is idle" not in (n.description or "")]

    pool.sort(
        key=lambda nd: (nd.poignancy or 0, nd.created),
        reverse=True,
    )
    return pool[:count]


def store_reflection_insights(persona, insights, source_nodes):
    """Store each insight string as a backlinked thought node (depth > 0).

    `filling` is the list of source node_ids -> add_thought derives depth as
    1 + max(source depth), guaranteeing depth > 0 for reflections.

    Returns the list of created thought ConceptNodes.
    """
    created = persona.scratch.curr_time
    expiration = None
    if created is not None:
        expiration = created + datetime.timedelta(days=REFLECTION_EXPIRATION_DAYS)
    source_ids = [n.node_id for n in source_nodes]
    name = persona.scratch.name

    made = []
    for insight in insights:
        text = (insight or "").strip()
        if not text:
            continue
        keywords = {"reflection", "insight"}
        node = persona.a_mem.add_thought(
            created,
            expiration,
            name,
            "reflect",
            text[:50],
            text,
            keywords,
            # Reflections are high-salience by construction.
            8,
            text,
            list(source_ids),
        )
        made.append(node)
        # Phase 3 (optional): if a reflection insight is about someone we already
        # know, record it as a first-person belief on the relationship model.
        # Reuses Phase-1 reflection output -- no new LLM call (D-002).
        _maybe_refine_belief(persona, text)
    return made


def _maybe_refine_belief(persona, insight_text):
    """Attach an insight as a belief about a known persona it mentions (3).

    Heuristic: if the insight text contains the name of a persona we already
    have a relationship record for, store the insight as a short first-person
    belief about them. Safe no-op when the persona has no relationship memory.
    """
    r_mem = getattr(persona, "r_mem", None)
    if r_mem is None or not getattr(r_mem, "relationships", None):
        return
    lowered = insight_text.lower()
    for rec in list(r_mem.relationships.values()):
        rec_name = rec.get("name") or ""
        if not rec_name:
            continue
        # Match on any token of the recorded name (first name is enough).
        if any(
            part and part.lower() in lowered for part in rec_name.split()
        ):
            r_mem.add_belief(rec_name, insight_text[:120])
