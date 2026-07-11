# Claudeville: Reactivating Generative-Agent Cognition on a Frontier Agentic SDK for a Human-Governed Economic Society

**A living research paper.**
Version 0.4 · Last updated 2026-07-02 · Status: **research prototype (not yet live)** ·
Covers commits `f6650752`…`9e673ab4` + the transaction-console working set on `main`.

> This document evolves with the system. Substantive changes are recorded in the
> [Version history](#version-history) at the end and narrated in [`DEVLOG.md`](DEVLOG.md). Every
> architectural claim is tied to a source file; every empirical number is tied to a recorded run artifact
> under `tools/eval/out/`. Where results are null or negative, they are reported as such — the goal is an
> honest account that grows toward the application going live, not a marketing summary.

---

## Abstract

Generative agents — language-model characters with memory, reflection, and planning — produce strikingly
believable individual and collective behaviour, but the canonical architecture of Park et al. (2023) was
built around a multi-call cognitive chain and embedding-based memory retrieval atop a now-superseded model
API. We present **Claudeville**, a re-architecture of the generative-agent paradigm onto a modern *agentic*
SDK (the Claude Agent SDK), and a study of what is gained and lost in the translation. Claudeville collapses
the perceive–plan–reflect chain into a **single unified structured call per simulation step**, replaces
embedding retrieval with a **keyword × recency × importance** scheme, and runs agents as **persistent,
self-compacting SDK sessions** rather than stateless completions. We document a counter-intuitive failure
mode of such migrations — the *dormant cognitive core*, in which the believability-critical machinery
(relevance retrieval, reflection, learned importance) survives as code but is never executed — and a
six-phase program that reactivates it and extends it with relationship/theory-of-mind memory, multi-day
goals and identity continuity, robustness/scale hardening, and society-scale grounding. We embed the agents
in a novel **human-governed micro-economy**: a cooperative ten-agent "startup" whose only path to reward is
*generating real-world money through legal, human-approved actions*, mediated by a Town Center
approval-and-reward loop. We contribute an **offline evaluation harness** (role specialization, request
coherence, contribution inequality, conversation networks, identity drift, and emergence trajectories) and an
**adversarial multi-agent verification methodology** that, applied to three phases, surfaced 17 confirmed
defects — several state-corruption and silent-data-loss bugs invisible to unit tests and short live runs.
We report the system's current empirical baseline honestly, and in doing so **correct a measurement
artifact** from this paper's first draft: an earlier "dead society" result (zero conversations, zero memory)
turned out to be a stale, never-saved run rather than a behavioural finding. On a fresh, saved run of current
code the society is demonstrably alive — it forms a *complete* conversation network (all pairs talk, density
1.0), holds multi-party dialogue, and accumulates hundreds of persisted memory nodes. What remains latent is
**economic throughput**: in a short morning window the team coordinates and drafts but files few formal
requests and closes \$0 revenue. We frame this honestly and identify the longer-horizon work that should
close it.

---

## 1. Introduction

### 1.1 Background and motivation

Park et al.'s *Generative Agents* (2023) demonstrated that LLM-driven characters, equipped with a **memory
stream**, a **retrieval** function weighting recency, importance, and relevance, **reflection** that distils
observations into higher-level beliefs, and **planning**, exhibit emergent individual routines and social
phenomena (information diffusion, coordination, relationship formation). The result reframed LLMs not as
chatbots but as substrates for *simulacra of human behaviour*, with applications from social-science
prototyping (Park et al., 2022) to game NPCs and, more recently, large-scale population simulation (Park et
al., 2024).

Two forces motivate a re-architecture. First, the original implementation predates **agentic SDKs** —
toolkits that manage a persistent model session, tool use, prompt caching, and permissions. Re-homing
generative agents onto such an SDK promises lower cost (via session reuse and caching), simpler tool
integration, and a path to *acting in the world*, not merely narrating it. Second, the original cognitive
loop issues several LLM calls per agent per step; at the scale of a populous town this dominates cost and
latency. Both pressures push toward **fewer, richer calls** and **stateful sessions**.

### 1.2 The problem this paper addresses

Migrations of this kind are not free. We observed — and this is the paper's organizing insight — that
collapsing the cognitive chain into a single call and swapping the retrieval substrate can leave the
believability-critical machinery **present but inert**. In Claudeville prior to this work, the
associative-memory module exposed relevance-retrieval methods that *nothing called*; per-event importance
was a hardcoded constant; and reflection never fired even though its trigger accumulator was being
decremented every step. The agents still *moved and talked*, so the regression was invisible to casual
observation — yet the very mechanisms responsible for the original paper's emergent behaviour were switched
off. We call this the **dormant cognitive core**.

This paper documents (a) how the dormancy arose and was diagnosed, (b) a program to reactivate the core and
extend it for a long-lived, socially and economically situated society, (c) an evaluation harness to make
the resulting behaviour *measurable*, (d) a verification methodology suited to the failure modes such systems
actually exhibit, and (e) an honest empirical baseline.

### 1.3 Contributions

1. **A faithful generative-agent re-architecture on an agentic SDK** — a single unified structured call per
   step, embedding-free keyword/recency/importance retrieval, and persistent self-compacting sessions
   (§3, §4.1).
2. **Reactivation of the dormant cognitive core** — relevance retrieval, LLM-judged importance, and
   reflection wired into the single call, plus dual-layer ("system thinking" / "inner monologue") cognition
   adapted from role-play prompting (§4.2).
3. **A persistent social and economic substrate** — relationship/theory-of-mind memory, multi-day goals and
   identity continuity, and a *human-governed* micro-economy whose objective is real-world revenue under an
   approval gate (§4.3–§4.4).
4. **An offline evaluation harness** computing role specialization, request coherence, contribution
   inequality, conversation-network structure, identity drift, and emergence trajectories (§3.6, §6).
5. **An adversarial multi-agent verification methodology** that found 17 confirmed defects across three
   phases — including critical state-corruption and silent-data-loss bugs missed by unit tests and smoke runs
   (§5).
6. **An honest empirical baseline** of a ten-agent human-governed startup society, including its null
   results and their analysis (§6).

A non-goal of this work is model fine-tuning: Claudeville adopts *prompt/architecture* ideas from the
literature (including the dual-layer scheme) but trains nothing, because the substrate is a hosted frontier
model.

---

## 2. Background and Related Work

### 2.1 Generative agents and social simulacra

*Generative Agents* (Park et al., 2023) is the direct ancestor: the memory-stream / retrieval / reflection /
planning architecture and the sandbox town ("Smallville") are the template Claudeville forks. *Social
Simulacra* (Park et al., 2022) earlier used LLMs to prototype social-system behaviour, and *Generative Agent
Simulations of 1,000 People* (Park et al., 2024) scaled the idea toward survey-faithful population
simulation — a north star for Claudeville's scale ambitions (§9).

### 2.2 Memory and retrieval for LLM agents

The original retrieval uses dense embeddings (cosine similarity) alongside recency and importance.
A line of subsequent work refines agent memory: **MemGPT/Letta** (2023) treats the context window like
virtual memory with paging between core and archival stores; **Reflective Memory Management (RMM)** (2025)
and **A-MEM** (2025) propose adaptive, self-organizing memory with reflective consolidation and linking;
**MemoryBank** (2023) and **HippoRAG** (2024) explore embedding- and graph-based long-term recall. Claudeville
deliberately departs from embeddings (decision **D-002**), using a keyword index combined with recency decay
and LLM-judged importance (§4.2); the embedding-based systems above are reference points for *what is traded
away* (semantic generalization) versus *what is gained* (cost, determinism, transparency).

### 2.3 Dual-process and role-play prompting

A recurring idea is separating an agent's private deliberation from its outward behaviour. Claudeville adopts
the *prompt design* of a dual-layer role-play scheme (HER; Du, 2026, arXiv:2601.21459): each step elicits a
brief in-character **system-thinking** (strategy) layer and a first-person **inner-monologue** (affect/belief)
layer alongside the outward action and dialogue, and persists the monologue as a memory that feeds importance
and reflection. We take the architecture, not the paper's supervised/RL training, since we do not fine-tune.

### 2.4 Social evaluation, theory of mind, and multi-agent platforms

**SOTOPIA** (2024) provides a rubric for evaluating *social intelligence* (goal completion, believability,
relationship maintenance, social-rule adherence) that informs Claudeville's optional LLM "believability
judge" (§3.6). Theory-of-mind benchmarks (e.g., **MuMA-ToM**) motivate the *beliefs-about-others* component
of our relationship memory (§4.3). Several platforms inform the social and governance design: **Concordia**
(DeepMind) uses a "Game Master" to adjudicate a narrated world — the model for Claudeville's optional world
arbiter (§4.4); **CAMEL** and **AgentVerse** (2023) study role-played multi-agent collaboration; **AI Town**
(a16z) is an engineering reference for a real-time agent town; and **Project Sid / PIANO** (Altera, 2024) and
**AgentSociety** (2024) study many-agent civilizational and societal dynamics at scale.

### 2.5 Emergent norms and cooperation

Recent work reports *emergent social conventions* and the *cultural evolution of cooperation* among
populations of LLM agents, and *network formation* dynamics in agent groups. These define the phenomena
Claudeville's emergence harness (§3.6, §6.4) is built to look for: specialization, reciprocity,
network growth, and shared conventions.

> **A note on citations.** This is a living document; the reference list (§References) is maintained as the
> work matures. Where a venue or year is approximate it is marked; no citation here is a placeholder for a
> source the authors have not actually consulted.

---

## 3. System Architecture

Claudeville is a Python 3.11 system in three tiers: a **Flask simulation engine** (`reverie/backend_server/`),
a **Django + Phaser frontend** (`environment/frontend_server/`), and **offline tooling** (`tools/`). It forks
Stanford's `reverie` engine and replaces its cognition and transport layers.

### 3.1 The simulation engine and step loop

`reverie.py`'s `ReverieServer` owns the world (`maze.py`), the persona set, the event ledger, and the Town
Center store, and serves the frontend over HTTP. A simulation **step** (`_process_step_unlocked`) proceeds:
(1) clear per-step caches and ingest authoritative tile positions; (2) detect *new encounters* and run them
**sequentially** with an initiative rule; (3) run all remaining personas' decisions **concurrently**, each
under its own timeout; (4) synchronize multi-party conversations; (5) persist atomic per-step snapshots,
advance the clock, and enqueue the movement packet for the frontend.

Two engineering choices decouple believability from LLM latency. An **autosim buffer** simulates steps ahead
of what the viewer is watching and applies backpressure (pausing production when the buffer is full or no
client is polling), and finished runs are compressed into a **master movement file** for **LLM-free offline
replay** — smooth playback that never re-invokes the model.

### 3.2 Persona cognition

`persona/persona.py::move()` is the per-step pipeline: perceive the local world; decide via a **skip policy**
whether an LLM call is even needed (continuing a walk or an in-progress action requires none); if needed,
assemble context (focal-keyword memory retrieval, social/relationship context, accessible locations, schedule,
Town Center feedback) and issue **one** unified call; then process the structured response, persist memory
(including the inner monologue), and *occasionally* reflect or compact.

### 3.3 The unified call: `UnifiedPersonaClient`

`persona/prompt_template/claude_structure.py` wraps the Claude Agent SDK. Each persona is a **persistent
session** (background event loop, per-persona client). `build_step_prompt` renders the current situation;
the model returns a single JSON object — `action`, `social`, `thoughts`, `schedule_update`, `town_request`,
and the dual-layer `system_thinking` / `inner_monologue` — parsed by `parse_step_response` with a
retry-on-malformed-JSON path. *Occasional* calls handle day planning (`plan_day`), reflection (`reflect`),
identity update at the day boundary (`update_identity`), and context **compaction** when the session nears
its token budget; none of these run every step. This is the central departure from the original four-call
chain (§4.1).

### 3.4 Memory structures

- **Associative memory** (`associative_memory.py`): the event/thought/chat stream as `ConceptNode`s with a
  **keyword index** (no embeddings), each carrying an LLM-judged `poignancy`.
- **Scratch** (`scratch.py`): short-term state — current action, path, schedule, conversation, identity
  markers, and the original-trait baseline; exposes `snapshot_action_state`/`restore_action_state` used for
  timeout rollback (§4.5).
- **Spatial memory** (`spatial_memory.py`): the per-tile event view used for perception.
- **Relationship memory** (`relationship_memory.py`): per-other-persona familiarity, affinity, sentiment,
  recent topics, and first-person *beliefs* (§4.3).
- **Goal memory** (`goal_memory.py`): multi-day goals/promises/projects that persist across day boundaries
  (§4.4).

### 3.5 The world, map pipeline, and frontend

`tools/mapgen/` turns a town specification (`town_spec.json`) into the engine's collision/sector/arena/object
matrices (`generate_world.py`) and **gates** them with a validator (`validate_world.py`) that checks address
resolution, ≥98% walkable connectivity, and that no spawn sits on a wall. The Django frontend serves movement
packets to a Phaser canvas (pan/zoom, play/pause, speed, per-conversation chat popups) and supports the
offline replay view.

### 3.6 Evaluation tooling

`tools/eval/` analyzes a finished run *offline* (no LLM, except the optional judge): `metrics.py` computes
role specialization (a normalized Herfindahl concentration of each actor's request types vs. its scenario
role), request-coherence (stage-tagged handoffs), per-agent contribution and Gini inequality, the
conversation network, and activity/memory growth; `emergence.py` adds *trajectory* analyses (specialization
over time, cooperation/reciprocity, network growth, convention emergence); `believability_judge.py` applies a
SOTOPIA-style rubric via an LLM; `replay_diff.py` checks determinism across runs. Outputs are JSON + Markdown.

---

## 4. Design and Methodology

### 4.1 Re-architecture decisions

| Concern | Generative Agents (2023) | Claudeville | Rationale / decision |
|---|---|---|---|
| Calls per step | perceive→plan→execute→reflect (≈4) | **1 unified** + occasional reflect/plan/compact | cost, latency, parallelism |
| Retrieval | dense embeddings + recency + importance | **keyword × recency × importance** | D-002 (no embeddings): cost, determinism, transparency |
| Session | stateless, full context each call | **persistent SDK session + compaction** | cache reuse; bounded growth (D-003, D-005) |
| Importance | constant | **LLM-judged poignancy** | fidelity to the agent's own valuation |
| Transport | file polling | HTTP polling + autosim buffer (SSE later, D-004) | responsiveness; decouple from LLM latency |

These choices are recorded as accepted ADRs (`docs/DECISIONS.md`, D-001…D-006). The keyword-retrieval choice
(D-001/D-002) is the most consequential and is revisited in Limitations (§8).

### 4.2 Reactivating the cognitive core (Phase 1)

The keystone phase wired the dormant machinery into the single call without adding per-step calls:
**relevance retrieval** (`cognitive_modules/retrieve.py`) scores candidate memories by
`recency_w·recency(recency_decay) + relevance_w·keyword_overlap + importance_w·(poignancy/10)` using the
formerly-inert `scratch` weights; **importance** flows from the model's per-action judgment into
`ConceptNode.poignancy`; **reflection** (`cognitive_modules/reflect.py`) fires when the importance
accumulator crosses zero, synthesizing back-linked higher-level thoughts (the only occasional extra call);
and **dual-layer cognition** (HER) elicits `system_thinking` and `inner_monologue` in the same response, the
monologue persisted as a thought that itself feeds importance and reflection.

### 4.3 Relationship and theory-of-mind memory (Phase 3)

`RelationshipMemory` gives each persona a persistent social model of every other: an interaction count
(familiarity), an affinity in [−1, 1] with a derived sentiment label, recent shared topics, and a bounded set
of first-person **beliefs** about the other (a lightweight theory of mind). It is updated heuristically from
committed conversations and can be refined by reflection. The step prompt surfaces a "people you know"
block, a **recall** of the last conversation with each nearby acquaintance (wiring up the previously-orphaned
`get_last_chat`), and **social-readiness** cues (do not greet someone who is asleep; prefer familiar/liked
partners).

### 4.4 Multi-day goals, identity, and the human-governed economy (Phases 4 & 6c)

`GoalMemory` ends the daily "agency reset": goals, promises, and projects persist across days, carry unfinished
work forward, track sub-goal progress, and are seeded at character creation from each persona's role. A
**structured compaction** schema preserves commitments, relationships, open goals, and identity markers across
a session reset, so a promise is never lost to summarization. An **identity anchor** lets `currently`/`learned`
traits evolve slowly at the day boundary while a **drift score** measures distance from the *original* traits.

The society is governed by the **Town Center** economy (`town_center.py`, `economy.py`). The scenario
`startup_team_v1` sets the objective verbatim: *"Generate real-world money through legal, human-approved
business actions."* Ten role-specialized agents (strategist, market researcher, offer designer, sales drafter,
delivery planner, analyst, operations coordinator, finance/scoring, tool advocate, critic/risk officer) earn
points under an explicitly **phased reward model** (early weights reward research and drafts; late weights
reward replies, meetings, and — heavily — *actual revenue*). Critically, **external actions require human
approval**: drafting and research are automatic, but sending email, posting content, or spending money are
*blocked* pending a human decision in the Town Center, and a set of behaviours (spam, deception, unauthorized
scraping, uncontrolled spending) is forbidden outright. An **opt-in world arbiter** (`world_arbiter.py`,
Concordia-style; off by default behind `CLAUDEVILLE_WORLD_ARBITER`) can adjudicate requests with a
deterministic rubric or an LLM that falls back to the rubric. This human-in-the-loop gate is the system's
primary safety and interpretability mechanism (§7).

