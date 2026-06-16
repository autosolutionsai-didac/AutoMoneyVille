"""Safe economy primitives for future money-agent simulation layers."""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)
# Serializes ledger appends across HTTP and CLI threads (ARCH-10).
_WRITE_LOCK = threading.Lock()


class RequestState(str, Enum):
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class ToolCapability:
    name: str
    category: str
    description: str
    requires_approval: bool
    risk_level: str


class ToolRegistry:
    """Catalog of tools and whether they may run without human approval."""

    def __init__(self, tools: list[ToolCapability]):
        self._tools = {tool.name: tool for tool in tools}

    @classmethod
    def default(cls) -> ToolRegistry:
        return cls(
            [
                ToolCapability(
                    "web_research",
                    "read",
                    "Research public information and summarize findings.",
                    False,
                    "low",
                ),
                ToolCapability(
                    "market_analysis",
                    "draft",
                    "Analyze niches, pain points, and service opportunities.",
                    False,
                    "low",
                ),
                ToolCapability(
                    "lead_list_draft",
                    "draft",
                    "Draft prospect lists without contacting anyone.",
                    False,
                    "low",
                ),
                ToolCapability(
                    "offer_draft",
                    "draft",
                    "Draft offers, proposals, and service packages.",
                    False,
                    "low",
                ),
                ToolCapability(
                    "send_email",
                    "external_action",
                    "Send outbound email or direct messages.",
                    True,
                    "high",
                ),
                ToolCapability(
                    "post_content",
                    "external_action",
                    "Publish content to an external account.",
                    True,
                    "high",
                ),
                ToolCapability(
                    "spend_money",
                    "external_action",
                    "Spend budget, buy services, or change paid accounts.",
                    True,
                    "critical",
                ),
            ]
        )

    def get(self, name: str) -> ToolCapability:
        return self._tools[name]

    def requires_approval(self, name: str) -> bool:
        tool = self._tools.get(name)
        return True if tool is None else tool.requires_approval

    def to_dicts(self) -> list[dict[str, Any]]:
        return [asdict(tool) for tool in self._tools.values()]


class JsonlLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _append(self, entry: dict[str, Any]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _WRITE_LOCK:
            with self.path.open("a", encoding="utf-8") as outfile:
                outfile.write(json.dumps(entry, ensure_ascii=True) + "\n")
                outfile.flush()
                os.fsync(outfile.fileno())
        return entry

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as infile:
            raw_lines = infile.readlines()
        # Index of the last non-blank line — only a torn write *there* is benign.
        last_idx = max(
            (i for i, ln in enumerate(raw_lines) if ln.strip()), default=-1
        )
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


class RequestLedger(JsonlLedger):
    """Append-only approval/request history."""

    def submit(
        self,
        *,
        actor: str,
        request_type: str,
        title: str,
        rationale: str,
        payload: dict[str, Any] | None = None,
        approval_required: bool | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": f"req_{uuid.uuid4().hex[:12]}",
            "state": RequestState.PROPOSED.value,
            "actor": actor,
            "type": request_type,
            "title": title,
            "rationale": rationale,
            "payload": payload or {},
            "created_at": _now(),
        }
        if approval_required is not None:
            entry["approval_required"] = approval_required
        return self._append(
            entry
        )

    def transition(
        self,
        request_id: str,
        state: RequestState,
        *,
        reviewer: str,
        note: str,
    ) -> dict[str, Any]:
        return self._append(
            {
                "id": request_id,
                "state": state.value,
                "reviewer": reviewer,
                "note": note,
                "created_at": _now(),
            }
        )


class RewardLedger(JsonlLedger):
    """Append-only mixed point and revenue reward ledger."""

    def award(
        self,
        *,
        actor: str,
        points: int,
        source: str,
        evidence: str,
        revenue_cents: int = 0,
        reference_id: str | None = None,
        outcome_valence: int | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": f"rew_{uuid.uuid4().hex[:12]}",
            "actor": actor,
            "points": points,
            "source": source,
            "evidence": evidence,
            "revenue_cents": revenue_cents,
            "outcome_valence": _clamp_valence(
                _default_outcome_valence(points, revenue_cents)
                if outcome_valence is None
                else outcome_valence
            ),
            "created_at": _now(),
        }
        if reference_id:
            entry["reference_id"] = reference_id
        return self._append(entry)

    def team_score(self) -> dict[str, int]:
        entries = self.read_all()
        return {
            "points": sum(int(entry.get("points", 0)) for entry in entries),
            "revenue_cents": sum(
                int(entry.get("revenue_cents", 0)) for entry in entries
            ),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_outcome_valence(points: int, revenue_cents: int = 0) -> int:
    if revenue_cents > 0:
        return 10
    if points > 0:
        return min(10, max(1, points * 2))
    if points < 0:
        return max(-10, min(-1, points * 2))
    return 0


def _clamp_valence(valence: int) -> int:
    return max(-10, min(10, int(valence)))
