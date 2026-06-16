# Architectural Decisions

Lightweight ADR log for the Claudeville improvement pass. Each decision records context, the choice, alternatives, and consequences. Status: **Proposed** (needs sign-off) · **Accepted** · **Superseded** · **Rejected**.

Add a new `D-00N` entry whenever a non-obvious, hard-to-reverse, or cross-cutting choice is made. Link decisions from [PRD.md](PRD.md), [TECH-SPEC.md](TECH-SPEC.md), and [IMPROVEMENT-LOG.md](IMPROVEMENT-LOG.md).

> Decisions D-001…D-006 below were surfaced as open questions by the Phase 1 audit (see [PHASE-1-AUDIT.md](PHASE-1-AUDIT.md) §7). **All six were decided on 2026-06-16** (owner delegated the call). Status is now **Accepted**; rationale recorded inline.

---

## D-001 — Memory: restore relevance-based retrieval, or formally retire to recency-only?
- **Status:** ✅ **Accepted 2026-06-16 — Restore** — **blocks PRD G2 / Phase B**
- **Decision rationale:** Claudeville is a *Generative Agents* fork; recall-by-relevance + reflection is the product's defining capability. Retiring to recency-only would abandon the thesis and reduce agents to recency puppets. We restore using the existing keyword×recency×importance scaffolding (no embeddings — see D-002), gated behind a config flag and validated by a scripted recall test (PRD §4 metric).
- **Context:** The README advertises "keyword + recency scoring," but the live path (`_get_recent_memories`) does no relevance matching and importance is a constant; `retrieve_relevant_events/thoughts` + keyword indexes are dead code (MEM-1, MEM-2, MEM-7). This is the central product question — it decides whether the agents are "generative."
- **Options:**
  - **(A) Restore** keyword × recency-decay × importance scoring (wire up the existing dead functions; have the LLM emit per-event importance; reconnect a reflection trigger). Higher fidelity, more LLM cost, behavior shift.
  - **(B) Retire** — delete the dead machinery, document retrieval as recency-only, drop the unused importance/reflection fields. Simpler, cheaper, lower fidelity; abandons the paper's thesis.
- **Recommendation:** **(A) Restore**, behind a config flag, validated on a scripted recall scenario. It is the product's reason to exist.
- **Consequences:** Drives BC-5, BC-8; affects token cost (D-005); requires the relevance-test metric in PRD §4.

## D-002 — Do NOT re-introduce embeddings in this pass
- **Status:** ✅ **Accepted 2026-06-16 — non-goal confirmed**
- **Context:** The fork deliberately removed `text-embedding-ada-002`/cosine similarity. Restoring relevance (D-001) can be done with keyword+recency+importance without embeddings.
- **Decision:** Embeddings/vector-DB retrieval is out of scope (PRD non-goal). Revisit as a separate future initiative if keyword relevance proves insufficient.
- **Consequences:** Keeps the dependency surface small; no vector store, no embedding API/auth.

## D-003 — Model & context-window policy
- **Status:** ✅ **Accepted 2026-06-16 — Sonnet 4.6 default, configurable, model-derived window** — **blocks LLM-6**
- **Context:** `DEFAULT_CLAUDE_MODEL = claude-sonnet-4-6` (valid), but docstrings claim "Opus," and `MAX_CONTEXT_TOKENS = 200000` is wrong for Sonnet 4.6 (1M window), so compaction math is off (LLM-6, LLM-9).
- **Decision rationale:** A run is N personas × many steps × per-step LLM calls, so cost/latency dominate — Sonnet 4.6 is the right default. Keep it, but make the model a single configurable value and **derive the context window from the model id** (not a literal). Expose Opus 4.8 as an opt-in for high-agency runs. Correct the misleading "Opus" docstrings. The real defect (the hardcoded 200K window) is fixed regardless.
- **Consequences:** Drives BC-7; changes compaction timing; needs the compaction regression test.

## D-004 — Transport: SSE/WebSocket vs polling-with-backoff
- **Status:** ✅ **Accepted 2026-06-16 — pause-aware backoff (Phase A), SSE (Phase C) with polling fallback**
- **Context:** 100% polling (health 3s / town 7s / pipeline 1s) drives constant load and the 984 KB log (FE-2, FE-3).
- **Decision:** Quick mitigation now (stop timers while paused, back off when idle); commit to a single SSE stream in Phase C with a polling fallback for one release (BC-9).
- **Consequences:** Drives BC-9, R-10; interacts with the Django→Flask double hop.

## D-005 — Cost controls: cap tokens and add a spend ceiling
- **Status:** ✅ **Accepted 2026-06-16**
- **Context:** No `max_tokens`, no spend ceiling; retries/compaction can multiply cost (LLM-7, LLM-8).
- **Decision:** Set explicit `max_tokens` on SDK options; aggregate usage into a per-run cost estimate; add a configurable per-run/per-persona ceiling that halts or degrades. Stop re-sending the static rulebook every step.
- **Consequences:** Bounds runaway spend; interacts with D-001/D-003 token budgets; R-8.

## D-006 — Concurrency model: world-snapshot + serial-apply (not locks)
- **Status:** ✅ **Accepted 2026-06-16** — **the core of G1**
- **Context:** Personas run concurrently over shared mutable state with no synchronization (ARCH-1), and timeouts abandon mutating coroutines (ARCH-2).
- **Decision:** Adopt **snapshot → concurrent read-only decide → collect intended mutations → apply serially in deterministic order**. Prefer this over fine-grained locking: it yields determinism (a PRD success metric) and is far easier to reason about and test. ARCH-2 (per-coroutine timeout + proper cancel/await) is the interim mitigation before the full snapshot engine lands in Phase C.
- **Consequences:** Enables the determinism harness; removes `random.sample` nondeterminism (MEM-8); R-1, R-4.

---

## Decision index

| ID | Decision | Status | Blocks |
|----|----------|--------|--------|
| D-001 | Restore generative memory (keyword×recency×importance, no embeddings) | ✅ Accepted | G2 / Phase B |
| D-002 | No embeddings this pass | ✅ Accepted | — |
| D-003 | Sonnet 4.6 default, configurable, model-derived window | ✅ Accepted | LLM-6 |
| D-004 | Backoff now (A) + SSE later (C) with fallback | ✅ Accepted | FE-2 |
| D-005 | Token cap + spend ceiling | ✅ Accepted | LLM-7/8 |
| D-006 | Snapshot + serial-apply concurrency | ✅ Accepted | G1 / ARCH-1/2 |

_All decisions accepted 2026-06-16. Revisit only if implementation surfaces a contradicting constraint (record as a superseding D-00N entry)._
