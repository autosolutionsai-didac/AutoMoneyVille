"""Append-only event ledger for simulation audit trails."""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
# Serializes appends so an HTTP-thread write cannot interleave bytes with a
# CLI/main-thread write to the same ledger file (ARCH-10).
_WRITE_LOCK = threading.Lock()


class EventLedger:
    """Small JSONL ledger used for auditable simulation events."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(
        self,
        event_type: str,
        *,
        actor: str | None = None,
        step: int | None = None,
        sim_time: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": f"evt_{uuid.uuid4().hex[:12]}",
            "type": event_type,
            "actor": actor,
            "step": step,
            "sim_time": sim_time,
            "payload": payload or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _WRITE_LOCK:
            with self.path.open("a", encoding="utf-8") as outfile:
                outfile.write(json.dumps(event, ensure_ascii=True) + "\n")
                outfile.flush()
                os.fsync(outfile.fileno())
        return event

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as infile:
            raw_lines = infile.readlines()
        # Index of the last non-blank line — only a torn write *there* is benign.
        last_idx = max((i for i, ln in enumerate(raw_lines) if ln.strip()), default=-1)
        entries = []
        for idx, line in enumerate(raw_lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entries.append(json.loads(stripped))
            except json.JSONDecodeError:
                if idx == last_idx:
                    # A torn/partial final line from an interrupted append is benign.
                    _LOGGER.warning("Ignoring torn final ledger line in %s", self.path)
                else:
                    # Mid-file corruption is a real integrity problem, not a torn
                    # append — surface it loudly (read still fails open).
                    _LOGGER.error(
                        "Corrupt ledger line %d in %s (skipped)", idx + 1, self.path
                    )
        return entries