### 4.5 Robustness, concurrency, and scale (Phases 5 & 6a/6b)

Long, large runs demand correctness under concurrency. Each persona's decision runs under its own
`asyncio` timeout via a shared `_move_persona_with_timeout`; on timeout the task is cancelled, awaited to
unwind, and the persona's **full** action/conversation state is rolled back from a snapshot (a partial
rollback was the source of a critical bug, §5). Pathfinding's fixed iteration cap — which silently truncated
legitimate long routes — was replaced with a maze-size-aware bound that distinguishes truncation from
unreachability and never fails silently; the static collision grid is cached. Snapshot writes are atomic
(temp + `fsync` + `replace`). Persona count is a generation-time knob, and characters are *grounded* —
backstory-derived identities seeded with starting goals and acquaintance relationships.

---

## 5. Engineering and Verification Methodology

We claim the *method* by which Claudeville was built is itself a contribution, because the failure modes of
LLM-agent systems are poorly covered by conventional testing. Two properties make them so: much logic only
executes on rare paths (a day boundary, a context compaction, a per-persona timeout, an encounter), and the
LLM is mocked in unit tests, so a contract that *parses fine but behaves wrongly* slips through.

Our protocol per phase was: implement to a tight spec → `ruff` + the full backend/Django suites → a **live
smoke run** of the real stack → for the riskiest phases, an **adversarial multi-agent verification workflow**
→ fix → commit. The verification workflow fans out independent reviewer agents across orthogonal risk
dimensions (e.g., for the concurrency phase: timeout/cancellation, cache behaviour-preservation, atomic-write
windows, signature integrity); each *finding* is then handed to an independent skeptic agent instructed to
**refute** it by tracing the concrete failure path in the real code; only findings that survive refutation are
reported, ranked, and fixed, with a regression test added for each.

