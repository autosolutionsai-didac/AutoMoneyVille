# Improvement Log

Chronological record of changes made during the Claudeville improvement pass. One row per merged change. Reference the finding ID(s) from [PHASE-1-AUDIT.md](PHASE-1-AUDIT.md) and the goal (G1–G9) from [PRD.md](PRD.md).

**How to use this file:**
- Add a row when a change merges (not when started — use the todo/issue tracker for in-flight work).
- "Verification" = the command(s) or metric that proves it works (e.g. `python -m unittest discover -s reverie/backend_server/tests`, a determinism-harness run, a before/after token count).
- When a finding is fully closed, tick it off in the **Findings burndown** table and note the PR/commit.
- Record any decision made along the way in [DECISIONS.md](DECISIONS.md) and link it here.

---

## Change log

| Date | Phase | Finding(s) | Goal | Change | Verification | PR / commit |
|------|-------|-----------|------|--------|--------------|-------------|
| 2026-06-16 | — | — | — | Phase 1 audit completed; PRD, Tech Spec, and docs scaffold created | n/a (planning artifact) | — |
| 2026-06-16 | — | D-001..D-006 | — | All six open decisions accepted (memory=restore, model=Sonnet 4.6 configurable, transport=backoff+SSE, etc.) | see [DECISIONS.md](DECISIONS.md) | local |
| 2026-06-16 | A | OPS-3 | G5 | Add `.github/workflows/ci.yml`: conda env + `ruff check` (blocking) + `ruff format --check` (non-blocking, OPS-6) + backend `unittest discover` + Django `translator` tests | All steps verified locally; first GitHub run pending push | local |
| 2026-06-16 | A | MEM-4 | G2 | Fix `scratch.py:211` variable bug (`act_start_time`, not `curr_time`); guard `save()` `strftime` on `None` `curr_time`/`act_start_time` | `test_phase_a_fixes.ScratchSaveLoadTests` (save/load fresh persona) | local |
| 2026-06-16 | A | MEM-9 | G2 | `act_check_finished` uses `>=` datetime compare (not exact-second `==`) + `None` guards. **Behavior change:** actions now finish at-or-after end, not only on the exact end second | `ActCheckFinishedTests` (past/before/None/no-address) | local |
| 2026-06-16 | A | MEM-6 | G2 | Fix `get_str_seq_events/thoughts` f-string tuple bug (was emitting a wrapped-tuple repr) | `AssociativeMemoryStrTests` | local |
| 2026-06-16 | A | MEM-7 | G2 | Fix `retrieve_relevant_events/thoughts` to lowercase lookup keys (index is lowercase-keyed) | `AssociativeMemoryRetrievalTests` (capitalized query matches) | local |
| 2026-06-16 | A | MEM-10 | G2 | Narrow `add_thought` `except Exception: pass` → `except KeyError` + `logging.warning` on dangling filling refs | covered by existing add_thought paths; logic unchanged on happy path | local |
| 2026-06-16 | A | LLM-4 | G3 | Coerce + clamp `duration_minutes` (1..1440) in `parse_step_response`; tolerate non-list `event`; append parse error on bad value | `DurationClampTests` (string/null/negative/huge/valid) | local |
| 2026-06-16 | A | (OPS-8 partial) | G8 | New test file adds the `sys.path` bootstrap so it runs standalone *and* under discover (full OPS-8 packaging fix still open) | standalone 12 OK + discover 49 OK | local |

**Batch verification (2026-06-16):** backend `unittest discover` → **49 tests OK** (was 37; +12 new); Django `translator` → **29 OK**; `ruff check` → clean on all changed files. Tests run via `env/Scripts/python.exe` (Python 3.11 + claude-agent-sdk).

### Batch 2 — stack-dependent Quick Wins (CSRF / env-secrets / XSS / logging)

