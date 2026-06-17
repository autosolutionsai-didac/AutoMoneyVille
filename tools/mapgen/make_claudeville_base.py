"""Create a persona base run for the claudeville world by re-homing the existing
startup_team_v1 personas. Clones the base, then rewrites only what references the
old world: meta.maze_name, each persona's spatial_memory.json + scratch.json
(living_area, daily_plan_req), and environment/0.json spawns (on verified-walkable
tiles read from the generated collision matrix).

Run: python tools/mapgen/make_claudeville_base.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).resolve().parent / "town_spec.json"
STORAGE = REPO_ROOT / "environment/frontend_server/storage/base"
SRC = STORAGE / "startup_team_v1"
DST = STORAGE / "claudeville_v1"
MATRIX = (
    REPO_ROOT
    / "environment/frontend_server/static_dirs/assets/claudeville/matrix"
)

HOME_SECTOR = "Residencia 1"
HOME_ARENA = "bedroom"
STANDUP_OLD = "Hobbs Cafe:cafe:cafe customer seating"
STANDUP_NEW = "Academia de Agentes:classroom"


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


def main() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    world = spec["world_name"]
    folder = world.lower()

    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    # meta.json
    meta = json.loads((DST / "reverie" / "meta.json").read_text())
    names = meta["persona_names"]
    # Optional: limit persona count for a snappier demo (first step is LLM-bound;
    # the subscription effectively serializes the concurrent first calls).
    if len(sys.argv) > 1:
        names = names[: int(sys.argv[1])]
    meta["maze_name"] = folder
    meta["fork_sim_code"] = f"base_{folder}_v1"
    meta["persona_names"] = names
    (DST / "reverie" / "meta.json").write_text(json.dumps(meta, indent=4))

    # spatial memory (shared) + per-persona scratch rewrites
    tree = build_spatial_memory(spec)
    home = f"{world}:{HOME_SECTOR}:{HOME_ARENA}"
    for name in names:
        boot = DST / "personas" / name / "bootstrap_memory"
        (boot / "spatial_memory.json").write_text(json.dumps(tree, indent=2))
        scratch = json.loads((boot / "scratch.json").read_text())
        scratch["living_area"] = home
        if scratch.get("daily_plan_req"):
            scratch["daily_plan_req"] = scratch["daily_plan_req"].replace(
                STANDUP_OLD, STANDUP_NEW
            )
        (boot / "scratch.json").write_text(json.dumps(scratch, indent=4))

    # environment/0.json spawns on verified-walkable tiles
    spawns = pick_spawns(spec, len(names))
    env = {}
    for name, (x, y) in zip(names, spawns):
        env[name] = {"maze": folder, "x": x, "y": y}
    (DST / "environment" / "0.json").write_text(json.dumps(env, indent=4))

    print(
        json.dumps(
            {
                "base": str(DST.relative_to(REPO_ROOT)),
                "maze_name": folder,
                "personas": len(names),
                "home": home,
                "spawn_sample": spawns[:3],
                "spatial_sectors": list(tree[world].keys()),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
