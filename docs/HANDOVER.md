# Claudeville — Developer Handover

> Self-contained onboarding for a new dev agent (or human) taking over Claudeville. Written 2026-07-11
> at the end of "Phase 1 — Make it watchable." Read this, then `docs/DEVLOG.md` (top few entries), then
> run the tests. Everything below is the source of truth; the detailed phase plan and review reports that
> produced it lived outside the repo, so their essential content is folded in here.

Repo (local): `f:\AI Project\Vibe Coding\Sim LLM City\Claudeville\claudeville`
Git: branch `main`, remote `origin` = https://github.com/autosolutionsai-didac/AutoMoneyVille.git

---

## 0. THE ONE DISTINCTION YOU MUST NOT GET WRONG

Two kinds of "AI" are involved:

- **The PERSONAS** (the 10 simulated townspeople) think by calling the **Claude Agent SDK** — one
  persistent `claude` CLI subprocess per persona. This is the sim's brain. Do **not** rip it out or swap
  the model unless the user explicitly asks. Model id is env `CLAUDEVILLE_CLAUDE_MODEL` (default a
  Sonnet-class model).
- **YOU** (the dev agent) work *on* the code. Whatever model you are is orthogonal to the sim's brain.

Never confuse "improve the agents' intelligence" (prompt/memory/model-routing work *inside* the sim)
with "which model the developer is." Different layers.

---

## 1. WHAT CLAUDEVILLE IS — HISTORY & VISION

Lineage: a fork of Stanford's **Generative Agents / Smallville** (Park et al. 2023), ported from the
original OpenAI/reverie stack to the **Claude Agent SDK**. A pixel-art town where ~10 LLM personas
perceive, remember, reflect, plan, converse, and move on a tile map, rendered in Phaser 3 in the browser.

The differentiator (this is the product): on top of the society sits a **human-governed economy**. A
"Town Center" control plane lets agents file typed requests to use business tools (web research,
drafting, outbound email/posting, spend). Read-only research executes for real (Firecrawl live search);
outbound/spend tools are **DRY-RUN only** (a reviewable draft, never actually sent/spent); revenue can
**only** be credited by a human via `record_delivery` with typed evidence — agents can never self-report
making money. Standing north-star goal: *eventually generate real-world money through legal,
human-approved business actions*, added in stages with the human always in the loop.

The product vision (from a deep review of SOTA agent-town products — AI Village, Project Sid, Showrunner,
Death by AI, Neuro-sama): every "AI town" that stayed a tech demo died of polite chatter. The ones that
lived had **real stakes, visible reasoning at decisive moments, curated digests over raw feeds,
persistent characters, and a town that summons its operator.** So the transformation target is: **from
research demo → "an office reality-show you govern."** Claudeville already owns the hardest part (a real
economy + human approval gate); the work is making it legible, alive, and meaningful to watch and operate.

There is a SEPARATE sibling repo `autosolutionsai-didac/SimMoneyWorld` (a sandbox-first, fully-simulated
variant) worked in another window — **OUT OF SCOPE.** Do not touch it.

---

## 2. HOW TO RUN & TEST (do this first to establish a baseline)

Stack: Python 3.11; Django frontend on **:8000** (serves the Phaser game + proxies the backend); Flask
backend on **:5000** (the sim engine — `ReverieServer`); a uv venv at `env/Scripts/python.exe`. Windows
machine (PowerShell + Git Bash both available).

Launch the whole stack (kills stale servers, loads `.env`, starts backend + frontend, waits for health):

```
powershell -ExecutionPolicy Bypass -File scripts\run_claudeville.ps1
```

Then open http://localhost:8000/simulator_home and press ▶ Play. **The first step takes ~60–120s** (cold-
starts 10 Claude sessions + day planning) — expected; the UI now says so.

Offline, instant, session-proof way to watch a recorded run (no LLM latency):
`http://localhost:8000/replay/<sim_code>/1/` (recorded runs live under
`environment/frontend_server/storage/runs/`).

Tests — run all three + ruff before and after any change; keep them green (prefix Python with
`PYTHONUTF8=1` on Windows):

