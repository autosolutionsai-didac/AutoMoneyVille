"""Town-center store for requests, tools, rewards, and scenario state."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

try:
    from .economy import RequestLedger, RequestState, RewardLedger, ToolRegistry
    from .scenario_config import load_scenario
except ImportError:
    from economy import RequestLedger, RequestState, RewardLedger, ToolRegistry
    from scenario_config import load_scenario


class TownCenterStore:
    """Persistent local store for the governed money-agent control plane."""

    def __init__(self, root: str | Path, scenario_id: str = "startup_team_v1"):
        self.root = Path(root) / "town_center"
        self.scenario_id = scenario_id
        self.scenario = load_scenario(scenario_id)
        self.tool_registry = ToolRegistry.default()
        self.requests = RequestLedger(self.root / "requests.jsonl")
        self.rewards = RewardLedger(self.root / "rewards.jsonl")

    def submit_request(
        self,
        *,
        actor: str,
        request_type: str,
        title: str,
        rationale: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        actor = self._canonical_actor(actor)
        payload = payload or {}
        tool = payload.get("tool") or payload.get("requested_tool")
        approval_required = self.tool_registry.requires_approval(str(tool)) if tool else True
        return self.requests.submit(
            actor=actor,
            request_type=request_type,
            title=title,
            rationale=rationale,
            payload=payload,
            approval_required=approval_required,
        )

    def transition_request(
        self,
        request_id: str,
        state: RequestState | str,
        *,
        reviewer: str,
        note: str,
    ) -> dict[str, Any]:
        if not isinstance(state, RequestState):
            state = RequestState(str(state))
        current_request = self._find_current_request(request_id)
        transition = self.requests.transition(
            request_id,
            state,
            reviewer=reviewer,
            note=note,
        )
        if current_request:
            self._award_transition_reward(current_request, state, note)
        return transition

    def award_reward(
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
        return self.rewards.award(
            actor=self._canonical_actor(actor),
            points=points,
            source=source,
            evidence=evidence,
            revenue_cents=revenue_cents,
            reference_id=reference_id,
            outcome_valence=outcome_valence,
        )

    def snapshot(self) -> dict[str, Any]:
        request_events = self.requests.read_all()
        reward_events = self.rewards.read_all()
        requests = self._current_requests(request_events)
        approval_queue = [
            request
            for request in requests
            if request.get("approval_required")
            and request.get("current_state")
            in {RequestState.PROPOSED.value, RequestState.UNDER_REVIEW.value}
        ]
        return {
            "scenario": self.scenario,
            "tools": self.tool_registry.to_dicts(),
            "requests": requests,
            "approval_queue": approval_queue,
            "request_events": request_events,
            "rewards": reward_events,
            "team_score": self.rewards.team_score(),
            "pending_approval_count": len(approval_queue),
        }

    def _current_requests(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for event in events:
            request_id = event["id"]
            if "title" in event:
                item = dict(event)
                item["current_state"] = event["state"]
                item.setdefault("approval_required", self._payload_requires_approval(event))
                by_id[request_id] = item
            elif request_id in by_id:
                by_id[request_id]["current_state"] = event["state"]
                by_id[request_id]["last_reviewer"] = event.get("reviewer")
                by_id[request_id]["last_note"] = event.get("note")
                by_id[request_id]["updated_at"] = event.get("created_at")
        return list(by_id.values())

    def _payload_requires_approval(self, event: dict[str, Any]) -> bool:
        payload = event.get("payload") or {}
        tool = payload.get("tool") or payload.get("requested_tool")
        return self.tool_registry.requires_approval(str(tool)) if tool else True

    def _find_current_request(self, request_id: str) -> dict[str, Any] | None:
        for request in self._current_requests(self.requests.read_all()):
            if request.get("id") == request_id:
                return request
        return None

    def _award_transition_reward(
        self, request: dict[str, Any], state: RequestState, note: str
    ) -> dict[str, Any] | None:
        if state == RequestState.APPROVED:
            points = 1
            source = "request_approved"
            outcome_valence = 2
        elif state == RequestState.COMPLETED:
            points = 3
            source = "request_completed"
            outcome_valence = 6
        elif state == RequestState.REJECTED:
            points = -1
            source = "request_rejected"
            outcome_valence = -3
        elif state == RequestState.FAILED:
            points = -2
            source = "request_failed"
            outcome_valence = -6
        else:
            return None

        reference_id = f"{request['id']}:{state.value}"
        if any(
            reward.get("reference_id") == reference_id
            for reward in self.rewards.read_all()
        ):
            return None

        evidence = (
            f"{state.value}: {request.get('title', 'Untitled request')}. "
            f"Reviewer note: {note}"
        )
        return self.rewards.award(
            actor=str(request.get("actor") or "team"),
            points=points,
            source=source,
            evidence=evidence,
            reference_id=reference_id,
            outcome_valence=outcome_valence,
        )

    def _canonical_actor(self, actor: str) -> str:
        normalized = _normalize_actor(actor)
        for agent in self.scenario.get("agents", []):
            name = str(agent.get("name", ""))
            if _normalize_actor(name) == normalized:
                return name
        return actor


def _normalize_actor(actor: str) -> str:
    return str(actor).replace("_", " ").strip().lower()
