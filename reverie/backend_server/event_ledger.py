"""Append-only event ledger for simulation audit trails."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        with self.path.open("a", encoding="utf-8") as outfile:
            outfile.write(json.dumps(event, ensure_ascii=True) + "\n")
        return event

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        entries = []
        with self.path.open("r", encoding="utf-8") as infile:
            for line in infile:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
