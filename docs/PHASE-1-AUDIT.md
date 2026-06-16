# Phase 1 — Research & Analysis Audit (Source of Truth)

- **Project:** Claudeville — a fork of Stanford's *Generative Agents* simulation, ported from the OpenAI API to the Claude Agent SDK.
- **Audit date:** 2026-06-16
- **Scope:** The simulation codebase under `claudeville/` — backend (`reverie/backend_server/`), frontend (`environment/frontend_server/`), tests, tooling, config. The venv (`env/`) and third-party libraries are **out of scope**.
- **Method:** Five parallel auditors, each owning one dimension (backend core/concurrency, LLM/SDK integration, persona+memory+pathfinding, frontend+API, tests+tooling+config+security). Every finding is grounded in `file:line` evidence read from the real source. Tests were actually executed.
- **Status:** This document is the **source of truth** for all subsequent phases. The PRD ([PRD.md](PRD.md)) ranks goals from these findings; the Tech Spec ([TECH-SPEC.md](TECH-SPEC.md)) designs the target architecture around them.

---

## 0. Premise corrections (read first)

The audit overturned several assumptions in the project's own docs and in the audit brief. These materially change scope:

1. **The README's "keyword + recency retrieval" is dead code.** `retrieve_relevant_events/thoughts`, `get_last_chat`, and the `kw_to_*` keyword indexes are defined but **never called**. The live memory path (`_get_recent_memories`, `claude_structure.py:1692`) does *no* relevance matching — it returns most-recent-today plus the top-5 older nodes "by poignancy," and poignancy is a hardcoded constant. See **MEM-1 / MEM-2**.
2. **The venv and logs are NOT committed to git.** `git ls-files env/` → 0 files; `backend.out.log`, `django.err.log` (984 KB), and `__pycache__` are all gitignored. The 984 KB log is a *local-disk* and *observability* problem, not a repo-bloat problem.
3. **Tests exist, are green, and are hermetic.** 66 tests total (37 backend `unittest` + 29 Django `SimpleTestCase`) pass in < 0.3 s with no network and no live SDK call. Coverage is concentrated on the *new* "money-agent / town-center" layer; the *inherited* Generative-Agents core is essentially untested. See **OPS-4**.
4. **The model in use is `claude-sonnet-4-6`, not Opus.** `DEFAULT_CLAUDE_MODEL` (`claude_structure.py:52`) is a valid current model, but the module docstring claims "Full Opus agency," and `MAX_CONTEXT_TOKENS = 200000` is wrong for Sonnet 4.6 (1M window). See **LLM-6 / LLM-9**.
5. **There IS genuine tracked bloat:** ~6 MB+ of paid-asset `.zip` packs committed alongside their already-extracted PNGs (1,390 tracked `.png`), plus 26 large character PNGs staged-as-deleted in the working tree — so `HEAD ≠ working tree`. See **OPS-7**.

---

## 1. Executive summary

Claudeville is a bold, working re-architecture of Generative Agents: a single unified LLM call per persona-step, persistent Claude SDK sessions, a Phaser game UI, and a new "town-center / economy" control plane. The new code (economy, town-center, scenario runtime, runtime storage) is reasonably tested and well-factored. The risk is concentrated in three places:

- **Concurrency correctness (CRITICAL).** All personas run concurrently each step over *shared, unlocked* world state (`maze`, `personas_tile`, persona objects), and the per-step timeout abandons in-flight coroutines that keep mutating that state across step boundaries. This is nondeterministic and corrupting (**ARCH-1, ARCH-2**).
- **Cognitive fidelity regressed silently (CRITICAL).** The retrieval and reflection machinery that makes "generative agents" generative is dead/inert: retrieval ignores relevance, importance is a constant, reflection never fires (**MEM-1, MEM-2**). The system runs, but agents recall by recency only.
- **LLM robustness & multi-agent safety (CRITICAL/HIGH).** Persona-authored dialogue is injected verbatim into other personas' prompts (agent-to-agent prompt injection that can reach the human-approval `town_request` capability) (**LLM-1**); malformed responses and API errors both silently collapse to "idle" with no telemetry (**LLM-2**); there is no transport retry/backoff (**LLM-3**).

Plus a set of cheap, high-value security and hygiene fixes (CSRF disabled, hardcoded `SECRET_KEY`/`DEBUG=True`, unescaped LLM output → DOM, no CI, no dependency pinning).