Applied to the three riskiest phases, this surfaced **17 confirmed defects** that the green test suite and the
live smoke had both missed:

- **Phase 4 (7 confirmed, 3 critical):** the identity-drift *baseline* was not persisted, so it silently
  re-anchored to the already-evolved traits on a day-2 reload, invalidating the metric; a completed goal
  *swallowed* an identical new daily requirement via de-duplication, leaving it permanently `done` and
  invisible; a parse error in the identity update silently dropped the entire drift checkpoint.
- **Phase 5 (8 confirmed, 1 critical):** the per-persona timeout rolled back only 3 of ~17 mutated state
  fields, leaving conversation/action state half-applied to corrupt the next step; removing the batch timeout
  left the sequential-encounter path unbounded (a hung encounter could deadlock a whole step); the environment
  snapshot used a post-increment step counter, mis-indexing it relative to the movement snapshot (an
  off-by-one with a time-of-check/time-of-use race).
- **Phase 6 (2 confirmed, medium):** the emergence and social-network analyzers crashed on malformed/non-dict
  run data instead of degrading gracefully.

The recurrence of *silent* failures (a dropped checkpoint, a swallowed goal, a half-rolled-back state) is the
empirical case for the method: these do not throw, do not fail a test, and do not disturb a six-step smoke;
they degrade fidelity or corrupt long-run state in ways only an adversarial reader tracing the rare path will
catch. The current automated baseline is **155 backend + 13 evaluation + 9 emergence + 34 Django tests**,
green, with `ruff` clean.

