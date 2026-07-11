# Claudeville — Development Diary (DEVLOG)

> A living, human-readable journal of what we built, *why*, and what we discovered along the way.
> This is the **narrative** companion to two more formal artifacts:
> - [`IMPROVEMENT-LOG.md`](IMPROVEMENT-LOG.md) — the terse, per-merge factual change log (finding IDs, verification, commit).
> - [`PAPER.md`](PAPER.md) — the publication-grade academic write-up of the system as a whole.
>
> **Discipline:** add an entry here whenever something meaningful ships, breaks, or is *discovered*.
> Entries are **reverse-chronological** (newest first). Keep prose; record the reasoning and the dead ends,
> not just the diff. A reusable entry template lives at the [bottom](#how-to-add-an-entry).

**Status at last update:** research prototype. Direction: **building toward real-world money**
(staged, safety-first). The economy has been **measured** (17/17 requests died at the absent approval gate)
and its missing organ built: a human **transaction console** (draft review → approve → persisted artifact →
`record_delivery` with typed evidence).
**Test baseline:** backend + eval + emergence + economy + HTTP-route + Django suites all green; `ruff` clean.
**Live search:** Firecrawl is the default provider and is **verified working** (real results into agent memory).

---

## 2026-07-11 — Phase 1 "Make it watchable": the sim becomes legible, honest, and operable

**What & why.** First phase of the next-level roadmap (built from an 8-report review: 5 code reviews +
3 SOTA research sweeps). The story was invisible (chat wiped itself after 5s; an agent was one emoji),
the console's primary action was a trap, the operator was never summoned, and real errors were being
swallowed. Phase 1 fixes the *experience* of the existing sim without touching art or cognition (Phase 2).

- **Engine honesty (E1)**: stopped redirecting process-wide `sys.stderr` to devnull in `run_flask`
  (every traceback from every thread was being discarded — incl. port-bind failures); `meta.json` saves
  are atomic now; `_pending_movements` capped (headless runs no longer grow RAM unboundedly); encounter
  pairs run **concurrently across pairs** and are **deduped per persona** (fixed a latent double-move:
  three personas meeting at once used to move A and B twice in one step); the promised-but-missing LLM
  semaphore exists (`CLAUDEVILLE_LLM_CONCURRENCY`, default 10) around connects + prompts; ~160 junk
  empty dirs (an exploded heredoc) purged from the app root.
- **Console fixed (D1)**: **Approve now executes** (`execute: true` chains approved→completed server-side:
  one click = approve + run tool + artifact + agent memory feed — previously Approve parked requests in
  unreachable limbo); full **approval-queue browser** (risk-sorted, sticky selection) instead of queue[0];
  **reviewer-note textarea** (agents read `last_note` back in their prompts — the operator's one steering
  channel finally has an input); **artifact browser** with full DRY-RUN draft bodies; panel collision fixed.
- **Operator summons (D2)**: browser Notification (permission asked on Play) + title-bar `(N)` badge +
  chime + toast when a new approval-required request lands — directly re-attacking the measured 17/17
  failure mode. Telegram tier stays P3.
- **Agent inspector (C1)**: click a persona → live drawer (currently, schedule w/ current block, goals,
  relationships, last-20 memory stream) via new `GET /persona/<name>/state` + Django proxy. The sim's
  whole point — agent cognition — is finally visible while it runs.
- **Event feed (C2)**: 500-event ring buffer + `GET /events?after_id=` + left panel with All/Chats/
  Economy/Sim filters; conversation start/end, requests (with NEEDS-YOUR-APPROVAL), transitions, real
  revenue, day rolls, autosaves; chat lines mirror into the feed permanently (the popup's 5s amnesia is
  no longer the only record); rows jump the camera or open the inspector.
- **Juice pass (A1+A2)**: contact shadows under sprites; the shipped-but-unused speech-bubble art now
  backs every emoji with a Back.easeOut pop on change (and sits ABOVE the night overlay — thoughts were
  being dimmed after dark); lerped **follow-cam** with a 🎥 toggle (auto-follow used to be hardcoded and
  fought manual panning); pointer-centered wheel zoom; day/night is now an hour-keyed **MULTIPLY color
  ramp** (dawn amber → clear → dusk orange → deep-blue night) instead of a flat black fade.
- **UX honesty (C6/C7)**: busy states show a live elapsed counter; first Play says "First step calls
  Claude for N personas (~60-120s)"; `/replay/` pages stop polling the live backend (they used to
  poll-and-reload against whatever sim was running — effectively broken) and wear a REPLAY badge;
  duplicate hidden-data DOM ids removed; **Space = play/pause** (Shift+Space = skip); first-run hint
  overlay; the saves-list `alert()` replaced with a disabled state.

