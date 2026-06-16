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

---

## Findings burndown

Mirror of the audit register (§2 of [PHASE-1-AUDIT.md](PHASE-1-AUDIT.md)). Status: ⬜ open · 🟦 in progress · ✅ closed · ⏸️ deferred (link a decision). Update as work lands.

### CRITICAL (0/6 closed)
| ID | Title | Status | Notes |
|----|-------|--------|-------|
| ARCH-1 | Parallel personas mutate shared world state | ⬜ | Phase C; ARCH-2 is interim mitigation |
| ARCH-2 | Move timeout abandons coroutines | ⬜ | Phase B |
| LLM-1 | Agent-to-agent prompt injection | ⬜ | Phase B (G4) |
| MEM-1 | Retrieval ignores relevance (dead keyword index) | ⬜ | Phase B; blocked on D-001 |
| MEM-2 | Poignancy/importance hardcoded; reflection inert | ⬜ | Phase B; blocked on D-001 |
| OPS-1 | CSRF disabled + `@csrf_exempt` everywhere | ✅ | Closed 2026-06-16 — middleware on, exemptions dropped, token wired, live-verified |

### HIGH (0/19 closed)
| ID | Title | Status | Notes |
|----|-------|--------|-------|
| ARCH-3 | `ReverieServer` god object | ⬜ | Phase C |
| ARCH-4 | Read/save routes bypass step lock | ⬜ | Phase A |
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
| OPS-5 | Zero dependency pinning | ⬜ | Phase A |

### MEDIUM (0/23 closed)
| ID | Title | Status | Notes |
|----|-------|--------|-------|
| ARCH-8 | `/movements` destructive; multi-client unsafe | ⬜ | Phase B |
| ARCH-9 | `town_center.snapshot()` re-reads full ledger | ⬜ | Phase B |
| ARCH-10 | Ledger appends not crash/concurrency-safe | ⬜ | Phase A |
| ARCH-11 | Convo/encounter uses private persona attrs | ⬜ | Phase A |
| ARCH-12 | Client positions unvalidated | ⬜ | Phase A |
| LLM-7 | Prompt bloat; static rulebook re-sent | ⬜ | Phase B |
| LLM-8 | No cost controls (max_tokens/spend cap) | ⬜ | Phase B |
| LLM-9 | Magic numbers/model params hardcoded | ⬜ | Phase A |
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
| OPS-6 | Ruff config minimal; pre-commit version skew | ⬜ | Phase A |
| OPS-7 | Asset ZIP bloat; 26 pending deletions | ⬜ | Phase A (reconcile) / B (full) |
| OPS-8 | Fragile dual test-import convention | ⬜ | Phase B |

### LOW (0/15 closed)
| ID | Title | Status |
|----|-------|--------|
| ARCH-13 | `_synchronize_conversations` dead guard | ⬜ |
| ARCH-14 | `print_persona_action` salted `hash()` color | ⬜ |
| ARCH-15 | Path-tester `except: pass`; rmtree before loop | ⬜ |
| ARCH-16 | `meta.json` rewritten 3× in `__init__` | ⬜ |
| ARCH-17 | Batch timeout discards completed work | ⬜ |
| LLM-12 | Naive fuzzy match mis-resolves locations | ⬜ |
| LLM-13 | `bypassPermissions` + empty allowed_tools footgun | ⬜ |
| MEM-11 | `_is_wall` infers opacity from empty arena | ⬜ |
| MEM-12 | `merge_chat_lines` unbounded / O(n²) | ⬜ |
| MEM-13 | Retrieval/perception magic numbers scattered | ⬜ |
| FE-7 | Dead/duplicated template data; `persona_name_str` unused | ⬜ |
| FE-8 | CSS duplication, no variables | ⬜ |
| FE-9 | `api_simulate` 240s synchronous proxy | ⬜ |
| OPS-9 | `.gitattributes` minimal; no binary/LFS | ⬜ |
| OPS-10 | `utils/__init__.py` dangling re-export | ⬜ |

**Progress:** 11 / 63 findings closed (1 CRITICAL · 4 HIGH · 6 MEDIUM). Remaining: 5 CRITICAL · 15 HIGH · 17 MEDIUM · 15 LOW.

_Phase A continues: remaining Quick Wins include OPS-5 (pin deps), OPS-6 (ruff rules + version), ARCH-4 (lock read/save routes), ARCH-10 (ledger fsync), ARCH-11 (private-attr methods), ARCH-12 (validate client positions), ARCH-16 (meta.json single write), LLM-9 (config/model constants), FE-2 backoff slice, OPS-7 (reconcile pending deletions), and the LOW batch. Then Phase B (structural) — gated on D-001 memory direction (already decided: Restore)._