---

## 6. Evaluation

### 6.1 Setup, and a correction to an earlier artifact

We report the offline harness applied to `startup_team_v1`. The headline run is
`claudeville_v1_20260624_213240` — a fresh, **saved** run on current code (commit `844c72ae` plus the
auto-save fix of §4.5/§5), covering 09:00→11:13 (≈2.2 sim-hours, 800 steps): the morning standup plus an
early work block, with **four active personas** instantiated from the ten-role roster (Nora Vale, Milo Chen,
Iris Morgan, Theo Grant). Source: `tools/eval/out/claudeville_v1_20260624_213240.{metrics,emergence}.json`.

**This run corrects a serious artifact in v0.1 of this paper.** The earlier draft reported a "dead society"
(zero conversations, zero memory) from run `…094847`. That run is now known to be a *measurement* artifact,
not a behavioural finding: it was created ~11.5 h **before** the Phase-3 social machinery landed, predates
Phase-5 live movement snapshots, and — decisively — was **never saved** (its `meta.json` shows `step: 0`
despite 4,342 logged events). Per-persona memory, conversations, and the social graph only reach disk on a
save, so the harness was reading empty inputs. The §4.5 periodic auto-save now closes that gap; the fresh run
persists everything live. *The "society does not talk" claim was false; the corrected evidence follows.*