**Verification.** 208 backend + 28 eval + 34 Django tests green (5 new route tests: approve-executes
chaining + idempotent rewards, persona-state snapshot incl. schedule-index, events cursor); `ruff` clean;
replay page renders every new surface with zero duplicate ids; live launcher smoke.
**Discoveries / surprises.** (1) Windows PowerShell 5.1 reads no-BOM UTF-8 scripts as ANSI — an em-dash
in a launcher string became a curly quote that *terminated the string*, killing the script with a parse
error pwsh 7 never sees. The launcher is ASCII-only now. (2) The overlapping-encounter double-move had
been silently costing an extra LLM call and overwriting movements whenever 3+ personas met.

**What & why.** First **measurement** of the request economy, then the fix it demanded. The new
`tools/eval/economy.py` (mirrors the emergence-report pattern; `python -m tools.eval.economy <sim_code>`)
mined the recorded runs and produced the headline: in the 1578-step 10-person run, agents filed **17
requests and every one died at `proposed`** — 0 transitions, 0 tool executions, 0 revenue. The economy's
binding constraint isn't agent capability; it's that **no human-approval surface existed**. Striking detail
from the pending queue: Felix Reed sourced *named real prospects* (a Reddit content strategist; "Kate R."
on LinkedIn) and designed per-message human-approval gates into his own proposals; Sofia Lane (risk officer)
autonomously **HELD** the email channel pending a risk checklist. Emergent governance, starved by an absent
reviewer. So we built the reviewer's organ:
- **Artifacts persist** (`economy.ArtifactLedger` → `town_center/artifacts.jsonl`): executed ToolResults
  (incl. dry-run drafts) previously vanished after the one-shot HTTP response — `transition_request`
  appended the transition row *before* attaching `tool_result`, so nothing auditable ever reached disk.
  Now every execution leaves a durable row, surfaced in `snapshot()["artifacts"]`.
- **`record_delivery` finally reachable**: `POST /town-center/requests/<id>/record-delivery` (Flask) +
  `api/town-center/requests/<id>/record-delivery/` (Django proxy that forwards 4xx bodies verbatim so form
  errors reach the human). Validates id (404) + typed evidence (400); idempotent replay.
- **Transaction console** in the Town Center overlay (`home.html` + `main_script.html`): pending-approval
  card now shows the full draft *before* you approve (tool, agent-labeled risk, claimed payoff marked
  "agent claim, unverified", preview text); latest executed artifact display; **Record real delivery** form
  (completed-request picker, USD amount, required evidence) — the human money-gate. All agent text rendered
  via `textContent` (no HTML injection path).
- **Launcher loads `.env`** (`scripts/run_claudeville.ps1`): without it, the backend silently degraded live
  search to the stub because the key never reached the process.

