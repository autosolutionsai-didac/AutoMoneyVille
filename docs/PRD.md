# Claudeville Improvement Pass — Product Requirements Document (PRD)

- **Version:** 1.0 (2026-06-16)
- **Grounded in:** [PHASE-1-AUDIT.md](PHASE-1-AUDIT.md) — every goal below traces to a finding ID.
- **Companion:** [TECH-SPEC.md](TECH-SPEC.md) (architecture & migration), [DECISIONS.md](DECISIONS.md) (ADRs), [IMPROVEMENT-LOG.md](IMPROVEMENT-LOG.md) (execution tracking).
- **Owner:** (assign) · **Status:** Draft for approval

---

## 1. Problem statement

Claudeville successfully re-architected Stanford's Generative Agents onto the Claude Agent SDK and a game-like UI. It runs — but the Phase 1 audit found that the qualities that make the system *correct, trustworthy, and "generative"* have eroded, mostly invisibly:

1. **The simulation is not correct under concurrency.** Every persona runs concurrently over shared, unlocked world state, and the per-step timeout abandons coroutines that keep mutating that state into the next step. Results are nondeterministic and can corrupt persona memory (ARCH-1, ARCH-2).
2. **The agents stopped being "generative."** Relevance-based memory retrieval and reflection — the heart of the original paper — are present in code but **dead/inert**. Agents recall by recency only, and importance is a constant. The README advertises behavior the system does not perform (MEM-1, MEM-2).
3. **The LLM integration fails silently and unsafely.** Malformed responses and API errors both collapse to "idle" with no telemetry, so a whole run can stall invisibly (LLM-2); there is no transport retry/backoff (LLM-3); and one persona's dialogue is injected verbatim into another's prompt, reaching a privileged human-approval capability (LLM-1).
4. **Basic security & reproducibility hygiene is missing.** CSRF is disabled, the Django `SECRET_KEY` is hardcoded with `DEBUG=True`, LLM output is written to the DOM unescaped, there is no CI, and dependencies are unpinned (OPS-1, OPS-2, FE-6, OPS-3, OPS-5).
5. **It won't scale over a long run.** Memory grows unbounded with O(n) per-step scans and full-file rewrites; pathfinding is O(W·H) per wave-step and silently fails on long paths; the UI polls three endpoints forever (MEM-5, MEM-3, FE-2).

**Net:** the project is a strong prototype carrying correctness, fidelity, safety, and scaling debt. This improvement pass pays down that debt in priority order without rewriting the product.

---

## 2. Goals (ranked by impact)

Ranked by (severity × blast radius × cost-to-leave). Each goal lists the findings it closes.

| # | Goal | Closes | Why it's ranked here |
|---|------|--------|----------------------|
| **G1** | **Make a simulation step correct under concurrency** — snapshot world state, apply mutations serially, cancel/await timed-out work properly | ARCH-1, ARCH-2, ARCH-17 | Highest blast radius: silent state corruption invalidates *every* downstream behavior and makes all other work unmeasurable. |
| **G2** | **Restore (or formally retire) generative memory** — relevance retrieval + real importance + reflection, or a documented recency-only model | MEM-1, MEM-2, MEM-7, MEM-6 | This *is* the product thesis. The system currently under-delivers its headline feature. |
| **G3** | **Harden the LLM call path** — robust parsing, telemetry on failure, transport retry/backoff, validated outputs | LLM-2, LLM-3, LLM-4, LLM-5, LLM-6 | Reliability floor: without it, runs stall invisibly and cost is unbounded. |
| **G4** | **Close the multi-agent prompt-injection vector** — treat persona text as untrusted data | LLM-1 | Safety: a privileged capability (`town_request`/`external_action`) is reachable from model-authored text. |
| **G5** | **Quick security & hygiene wins** — CSRF on, secrets/DEBUG from env, escape DOM output, add CI, pin deps | OPS-1, OPS-2, FE-6, OPS-3, OPS-5, OPS-6 | Cheap (mostly Quick Wins), high embarrassment/risk reduction, and CI protects all later work. |
| **G6** | **Fix scaling walls** — bounded memory + expiration, frontier-queue pathfinding, materialized town-center view | MEM-5, MEM-3, MEM-8, ARCH-9, MEM-12 | Determines whether long simulations are viable at all. |
| **G7** | **Decompose the monolith & unify persistence** — split `ReverieServer`, single storage path, atomic saves | ARCH-3, ARCH-6, ARCH-7, ARCH-4, ARCH-5 | Makes everything above testable and maintainable; enables the background-worker `/simulate`. |
| **G8** | **Backfill tests for the inherited core** — deterministic units + a fake SDK client; raise coverage | OPS-4, OPS-8 | Locks in G1–G7 and prevents regressions. |
| **G9** | **Modernize the transport & frontend** — SSE/pause-aware polling, extract inline JS, logging config | FE-2, FE-3, FE-4, FE-5, FE-9 | Highest effort, lowest correctness risk — do last, behind the stabilized backend. |