| Date | Phase | Finding(s) | Goal | Change | Verification | PR / commit |
|------|-------|-----------|------|--------|--------------|-------------|
| 2026-06-16 | A | OPS-1 | G5 | Re-enable `CsrfViewMiddleware`; drop all 6 `@csrf_exempt`; prime `csrftoken` via `@ensure_csrf_cookie` on `home`/`path_tester`/`replay`; send `X-CSRFToken` from the 3 mutating fetches + path_tester XHR | Live runserver: cookie primed (200), untokened POST→403, tokened POST→502; `CsrfProtectionTests` (4) | local |
| 2026-06-16 | A | OPS-2 | G5 | `SECRET_KEY`/`DEBUG`(default False)/`ALLOWED_HOSTS`/`BACKEND_URL` from env; rotated committed key out to a dev-only fallback; `start.sh` exports dev `DJANGO_DEBUG=True`; added `.env.example` | `manage.py check` clean at DEBUG=False; 33 Django tests | local |
| 2026-06-16 | A | FE-3 | G9 | `LOGGING` dict raises `django.server` to WARNING (drops 2xx/3xx access noise, keeps 4xx/5xx) | Live runserver: GET-200 access lines=0, 403/502 logged | local |
| 2026-06-16 | A | FE-6 | G5 | Escape/`textContent` all server+LLM-derived DOM sinks: home (chat bubble, action/target, game-time, saves-list attr+text), demo (emoji/action/target/chat), demo.html persona name | Adversarial XSS re-sweep = SHIP; `escapeHtml`/`escHtml` helpers | local |
| 2026-06-16 | A | OPS-1 (fix) | G5 | Adversarial review caught `replay` view missing `@ensure_csrf_cookie` (renders home.html w/ POST buttons) → cold `/replay` visit would 403; added decorator + regression test | `test_replay_page_primes_csrf_cookie` | local |

**Batch 2 verification (2026-06-16):** Django `translator` → **33 OK** (29 → +4 CSRF/replay); backend **49 OK** (unchanged); `manage.py check` clean (DEBUG=False default); `ruff check` clean on changed Python. Process: exhaustive discovery workflow (4 agents) → coordinated edits → live runserver round-trip verification → adversarial review workflow (4 agents, found 1 real bug, fixed). Frontend JS (`escapeHtml`, fetch headers) verified by inspection + the live CSRF round-trip; no automated JS test harness exists yet.

### Batch 3 — backend correctness + tooling Quick Wins

| Date | Phase | Finding(s) | Goal | Change | Verification | PR / commit |
|------|-------|-----------|------|--------|--------------|-------------|
| 2026-06-16 | A | ARCH-4 | G7 | `/save` route holds `_step_lock`; `runtime_status` snapshots `list(personas.items())` (lock-free so `/health` stays responsive) | review: no deadlock (Lock non-reentrant, save() lock-free, separate thread) | local |
| 2026-06-16 | A | ARCH-10 | G6 | Both ledgers: module `_WRITE_LOCK` + `flush()`+`os.fsync()` per append; `read_all` tolerates only a torn **final** line, logs mid-file corruption at error | review SHIP after trailing-only fix | local |
| 2026-06-16 | A | ARCH-12 | G1 | `_validate_env_tile` — client positions validated (missing key / non-numeric / out-of-bounds → fall back to current tile) | review: maze bounds correct | local |
| 2026-06-16 | A | ARCH-14 | — | `print_persona_action` uses `zlib.crc32` (stable across runs) instead of salted `hash()` | review OK | local |
| 2026-06-16 | A | ARCH-16 | G7 | `meta.json` rewritten only when `fork_sim_code` changed | review: guard correct | local |
| 2026-06-16 | A | LLM-9 | G3 | `MAX_CONTEXT_TOKENS` model-derived (Sonnet 4.6 → 1M, fixing wrong 200K); tunables env-overridable via safe `_env_int/_env_float`; fixed "Opus agency" docstring | review SHIP; Opus 4.8→1M + malformed-env fallback verified | local |
| 2026-06-16 | A | LLM-12 | — | `_fuzzy_match` prefers exact (case-insensitive) match before substring | review: strict improvement | local |
| 2026-06-16 | A | LLM-13 | G4 | `bypassPermissions` guarded by named `allowed_tools=[]` + assert | review OK | local |
| 2026-06-16 | A | OPS-5 | G5 | Pinned `claude-agent-sdk>=0.2.101,<0.3`, `ruff==0.15.17`, `django>=4.2,<4.3` (full conda-lock deferred — needs a conda host; dev venv is a pip-less uv venv) | review: pins consistent + installed | local |
| 2026-06-16 | A | OPS-6 | G5 | ruff `select += I, UP` (+ `target-version=py39`); bumped pre-commit ruff `v0.1.9→v0.15.17`; autofixed repo (B/S deferred — need per-site judgment) | `ruff check` clean | local |
| 2026-06-16 | A | OPS-9 | — | `.gitattributes` binary rules for image/zip/audio/font assets | review: syntax OK | local |
| 2026-06-16 | A | OPS-10 | — | `utils/__init__` re-exports `read_file_to_list` | review: no circular import | local |
| 2026-06-16 | A | (review fixes) | — | Fixed 4 adversarial-review findings: path_finder 3.9-union crash (`from __future__ import annotations` + ruff target-version), ledger trailing-only tolerance, Opus window 200K→1M, env-cast crash-on-typo | re-verified all suites + ruff | local |

