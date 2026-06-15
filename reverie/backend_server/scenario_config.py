"""Scenario configuration loading for Claudeville simulation variants."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SCENARIO_DIR = Path(__file__).resolve().parent / "scenarios"


def load_scenario(scenario_id: str, scenario_dir: str | Path | None = None) -> dict[str, Any]:
    """Load and validate a scenario JSON file by id."""
    base_dir = Path(scenario_dir) if scenario_dir else SCENARIO_DIR
    path = base_dir / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario '{scenario_id}' was not found at {path}.")

    with path.open("r", encoding="utf-8") as infile:
        scenario = json.load(infile)

    validate_scenario(scenario)
    return deepcopy(scenario)


def validate_scenario(scenario: dict[str, Any]) -> None:
    """Raise ValueError when a scenario is missing required simulation metadata."""
    required = [
        "id",
        "name",
        "objective",
        "starting_resources",
        "real_world_policy",
        "reward_model",
        "agents",
    ]
    missing = [key for key in required if key not in scenario]
    if missing:
        raise ValueError(f"Scenario is missing required fields: {', '.join(missing)}")

    agents = scenario["agents"]
    if not isinstance(agents, list) or not agents:
        raise ValueError("Scenario must define at least one agent.")
    for agent in agents:
        for key in ("name", "role", "mission"):
            if not agent.get(key):
                raise ValueError(f"Scenario agent is missing '{key}'.")

    resources = scenario["starting_resources"]
    if not resources.get("approval_required_for_external_actions", False):
        raise ValueError("Scenario must require approval for external actions.")

    policy = scenario["real_world_policy"]
    if "automatic_capabilities" not in policy or "blocked_without_approval" not in policy:
        raise ValueError("Scenario policy must declare automatic and blocked tools.")
