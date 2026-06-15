# Money-Agent Foundation

This repository is being adapted into a staged multi-agent startup simulation. The first implementation slice focuses on runtime reliability and safe extension points, not autonomous real-world execution.

## Current Foundation

- `tools/claudeville.ps1` starts, stops, restarts, and checks local Windows runtime processes.
- Backend `/health` reports simulation time, step, movement queue depth, busy state, and persona activity.
- Frontend `/api/health/` proxies backend health while keeping Django usable if Flask is down.
- The simulator UI now separates browser playback state from backend simulation state.
- `runtime_storage.py` centralizes run creation, metadata, and current-run pointers.
- `event_ledger.py` records append-only simulation events.
- `economy.py` defines safe tool capabilities, approval requests, and reward ledgers.
- `scenario_config.py` validates scenario files before they are used by the runtime.
- `scenario_runtime.py` writes active scenario metadata into each run and builds compact prompt briefs.
- `town_center.py` stores run-local requests, approval transitions, rewards, and scores.
- `scenarios/startup_team_v1.json` defines the first 10-agent startup scenario.
- Backend `/town-center` and frontend `/api/town-center/` expose the scenario, tool registry, request queue, reward history, and team score.
- The simulator UI includes a compact Town Center panel with objective, points, revenue, requests, and pending approvals.
- Requests that require approval now appear in an explicit `approval_queue`; the UI can approve, reject, complete, or fail the current pending request.
- Persona initial and step prompts include the active scenario objective, safety policy, tool boundaries, and role-specific mission when the persona appears in the scenario roster.
- Persona step responses may now include a `town_request`; the runtime records valid proposals in the Town Center ledger and audit event stream without executing external actions.
- Approved and completed requests now create auditable reward entries once per lifecycle state, so points can be traced back to request IDs and reviewer notes.
- Request and reward actors are canonicalized against the active scenario roster, preventing fragmented identities such as `felix_reed` versus `Felix Reed`.
- Reward entries include `outcome_valence` on a -10 to +10 scale. Approved/completed requests create positive signals; rejected/failed requests create negative signals and point penalties.
- `storage/base/startup_team_v1/` provides a runnable 10-agent startup-team base that matches the scenario roster, including persona scratch context and character sprites.

## Fork-Inspired Lessons

- `fvdveen/generative_agents` adds valence-aware memory scoring. Claudeville now applies the same principle to business outcomes by recording positive and negative reward valence.
- `Crows12138/generative_agents_local_llm_with_godot` emphasizes canonical NPC names, direct state sync, local-model support, and lightweight cached memory. Claudeville has adopted canonical actor names first; local-model and streaming bridges remain future candidates.

## Safety Boundary

V1 uses a hybrid sandbox. Agents may research, analyze, and draft internally. They must request human approval before any external action, including sending messages, posting content, spending money, modifying accounts, buying services, scraping at scale, or contacting people.

Unknown tools default to approval-required. The system should never silently grant new real-world capabilities.

## Next Implementation Slices

Run the startup team locally with `powershell -NoProfile -ExecutionPolicy Bypass -File tools\claudeville.ps1 restart -Fork startup_team_v1`.

1. Add configurable scoring rules that gradually shift from milestone points toward actual revenue.
2. Add optional local/OpenAI-compatible model adapters and streaming status surfaces.
3. Make the launcher install/setup path fully one-command.