**Batch 3 verification (2026-06-16):** backend **49 OK**, Django **33 OK**, `manage.py check` clean, `ruff check` clean (now with `I`+`UP`, target py39). Process: discovery (ruff blast-radius + dep versions) → wave-1/wave-2 edits with test gates → adversarial review workflow (3 agents, found 4 real bugs incl. a Python-3.9 startup crash, all fixed). **Deferred (logged):** ARCH-11 (encounter-method refactor — 2-file behavior risk, thin tests), ARCH-13 (dead guard in 340-line conv-sync), ARCH-15 (path-tester except/rmtree, dev-only), FE-7/FE-8 (frontend — need visual verification), OPS-6 `B`/`S` rules (~17 manual sites).

### Live-test session (2026-06-17) — full stack run

Ran the full stack end-to-end via the `env/` venv (no conda → `start.sh` unused; frontend from `environment/frontend_server/`, backend from `reverie/backend_server/` with `PYTHONUTF8=1`). The sim works: agents progress through a realistic day (sleep → wake ~6am → Isabella runs Hobbs Cafe, Maria showers, Klaus heads to the cafe). One fix + four findings:

| Date | Finding | Status | Notes |
|------|---------|--------|-------|
| 2026-06-17 | Move-timeout default 15s too tight | ✅ fixed | 3 concurrent persona LLM calls on a grown context routinely exceeded 15s → no-op "continue current action" fallback = playback stutter. Default raised **15s→45s** (`CLAUDEVILLE_PERSONA_MOVE_TIMEOUT`); `test_movement_stream` bound updated 15→60. Ties to ARCH-2/LLM-5 (Phase B: per-persona timeout excluding compaction). |
| 2026-06-17 | **NEW** — CLI header crashes on non-UTF-8 stdout | ⬜ open (LOW) | `cli_interface.print_header` emits Unicode/box-drawing; on Windows with piped/redirected stdout (cp1252) it raises `UnicodeEncodeError` and the backend never starts. Workaround: `PYTHONUTF8=1`. Fix: force UTF-8 stdout or ASCII-fallback the banner. |
| 2026-06-17 | **ARCH-7 confirmed** (frontend CWD) | ⬜ open | Django `home`/`replay`/`demo` views use relative `storage/...` paths → the frontend must run from `environment/frontend_server/` or it 500s. Live instance of the audited CWD-dependent-paths finding. |
| 2026-06-17 | **NEW** — 5 AM dead cold-start UX | ⬜ open (LOW) | Continuing a save at 05:00 means all agents sleep → static map + a stuck "backend busy" label looks frozen. UI should surface "💤 agents sleeping" / auto-skip the night. |
| 2026-06-17 | **FE-2 confirmed** (speed vs LLM-bound sim) | ⬜ open | High playback speed drains the small movement buffer faster than the LLM-bound backend can simulate → stalls then resumes. Reinforces the SSE/async-prebuffer direction (FE-2/ARCH-5, Phase C). |

---

### Roadmap reconciliation (2026-06-25)

After Phase A, a **6-phase believability/society roadmap** shipped (commits `f6650752`→`844c72ae`; see
[DEVLOG.md](DEVLOG.md)) plus periodic auto-save and an LLM-1 safety fix. This closed/advanced several audit
findings the burndown below still listed as open — recorded here so state isn't mis-read:

| Finding | New status | Evidence |
|---------|-----------|----------|
| MEM-1 (retrieval ignores relevance) | ✅ closed | Phase 1 `f6650752`: `cognitive_modules/retrieve.py::retrieve_focal` (keyword×recency×importance) feeds the `=== RELEVANT MEMORIES ===` step section. |
| MEM-2 (poignancy hardcoded; reflection inert) | ✅ closed | Phase 1: LLM-judged importance → `ConceptNode.poignancy` (perceive.py); `persona._maybe_reflect` fires at the trigger. |
| MEM-3 (silent pathfinding failure) | ✅ closed | Phase 5 `087a843e`: `max(150, w*h)` bound + non-silent truncation sentinel/log. |
| ARCH-2 (move timeout abandons coroutines) | 🟦 mitigated | Phase 5: per-persona `_move_persona_with_timeout` cancels+awaits + full scratch rollback. Root determinism (ARCH-1) still open. |
| ARCH-5 (`/simulate` synchronous) | ✅ closed | Phase 5: autosim buffer + backpressure; `/simulate` is a no-op echo when autosim is on. |
| LLM-1 (agent-to-agent prompt injection) | ✅ closed | 2026-06-25: `_sanitize_external` + UNTRUSTED framing of conversation/recall text (`test_prompt_injection.py`). |
| OPS-4 (core untested) | 🟦 partial | Roadmap added ~110 backend + 22 eval/emergence tests (cognition/relationships/goals/robustness/society/auto-save); inherited maze/path_finder/perceive still thin. |

