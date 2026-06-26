# Claudeville — Improvement Project Docs

Source-of-truth documentation for the Claudeville improvement pass (SPARC: Specification phase). Read in this order.

| Doc | Purpose |
|-----|---------|
| [PHASE-1-AUDIT.md](PHASE-1-AUDIT.md) | **Source of truth.** The grounded research/analysis audit — 63 evidence-backed findings (6 CRITICAL · 19 HIGH · 23 MEDIUM · 15 LOW) with `file:line`, impact, fix, and effort. |
| [PRD.md](PRD.md) | Product requirements — problem, ranked goals (G1–G9), non-goals, measurable success metrics, 3-phase delivery plan. |
| [TECH-SPEC.md](TECH-SPEC.md) | As-is & to-be architecture (Mermaid), migration path, breaking-changes inventory, risk register, verification strategy. |
| [DECISIONS.md](DECISIONS.md) | ADR log — open decisions (D-001…D-006) that must be resolved before dependent work begins. |
| [IMPROVEMENT-LOG.md](IMPROVEMENT-LOG.md) | Execution tracking — terse, per-merge change log + findings burndown. |
| [DEVLOG.md](DEVLOG.md) | **Living diary** — the human narrative of changes, discoveries, and dead ends (newest first); companion to the IMPROVEMENT-LOG. |
| [PAPER.md](PAPER.md) | **Living academic paper** — publication-grade write-up of the system: architecture, methodology, verification, honest evaluation (incl. null results), related work, references. Evolves until the app is live. |
| [money_agent_foundation.md](money_agent_foundation.md) | Pre-existing design note for the town-center / economy layer (predates this pass). |

## How these connect

```
PHASE-1-AUDIT (findings)
      │  ranks into
      ▼
   PRD (goals G1–G9, phases A/B/C, metrics)
      │  designed by              decided by
      ▼                               ▼
 TECH-SPEC (as-is→to-be) ◄──────► DECISIONS (D-001…D-006)
      │  executed & tracked in
      ▼
 IMPROVEMENT-LOG (burndown)
```

## Status (2026-06-16)

- ✅ Phase 1 audit complete; spec docs created.
- ⏳ **Next:** resolve the open decisions (D-001 memory direction, D-003 model/context, D-004 transport) per the PRD approval checklist, then authorize **Phase A — Quick Wins** (start with CI, OPS-3).

> Subject of this improvement pass: the **Claudeville / reverie simulation** in this repository. The `ruflo`/`claude-flow` tooling registered at the workspace root is the dev harness, not the audit target.