**Finding counts:** 6 CRITICAL · 19 HIGH · 23 MEDIUM · 15 LOW.

By remediation effort: **Quick Win (<1d): 22** · **Structural (1–3d): 27** · **Deep Refactor (1wk+): 6**.

---

## 2. Findings register

Severity: 🔴 CRITICAL · 🟠 HIGH · 🟡 MEDIUM · ⚪ LOW. Effort: **QW** Quick Win (<1d) · **ST** Structural (1–3d) · **DR** Deep Refactor (1wk+).

| ID | Sev | Eff | Title | Primary location |
|----|-----|-----|-------|------------------|
| ARCH-1 | 🔴 | DR | Parallel personas mutate shared world state with no synchronization | `reverie.py:664-671` |
| ARCH-2 | 🔴 | ST | Move timeout abandons coroutines that keep mutating state across steps | `reverie.py:676-695` |
| LLM-1  | 🔴 | ST | Agent-to-agent prompt injection via verbatim conversation lines | `claude_structure.py:510-571` |
| MEM-1  | 🔴 | ST | Memory retrieval ignores relevance; keyword index is dead code | `claude_structure.py:1719-1771` |
| MEM-2  | 🔴 | ST | Poignancy/importance hardcoded → reflection subsystem inert | `perceive.py:16-28` |
| OPS-1  | 🔴 | QW | CSRF disabled globally + `@csrf_exempt` on every mutating API | `settings/base.py:48`, `views.py` |
| ARCH-3 | 🟠 | DR | `ReverieServer` god object — 7 responsibilities, ~1700 lines | `reverie.py:129-1829` |
| ARCH-4 | 🟠 | QW | Read/save Flask routes bypass the step lock | `reverie.py:462,330,545` |
| ARCH-5 | 🟠 | ST | `/simulate` runs ≤10 LLM steps synchronously in the request thread | `reverie.py:468-519` |
| ARCH-6 | 🟠 | ST | `save()` is non-atomic and CWD-dependent → corrupt runs | `reverie.py:1505-1539` |
| ARCH-7 | 🟠 | ST | Two divergent path/storage systems (`RunStorage` vs `fs_storage*`) | `reverie.py:140` vs `runtime_storage.py:15` |
| LLM-2  | 🟠 | ST | Malformed-JSON / API errors silently → idle, no telemetry | `claude_structure.py:843-854,1069-1074` |
| LLM-3  | 🟠 | ST | No retry/backoff for SDK transport errors (429/529/5xx) | `claude_structure.py:1065-1074` |
| LLM-4  | 🟠 | QW | `duration_minutes` taken from JSON unvalidated → TypeError/time corruption | `claude_structure.py:894` |
| LLM-5  | 🟠 | ST | Sleep compaction can't fire on long sleeps; failed summary discards context | `persona.py:255-259`, `claude_structure.py:1114-1120` |
| LLM-6  | 🟠 | ST | Token accounting input-only + overwritten; `MAX_CONTEXT_TOKENS` wrong for Sonnet | `claude_structure.py:1077-1087` |
| MEM-3  | 🟠 | ST | Pathfinding O(W·H)/wave, 150-iter cap; long paths silently fail | `path_finder.py:139-180` |
| MEM-4  | 🟠 | QW | `scratch.save()` crashes on `None` times; line-211 variable bug | `scratch.py:249,278,211` |
| MEM-5  | 🟠 | ST | Associative memory grows unbounded; O(n) save/retrieve; expiration never enforced | `associative_memory.py:63-69,152` |
| OPS-2  | 🟠 | QW | Hardcoded `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=[]`, no env override | `settings/base.py:23,26,28` |
| FE-1   | 🟠 | ST | Sprite bug: silent spritesheet 404 → all personas fall back to shared atlas | `main_script.html:801-807,915-952` |
| FE-2   | 🟠 | DR | 100% HTTP polling (health 3s / town 7s / pipeline 1s), no SSE; double-hop health | `main_script.html:1190-1192` |
| OPS-3  | 🟠 | QW | No CI / quality gates — tests & pre-commit are advisory only | repo root (no `.github/`) |
| OPS-4  | 🟠 | ST | ~5,900 LOC of simulation core has zero unit tests | `persona/**`, `reverie.py`, `maze.py`, `path_finder.py` |
| OPS-5  | 🟠 | QW | Zero dependency pinning; no lockfile; `claude-agent-sdk>=0.1.0` | `environment.yaml` |
| ARCH-8 | 🟡 | ST | `/movements` destructive pop; multi-client unsafe; silent gap loss | `reverie.py:370-396` |
| ARCH-9 | 🟡 | ST | `town_center.snapshot()` re-reads full JSONL ledger every call | `town_center.py:92-139` |
| ARCH-10| 🟡 | QW | Ledger appends not crash-safe (no fsync) and not concurrency-safe | `event_ledger.py:36-39`, `economy.py:109-113` |
| ARCH-11| 🟡 | QW | Conversation/encounter logic reaches into private persona attrs | `reverie.py:935,1039,1068` |
| ARCH-12| 🟡 | QW | Client-supplied persona positions unvalidated (KeyError / OOB) | `reverie.py:579-591` |
| LLM-7  | 🟡 | ST | Prompt bloat: ~250-line static rulebook re-sent every step; no `cache_control` | `claude_structure.py:631-677` |
| LLM-8  | 🟡 | ST | No cost controls: no `max_tokens`, no spend ceiling | `claude_structure.py:1003-1007` |
| LLM-9  | 🟡 | QW | Magic numbers / model params hardcoded; no central config | `claude_structure.py:44-52` |
| LLM-10 | 🟡 | DR | Module-global mutable state defeats testability; name collisions | `claude_structure.py:56,123-132` |
| LLM-11 | 🟡 | ST | `_send_prompt` re-entrancy: compaction calls `_send_prompt` from inside itself | `claude_structure.py:1086-1120` |
| MEM-6  | 🟡 | QW | `get_str_seq_events/thoughts` f-string tuple bug → garbage output | `associative_memory.py:390,396` |
| MEM-7  | 🟡 | QW | `retrieve_relevant_events` case-sensitivity bug (misses lowercase index) | `associative_memory.py:419-428` |
| MEM-8  | 🟡 | ST | `_resolve_location_to_tile` runs ≤4 BFS + rebuilds PathFinder per move; `random.sample` nondeterministic | `persona.py:1106-1132` |
| MEM-9  | 🟡 | QW | `act_check_finished` string-equality; two divergent "finished" definitions | `scratch.py:513-538` |
| MEM-10 | 🟡 | QW | `add_thought` depth `except Exception: pass` masks dangling refs | `associative_memory.py:279-283` |
| FE-3   | 🟡 | QW | Django `runserver` access log → stderr → 984 KB of polling noise; no `LOGGING` | `start.sh:68` |
| FE-4   | 🟡 | DR | 1561-line inline JS in HTML; ~40 globals; Django tags block extraction | `main_script.html:12-1561` |
| FE-5   | 🟡 | ST | Inconsistent error handling / method guards across views; `str(e)` leaked | `views.py:269,429,515` |
| FE-6   | 🟡 | QW | Unescaped persona text via `innerHTML` → stored-XSS-style risk from LLM output | `main_script.html:1408-1411,684` |
| OPS-6  | 🟡 | QW | Ruff config minimal (E,F,W only); pre-commit ruff `v0.1.9` vs on-disk `0.15.17` | `ruff.toml`, `.pre-commit-config.yaml:15` |
| OPS-7  | 🟡 | ST | Tracked paid-asset ZIP bloat (~6 MB) + 26 pending deletions (HEAD≠worktree) | `static_dirs/assets/.../map_assets/` |
| OPS-8  | 🟡 | ST | Fragile dual test-import convention; env-pinned; no documented test command | `tests/test_*.py` |
| ARCH-13| ⚪ | QW | `_synchronize_conversations` Step 7 dead `ended_groups` guard | `reverie.py:1352,1374` |
| ARCH-14| ⚪ | QW | `print_persona_action` uses salted `hash()` → color changes per run | `cli_interface.py:217` |
| ARCH-15| ⚪ | QW | Path-tester `except Exception: pass`; `rmtree` before non-returning loop | `reverie.py:1634,1815` |
| ARCH-16| ⚪ | QW | `meta.json` rewritten 3× during `__init__` | `reverie.py:159-164` |
| ARCH-17| ⚪ | ST | Coarse batch timeout discards completed personas' work | `reverie.py:676-695` |
| LLM-12 | ⚪ | QW | Naive substring/char-overlap fuzzy match mis-resolves locations | `claude_structure.py:968-974,1616-1634` |
| LLM-13 | ⚪ | QW | `bypassPermissions` + empty `allowed_tools` is a footgun if tools added | `claude_structure.py:1003-1007` |
| MEM-11 | ⚪ | ST | `_is_wall` infers opacity from empty arena → false walls/furniture | `maze.py:331-356` |
| MEM-12 | ⚪ | ST | `merge_chat_lines` unbounded / O(n²); chat duplicated per persona | `scratch.py:595-632` |
| MEM-13 | ⚪ | QW | Retrieval/perception magic numbers scattered, undocumented | `scratch.py:19-21,52-56` |
| FE-7   | ⚪ | QW | Dead/duplicated template data elements; `persona_name_str` never set | `home.html:9-16`, `main_script.html:3-10` |
| FE-8   | ⚪ | QW | CSS: 907 lines, duplicated panel/scrollbar blocks, no variables | `static_dirs/css/style.css` |
| FE-9   | ⚪ | ST | `api_simulate` 240 s synchronous proxy holds a Django worker | `views.py:148-161` |
| OPS-9  | ⚪ | QW | `.gitattributes` minimal — no binary/LFS rules for 1,390 PNGs | `.gitattributes` |
| OPS-10 | ⚪ | QW | `utils/__init__.py` dangling "re-export" comment, no export | `utils/__init__.py:26` |