```
Backend:  env\Scripts\python.exe -m unittest discover -s reverie/backend_server/tests -t .
Eval:     env\Scripts\python.exe -m unittest discover -s tests -t .
Django:   cd environment/frontend_server && ..\..\env\Scripts\python.exe manage.py test
Lint:     env\Scripts\python.exe -m ruff check reverie/ tools/ tests/
```

Current green baseline: **230 backend + 78 Django** tests, the focused Claudeville world/renderer suites,
map validators, and ruff are clean.

---

## 3. ARCHITECTURE MAP

- `reverie/backend_server/reverie.py` — **THE CORE.** `ReverieServer`: the step loop; an "autosim"
  producer thread that simulates ahead of playback into a movement buffer (backpressure-aware, pauses when
  nobody polls); Flask routes; per-step atomic movement/environment snapshots; save/autosave. Personas
  within a step run concurrently (`asyncio.gather`); steps are serialized by a step lock.
- `reverie/backend_server/persona/` — cognition:
  - `prompt_template/claude_structure.py` — the **unified per-step Claude call**: prompt assembly
    (`build_step_prompt`), the per-persona session pool, token/compaction handling, JSON parse.
  - `cognitive_modules/{perceive,retrieve,reflect,plan}.py` — the GA loop.
  - `memory_structures/{associative_memory,scratch,spatial_memory,relationship_memory,goal_memory}.py`.
  - `persona.py` — per-step `move()` orchestration + skip logic (many ticks cost zero LLM calls).
- `reverie/backend_server/{town_center,economy,tool_executor,world_arbiter,scenario_config,text_safety}.py`
  — the governed economy: request lifecycle (`proposed→approved→completed…`), append-only JSONL ledgers
  (requests/rewards/artifacts), dry-run outbound, evidence-gated revenue (`record_delivery`), an optional
  dormant "Game Master" arbiter, and LLM-1 input sanitization.
- `environment/frontend_server/` — Django:
  - `translator/views.py` — thin proxy to the Flask backend + page renderers.
  - `frontend_server/urls.py` — routes.
  - `templates/home/{home.html, main_script.html, inspector_script.html, feed_script.html}` — the game
    page (Phaser + all UI JS is inline here; `main_script.html` is large).
  - `static_dirs/css/style.css` — all UI styling.
  - `static_dirs/assets/claudeville/world.json` — the active data-driven world contract. It selects the
    native-16 v45 Tiled runtime, ordered layers, curated atlases, English aliases, collision data, and the
    schema-v2 character catalog. The old painted Claudeville scene remains load-failure fallback only.
  - `static_dirs/js/world_collision.js` — collision-aware spawn and historical-replay projection helpers.
- `tools/eval/` — read-only run analyzers (metrics, emergence, economy, believability_judge, report);
  e.g. `python -m tools.eval.economy <sim_code>`.
- `tools/mapgen/` — authoritative world generation plus the native-16 Tiled authoring/compiler and curated
  Modern Pixels asset pipeline (`town_spec.json → maze CSVs`, TMJ → deterministic runtime JSON), validated
  through the real engine by `validate_world.py` and exact collision-parity tests.
- `scripts/run_claudeville.ps1` — the launcher (must stay ASCII-only — see §8).

---

## 4. NON-NEGOTIABLE CONSTRAINTS

- **D-002: NO vector embeddings, anywhere.** Retrieval/memory is keyword + heuristic only. Hard design
  rule (there are cheap, embedding-free ways to improve retrieval — see roadmap).
- **LLM-1 (prompt-injection defense):** any external or agent-authored text must pass
  `text_safety.sanitize_external` before re-entering a prompt; in the browser, agent text renders via
  `textContent` (never `innerHTML`). Keep this discipline.
- **Money/safety model:** outbound + spend tools NEVER really execute (dry-run artifacts only). Revenue is
  credited ONLY by a human via `record_delivery` with typed evidence. Do not add a path where an agent
  self-credits money or an outbound tool really fires without an explicit env flag + allow-list + human
  confirm (the deliberately-gated future "Stage 2").
- **Secrets:** `.env` is gitignored; never commit keys; verify `git diff` has no key before any commit.
  (Firecrawl/Exa search keys passed through chat historically and should be rotated by the user.)
