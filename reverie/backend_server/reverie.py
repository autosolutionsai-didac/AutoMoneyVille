"""
Original Author: Joon Sung Park (joonspk@stanford.edu)
Heavily modified for Claudeville (Claude CLI port)

File: reverie.py
Description: Main program for running generative agent simulations.
"""

import asyncio
import collections
import datetime
import json
import math
import os
import shutil
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field

import cli_interface as cli
from agent_requests import submit_latest_town_request
from economy import RequestState
from event_ledger import EventLedger
from flask import Flask, jsonify, request
from maze import Maze
from persona.persona import Persona
from persona.prompt_template.claude_structure import _run_async
from runtime_storage import RunStorage
from scenario_runtime import attach_scenario_to_personas, bind_scenario_to_run
from town_center import TownCenterStore
from utils import (
    debug,
    fs_storage,
    fs_storage_runs,
    fs_temp_storage,
)

# Per-persona budget for a single move() (each persona is timed independently —
# ARCH-2 mitigated). On a grown context a heavy step (day-planning or a piggybacked
# compaction) can be slow, and with the FULL 10-persona roster ~10 concurrent LLM
# calls contend, so the cold standup/day-planning window tripped a 45s cap into
# benign "continue current action" fallbacks. 90s gives the heavy warmup steps room;
# the fallback is harmless (full state rollback) so a higher cap just avoids wasted
# empty steps. Override with CLAUDEVILLE_PERSONA_MOVE_TIMEOUT.
PERSONA_MOVE_TIMEOUT_SECONDS = float(
    os.environ.get("CLAUDEVILLE_PERSONA_MOVE_TIMEOUT", "90")
)


##############################################################################
#                           CONVERSATION GROUPS                              #
##############################################################################


