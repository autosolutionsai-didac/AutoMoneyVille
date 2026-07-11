"""
Author: Joon Sung Park (joonspk@stanford.edu)

File: compress_sim_storage.py
Description: Compresses a simulation for replay demos.
"""

import json
import os
import shutil
import sys
from pathlib import Path

# Resolve storage roots from this script's location so compress works from any CWD.
# Runs live under storage/runs/<sim> (matches fs_storage_runs); recordings go to
# compressed_storage/<sim> for the demo/replay views.
_FE = (Path(__file__).resolve().parent.parent / "environment" / "frontend_server")
_RUNS = _FE / "storage" / "runs"
_COMPRESSED = _FE / "compressed_storage"


def compress(sim_code):
    sim_storage = str(_RUNS / sim_code)
    compressed_storage = str(_COMPRESSED / sim_code)
    persona_folder = sim_storage + "/personas"
    move_folder = sim_storage + "/movement"
    meta_file = sim_storage + "/reverie/meta.json"

    if not Path(move_folder).exists():
        raise SystemExit(
            f"No movement/ folder in {sim_storage}; run the sim first "
            "(per-step movement files are written as it steps)."
        )

    max_move_count = max(
        int(p.stem) for p in Path(move_folder).glob("*.json") if p.stem.isdigit()
    )

    # Active personas = those present in the movement stream (a base may ship more
    # persona folders than the run actually simulated).
    with open(f"{move_folder}/0.json") as json_file:
        persona_names = list(json.load(json_file)["persona"].keys())

    persona_last_move = dict()
    master_move = dict()
    for i in range(max_move_count + 1):
        master_move[i] = dict()
        with open(f"{move_folder}/{str(i)}.json") as json_file:
            i_move_dict = json.load(json_file)["persona"]
            for p in persona_names:
                # A step's packet may omit a persona (e.g. a move timeout or the
                # sequential-encounter path). Skip it this step — the delta format
                # carries its last-known position forward in replay.
                if p not in i_move_dict:
                    continue
                move = False
                if i == 0 or (
                    i_move_dict[p]["movement"] != persona_last_move[p]["movement"]
                    or i_move_dict[p]["pronunciatio"]
                    != persona_last_move[p]["pronunciatio"]
                    or i_move_dict[p]["description"]
                    != persona_last_move[p]["description"]
                    or i_move_dict[p]["chat"] != persona_last_move[p]["chat"]
                ):
                    move = True

                if move:
                    persona_last_move[p] = {
                        "movement": i_move_dict[p]["movement"],
                        "pronunciatio": i_move_dict[p]["pronunciatio"],
                        "description": i_move_dict[p]["description"],
                        "chat": i_move_dict[p]["chat"],
                    }
                    master_move[i][p] = {
                        "movement": i_move_dict[p]["movement"],
                        "pronunciatio": i_move_dict[p]["pronunciatio"],
                        "description": i_move_dict[p]["description"],
                        "chat": i_move_dict[p]["chat"],
                    }

    os.makedirs(compressed_storage, exist_ok=True)
    with open(f"{compressed_storage}/master_movement.json", "w") as outfile:
        outfile.write(json.dumps(master_move, indent=2))

    if Path(meta_file).exists():
        shutil.copyfile(meta_file, f"{compressed_storage}/meta.json")
    shutil.copytree(
        persona_folder, f"{compressed_storage}/personas/", dirs_exist_ok=True
    )
    print(f"compressed {max_move_count + 1} steps -> {compressed_storage}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python compress_sim_storage.py <sim_code>")
    compress(sys.argv[1])
