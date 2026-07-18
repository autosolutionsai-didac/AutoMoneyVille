"""Read a frozen persona inspector snapshot from an immutable saved run."""

import datetime
import json
import re
from pathlib import Path

MEMORY_LIMIT = 20
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_REPLAY_STEP = 99_999_999
_SIM_CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z", re.ASCII)
_PERSONA_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _'-]{0,99}\Z", re.ASCII)
_STEP = re.compile(r"(?:0|[1-9][0-9]{0,7})\Z", re.ASCII)


class InvalidReplayRequest(ValueError):
    """The URL contained an invalid run or persona identifier."""


class ReplayStateNotFound(FileNotFoundError):
    """The requested run or persona does not exist."""


class ReplayStateUnavailable(Exception):
    """The saved state exists but cannot be read safely."""


def _contained(root, candidate):
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ReplayStateUnavailable from exc
    return candidate


def _safe_child(root, *parts):
    return _contained(root, root.joinpath(*parts).resolve())


def _read_object(memory_root, *parts):
    path = _safe_child(memory_root, *parts)
    try:
        if not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
            raise ReplayStateUnavailable
        with path.open(encoding="utf-8") as json_file:
            value = json.load(json_file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayStateUnavailable from exc
    if not isinstance(value, dict):
        raise ReplayStateUnavailable
    return value


def _run_root(frontend_root, sim_code):
    if not _SIM_CODE.fullmatch(sim_code or ""):
        raise InvalidReplayRequest
    runs_root = Path(frontend_root).joinpath("storage", "runs").resolve()
    run_root = _safe_child(runs_root, sim_code)
    if not run_root.is_dir():
        raise ReplayStateNotFound
    return run_root


def _requested_step(value):
    if isinstance(value, bool):
        raise InvalidReplayRequest
    if isinstance(value, int):
        if 0 <= value <= MAX_REPLAY_STEP:
            return value
        raise InvalidReplayRequest
    if not isinstance(value, str) or not _STEP.fullmatch(value):
        raise InvalidReplayRequest
    try:
        parsed = int(value)
    except (OverflowError, ValueError) as exc:
        raise InvalidReplayRequest from exc
    if parsed > MAX_REPLAY_STEP:
        raise InvalidReplayRequest
    return parsed


def load_replay_environment(frontend_root, sim_code, requested_step):
    """Load the exact or nearest earlier immutable environment snapshot."""
    requested_step = _requested_step(requested_step)
    environment_root = _safe_child(_run_root(frontend_root, sim_code), "environment")
    if not environment_root.is_dir():
        raise ReplayStateNotFound
    eligible = []
    try:
        for path in environment_root.iterdir():
            if path.is_file() and path.suffix == ".json" and path.stem.isdigit():
                candidate = int(path.stem)
                if candidate <= requested_step:
                    eligible.append(candidate)
    except OSError as exc:
        raise ReplayStateUnavailable from exc
    if not eligible:
        raise ReplayStateNotFound
    effective_step = max(eligible)
    environment = _read_object(environment_root, f"{effective_step}.json")
    return {
        "requested_step": requested_step,
        "effective_step": effective_step,
        "environment": environment,
    }


def load_replay_snapshot(frontend_root, sim_code, requested_step):
    """Return safe page metadata, persona names, and one recorded environment."""
    step_state = load_replay_environment(frontend_root, sim_code, requested_step)
    run_root = _run_root(frontend_root, sim_code)
    meta = _read_object(_safe_child(run_root, "reverie"), "meta.json")
    personas_root = _safe_child(run_root, "personas")
    if not personas_root.is_dir():
        raise ReplayStateNotFound
    try:
        names = sorted(
            path.name
            for path in personas_root.iterdir()
            if path.is_dir() and _PERSONA_NAME.fullmatch(path.name)
        )
    except OSError as exc:
        raise ReplayStateUnavailable from exc
    if not names:
        raise ReplayStateNotFound
    return {**step_state, "meta": meta, "persona_names": names}


def _minutes_since_midnight(value):
    if not isinstance(value, str):
        return -1
    for date_format in (
        "%B %d, %Y, %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            parsed = datetime.datetime.strptime(value, date_format)
            return parsed.hour * 60 + parsed.minute
        except ValueError:
            continue
    return -1


def _schedule(scratch):
    schedule = []
    current_index = -1
    elapsed = 0
    minutes_now = _minutes_since_midnight(scratch.get("curr_time"))
    raw_schedule = scratch.get("f_daily_schedule", [])
    if not isinstance(raw_schedule, list):
        return schedule, current_index
    for index, row in enumerate(raw_schedule[:48]):
        if not isinstance(row, list) or not row:
            continue
        try:
            minutes = max(0, int(row[1])) if len(row) > 1 else 0
        except (TypeError, ValueError):
            minutes = 0
        if current_index < 0 and elapsed <= minutes_now < elapsed + max(minutes, 1):
            current_index = len(schedule)
        schedule.append({"task": str(row[0])[:300], "minutes": minutes})
        elapsed += minutes
    return schedule, current_index


def _goals(raw):
    records = raw.get("goals", raw)
    if not isinstance(records, dict):
        return []
    result = []
    for record in records.values():
        if not isinstance(record, dict):
            continue
        status = str(record.get("status", ""))
        if status.lower() not in {"active", "in_progress", "pending"}:
            continue
        title = str(
            record.get("title")
            or record.get("description")
            or record.get("goal")
            or record.get("text")
            or ""
        )[:160]
        if title:
            result.append({"title": title, "status": status})
        if len(result) == 20:
            break
    return result


def _number(value, default):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _relationships(raw):
    result = []
    for other, record in raw.items():
        if not isinstance(record, dict):
            continue
        topics = record.get("last_topics", [])
        if not isinstance(topics, list):
            topics = []
        result.append(
            {
                "name": str(record.get("name") or other)[:100],
                "familiarity": _number(record.get("familiarity"), 0),
                "affinity": _number(record.get("affinity"), 0.0),
                "sentiment": str(record.get("sentiment", ""))[:40],
                "last_topics": [str(topic)[:80] for topic in topics[:4]],
            }
        )
    result.sort(key=lambda record: -record["familiarity"])
    return result[:20]


def _memories(raw):
    result = []
    for record in raw.values():
        if not isinstance(record, dict):
            continue
        kind = str(record.get("type", ""))
        if kind not in {"event", "thought", "chat"}:
            continue
        result.append(
            {
                "kind": kind,
                "description": str(record.get("description", ""))[:1000],
                "created": str(record.get("created", ""))[:40],
                "poignancy": _number(record.get("poignancy"), None),
            }
        )
    result.sort(key=lambda memory: memory["created"], reverse=True)
    return result[:MEMORY_LIMIT]


def load_replay_persona_state(frontend_root, sim_code, requested_step, persona_name):
    """Return the inspector schema from one saved run without backend access."""
    if not _SIM_CODE.fullmatch(sim_code or "") or not _PERSONA_NAME.fullmatch(
        persona_name or ""
    ):
        raise InvalidReplayRequest
    persona_name = " ".join(persona_name.replace("_", " ").split())

    step_state = load_replay_environment(frontend_root, sim_code, requested_step)
    run_root = _run_root(frontend_root, sim_code)
    personas_root = _safe_child(run_root, "personas")
    memory_root = _safe_child(
        personas_root, persona_name, "bootstrap_memory"
    )
    if not memory_root.is_dir():
        raise ReplayStateNotFound

    scratch = _read_object(memory_root, "scratch.json")
    goals = _read_object(memory_root, "goals.json")
    relationships = _read_object(memory_root, "relationships.json")
    nodes = _read_object(memory_root, "associative_memory", "nodes.json")
    schedule, current_index = _schedule(scratch)
    tile = scratch.get("curr_tile", [])
    if not isinstance(tile, list) or len(tile) < 2:
        tile = []
    environment_record = step_state["environment"].get(persona_name, {})
    if not isinstance(environment_record, dict):
        environment_record = {}
    x = environment_record.get("x")
    y = environment_record.get("y")
    has_step_tile = all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in (x, y)
    )
    if has_step_tile:
        tile = [x, y]

    def recorded_or_final(*keys, fallback):
        for key in keys:
            value = environment_record.get(key)
            if value is not None:
                return str(value)
        return str(scratch.get(fallback, ""))

    def has_recorded(*keys):
        return any(environment_record.get(key) is not None for key in keys)

    return {
        "name": str(scratch.get("name") or persona_name)[:100],
        "currently": recorded_or_final("currently", fallback="currently")[:1000],
        "action": recorded_or_final(
            "action", "description", "act_description", fallback="act_description"
        )[:1000],
        "address": recorded_or_final("address", "act_address", fallback="act_address")[
            :500
        ],
        "chatting_with": scratch.get("chatting_with") or None,
        "tile": list(tile[:2]),
        "schedule": schedule,
        "schedule_current_index": current_index,
        "goals": _goals(goals),
        "relationships": _relationships(relationships),
        "memories": _memories(nodes),
        "requested_step": step_state["requested_step"],
        "effective_step": step_state["effective_step"],
        "position_scope": (
            "environment-step" if has_step_tile else "final-recorded-memory"
        ),
        "currently_scope": (
            "environment-step"
            if has_recorded("currently")
            else "final-recorded-memory"
        ),
        "action_scope": (
            "environment-step"
            if has_recorded("action", "description", "act_description")
            else "final-recorded-memory"
        ),
        "address_scope": (
            "environment-step"
            if has_recorded("address", "act_address")
            else "final-recorded-memory"
        ),
        "state_scope": "final-recorded-memory",
    }
