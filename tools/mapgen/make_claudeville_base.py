"""Create claudeville_v2 by cloning the immutable claudeville_v1 base.

Clones the archive, then rewrites only what references the canonical world:
meta.maze_name, each persona's spatial_memory.json + scratch.json
(living_area, daily_plan_req), and environment/0.json spawns (on verified-walkable
tiles read from the generated collision matrix).

Phase 6a/6b: persona count is a clean, documented knob (``--count N``) and each
persona is GROUNDED — its scratch identity (innate/learned/currently/lifestyle +
identity_markers) is enriched from a per-role backstory, and its Phase 3-4 stores
are seeded (a few GoalMemory goals + RelationshipMemory acquaintances). Generation
is deterministic/reproducible (no random, no clock).

Run:
    python tools/mapgen/make_claudeville_base.py            # full scenario roster
    python tools/mapgen/make_claudeville_base.py --count 6  # first 6 personas
    python tools/mapgen/make_claudeville_base.py --count 16 # scale beyond roster
    python tools/mapgen/make_claudeville_base.py --no-grounding  # legacy re-home only
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).resolve().parent / "town_spec.json"
STORAGE = REPO_ROOT / "environment/frontend_server/storage/base"
SRC = STORAGE / "claudeville_v1"
DST = STORAGE / "claudeville_v2"
MATRIX = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/matrix"
)
SCENARIOS = REPO_ROOT / "reverie/backend_server/scenarios"

HOME_SECTOR = "Home 1"
HOME_ARENA = "bedroom"
STANDUP_OLD = "Academia de Agentes:classroom"
STANDUP_NEW = "Agent Academy:classroom"

# Deterministic seed day for created_day stamps on seeded goals (reproducible).
SEED_DAY = "2023-02-13"

# tools/mapgen is not a package; import the sibling factory by path.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import persona_factory  # noqa: E402


def build_spatial_memory(spec) -> dict:
    world = spec["world_name"]
    tree: dict = {world: {}}
    for s in spec.get("sectors", []):
        tree[world].setdefault(s["name"], {})
    for a in spec.get("arenas", []):
        tree[world].setdefault(a["sector"], {}).setdefault(a["name"], [])
    for o in spec.get("objects", []):
        objs = tree[world].setdefault(o["sector"], {}).setdefault(o["arena"], [])
        if o["type"] not in objs:
            objs.append(o["type"])
    return tree


def walkable_tiles(spec) -> list:
    W = spec["grid"]["maze_width"]
    cbid = str(spec.get("collision_block_id", "32125"))
    flat = [
        t.strip()
        for t in (MATRIX / "maze" / "collision_maze.csv").read_text().split(",")
    ]
    free = []
    for i, t in enumerate(flat):
        if t != cbid:
            free.append((i % W, i // W))
    return free


def pick_spawns(spec, n) -> list:
    """Spread spawns across walkable tiles in the central band for visibility."""
    free = walkable_tiles(spec)
    central = [
        (x, y) for (x, y) in free if 18 <= x <= 70 and 18 <= y <= 42
    ] or free
    central.sort(key=lambda t: (t[1], t[0]))
    if not central:
        raise SystemExit("no walkable tiles found")
    step = max(1, len(central) // n)
    return [central[min(i * step, len(central) - 1)] for i in range(n)]


def load_scenario(scenario_id: str) -> dict:
    """Load a scenario JSON by id (no backend import needed for this script)."""
    path = SCENARIOS / f"{scenario_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _ensure_persona_dir(name: str) -> Path:
    """Return (creating if needed) the bootstrap_memory dir for a persona."""
    boot = DST / "personas" / name / "bootstrap_memory"
    boot.mkdir(parents=True, exist_ok=True)
    (boot / "associative_memory").mkdir(parents=True, exist_ok=True)
    return boot


def _base_scratch_for(name: str) -> dict:
    """Read a persona's existing scratch.json, or fall back to any template."""
    boot = DST / "personas" / name / "bootstrap_memory"
    own = boot / "scratch.json"
    if own.exists():
        return json.loads(own.read_text(encoding="utf-8"))
    # Synthetic personas (scaling beyond the roster) reuse the first base
    # persona's scratch as a structural template.
    for persona_dir in sorted((SRC / "personas").iterdir()):
        cand = persona_dir / "bootstrap_memory" / "scratch.json"
        if cand.exists():
            return json.loads(cand.read_text(encoding="utf-8"))
    raise SystemExit("no template scratch.json found")


