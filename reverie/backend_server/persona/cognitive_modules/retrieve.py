"""
Original Author: Joon Sung Park (joonspk@stanford.edu)
Heavily modified for Claudeville (Claude CLI port)

File: retrieve.py
Description: Relevance-based retrieval for generative agents (Gen Agents paper).

Claudeville hard constraint (D-002): NO vector embeddings. Relevance is computed
from keyword overlap only; recency from a decay over created-order rank; and
importance from node poignancy. This keeps retrieval keyword/recency/LLM-only.
"""


def _normalize(scores):
    """Min-max normalize a list of floats to 0..1.

    If all values are equal (including a single element), every score maps to
    1.0 so a present-but-uniform signal still contributes its full weight rather
    than collapsing to zero.
    """
    if not scores:
        return []
    lo = min(scores)
    hi = max(scores)
    if hi == lo:
        return [1.0 for _ in scores]
    span = hi - lo
    return [(s - lo) / span for s in scores]


def _gather_candidates(persona, focal_keywords):
    """Collect unique candidate event + thought nodes for the focal keywords.

    Uses the associative memory keyword indexes (kw_to_event / kw_to_thought via
    retrieve_relevant_*). De-duplicates by node_id, preserving first sight.
    """
    a_mem = persona.a_mem
    candidates = {}
    for kw in focal_keywords:
        if not kw:
            continue
        for node in a_mem.retrieve_relevant_events(kw, kw, kw):
            candidates[node.node_id] = node
        for node in a_mem.retrieve_relevant_thoughts(kw, kw, kw):
            candidates[node.node_id] = node
    return list(candidates.values())


def _relevance(node, focal_set):
    """Keyword-overlap fraction between a node's keywords and the focal set."""
    if not focal_set:
        return 0.0
    node_kw = {str(k).lower() for k in (node.keywords or [])}
    if not node_kw:
        return 0.0
    overlap = node_kw & focal_set
    return len(overlap) / len(focal_set)


def retrieve_focal(persona, focal_keywords, n=8):
    """
    Retrieve the top-n most relevant memory nodes for the focal keywords.

    Scoring (Gen Agents): a weighted sum of three min-max normalized signals
      score = recency_w*recency + relevance_w*relevance + importance_w*importance
    where
      recency    = recency_decay ** age_rank   (rank 0 = most recent by created)
      relevance  = keyword-overlap fraction vs focal_keywords
      importance = poignancy / 10

    Side effect: updates each returned node's last_accessed to curr_time.

    INPUT:
      persona: the <Persona> whose memory we search.
      focal_keywords: iterable of keyword strings to focus retrieval on.
      n: number of top nodes to return.
    OUTPUT:
      A list of <ConceptNode> sorted by descending combined score (top-n).
    """
    focal_set = {str(k).lower() for k in focal_keywords if k}
    candidates = _gather_candidates(persona, focal_keywords)
    if not candidates:
        return []

    # Recency rank: order candidates by created time (newest first). The newest
    # node gets age_rank 0 -> recency_decay**0 = 1.0; older nodes decay.
    by_created = sorted(
        candidates,
        key=lambda nd: nd.created,
        reverse=True,
    )
    decay = getattr(persona.scratch, "recency_decay", 0.99)
    rank_of = {nd.node_id: rank for rank, nd in enumerate(by_created)}

    recency_raw = [decay ** rank_of[nd.node_id] for nd in candidates]
    relevance_raw = [_relevance(nd, focal_set) for nd in candidates]
    importance_raw = [(nd.poignancy or 0) / 10.0 for nd in candidates]

    recency = _normalize(recency_raw)
    relevance = _normalize(relevance_raw)
    importance = _normalize(importance_raw)

    rw = getattr(persona.scratch, "recency_w", 1)
    rel_w = getattr(persona.scratch, "relevance_w", 1)
    iw = getattr(persona.scratch, "importance_w", 1)

    scored = []
    for i, node in enumerate(candidates):
        score = rw * recency[i] + rel_w * relevance[i] + iw * importance[i]
        scored.append((score, node))

    # Stable, deterministic ordering: score desc, then most-recent first.
    scored.sort(key=lambda pair: (pair[0], pair[1].created), reverse=True)

    top = [node for _, node in scored[:n]]

    # Update last_accessed for retrieved nodes (Gen Agents recency bookkeeping).
    curr_time = getattr(persona.scratch, "curr_time", None)
    if curr_time is not None:
        for node in top:
            node.last_accessed = curr_time

    return top
