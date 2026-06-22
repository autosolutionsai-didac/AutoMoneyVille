"""Claudeville offline evaluation harness (Phase 2).

Additive, read-only analysis over a finished run's on-disk data plus an optional
LLM judge. Nothing here changes backend runtime behavior.

Modules:
- run_loader: resolve a run directory and read its JSON/JSONL artifacts.
- metrics:    pure (no-LLM) structural metrics over the loaded run.
- report:     render metrics into JSON + Markdown.
- analyze_run:        CLI -> structural metrics + report (+ --emergence).
- believability_judge: CLI -> SOTOPIA-style LLM scores merged into the report.
- replay_diff:        CLI -> determinism/regression diff of two runs.
- emergence:          CLI -> over-time emergence report (specialization,
  cooperation, network growth, conventions). Phase 6d.
"""