---

## 3. Non-goals (explicitly out of scope for this pass)

- **No product/feature expansion.** The Roadmap items in `README.md` (minimap, click-to-follow, lecture scenarios, smart persona-panel ordering) are deferred. This pass is debt paydown, not feature work.
- **No re-introduction of embedding-based retrieval / a vector DB.** G2 restores relevance using the *existing* keyword+recency+importance scoring (or formally retires it). Adding embeddings is a separate future decision (see [DECISIONS.md](DECISIONS.md) D-002).
- **No change to the Claude Agent SDK dependency or auth model.** We keep ambient (subscription) auth and `allowed_tools=[]`; we do not add API-key handling.
- **No migration off Django/Flask/Phaser.** We improve them in place; we do not adopt React/FastAPI/a new game engine.
- **No git history rewrite for asset bloat.** OPS-7 is addressed at HEAD only (drop ZIPs from tracking, reconcile pending deletions); rewriting history/LFS migration is a separate, opt-in operation.
- **No multiplayer / multi-process / horizontal scaling.** Single-process is assumed throughout.
- **No changes to game art assets or map design** beyond what FE-1 (sprite loading) and OPS-7 (tracking) require.
- **No production deployment / hosting work.** We make the app *deployable-safe* (G5) but do not stand up infra.

---

## 4. Success metrics

Targets are measurable and checked at phase exit. Where no baseline exists today, the first task is to **establish the baseline**, then hit the target.

| Area | Metric | Baseline (today) | Target |
|------|--------|------------------|--------|
| **Correctness (G1)** | Determinism: same seed + same scripted inputs → identical persona positions/actions over N=50 steps | Non-deterministic (unsynchronized shared state) | Bit-identical across 3 runs |
| | Cross-step state-corruption incidents under induced timeout (test harness) | Reproducible corruption | 0 |
| **Memory fidelity (G2)** | Retrieval relevance: in a scripted recall scenario, the relevant memory appears in the prompt's memory section | ~0% (recency-only) | ≥ 90% of scripted cases (if G2=restore) **or** documented & dead code removed (if G2=retire) |
| | Reflection fires when importance threshold crossed | Never | Fires within expected step window in test |
| **LLM reliability (G3)** | Silent idle-stalls attributable to unlogged parse/API errors | Untracked (invisible) | 0 silent; 100% of failures emit a typed metric |
| | Transport-error recovery rate (injected 429/529/timeout) | 0% (no retry) | ≥ 95% recovered within backoff budget |
| | Malformed-JSON parse-survival (fuzzed responses) | greedy regex, brittle | ≥ 99% parsed or cleanly degraded with telemetry |
| **Safety (G4)** | Injection-corpus test: persona lines crafted to issue instructions/`town_request` to others | Vulnerable | 0 successful injections |
| **Security/hygiene (G5)** | CSRF enabled on mutating endpoints | Disabled | Enabled, tests pass |
| | Secrets/DEBUG sourced from env (no hardcoded prod-affecting values) | Hardcoded | 0 hardcoded; `DEBUG=False` default |
| | CI: tests + ruff + format run on every push/PR | None | Green required check |
| | Dependencies pinned + lockfile committed | Floors only | 100% pinned, lockfile present |
| **Scaling (G6)** | Pathfinding worst-case cell visits per query | ~2.1M (150×14k) | O(V+E) ≈ ≤ 14k; no silent path failure |
| | Per-step memory-retrieval cost growth over a 500-step run | O(history) (linear growth) | O(window) (flat) |
| | Long paths (> 150 tiles) resolved correctly | Silently fail to `[end]` | Correct path or explicit "no path" |
| **Maintainability (G7)** | Largest class/file LOC | `ReverieServer` ~1700 | No single class > 600 LOC; storage via one path |
| | `save()` atomicity (crash-injection mid-save) | Corrupts run | Atomic (temp+rename); 0 corrupt runs |
| **Tests (G8)** | Line coverage on deterministic core (`path_finder`, `maze`, `associative_memory`, `scratch`, `parse_step_response`) | ~0% | ≥ 70% |
| | Overall measured coverage (tooling introduced) | Not measured | Reported in CI; ratchet upward |
| **Frontend (G9)** | Backend log volume per idle hour | ~ hundreds of KB (3s polling) | < 5% of baseline (SSE or pause-aware) |
| | Inline JS in `main_script.html` | 1561 lines | Extracted to ≥ 1 lintable static module |