@dataclass
class ConversationGroup:
    """
    Represents an active multi-party conversation.

    Managed centrally by ReverieServer to enable 3+ persona conversations.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    participants: set = field(default_factory=set)
    chat: list = field(default_factory=list)  # [(speaker, line), ...]
    location_tile: tuple = (0, 0)  # Anchor location (first participant's tile)
    started_at: datetime.datetime = None
    end_time: datetime.datetime = None
    last_activity: datetime.datetime = None  # Last time a new message was added
    stale_steps: int = 0  # Steps since last new message

    def add_participant(self, name: str) -> bool:
        """Add a participant to the conversation. Returns True if newly added."""
        if name in self.participants:
            return False
        self.participants.add(name)
        return True

    def add_line(
        self, speaker: str, line: str, curr_time: datetime.datetime = None
    ) -> bool:
        """Add a chat line. Returns True if added (not duplicate)."""
        entry = (speaker, line)
        if entry not in [(spk, txt) for spk, txt in self.chat]:
            self.chat.append(entry)
            self.last_activity = curr_time
            self.stale_steps = 0  # Reset stale counter on new activity
            return True
        return False

    def merge_lines(self, lines: list, curr_time: datetime.datetime = None) -> int:
        """Merge lines from another source. Returns count of new lines added."""
        added = 0
        for speaker, line in lines:
            if self.add_line(speaker, line, curr_time):
                added += 1
        return added

    def get_participants_str(self) -> str:
        """Get participant names as comma-separated string."""
        return ", ".join(sorted(self.participants))

    def remove_participant(self, name: str) -> bool:
        """Remove a participant from the conversation. Returns True if removed."""
        if name in self.participants:
            self.participants.discard(name)
            return True
        return False


def _tile_distance(tile1: tuple, tile2: tuple) -> float:
    """Calculate Chebyshev distance between two tiles (consistent with perception)."""
    if not tile1 or not tile2:
        return float("inf")
    # Chebyshev distance: max of absolute differences (square radius, not circular)
    # This matches how perception uses get_nearby_tiles which checks a square area
    return max(abs(tile1[0] - tile2[0]), abs(tile1[1] - tile2[1]))


def _are_within_range(tile1: tuple, tile2: tuple, vision_r: int = 4) -> bool:
    """Check if two tiles are within vision range of each other."""
    return _tile_distance(tile1, tile2) <= vision_r


def _atomic_write_json(path: str, payload) -> None:
    """
    Write JSON to `path` atomically (5d): serialize to a temp file in the SAME
    directory, flush+fsync it, then os.replace() it onto the target. os.replace
    is atomic on both POSIX and Windows, so a crash mid-write can only ever
    leave either the old complete file or the new complete file — never a
    half-written, corrupt step file. The temp file is cleaned up on failure.
    """
    # Unique temp name in the SAME directory as `path` (it shares the path's
    # dirname) guarantees a same-filesystem rename and avoids collisions if two
    # writers ever target the same dir concurrently.
    tmp_path = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp_path, "w") as outfile:
            outfile.write(json.dumps(payload, indent=2))
            outfile.flush()
            os.fsync(outfile.fileno())
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup so a failed write never leaves a stray temp file.
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


# Backend HTTP server port
BACKEND_PORT = 5000

##############################################################################
#                                  REVERIE                                   #
##############################################################################


class ReverieServer:
    def __init__(self, fork_sim_code, sim_code):
        self.run_storage = RunStorage()

        # FORKING FROM A PRIOR SIMULATION:
        # <fork_sim_code> indicates the simulation we are forking from.
        # Base templates are in storage/base/, simulation runs go to storage/runs/
        self.fork_sim_code = self.run_storage.canonical_fork_code(fork_sim_code)

        # <sim_code> indicates our current simulation. Runs always go to storage/runs/
        self.sim_code = sim_code
        sim_folder = f"{fs_storage_runs}/{self.sim_code}"
        if not os.path.exists(sim_folder):
            self.run_storage.create_run_from_fork(fork_sim_code, self.sim_code)

        # Create movement folder for this run (not in base template)
        os.makedirs(f"{sim_folder}/movement", exist_ok=True)
        self.event_ledger = EventLedger(
            self.run_storage.run_dir(self.sim_code) / "events.jsonl"
        )
        self.town_center = TownCenterStore(
            self.run_storage.run_dir(self.sim_code),
            scenario_id="startup_team_v1",
        )
        bind_scenario_to_run(
            self.run_storage,
            self.sim_code,
            self.town_center.scenario,
        )

        with open(f"{sim_folder}/reverie/meta.json") as json_file:
            reverie_meta = json.load(json_file)

        # Only rewrite when the fork code actually changed — RunStorage already
        # persisted meta during fork resolution, so this avoids a redundant write
        # (and its partial-write surface) on every startup (ARCH-16).
        if reverie_meta.get("fork_sim_code") != self.fork_sim_code:
            reverie_meta["fork_sim_code"] = self.fork_sim_code
            with open(f"{sim_folder}/reverie/meta.json", "w") as outfile:
                outfile.write(json.dumps(reverie_meta, indent=2))

        # LOADING REVERIE'S GLOBAL VARIABLES
        # The start datetime of the Reverie:
        # <start_datetime> is the datetime instance for the start datetime of
        # the Reverie instance. Once it is set, this is not really meant to
        # change. It takes a string date in the following example form:
        # "June 25, 2022"
        # e.g., ...strptime(June 25, 2022, "%B %d, %Y")
        self.start_time = datetime.datetime.strptime(
            f"{reverie_meta['start_date']}, 00:00:00", "%B %d, %Y, %H:%M:%S"
        )
        # <curr_time> is the datetime instance that indicates the game's current
        # time. This gets incremented by <sec_per_step> amount everytime the world
        # progresses (that is, everytime curr_env_file is recieved).
        self.curr_time = datetime.datetime.strptime(
            reverie_meta["curr_time"], "%B %d, %Y, %H:%M:%S"
        )
        # <sec_per_step> denotes the number of seconds in game time that each
        # step moves foward.
        self.sec_per_step = reverie_meta["sec_per_step"]

        # <maze> is the main Maze instance. Note that we pass in the maze_name
        # (e.g., "double_studio") to instantiate Maze.
        # e.g., Maze("double_studio")
        self.maze = Maze(reverie_meta["maze_name"])

        # <step> denotes the number of steps that our game has taken. A step here
        # literally translates to the number of moves our personas made in terms
        # of the number of tiles.
        self.step = reverie_meta["step"]

        # SETTING UP PERSONAS IN REVERIE
        # <personas> is a dictionary that takes the persona's full name as its
        # keys, and the actual persona instance as its values.
        # This dictionary is meant to keep track of all personas who are part of
        # the Reverie instance.
        # e.g., ["Isabella Rodriguez"] = Persona("Isabella Rodriguezs")
        self.personas = dict()
        # <personas_tile> is a dictionary that contains the tile location of
        # the personas (!-> NOT px tile, but the actual tile coordinate).
        # The tile take the form of a set, (row, col).
        # e.g., ["Isabella Rodriguez"] = (58, 39)
        self.personas_tile = dict()

        # # <persona_convo_match> is a dictionary that describes which of the two
        # # personas are talking to each other. It takes a key of a persona's full
        # # name, and value of another persona's full name who is talking to the
        # # original persona.
        # # e.g., dict["Isabella Rodriguez"] = ["Maria Lopez"]
        # self.persona_convo_match = dict()
        # # <persona_convo> contains the actual content of the conversations. It
        # # takes as keys, a pair of persona names, and val of a string convo.
        # # Note that the key pairs are *ordered alphabetically*.
        # # e.g., dict[("Adam Abraham", "Zane Xu")] = "Adam: baba \n Zane:..."
        # self.persona_convo = dict()

        # Loading in all personas.
        # Try to get positions from meta (new way) or fall back to environment file (old way)
        persona_tiles = reverie_meta.get("persona_tiles")
        if not persona_tiles:
            # Fallback: load from environment file (for old simulations)
            init_env_file = f"{sim_folder}/environment/{str(self.step)}.json"
            if os.path.exists(init_env_file):
                init_env = json.load(open(init_env_file))
                persona_tiles = {
                    name: [init_env[name]["x"], init_env[name]["y"]]
                    for name in reverie_meta["persona_names"]
                }
            else:
                # Last resort: find most recent environment file
                env_dir = f"{sim_folder}/environment"
                env_files = [f for f in os.listdir(env_dir) if f.endswith(".json")]
                if env_files:
                    latest = max(env_files, key=lambda f: int(f.replace(".json", "")))
                    init_env = json.load(open(f"{env_dir}/{latest}"))
                    persona_tiles = {
                        name: [init_env[name]["x"], init_env[name]["y"]]
                        for name in reverie_meta["persona_names"]
                    }
                else:
                    raise FileNotFoundError(
                        f"No persona position data found for {self.sim_code}"
                    )

        for persona_name in reverie_meta["persona_names"]:
            persona_folder = f"{sim_folder}/personas/{persona_name}"
            p_x, p_y = persona_tiles[persona_name]
            curr_persona = Persona(persona_name, persona_folder)

            self.personas[persona_name] = curr_persona
            self.personas_tile[persona_name] = (p_x, p_y)
            self.maze.tiles[p_y][p_x]["events"].add(
                curr_persona.scratch.get_curr_event_and_desc()
            )

        attach_scenario_to_personas(self.personas, self.town_center.scenario)

        # Initialize all persona sessions in parallel (avoids delays later)
        from persona.prompt_template.claude_structure import (
            initialize_all_personas_sync,
        )

        initialize_all_personas_sync(self.personas)

        # REVERIE SETTINGS PARAMETERS:
        # <server_sleep> denotes the amount of time that our while loop rests each
        # cycle; this is to not kill our machine.
        self.server_sleep = 0.1

        # SIGNALING THE FRONTEND SERVER:
        # curr_sim_code.json contains the current simulation code, and
        # curr_step.json contains the current step of the simulation. These are
        # used to communicate the code and step information to the frontend.
        # Note that step file is removed as soon as the frontend opens up the
        # simulation.
        self.run_storage.write_current_run_pointer(self.sim_code, self.step)

        # Track game object cleanup between steps
        self._game_obj_cleanup = dict()

        # Lock to prevent concurrent step processing (CLI vs HTTP)
        self._step_lock = threading.Lock()
        self._busy_since = None
        self._busy_reason = None

        # Queue of pending movements for frontend to display
        # Each entry is a movements dict from _process_step
        self._pending_movements = []
        self._movement_history = []
        self._movements_lock = threading.Lock()

        # Live event feed (P1.C2): a small ring buffer of viewer-relevant
        # moments (conversations, requests, day rolls, saves) served over
        # GET /events. The durable audit trail stays in events.jsonl — this is
        # the cheap in-memory view that lets the UI tell the story.
        self._feed_events = collections.deque(maxlen=500)
        self._feed_next_id = 1
        self._feed_lock = threading.Lock()

        # --- Smooth playback: a background producer simulates steps AHEAD of what
        # the frontend has displayed, so the frontend replays a deep buffer at a
        # steady cadence (decouples animation from per-step LLM latency). The
        # /movements cursor reports the displayed step for backpressure, and the
        # producer pauses when nobody is polling so it never burns LLM calls on an
        # idle/closed tab (FE-2 / ARCH-5). ---
        self._buffer_ahead = int(os.environ.get("CLAUDEVILLE_BUFFER_AHEAD", "20"))
        self._autosim_min_fill = int(
            os.environ.get("CLAUDEVILLE_BUFFER_MIN_FILL", "5")
        )
        self._autosim_idle_pause_s = float(
            os.environ.get("CLAUDEVILLE_AUTOSIM_IDLE_S", "8")
        )
        self._displayed_step = max(0, self.step - 1)
        self._last_poll_at = 0.0
        self._autosim_enabled = threading.Event()
        self._stop_autosim = threading.Event()
        # keep history comfortably larger than the buffer so recent packets aren't
        # evicted before a slow/refreshed client reads them
        self._movement_history_limit = max(500, self._buffer_ahead * 6)

        # Periodic auto-save: persona memory (associative/relationships/goals) only
        # hits disk on save(), so a long/unattended run that is never manually saved
        # loses everything (and the eval harness then reads empty memory/social
        # metrics). Auto-save every N steps closes that gap. 0 disables.
        self._autosave_every_steps = int(
            os.environ.get("CLAUDEVILLE_AUTOSAVE_EVERY_STEPS", "250")
        )
        # Seed from the loaded step so a freshly-resumed run waits a full interval
        # before its first auto-save rather than saving immediately.
        self._last_autosave_step = self.step

        # Active conversation groups for multi-party conversations
        # Maps group_id -> ConversationGroup
        self.active_conversations: dict[str, ConversationGroup] = {}

        # HTTP SERVER SETUP
        # Flask app for handling step requests from frontend
        self.flask_app = Flask(__name__)
        self.flask_app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False
        self._setup_flask_routes()

    def _mark_backend_busy(self, reason: str) -> None:
        self._busy_since = datetime.datetime.now(datetime.timezone.utc)
        self._busy_reason = reason

    def _clear_backend_busy(self) -> None:
        self._busy_since = None
        self._busy_reason = None

    def runtime_status(self):
        """Return a compact runtime snapshot for health checks and UI panels."""
        pending_movements = len(getattr(self, "_pending_movements", []))
        step_lock = getattr(self, "_step_lock", None)
        backend_busy = bool(step_lock.locked()) if step_lock else False
        busy_since = getattr(self, "_busy_since", None)
        busy_seconds = None
        if backend_busy and busy_since:
            busy_seconds = round(
                (
                    datetime.datetime.now(datetime.timezone.utc) - busy_since
                ).total_seconds(),
                1,
            )
        personas = []
        # Snapshot to avoid "dict changed size during iteration" if personas
        # mutate concurrently; intentionally lock-free so /health stays
        # responsive during a step (which it reports via backend_busy) (ARCH-4).
        for name, persona in list(self.personas.items()):
            personas.append(
                {
                    "name": name,
                    "tile": self.personas_tile.get(name),
                    "action": persona.scratch.act_description,
                    "location": persona.scratch.act_address,
                    "chatting_with": persona.scratch.chatting_with,
                }
            )
        autosim_evt = getattr(self, "_autosim_enabled", None)
        displayed_step = getattr(self, "_displayed_step", self.step - 1)

        # --- Backpressure / stall observability (5c) ---
        # Additive only: surface enough state for a client/operator to see when
        # production (the autosim producer) is lagging consumption (the polling
        # frontend). None of these fields change simulation behavior.
        min_fill = getattr(self, "_autosim_min_fill", 5)
        buffer_actual = max(0, self.step - 1 - displayed_step)
        # Lock-free length read (matches the pending-movements read above): keeps
        # /health responsive and avoids any chance of deadlock with the producer.
        history_depth = len(getattr(self, "_movement_history", []))
        last_poll_at = getattr(self, "_last_poll_at", 0.0)
        seconds_since_last_poll = (
            round(time.monotonic() - last_poll_at, 1) if last_poll_at else None
        )
        autosim_on = bool(autosim_evt.is_set()) if autosim_evt else False
        # A stall is when a consumer is actively polling (recent poll) and
        # autosim is enabled, yet the ahead-buffer is starved below min fill —
        # i.e. the producer cannot keep up with playback.
        recently_polled = (
            seconds_since_last_poll is not None
            and seconds_since_last_poll
            <= getattr(self, "_autosim_idle_pause_s", 8)
        )
        producer_stalled = bool(
            autosim_on and recently_polled and buffer_actual < min_fill
        )

        return {
            "ok": True,
            "service": "claudeville-backend",
            "sim_code": self.sim_code,
            "fork_sim_code": self.fork_sim_code,
            "maze_name": self.maze.maze_name,
            "map_width_px": self.maze.maze_width * self.maze.sq_tile_size,
            "map_height_px": self.maze.maze_height * self.maze.sq_tile_size,
            "step": self.step,
            "curr_time": self.curr_time.strftime("%B %d, %Y, %H:%M:%S"),
            "sec_per_step": self.sec_per_step,
            "movement_queue_depth": pending_movements,
            "backend_busy": backend_busy,
            "backend_busy_since": (
                busy_since.isoformat() if backend_busy and busy_since else None
            ),
            "backend_busy_seconds": busy_seconds,
            "backend_busy_reason": (
                getattr(self, "_busy_reason", None) if backend_busy else None
            ),
            "active_conversations": len(self.active_conversations),
            "persona_count": len(self.personas),
            "personas": personas,
            # smooth-playback buffer state (for the frontend's buffering UX)
            "autosim_enabled": autosim_on,
            "buffer_ahead_target": getattr(self, "_buffer_ahead", 0),
            "buffer_ahead_actual": buffer_actual,
            "buffering": buffer_actual < min_fill,
            # backpressure / stall observability (5c) — additive, no behavior change
            "buffer_min_fill": min_fill,
            "movement_history_depth": history_depth,
            "movement_history_limit": getattr(self, "_movement_history_limit", 0),
            "seconds_since_last_poll": seconds_since_last_poll,
            "producer_stalled": producer_stalled,
        }

    def _persona_state_snapshot(self, persona) -> dict:
        """Build the live-inspector view of one persona.

        Everything is read defensively (getattr + try) from in-memory state:
        a mid-step read must degrade to partial data, never to a 500.
        """
        scratch = getattr(persona, "scratch", None)

        def _s(attr, default=""):
            value = getattr(scratch, attr, default) if scratch else default
            return default if value is None else value

        # Schedule: f_daily_schedule rows are [task, duration_minutes]; the
        # current row is where cumulative minutes pass minutes-since-midnight.
        schedule = []
        current_index = -1
        try:
            raw = list(_s("f_daily_schedule", []) or [])
            curr_time = _s("curr_time", None)
            minutes_now = (
                curr_time.hour * 60 + curr_time.minute if curr_time else -1
            )
            elapsed = 0
            for i, row in enumerate(raw):
                task = str(row[0]) if row else ""
                minutes = int(row[1]) if row and len(row) > 1 else 0
                if current_index < 0 and minutes_now >= 0 and (
                    elapsed <= minutes_now < elapsed + max(minutes, 1)
                ):
                    current_index = i
                schedule.append({"task": task, "minutes": minutes})
                elapsed += minutes
        except Exception:
            schedule = []
            current_index = -1

        # Recent memories: seq_* lists are newest-first ConceptNodes.
        memories = []
        try:
            a_mem = getattr(persona, "a_mem", None)
            buckets = [
                ("event", list(getattr(a_mem, "seq_event", []) or [])[:10]),
                ("thought", list(getattr(a_mem, "seq_thought", []) or [])[:10]),
                ("chat", list(getattr(a_mem, "seq_chat", []) or [])[:10]),
            ]
            for kind, nodes in buckets:
                for node in nodes:
                    created = getattr(node, "created", None)
                    memories.append(
                        {
                            "kind": kind,
                            "description": str(getattr(node, "description", "")),
                            "created": str(created) if created else "",
                            "poignancy": getattr(node, "poignancy", None),
                        }
                    )
            memories.sort(key=lambda m: m["created"], reverse=True)
            memories = memories[:20]
        except Exception:
            memories = []

        # Relationships: name -> record with familiarity/affinity/sentiment.
        relationships = []
        try:
            records = dict(
                getattr(getattr(persona, "r_mem", None), "relationships", {}) or {}
            )
            for other, rec in records.items():
                relationships.append(
                    {
                        "name": str(rec.get("name", other)),
                        "familiarity": rec.get("familiarity", 0),
                        "affinity": rec.get("affinity", 0.0),
                        "sentiment": rec.get("sentiment", ""),
                        "last_topics": list(rec.get("last_topics", []) or [])[:4],
                    }
                )
            relationships.sort(key=lambda r: -r["familiarity"])
        except Exception:
            relationships = []

        # Goals: keep it to plain strings per record.
        goals = []
        try:
            for rec in (getattr(getattr(persona, "g_mem", None), "goals", {}) or {}).values():
                if isinstance(rec, dict):
                    goals.append(
                        {
                            "title": str(
                                rec.get("title")
                                or rec.get("description")
                                or rec.get("goal")
                                or ""
                            )[:160],
                            "status": str(rec.get("status", "")),
                        }
                    )
        except Exception:
            goals = []

        name = getattr(persona, "name", "")
        return {
            "name": name,
            "currently": str(_s("currently", "")),
            "action": str(_s("act_description", "")),
            "address": str(_s("act_address", "")),
            "chatting_with": _s("chatting_with", None) or None,
            "tile": list(self.personas_tile.get(name, []) or []),
            "schedule": schedule,
            "schedule_current_index": current_index,
            "memories": memories,
            "relationships": relationships,
            "goals": goals,
        }

    def feed_event(
        self,
        event_type: str,
        text: str,
        *,
        personas: list[str] | None = None,
        tile=None,
    ) -> None:
        """Append a viewer-relevant moment to the live feed ring buffer.

        Never raises: the feed is presentation-layer telemetry and must not be
        able to break a step. `category` is derived for the UI's filter chips.
        """
        try:
            category = "sim"
            if event_type.startswith("conversation"):
                category = "chat"
            elif event_type.startswith(("request", "delivery")):
                category = "economy"
            curr_time = getattr(self, "curr_time", None)
            with self._feed_lock:
                self._feed_events.append(
                    {
                        "id": self._feed_next_id,
                        "step": getattr(self, "step", 0),
                        "sim_time": curr_time.strftime("%H:%M") if curr_time else "",
                        "type": event_type,
                        "category": category,
                        "text": str(text)[:300],
                        "personas": list(personas or []),
                        "tile": list(tile) if tile else None,
                    }
                )
                self._feed_next_id += 1
        except Exception:
            pass

    def _setup_flask_routes(self):
        """Set up Flask HTTP endpoints for frontend communication."""

        @self.flask_app.route("/health", methods=["GET"])
        def handle_health():
            """Return backend health and queue information."""
            return jsonify(self.runtime_status())

        @self.flask_app.route("/movements", methods=["GET"])
        def handle_movements():
            """
            Return pending movements for frontend to animate.
            Frontend polls this endpoint to get movement data.
            Backend (CLI) drives the simulation and queues movements here.
            """
            after_step = request.args.get("after_step", type=int)
            with self._movements_lock:
                # a poll means a client is actively watching -> let the producer run,
                # and advance the displayed-step cursor for backpressure.
                self._last_poll_at = time.monotonic()
                if after_step is not None and after_step > getattr(
                    self, "_displayed_step", -1
                ):
                    self._displayed_step = after_step
                if after_step is not None:
                    self._pending_movements = [
                        movement
                        for movement in self._pending_movements
                        if self._movement_step(movement) > after_step
                    ]
                    for movement in self._movement_history:
                        if self._movement_step(movement) > after_step:
                            return jsonify(movement)
                    return jsonify({"empty": True, "step": self.step, "cursor": after_step})

                if self._pending_movements:
                    # Return oldest pending movement
                    movement = self._pending_movements.pop(0)
                    return jsonify(movement)
                else:
                    # No pending movements
                    return jsonify({"empty": True, "step": self.step})

        @self.flask_app.route("/status", methods=["GET"])
        def handle_status():
            """Return current simulation status."""
            status = self.runtime_status()
            status["personas"] = list(self.personas.keys())
            return jsonify(status)

        @self.flask_app.route("/scenario", methods=["GET"])
        def handle_scenario():
            """Return the active scenario configuration."""
            return jsonify(self.town_center.scenario)

        @self.flask_app.route("/town-center", methods=["GET"])
        def handle_town_center():
            """Return the governed money-agent control-plane snapshot."""
            return jsonify(self.town_center.snapshot())

        @self.flask_app.route("/town-center/requests", methods=["POST"])
        def handle_town_center_request():
            """Submit a request for tools, resources, approvals, or actions."""
            data = request.get_json() or {}
            if not data.get("title"):
                return jsonify({"error": "title is required"}), 400
            entry = self.town_center.submit_request(
                actor=data.get("actor", "human"),
                request_type=data.get("type", "tool"),
                title=data["title"],
                rationale=data.get("rationale", ""),
                payload=data.get("payload", {}),
            )
            return jsonify(entry)

        @self.flask_app.route(
            "/town-center/requests/<request_id>/transition", methods=["POST"]
        )
        def handle_town_center_request_transition(request_id):
            """Move a request through the approval lifecycle.

            With `execute: true` in the body (the console's default for its
            Approve button), an `approved` transition immediately chains to
            `completed` so ONE human click = approve + run tool + persist
            artifact + feed the agent's memory. Previously Approve parked the
            request in an unreachable limbo (only `completed` executes, and the
            UI could never reach an approved request again).
            """
            data = request.get_json() or {}
            try:
                target_state = RequestState(data.get("state", ""))
                entry = self.town_center.transition_request(
                    request_id,
                    target_state,
                    reviewer=data.get("reviewer", "human"),
                    note=data.get("note", ""),
                )
                if target_state == RequestState.APPROVED and data.get("execute"):
                    entry = self.town_center.transition_request(
                        request_id,
                        RequestState.COMPLETED,
                        reviewer=data.get("reviewer", "human"),
                        note=data.get("note", "") or "approved and executed",
                    )
            except ValueError:
                return jsonify({"error": "invalid request state"}), 400
            # Stage 1: feed a human-approved tool's executed result into the
            # requesting persona's memory too (same grounding as the auto path).
            if isinstance(entry, dict) and entry.get("tool_result"):
                actor = entry.get("actor")
                self._feed_tool_result_to_persona(
                    self.personas.get(actor) if actor else None,
                    entry.get("tool_result"),
                )
            if isinstance(entry, dict):
                req = self.town_center.find_request(request_id) or {}
                self.feed_event(
                    "request_transition",
                    f"You marked \"{req.get('title', request_id)}\" "
                    f"{entry.get('state', '?')}",
                    personas=[str(req.get("actor") or "")],
                )
            return jsonify(entry)

        @self.flask_app.route("/town-center/rewards", methods=["POST"])
        def handle_town_center_reward():
            """Award auditable points or revenue evidence."""
            data = request.get_json() or {}
            if not data.get("actor") or not data.get("source"):
                return jsonify({"error": "actor and source are required"}), 400
            entry = self.town_center.award_reward(
                actor=data["actor"],
                points=int(data.get("points", 0)),
                source=data["source"],
                evidence=data.get("evidence", ""),
                revenue_cents=int(data.get("revenue_cents", 0)),
            )
            return jsonify(entry)

        @self.flask_app.route(
            "/town-center/requests/<request_id>/record-delivery", methods=["POST"]
        )
        def handle_town_center_record_delivery(request_id):
            """Credit HUMAN-CONFIRMED revenue for a delivered request.

            The only path to real revenue_cents (Stage 1.4): requires typed
            evidence from the human reviewer; idempotent per request.
            """
            data = request.get_json() or {}
            if self.town_center.find_request(request_id) is None:
                return jsonify({"error": "unknown request id"}), 404
            evidence = str(data.get("evidence", "")).strip()
            if not evidence:
                return jsonify({"error": "evidence is required"}), 400
            try:
                revenue_cents = int(data.get("revenue_cents", 0))
            except (TypeError, ValueError):
                return jsonify({"error": "revenue_cents must be an integer"}), 400
            entry = self.town_center.record_delivery(
                request_id,
                revenue_cents=revenue_cents,
                evidence=evidence,
                reviewer=str(data.get("reviewer", "human")),
            )
            if entry is None:
                return jsonify(
                    {"already_recorded": True, "request_id": request_id}
                )
            self.feed_event(
                "delivery_recorded",
                f"REAL REVENUE: {entry.get('revenue_cents', 0) / 100:.2f} USD "
                f"credited to {entry.get('actor', '?')}",
                personas=[str(entry.get("actor") or "")],
            )
            return jsonify(entry)

        @self.flask_app.route("/events", methods=["GET"])
        def handle_events():
            """Live event feed since `after_id` (viewer-relevant moments)."""
            try:
                after_id = int(request.args.get("after_id", 0))
            except (TypeError, ValueError):
                after_id = 0
            with self._feed_lock:
                events = [e for e in self._feed_events if e["id"] > after_id]
                latest = self._feed_next_id - 1
            return jsonify({"events": events, "latest_id": latest})

        @self.flask_app.route("/persona/<persona_name>/state", methods=["GET"])
        def handle_persona_state(persona_name):
            """Live inspector snapshot for one persona (read-only, lock-free —
            same best-effort semantics as /health). The sim's whole point is
            agent cognition; this is the endpoint that finally exposes it."""
            persona = self.personas.get(persona_name)
            if persona is None:
                # Tolerate URL-encoded / underscore variants of display names.
                wanted = persona_name.replace("_", " ").strip().lower()
                for name, candidate in self.personas.items():
                    if name.lower() == wanted:
                        persona = candidate
                        break
            if persona is None:
                return jsonify({"error": "unknown persona"}), 404
            return jsonify(self._persona_state_snapshot(persona))

        @self.flask_app.route("/save", methods=["POST"])
        def handle_save():
            """Save simulation state."""
            # Pause the autosim producer so it doesn't starve the save of the step
            # lock, then hold the lock so a save can't capture half-mutated state
            # while a step is in progress (ARCH-4). Saves the backend head.
            autosim_evt = getattr(self, "_autosim_enabled", None)
            was_enabled = bool(autosim_evt.is_set()) if autosim_evt else False
            if autosim_evt:
                autosim_evt.clear()
            try:
                with self._step_lock:
                    self.save()
                    saved_step = self.step
            finally:
                if was_enabled:
                    autosim_evt.set()
            return jsonify({"status": "saved", "step": saved_step})

        @self.flask_app.route("/simulate", methods=["POST"])
        def handle_simulate():
            """
            Run simulation steps on demand from frontend.
            Request body: {"steps": N} where N is number of steps to simulate.
            Returns immediately after queueing the steps.
            """
            # When autosim is on, the background producer drives stepping; the
            # frontend is a pure consumer, so /simulate is a no-op echo (removes the
            # in-request synchronous stepping + proxy-timeout risk, ARCH-5).
            autosim_evt = getattr(self, "_autosim_enabled", None)
            if autosim_evt and autosim_evt.is_set():
                self._last_poll_at = time.monotonic()
                gap = max(0, self.step - 1 - self._displayed_step)
                return jsonify(
                    {
                        "status": "autosim",
                        "current_step": self.step,
                        "buffer_ahead_actual": gap,
                        "buffer_ahead_target": self._buffer_ahead,
                        "queued_movements": len(self._pending_movements),
                    }
                )

            # Check if a step is already in progress (non-blocking)
            if not self._step_lock.acquire(blocking=False):
                # Step already running - return current state without running more
                return jsonify(
                    {
                        "status": "busy",
                        "message": "Step already in progress",
                        "current_step": self.step,
                        "queued_movements": len(self._pending_movements),
                    }
                )

            try:
                self._mark_backend_busy("simulate request")
                data = request.get_json() or {}
                num_steps = min(data.get("steps", 1), 10)  # Cap at 10 steps per request
                self._busy_reason = f"simulate {num_steps} step(s)"

                # Build environment data from current state
                environment = {}
                for persona_name in self.personas:
                    tile = self.personas_tile[persona_name]
                    environment[persona_name] = {"x": tile[0], "y": tile[1]}

                # Run the steps (movements get queued automatically)
                for i in range(num_steps):
                    # Print step header like CLI does
                    cli.print_step_start(self.step, self.curr_time)
                    self._process_step_unlocked({"environment": environment})
                    # Update environment for next step
                    for persona_name in self.personas:
                        tile = self.personas_tile[persona_name]
                        environment[persona_name] = {"x": tile[0], "y": tile[1]}

                return jsonify(
                    {
                        "status": "ok",
                        "steps_run": num_steps,
                        "current_step": self.step,
                        "queued_movements": len(self._pending_movements),
                    }
                )
            finally:
                self._clear_backend_busy()
                self._step_lock.release()

        @self.flask_app.route("/saves", methods=["GET"])
        def handle_list_saves():
            """List available save files."""
            saves = []
            runs_dir = fs_storage
            if os.path.exists(runs_dir):
                for sim_name in os.listdir(runs_dir):
                    meta_path = f"{runs_dir}/{sim_name}/reverie/meta.json"
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path) as f:
                                meta = json.load(f)
                            saves.append(
                                {
                                    "sim_code": sim_name,
                                    "step": meta.get("step", 0),
                                    "curr_time": meta.get("curr_time", ""),
                                    "personas": meta.get("persona_names", []),
                                }
                            )
                        except (OSError, json.JSONDecodeError, KeyError):
                            pass
            return jsonify({"saves": saves})

    def _process_step(self, data):
        """
        Process one simulation step. This is the core logic extracted from
        start_server() but designed for HTTP request/response instead of
        file-based polling.

        Args:
            data: dict with 'step', 'sim_code', 'environment' keys
                  environment contains persona positions: {name: {x, y, maze}}

        Returns:
            dict with 'persona' movements and 'meta' information

        Thread-safe: Uses _step_lock to prevent concurrent processing.
        """
        with self._step_lock:
            self._mark_backend_busy("process simulation step")
            try:
                return self._process_step_unlocked(data)
            finally:
                self._clear_backend_busy()

    def _validate_env_tile(self, env_pos, fallback_tile):
        """Validate a frontend-supplied tile, falling back to the current backend
        tile when the persona is missing from the payload or the coordinates are
        absent, non-numeric, or out of maze bounds (ARCH-12)."""
        if not isinstance(env_pos, dict) or "x" not in env_pos or "y" not in env_pos:
            return fallback_tile
        try:
            px, py = int(env_pos["x"]), int(env_pos["y"])
        except (TypeError, ValueError):
            return fallback_tile
        if 0 <= px < self.maze.maze_width and 0 <= py < self.maze.maze_height:
            return (px, py)
        return fallback_tile

    def _process_step_unlocked(self, data):
        """Internal step processing (must hold _step_lock)."""
        # Note: We ignore data["step"] - the backend is authoritative.
        # This allows CLI "run" commands to work alongside frontend requests.
        # Lightweight, additive component timing (EVAL Phase 2): coarse
        # wall-clock for perceive/position-update, the persona cognitive/move
        # batch, and serialize. Recorded as one extra "step_timing" ledger event
        # at the end; it never alters any decision path.
        _t_step_start = time.perf_counter()
        environment = data.get("environment", {})

        # Reset per-step spatial caches (5e). get_nearby_tiles memoizes within a
        # step; clearing here guarantees no cross-step leakage. Geometry is
        # step-invariant so this never changes results — it only bounds the cache.
        self.maze.clear_step_cache()

        # Clean up game object events from previous cycle
        for key, val in self._game_obj_cleanup.items():
            self.maze.turn_event_from_tile_idle(key, val)
        self._game_obj_cleanup = dict()

        # Update persona positions in backend to match frontend
        for persona_name, persona in self.personas.items():
            curr_tile = self.personas_tile[persona_name]
            new_tile = self._validate_env_tile(
                environment.get(persona_name), curr_tile
            )

            # Move persona on backend tile map
            self.personas_tile[persona_name] = new_tile
            self.maze.remove_subject_events_from_tile(persona.name, curr_tile)
            self.maze.add_event_from_tile(
                persona.scratch.get_curr_event_and_desc(), new_tile
            )

            # If persona reached destination, activate object action
            if not persona.scratch.planned_path:
                self._game_obj_cleanup[
                    persona.scratch.get_curr_obj_event_and_desc()
                ] = new_tile
                self.maze.add_event_from_tile(
                    persona.scratch.get_curr_obj_event_and_desc(), new_tile
                )
                blank = (
                    persona.scratch.get_curr_obj_event_and_desc()[0],
                    None,
                    None,
                    None,
                )
                self.maze.remove_event_from_tile(blank, new_tile)

        # Feed each persona the outcomes of their recent Town Center requests so the
        # next decision can adapt (approved -> proceed, rejected -> rethink).
        self._refresh_town_center_feedback()

        # Boundary: perceive / position-update phase complete; cognitive begins.
        _t_perceive_done = time.perf_counter()

        # Run cognitive pipeline for all personas
        movements = {"persona": {}, "meta": {}}
        submitted_town_requests = []

        # SEQUENTIAL INITIATIVE SYSTEM
        # For new encounters (two personas seeing each other for first time),
        # we run them sequentially to avoid both greeting simultaneously.
        # Initiative is determined by: alphabetical order, flipped on odd steps.
        new_encounter_pairs = self._detect_new_encounters()
        handled_personas = set()  # Personas already processed via sequential initiative

        if new_encounter_pairs:
            sequential_results = _run_async(
                self._run_sequential_encounters(new_encounter_pairs)
            )
            for result in sequential_results:
                if isinstance(result, Exception):
                    cli.print_error(f"Sequential encounter failed: {result}")
                    continue
                name, next_tile, pronunciatio, description, chat, had_llm_call = result
                movements["persona"][name] = {
                    "movement": next_tile,
                    "pronunciatio": pronunciatio,
                    "description": description,
                    "chat": chat,
                    "had_action": had_llm_call,
                }
                if had_llm_call:
                    self._submit_latest_town_request(name, submitted_town_requests)
                self.personas_tile[name] = next_tile
                handled_personas.add(name)

        async def run_persona_move(name, persona):
            """
            Run a single persona's move with its OWN timeout (5b).

            Each persona gets an independent PERSONA_MOVE_TIMEOUT_SECONDS budget
            (via _move_persona_with_timeout), so one slow/hung persona no longer
            forces the whole batch into the no-op fallback — the others still
            produce real results, and a timed-out persona is fully rolled back to
            its pre-step state and gets the continue-current-action fallback.
            """
            next_tile, pronunciatio, description, had_llm_call = (
                await self._move_persona_with_timeout(name, persona)
            )
            return (
                name,
                next_tile,
                pronunciatio,
                description,
                persona.scratch.chat,
                had_llm_call,
            )

        async def run_remaining_personas():
            """Run remaining personas (not handled by sequential initiative) in parallel.

            Per-persona timeouts live inside run_persona_move, so this gather has
            no outer batch timeout — a single slow persona is isolated to its own
            task and the others still complete with real results.
            """
            tasks = [
                run_persona_move(name, persona)
                for name, persona in self.personas.items()
                if name not in handled_personas
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)

        # Run remaining persona moves in parallel. No outer batch timeout: each
        # persona is bounded individually inside run_persona_move (5b).
        try:
            self._busy_reason = f"processing step {self.step}: moving personas"
            results = _run_async(run_remaining_personas())
            # Check for exceptions in results
            for r in results:
                if isinstance(r, Exception):
                    cli.print_error(f"Persona move failed: {r}")
                    import traceback

                    traceback.print_exception(type(r), r, r.__traceback__)
        except Exception as e:
            cli.print_error(f"Fatal error in parallel execution: {e}")
            import traceback

            traceback.print_exc()
            raise

        # Track if any persona had an LLM call (new action)
        any_llm_call = False
        active_personas = []  # Track which personas made LLM decisions
        for result in results:
            # Skip exceptions (already logged above)
            if isinstance(result, Exception):
                continue
            name, next_tile, pronunciatio, description, chat, had_llm_call = result
            movements["persona"][name] = {
                "movement": next_tile,
                "pronunciatio": pronunciatio,
                "description": description,
                "chat": chat,
                "had_action": had_llm_call,  # Mark individual persona's LLM status
            }
            # Update backend position state with new tile
            self.personas_tile[name] = next_tile
            if had_llm_call:
                any_llm_call = True
                active_personas.append(name)
                self._submit_latest_town_request(name, submitted_town_requests)

        # Boundary: persona cognitive/move batch complete; serialize begins.
        _t_move_done = time.perf_counter()

        # CONVERSATION SYNCHRONIZATION
        # After all personas have moved in parallel, synchronize their chats.
        # If Klaus is chatting with Maria and Maria is chatting with Klaus,
        # merge their chat lists so both have the full conversation.
        try:
            self._busy_reason = f"processing step {self.step}: synchronizing"
            self._synchronize_conversations()
        except Exception as e:
            cli.print_error(f"Error in conversation sync: {e}")
            import traceback

            traceback.print_exc()

        # Update movements with synchronized chat data and conversation partner
        # This ensures frontend receives the complete merged conversation
        for name, persona in self.personas.items():
            if name in movements["persona"]:
                if persona.scratch.chat:
                    movements["persona"][name]["chat"] = persona.scratch.chat
                # Add conversation partner for sprite facing direction
                if persona.scratch.chatting_with:
                    movements["persona"][name][
                        "chatting_with"
                    ] = persona.scratch.chatting_with

        # Add meta information (step is sent BEFORE increment so frontend knows what step this was)
        movements["meta"]["curr_time"] = self.curr_time.strftime("%B %d, %Y, %H:%M:%S")
        movements["meta"]["step"] = self.step  # Current step being processed
        movements["meta"][
            "had_new_action"
        ] = any_llm_call  # True if any persona made new decision
        movements["meta"][
            "active_personas"
        ] = active_personas  # List of personas who made decisions
        movements["meta"]["town_requests"] = submitted_town_requests
        movements["meta"]["town_request_count"] = len(submitted_town_requests)

        # Add active conversation groups for frontend display
        movements["meta"]["conversations"] = {
            group_id: {
                "participants": list(group.participants),
                "line_count": len(group.chat),
            }
            for group_id, group in self.active_conversations.items()
        }

        # Advance simulation state
        self.step += 1
        previous_date = self.curr_time.date()
        self.curr_time += datetime.timedelta(seconds=self.sec_per_step)
        if self.curr_time.date() != previous_date:
            self.feed_event(
                "new_day",
                f"A new day begins: {self.curr_time.strftime('%A, %B %d')}",
            )

        self.run_storage.write_current_run_pointer(self.sim_code, self.step)

        # Queue movements for frontend to poll
        self._busy_reason = f"processing step {self.step}: queueing movement"
        self.event_ledger.append(
            "simulation_step",
            actor="runtime",
            step=movements["meta"]["step"],
            sim_time=movements["meta"]["curr_time"],
            payload={
                "had_new_action": any_llm_call,
                "active_personas": active_personas,
                "persona_count": len(movements["persona"]),
                "conversation_count": len(movements["meta"]["conversations"]),
                "town_request_count": len(submitted_town_requests),
            },
        )
        self._record_movement(movements)

        # Phase 4e: emit any pending day-boundary identity-drift checkpoints so
        # the eval harness can read them (a persona stashes its drift result on
        # last_identity_drift at the day rollover). Best-effort and cleared after
        # emission so each checkpoint is recorded once.
        for name, persona in self.personas.items():
            drift = getattr(persona, "last_identity_drift", None)
            if not drift:
                continue
            try:
                self.event_ledger.append(
                    "identity_drift",
                    actor=name,
                    step=movements["meta"]["step"],
                    sim_time=drift.get("sim_time") or movements["meta"]["curr_time"],
                    payload={
                        "drift_score": drift.get("drift_score", 0.0),
                        "drift_note": drift.get("drift_note", ""),
                    },
                )
            except Exception:
                pass
            persona.last_identity_drift = None

        # Additive component timing (EVAL Phase 2). Best-effort: a telemetry
        # failure must never break a simulation step.
        try:
            _t_end = time.perf_counter()
            self.event_ledger.append(
                "step_timing",
                actor="runtime",
                step=movements["meta"]["step"],
                sim_time=movements["meta"]["curr_time"],
                payload={
                    "perceive_ms": round((_t_perceive_done - _t_step_start) * 1000, 2),
                    "move_ms": round((_t_move_done - _t_perceive_done) * 1000, 2),
                    "serialize_ms": round((_t_end - _t_move_done) * 1000, 2),
                    "total_ms": round((_t_end - _t_step_start) * 1000, 2),
                },
            )
        except Exception:
            pass

        return movements

    def _fallback_persona_move_result(self, name, persona):
        """Return a no-LLM movement for a persona when a step times out."""
        tile = self.personas_tile.get(name) or getattr(
            persona.scratch, "curr_tile", None
        )
        if tile is None:
            tile = (0, 0)
        description = persona.scratch.act_description or "Waiting for next step"
        address = persona.scratch.act_address
        if address and " @ " not in description:
            description = f"{description} @ {address}"
        return (
            name,
            tile,
            persona.scratch.act_pronunciatio or "",
            description,
            persona.scratch.chat,
            False,
        )

    async def _move_persona_with_timeout(self, name, persona):
        """Run one persona.move() under its OWN PERSONA_MOVE_TIMEOUT_SECONDS (5b).

        On timeout the move task is cancelled+awaited (no leaked task) and the
        persona's FULL action/conversation decision state is rolled back to the
        pre-step snapshot — not just curr_tile/planned_path — so a partially
        applied action (e.g. chatting_with/chat/act_address) can't poison the
        next step. Returns (next_tile, pronunciatio, description, had_llm_call),
        the continue-current-action fallback on timeout. Used by BOTH the parallel
        batch and the sequential-encounter path so neither can hang the step.
        """
        snap = persona.scratch.snapshot_action_state()
        move_task = asyncio.ensure_future(
            persona.move(
                self.maze,
                self.personas,
                self.personas_tile,
                self.personas_tile[name],
                self.curr_time,
            )
        )
        try:
            return await asyncio.wait_for(
                move_task, timeout=PERSONA_MOVE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            # wait_for already requested cancellation; await so it unwinds (no
            # pending/leaked task, no "Task was destroyed but pending" warning).
            try:
                await move_task
            except (asyncio.CancelledError, Exception):
                pass
            persona.scratch.restore_action_state(snap)
            cli.print_error(
                f"Persona '{name}' move timed out after "
                f"{PERSONA_MOVE_TIMEOUT_SECONDS:.0f}s; continuing current action."
            )
            fb = self._fallback_persona_move_result(name, persona)
            # fb = (name, tile, pronunciatio, description, chat, had_llm_call)
            return fb[1], fb[2], fb[3], fb[5]

    def _movement_step(self, movement: dict) -> int:
        """Return a movement packet step, or -1 for malformed packets."""
        try:
            return int(movement.get("meta", {}).get("step", -1))
        except (TypeError, ValueError):
            return -1

    def _record_movement(self, movements: dict):
        """Record a movement packet for live clients and refresh recovery."""
        with self._movements_lock:
            self._pending_movements.append(movements)
            # Cap the pending queue too: with no browser attached (headless/CLI
            # runs) nothing ever drains it, and an unbounded list of full packets
            # slowly eats RAM. History (below) remains the catch-up source, so a
            # late-joining client loses nothing within the history window.
            if len(self._pending_movements) > self._movement_history_limit:
                overflow = (
                    len(self._pending_movements) - self._movement_history_limit
                )
                del self._pending_movements[:overflow]
            self._movement_history.append(movements)
            if len(self._movement_history) > self._movement_history_limit:
                overflow = len(self._movement_history) - self._movement_history_limit
                del self._movement_history[:overflow]
        if hasattr(self, "personas_tile") and hasattr(self, "maze") and hasattr(
            self, "sim_code"
        ):
            # Derive the step from the movement packet (captured before the step
            # counter was incremented) and use it for BOTH snapshots so the
            # environment and movement files for a step always agree — reading
            # self.step here raced/skewed the env file ahead by one (TOCTOU).
            step = self._movement_step(movements)
            if step >= 0:
                self._write_environment_snapshot(step)
                self._write_movement_snapshot(movements, step)

    def _write_movement_snapshot(self, movements: dict, step: int):
        """Persist the full per-step movement packet so a finished run can be compressed
        into a replayable master_movement.json (offline, LLM-free smooth playback)."""
        if step < 0:
            return
        move_dir = f"{fs_storage}/{self.sim_code}/movement"
        os.makedirs(move_dir, exist_ok=True)
        _atomic_write_json(f"{move_dir}/{step}.json", movements)

    def _write_environment_snapshot(self, step: int):
        """Persist current persona tiles so refreshed browsers start in sync."""
        if step < 0:
            return
        env_dir = f"{fs_storage}/{self.sim_code}/environment"
        os.makedirs(env_dir, exist_ok=True)
        snapshot = {
            name: {"maze": self.maze.maze_name, "x": tile[0], "y": tile[1]}
            for name, tile in self.personas_tile.items()
        }
        _atomic_write_json(f"{env_dir}/{step}.json", snapshot)

    def _refresh_town_center_feedback(self) -> None:
        """Write each persona's recent Town Center request outcomes onto its scratch so
        the step prompt can surface them and the agent learns from approvals/rejections."""
        for persona in self.personas.values():
            try:
                recent = self.town_center.recent_requests_for(persona.name, limit=3)
            except Exception:
                recent = []
            lines = []
            for r in recent:
                state = str(r.get("current_state", "proposed")).upper()
                line = f'- "{r.get("title", "request")}" -> {state}'
                note = r.get("last_note")
                if note:
                    line += f" (reviewer note: {note})"
                lines.append(line)
            persona.scratch.town_center_feedback = (
                "Outcomes of your recent Town Center requests:\n" + "\n".join(lines)
                if lines
                else ""
            )

            # Coordination: surface what TEAMMATES recently produced so work can
            # pipeline (research -> offer -> outreach) instead of each agent acting
            # in isolation. Titles are agent-authored, so render sanitized.
            try:
                team = self.town_center.recent_team_deliverables(persona.name, limit=4)
            except Exception:
                team = []
            tlines = []
            for r in team:
                st = str(r.get("current_state", "proposed")).upper()
                actor = str(r.get("actor", "?"))
                title = str(r.get("title", "work"))
                tlines.append(f'- {actor}: "{title}" [{st}]')
            persona.scratch.team_activity = "\n".join(tlines)

    def _feed_tool_result_to_persona(self, persona, result: dict | None) -> None:
        """Store an executed tool's result as an observation in the persona's
        associative memory (Stage 1), so real outcomes ground future decisions.

        `result` is the sanitized ToolResult dict; best-effort and never fatal.
        """
        if not persona or not isinstance(result, dict):
            return
        summary = str(result.get("summary") or "").strip()
        if not summary:
            return
        try:
            created = self.curr_time
            expiration = created + datetime.timedelta(days=30)
            tool = str(result.get("tool") or "tool")
            desc = summary if summary.lower().startswith(tool.lower()) else f"{tool}: {summary}"
            persona.a_mem.add_event(
                created,
                expiration,
                persona.name,
                "received result of",
                tool,
                desc,
                {"tool", "result", tool.lower().replace(" ", "_")},
                5,
                desc,
                [],
            )
        except Exception as e:
            self._log_safe(f"  tool-result memory feed failed: {e}", error=True)

    def _submit_latest_town_request(
        self, persona_name: str, submitted_town_requests: list[dict]
    ) -> dict | None:
        persona = self.personas.get(persona_name)
        if not persona:
            return None

        sim_time = self.curr_time.strftime("%B %d, %Y, %H:%M:%S")
        request_entry = submit_latest_town_request(
            self.town_center,
            actor=persona_name,
            persona=persona,
            event_ledger=self.event_ledger,
            step=self.step,
            sim_time=sim_time,
        )
        if not request_entry:
            return None

        # Stage 1: ground the persona in the real outcome of an executed (safe)
        # tool, so the result feeds future retrieval/decisions instead of vanishing.
        self._feed_tool_result_to_persona(persona, request_entry.get("tool_result"))

        summary = {
            "id": request_entry["id"],
            "actor": request_entry["actor"],
            "type": request_entry["type"],
            "title": request_entry["title"],
            "approval_required": request_entry.get("approval_required", True),
        }
        submitted_town_requests.append(summary)
        cli.print_info(
            f"  Town Center request: {persona_name} -> {request_entry['title']}"
        )
        state = str(request_entry.get("current_state") or request_entry.get("state") or "proposed")
        needs_approval = request_entry.get("approval_required", True) and state == "proposed"
        self.feed_event(
            "request_submitted",
            f"{persona_name} filed: {request_entry['title']}"
            + (" — NEEDS YOUR APPROVAL" if needs_approval else f" [{state}]"),
            personas=[persona_name],
            tile=self.personas_tile.get(persona_name),
        )
        return request_entry

    def _detect_new_encounters(self) -> list[tuple[str, str]]:
        """
        Detect pairs of personas who are seeing each other for the first time.

        A "new encounter" is when:
        1. Both personas are within vision range of each other
        2. Neither has acknowledged the other yet (not in _acknowledged_nearby)
        3. Neither is already in a conversation

        Returns:
            List of (persona_a, persona_b) tuples representing new encounter pairs.
        """
        new_encounters = []
        checked_pairs = set()

        # Iterate over all persona pairs directly using authoritative positions
        persona_names = list(self.personas.keys())
        for i, name_a in enumerate(persona_names):
            persona_a = self.personas[name_a]

            # Skip if already in conversation
            if persona_a.scratch.chatting_with:
                continue

            tile_a = self.personas_tile.get(name_a)
            if not tile_a:
                continue

            for name_b in persona_names[i + 1 :]:
                persona_b = self.personas[name_b]

                # Skip if B is already in conversation
                if persona_b.scratch.chatting_with:
                    continue

                tile_b = self.personas_tile.get(name_b)
                if not tile_b:
                    continue

                # Check distance (Chebyshev)
                dist = max(abs(tile_a[0] - tile_b[0]), abs(tile_a[1] - tile_b[1]))
                if dist > persona_a.scratch.vision_r:
                    continue

                # Check line of sight
                if not self.maze.has_line_of_sight(tile_a, tile_b):
                    continue

                # Create sorted pair to avoid duplicates
                pair = tuple(sorted([name_a, name_b]))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)

                # Check if this is a NEW encounter for BOTH personas
                # (neither has acknowledged the other yet)
                a_knows_b = any(
                    nearby[0] == name_b for nearby in persona_a._acknowledged_nearby
                )
                b_knows_a = any(
                    nearby[0] == name_a for nearby in persona_b._acknowledged_nearby
                )

                if not a_knows_b and not b_knows_a:
                    # Debug: log the encounter detection with positions
                    cli.print_info(
                        f"  [DEBUG] New encounter detected: {name_a} @ {tile_a} <-> "
                        f"{name_b} @ {tile_b} (dist: {dist}, LOS: checked)"
                    )
                    new_encounters.append(pair)

        return new_encounters

    @staticmethod
    def _disjoint_encounter_pairs(
        encounter_pairs: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        """Keep at most ONE pair per persona (first wins, input order).

        Three personas meeting at once yields (A,B), (A,C), (B,C); running all
        of them would move A and B twice in one step (double LLM call, second
        result silently overwriting the first). The dropped pair members still
        acknowledge each other through normal perception on the next step.
        """
        claimed: set[str] = set()
        disjoint: list[tuple[str, str]] = []
        for pair in encounter_pairs:
            if pair[0] in claimed or pair[1] in claimed:
                cli.print_info(
                    f"  Encounter {pair} deferred (member already in an encounter)"
                )
                continue
            claimed.update(pair)
            disjoint.append(pair)
        return disjoint

    async def _run_encounter_pair(self, pair: tuple[str, str]) -> list:
        """
        Run ONE new-encounter pair with the initiative system.

        1. Determine who has initiative (alphabetical, flipped on odd steps)
        2. Run initiative holder's move first
        3. If they didn't initiate conversation, run the other with context
        4. If they did initiate, the other will respond naturally next step

        Returns a list of move-result tuples (1-2 entries), or [exception].
        """
        results = []
        name_a, name_b = pair  # Already sorted alphabetically

        # Flip initiative on odd steps so it's not always the same person
        if self.step % 2 == 0:
            first, second = name_a, name_b
        else:
            first, second = name_b, name_a

        cli.print_info(f"  New encounter: {first} has initiative over {second}")

        # Run first persona's move
        persona_first = self.personas[first]
        try:
            (
                next_tile,
                pronunciatio,
                description,
                had_llm_call,
            ) = await self._move_persona_with_timeout(first, persona_first)
            results.append(
                (
                    first,
                    next_tile,
                    pronunciatio,
                    description,
                    persona_first.scratch.chat,
                    had_llm_call,
                )
            )

            # Check if first persona initiated conversation with second
            first_initiated = (
                persona_first.scratch.chatting_with == second
                and persona_first.scratch.chat
            )

            if first_initiated:
                # First initiated - DON'T run second's move this step
                # Second will respond naturally on the NEXT step when they
                # detect the unheard dialogue via _has_unheard_dialogue
                cli.print_info(
                    f"    {first} initiated → {second} will respond next step"
                )
                # Keep second in place this step (no LLM call) so they don't
                # also run in the parallel batch.
                persona_second = self.personas[second]
                results.append(
                    (
                        second,
                        self.personas_tile[second],  # Stay in place
                        persona_second.scratch.act_pronunciatio or "💭",
                        persona_second.scratch.act_description
                        or f"{second} is idle",
                        persona_second.scratch.chat,
                        False,  # No LLM call
                    )
                )
            else:
                # First declined - give second the knowledge and let them decide
                # Add context that first saw them but didn't initiate
                persona_second = self.personas[second]
                persona_second._encounter_context = (
                    f"{first} noticed you but didn't start a conversation"
                )

                # Run second persona's move
                (
                    next_tile_2,
                    pronunciatio_2,
                    description_2,
                    had_llm_call_2,
                ) = await self._move_persona_with_timeout(second, persona_second)
                results.append(
                    (
                        second,
                        next_tile_2,
                        pronunciatio_2,
                        description_2,
                        persona_second.scratch.chat,
                        had_llm_call_2,
                    )
                )

                # Clear the encounter context
                if hasattr(persona_second, "_encounter_context"):
                    delattr(persona_second, "_encounter_context")

        except Exception as e:
            cli.print_error(f"Error in sequential encounter {pair}: {e}")
            import traceback

            traceback.print_exc()
            results.append(e)

        return results

    async def _run_sequential_encounters(
        self, encounter_pairs: list[tuple[str, str]]
    ) -> list:
        """
        Run new-encounter pairs CONCURRENTLY across pairs (pairs are made
        persona-disjoint first), while keeping the within-pair initiative
        sequence. Previously pairs ran one-after-another, so step latency grew
        linearly with the number of simultaneous encounters (~2 LLM calls each).

        Returns:
            Flat list of move results for all personas in encounter pairs.
        """
        disjoint = self._disjoint_encounter_pairs(encounter_pairs)
        if not disjoint:
            return []
        per_pair = await asyncio.gather(
            *(self._run_encounter_pair(pair) for pair in disjoint)
        )
        return [item for pair_results in per_pair for item in pair_results]

    def _synchronize_conversations(self):
        """
        Synchronize chat histories between personas who are in conversation.

        After all personas have moved in parallel, this method:
        1. Removes participants who have moved out of range
        2. Manages ConversationGroup objects for multi-party conversations
        3. Detects conversations and groups participants together (with proximity checks)
        4. Merges chat lines so all participants see the full conversation
        5. Stores completed conversations in all participants' memories

        This is critical because personas run in parallel and don't see each
        other's dialogue responses within a single simulation step.
        """
        # Perception range for initiating conversations (must see target) = vision_r = 4
        # Delivery range is slightly larger to account for movement during parallel execution.
        # A persona decides to talk based on their position when LLM was called, but
        # validation happens after moves complete - both parties may have moved 1 tile.
        CONVERSATION_DELIVERY_RANGE = 6

        def can_converse(tile1, tile2) -> bool:
            """Check if two tiles are within conversation delivery range AND have line of sight."""
            if not tile1 or not tile2:
                return False
            if _tile_distance(tile1, tile2) > CONVERSATION_DELIVERY_RANGE:
                return False
            return self.maze.has_line_of_sight(tile1, tile2)

        # Step 0: Collect who is actively chatting FIRST, before any range checks
        # We need this to know who's still engaged before deciding to kick anyone
        active_chatters_quick = set()  # Names of personas who are actively talking
        for name, persona in self.personas.items():
            if persona.scratch.chatting_with and persona.scratch.chat:
                active_chatters_quick.add(name)

        # Step 0b: Remove out-of-range participants from existing groups
        # BUT only if they're not actively chatting (still engaged in conversation)
        for group_id, group in list(self.active_conversations.items()):
            if len(group.participants) < 2:
                continue

            # Find participants who are no longer within range of ANY other participant
            to_remove = []
            for participant in group.participants:
                if participant not in self.personas:
                    to_remove.append(participant)
                    continue

                # If this participant is actively chatting this step, don't remove them
                # They're still engaged even if positions shifted during parallel execution
                if participant in active_chatters_quick:
                    continue

                my_tile = self.personas_tile.get(participant)

                # Check if this participant is within extended range of at least one other
                has_nearby_partner = False
                for other in group.participants:
                    if other == participant or other not in self.personas:
                        continue
                    other_tile = self.personas_tile.get(other)
                    if can_converse(my_tile, other_tile):
                        has_nearby_partner = True
                        break

                if not has_nearby_partner:
                    to_remove.append(participant)

            # Remove out-of-range participants and end their conversation
            for participant in to_remove:
                if participant in self.personas:
                    persona = self.personas[participant]
                    cli.print_info(
                        f"  {participant} left conversation [{group_id}] (moved out of range)"
                    )
                    self._end_and_store_conversation(persona)
                    persona.scratch.conversation_group_id = None
                group.remove_participant(participant)

        # Step 1: Build mapping of persona -> existing group from scratch
        # This ensures we reuse existing groups instead of creating new ones
        persona_to_group: dict[str, str] = {}
        for name, persona in self.personas.items():
            group_id = persona.scratch.conversation_group_id
            if group_id and group_id in self.active_conversations:
                persona_to_group[name] = group_id

        # Step 2: Collect all active conversationalists and their chat lines
        active_chatters = {}  # {name: (partner, chat_lines)}
        for name, persona in self.personas.items():
            if persona.scratch.chatting_with and persona.scratch.chat:
                active_chatters[name] = (
                    persona.scratch.chatting_with,
                    persona.scratch.chat or [],
                )

        # Detect mutual encounters (both greeted each other on same step)
        # This indicates the sequential initiative system didn't prevent it
        # (could happen if both were already in motion or edge cases)
        # Just log it - both lines will be merged and conversation continues normally
        mutual_encounters = set()
        for name, (partner, _) in active_chatters.items():
            if partner in active_chatters and active_chatters[partner][0] == name:
                pair = tuple(sorted([name, partner]))
                if pair not in mutual_encounters:
                    mutual_encounters.add(pair)
                    cli.print_info(f"  Mutual greeting: {name} <-> {partner}")

        # Step 3: Find or create conversation groups (with proximity validation)
        for name, (partner, chat_lines) in active_chatters.items():
            group = None
            group_id = None
            my_tile = self.personas_tile.get(name)

            # Check if this persona is already in a group
            if name in persona_to_group:
                group_id = persona_to_group[name]
                group = self.active_conversations.get(group_id)

            # Check if partner is already in a group we should join
            # Trust the LLM's decision - it validated proximity when deciding to talk
            if not group and partner in persona_to_group:
                group_id = persona_to_group[partner]
                group = self.active_conversations.get(group_id)
                if group:
                    group.add_participant(name)
                    persona_to_group[name] = group_id
                    # Update persona's group reference
                    self.personas[name].scratch.conversation_group_id = group_id

            # Create new group if neither is in one
            if not group:
                # Trust the LLM's decision to initiate - it validated proximity when deciding
                # Don't re-check distance here as positions may have changed during parallel execution
                group = ConversationGroup(
                    participants={name},
                    location_tile=self.personas_tile.get(name, (0, 0)),
                    started_at=self.curr_time,
                )
                self.active_conversations[group.id] = group
                persona_to_group[name] = group.id
                group_id = group.id
                # Update persona's group reference
                self.personas[name].scratch.conversation_group_id = group_id
                self.feed_event(
                    "conversation_started",
                    f"{name} started talking with {partner}",
                    personas=[name, partner],
                    tile=my_tile,
                )

            # Add all conversation targets to group (supports multi-target/broadcast)
            # chatting_with_buffer contains all targets from persona's social decision
            all_targets = set()
            if partner:
                all_targets.add(partner)
            # Also add anyone from the chatting_with_buffer (for multi-target)
            if self.personas[name].scratch.chatting_with_buffer:
                all_targets.update(
                    self.personas[name].scratch.chatting_with_buffer.keys()
                )

            for target in all_targets:
                if target in self.personas and target not in group.participants:
                    target_tile = self.personas_tile.get(target)
                    if can_converse(my_tile, target_tile):
                        group.add_participant(target)
                        persona_to_group[target] = group_id
                        # Update target's group reference
                        self.personas[target].scratch.conversation_group_id = group_id

            # Merge this persona's chat lines into the group
            group.merge_lines(chat_lines, self.curr_time)

        # Step 4: Synchronize all group members' chat lists
        for group_id, group in list(self.active_conversations.items()):
            if len(group.participants) < 2:
                continue

            # Get the full merged chat from the group
            full_chat = group.chat

            # Update each participant's scratch with the full conversation
            for participant_name in list(group.participants):
                if participant_name not in self.personas:
                    continue

                persona = self.personas[participant_name]
                persona.scratch.merge_chat_lines(full_chat)
                # Ensure group reference is set
                persona.scratch.conversation_group_id = group_id

                # If they weren't in a conversation, set them up
                if not persona.scratch.chatting_with:
                    # Pick the nearest other participant as their "chatting_with"
                    my_tile = self.personas_tile.get(participant_name)
                    others = [p for p in group.participants if p != participant_name]
                    # Sort by distance to pick nearest
                    others.sort(
                        key=lambda p: _tile_distance(my_tile, self.personas_tile.get(p))
                    )
                    if others:
                        persona.scratch.chatting_with = others[0]
                        persona.scratch.chat = list(full_chat)
                        persona.scratch.chatting_with_buffer = {
                            p: persona.scratch.vision_r for p in others
                        }
                        if group.end_time:
                            persona.scratch.chatting_end_time = group.end_time
                        else:
                            persona.scratch.chatting_end_time = (
                                self.curr_time + datetime.timedelta(minutes=5)
                            )

            # Debug output
            cli.print_info(
                f"  Conversation group [{group.id}]: "
                f"{group.get_participants_str()} ({len(group.chat)} lines)"
            )

        # Step 5: Handle one-sided conversations (A talks to B, B hasn't responded)
        # Validate proximity before delivering - LLM may hallucinate nearby personas
        for name, (partner, chat_lines) in active_chatters.items():
            if partner not in self.personas:
                continue

            persona_a = self.personas[name]
            persona_b = self.personas[partner]

            # Validate partner is actually within conversation delivery range
            tile_a = self.personas_tile.get(name)
            tile_b = self.personas_tile.get(partner)
            if not _are_within_range(tile_a, tile_b, CONVERSATION_DELIVERY_RANGE):
                cli.print_warning(
                    f"  {name} tried to talk to {partner} but they're "
                    f"not nearby (distance: {_tile_distance(tile_a, tile_b):.0f} tiles) - ignoring"
                )
                # Clear A's conversation state since target isn't reachable
                persona_a.scratch.chatting_with = None
                persona_a.scratch.chat = None
                persona_a.scratch.chatting_with_buffer = {}
                continue

            # If B isn't chatting yet, set them up to receive and respond
            if not persona_b.scratch.chatting_with and chat_lines:
                persona_b.scratch.chatting_with = name
                persona_b.scratch.chat = []
                persona_b.scratch.merge_chat_lines(chat_lines)
                persona_b.scratch.chatting_with_buffer = {
                    name: persona_b.scratch.vision_r
                }

                if persona_a.scratch.chatting_end_time:
                    persona_b.scratch.chatting_end_time = (
                        persona_a.scratch.chatting_end_time
                    )
                else:
                    persona_b.scratch.chatting_end_time = (
                        self.curr_time + datetime.timedelta(minutes=5)
                    )

                # Also add B to the conversation group so it's properly tracked
                if name in persona_to_group:
                    group_id = persona_to_group[name]
                    group = self.active_conversations.get(group_id)
                    if group and partner not in group.participants:
                        group.add_participant(partner)
                        persona_to_group[partner] = group_id
                        persona_b.scratch.conversation_group_id = group_id

                cli.print_info(
                    f"  Initiated conversation: {name} -> {partner} "
                    f"({len(chat_lines)} lines shared)"
                )

        # Step 6: Check for conversations that have ended (by time)
        # Each person ends individually - others can still respond before they also end
        # This allows farewell exchanges where both parties can say goodbye
        ended_groups = []
        for name, persona in self.personas.items():
            scratch = persona.scratch
            if scratch.chatting_end_time and scratch.curr_time:
                if scratch.curr_time >= scratch.chatting_end_time:
                    group_id = scratch.conversation_group_id
                    group = (
                        self.active_conversations.get(group_id) if group_id else None
                    )

                    # End just for this persona - remove them from the group
                    # Others can still respond; group cleaned up when empty
                    self._end_and_store_conversation(persona)
                    scratch.conversation_group_id = None

                    if group:
                        group.remove_participant(name)
                        # If only one person left, they can still send one more message
                        # Group will be cleaned up in Step 7 when it becomes empty/stale

        # Step 7: Clean up orphaned, single-participant, or stale groups
        STALE_THRESHOLD = 5  # Auto-end after 5 steps of no new messages
        for group_id, group in list(self.active_conversations.items()):
            if group_id in ended_groups:
                continue  # Already marked for deletion

            # Increment stale counter for groups with no new activity
            group.stale_steps += 1

            # Remove individual participants who have stopped chatting
            # (their chatting_with is now None, meaning they started a different action)
            inactive_participants = []
            for participant in list(group.participants):
                if participant in self.personas:
                    scratch = self.personas[participant].scratch
                    if not scratch.chatting_with:
                        inactive_participants.append(participant)

            for participant in inactive_participants:
                self._end_and_store_conversation(self.personas[participant])
                self.personas[participant].scratch.conversation_group_id = None
                group.remove_participant(participant)

            # Clean up single-participant groups (everyone else left)
            if len(group.participants) < 2:
                ended_groups.append(group_id)
                for participant in list(group.participants):
                    if participant in self.personas:
                        self._end_and_store_conversation(self.personas[participant])
                        self.personas[participant].scratch.conversation_group_id = None
                continue

            # Auto-end stale conversations (no new messages for too long)
            if group.stale_steps >= STALE_THRESHOLD:
                cli.print_info(
                    f"  Auto-ending stale conversation [{group_id}] "
                    f"({group.stale_steps} steps inactive)"
                )
                ended_groups.append(group_id)
                for participant in list(group.participants):
                    if participant in self.personas:
                        self._end_and_store_conversation(self.personas[participant])
                        self.personas[participant].scratch.conversation_group_id = None
                continue

        # Clean up ended conversation groups
        for group_id in ended_groups:
            group = self.active_conversations.get(group_id)
            if group is not None:
                participants = sorted(group.participants)
                self.feed_event(
                    "conversation_ended",
                    f"Conversation ended: {', '.join(participants)}",
                    personas=participants,
                    tile=getattr(group, "location_tile", None),
                )
                del self.active_conversations[group_id]

    def _end_and_store_conversation(self, persona):
        """
        End a conversation and store it in the persona's associative memory.

        Called when chatting_end_time has been reached.
        """
        partner, chat_lines = persona.scratch.end_conversation()
        if not partner or not chat_lines:
            return

        # Build a description of the conversation
        num_lines = len(chat_lines)
        description = f"Conversation with {partner} ({num_lines} exchanges)"

        # Create keywords from the conversation
        keywords = set([partner.lower(), "conversation", "chat"])
        for speaker, line in chat_lines:
            # Add speaker names as keywords
            keywords.add(speaker.lower())
            # Add key words from the conversation (simplified)
            words = line.lower().split()[:5]
            keywords.update(w for w in words if len(w) > 3)

        # Store in associative memory
        created = persona.scratch.curr_time
        expiration = created + datetime.timedelta(days=30)
        s = persona.scratch.name
        p = "chat with"
        o = partner

        # Calculate poignancy based on conversation length
        poignancy = min(5 + num_lines, 10)

        persona.a_mem.add_chat(
            created=created,
            expiration=expiration,
            s=s,
            p=p,
            o=o,
            description=description,
            keywords=keywords,
            poignancy=poignancy,
            embedding_key=description,
            filling=chat_lines,
        )

        # Phase 3: update this persona's relationship model from the real
        # interaction. Heuristic (no LLM, no embeddings - D-002): bump
        # familiarity, nudge affinity, extract a topic gist. We update toward
        # every OTHER speaker in the chat so multi-party conversations register
        # for all participants, not just the primary partner.
        r_mem = getattr(persona, "r_mem", None)
        if r_mem is not None:
            others = {partner}
            for entry in chat_lines:
                if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                    speaker = entry[0]
                    if speaker and speaker != s:
                        others.add(speaker)
            for other in others:
                if other:
                    r_mem.note_from_chat(other, chat_lines, when=created)

        # Phase 4a: capture commitments this persona MADE during the conversation
        # into multi-day goal memory (heuristic, keyword-only — D-002, no LLM, no
        # embeddings) so a promise like "I'll help you tomorrow" outlives the day.
        g_mem = getattr(persona, "g_mem", None)
        if g_mem is not None:
            try:
                promises = g_mem.capture_promises_from_chat(
                    s, chat_lines, partner=partner, when=created
                )
                if promises:
                    cli.print_info(
                        f"  {s}: captured {len(promises)} promise(s) -> goal memory"
                    )
            except Exception as exc:  # promise capture must never break a step
                cli.print_error(f"  promise capture failed for {s}: {exc}")

        cli.print_info(f"  Stored conversation: {s} <-> {partner} ({num_lines} lines)")

    def _autosim_loop(self):
        """Background producer for smooth playback: simulate steps ahead of the
        displayed step, capped by the buffer-ahead window. Pauses when nobody is
        polling so it never burns LLM calls on an idle/closed tab."""
        while not self._stop_autosim.is_set():
            if not self._autosim_enabled.is_set():
                time.sleep(0.2)
                continue
            # cost guard: only produce while a client is actively polling
            now = time.monotonic()
            if (
                self._last_poll_at == 0.0
                or (now - self._last_poll_at) > self._autosim_idle_pause_s
            ):
                time.sleep(0.3)
                continue
            # backpressure: stop if already buffer_ahead steps ahead of the display
            if (self.step - 1 - self._displayed_step) >= self._buffer_ahead:
                time.sleep(0.1)
                continue
            environment = {}
            for persona_name in self.personas:
                tile = self.personas_tile[persona_name]
                environment[persona_name] = {"x": tile[0], "y": tile[1]}
            try:
                self._process_step({"environment": environment})
                # Periodic auto-save so unattended autosim runs persist memory
                # (the lock is free here — _process_step has released it).
                self._maybe_autosave()
            except Exception as e:
                cli.print_error(f"autosim step failed: {e}")
                time.sleep(0.5)

    def start_autosim(self):
        """Launch the background producer thread (HTTP mode)."""
        if os.environ.get("CLAUDEVILLE_AUTOSIM", "1") == "0":
            cli.print_info("autosim disabled (CLAUDEVILLE_AUTOSIM=0)")
            return
        self._autosim_enabled.set()
        self.autosim_thread = threading.Thread(target=self._autosim_loop, daemon=True)
        self.autosim_thread.start()
        cli.print_info(
            f"autosim producer started (buffer_ahead={self._buffer_ahead}, "
            f"min_fill={self._autosim_min_fill})"
        )

    def start_http_server(self):
        """Start the Flask HTTP server in a background thread."""
        import logging
        import sys

        # Suppress Flask/Werkzeug output completely
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)
        log.disabled = True

        # Redirect Flask's startup message to devnull
        cli_module = sys.modules.get("flask.cli")
        if cli_module:
            cli_module.show_server_banner = lambda *args, **kwargs: None

        def run_flask():
            # Werkzeug logging + the flask.cli banner are silenced above; do NOT
            # redirect sys.stderr here — it is process-global, so doing so used to
            # swallow every traceback from every thread for the life of the run
            # (including a port-bind failure, leaving a silently dead HTTP server).
            try:
                self.flask_app.run(
                    host="127.0.0.1",
                    port=BACKEND_PORT,
                    threaded=True,
                    use_reloader=False,
                )
            except OSError as exc:
                self._log_safe(
                    f"HTTP server failed to start on :{BACKEND_PORT} ({exc}) — "
                    "is another instance running?",
                    error=True,
                )

        self.flask_thread = threading.Thread(target=run_flask, daemon=True)
        self.flask_thread.start()
        cli.print_info(f"HTTP server started on http://127.0.0.1:{BACKEND_PORT}")

    @staticmethod
    def _log_safe(message: str, error: bool = False) -> None:
        """Print via cli but never raise — guards against non-UTF-8 stdout
        (cp1252) choking on the banner glyphs, so logging can't break a run."""
        try:
            (cli.print_error if error else cli.print_info)(message)
        except Exception:
            pass

    def _should_autosave(self, step: int) -> bool:
        """True when a periodic auto-save is due (pure; unit-testable).

        Fires once at least ``_autosave_every_steps`` steps have elapsed since the
        last auto-save; ``0`` disables. Uses an elapsed-since comparison (not an
        exact modulo) so it is robust to any step that isn't a clean multiple.
        """
        every = getattr(self, "_autosave_every_steps", 0)
        if every <= 0:
            return False
        return (step - getattr(self, "_last_autosave_step", 0)) >= every

    def _maybe_autosave(self, force: bool = False) -> None:
        """Best-effort periodic save so long/unattended runs persist memory.

        A save failure must NEVER kill a run, so the whole thing is guarded. The
        save is serialized against stepping via ``_step_lock`` (mirroring the
        /save route, ARCH-4); callers must invoke this only when they do NOT
        already hold the lock (between steps), which both call sites satisfy.
        """
        if not force and not self._should_autosave(self.step):
            return
        lock = getattr(self, "_step_lock", None)
        try:
            if lock is not None:
                lock.acquire()
            try:
                self.save()
                self._last_autosave_step = self.step
            finally:
                if lock is not None:
                    lock.release()
        except Exception as e:
            self._log_safe(f"auto-save failed at step {self.step}: {e}", error=True)
            return
        self._log_safe(f"  auto-saved at step {self.step}")
        self.feed_event("autosave", f"Progress auto-saved at step {self.step}")

    def save(self):
        """
        Save all Reverie progress -- this includes Reverie's global state as well
        as all the personas.

        INPUT
          None
        OUTPUT
          None
          * Saves all relevant data to the designated memory directory
        """
        # <sim_folder> points to the current simulation folder.
        sim_folder = f"{fs_storage}/{self.sim_code}"

        # Save Reverie meta information.
        reverie_meta = dict()
        reverie_meta["fork_sim_code"] = self.fork_sim_code
        reverie_meta["start_date"] = self.start_time.strftime("%B %d, %Y")
        reverie_meta["curr_time"] = self.curr_time.strftime("%B %d, %Y, %H:%M:%S")
        reverie_meta["sec_per_step"] = self.sec_per_step
        reverie_meta["maze_name"] = self.maze.maze_name
        reverie_meta["persona_names"] = list(self.personas.keys())
        reverie_meta["step"] = self.step
        # Save persona positions directly in meta (avoids needing environment files)
        reverie_meta["persona_tiles"] = {
            name: list(tile) for name, tile in self.personas_tile.items()
        }
        # Atomic write: meta.json is the one file the loader hard-requires — a
        # crash mid-save must never leave it torn (same writer as movement/env).
        reverie_meta_f = f"{sim_folder}/reverie/meta.json"
        _atomic_write_json(reverie_meta_f, reverie_meta)

        # Save the personas.
        for persona_name, persona in self.personas.items():
            save_folder = f"{sim_folder}/personas/{persona_name}/bootstrap_memory"
            persona.save(save_folder)

    def start_path_tester_server(self):
        """
        Starts the path tester server. This is for generating the spatial memory
        that we need for bootstrapping a persona's state.

        To use this, you need to open server and enter the path tester mode, and
        open the front-end side of the browser.

        INPUT
          None
        OUTPUT
          None
          * Saves the spatial memory of the test agent to the path_tester_env.json
            of the temp storage.
        """

        def print_tree(tree):
            def _print_tree(tree, depth):
                dash = " >" * depth

                if isinstance(tree, list):
                    if tree:
                        print(dash, tree)
                    return

                for key, val in tree.items():
                    if key:
                        print(dash, key)
                    _print_tree(val, depth + 1)

            _print_tree(tree, 0)

        # <curr_vision> is the vision radius of the test agent. Recommend 8 as
        # our default.
        curr_vision = 8
        # <s_mem> is our test spatial memory.
        s_mem = dict()

        # The main while loop for the test agent.
        while True:
            try:
                curr_dict = {}
                tester_file = fs_temp_storage + "/path_tester_env.json"
                if os.path.exists(tester_file):
                    with open(tester_file) as json_file:
                        curr_dict = json.load(json_file)
                        os.remove(tester_file)

                    # Current camera location
                    curr_sts = self.maze.sq_tile_size
                    curr_camera = (
                        int(math.ceil(curr_dict["x"] / curr_sts)),
                        int(math.ceil(curr_dict["y"] / curr_sts)) + 1,
                    )
                    curr_tile_det = self.maze.access_tile(curr_camera)

                    # Initiating the s_mem
                    world = curr_tile_det["world"]
                    if curr_tile_det["world"] not in s_mem:
                        s_mem[world] = dict()

                    # Iterating throughn the nearby tiles.
                    nearby_tiles = self.maze.get_nearby_tiles(curr_camera, curr_vision)
                    for i in nearby_tiles:
                        i_det = self.maze.access_tile(i)
                        if (
                            curr_tile_det["sector"] == i_det["sector"]
                            and curr_tile_det["arena"] == i_det["arena"]
                        ):
                            if i_det["sector"] != "":
                                if i_det["sector"] not in s_mem[world]:
                                    s_mem[world][i_det["sector"]] = dict()
                            if i_det["arena"] != "":
                                if i_det["arena"] not in s_mem[world][i_det["sector"]]:
                                    s_mem[world][i_det["sector"]][
                                        i_det["arena"]
                                    ] = list()
                            if i_det["game_object"] != "":
                                if (
                                    i_det["game_object"]
                                    not in s_mem[world][i_det["sector"]][i_det["arena"]]
                                ):
                                    s_mem[world][i_det["sector"]][i_det["arena"]] += [
                                        i_det["game_object"]
                                    ]

                # Incrementally outputting the s_mem and saving the json file.
                print("= " * 15)
                out_file = fs_temp_storage + "/path_tester_out.json"
                with open(out_file, "w") as outfile:
                    outfile.write(json.dumps(s_mem, indent=2))
                print_tree(s_mem)

            except Exception:
                pass

            time.sleep(self.server_sleep * 10)

    def run_steps(self, num_steps):
        """
        Run the simulation for a given number of steps (CLI mode).

        This runs the cognitive pipeline directly. Movements are queued
        for the frontend to poll and display.

        INPUT
          num_steps: Number of simulation steps to run
        OUTPUT
          None
        """
        for i in range(num_steps):
            # Print step header
            cli.print_step_start(self.step, self.curr_time)

            # Build environment data from current backend state
            environment = {}
            for persona_name in self.personas:
                tile = self.personas_tile[persona_name]
                environment[persona_name] = {"x": tile[0], "y": tile[1]}

            # Run one step - movements are queued for frontend
            self._process_step({"environment": environment})

            # Periodic auto-save between steps (lock is free here; best-effort).
            self._maybe_autosave()

        # Persist final state at the end of a CLI run so memory is never lost.
        self._maybe_autosave(force=True)

    def open_server(self):
        """
        Open up an interactive terminal prompt that lets you run the simulation
        step by step and probe agent state.
        """
        # Show simulation info
        cli.print_simulation_started(self.sim_code)
        cli.print_sim_info(
            self.sim_code,
            self.fork_sim_code,
            self.curr_time,
            self.step,
            list(self.personas.keys()),
        )

        sim_folder = f"{fs_storage_runs}/{self.sim_code}"

        while True:
            sim_command = cli.get_prompt()
            if not sim_command:
                continue

            try:
                cmd = sim_command.lower().strip()
                parts = sim_command.split()

                # === CONTROL COMMANDS ===
                if cmd in ["f", "fin", "finish", "save", "exit"]:
                    self.save()
                    if cmd != "save":
                        cli.print_success("Simulation saved. Goodbye!")
                        break
                    else:
                        cli.print_success("Simulation saved.")

                elif cmd == "quit":
                    cli.print_warning("Exiting without saving current state...")
                    break

                elif cmd == "discard":
                    cli.print_warning("Discarding simulation and deleting all data...")
                    shutil.rmtree(sim_folder)
                    break

                elif cmd.startswith("run"):
                    if len(parts) < 2:
                        cli.print_error("Usage: run <number_of_steps>")
                        continue
                    try:
                        int_count = int(parts[-1])
                        start_time = time.time()
                        self.run_steps(int_count)
                        elapsed = time.time() - start_time
                        cli.print_run_complete(int_count, elapsed)
                    except ValueError:
                        cli.print_error(f"Invalid step count: {parts[-1]}")

                # === STATUS COMMANDS ===
                elif cmd in ["help", "?"]:
                    cli.print_help()

                elif cmd == "status":
                    cli.print_sim_info(
                        self.sim_code,
                        self.fork_sim_code,
                        self.curr_time,
                        self.step,
                        list(self.personas.keys()),
                    )

                elif cmd == "time":
                    cli.print_info(
                        f"Simulation time: {self.curr_time.strftime('%B %d, %Y, %H:%M:%S')}"
                    )
                    cli.print_info(f"Step: {self.step}")

                elif cmd == "personas":
                    for name in self.personas.keys():
                        persona = self.personas[name]
                        action = persona.scratch.act_description or "idle"
                        cli.print_persona_action(name, action)

                # === PERSONA COMMANDS ===
                elif cmd.startswith("schedule "):
                    name = " ".join(parts[1:])
                    if name in self.personas:
                        print(
                            self.personas[name].scratch.get_str_daily_schedule_summary()
                        )
                    else:
                        cli.print_error(f"Persona '{name}' not found")

                elif cmd.startswith("location "):
                    name = " ".join(parts[1:])
                    if name in self.personas:
                        tile = self.personas[name].scratch.curr_tile
                        addr = self.personas[name].scratch.act_address
                        cli.print_info(f"{name} is at tile {tile}")
                        cli.print_info(f"Location: {addr}")
                    else:
                        cli.print_error(f"Persona '{name}' not found")

                elif cmd.startswith("memory "):
                    name = " ".join(parts[1:])
                    if name in self.personas:
                        p = self.personas[name]
                        cli.print_memory_summary(
                            name,
                            len(p.a_mem.seq_event)
                            if hasattr(p.a_mem, "seq_event")
                            else 0,
                            len(p.a_mem.seq_thought)
                            if hasattr(p.a_mem, "seq_thought")
                            else 0,
                            len(p.a_mem.seq_chat)
                            if hasattr(p.a_mem, "seq_chat")
                            else 0,
                        )
                    else:
                        cli.print_error(f"Persona '{name}' not found")

                elif cmd.startswith("chat "):
                    name = " ".join(parts[1:])
                    if name in self.personas:
                        self.personas[name].open_convo_session("analysis")
                    else:
                        cli.print_error(f"Persona '{name}' not found")

                # === LEGACY COMMANDS (for backwards compatibility) ===
                elif "print persona schedule" in cmd:
                    name = " ".join(parts[-2:])
                    if name in self.personas:
                        print(
                            self.personas[name].scratch.get_str_daily_schedule_summary()
                        )

                elif "print all persona schedule" in cmd:
                    for persona_name, persona in self.personas.items():
                        print(f"\n{persona_name}")
                        print(persona.scratch.get_str_daily_schedule_summary())
                        print("---")

                elif "print current time" in cmd:
                    print(f"{self.curr_time.strftime('%B %d, %Y, %H:%M:%S')}")
                    print(f"steps: {self.step}")

                elif "call -- analysis" in cmd:
                    persona_name = sim_command[len("call -- analysis") :].strip()
                    if persona_name in self.personas:
                        self.personas[persona_name].open_convo_session("analysis")

                elif cmd == "start path tester mode":
                    shutil.rmtree(sim_folder)
                    self.start_path_tester_server()

                else:
                    cli.print_warning(f"Unknown command: {sim_command}")
                    cli.print_info("Type 'help' for available commands")

            except KeyboardInterrupt:
                print()
                continue
            except Exception as e:
                cli.print_error(str(e))
                if debug:
                    traceback.print_exc()


