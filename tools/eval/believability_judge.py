"""CLI: LLM-judge each persona's day-trace on a SOTOPIA-EVAL-style rubric.

For every persona we assemble a compact day-trace (movement descriptions, chat
lines, submitted town requests, scenario role/mission) and ask a Claude judge to
score five dimensions 1-10 with a one-line justification each:
    goal_completion, believability, relationship, social_rules, role_alignment

Graceful by design: if the Claude Agent SDK or the LLM is unavailable, the judge
is skipped with a clear note and the structural metrics report is still emitted.
The judge result is merged into out/<sim_code>.metrics.json under the
"believability_judge" key and re-rendered into the Markdown report.

Usage:
    python -m tools.eval.believability_judge <sim_code>
    python tools/eval/believability_judge.py <sim_code> --max-personas 4
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.eval import metrics as metrics_mod
    from tools.eval import report as report_mod
    from tools.eval.run_loader import RunData, load_run
else:
    from . import metrics as metrics_mod
    from . import report as report_mod
    from .run_loader import RunData, load_run

_DIMENSIONS = [
    "goal_completion",
    "believability",
    "relationship",
    "social_rules",
    "role_alignment",
]

# Bound the trace so the judge prompt stays small and cheap.
_MAX_DESC_LINES = 24
_MAX_CHAT_LINES = 24
_MAX_REQUESTS = 8

DEFAULT_MODEL = os.environ.get("CLAUDEVILLE_CLAUDE_MODEL", "claude-sonnet-4-6")


def build_day_traces(run: RunData) -> dict[str, dict[str, Any]]:
    """Assemble a per-persona day-trace from on-disk movement + requests."""
    roles = run.scenario_roles()
    traces: dict[str, dict[str, Any]] = {}
    for name in run.persona_names:
        traces[name] = {
            "role": roles.get(name, {}).get("role", ""),
            "mission": roles.get(name, {}).get("mission", ""),
            "descriptions": [],
            "chat_lines": [],
            "town_requests": [],
        }

    last_desc: dict[str, str] = {}
    for _step, packet in sorted(run.movement.items()):
        persona_block = packet.get("persona", {}) if isinstance(packet, dict) else {}
        for name, pdata in persona_block.items():
            tr = traces.setdefault(
                name,
                {
                    "role": "",
                    "mission": "",
                    "descriptions": [],
                    "chat_lines": [],
                    "town_requests": [],
                },
            )
            desc = pdata.get("description")
            if desc and desc != last_desc.get(name):
                tr["descriptions"].append(desc)
                last_desc[name] = desc
            chat = pdata.get("chat")
            if isinstance(chat, list):
                for line in chat:
                    if isinstance(line, (list, tuple)) and len(line) >= 2:
                        tr["chat_lines"].append(f"{line[0]}: {line[1]}")

    for r in run.requests:
        actor = r.get("actor")
        if actor and r.get("title") and actor in traces:
            traces[actor]["town_requests"].append(
                f"[{r.get('type', '?')}] {r.get('title', '')}"
            )

    # Trim to bounds.
    for tr in traces.values():
        tr["descriptions"] = tr["descriptions"][:_MAX_DESC_LINES]
        tr["chat_lines"] = tr["chat_lines"][:_MAX_CHAT_LINES]
        tr["town_requests"] = tr["town_requests"][:_MAX_REQUESTS]
    return traces


def build_judge_prompt(
    persona: str, trace: dict[str, Any], objective: str
) -> str:
    """Build a SOTOPIA-EVAL-style judging prompt for one persona's day."""
    descs = "\n".join(f"- {d}" for d in trace["descriptions"]) or "(none)"
    chats = "\n".join(f"- {c}" for c in trace["chat_lines"]) or "(none)"
    reqs = "\n".join(f"- {r}" for r in trace["town_requests"]) or "(none)"
    return f"""You are an expert evaluator of social-simulation agents, using a \
SOTOPIA-EVAL-style rubric. Score the agent's day below on five dimensions, each \
an integer 1-10 (1 = very poor, 10 = excellent), with a single concise \
justification sentence per dimension.

AGENT: {persona}
ASSIGNED ROLE: {trace['role']}
MISSION: {trace['mission']}
TEAM OBJECTIVE: {objective}

OBSERVED ACTIONS (descriptions over the run):
{descs}

DIALOGUE (what the agent said):
{chats}

TOWN-CENTER REQUESTS SUBMITTED:
{reqs}

DIMENSIONS:
- goal_completion: did the agent make progress toward its mission and the team objective?
- believability: were the actions natural, consistent, and human-like (not robotic or hallucinated)?
- relationship: did the agent build/maintain useful working relationships with teammates?
- social_rules: did the agent respect norms and constraints (e.g. seek approval, avoid forbidden actions)?
- role_alignment: did the agent's behavior match its assigned role rather than drifting into others' roles?

Respond with ONLY a JSON object in this exact shape:
{{
  "goal_completion": {{"score": 7, "justification": "..."}},
  "believability": {{"score": 7, "justification": "..."}},
  "relationship": {{"score": 7, "justification": "..."}},
  "social_rules": {{"score": 7, "justification": "..."}},
  "role_alignment": {{"score": 7, "justification": "..."}}
}}"""