- **Windows:** keep every `.ps1` ASCII-only (PowerShell 5.1 reads no-BOM UTF-8 as ANSI and a stray
  em-dash becomes a string-terminating curly quote — this already broke the launcher once). Use
  `PYTHONUTF8=1` for Python; most file I/O should pass `encoding="utf-8"`.
- **Git etiquette:** commit only when the user asks; do NOT add a `Co-Authored-By` trailer; branch off
  main if needed. Ask before destructive/irreversible actions.
- **Repo hygiene:** read a file before editing; prefer editing existing files; keep files under ~500
  lines; put temp/experimental files in a scratch dir, never the repo root (a past shell mishap littered
  the root with ~160 junk dirs — now cleaned).
- The repo's `CLAUDE.md`/`AGENTS.md` contain a lot of "ruflo/claude-flow swarm" boilerplate that is mostly
  aspirational noise — you are NOT required to use any of that MCP/swarm tooling. The real rules are here.

---

## 5. CURRENT STATE (Claudeville v45 promoted)

The Modern Pixels implementation is recorded by **`dbeefc07`** and its follow-up handover commit. It is
merged to `main` and pushed to `origin/main`. The only intentionally excluded local items are browser
scratch captures and generated `tools/eval/out/*` reports. Full narrative history is in `docs/DEVLOG.md`
(reverse-chronological — read the top few entries first).

**CLAUDEVILLE MODERN PIXELS TOWN — COMPLETE & promoted:**

- **Map contract:** `88×48 @ 32px` logical simulation grid and `176×96 @ 16px` visual grid, preserving the
  original `2816×1536` world dimensions. `world.json` selects
  `visual_candidates/browser-target-v45/claudeville_v2.json`; the editable source is
  `visuals/claudeville_target_v45.tmj`.
- **Composition:** a hand-authored three-row town with Bank, Home 1, University, Agent Academy, Market and
  Post Office in the north; Workshop, Community Center, Central Plaza, Claudeville Cafe and Library in the
  middle; Homes 2–10 and Town Hall in the south. Facilities use distinct, purposeful cutaway interiors.
- **Assets:** only curated runtime derivatives from licensed Modern Exteriors, Modern Office and full Modern
  Interiors sources are committed, with required LimeZu/0a3r credits. Raw vendor packs, generators, ZIPs,
  Free Interiors, old versions, previews, and unused 32/48px duplicates remain excluded.
- **Semantics:** 21 sectors, 73 authored zones, 70 reachable interactions/stance cells, 38 semantic objects,
  and 1,235 visual props. All active names, descriptions and UI are English; Spanish names survive only as
  hidden historical input aliases.
- **Navigation:** the backend matrices remain authoritative. The generated Tiled collision layer has zero
  mismatches, all solid prop footprints are blocked, and all 2,080 walkable cells form one connected
  component (**100% connectivity**).
- **Residents:** the ten canonical residents use distinct licensed/generated 16×32 sprite sheets at native
  scale, bottom-centre anchors, explicit four-direction idle/walk frames, portraits and provenance in the
  schema-v2 character manifest. Historical replay positions project to the nearest safe logical cell.
- **Renderer:** Phaser renders the actual Tiled tile/object layers with nearest-neighbour pixels, foot-based
  depth sorting, collision-aware actors, camera drag/zoom/follow, inspector, replay controls, speech bubbles,
  and day/night tinting. The accepted legacy image is load-failure fallback only.
- **Verification:** 85 focused world tests (1,354 subtests), 16 renderer/collision tests, 230 backend tests,
  78 Django tests, ruff, `validate_world.py`, and the replay smoke passed. Playwright captures at full-town,
  100%, 150%, 200%, 300% actor and mobile views loaded 1,235 objects with no missing assets, console errors,
  failed requests, or fallback activation.

The earlier **`1f74efcd`** milestone consolidated the transaction console, economy analyzer and Phase 1:

**PHASE 1 "Make it watchable" — COMPLETE & green:**

- **Engine honesty:** un-swallowed process-wide `stderr` (tracebacks/port-bind errors were being
  discarded); atomic `meta.json` saves; capped pending-movement queue; encounters run concurrently +
  deduped per persona (fixed a latent double-move when 3+ agents met); added the missing LLM-concurrency
  semaphore (env `CLAUDEVILLE_LLM_CONCURRENCY`, default 10).