**Verification.** New suites green: 6 economy-eval + 2 town-center (artifact persistence, `find_request`)
+ 5 HTTP-route tests (404/400/idempotency/artifact exposure via real Flask test client); full backend +
eval suites green; `ruff` clean; Django `manage.py check` clean and the replay page renders the new console
elements (Django test client, HTTP 200). Economy reports written to `tools/eval/out/*.economy.{json,md}`.
**Discoveries / surprises.** (1) A latent **dual-import bug**: `RequestState` exists as two distinct classes
(bare `economy` vs `reverie.backend_server.economy` import paths); `transition_request`'s
`RequestState(str(state))` fallback exploded on foreign-path members because `str(EnumMember)` is
`"RequestState.COMPLETED"`. Fixed with a `.value`-first normalization. (2) The compress script crashed on
any live run (`KeyError` when a step's packet omits a persona — timeout/encounter paths do this); fixed
with carry-forward, which is what made the 1578-step replay watchable at all. (3) Agents *filed bug reports
about the sim itself* (Milo: "Hobbs Cafe missing from accessible locations", "conversation lock blocking
noon deadline") — the request channel doubles as emergent QA.

---

## 2026-06-26 — Swapped live search to Firecrawl (verified working)

Exa was out of credits (402), so swapped the default provider to **Firecrawl** (`fc-` key). Added a
`_firecrawl_search` adapter (`POST https://api.firecrawl.dev/v1/search`, `Authorization: Bearer`, maps
`data[] -> {title,url,snippet=description}`); same never-raise contract; default provider is now `firecrawl`
(exa retained in the map, selectable via `CLAUDEVILLE_SEARCH_BACKEND`). **Live-verified**: a real query
returned HTTP 200 with 5 real sources flowing through `execute("web_research")` into a `ToolResult`
(`evidence.live=True`) — e.g. real agency-onboarding articles. So agents can now ground research in real web
data. Tests updated to Firecrawl payloads (+ kept an exa-dispatch test); `.env.example` defaults to firecrawl.
194 backend green. Key lives in `.env` only (gitignored) — rotate it (shared in chat).

---

## 2026-06-26 — Real web search (Exa) wired into the execution layer

- `tool_executor._run_search` now dispatches on `CLAUDEVILLE_SEARCH_BACKEND` (extensible map) to a real
  **Exa** adapter (`requests` → `POST https://api.exa.ai/search`, `x-api-key`, maps `results[]` →
  `{title,url,snippet}`). **Never raises**: missing key / unknown provider / network / HTTP / parse error →
  `[]` → the honest "no live search" stub (no fabrication). Results still sanitized (LLM-1) + fed into the
  requesting persona's memory.
- **Live check:** the integration is correct — a real call authenticated and reached Exa, but the account
  returned **HTTP 402 `NO_MORE_CREDITS`** ("top up at dashboard.exa.ai"). The fallback behaved exactly as
  designed (stub, live=False). Added a `logging.warning` so an operator can tell out-of-credits/bad-key from
  a code bug (no longer a silent swallow). **Action: top up Exa credits, then set
  `CLAUDEVILLE_SEARCH_BACKEND=exa` + `CLAUDEVILLE_SEARCH_API_KEY` in `.env`** (gitignored) to go live.
- Tests: 4 mocked-HTTP cases (live mapping + tagged `evidence.live`, HTTP-error→stub, missing-key→stub,
  unknown-backend→stub). `.env.example` documents the vars (placeholder only — no secret). 192 backend green.
- **Security:** the key lives only in `.env`; never committed/echoed. (Key was shared in chat → consider
  rotating it.)

---

## 2026-06-26 — Full 10-person roster + team coordination

## 2026-06-26 — Full 10-person roster + team coordination

- **Booted to the full 10-person startup roster** (strategist, market_researcher, offer_designer,
  sales_drafter, delivery_planner, analyst, ops_coordinator, finance/scoring, tool_advocate,
  critic/risk). Regenerated the grounded base at `--count 10`; raised the per-persona move timeout
  **45→90s** (with ~10 concurrent LLM calls the cold day-planning window tripped the 45s cap into benign
  fallbacks). Verified: all 10 initialize, **0 tracebacks**, fewer warmup timeouts (3 vs 11), and the
  standup already shows role-aware coordination (e.g., "add prospect reachability to your rubric…").
  Note: 10 personas step ~2.5× slower than 4 — auto-save keeps runs interruptible-and-measurable.
- **Coordination / throughput (toward real money):** the team can now SEE each other's deliverables.
  New `town_center.recent_team_deliverables(exclude_actor)` + a sanitized `=== TEAMMATES' RECENT WORK ===`
  step-prompt section with handoff guidance ("build on it — take the NEXT step in the pipeline"). This
  attacks the root cause of the sparse, isolated economy (each agent previously saw only its OWN request
  outcomes, so research→offer→outreach handoffs never formed) and lets Stage-1 executed deliverables be
  built upon. Tests: team-deliverables excludes self + prefers completed; the prompt section renders and
  neutralizes injected markers. **188 backend + 22 eval/emergence + 34 Django green.**

---

## 2026-06-25 — Toward real money, Stage 0 (safety) + Stage 1 (execution layer)

Direction chosen after a full reassessment: **build toward real-world money**. The reassessment's headline
was that the economy was a *closed fiction* — approving a request executed nothing and "revenue" was the
agent's own self-reported `expected_payoff`, rubber-stamped on approval. (Also confirmed the cognitive core
is genuinely **active** — the audit burndown listing MEM-1/2 as open was stale; reconciled in
[IMPROVEMENT-LOG](IMPROVEMENT-LOG.md).)

**Stage 0 — foundation & safety**
- **LLM-1 prompt injection closed**: agent-authored dialogue / overheard chat / recalled conversation are
  now UNTRUSTED — sanitized (`text_safety.sanitize_external`: breaks `===` headers + ``` fences, neutralizes
  control-key JSON, collapses newlines, caps length) and rendered as quoted speech inside a labeled frame.
  `test_prompt_injection.py` (10 tests) proves a crafted line can't forge a section or a `town_request`.
- **Grounded base regenerated** (`make_claudeville_base.py`): personas now carry backstory identities +
  seeded goals/relationships. Map-independent (generator only reads the collision matrix).
- **Pushed**: the 16 local commits (`350e31c2..844c72ae`) are on `origin/main` — the long-standing 403 is gone.

**Stage 1 — real execution layer (safety-first)**
- New `tool_executor.py`: a request that completes now actually **executes** its tool. Read-only research
  (`web_research`/`market_analysis`) runs for real *iff* a search backend is configured
  (`CLAUDEVILLE_SEARCH_BACKEND`), else returns an **honest stub** (never fabricates findings). Outbound/spend
  tools (`send_email`/`post_content`/`spend_money`/…) are **dry-run only** — a reviewable artifact, nothing
  sent. All output sanitized (LLM-1).
- **Wired** into the request lifecycle (`town_center.transition_request` for both auto-complete and
  human-approval paths); the result feeds back into the requesting persona's associative memory
  (`reverie._feed_tool_result_to_persona`) so agents ground future decisions in real outcomes.
- **Revenue de-fictionalized**: completion no longer credits self-reported `expected_payoff`. Revenue is
  credited **only** via `town_center.record_delivery(...)` against human-confirmed evidence (idempotent).

**Verification.** ruff clean; **186 backend** (LLM-1 ×10, tool_executor ×11 incl. memory-feed, town-center
execution/dry-run/evidence-gated-revenue) + 22 eval/emergence + 34 Django green. Live: the grounded base
boots clean (0 tracebacks at both 4- and 10-persona rosters).

**Discoveries / decisions.**
- Regenerating the grounded base at the **default roster flips active personas 4→10** (via `meta.json`),
  which ~2.5× slows stepping and triggers frequent (benign) 45s move-timeouts. Re-grounded at **`--count 4`**
  to keep the fast roster matching the baseline; **scaling to 10 is a deliberate, cost-aware choice** (it
  boots fine) — flagged for the user.
- Town-center requests are **sparse** in the morning window, so an organic research→execution→memory event
  is unreliable to observe live; the path is instead **deterministically unit-verified** end-to-end.
- The economy/tool layer was decoupled from the heavy prompt layer via a new dependency-free `text_safety.py`
  (shared sanitizer) so `tool_executor` doesn't drag in `claude_structure`'s runtime imports.

**Next (Stages 2+):** real outbound email behind allow-list + per-action human confirm; revenue validation
against real receipts; a Town Center **transaction console** UI (full payload/draft/exec-status); wire a real
search backend so `web_research` returns live data.

---

## 2026-06-24 — Measured reality: periodic auto-save + the first trustworthy baseline

**What & why.** We had never actually measured current code — the only recorded run (`…094847`) was stale,
predated Phase 3, and was **never saved**, so the paper's alarming nulls (0 conversations, 0 memory) were
*measurement artifacts*. Fixed the root cause and measured for real.

- **Periodic auto-save** (`reverie.py`): new `_should_autosave`/`_maybe_autosave` (env
  `CLAUDEVILLE_AUTOSAVE_EVERY_STEPS`, default 250; `0` disables), hooked into `run_steps` (between steps +
  a forced final save) and the autosim loop (under `_step_lock`). Best-effort with bulletproof logging
  (`_log_safe`) so a save — or even a non-UTF-8 stdout glyph — can never kill a run. 8 unit tests; full
  suite now **163 backend + 22 eval/emergence + 34 Django**, green.
- **Fresh saved baseline** (`claudeville_v1_20260624_213240`, 800 steps, 09:00→11:13, 4 active personas):
  ran headless via `run_steps` so auto-save persists memory as it goes (the run is interruptible-and-still-
  measurable). Auto-save fired at 200/400/600/800; zero errors.

**Result — the "dead society" was an artifact.** The harness on the fresh run reports a **complete
conversation network** (6/6 pairs, density 1.0), 75 talk-steps, multi-party groups (max 3), strongest tie
Milo↔Theo, and **362 persisted memory nodes** (was 0) across 800 movement snapshots (was 0). Emergence: a
rising network trajectory (mean degree 1.42→4.06), mutual conversation across all pairs, and convention
emergence (273 shared content-words; "pain" used by all 4). **Honest caveat:** this 2.2-h morning window is
economically thin — ~1–2 Town Center requests, \$0 revenue, 3 points — because the team coordinated by
talking/drafting rather than filing requests. Economic throughput needs a longer run.

**Discoveries / surprises.**
- The prior nulls were *entirely* a persistence/staleness artifact — current code is socially rich out of
  the box (Phase 3 did its job). Lesson: never trust an unsaved run; auto-save is now the guardrail.
- The validation run's first attempt in the prior session **hung at persona init** under API rate
  contention with a concurrent verification workflow — re-confirmed here that a solo run boots and steps cleanly.
- Updated `PAPER.md` to v0.2: §6 + abstract rewritten around the corrected, measured baseline.

**Next (evidence-driven):** a longer/multi-day saved run to measure economic throughput + forward handoffs;
then, if requests/handoffs stay thin, the coordination levers (surface teammates' deliverables, handoff
reward) — but conversation itself is *not* the gap it appeared to be.

---

## 2026-06-23 — Documentation pass: this diary + the academic paper

Created the two living documents the project had been missing: this DEVLOG and [`PAPER.md`](PAPER.md).
The paper is written to arXiv standard (related work, architecture, methodology, evaluation with **honest
null results**, threats to validity, references) and is meant to evolve until the application is live.

**Discovery while surveying for the docs:** the repo already carries a mature `docs/` system from an earlier
audit (the 63-finding [`PHASE-1-AUDIT.md`](PHASE-1-AUDIT.md), [`PRD.md`](PRD.md), [`DECISIONS.md`](DECISIONS.md),
[`IMPROVEMENT-LOG.md`](IMPROVEMENT-LOG.md)). The audit's deepest CRITICAL/HIGH findings —
`MEM-1` (retrieval ignores relevance), `MEM-2` (importance hardcoded / reflection inert), `ARCH-2`
(move-timeout abandons coroutines), `MEM-3` (silent pathfinding failure), `OPS-4` (core untested) — are
**precisely what the six-phase roadmap closed**. The documentation now reflects that the diagnosed
"dormant cognitive core" has been switched on.

---

## 2026-06-23 — Phase 6: society scale & persona grounding (`844c72ae`)

**What & why.** The final roadmap phase makes the society *scalable* and *grounded*, and gives us a lens to
look for emergence. All new behaviour is opt-in / off by default so the economy path is unchanged.
- **Scale knob (6a):** `tools/mapgen/make_claudeville_base.py --count N` (+ `persona_factory.personas_for`).
  Confirmed nothing on the runtime path hard-codes the roster size — the async gather already scales.
- **Persona grounding (6b):** `tools/mapgen/persona_factory.py` (deterministic) writes backstory-grounded
  identities and **seeds the Phase-3/4 stores** — starting `goals.json` + `relationships.json` that load
  through the real `GoalMemory`/`RelationshipMemory` classes.
- **World/economy arbiter (6c):** new `reverie/backend_server/world_arbiter.py` — a Concordia-style
  Game-Master with a deterministic no-LLM rubric and an opt-in LLM path that falls back to the rubric.
  Gated by `CLAUDEVILLE_WORLD_ARBITER`; `build_arbiter()` returns `None` when unset → economy path untouched.
- **Emergence report (6d):** `tools/eval/emergence.py` (+ `analyze_run --emergence`) — specialization
  trajectory, cooperation/reciprocity, social-network growth, convention emergence.

**Adversarial verification → 2 fixes.** A 4-dimension verification workflow (arbiter/economy integrity,
generator grounding, emergence purity, signatures) cleared the behaviour-touching surfaces and found **2
medium** defects: the emergence + social-network analyzers crashed (`AttributeError`) on malformed/non-dict
run data (`{"persona": {"X": null}}`, non-dict `conversations`). Hardened with `isinstance` guards so the
harness degrades to empty results; added a malformed-run regression test.

**Live smoke.** First attempt *hung at persona init* — diagnosed as **API rate contention**: the
verification workflow's ~16 concurrent agents were starving the backend's init LLM calls. Re-ran after the
workflow finished → clean boot, stepped to 6, economy path silent (arbiter off), backpressure fields present.

---

## 2026-06-23 — Phase 5: robustness & scale (`087a843e`)

**What & why.** Hardening for longer/larger runs, behaviour-preserving where it counts.
- **Pathfinding (5a):** replaced the fixed `max_iterations=150` — which **silently truncated** legitimate
  long routes (the real maze's diameter is 156, so cross-town paths were quietly failing) — with
  `max(150, width·height)`; truncation is now non-silent (sentinel + warning), distinguished from
  unreachability via a wave-stagnation early-exit. Cached the static collision grid across calls.
- **Per-persona timeout (5b):** each persona gets its own `asyncio.wait_for`; one slow agent no longer
  forces the whole batch into the no-op fallback.
- **Atomic writes (5d):** snapshot writers use temp-file + `fsync` + `os.replace`.
- **Perception cache (5e)** + **backpressure observability (5c)** in `runtime_status`.

**Adversarial verification → 8 fixes (1 critical).** The verification workflow paid for itself here:
- **Critical:** the timeout rollback restored only **3 of ~17** mutated scratch fields — leaving
  `act_address`/`chatting_with`/`chat` half-applied to poison the *next* step. Fixed with full
  `Scratch.snapshot_action_state()` / `restore_action_state()`.
- **High:** removing the old batch timeout left the **sequential-encounter path unbounded** — a hung
  encounter persona could deadlock the whole step. Factored a shared `_move_persona_with_timeout()` used by
  both the parallel batch *and* both encounter move-sites.
- **High:** the environment snapshot was written to `{self.step}.json` (post-increment) while movement used
  the captured step — an off-by-one + TOCTOU. Both now use the authoritative captured step (verified live:
  `movement/` and `environment/` indices align 0..N).

**Live smoke.** Reached an encounter through the new timeout helper with zero errors and step-aligned snapshots.

---

## 2026-06-22 — Phase 4: multi-day goals & identity continuity (`4e0b445d`)

**What & why.** End the daily agency reset; keep personas coherent across days. New LLM work rides existing
*occasional* calls (day-planning / compaction / a day-boundary identity call) — **no new per-step call**.
- **`GoalMemory` (4a/4b):** goals/promises/projects persisted as `goals.json`; unfinished goals **carry over**
  at day rollover (not wiped); sub-goal progress; promises captured from conversations.
- **Structured compaction (4c):** a schema (commitments / relationships / open-goals / identity markers)
  folded back into durable memory + re-seeded next session — so "I promised Alice X" can't be dropped.
- **Identity anchor + drift (4d/4e):** `get_str_iss` populated from evolving `identity_markers`; a
  day-boundary drift score vs the *original* traits, emitted as an `identity_drift` ledger event for the harness.

**Adversarial verification → 7 fixes (3 critical).** This is where the verification methodology proved its
worth — none of these would surface in a short smoke or in mocked unit tests:
- **Critical:** `initial_innate/initial_learned` (the drift baseline) weren't persisted → on a day-2 reload
  the baseline re-snapshotted the *already-evolved* traits, silently invalidating the drift metric.
- **Critical:** `_find_by_text` deduped against **all** goals, so a goal completed yesterday *swallowed*
  today's identical daily requirement → it stayed `done` and invisible.
- **Critical:** a parse error in the identity update silently dropped the whole drift checkpoint.
- Plus 4 high/medium (completed-goal status reverting to active; compaction goals lost on JSON-parse
  failure; absorbed goals not flushed to disk; a fragile `score`/`note`→`drift_score`/`drift_note` rename).

---

## 2026-06-22 — Phase 3: relationship & theory-of-mind memory (`fb5e3a48`)

**What & why.** Agents had no social model — every encounter treated others as a blank slate.
- **`RelationshipMemory`:** per-other-persona familiarity / affinity[-1,1] / sentiment / last-topics /
  first-person *beliefs* (a lightweight theory-of-mind), persisted as `relationships.json`.
- Wired the previously-orphaned `get_last_chat` into a **RECALL** prompt block; added social-readiness cues
  (don't greet sleepers; prefer known/liked people) and a light group-conversation turn-taking nudge.

**Bug caught live (the value of smoke-testing).** First post-Phase-3 run crashed on **every encounter** with
`'tuple' object has no attribute 'lower'`: the new social-readiness code lowercased the activity field, but
`_get_nearby_personas` supplies it as a `(predicate, object)` *tuple*. Tests had passed only because their
stubs used string activities. Normalized at the prompt-build site + added a regression test with the real tuple shape.

---

## 2026-06-22 — Phase 2: evaluation harness & telemetry (`8253ad3b`)

**What & why.** There were **zero** metrics — emergence was unmeasurable. Built the offline harness
`tools/eval/` (`analyze_run`, `metrics`, `report`, `believability_judge`, `replay_diff`) computing role
specialization (Herfindahl), request coherence, per-agent contribution + Gini, the conversation network, and
activity/memory growth → JSON + Markdown. Added a best-effort `step_timing` telemetry event in `reverie.py`.
This harness is the scorecard that makes Phases 3–6 A/B-provable. First real run surfaced signal:
role-concentration 0.75, team points 5, 100% approval.

---

## 2026-06-22 — Phase 1: activating the Generative-Agents cognitive core (`f6650752`)

**The keystone.** The deep review's headline finding was that Claudeville implemented the *single unified
LLM call* well but the classic Generative-Agents "brain" was **present as data structures yet never
executed**: relevance retrieval methods existed but were never called; importance was a hardcoded constant;
reflection never fired despite the accumulator being decremented. Phase 1 switched it on, inside the one
per-step call (no embeddings, D-002):
- **Relevance retrieval** (`cognitive_modules/retrieve.py`): score candidate memories by
  `recency_w·recency(recency_decay) + relevance_w·keyword-overlap + importance_w·(poignancy/10)`, using the
  previously-inert `scratch` weights.
- **LLM-judged importance** → `ConceptNode.poignancy` (replacing the constant 5).
- **Reflection** (`cognitive_modules/reflect.py`): when the importance accumulator crosses zero, synthesize
  back-linked higher-level insights; the only *occasional* extra call.
- **Dual-layer cognition (HER, arXiv 2601.21459):** the step also elicits `system_thinking` (strategy) and
  `inner_monologue` (private first-person thought); the monologue is persisted as a thought. Prompt design only.

**Live smoke:** clean — no parse errors across 6 steps × 4 personas; agents navigate and reference recalled memory.

---

## 2026-06-19 → 2026-06-22 — The "ship" pass: world fidelity, economy, replay, launch

Before the believability roadmap, a four-part pass made the simulation demonstrable end-to-end
(`80dce4da`, `58162aeb`, `34da8b4a`, `73f8e57b`, `eb6a8d90`, `56059236`):
1. **World fidelity** — higher-quality town art + a re-derived navigation mesh; per-footprint room
   segmentation and furniture-aware object placement in the `tools/mapgen` pipeline.
2. **Economy loop** — closed the Town Center: agent feedback on request outcomes, revenue-on-completion,
   auto-resolution of safe (no-approval) tools.
3. **Cold-start replay** — offline pre-simulation → smooth recorded playback (LLM-free), so a fresh viewer
   isn't staring at a frozen 5 a.m. town.
4. **Launch** — one-command start scripts + restored `the_ville` assets.

**Discoveries this pass:**
- **Black screen / green lines** in the browser = `DJANGO_DEBUG=False` not serving static assets. Always
  launch the frontend with `DJANGO_DEBUG=True` in dev.
- **Stale-code "zombie" on port 5000** — an old backend kept serving old code; revenue read 0 until it was
  hard-killed (`Get-NetTCPConnection -LocalPort 5000 | Stop-Process`) and relaunched.
- **"Deleted" `the_ville` files** were really the **Windows 260-char path limit**; fixed with
  `git config core.longpaths true`, tree restored.

---

## 2026-06-16 → 2026-06-17 — Audit baseline + Phase A quick wins

A grounded audit produced [`PHASE-1-AUDIT.md`](PHASE-1-AUDIT.md): **63 findings** (6 CRITICAL · 19 HIGH ·
23 MEDIUM · 15 LOW) with `file:line` evidence, ranked into goals G1–G9 in [`PRD.md`](PRD.md). Phase A closed
the security/correctness quick wins (CSRF re-enabled, secrets/`DEBUG` moved to env, DOM XSS sinks escaped, CI
added, several memory/parse bugs fixed) and accepted decisions `D-001…D-006`. See `IMPROVEMENT-LOG.md` for
the per-change ledger. The deeper CRITICAL/HIGH items (`MEM-1`, `MEM-2`, `ARCH-2`, `MEM-3`, `OPS-4`) were
left for "Phase B" — and are what the six-phase roadmap above ultimately resolved.

---

## Genesis — Stanford *Generative Agents* → Claude Agent SDK

Claudeville is a fork of Park et al.'s *Generative Agents* (UIST '23) re-architected for the **Claude Agent
SDK**. The defining re-architecture decisions, made before this diary begins:
- **One unified LLM call per step** returning *all* decisions (action, social, thought, town-request) as
  structured JSON — versus the original perceive→plan→execute→reflect multi-call chain (≈3–4× fewer calls).
- **No vector embeddings (D-002):** retrieval is keyword + recency + (LLM-judged) importance.
- **Persistent SDK session + compaction** instead of stateless full-context calls.
- A new **human-in-the-loop economy** (the "Town Center") and a goal — *generate real-world money through
  legal, human-approved business actions* — that the original simulation did not have.

---

## Standing follow-ups (live list)

- [x] **`git push` — RESOLVED (2026-07-11).** Auth works now; `main` is pushed to
      `origin/main` at `1f74efcd` (Phase 1 + console/economy milestone). Remote = AutoMoneyVille.
- [ ] **Base not regenerated with Phase-6 grounding.** Running `tools/mapgen/make_claudeville_base.py`
      materializes grounded personas but also pulls a stale→current `town_spec` map change — do it as a
      deliberate, reviewed step.
- [ ] **Longer saved run pending (economic throughput).** The 2026-06-24 baseline (800 steps) confirmed rich
      *social* emergence but a too-short window for *economic* signal (≈1–2 requests, \$0 revenue). A
      multi-hour/multi-day saved run is needed to measure revenue + forward handoffs. (Auto-save now makes
      such runs safe and interruptible-and-measurable — the gap that lost `…094847` is closed.)
- [ ] **`ARCH-1` shared-state determinism (Phase C).** Personas still mutate shared world state concurrently;
      the snapshot→concurrent-decide→serial-apply model (`D-006`) is designed but not built.
- [ ] **CLI header `UnicodeEncodeError` on non-UTF-8 stdout** (Windows) — workaround `PYTHONUTF8=1`.

---

## How to add an entry

Copy this block to the top of the dated entries (newest first):

```markdown
## YYYY-MM-DD — <short title> (`<commit hash if any>`)

**What & why.** <1–3 sentences: what changed and the problem it solves.>
- <key change> (`file/path.py`): <one line>
- ...

**Verification.** <tests / live smoke / metric before→after.>
**Discoveries / surprises.** <anything non-obvious learned — bugs, gotchas, dead ends.>
```

Conventions:
- Tie changes to a commit hash and, where relevant, a finding ID (`MEM-1`) or roadmap phase.
- Record **discoveries and dead ends**, not just successes — that's the point of a diary.
- Keep the factual one-liner in [`IMPROVEMENT-LOG.md`](IMPROVEMENT-LOG.md); keep the *story* here.
