"""Runtime helpers for binding scenario configuration to active simulations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def bind_scenario_to_run(run_storage, sim_code: str, scenario: dict[str, Any]) -> None:
    """Persist scenario metadata and a full scenario snapshot for a run."""
    meta = run_storage.read_run_meta(sim_code)
    meta["scenario_id"] = scenario["id"]
    meta["scenario_name"] = scenario["name"]
    meta["scenario_objective"] = scenario["objective"]
    meta["scenario_team_structure"] = scenario.get("team_structure")
    run_storage.write_run_meta(sim_code, meta)

    scenario_path = Path(run_storage.run_dir(sim_code)) / "reverie" / "scenario.json"
    scenario_path.parent.mkdir(parents=True, exist_ok=True)
    with scenario_path.open("w", encoding="utf-8") as outfile:
        json.dump(scenario, outfile, indent=2)


def build_scenario_brief(
    scenario: dict[str, Any], persona_name: str | None = None
) -> str:
    """Build a compact prompt-safe scenario brief."""
    policy = scenario.get("real_world_policy", {})
    automatic = ", ".join(policy.get("automatic_capabilities", [])) or "none"
    blocked = ", ".join(policy.get("blocked_without_approval", [])) or "none"
    forbidden = ", ".join(policy.get("forbidden_behaviors", [])) or "none"
    visible_routine = scenario.get("visible_morning_routine", [])
    visible_lines = "\n".join(f"- {item}" for item in visible_routine)
    agent_lines = [
        f"- {agent['name']}: {agent['role']} - {agent['mission']}"
        for agent in scenario.get("agents", [])
    ]

    role_section = ""
    if persona_name:
        agent = _find_agent(scenario, persona_name)
        if agent:
            role_section = f"""
Your startup role: {agent["role"]}.
Your mission: {agent["mission"]}.
"""

    return f"""=== STARTUP SCENARIO ===
Scenario: {scenario["name"]}
Objective: {scenario["objective"]}
Team mode: {scenario.get("team_structure", "cooperative")}
{role_section}
Automatic internal tools: {automatic}
Human approval required before: {blocked}
Forbidden behavior: {forbidden}
Visible movement routine:
{visible_lines or "- none"}

Team roles:
{chr(10).join(agent_lines)}

Use the Town Center for requests, approvals, resources, and tool access.
Never send, post, spend, scrape at scale, purchase, contact people, or change accounts without human approval.
"""


def attach_scenario_to_personas(
    personas: dict[str, Any], scenario: dict[str, Any]
) -> None:
    """Attach scenario prompt context to personas that participate in the scenario."""
    for name, persona in personas.items():
        persona.scenario_context = build_scenario_brief(scenario, name)


def _find_agent(
    scenario: dict[str, Any], persona_name: str
) -> dict[str, Any] | None:
    for agent in scenario.get("agents", []):
        if agent.get("name") == persona_name:
            return agent
    return None
