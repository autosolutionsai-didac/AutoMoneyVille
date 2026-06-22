"""Read-only loaders for a finished Claudeville run on disk.

A run lives under:
    environment/frontend_server/storage/runs/<sim_code>/

This module knows the on-disk layout (confirmed against real runs) and exposes a
single ``RunData`` object so the metric/report/judge code never re-derives paths
or re-parses files. Everything here is defensive: a missing or malformed file
yields an empty default rather than an exception, because finished runs vary in
completeness (e.g. an early-aborted run may have no town_center/).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Repo-root-relative location of the runs directory.
_RUNS_SUBPATH = ("environment", "frontend_server", "storage", "runs")


def repo_root() -> Path:
    """Return the repository root (two levels up from tools/eval/)."""
    return Path(__file__).resolve().parents[2]


def runs_dir() -> Path:
    """Return the absolute runs/ directory."""
    return repo_root().joinpath(*_RUNS_SUBPATH)


def resolve_run_dir(sim_code: str) -> Path:
    """Resolve a sim_code (or absolute path) to its run directory.

    Accepts an exact sim_code, an absolute/relative path to a run dir, or the
    special value "latest"/"latest:<prefix>" to pick the newest matching run.
    """
    if not sim_code:
        raise ValueError("sim_code must be a non-empty string")

    candidate = Path(sim_code)
    if candidate.is_dir() and (candidate / "reverie").exists():
        return candidate

    base = runs_dir()
    if sim_code == "latest" or sim_code.startswith("latest:"):
        prefix = sim_code.split(":", 1)[1] if ":" in sim_code else ""
        return _latest_run(base, prefix)

    direct = base / sim_code
    if direct.is_dir():
        return direct
    raise FileNotFoundError(f"Run directory not found for sim_code: {sim_code!r}")


def _latest_run(base: Path, prefix: str) -> Path:
    """Return the newest run dir under base whose name starts with prefix."""
    if not base.is_dir():
        raise FileNotFoundError(f"runs directory does not exist: {base}")
    matches = sorted(
        d for d in base.iterdir() if d.is_dir() and d.name.startswith(prefix)
    )
    if not matches:
        raise FileNotFoundError(f"No run dir under {base} matching prefix {prefix!r}")
    return matches[-1]


def _read_json(path: Path, default: Any) -> Any:
    """Read a JSON file, returning default on missing/malformed content."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of dicts, skipping blank/torn lines."""
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            rows.append(json.loads(stripped))
        except json.JSONDecodeError:
            # A torn final append is benign; mid-file corruption is rare for an
            # offline analysis and we prefer best-effort over hard failure.
            continue
    return rows


@dataclass
class RunData:
    """All on-disk artifacts for one run, loaded once."""

    sim_code: str
    run_dir: Path
    meta: dict[str, Any] = field(default_factory=dict)
    scenario: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    requests: list[dict[str, Any]] = field(default_factory=list)
    rewards: list[dict[str, Any]] = field(default_factory=list)
    # step -> movement packet (the frontend movement/<step>.json schema).
    movement: dict[int, dict[str, Any]] = field(default_factory=dict)
    # persona name -> memory node count (0 if no nodes.json present).
    memory_counts: dict[str, int] = field(default_factory=dict)

    @property
    def persona_names(self) -> list[str]:
        names = list(self.meta.get("persona_names") or [])
        if names:
            return names
        # Fall back to scenario agents if meta is sparse.
        return [a.get("name") for a in self.scenario.get("agents", []) if a.get("name")]

    def scenario_roles(self) -> dict[str, dict[str, str]]:
        """Map persona name -> {role, mission} from the scenario config."""
        out: dict[str, dict[str, str]] = {}
        for agent in self.scenario.get("agents", []):
            name = agent.get("name")
            if not name:
                continue
            out[name] = {
                "role": str(agent.get("role", "")),
                "mission": str(agent.get("mission", "")),
            }
        return out


def load_run(sim_code: str) -> RunData:
    """Load every artifact for a run into a RunData object."""
    run_dir = resolve_run_dir(sim_code)
    data = RunData(sim_code=run_dir.name, run_dir=run_dir)

    data.meta = _read_json(run_dir / "reverie" / "meta.json", {})
    data.scenario = _read_json(run_dir / "reverie" / "scenario.json", {})
    data.events = _read_jsonl(run_dir / "events.jsonl")
    data.requests = _read_jsonl(run_dir / "town_center" / "requests.jsonl")
    data.rewards = _read_jsonl(run_dir / "town_center" / "rewards.jsonl")
    data.movement = _load_movement(run_dir / "movement")
    data.memory_counts = _load_memory_counts(run_dir / "personas")
    return data


def _load_movement(move_dir: Path) -> dict[int, dict[str, Any]]:
    """Load movement/<step>.json files keyed by integer step."""
    out: dict[int, dict[str, Any]] = {}
    if not move_dir.is_dir():
        return out
    for path in move_dir.glob("*.json"):
        stem = path.stem
        if not stem.isdigit():
            continue
        packet = _read_json(path, None)
        if isinstance(packet, dict):
            out[int(stem)] = packet
    return out


def _load_memory_counts(personas_dir: Path) -> dict[str, int]:
    """Count associative-memory nodes per persona if nodes.json exists."""
    out: dict[str, int] = {}
    if not personas_dir.is_dir():
        return out
    for persona_dir in personas_dir.iterdir():
        if not persona_dir.is_dir():
            continue
        nodes_path = (
            persona_dir
            / "bootstrap_memory"
            / "associative_memory"
            / "nodes.json"
        )
        nodes = _read_json(nodes_path, {})
        out[persona_dir.name] = len(nodes) if isinstance(nodes, dict) else 0
    return out