---

## 3. CRITICAL findings (detail)

### 🔴 ARCH-1 — Parallel personas mutate shared world state with no synchronization
**Location:** `reverie.py:664-671` (and `641-662`). **Effort:** Deep Refactor.
Each step does `await asyncio.gather(*[run_persona_move(name, p) ...])`, and every `persona.move(self.maze, self.personas, self.personas_tile, ...)` receives references to the *same* shared `maze` (tile event sets) and `personas_tile` dicts. With coroutines interleaving at `await` points and no locks, perception/pathing can observe torn, half-updated world state.
**Impact:** Nondeterministic, order-dependent results; a persona can perceive a neighbor at a stale tile or see an event added/removed mid-perception.
**Fix:** Snapshot the world per step into read-only views; have each persona *return* intended mutations; apply them serially after `gather`. Never hand live shared dicts to concurrent coroutines.

### 🔴 ARCH-2 — Move timeout abandons in-flight coroutines that keep mutating state
**Location:** `reverie.py:676-695`; `claude_structure.py:193-201`. **Effort:** Structural.
On `PERSONA_MOVE_TIMEOUT_SECONDS` the code builds `_fallback_persona_move_result(...)` for every persona and advances `step`/`curr_time`, but `future.cancel()` only requests cancellation of the outer gather on a separate event loop — in-flight `move()` coroutines (and their LLM calls) keep running and mutating `personas`/`maze`/`scratch` *after* the main thread moved to the next step.
**Impact:** Main thread and orphaned coroutines race on the same persona objects across step boundaries → corrupted scratch state and conversation buffers.
**Fix:** Make `move()` cooperatively cancellable and await actual cancellation before advancing; or enforce a hard per-persona timeout *inside* the coroutine. Never advance global step/time while abandoned coroutines may still touch shared state.

