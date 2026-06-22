"""
Multi-day goal / commitment memory for Claudeville personas (Phase 4).

This module gives each persona a persistent, multi-day backlog of goals,
promises, and projects so daily agency no longer resets at midnight. Today's
``daily_req`` is regenerated each morning and unfinished aims evaporate; a
``GoalMemory`` carries open commitments forward across day rollovers, lets the
day-plan / reflection update their progress, and surfaces them back into the
day-planning and step prompts so the persona honors what it set out (or
promised) to do (Generative-Agents long-horizon planning).

HARD CONSTRAINTS (docs/DECISIONS.md):
- D-002: NO vector embeddings. Promise capture is heuristic (keyword) +
  reflection-driven (text). Goals are keyed by a stable opaque id.
- One unified LLM call per step: this module never calls an LLM. It is fed by
  outputs already produced elsewhere (day-planning, reflection, conversation
  commits). Identity/goal evolution rides existing OCCASIONAL calls only.

Persistence: a single JSON file ``goals.json`` saved alongside the other
bootstrap_memory artifacts (nodes.json, scratch.json, relationships.json, ...).

Author: Claudeville Project
"""

from __future__ import annotations

import datetime
import json
import os

# Valid enums kept small and explicit so a malformed value coerces to a safe
# default rather than silently polluting the backlog.
VALID_KINDS = ("goal", "promise", "project")
VALID_STATUSES = ("active", "blocked", "done", "abandoned")
# Statuses that count as "still open" -> carried across day rollover + surfaced.
OPEN_STATUSES = ("active", "blocked")

# Bounds keep the backlog compact for context budget and disk footprint.
MAX_NOTES = 8
MAX_SUBGOALS = 12
# Default cap on how many active goals are rendered into a prompt block.
DEFAULT_PROMPT_LIMIT = 6

# Heuristic promise cues (lowercased). A chat line a persona SAYS that contains
# one of these is treated as a candidate commitment (D-002: no embeddings).
_PROMISE_CUES = (
    "i promise",
    "i'll ",
    "i will ",
    "i can ",
    "i'll get",
    "let me ",
    "i'll bring",
    "i'll send",
    "i'll help",
    "i'll make",
    "i'll take care",
    "count on me",
    "you can count on me",
    "i'll have it",
    "i'll do it",
    "by tomorrow",
    "i owe you",
)