Test baseline now: **173 backend + 13 eval + 9 emergence + 34 Django**, green; ruff clean.

---

## Findings burndown

Mirror of the audit register (§2 of [PHASE-1-AUDIT.md](PHASE-1-AUDIT.md)). Status: ⬜ open · 🟦 in progress · ✅ closed · ⏸️ deferred (link a decision). Update as work lands.
**Note (2026-06-25):** the row statuses below predate the roadmap reconciliation table above — trust that table where they differ; a full row-by-row refresh is pending.

### CRITICAL (0/6 closed)
| ID | Title | Status | Notes |
|----|-------|--------|-------|
| ARCH-1 | Parallel personas mutate shared world state | ⬜ | Still open — determinism (D-006 snapshot→decide→apply) not built |
| ARCH-2 | Move timeout abandons coroutines | 🟦 | Mitigated (Phase 5 per-persona timeout + rollback); root tied to ARCH-1 |
| LLM-1 | Agent-to-agent prompt injection | ✅ | Closed 2026-06-25 — `_sanitize_external` + UNTRUSTED framing + tests |
| MEM-1 | Retrieval ignores relevance (dead keyword index) | ✅ | Closed (Phase 1 `f6650752`) — `retrieve_focal` wired into step prompt |
| MEM-2 | Poignancy/importance hardcoded; reflection inert | ✅ | Closed (Phase 1) — LLM importance → poignancy; `_maybe_reflect` fires |
| OPS-1 | CSRF disabled + `@csrf_exempt` everywhere | ✅ | Closed 2026-06-16 — middleware on, exemptions dropped, token wired, live-verified |

### HIGH (0/19 closed)
| ID | Title | Status | Notes |
|----|-------|--------|-------|
| ARCH-3 | `ReverieServer` god object | ⬜ | Phase C |
| ARCH-4 | Read/save routes bypass step lock | ✅ | Closed 2026-06-16 — /save locked, status snapshot |
| ARCH-5 | `/simulate` synchronous in request thread | ⬜ | Phase B |
| ARCH-6 | `save()` non-atomic + CWD-dependent | ⬜ | Phase B |
| ARCH-7 | Two divergent storage path systems | ⬜ | Phase B |
| LLM-2 | Malformed/API errors → silent idle, no telemetry | ⬜ | Phase B (G3) |
| LLM-3 | No transport retry/backoff | ⬜ | Phase B (G3) |
| LLM-4 | `duration_minutes` unvalidated | ✅ | Closed 2026-06-16 — clamp 1..1440 + tests |
| LLM-5 | Sleep compaction can't fire; failed summary loses context | ⬜ | Phase B |
| LLM-6 | Token accounting wrong + wrong context constant | ⬜ | Phase B; blocked on D-003 |
| MEM-3 | Pathfinding O(W·H)/wave; silent long-path failure | ⬜ | Phase B |
| MEM-4 | `scratch.save()` crashes on None; line-211 bug | ✅ | Closed 2026-06-16 — guards + fix + tests |
| MEM-5 | Associative memory unbounded; O(n) save/retrieve | ⬜ | Phase B |
| OPS-2 | Hardcoded SECRET_KEY/DEBUG/ALLOWED_HOSTS | ✅ | Closed 2026-06-16 — env-driven, key rotated, .env.example + start.sh |
| FE-1 | Sprite bug: silent 404 → shared atlas | ⬜ | Phase B |
| FE-2 | 100% polling, no SSE; double-hop health | ⬜ | Phase C (backoff in A) |
| OPS-3 | No CI / quality gates | ✅ | Closed 2026-06-16 — ci.yml added; first GH run pending push |
| OPS-4 | ~5,900 LOC core untested | ⬜ | Phase B (G8) |
| OPS-5 | Zero dependency pinning | ✅ | Closed 2026-06-16 — sdk/ruff/django pinned (full conda-lock = follow-up) |