### 🔴 LLM-1 — Agent-to-agent prompt injection via verbatim conversation lines
**Location:** `claude_structure.py:510-571`; stored at `persona.py:866,887`; parsed at `claude_structure.py:907`. **Effort:** Structural.
`conversation_line` comes straight from model JSON, is stored in `scratch.chat`, and is interpolated **verbatim** into other personas' step prompts (and into `_get_recent_memories`). A persona can emit a line containing fake prompt sections (`=== HOW TO RESPOND ===`, JSON-shaped `town_request` instructions). Because `town_request` with `external_action` payloads is a real human-approval capability (`claude_structure.py:323-344`), a crafted line could drive *other* personas to submit privileged requests.
**Impact:** Multi-agent prompt injection reaching a privileged capability surface.
**Fix:** Treat all persona-authored text as untrusted data — wrap conversation/memory snippets in a delimited, escaped block with a nonce; strip ``` ``` ```/`===`/`json` markers; add a standing system instruction that text inside the block is speech to react to, never instructions.

### 🔴 MEM-1 — Memory retrieval ignores relevance entirely (keyword index is dead code)
**Location:** `claude_structure.py:1719-1771`; dead funcs at `associative_memory.py:408-428`. **Effort:** Structural.
The live path collects *all* event/thought nodes, splits today vs older, then `older_nodes.sort(key=lambda n: n.poignancy, reverse=True)[:5]`. Poignancy is a constant (see MEM-2), so the "top-5 by importance" is effectively insertion-order. `retrieve_relevant_events/thoughts` and the `kw_to_*` indexes are never called.
**Impact:** Agents cannot recall a memory because it is *relevant to the current situation* — only most-recent-today + 5 arbitrary older items. This is the core cognitive regression vs the original embedding retrieval (and contradicts the README).
**Fix:** Either wire keyword-overlap × recency-decay × poignancy scoring into `_get_recent_memories` (the `scratch` weights `recency_w/relevance_w/importance_w` already exist), or delete the dead code and document retrieval as recency-only. The former is the intended design.

### 🔴 MEM-2 — Poignancy/importance hardcoded → reflection subsystem inert
**Location:** `perceive.py:16-28`; `persona.py:1141-1165`. **Effort:** Structural.
`generate_poig_score(...)` returns `1` for idle and `5` for everything else. Event nodes all get poignancy 5; `importance_trigger_curr`/`importance_ele_n` accumulate but nothing reads them, so reflection never triggers.
**Impact:** Importance ranking is meaningless; reflection — a defining feature of generative agents — never happens; persisted importance fields are dead weight.
**Fix:** Have the unified LLM call emit per-event importance (it already emits `thought.importance`) and feed it to `add_event`; reconnect the importance trigger to a reflection step, or remove the machinery if reflection is intentionally cut.

### 🔴 OPS-1 — CSRF disabled globally + `@csrf_exempt` on every mutating API
**Location:** `settings/base.py:48` (`CsrfViewMiddleware` commented out); `views.py:67,124,138,186,206,226`. **Effort:** Quick Win.
No CSRF protection anywhere; `api_save`, `api_simulate` (triggers expensive LLM runs), and town-center POSTs are invokable cross-origin.
**Impact:** Local-tool risk today (localhost + `DEBUG`), but the pattern is unconditional and would ship to any networked deployment as-is.
**Fix:** Re-enable `CsrfViewMiddleware`; drop `@csrf_exempt`; have the JS send `X-CSRFToken` (it already sends a custom header, so the plumbing exists).

---

## 4. HIGH findings (detail)

### 🟠 ARCH-3 — `ReverieServer` god object
`reverie.py:129-1829` — one ~1700-line class owns persona init, the Flask app + 12 routes, the cognitive step engine, conversation grouping/sync (`_synchronize_conversations` is a 340-line, 7-step method), encounter sequencing, persistence, the path-tester tool, and the CLI REPL. **Fix:** split into `StepEngine`, `ConversationManager`, `ReverieHTTPApp`, `SimulationCLI`, and a persistence component with injected dependencies. **DR.**

### 🟠 ARCH-4 — Read/save routes bypass the step lock
`/save` (`reverie.py:462`), `runtime_status` (`330`), `/health` (`545`) read/write `personas`, `step`, `personas_tile`, scratch while `_process_step` mutates them under `_step_lock`. Flask is `threaded=True`. **Impact:** a `/save` during a CLI `run` writes an inconsistent on-disk state; iterating `personas.items()` mid-mutation can raise. **Fix:** acquire `_step_lock` (or snapshot) in these handlers. **QW.**

### 🟠 ARCH-5 — `/simulate` blocks the request thread for up to minutes
`reverie.py:468-519` — docstring says "returns immediately after queueing," but the handler runs the loop inline holding `_step_lock`, returning only after ≤10 sequential cognitive steps. **Impact:** HTTP worker held open for minutes; proxy/browser timeouts abort it; contract is false. **Fix:** run steps on a background worker; `/simulate` enqueues and returns `{"status":"queued"}`; poll `/health`/`/movements`. **ST.** (Frontend mirror: **FE-9**.)

### 🟠 ARCH-6 — `save()` non-atomic and CWD-dependent
`reverie.py:1505-1539` writes `meta.json` directly then loops persona saves — no temp+rename, and paths derive from CWD-relative `fs_storage` (`utils/__init__.py:13`). **Impact:** crash mid-save desyncs meta/persona state; launching from any dir other than `backend_server/` breaks all paths. **Fix:** route persistence through `RunStorage` (which already does atomic temp+rename) and resolve roots from `__file__`. **ST.**

### 🟠 ARCH-7 — Two divergent path/storage systems
`reverie.py` uses both `self.run_storage` (`RunStorage`, absolute, atomic) and CWD-relative `fs_storage*` string constants (`reverie.py:140,838,1517`). They only coincide when CWD == `backend_server/`. **Fix:** delete the `fs_storage*` usages; route everything through `RunStorage`. **ST.**

### 🟠 LLM-2 — Malformed-JSON / API errors silently degrade to idle, no telemetry
Extraction is a greedy `re.search(r"\{.*\}", ..., DOTALL)` (`claude_structure.py:844`); on failure → empty `StepResponse` → `persona.py:795` returns idle. `_send_prompt` swallows *all* SDK exceptions into `("", None)` (`1069-1074`), indistinguishable from a parse failure. **Impact:** a whole sim can stall with every persona idle and no signal why; the greedy regex also mis-captures when prose contains braces. **Fix:** prefer fenced-block extraction then balanced-brace fallback; separate transport-error counters from parse-error counters; track per-persona failure rate. **ST.**

### 🟠 LLM-3 — No retry/backoff for SDK transport errors
`_send_prompt` (`claude_structure.py:1069-1074`) returns `("", None)` on timeout/exception with no retry; the only retry (`1229`) fires solely on `parse_errors`, re-sending on the same persistent connection. No handling of 429/529/5xx. **Impact:** transient overloads become permanent idle steps; under load every persona can fail the same step. **Fix:** bounded exponential backoff + jitter for retryable failures; recreate the client on connection-level errors; separate "transport retry" from "reformat retry". **ST.**

### 🟠 LLM-4 — `duration_minutes` unvalidated → TypeError / time corruption
`claude_structure.py:894` takes `duration_minutes` straight from JSON; it feeds `timedelta(minutes=...)` (`persona.py:874`). The day-planning parser clamps (`789-811`); the step parser does not. **Impact:** `"30 minutes"`/`null` → `TypeError`; negative → instant-complete; huge → persona pinned forever. **Fix:** coerce+clamp to 1–1440 in `parse_step_response`; validate the event triple elements are strings. **QW.**

### 🟠 LLM-5 — Sleep compaction can't fire on long sleeps; failed summary discards context
Compaction triggers only if `"sleep"`/`"go to bed"` is in the action description (`persona.py:256`), but skip-logic continues in-progress sleeps without re-entering `move()`, so `compact_for_sleep` runs at most once. Separately, `_trigger_compaction` disconnects/deletes the client (`claude_structure.py:1114-1120`) regardless of whether the summary call succeeded — a failed summary silently discards the persona's whole context. **Fix:** trigger compaction on the sleep *state transition*, not a substring; if the summary is empty/errored, keep the existing session and retry. **ST.**

### 🟠 LLM-6 — Token accounting input-only + overwritten; wrong context constant
`context_tokens` excludes output tokens and is *assigned* (not accumulated) each call (`claude_structure.py:1078-1083`); `MAX_CONTEXT_TOKENS = 200000` (`44`) is wrong for Sonnet 4.6 (1M), so the 160K compaction limit is ~16% of the real window. **Impact:** compaction over-fires or never fires; reported usage % is misleading. **Fix:** derive the window from the model; track cumulative session size; include output tokens; add a regression test. (UNVERIFIED: exact `ResultMessage.usage` semantics for a persistent multi-turn session — confirm whether it's per-turn or cumulative.) **ST.**

### 🟠 MEM-3 — Pathfinding O(W·H) per wave-step, 150-iter cap, silent failure
`path_finder.py:139-180` rescans the full 140×100 grid every wave-step (no frontier queue), capped at 150 iterations → worst case ~2.1M cell visits per query, and **paths longer than 150 tiles silently return a degenerate `[end]`** (teleport / unreachable) with no error. `find_path_to_nearest` rebuilds the collision map per call. **Fix:** `deque`-based BFS frontier; cache the base collision map per instance; return an explicit "no path" sentinel; raise/remove the cap. **ST.**

### 🟠 MEM-4 — `scratch.save()` crashes on `None` times; line-211 variable bug
`scratch.py:249,278` call `.strftime(...)` unconditionally on `curr_time`/`act_start_time`, both initialized to `None`. **Impact:** saving a never-acted persona throws `AttributeError`, losing the save. Also `scratch.py:211` sets `self.curr_time = None` in the `act_start_time is None` branch (wrong variable). **Fix:** guard both `strftime` calls; fix line 211 to `self.act_start_time = None`. **QW.**

### 🟠 MEM-5 — Associative memory grows unbounded; O(n) save/retrieve; expiration never enforced
`seq_event/seq_thought/seq_chat` and `kw_to_*` only grow; `save()` rewrites the entire `nodes.json` each time (`associative_memory.py:152`); `_get_recent_memories` scans+sorts the whole history every step. `expiration` is set (`persona.py:731`) but never swept. **Impact:** per-step cost is O(lifetime perceptions) — the primary long-run scaling wall. **Fix:** bounded recency window for prompt assembly; expiration sweep on load/save; incremental/periodic JSON compaction instead of full rewrite. **ST.**

### 🟠 OPS-2 — Hardcoded `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=[]`
`settings/base.py:23,26,28` — the only settings module; these dev values are the deployed values, with no env-var path. `pre-commit`'s `detect-private-key` does not catch Django secret keys. **Fix:** read all three from env with safe defaults; add a `production.py` with `DEBUG=False`; rotate the committed key. **QW.**

### 🟠 FE-1 — Sprite bug root cause: silent spritesheet 404 → shared atlas fallback
`main_script.html:801-807` loads per-persona sheets keyed by name; `915-952` falls back to the shared `"atlas"` "down" frame when `textures.exists(sprite_key)` is false. The per-persona PNGs exist and are valid (96×128); Phaser does **not** throw on a missing image, and there is **no `loaderror` handler** — so when a sheet fails to resolve (static path/`collectstatic` issue or a name-mismatch), every persona silently becomes the same generic sprite, invisibly. **Fix:** add `this.load.on('loaderror', …)` logging; verify the static URL serves `assets/characters/<Name>.png`; fail loudly rather than substituting an identical sprite. **ST** (small fix; confirming the static-path cause requires running the stack).

### 🟠 FE-2 — 100% HTTP polling, no SSE/WebSocket; double-hop health
`main_script.html:1190-1192` — three forever-timers: health 3s (browser→Django→Flask double hop), town-center 7s, pipeline 1s — running even while paused. This is the direct cause of the 984 KB log and constant background load. **Fix:** replace with a single SSE stream from Flask; at minimum, stop health/town-center timers while paused and back off when idle. **DR** for SSE; **QW** for pause-aware backoff.

### 🟠 OPS-3 — No CI / quality gates
No `.github/`; the 66 green tests and ruff/pre-commit are opt-in and never run automatically. **Fix:** add `.github/workflows/ci.yml` that builds the env, runs both test suites, and runs `ruff check` + `ruff format --check` + `pre-commit run --all-files`. **QW.**

### 🟠 OPS-4 — ~5,900 LOC of simulation core has zero unit tests
Untested: `associative_memory.py`, `scratch.py`, `maze.py`, `path_finder.py`, `perceive.py`, `spatial_memory.py`, `cli_interface.py`, and all SDK-calling paths of `claude_structure.py`/`persona.py`. The deterministic, network-free pieces (A*, tile math, retrieval scoring, `parse_step_response` edge cases) are cheap to test. **Fix:** deterministic unit tests for pathfinding/maze/memory/parsing; a thin fake `ClaudeSDKClient` for the LLM round-trip; add coverage measurement. **ST.**

### 🟠 OPS-5 — Zero dependency pinning / no lockfile
`environment.yaml` uses floors only (`claude-agent-sdk>=0.1.0`; installed is `0.2.101`). No `conda-lock`/`requirements.txt`/freeze. **Impact:** non-reproducible builds; a fast-moving SDK breaking change silently breaks new installs while existing envs keep working. **Fix:** commit a lockfile; pin `claude-agent-sdk==0.2.x`, `django`, and `ruff` (reconcile with the stale pre-commit pin). **QW.**

---

## 5. MEDIUM & LOW findings

MEDIUM and LOW findings are fully specified (location, evidence, impact, fix, effort) in the **register table (§2)**. Highlights worth early attention because they are cheap and user-visible or correctness-affecting:

- **FE-6 (QW, security):** persona/LLM text written via `innerHTML` (`main_script.html:1408`) → escape with `textContent`.
- **MEM-6 (QW, bug):** `get_str_seq_*` f-string tuple bug emits tuple-repr garbage.
- **MEM-7 (QW, bug):** `retrieve_relevant_events` case mismatch — relevant if MEM-1 is wired in.
- **MEM-9 (QW, bug):** two divergent "action finished" predicates; unify on a `>=` datetime compare.
- **ARCH-12 (QW, robustness):** validate client-supplied positions (bounds + missing key).
- **FE-3 (QW, observability):** add a `LOGGING` config to silence `django.server` 2xx access lines.
- **LLM-7 / LLM-8 (ST, cost):** stop re-sending the static rulebook every step; add `max_tokens` + a spend ceiling.
- **OPS-7 (ST, hygiene):** drop committed asset ZIPs; reconcile the 26 pending deletions so `HEAD == working tree` before Phase 2.

---

## 6. As-is architecture (per-dimension notes)

**Backend.** `reverie.py` is the monolith (`ReverieServer` god object + `ConversationGroup` + `__main__` launcher). Supporting modules are thin and sound: `runtime_storage.py` (atomic JSON, fork resolution), `event_ledger.py`/`economy.py` (append-only JSONL, `ToolRegistry`, `RequestState`), `town_center.py` (folds ledgers into a control-plane snapshot), `scenario_config.py`/`scenario_runtime.py`, `agent_requests.py`, `cli_interface.py` (pure presentation). **Concurrency:** one backend process; a persistent background asyncio loop (in `claude_structure`) runs all persona LLM work; the main thread drives the sim; a daemon thread runs Flask `threaded=True`; a single `_step_lock` serializes step processing between CLI and HTTP but read/save endpoints bypass it.

**A simulation step:** clear prior game-object events → overwrite backend tiles from client `environment` (treated as authoritative) → detect new encounters and run them sequentially → `asyncio.gather` all remaining persona `move()` with a 15 s batch timeout (no-op fallback on timeout) → `_synchronize_conversations` (340-line group merge) → write merged chat into each scratch → increment step/time → append a `simulation_step` ledger event + write an env snapshot + enqueue a movements packet. Frontend GET-polls `/movements` to animate.

**LLM call path:** `persona.move` → skip-logic → `UnifiedPersonaClient.step()` → `_send_prompt()` → persistent `ClaudeSDKClient.query()` (`claude-sonnet-4-6`, `bypassPermissions`, no tools, no `max_tokens`). Response scraped with greedy regex → `json.loads` → `StepResponse` with mostly-unvalidated `.get()` defaults → applied to `scratch`. Compaction: threshold (input-token count ≥ 160K of a wrong 200K constant) or sleep keyword; both rebuild the session from a summary, and a failed summary discards context.

**Memory:** three parallel newest-first lists + `id_to_node` + lowercase keyword indexes in `AssociativeMemory`, serialized by full JSON rewrite. Embeddings removed (`embedding_key` is now just the description). Retrieval is recency + constant-poignancy; keyword index, `kw_strength`, `retrieve_relevant_*`, `get_last_chat` are dead code. Unbounded growth; no expiration sweep.

**Frontend:** Browser → Django (thin `requests` proxy, port 8000) → Flask (port 5000). SQLite is `:memory:` and unused — all state is JSON under `storage/`. One full-screen Phaser 3.55.2 game with a 1561-line inline-JS engine; HTML overlay panels updated by DOM manipulation. Communication is 100% polling (no push). A `X-Claudeville-Client: stream-v2` handshake (`views.py:23-34`) returns HTTP 409 on mismatch and the JS auto-reloads on a new backend run.

**Tests/tooling:** 66 hermetic tests, concentrated on economy/town-center/scenario/runtime-storage (good there); inherited GA core untested. Local ruff + pre-commit intent undermined by no CI, version skew, no dependency pinning, hardcoded committed secrets, and brittle dual test-import conventions.

---

## 7. Open questions to resolve in the PRD / Tech Spec

1. **Memory direction (MEM-1/MEM-2):** restore relevance-based retrieval + reflection (toward original GA fidelity), or formally adopt "recency-only" and delete the dead machinery? *This is the single biggest product decision.*
2. **Model & context policy (LLM-6/LLM-9):** is Sonnet 4.6 the intended default, or should it be Opus 4.8? Correct the context-window constant accordingly.
3. **Transport architecture (FE-2/ARCH-5):** commit to SSE/WebSocket, or stay on polling with pause-aware backoff for now?
4. **Determinism (ARCH-1, MEM-8):** is reproducibility a goal? It drives the concurrency refactor and the `random.sample` removal.
5. **Deployment target:** local-only tool, or networked? Determines how hard the security findings (OPS-1/OPS-2/FE-6) must be enforced.