> **Instrumentation note:** several metrics (token usage, latency, failure counts) require the telemetry added in **G3** to even be measured. Adding measurement is itself a Phase-1/2 deliverable, not an afterthought.

---

## 5. Phased delivery

Three phases by *remediation effort per item* (per the audit's effort buckets), sequenced so that safety/correctness land early and CI protects everything after. Items reference finding IDs; full detail in [PHASE-1-AUDIT.md](PHASE-1-AUDIT.md).

### Phase A — Quick Wins (< 1 day each) · 22 items
Independent, low-risk, high-value. CI lands first so the rest is protected.

- **OPS-3** — Add `.github/workflows/ci.yml` (build env, run both test suites, ruff, format check). *Do first.*
- **OPS-5** — Pin dependencies + commit a lockfile; pin `claude-agent-sdk`.
- **OPS-6** — Expand ruff (`I,B,UP,S`); reconcile pre-commit ruff version.
- **OPS-1** — Re-enable CSRF; remove `@csrf_exempt`; send `X-CSRFToken` from JS.
- **OPS-2** — `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` from env; rotate key.
- **FE-6** — Escape persona/LLM text (`textContent` instead of `innerHTML`).
- **FE-3** — Add `LOGGING` config to silence `django.server` 2xx access lines.
- **LLM-4** — Coerce/clamp `duration_minutes`; validate event triple.
- **MEM-4** — Guard `scratch.save()` `None` times; fix line-211 variable bug.
- **MEM-6** — Fix `get_str_seq_*` f-string tuple bug.
- **MEM-7** — Fix `retrieve_relevant_events` case-sensitivity.
- **MEM-9** — Unify "action finished" on `>=` datetime compare.
- **MEM-10** — Narrow `add_thought` exception; log dangling refs.
- **ARCH-4** — Acquire `_step_lock` (or snapshot) in read/save routes.
- **ARCH-10** — Serialize ledger writes; tolerate trailing partial line; `fsync` critical events.
- **ARCH-11** — Replace private-attr access with explicit Persona methods.
- **ARCH-12** — Validate client-supplied positions (bounds + missing key).
- **ARCH-16** — Read `meta.json` once, write once.
- **LLM-9 / MEM-13** — Hoist magic numbers to named config; fix `MAX_CONTEXT_TOKENS`.
- **ARCH-13/14/15, LLM-12/13, FE-7/8, OPS-9/10** — Remaining low-severity QWs (dead guards, stable hash, fuzzy-match, gitattributes, template dupes, CSS variables).
- **FE-2 (partial)** — Pause-aware polling backoff (the QW slice of the SSE goal).
- **OPS-7 (partial)** — Reconcile the 26 pending deletions so `HEAD == working tree`.

**Phase A exit gate:** CI green and required; security QWs merged; `HEAD == working tree`.

### Phase B — Structural Improvements (1–3 days each) · 27 items
Bounded refactors with tests. Most product value lands here.

- **G1 core — ARCH-2:** cancel/await timed-out coroutines; per-persona timeout inside the coroutine.
- **G2 — MEM-1, MEM-2:** wire relevance retrieval (keyword × recency × importance) and real per-event importance + reflection trigger (pending **D-001** decision).
- **G3 — LLM-2, LLM-3, LLM-5, LLM-6:** fenced+balanced JSON parsing with telemetry; transport retry/backoff + reconnect; state-transition compaction with safe summary fallback; correct cumulative token accounting.
- **G4 — LLM-1:** delimited/escaped untrusted-text block + standing system instruction.
- **G6 — MEM-3, MEM-5, MEM-8, ARCH-9:** frontier-queue BFS + cached collision map; bounded memory window + expiration sweep; single multi-source BFS per move; materialized town-center view.
- **G7 (partial) — ARCH-5, ARCH-6, ARCH-7:** background-worker `/simulate`; atomic saves via `RunStorage`; unify storage paths.
- **G8 — OPS-4, OPS-8:** deterministic unit tests + fake SDK client; standardize test import root; document test command.
- **ARCH-8, FE-5, FE-9, OPS-7 (full), MEM-11/12:** cursor-based `/movements`; consistent view error handling; fire-and-poll proxy; asset-tracking cleanup; LoS/chat-bound fixes.

**Phase B exit gate:** determinism test passes; G2 decision implemented & measured; LLM telemetry live; coverage ≥ 70% on deterministic core.

### Phase C — Deep Refactors (1+ week each) · 6 items
Highest effort, lowest correctness risk — sequenced last, on a stabilized, tested base.

- **G1 — ARCH-1:** full per-step world-snapshot / serial-apply model (the proper concurrency architecture; ARCH-2 is the interim mitigation).
- **G7 — ARCH-3:** decompose `ReverieServer` into `StepEngine` / `ConversationManager` / `ReverieHTTPApp` / `SimulationCLI` / persistence.
- **G3 — LLM-10:** encapsulate per-persona state in an injectable client (kills module globals; enables real LLM-path tests).
- **G9 — FE-2 (full), FE-4:** SSE/WebSocket transport; extract the 1561-line inline JS into ES modules with a data-island handshake.
- **(carry) LLM-11:** move compaction out of `_send_prompt`'s tail; hold the per-persona lock across query+receive.

**Phase C exit gate:** all success metrics in §4 met; audit findings closed or explicitly deferred with rationale in [DECISIONS.md](DECISIONS.md).

---

## 6. Dependencies & sequencing rules

- **CI (OPS-3) is the very first task** — nothing else is safe to merge without it.
- **G1 (concurrency) precedes performance work (G6):** you cannot benchmark or trust latency numbers on a racy base.
- **G3 telemetry precedes most success-metric measurement** — reliability/cost/latency are unmeasurable until failures are observable.
- **G7 decomposition (Phase C) depends on G8 tests (Phase B)** — don't refactor the monolith without a safety net.
- **The G2 memory direction (D-001) must be decided before Phase B starts** — it changes whether MEM-1/MEM-2/MEM-7 are "implement" or "delete + document."

---

## 7. Approval checklist

- [x] Problem statement and goal ranking accepted
- [x] **D-001** memory direction decided — **Restore** relevance (2026-06-16)
- [x] **D-003** model/context policy decided — **Sonnet 4.6 default, configurable, model-derived window** (2026-06-16)
- [x] **D-004** transport decision — **backoff now + SSE later with fallback** (2026-06-16)
- [x] Success-metric targets ratified (baseline-then-target where no baseline exists)
- [x] **Phase A authorized and started** (2026-06-16) — see [IMPROVEMENT-LOG.md](IMPROVEMENT-LOG.md)