def load_local_config():
    """Load local config from project root (two levels up from this file)."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "local_config.json"
    )
    config_path = os.path.normpath(config_path)
    try:
        with open(config_path) as f:
            return json.load(f), config_path
    except FileNotFoundError:
        # Return default config if file doesn't exist
        return {
            "default_fork": "the_ville_isabella_maria_klaus",
            "last_simulation": None,
        }, config_path


def save_local_config(config, config_path):
    """Save local config to project root."""
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def generate_simulation_name(fork_name):
    """Generate a new simulation name based on fork name + timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{fork_name}_{timestamp}"


if __name__ == "__main__":
    import sys

    # Load local config
    config, config_path = load_local_config()
    default_fork = config.get("default_fork", "the_ville_isabella_maria_klaus")
    last_sim = config.get("last_simulation")

    # Show startup menu
    cli.print_startup_menu(default_fork, last_sim)

    choice = input(cli.c("  > ", cli.Colors.BRIGHT_BLACK)).strip().lower()

    if choice in ["c", "continue"]:
        if not last_sim:
            cli.print_error("No previous simulation to continue.")
            sys.exit(1)
        target = last_sim
        target_folder = f"{fs_storage_runs}/{target}"
        if not os.path.exists(target_folder):
            cli.print_error(f"Simulation '{target}' not found.")
            sys.exit(1)
        # Load the existing simulation's meta to get its fork
        meta_file = f"{target_folder}/reverie/meta.json"
        with open(meta_file) as json_file:
            meta = json.load(json_file)
        origin = meta.get("fork_sim_code", default_fork)
        cli.print_info(f"Continuing: {target}")

    elif choice == "custom":
        # Prompt for fork simulation with default
        print(f"\n  Fork from [{cli.c(default_fork, cli.Colors.CYAN)}]: ", end="")
        origin = input().strip()
        if not origin:
            origin = default_fork

        # Prompt for target simulation with auto-generated default
        auto_target = generate_simulation_name(origin)
        print(f"  New name [{cli.c(auto_target, cli.Colors.GREEN)}]: ", end="")
        target = input().strip()
        if not target:
            target = auto_target

    else:
        # Default: start new simulation with auto-generated name
        origin = default_fork
        target = generate_simulation_name(origin)

    # Save the simulation name to local config
    config["last_simulation"] = target
    save_local_config(config, config_path)

    rs = ReverieServer(origin, target)

    # Start HTTP server for frontend communication
    rs.start_http_server()

    # Start the background producer for smooth playback (frontend replays a deep
    # buffer it fills ahead of the displayed step)
    rs.start_autosim()

    # Run CLI interface
    rs.open_server()