### 6.2 Social behaviour and memory (observed — the corrected result)

On current code the society is demonstrably **social and remembering**:

| Metric | Value | Source field |
|---|---|---|
| Conversation network edges | **6** (a *complete* graph on the 4 personas) | `social_network.edge_count` |
| Network density | **1.0** | `emergence.network_growth.final_density` |
| Talk-steps | 75 | `social_network.talk_steps` |
| Mean / max conversation group size | 2.27 / 3 (multi-party) | `social_network.group_size_*` |
| Strongest tie | Milo Chen ↔ Theo Grant (weight 58) | `social_network.edges` |
| Most central agents | Theo (34.0), Milo (28.7) | `social_network.degree_centrality` |
| Persisted memory nodes | **362** (Nora 111, Theo 93, Iris 87, Milo 71) | `activity.memory_node_counts` |
| Movement snapshots written | 800 | `activity.movement_snapshot_count` |

Every one of these read **zero** in the stale run. The agents converge for the standup, form a *fully
connected* conversation network (all six pairs talk, density 1.0), hold multi-party conversations (groups up
to three), and accumulate substantial associative memory. The **16.5% active-step ratio** (vs. the stale
run's 7%) reflects the conversation-heavy morning — most steps still skip the LLM (the cost lever), but
dialogue raises activity.

### 6.3 Economic activity (observed — thin in this window, honestly)

The same morning slice is economically quiet, and we report that plainly:

| Metric | Value | Reading |
|---|---|---|
| Town requests submitted | ~1–2 | a standup+planning window, not a request-heavy one |
| Realized revenue | \$0 (`team_revenue_cents` = 0) | no outbound deal in 2.2 h |
| Team points | 3 | early-reward, low-volume |
| Forward handoffs | 1 of 1 transition (research→finance) | too few requests to assess a pipeline |
| Mean role specialization | 0.0 | undefined-in-practice with ~1 request |

This is the inverse trade-off from the stale run, and it is informative: in this short window the agents
**coordinated by talking and drafting** (auto-approved `internal_planning`/drafting needs no Town Center
request) rather than filing formal requests, so request-derived metrics are thin. The earlier `…094847` run —
useful *only* for the request picture, since its memory/social data never persisted — showed the
complementary regime: over 4,342 steps it logged 5 requests, 100% human-approved, role concentration ≈ 0.75.
Neither window alone characterizes the economy; **\$0 revenue remains the honest headline** and reflects the
deliberate human-approval gate plus a short horizon (revenue needs an approved outbound action *and* a real
reply). A longer, saved run is required to measure economic throughput and forward handoffs properly (§9).

**Update (v0.4, 2026-07-02) — the request-rich window arrived, and it isolates the bottleneck.** A dedicated
economy analyzer (`tools/eval/economy.py`; outputs under `tools/eval/out/*.economy.{json,md}`) was run
against the 10-persona, 1,578-step run `…003901`. The measured funnel: **17 requests submitted, 0
transitions, 0 tools executed, 0 revenue — every request terminated in `proposed`**, and all 17 were queued
at the human-approval gate (`approval_required = true` or unregistered tools). This cleanly separates two
hypotheses the earlier windows could not: the economy's constraint in this regime is **not** agent
request-productivity (17 requests in one simulated morning across 3 active requesters) but the **absence of
a reviewing human in the loop** — no approval surface existed in the operator UI. Two qualitative findings
from the pending queue deserve emphasis. First, proposal quality was higher than the \$33.00 of (unverified,
agent-claimed) payoff suggests: agents sourced *named real-world prospects* from live web research and
embedded per-message human-approval conditions in their own outreach proposals. Second, **governance emerged
without being scripted**: the team's risk officer filed a formal HOLD (`risk_flag`) against a teammate's
outreach-channel request pending a risk checklist, and the requester answered with a structured checklist
response — an approval dialogue conducted entirely between agents, waiting on a human who had no console.
In response, v0.4 ships that console (§3.5): dry-run artifacts now persist to an append-only
`artifacts.jsonl` ledger (previously the executed `ToolResult` was discarded after a single HTTP response),
`record_delivery` is reachable over HTTP behind evidence validation and idempotency, and the operator
overlay shows the full draft (tool, agent-labeled risk, claimed payoff explicitly marked unverified, and
preview text) *before* approval, plus a record-delivery form gating any `revenue_cents` on typed human
evidence. Whether a reviewed queue converts proposals into approved actions — and eventually confirmed
revenue — is the next measurement (§9).

### 6.4 Emergence (partially observed on the real run)

Run against the fresh run, the emergence analyzer reports genuine — if early — signal, not just a synthetic
fixture: a **rising conversation-network trajectory** (per-step mean degree `first` 1.42 → `last` 4.06,
`rising: true` over 800 points), **mutual (bidirectional) conversation across all six pairs**
(`cooperation.cooperating = true`), and **convention emergence** (273 shared content-words used by ≥2
personas; e.g. the domain term *"pain"* used by all four — apt for a market-research team). Two phenomena are
*not* yet observed and remain instrument-validated only (via `emergent_run.emergence.json`): reciprocal
*request* handoffs and a rising specialization trajectory both need a request-richer run than this morning
slice provided.

### 6.5 Summary

The corrected baseline: Claudeville's cognition is active, and the society **talks, forms a complete
relationship network, remembers, and begins to share conventions** — the opposite of v0.1's artifactual
"dead society." What remains genuinely latent is **economic throughput**: in a 2.2-hour morning window the
team coordinates and drafts but files few formal requests and closes no revenue. The honest one-line summary
is now: *the brain is on, the society is talking and remembering, and the next question is whether — over a
longer horizon — it can turn that coordination into approved actions and real revenue.*

---

## 7. Discussion

**Human-in-the-loop as a feature, not a limitation.** The approval gate is what makes a "make real money"
objective tractable and safe to run: every world-affecting action is mediated by a human decision the agents
then see and learn from. This bounds agency, keeps the system interpretable, and turns the economy into a
legible record (the request/reward ledgers) that the evaluation harness reads directly. It also reframes
"emergence" — we are interested not in unconstrained autonomy but in *what a governed society of agents
proposes and coordinates*.

**Determinism and reproducibility.** The single largest open correctness issue (audit `ARCH-1`) is that
personas mutate shared world state concurrently within a step. The per-persona timeout and full-state rollback
(§4.5) mitigate the worst corruption, but true reproducibility requires the designed
snapshot→concurrent-decide→serial-apply model (D-006), which is not yet built. Until then, runs are not
bit-reproducible, which constrains the strength of any quantitative comparison.

**Cost geometry.** The unified call plus the skip policy (7% active steps) and session caching make a populous
town economically simulable; compaction bounds the per-agent context as days accumulate. This geometry is what
makes the §9 scale ambitions plausible.

---

## 8. Limitations and Threats to Validity

- **Single-model dependence.** Behaviour is the behaviour of one hosted model family; we do not disentangle
  model-specific artifacts from architecture-driven ones, and cannot fine-tune.
- **Keyword vs. embedding retrieval (D-002).** Keyword overlap misses paraphrase and semantic relatedness that
  embeddings capture; this likely under-retrieves relevant-but-lexically-distinct memories and may suppress the
  associative leaps that drive some emergent behaviour. The trade for cost/determinism/transparency is
  deliberate but unquantified.
- **Small N, short horizons.** Ten agents over short recorded windows is far from the population scales where
  social phenomena become statistically visible; the headline run is also a pre-final baseline.
- **Pre/post-activation confound.** Because the analyzed run predates some phases, its nulls cannot be cleanly
  attributed to the final architecture.
- **Construct validity of the metrics.** Role specialization (Herfindahl over request types), "coherence"
  (stage-tagged handoffs), and convention detection (shared content words) are proxies; the LLM believability
  judge inherits the biases of the judging model.
- **Reproducibility.** See §7 — concurrent shared-state mutation means runs are not deterministic yet.

---

## 9. Future Work

1. **Long, fully-serialized runs** — the immediate need: multi-day runs with persisted memory, then re-run the
   harness so emergence claims move from *instrument-validated* to *observed*.
2. **Make the society talk** — diagnose the zero-conversation result (co-location choreography, social-readiness
   weighting, dialogue-vs-request balance in the unified prompt) and re-measure the conversation network.
3. **Close the determinism gap** — implement the snapshot→decide→apply concurrency model (D-006) for
   reproducible runs.
4. **Transport** — SSE/push to replace polling (D-004), removing playback stalls under LLM-bound production.
5. **Scale** — toward the populations of Park et al. (2024) and the many-agent regimes of Project Sid /
   AgentSociety, using the autosim cost geometry and the persona-count knob.
6. **Real revenue** — exercise the approval loop on genuine (human-mediated) outbound actions and measure the
   late-stage reward model end to end.
7. **Retrieval ablation** — quantify what D-002 costs by A/B-testing keyword vs. embedding retrieval on
   believability and emergence metrics.

---

## 10. Conclusion

Claudeville is an attempt to carry the generative-agent paradigm onto a modern agentic substrate without
losing what made it work, and to situate it in a governed economy with a concrete, safe objective. The
central lesson so far is cautionary and general: *a believable-agent system can pass its tests, render
correctly, and still have its cognitive heart switched off.* Re-activating that core, instrumenting it so the
claim "it behaves believably" is falsifiable, and verifying it with adversarial readers rather than only unit
tests, are the substantive contributions. The current society is cognitively active and economically coherent
but socially quiet and not yet earning — a baseline we report plainly and intend this document to track as the
system grows toward going live.

---

## References

*(Living list; entries reflect sources actually consulted. Venues/years marked "approx." pending final
verification.)*

1. J. S. Park, J. C. O'Brien, C. J. Cai, M. R. Morris, P. Liang, M. S. Bernstein. **Generative Agents:
   Interactive Simulacra of Human Behavior.** UIST 2023.
2. J. S. Park, L. Popowski, C. J. Cai, M. R. Morris, P. Liang, M. S. Bernstein. **Social Simulacra:
   Creating Populated Prototypes for Social Computing.** UIST 2022.
3. J. S. Park et al. **Generative Agent Simulations of 1,000 People.** 2024 (approx.).
4. C. Packer et al. **MemGPT: Towards LLMs as Operating Systems.** 2023. (Letta.)
5. **Reflective Memory Management (RMM) for long-term agent memory.** 2025 (approx.).
6. **A-MEM: Agentic Memory for LLM Agents.** 2025 (approx.).
7. W. Zhong et al. **MemoryBank: Enhancing LLMs with Long-Term Memory.** 2023 (approx.).
8. B. Jimenez Gutierrez et al. **HippoRAG: Neurobiologically Inspired Long-Term Memory for LLMs.** 2024 (approx.).
9. Y. Du et al. **HER: dual-layer (system-thinking / role inner-monologue / response) role-play.**
   arXiv:2601.21459, 2026.
10. X. Zhou et al. **SOTOPIA: Interactive Evaluation for Social Intelligence in Language Agents.** ICLR 2024.
11. DeepMind. **Concordia: Generative Agent-Based Modeling with a Game Master.** 2023–2024 (approx.).
12. G. Li et al. **CAMEL: Communicative Agents for "Mind" Exploration of LLM Society.** NeurIPS 2023.
13. W. Chen et al. **AgentVerse: Facilitating Multi-Agent Collaboration.** 2023 (approx.).
14. a16z. **AI Town.** Open-source real-time AI agent town (engineering reference).
15. Altera. **Project Sid / PIANO: many-agent civilizational simulation.** 2024 (approx.).
16. **AgentSociety: large-scale societal simulation with LLM agents.** 2024 (approx.).
17. **Multi-agent theory of mind (e.g., MuMA-ToM).** 2024–2025 (approx.).
18. **Emergent social conventions among populations of LLM agents.** Science Advances, 2025 (approx.).
19. **Cultural evolution of cooperation among LLM agents.** 2024–2025 (approx.).

---

## Appendix A — Scenario and persona roster (`startup_team_v1`)

**Objective (verbatim):** "Generate real-world money through legal, human-approved business actions."
**Team:** cooperative startup, 10 agents. **Starting resources:** 100 team points, \$0 cash, external actions
gated by human approval. **Reward model (early → late weights):** validated opportunity 3→1, reply received
5→3, meeting booked 10→5, **actual revenue 20→50**; early-only: useful research 1, approved request 2, draft
deliverable 2.

| Persona | Role | Mission |
|---|---|---|
| Nora Vale | strategist | Choose the most promising path to revenue and keep the team focused. |
| Milo Chen | market_researcher | Find niches, pains, buyer signals, and reachable prospects. |
| Iris Morgan | offer_designer | Turn market pain into specific service packages and guarantees. |
| Theo Grant | sales_drafter | Draft outreach, proposals, and follow-up messages for human approval. |
| Lena Ortiz | delivery_planner | Plan how the team would fulfill sold services with minimal risk. |
| Ravi Singh | analyst | Score opportunities and track evidence behind every decision. |
| June Park | operations_coordinator | Coordinate tasks, dependencies, and team handoffs. |
| Amara Cole | finance_scoring_agent | Track points, revenue evidence, costs, and survival pressure. |
| Felix Reed | tool_advocate | Submit town-center requests for tools, approvals, and resources. |
| Sofia Lane | critic_risk_officer | Challenge unsafe, low-quality, or unrealistic plans before approval. |

## Appendix B — Phase changelog (commits)

| Phase | Commit | Title |
|---|---|---|
| 1 | `f6650752` | Activate the Generative-Agents core + dual-layer cognition |
| 2 | `8253ad3b` | Offline evaluation harness + step telemetry |
| 3 | `fb5e3a48` | Relationship & theory-of-mind memory |
| 4 | `4e0b445d` | Multi-day goals & identity continuity (+7 verified fixes) |
| 5 | `087a843e` | Robustness: pathfinding, per-persona timeout, atomic writes, caching (+8 verified fixes) |
| 6 | `844c72ae` | Society scale, persona grounding, opt-in arbiter, emergence report (+2 verified fixes) |

Earlier "ship" pass (world fidelity, economy loop, replay, launch) and the Phase-A audit quick wins precede
these; see [`DEVLOG.md`](DEVLOG.md) and [`IMPROVEMENT-LOG.md`](IMPROVEMENT-LOG.md).

## Appendix C — Reproducibility

```bash
# Backend tests (155), evaluation (13) + emergence (9), Django (34)
env/Scripts/python.exe -m unittest discover -s reverie/backend_server/tests -p "test_*.py"
env/Scripts/python.exe -m unittest tests.test_eval_harness tests.test_emergence
( cd environment/frontend_server && DJANGO_DEBUG=True python manage.py test )

# Analyze a finished run (offline; writes JSON + Markdown to tools/eval/out/)
env/Scripts/python.exe tools/eval/analyze_run.py <sim_code> --emergence

# Run the simulation (frontend must run with DJANGO_DEBUG=True for static assets)
cd environment/frontend_server && DJANGO_DEBUG=True python manage.py runserver 8000
cd reverie/backend_server && python reverie.py     # binds :5000
```

Key tunables (env): `CLAUDEVILLE_CLAUDE_MODEL`, `CLAUDEVILLE_PERSONA_MOVE_TIMEOUT`,
`CLAUDEVILLE_BUFFER_AHEAD`, `CLAUDEVILLE_WORLD_ARBITER` (opt-in arbiter, off by default).

---

## Version history

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-06-23 | Initial draft: architecture, six-phase methodology, verification, baseline (run `…094847`) and null results, related work, references. Covers commits `f6650752`…`844c72ae`. |
| 0.2 | 2026-06-24 | **Corrected §6 + abstract**: the v0.1 "dead society" nulls were a stale/unsaved-run artifact. Added periodic auto-save; ran a fresh saved baseline (`…213240`, 800 steps) showing a complete conversation network (density 1.0), 362 persisted memory nodes, and emergent conventions. Economic throughput (revenue/handoffs) remains latent in a short window — flagged for a longer run. |
| 0.3 | 2026-06-25 | **Toward real money (Stage 0+1).** Closed the prompt-injection vector (LLM-1: untrusted-text sanitization). Added a tool **execution layer** (`tool_executor.py`): completed requests now actually run — read-only research executes (real if a search backend is configured, else an honest stub) and feeds results back into persona memory; outbound/spend tools are dry-run only. **De-fictionalized revenue**: it is no longer the agent's self-reported `expected_payoff` on approval; credited only via human-confirmed `record_delivery` evidence. Pushed the 6-phase roadmap to origin/main. Real outbound execution + revenue validation + an operator transaction-console UI remain future stages (§9). |
| 0.4 | 2026-07-02 | **Measured the economy; shipped the transaction console.** New economy analyzer (`tools/eval/economy.py`) on the 10-persona, 1,578-step run `…003901`: 17 requests, **all terminated at the human-approval gate** (0 transitions, 0 executions, \$0) — isolating the absent reviewer, not agent productivity, as the binding constraint; documented emergent agent-to-agent governance (risk-officer HOLD + checklist response). Shipped the operator console: persistent `artifacts.jsonl` for executed ToolResults, an HTTP `record-delivery` endpoint (evidence-validated, idempotent), and a review UI showing full drafts pre-approval with claimed payoffs marked unverified (§6.3 update). |