def parse_judge_response(text: str) -> dict[str, Any]:
    """Parse the judge JSON, clamping scores to 1-10."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {}
    out: dict[str, Any] = {}
    for dim in _DIMENSIONS:
        entry = data.get(dim, {})
        if not isinstance(entry, dict):
            continue
        raw = entry.get("score", 0)
        try:
            score = max(1, min(10, int(raw)))
        except (TypeError, ValueError):
            score = None
        out[dim] = {
            "score": score,
            "justification": str(entry.get("justification", "")).strip(),
        }
    return out


async def _judge_one(client: Any, result_message_cls: Any, prompt: str) -> str:
    """Send one prompt through a connected SDK client and return the result."""
    await client.query(prompt)
    result_text = ""
    async for message in client.receive_response():
        if isinstance(message, result_message_cls):
            result_text = message.result or ""
    return result_text


async def _run_judge_async(
    prompts: dict[str, str], model: str, timeout: float
) -> dict[str, dict[str, Any]]:
    """Connect a single SDK client and score every persona sequentially."""
    from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
    from claude_agent_sdk.types import ResultMessage

    options = ClaudeAgentOptions(
        allowed_tools=[],
        permission_mode="bypassPermissions",
        model=model,
    )
    scores: dict[str, dict[str, Any]] = {}
    client = ClaudeSDKClient(options)
    await asyncio.wait_for(client.connect(), timeout=30.0)
    try:
        for persona, prompt in prompts.items():
            try:
                text = await asyncio.wait_for(
                    _judge_one(client, ResultMessage, prompt), timeout=timeout
                )
            except asyncio.TimeoutError:
                scores[persona] = {}
                continue
            scores[persona] = parse_judge_response(text)
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    return scores


def run_judge(
    run: RunData,
    max_personas: int | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Score personas with the LLM judge, returning a graceful status block."""
    try:
        import claude_agent_sdk  # noqa: F401
    except Exception as exc:  # SDK not installed / import error.
        return {
            "status": "skipped",
            "reason": f"Claude Agent SDK unavailable ({exc})",
        }

    traces = build_day_traces(run)
    objective = run.meta.get("scenario_objective") or run.scenario.get(
        "objective", ""
    )
    names = [n for n in run.persona_names if n in traces] or list(traces)
    if max_personas is not None:
        names = names[:max_personas]
    prompts = {
        n: build_judge_prompt(n, traces[n], objective) for n in names
    }
    if not prompts:
        return {"status": "skipped", "reason": "no persona traces found"}

    try:
        scores = asyncio.run(_run_judge_async(prompts, model, timeout))
    except Exception as exc:  # Connection / runtime failure -> graceful skip.
        return {
            "status": "skipped",
            "reason": f"judge call failed ({type(exc).__name__}: {exc})",
        }

    scored = {n: s for n, s in scores.items() if s}
    if not scored:
        return {
            "status": "skipped",
            "reason": "judge returned no parseable scores",
        }
    return {"status": "ok", "model": model, "scores": scored}


def judge(
    sim_code: str,
    max_personas: int | None = None,
    model: str = DEFAULT_MODEL,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Compute metrics (reusing cached file if present), run judge, re-render."""
    run = load_run(sim_code)
    payload = report_mod.load_metrics_json(run.sim_code)
    if payload is None:
        payload = metrics_mod.compute_metrics(run)

    payload["believability_judge"] = run_judge(run, max_personas, model, timeout)
    json_path = report_mod.write_metrics_json(run.sim_code, payload)
    md_path = report_mod.write_report_md(run.sim_code, payload)
    payload["_outputs"] = {"metrics_json": str(json_path), "report_md": str(md_path)}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM believability judge.")
    parser.add_argument("sim_code", help="Run sim_code, path, or 'latest[:prefix]'.")
    parser.add_argument(
        "--max-personas", type=int, default=None, help="Cap personas scored."
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Judge model id.")
    parser.add_argument(
        "--timeout", type=float, default=120.0, help="Per-persona timeout (s)."
    )
    args = parser.parse_args(argv)
    try:
        payload = judge(args.sim_code, args.max_personas, args.model, args.timeout)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    jb = payload.get("believability_judge", {})
    if jb.get("status") == "ok":
        print(f"Judge OK ({jb.get('model')}): scored {len(jb.get('scores', {}))} personas")
        for persona, sc in jb.get("scores", {}).items():
            gc = sc.get("goal_completion", {}).get("score")
            bel = sc.get("believability", {}).get("score")
            print(f"  {persona}: goal={gc} believability={bel}")
    else:
        print(f"Judge skipped: {jb.get('reason')}")
    outputs = payload.get("_outputs", {})
    print(f"  wrote: {outputs.get('metrics_json')}")
    print(f"  wrote: {outputs.get('report_md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
