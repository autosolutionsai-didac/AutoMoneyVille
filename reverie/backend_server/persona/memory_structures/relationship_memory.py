"""
Relationship & theory-of-mind memory for Claudeville personas (Phase 3).

This module gives each persona a persistent social model: per other-persona
records of familiarity, affinity, sentiment, recently-discussed topics, and
short first-person beliefs ("what I think about them"). It lets rapport,
rivalry, familiarity and status emerge across encounters and be recalled.

HARD CONSTRAINTS (docs/DECISIONS.md):
- D-002: NO vector embeddings. Relationship updates are heuristic + LLM-driven
  (text only), keyword-keyed. Records are keyed by lowercased persona name.
- One unified LLM call per step: this module never calls an LLM. It is fed by
  outputs already produced elsewhere (conversation commits, reflection).

Persistence: a single JSON file `relationships.json` saved alongside the other
bootstrap_memory artifacts (nodes.json, scratch.json, ...).

Author: Claudeville Project
"""

from __future__ import annotations

import datetime
import json
import os

# Bounds keep records compact for context budget and disk footprint.
MAX_TOPICS = 8
MAX_BELIEFS = 6

# Affinity is clamped to [-1, +1]. note_from_chat nudges it gently upward so
# repeated friendly contact builds rapport without runaway accumulation.
AFFINITY_MIN = -1.0
AFFINITY_MAX = 1.0
CHAT_AFFINITY_DELTA = 0.05

# Lowercased stopwords for the heuristic topic-gist extraction. Kept aligned
# with persona._build_focal_keywords so the social vocabulary stays consistent.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "in", "on",
    "at", "and", "or", "with", "for", "you", "your", "i", "it", "this",
    "that", "be", "as", "from", "by", "has", "have", "had", "im", "ive",
    "hey", "hi", "hello", "yeah", "yes", "no", "ok", "okay", "so", "but",
    "we", "they", "he", "she", "my", "me", "do", "did", "what", "how",
    "about", "just", "like", "going", "good", "well", "thanks", "thank",
}