def _clamp_progress(value) -> float:
    """Clamp a progress value into [0.0, 1.0]; non-numeric -> 0.0."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, value))


def _coerce_kind(kind: str | None) -> str:
    k = (kind or "goal").strip().lower()
    return k if k in VALID_KINDS else "goal"


def _coerce_status(status: str | None) -> str:
    s = (status or "active").strip().lower()
    return s if s in VALID_STATUSES else "active"


def _now_str(when) -> str | None:
    """Normalize a datetime (or pre-formatted str) to a stable string, or None."""
    if when is None:
        return None
    if isinstance(when, datetime.datetime):
        return when.strftime("%Y-%m-%d %H:%M:%S")
    return str(when)


def looks_like_promise(line: str) -> bool:
    """Heuristic: does a spoken line read as a commitment? (D-002, keyword only)."""
    if not isinstance(line, str) or not line.strip():
        return False
    low = line.lower()
    return any(cue in low for cue in _PROMISE_CUES)


class GoalMemory:
    """Persistent multi-day goal / commitment backlog for one persona.

    Each goal record holds:
      - id:           stable opaque id ("g1", "g2", ...)
      - text:         short description of the goal/promise
      - kind:         goal | promise | project
      - status:       active | blocked | done | abandoned
      - progress:     float in [0.0, 1.0]
      - created_day:  date string the goal first appeared (e.g. "2026-06-22")
      - target_day:   optional date string deadline
      - source:       provenance, e.g. "promised Alice" / "day plan"
      - notes:        bounded list of short progress notes
      - sub_goals:    optional ordered list of {text, status, progress} steps
      - last_updated: datetime string of the most recent change
    """

    def __init__(self, f_saved: str | None = None):
        # id -> record dict
        self.goals: dict[str, dict] = {}
        self._next_id = 1
        # Remember where to persist so goals absorbed mid-session (e.g. during
        # sleep compaction) can be flushed to disk without the caller knowing
        # the path. None until a save/load binds a directory.
        self._save_dir: str | None = f_saved
        if f_saved:
            self.load(f_saved)

    # ------------------------------------------------------------------ helpers
    def _new_id(self) -> str:
        gid = f"g{self._next_id}"
        self._next_id += 1
        return gid

    def get(self, goal_id: str) -> dict | None:
        """Return the record for ``goal_id``, or None."""
        return self.goals.get(goal_id)

    def _day_str(self, when) -> str | None:
        if isinstance(when, datetime.datetime):
            return when.strftime("%Y-%m-%d")
        if isinstance(when, str) and when:
            return when
        return None

    def _find_by_text(self, text: str) -> dict | None:
        """Find an existing OPEN goal whose text matches (case-insensitive).

        Used to dedupe so re-stating the same aim in the day plan or a repeated
        promise doesn't create a duplicate backlog entry.
        """
        norm = (text or "").strip().lower()
        if not norm:
            return None
        for rec in self.goals.values():
            # Only dedupe against still-open goals: a goal completed/abandoned
            # on a previous day must NOT swallow today's restatement, or the
            # daily requirement would stay done+invisible and never resurface.
            if rec.get("status") not in OPEN_STATUSES:
                continue
            if rec.get("text", "").strip().lower() == norm:
                return rec
        return None

    # ------------------------------------------------------------------ mutate
    def add(
        self,
        text: str,
        kind: str = "goal",
        source: str | None = None,
        created_day=None,
        target_day=None,
        status: str = "active",
        progress: float = 0.0,
        when=None,
        dedupe: bool = True,
    ) -> dict | None:
        """Add a new goal/promise/project. Returns the record (or existing one).

        ``dedupe`` (default True) reuses an existing record with identical text
        rather than creating a duplicate, refreshing its source/target if newly
        supplied. Returns None for empty text.
        """
        text = (text or "").strip()
        if not text:
            return None

        if dedupe:
            existing = self._find_by_text(text)
            if existing is not None:
                # Refresh metadata that may have arrived with the restatement.
                if source and not existing.get("source"):
                    existing["source"] = source
                if target_day and not existing.get("target_day"):
                    existing["target_day"] = self._day_str(target_day)
                existing["last_updated"] = _now_str(when)
                return existing

        gid = self._new_id()
        rec = {
            "id": gid,
            "text": text,
            "kind": _coerce_kind(kind),
            "status": _coerce_status(status),
            "progress": _clamp_progress(progress),
            "created_day": self._day_str(created_day) or self._day_str(when),
            "target_day": self._day_str(target_day),
            "source": source or "",
            "notes": [],
            "sub_goals": [],
            "last_updated": _now_str(when),
        }
        self.goals[gid] = rec
        return rec

    def update_progress(
        self, goal_id: str, progress: float, note: str | None = None, when=None
    ) -> dict | None:
        """Set a goal's progress (clamped) and optionally append a note.

        Reaching progress >= 1.0 auto-marks the goal done so it stops resurfacing.
        Returns the updated record, or None if the id is unknown.
        """
        rec = self.goals.get(goal_id)
        if rec is None:
            return None
        rec["progress"] = _clamp_progress(progress)
        if note:
            self._add_note(rec, note)
        if rec["progress"] >= 1.0 and rec["status"] not in ("abandoned",):
            rec["status"] = "done"
        rec["last_updated"] = _now_str(when)
        return rec

    def mark(self, goal_id: str, status: str, when=None) -> dict | None:
        """Set a goal's status (validated). Returns the record, or None."""
        rec = self.goals.get(goal_id)
        if rec is None:
            return None
        rec["status"] = _coerce_status(status)
        if rec["status"] == "done":
            rec["progress"] = 1.0
        rec["last_updated"] = _now_str(when)
        return rec

    def _add_note(self, rec: dict, note: str) -> None:
        note = str(note).strip()
        if not note:
            return
        notes = rec.get("notes", [])
        if note in notes:
            notes.remove(note)
        notes.insert(0, note)
        rec["notes"] = notes[:MAX_NOTES]

    def add_note(self, goal_id: str, note: str, when=None) -> dict | None:
        """Public helper: attach a short progress note to a goal."""
        rec = self.goals.get(goal_id)
        if rec is None:
            return None
        self._add_note(rec, note)
        rec["last_updated"] = _now_str(when)
        return rec

    def set_sub_goals(self, goal_id: str, sub_goals, when=None) -> dict | None:
        """Decompose a project into an ordered list of sub-goals (4b).

        ``sub_goals`` is an iterable of strings or dicts. Each becomes
        {text, status, progress}; dependency/blocked status is preserved when
        supplied as a dict, mirroring the Town Center request decomposition.
        Returns the updated record, or None if the id is unknown.
        """
        rec = self.goals.get(goal_id)
        if rec is None:
            return None
        normalized = []
        for item in sub_goals or []:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                normalized.append(
                    {
                        "text": text,
                        "status": _coerce_status(item.get("status", "active")),
                        "progress": _clamp_progress(item.get("progress", 0.0)),
                    }
                )
            elif isinstance(item, str) and item.strip():
                normalized.append(
                    {"text": item.strip(), "status": "active", "progress": 0.0}
                )
            if len(normalized) >= MAX_SUBGOALS:
                break
        rec["sub_goals"] = normalized
        rec["last_updated"] = _now_str(when)
        return rec

    # --------------------------------------------------------------- capture
    def capture_promises_from_chat(
        self, speaker_name: str, chat_lines, partner: str | None = None, when=None
    ) -> list[dict]:
        """Heuristically extract commitments the persona MADE in a conversation.

        Only lines spoken by ``speaker_name`` that match a promise cue are
        captured, each as a ``promise`` goal sourced to the partner (D-002,
        keyword heuristic, no LLM). Returns the list of newly created records.
        """
        made: list[dict] = []
        for entry in chat_lines or []:
            if not (isinstance(entry, (list, tuple)) and len(entry) >= 2):
                continue
            speaker, line = entry[0], entry[1]
            if speaker != speaker_name:
                continue
            if not looks_like_promise(line):
                continue
            src = f"promised {partner}" if partner else "promise made in conversation"
            rec = self.add(
                str(line).strip(),
                kind="promise",
                source=src,
                created_day=when,
                when=when,
            )
            if rec is not None and rec not in made:
                made.append(rec)
        return made

    # ------------------------------------------------------------------ query
    def get_active(self, include_blocked: bool = True) -> list[dict]:
        """Return open goals (active, and optionally blocked), newest id first."""
        statuses = OPEN_STATUSES if include_blocked else ("active",)
        out = [r for r in self.goals.values() if r.get("status") in statuses]
        # Stable order: by numeric id ascending so creation order is preserved.
        out.sort(key=lambda r: _id_sort_key(r.get("id", "")))
        return out

    def carry_over(self, new_day=None) -> int:
        """Day-rollover hook: open goals survive into the new day untouched.

        Unlike ``daily_req`` (regenerated each morning), goals are NOT wiped at a
        day boundary. This method exists as the explicit carry-over seam: it
        leaves open goals intact and returns how many carried over. Done /
        abandoned goals remain stored (history) but are excluded from the count
        and from ``get_active`` / ``to_prompt_block`` so they never resurface.
        """
        return len(self.get_active())

    # ------------------------------------------------------------------ render
    def to_prompt_block(self, limit: int = DEFAULT_PROMPT_LIMIT) -> str:
        """Render a compact "YOUR ONGOING GOALS & COMMITMENTS" block.

        Only open goals are shown, capped at ``limit``. Returns an empty string
        when there is nothing to show so prompts stay clean.
        """
        active = self.get_active()[:limit]
        if not active:
            return ""
        lines = [self._render_record(rec) for rec in active]
        body = "\n".join(lines)
        return f"\n=== YOUR ONGOING GOALS & COMMITMENTS ===\n{body}\n"

    def to_step_line(self, limit: int = 3) -> str:
        """Render a single short line of top active goals for the step prompt.

        Returns an empty string when there are no open goals.
        """
        active = self.get_active()[:limit]
        if not active:
            return ""
        bits = []
        for rec in active:
            pct = int(round(rec.get("progress", 0.0) * 100))
            tag = rec.get("kind", "goal")
            bits.append(f"{rec.get('text', '')} ({tag} {pct}%)")
        return "Open goals: " + "; ".join(bits)

    def _render_record(self, rec: dict) -> str:
        text = rec.get("text", "?")
        kind = rec.get("kind", "goal")
        status = rec.get("status", "active")
        pct = int(round(rec.get("progress", 0.0) * 100))
        parts = [f"- [{kind}] {text} — {status}, {pct}%"]

        source = rec.get("source")
        if source:
            parts.append(f"({source})")
        target = rec.get("target_day")
        if target:
            parts.append(f"due {target}")

        head = " ".join(parts)
        subs = rec.get("sub_goals", [])
        if subs:
            sub_lines = []
            for sub in subs[:MAX_SUBGOALS]:
                spct = int(round(sub.get("progress", 0.0) * 100))
                sub_lines.append(
                    f"    • {sub.get('text', '')} [{sub.get('status', 'active')}, {spct}%]"
                )
            return head + "\n" + "\n".join(sub_lines)
        return head

    # ------------------------------------------------------------------ persist
    def save(self, save_dir: str) -> None:
        """Persist goals to ``save_dir``/goals.json."""
        os.makedirs(save_dir, exist_ok=True)
        self._save_dir = save_dir
        out_path = os.path.join(save_dir, "goals.json")
        payload = {"next_id": self._next_id, "goals": self.goals}
        with open(out_path, "w", encoding="utf-8") as outfile:
            json.dump(payload, outfile, ensure_ascii=False, indent=2)

    def persist(self) -> bool:
        """Flush to the remembered directory (bound at construction/save/load).

        Lets goals folded in mid-session (sleep compaction) survive a crash
        before the next full persona.save(). Returns False if no dir is known.
        """
        if not self._save_dir:
            return False
        self.save(self._save_dir)
        return True

    def load(self, save_dir: str) -> None:
        """Load goals from ``save_dir``/goals.json if present.

        Missing/corrupt files are tolerated (existing bootstrap personas have no
        goals.json yet) — we simply start from an empty backlog.
        """
        self._save_dir = save_dir
        in_path = os.path.join(save_dir, "goals.json")
        if not os.path.exists(in_path):
            self.goals = {}
            self._next_id = 1
            return
        try:
            with open(in_path, encoding="utf-8") as infile:
                data = json.load(infile)
        except (json.JSONDecodeError, OSError):
            self.goals = {}
            self._next_id = 1
            return

        raw_goals = data.get("goals", {}) if isinstance(data, dict) else {}
        normalized: dict[str, dict] = {}
        max_seen = 0
        if isinstance(raw_goals, dict):
            for gid, rec in raw_goals.items():
                if not isinstance(rec, dict):
                    continue
                norm = self._normalize_record(gid, rec)
                normalized[norm["id"]] = norm
                max_seen = max(max_seen, _id_sort_key(norm["id"]))
        self.goals = normalized

        next_id = data.get("next_id") if isinstance(data, dict) else None
        try:
            self._next_id = max(int(next_id), max_seen + 1)
        except (TypeError, ValueError):
            self._next_id = max_seen + 1

    def _normalize_record(self, gid: str, rec: dict) -> dict:
        """Backfill/clamp a loaded record so downstream code can trust it."""
        sub_goals = []
        for sub in rec.get("sub_goals", []) or []:
            if isinstance(sub, dict) and str(sub.get("text", "")).strip():
                sub_goals.append(
                    {
                        "text": str(sub["text"]).strip(),
                        "status": _coerce_status(sub.get("status", "active")),
                        "progress": _clamp_progress(sub.get("progress", 0.0)),
                    }
                )
        return {
            "id": rec.get("id") or gid,
            "text": str(rec.get("text", "")).strip(),
            "kind": _coerce_kind(rec.get("kind")),
            "status": _coerce_status(rec.get("status")),
            "progress": _clamp_progress(rec.get("progress", 0.0)),
            "created_day": rec.get("created_day"),
            "target_day": rec.get("target_day"),
            "source": rec.get("source", "") or "",
            "notes": list(rec.get("notes", []))[:MAX_NOTES],
            "sub_goals": sub_goals[:MAX_SUBGOALS],
            "last_updated": rec.get("last_updated"),
        }


def _id_sort_key(goal_id: str) -> int:
    """Numeric sort key for ids like 'g12' -> 12; falls back to 0."""
    try:
        return int(str(goal_id).lstrip("g") or 0)
    except (TypeError, ValueError):
        return 0