### MEDIUM (0/23 closed)
| ID | Title | Status | Notes |
|----|-------|--------|-------|
| ARCH-8 | `/movements` destructive; multi-client unsafe | ⬜ | Phase B |
| ARCH-9 | `town_center.snapshot()` re-reads full ledger | ⬜ | Phase B |
| ARCH-10 | Ledger appends not crash/concurrency-safe | ✅ | Closed 2026-06-16 — lock + fsync + torn-line tolerance |
| ARCH-11 | Convo/encounter uses private persona attrs | ⬜ | Phase A |
| ARCH-12 | Client positions unvalidated | ✅ | Closed 2026-06-16 — _validate_env_tile |
| LLM-7 | Prompt bloat; static rulebook re-sent | ⬜ | Phase B |
| LLM-8 | No cost controls (max_tokens/spend cap) | ⬜ | Phase B |
| LLM-9 | Magic numbers/model params hardcoded | ✅ | Closed 2026-06-16 — model-derived window + env tunables |
| LLM-10 | Module-global mutable state | ⬜ | Phase C |
| LLM-11 | `_send_prompt` re-entrancy on compaction | ⬜ | Phase B/C |
| MEM-6 | `get_str_seq_*` f-string tuple bug | ✅ | Closed 2026-06-16 — readable interpolation + test |
| MEM-7 | `retrieve_relevant_events` case bug | ✅ | Closed 2026-06-16 — lowercase keys + test |
| MEM-8 | 4× BFS + PathFinder rebuild per move; nondeterministic sample | ⬜ | Phase B |
| MEM-9 | `act_check_finished` string-equality; divergent predicates | ✅ | Closed 2026-06-16 — `>=` compare + guards + tests |
| MEM-10 | `add_thought` bare except masks dangling refs | ✅ | Closed 2026-06-16 — narrowed to KeyError + log |
| FE-3 | Django access log → stderr; no LOGGING | ✅ | Closed 2026-06-16 — LOGGING silences django.server 2xx, live-verified |
| FE-4 | 1561-line inline JS; tags block extraction | ⬜ | Phase C |
| FE-5 | Inconsistent view error handling; `str(e)` leak | ⬜ | Phase B |
| FE-6 | Unescaped persona text → DOM (XSS) | ✅ | Closed 2026-06-16 — all sinks escaped/textContent (home+demo), adversarially re-swept |
| OPS-6 | Ruff config minimal; pre-commit version skew | ✅ | Closed 2026-06-16 — +I/UP/target-version, version reconciled (B/S follow-up) |
| OPS-7 | Asset ZIP bloat; 26 pending deletions | ⬜ | Phase A (reconcile) / B (full) |
| OPS-8 | Fragile dual test-import convention | ⬜ | Phase B |

### LOW (0/15 closed)
| ID | Title | Status |
|----|-------|--------|
| ARCH-13 | `_synchronize_conversations` dead guard | ⬜ |
| ARCH-14 | `print_persona_action` salted `hash()` color | ✅ |
| ARCH-15 | Path-tester `except: pass`; rmtree before loop | ⬜ |
| ARCH-16 | `meta.json` rewritten 3× in `__init__` | ✅ |
| ARCH-17 | Batch timeout discards completed work | ⬜ |
| LLM-12 | Naive fuzzy match mis-resolves locations | ✅ |
| LLM-13 | `bypassPermissions` + empty allowed_tools footgun | ✅ |
| MEM-11 | `_is_wall` infers opacity from empty arena | ⬜ |
| MEM-12 | `merge_chat_lines` unbounded / O(n²) | ⬜ |
| MEM-13 | Retrieval/perception magic numbers scattered | ⬜ |
| FE-7 | Dead/duplicated template data; `persona_name_str` unused | ⬜ |
| FE-8 | CSS duplication, no variables | ⬜ |
| FE-9 | `api_simulate` 240s synchronous proxy | ⬜ |
| OPS-9 | `.gitattributes` minimal; no binary/LFS | ✅ |
| OPS-10 | `utils/__init__.py` dangling re-export | ✅ |

**Progress:** 23 / 63 findings closed (1 CRITICAL · 6 HIGH · 10 MEDIUM · 6 LOW). Remaining: 5 CRITICAL · 13 HIGH · 13 MEDIUM · 9 LOW.

_Phase A nearly complete. Still open (deferred with rationale): ARCH-11 (encounter-method refactor), ARCH-13/ARCH-15 (LOW, complex/dev-only), FE-7/FE-8 (frontend — need visual verification), OPS-6 `B`/`S` ruff rules, OPS-7 (reconcile the 26 pending PNG deletions). Then Phase B (structural) — gated on D-001 (decided: Restore memory)._