def write_persona(
    persona: dict, spatial: dict, home: str, ground: bool, roster: list
) -> None:
    """Write one persona's spatial_memory, grounded scratch, goals, relationships."""
    name = persona["name"]
    role = persona["role"]
    mission = persona["mission"]
    boot = _ensure_persona_dir(name)

    (boot / "spatial_memory.json").write_text(json.dumps(spatial, indent=2))

    scratch = _base_scratch_for(name)
    scratch["name"] = name
    scratch["first_name"] = name.split()[0]
    scratch["last_name"] = name.split()[-1]
    scratch["living_area"] = home
    if scratch.get("daily_plan_req"):
        scratch["daily_plan_req"] = scratch["daily_plan_req"].replace(
            STANDUP_OLD, STANDUP_NEW
        )

    if ground:
        identity = persona_factory.build_scratch_identity(name, role, mission)
        scratch.update(identity)
        # Goals + relationships seeds (Phase 3-4 stores).
        goals = persona_factory.seed_goals(role, mission, created_day=SEED_DAY)
        (boot / "goals.json").write_text(
            json.dumps(goals, ensure_ascii=False, indent=2)
        )
        rels = persona_factory.seed_relationships(name, role, roster)
        (boot / "relationships.json").write_text(
            json.dumps(rels, ensure_ascii=False, indent=2)
        )

    (boot / "scratch.json").write_text(json.dumps(scratch, indent=4))
    # Ensure an empty associative-memory nodes file exists (runtime expects it).
    nodes = boot / "associative_memory" / "nodes.json"
    if not nodes.exists():
        nodes.write_text("{}")


def generate(
    count: int | None = None,
    scenario_id: str = "startup_team_v1",
    ground: bool = True,
) -> dict:
    """Build claudeville_v2 for ``count`` personas. Returns a summary."""
    if count is not None and count < 1:
        raise ValueError("count must be a positive integer")
    if SRC.resolve() == DST.resolve():
        raise ValueError("claudeville_v1 source and claudeville_v2 destination differ")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    world = spec["world_name"]
    folder = world.lower()

    scenario = load_scenario(scenario_id)
    roster = persona_factory.personas_for(scenario, count)
    names = [p["name"] for p in roster]

    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    # meta.json
    meta = json.loads((DST / "reverie" / "meta.json").read_text())
    meta["maze_name"] = folder
    meta["fork_sim_code"] = f"base_{folder}_v2"
    meta["persona_names"] = names
    (DST / "reverie" / "meta.json").write_text(json.dumps(meta, indent=4))

    # Prune any copied persona dirs not in the (possibly smaller) roster so the
    # base contains EXACTLY the requested personas — the count knob is exact.
    wanted = set(names)
    personas_root = DST / "personas"
    if personas_root.is_dir():
        for persona_dir in personas_root.iterdir():
            if persona_dir.is_dir() and persona_dir.name not in wanted:
                shutil.rmtree(persona_dir)

    tree = build_spatial_memory(spec)
    home = f"{world}:{HOME_SECTOR}:{HOME_ARENA}"
    for persona in roster:
        write_persona(persona, tree, home, ground, roster)

    # environment/0.json spawns on verified-walkable tiles
    spawns = pick_spawns(spec, len(names))
    env = {}
    for name, (x, y) in zip(names, spawns):
        env[name] = {"maze": folder, "x": x, "y": y}
    (DST / "environment" / "0.json").write_text(json.dumps(env, indent=4))

    try:
        base_label = str(DST.relative_to(REPO_ROOT))
    except ValueError:
        # DST may be redirected outside the repo (e.g. a test temp dir).
        base_label = str(DST)
    return {
        "base": base_label,
        "maze_name": folder,
        "personas": len(names),
        "grounded": ground,
        "home": home,
        "spawn_sample": spawns[:3],
        "spatial_sectors": list(tree[world].keys()),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # Positional count kept for backward compatibility with the old invocation
    # (`make_claudeville_base.py 6`); --count takes precedence if both given.
    parser.add_argument(
        "count_pos", nargs="?", type=int, default=None, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--count",
        "-n",
        type=int,
        default=None,
        help="Number of personas to generate (default: full scenario roster). "
        "Values larger than the roster synthesize extra personas.",
    )
    parser.add_argument(
        "--scenario", default="startup_team_v1", help="Scenario id to draw roles from."
    )
    parser.add_argument(
        "--no-grounding",
        action="store_true",
        help="Skip identity grounding + goal/relationship seeding (legacy re-home).",
    )
    args = parser.parse_args(argv)

    count = args.count if args.count is not None else args.count_pos
    summary = generate(
        count=count, scenario_id=args.scenario, ground=not args.no_grounding
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