- **Transaction console:** **Approve now executes** (`approved→completed` chains server-side: one click =
  approve + run tool + persist artifact + feed agent memory; previously "Approve" parked requests in
  unreachable limbo and only "Done" executed); risk-sorted approval-queue browser; a reviewer-note
  textarea (agents read the note back in their prompts — the operator's one steering channel); an artifact
  browser with full dry-run draft bodies.
- **Operator summons:** browser Notification + title-bar `(N)` badge + chime + toast on a new
  approval-required request. New endpoints: Flask `/persona/<name>/state`, `/events?after_id=`; Django
  proxies `api/persona/<name>/state/`, `api/events/`.
- **Agent inspector:** click a persona → live drawer (currently, schedule w/ current block, goals,
  relationships, last-20 memory stream).
- **Event feed:** 500-event ring buffer + filterable left panel; conversations, requests, revenue, day
  rolls; chat mirrors in permanently (the popup used to wipe after 5s); rows jump the camera / open the
  inspector.
- **Visual juice:** sprite shadows; real speech bubbles (pop tween, above the night overlay); lerped
  follow-cam with a 🎥 toggle; pointer-centered zoom; hour-keyed MULTIPLY day/night color ramp.
- **UX honesty:** elapsed-seconds counter during LLM waits; "first step ~60-120s" message; fixed `/replay`
  pages (REPLAY badge, no phantom live polling); removed duplicate DOM ids; Space=play/pause
  (Shift+Space=skip); first-run hint overlay; saves-list `alert()` → disabled state.

---

## 6. THE AGREED ROADMAP (P1 and P2 visuals done; intelligence/P3→P4 next)

Sequencing reviewed and approved by the user as **P1→P2→P3→P4**.

### P2 "New world, new mind" (~2-3 weeks) — two parallel tracks

**(A) INTELLIGENCE** (highest leverage; mostly `claude_structure.py` + `persona/*`):

1. **Feed research CONTENT into agents.** A completed `web_research` stores only the summary line
   ("5 sources on X"); the actual titles/URLs/snippets (`ToolResult.detail`) are persisted to
   `artifacts.jsonl` but NEVER reach any prompt/memory. Route a trimmed, sanitized detail into the
   requester's memory + let teammates read a one-line artifact excerpt. **Single highest-leverage coupling
   fix** — live search currently buys agents a source *count*, not knowledge.
2. **Tiered model routing:** route routine ticks to a cheap/fast model (Haiku-class), keep the
   Sonnet-class model for decisions/dialogue, reserve an Opus-class model for reflections + a future
   "director." The skip-logic already computes the routing signal (~45-55% cost cut; with caching + gating,
   estimated ~85-95% total).
3. **Prompt-cache alignment** (freeze persona system prompt first, volatile world state last) + compact
   context around ~100-150K instead of ~800K + stop re-sending the full accessible-locations tree every
   step (send deltas). Big input-token cuts.
4. **Structured JSON outputs** (json_schema) to kill the regex-parse + full-prompt-retry burn.
5. **Fix thought/reflection retrieval:** thought nodes get constant keywords ("thought"), so a persona's
   entire reflective life is invisible to keyword retrieval. Derive keywords from content (still
   D-002-compliant); enforce node expiration; nightly memory consolidation at sleep-compaction.
6. **A real conversation subsystem:** a bounded multi-turn dialogue loop within one step (a chat resolves
   in 1 step instead of ~6) with a slim dialogue-only prompt; group scenes via a cheap arbiter.
7. **Interview-grade persona documents** (Stanford's 1000-people result: rich "life-interview" persona
   docs massively outperform trait lists — one-time generation, hand-edited for drama).

**(B) VISUALS — COMPLETE:** Claudeville v45 is the promoted native-16 Tiled town described in §5. Future
visual work is refinement rather than another retile: hand-tune individual rooms/props in the source TMJ,
recompile deterministically, run collision parity, and inspect the Playwright screenshot matrix before
changing `world.json`. Never commit or serve the raw licensed vendor directories.

### P3 "The show + the game" (~2 weeks)

- **"Claudeville Gazette":** end-of-day LLM pass over the event log → 3-5 storylines with continuity (the
  Showrunner move; the sim is the writers' room, the digest is the show).
- **Live reasoning pane** shown ONLY at decisive moments (approvals, big decisions) — drama, not noise.
- **Economic stakes that mean something:** seed starting resources into the ledger, a daily burn (survival
  pressure), a runway/goal line surfaced BOTH in the console AND inside agent prompts (agents currently
  can't see team points/revenue), and actually consume the scenario's `reward_model` (dead code today).
- **Wire the dormant `world_arbiter`** as reviewer-assist on the approval card (code-complete, tested,
  currently unreachable).
- **An "event director"** that injects shocks (audit, shortage, new arrival) when flatness metrics
  (conversation entropy, wealth Gini, request rate) say the town went quiet (Project Sid: societies stall
  without injected motivation).
- **The Telegram approval bot** (design agreed: standalone long-poll process using `getUpdates`, chat-id
  allow-list, plain-text messages, Approve/Reject inline buttons hitting the existing transition endpoint)
  so the operator can approve from their phone.

### P4 "Scale & share" (open-ended)

SSE push + per-client cursors (multi-viewer); a `CLAUDEVILLE_HEADLESS` mode (overnight runs, then watch
the digest/replay — fits the Batch API at 50% off); storage sharding for multi-day runs; session pooling
toward 25+ personas; competitive teams / public spectator replay.

### DEFERRED (needs explicit user go)

Real outbound (`send_email` actually sends) behind `CLAUDEVILLE_OUTBOUND_ENABLE` + recipient allow-list +
per-action human confirm. This is "Stage 2" of the money path — **do not enable without the user.**

---

## 7. IMMEDIATE NEXT STEPS (in order)

1. Launch the stack (`scripts\run_claudeville.ps1`) and use the promoted v45 world for all new live runs.
   Keep v1 and the accepted legacy image unchanged for historical replay/load-failure rollback.
2. If visually refining the town, edit `claudeville_target_v45.tmj`; do not reintroduce procedural prop
   scattering or edit compiled runtime JSON by hand. Recompile, validate exact collision parity, and repeat
   the full-town/district/zoom/mobile Playwright review before promotion.
3. Continue **P2 intelligence A1** (feed sanitized research detail into agents), then model tiering and
   prompt-cache/location-delta work. The visual track no longer blocks these milestones.

---

## 8. HARD-WON GOTCHAS

- Servers die at session/tool boundaries; the offline `/replay/<sim>/<step>/` page is the reliable way to
  watch a society without a live backend.
- Windows cp1252: the launcher and any `.ps1` must be ASCII (§4). Python needs `PYTHONUTF8=1`.
- The autosim producer PAUSES when nobody polls `/movements` (cost guard) — a headless run needs the
  (to-be-built) `CLAUDEVILLE_HEADLESS` decoupling, or it stalls.
- A completed request executes its tool ONLY on the `completed` transition (not `approved`) — P1's
  approve-executes chaining depends on this; keep it.
- Many persona ticks are intentionally LLM-free (skip logic) — don't "fix" that; it's the cost frame.
- The compress-for-replay script assumes every step's packet has every persona; a live run can omit one
  (timeout/encounter) — the carry-forward guard in `compress_sim_storage.py` handles it; don't regress it.

---

## 9. READ THESE IN-REPO DOCS FIRST

`docs/DEVLOG.md` (narrative history, newest-first — start here), `docs/PAPER.md` (academic write-up incl.
the measured "17/17 requests died at the absent approval gate" result that motivated the console),
`docs/DECISIONS.md`, `docs/IMPROVEMENT-LOG.md`, `docs/PRD.md`, `docs/TECH-SPEC.md`, `docs/PHASE-1-AUDIT.md`.

---

## 10. WORKING AGREEMENT

Make focused, tested changes; keep all suites green and ruff clean after every change; write a DEVLOG
entry when something meaningful ships or is discovered (reverse-chronological — keep the reasoning + dead
ends). Prefer reusing existing patterns over inventing new ones. For anything destructive, outward-facing,
or scope-changing (enabling real outbound, deleting data, committing/pushing, swapping the persona model),
STOP and ask the user first. Lead updates with the outcome, in plain prose.