def _clamp_affinity(value: float) -> float:
    """Clamp an affinity value into [-1, +1]."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(AFFINITY_MIN, min(AFFINITY_MAX, value))


def _sentiment_label(affinity: float) -> str:
    """Map an affinity float to a coarse human-readable sentiment label."""
    if affinity >= 0.6:
        return "close"
    if affinity >= 0.2:
        return "friendly"
    if affinity > -0.2:
        return "neutral"
    if affinity > -0.6:
        return "wary"
    return "hostile"


def _now_str(when) -> str | None:
    """Normalize a datetime (or pre-formatted str) to a stable string, or None."""
    if when is None:
        return None
    if isinstance(when, datetime.datetime):
        return when.strftime("%Y-%m-%d %H:%M:%S")
    return str(when)


def _topic_gist(chat_lines, limit: int = 3) -> list[str]:
    """Extract a short topic gist (content keywords) from chat lines.

    Heuristic only (D-002): lowercase, strip punctuation, drop stopwords and
    short tokens, keep the most frequent content words, order preserved.
    """
    if not chat_lines:
        return []

    counts: dict[str, int] = {}
    first_seen: dict[str, int] = {}
    for entry in chat_lines:
        line = None
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            line = entry[1]
        elif isinstance(entry, str):
            line = entry
        if not isinstance(line, str):
            continue
        for raw in line.split():
            word = "".join(ch for ch in raw.lower() if ch.isalnum())
            if len(word) <= 3 or word in _STOPWORDS:
                continue
            if word not in counts:
                first_seen[word] = len(first_seen)
            counts[word] = counts.get(word, 0) + 1

    # Most frequent first; ties broken by first-seen order (stable). first_seen
    # is captured up-front so the comparison key is stable during sorting.
    words = sorted(counts, key=lambda w: (-counts[w], first_seen[w]))
    return words[:limit]


class RelationshipMemory:
    """Persistent per-persona social model (Phase 3).

    Keyed by lowercased other-persona name. Each record holds:
      - name:             canonical display name as last observed
      - familiarity:      interaction count (int)
      - affinity:         float in [-1, +1]
      - sentiment:        coarse label derived from affinity
      - last_topics:      bounded list of recent topic keywords
      - beliefs:          bounded list of short first-person notes
      - last_interaction: datetime string of the most recent interaction
      - times_talked:     count of conversations committed to memory
    """

    def __init__(self, f_saved: str | None = None):
        # name_key (lowercase) -> record dict
        self.relationships: dict[str, dict] = {}
        if f_saved:
            self.load(f_saved)

    # ------------------------------------------------------------------ access
    def _key(self, name: str) -> str:
        return (name or "").strip().lower()

    def get(self, name: str) -> dict | None:
        """Return the record for ``name`` (case-insensitive), or None."""
        return self.relationships.get(self._key(name))

    def _ensure(self, name: str) -> dict:
        """Return the existing record for ``name`` or create a blank one."""
        key = self._key(name)
        rec = self.relationships.get(key)
        if rec is None:
            rec = {
                "name": name,
                "familiarity": 0,
                "affinity": 0.0,
                "sentiment": _sentiment_label(0.0),
                "last_topics": [],
                "beliefs": [],
                "last_interaction": None,
                "times_talked": 0,
            }
            self.relationships[key] = rec
        else:
            # Keep the freshest display name (capitalization can drift).
            if name:
                rec["name"] = name
        return rec

    # ------------------------------------------------------------------ update
    def observe_interaction(
        self,
        name: str,
        topics=None,
        affinity_delta: float = 0.0,
        belief: str | None = None,
        when=None,
    ) -> dict:
        """Record a single observed interaction with ``name``.

        Bumps familiarity, applies a clamped affinity delta, merges any topics,
        appends an optional first-person belief, and stamps the time. Returns
        the updated record.
        """
        rec = self._ensure(name)
        rec["familiarity"] = int(rec.get("familiarity", 0)) + 1

        if affinity_delta:
            rec["affinity"] = _clamp_affinity(
                rec.get("affinity", 0.0) + affinity_delta
            )
        rec["sentiment"] = _sentiment_label(rec["affinity"])

        if topics:
            self._merge_topics(rec, topics)

        if belief:
            self._add_belief(rec, belief)

        stamp = _now_str(when)
        if stamp:
            rec["last_interaction"] = stamp

        return rec

    def note_from_chat(self, name: str, chat_lines, when=None) -> dict:
        """Update the relationship from a committed conversation (heuristic).

        +familiarity, a small positive affinity nudge (rapport builds with
        contact), a topic gist extracted from the lines, and times_talked++.
        No LLM call (D-002). Returns the updated record.
        """
        topics = _topic_gist(chat_lines)
        rec = self.observe_interaction(
            name,
            topics=topics,
            affinity_delta=CHAT_AFFINITY_DELTA,
            when=when,
        )
        rec["times_talked"] = int(rec.get("times_talked", 0)) + 1
        return rec

    def _merge_topics(self, rec: dict, topics) -> None:
        """Merge topic keywords into a record's bounded MRU topic list."""
        existing = rec.get("last_topics", [])
        if isinstance(topics, str):
            topics = [topics]
        merged = list(existing)
        for t in topics:
            if not t:
                continue
            t = str(t).strip()
            if not t:
                continue
            # Move-to-front semantics (most recent topic first), dedup.
            if t in merged:
                merged.remove(t)
            merged.insert(0, t)
        rec["last_topics"] = merged[:MAX_TOPICS]

    def _add_belief(self, rec: dict, belief: str) -> None:
        """Append a short first-person belief, bounded and deduplicated."""
        belief = str(belief).strip()
        if not belief:
            return
        beliefs = rec.get("beliefs", [])
        if belief in beliefs:
            beliefs.remove(belief)
        beliefs.insert(0, belief)
        rec["beliefs"] = beliefs[:MAX_BELIEFS]

    def add_belief(self, name: str, belief: str) -> dict:
        """Public helper: attach a first-person belief about ``name``.

        Used by reflection to refine theory-of-mind without a new LLM call
        (reflection's insights are already produced in Phase 1).
        """
        rec = self._ensure(name)
        self._add_belief(rec, belief)
        return rec

    # ------------------------------------------------------------------ render
    def to_prompt_block(self, names) -> str:
        """Render a compact "PEOPLE YOU KNOW (nearby)" block for ``names``.

        Only personas we actually have a record for AND who are in ``names``
        (i.e. currently nearby) are shown, so the prompt stays focused. Returns
        an empty string when there is nothing to show.
        """
        if not names:
            return ""

        lines = []
        for name in names:
            rec = self.get(name)
            if not rec:
                continue
            lines.append(self._render_record(rec))

        if not lines:
            return ""

        body = "\n".join(lines)
        return f"\n=== PEOPLE YOU KNOW (nearby) ===\n{body}\n"

    def _render_record(self, rec: dict) -> str:
        """Render one relationship record as a single compact prompt line."""
        name = rec.get("name", "?")
        fam = int(rec.get("familiarity", 0))
        aff = float(rec.get("affinity", 0.0))
        sentiment = rec.get("sentiment") or _sentiment_label(aff)
        parts = [f"- {name}: {sentiment} (familiarity {fam}, affinity {aff:+.2f})"]

        topics = rec.get("last_topics", [])
        if topics:
            parts.append("recent topics: " + ", ".join(topics[:3]))

        beliefs = rec.get("beliefs", [])
        if beliefs:
            parts.append("you think: " + "; ".join(beliefs[:2]))

        return " | ".join(parts)

    # ------------------------------------------------------------------ persist
    def save(self, save_dir: str) -> None:
        """Persist relationships to ``save_dir``/relationships.json."""
        os.makedirs(save_dir, exist_ok=True)
        out_path = os.path.join(save_dir, "relationships.json")
        with open(out_path, "w", encoding="utf-8") as outfile:
            json.dump(self.relationships, outfile, ensure_ascii=False, indent=2)

    def load(self, save_dir: str) -> None:
        """Load relationships from ``save_dir``/relationships.json if present.

        Missing/corrupt files are tolerated (existing bootstrap personas have no
        relationships.json yet) — we simply start from an empty social model.
        """
        in_path = os.path.join(save_dir, "relationships.json")
        if not os.path.exists(in_path):
            self.relationships = {}
            return
        try:
            with open(in_path, encoding="utf-8") as infile:
                data = json.load(infile)
        except (json.JSONDecodeError, OSError):
            self.relationships = {}
            return

        # Normalize: re-key by lowercase, backfill any missing fields/bounds.
        normalized: dict[str, dict] = {}
        if isinstance(data, dict):
            for raw_key, rec in data.items():
                if not isinstance(rec, dict):
                    continue
                name = rec.get("name") or raw_key
                key = self._key(name)
                affinity = _clamp_affinity(rec.get("affinity", 0.0))
                normalized[key] = {
                    "name": name,
                    "familiarity": int(rec.get("familiarity", 0) or 0),
                    "affinity": affinity,
                    "sentiment": rec.get("sentiment") or _sentiment_label(affinity),
                    "last_topics": list(rec.get("last_topics", []))[:MAX_TOPICS],
                    "beliefs": list(rec.get("beliefs", []))[:MAX_BELIEFS],
                    "last_interaction": rec.get("last_interaction"),
                    "times_talked": int(rec.get("times_talked", 0) or 0),
                }
        self.relationships = normalized
