"""Town-center store for requests, tools, rewards, and scenario state."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

try:
    from . import tool_executor
    from .economy import (
        ArtifactLedger,
        RequestLedger,
        RequestState,
        RewardLedger,
        ToolRegistry,
    )
    from .scenario_config import load_scenario
    from .world_arbiter import WorldArbiter, build_arbiter
except ImportError:
    import tool_executor
    from economy import (
        ArtifactLedger,
        RequestLedger,
        RequestState,
        RewardLedger,
        ToolRegistry,
    )
    from scenario_config import load_scenario
    from world_arbiter import WorldArbiter, build_arbiter

# Most-recent executed-tool artifacts surfaced in snapshot() for the console.
_SNAPSHOT_ARTIFACTS = 20


class TownCenterStore:
    """Persistent local store for the governed money-agent control plane."""

    def __init__(
        self,
        root: str | Path,
        scenario_id: str = "startup_team_v1",
        *,
        arbiter: WorldArbiter | None = None,
    ):
        self.root = Path(root) / "town_center"
        self.scenario_id = scenario_id
        self.scenario = load_scenario(scenario_id)
        self.tool_registry = ToolRegistry.default()
        self.requests = RequestLedger(self.root / "requests.jsonl")
        self.rewards = RewardLedger(self.root / "rewards.jsonl")
        self.artifacts = ArtifactLedger(self.root / "artifacts.jsonl")
        # Phase 6c: optional Game-Master arbiter. Constructed ONLY when explicitly
        # passed or enabled via CLAUDEVILLE_WORLD_ARBITER. None (the default) keeps
        # the legacy approval/reward path byte-for-byte unchanged.
        self.arbiter: WorldArbiter | None = arbiter or build_arbiter(
            self.scenario.get("real_world_policy")
        )

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
            # getattr(.value) also normalizes a RequestState from the OTHER
            # import path (bare `economy` vs package `reverie.backend_server.
            # economy` are distinct classes; str() on a foreign member would
            # yield "RequestState.COMPLETED" and fail the value lookup).
            state = RequestState(getattr(state, "value", None) or str(state))
        current_request = self._find_current_request(request_id)
        transition = self.requests.transition(
            request_id,
            state,
            reviewer=reviewer,
            note=note,
        )
        # Stage 1: a completed request actually EXECUTES its tool (read-only
        # research runs for real or returns an honest stub; outbound/spend tools
        # are dry-run only). The result is attached so callers can ground the
        # requesting persona's memory in the real outcome.
        if current_request and state == RequestState.COMPLETED:
            transition["tool_result"] = self._execute_request_tool(current_request)
            transition["actor"] = current_request.get("actor")
            self._persist_artifact(current_request, transition["tool_result"])
        if current_request:
            self._award_transition_reward(current_request, state, note)
        return transition

    def _execute_request_tool(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run the request's tool via the execution layer; return a result dict."""
        payload = request.get("payload") or {}
        tool = payload.get("tool") or payload.get("requested_tool")
        # Carry the request title as a query hint for research tools.
        exec_payload = dict(payload)
        exec_payload.setdefault("query", request.get("title", ""))
        result = tool_executor.execute(
            tool, exec_payload, persona_name=str(request.get("actor") or "")
        )
        return result.to_dict()

    def _persist_artifact(
        self, request: dict[str, Any], tool_result: dict[str, Any]
    ) -> None:
        """Append the executed ToolResult to artifacts.jsonl so dry-run drafts
        and research evidence survive the HTTP response and stay auditable."""
        self.artifacts.record(
            request_id=str(request.get("id") or ""),
            actor=str(request.get("actor") or ""),
            title=str(request.get("title") or ""),
            tool_result=tool_result,
        )

    def adjudicate_request(
        self, request_id: str, *, use_llm: bool = False
    ) -> dict[str, Any] | None:
        """Adjudicate a request with the Game-Master arbiter, if one is configured.

        Returns the verdict dict (verdict / rationale / reward_adjustment /
        confidence / source) and applies the reward adjustment to the ledger, or
        None when no arbiter is configured (the default) — in which case the
        caller falls back to the unchanged human-approval path. Behavior-
        preserving: with the arbiter OFF this method is a no-op returning None.
        """
        if self.arbiter is None:
            return None
        request = self._find_current_request(request_id)
        if not request:
            return None

        risk_level = self._risk_level_for(request)
        objective = str(self.scenario.get("objective", ""))
        if use_llm:
            verdict = self.arbiter.adjudicate_llm(
                request, objective=objective, risk_level=risk_level
            )
        else:
            verdict = self.arbiter.adjudicate(request, risk_level=risk_level)

        adjustment = int(verdict.reward_adjustment)
        if adjustment:
            reference_id = f"{request_id}:arbiter:{verdict.verdict}"
            already = any(
                r.get("reference_id") == reference_id
                for r in self.rewards.read_all()
            )
            if not already:
                self.rewards.award(
                    actor=str(request.get("actor") or "team"),
                    points=adjustment,
                    source=f"arbiter_{verdict.verdict}",
                    evidence=verdict.rationale,
                    reference_id=reference_id,
                )
        return verdict.to_dict()

    def _risk_level_for(self, request: dict[str, Any]) -> str:
        """Best-effort risk tier for a request from its requested tool."""
        payload = request.get("payload") or {}
        tool = payload.get("tool") or payload.get("requested_tool")
        if tool:
            try:
                return self.tool_registry.get(str(tool)).risk_level
            except KeyError:
                pass
        return "high"

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
            "artifacts": self.artifacts.read_all()[-_SNAPSHOT_ARTIFACTS:],
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

    def find_request(self, request_id: str) -> dict[str, Any] | None:
        """Public lookup of a request's current view (None if unknown) — lets
        API callers validate an id before acting on it (e.g. record-delivery)."""
        return self._find_current_request(request_id)

    def _award_transition_reward(
        self, request: dict[str, Any], state: RequestState, note: str
    ) -> dict[str, Any] | None:
        revenue_cents = 0
        if state == RequestState.APPROVED:
            points = 1
            source = "request_approved"
            outcome_valence = 2
        elif state == RequestState.COMPLETED:
            points = 3
            source = "request_completed"
            outcome_valence = 6
            # Stage 1 de-fiction: revenue is NO LONGER credited from the agent's
            # self-reported `expected_payoff`. Completing a request earns effort
            # points only; real revenue is credited solely via `record_delivery`
            # against human-confirmed evidence (see below). revenue_cents stays 0.
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
            revenue_cents=revenue_cents,
            reference_id=reference_id,
            outcome_valence=outcome_valence,
        )

    def record_delivery(
        self,
        request_id: str,
        *,
        revenue_cents: int,
        evidence: str,
        reviewer: str = "human",
    ) -> dict[str, Any] | None:
        """Credit HUMAN-CONFIRMED revenue against a delivered request (Stage 1.4).

        This is the ONLY path to `revenue_cents`, replacing the old self-reported
        `expected_payoff` credit. It requires an explicit amount + evidence from a
        human reviewer and is idempotent per request. Returns the reward row, or
        None if already recorded.
        """
        revenue_cents = max(0, int(revenue_cents or 0))
        request = self._find_current_request(request_id)
        actor = str((request or {}).get("actor") or "team")
        reference_id = f"{request_id}:delivered"
        if any(
            r.get("reference_id") == reference_id for r in self.rewards.read_all()
        ):
            return None
        return self.rewards.award(
            actor=actor,
            points=0,
            source="revenue_confirmed",
            evidence=f"delivered ({reviewer}): {evidence}",
            revenue_cents=revenue_cents,
            reference_id=reference_id,
            outcome_valence=8,
        )

    def recent_requests_for(
        self, actor: str, limit: int = 3
    ) -> list[dict[str, Any]]:
        """Most-recent requests proposed by `actor`, with their current state — used to
        feed request outcomes back into the agent's next decision."""
        norm = _normalize_actor(actor)
        mine = [
            r
            for r in self._current_requests(self.requests.read_all())
            if _normalize_actor(str(r.get("actor", ""))) == norm
        ]
        return mine[-limit:]

    def recent_team_deliverables(
        self, exclude_actor: str, limit: int = 4
    ) -> list[dict[str, Any]]:
        """Recent requests by OTHER team members (most-recent first), so a persona
        can SEE and BUILD ON what teammates produced — enabling research → offer →
        outreach handoffs that isolated, self-only feedback never surfaced. Prefers
        completed/approved deliverables over still-proposed ones."""
        norm = _normalize_actor(exclude_actor)
        others = [
            r
            for r in self._current_requests(self.requests.read_all())
            if _normalize_actor(str(r.get("actor", ""))) != norm
        ]
        done = [
            r
            for r in others
            if str(r.get("current_state", "")).lower() in ("completed", "approved")
        ]
        return (done or others)[-limit:]

    def _canonical_actor(self, actor: str) -> str:
        normalized = _normalize_actor(actor)
        for agent in self.scenario.get("agents", []):
            name = str(agent.get("name", ""))
            if _normalize_actor(name) == normalized:
                return name
        return actor


def _normalize_actor(actor: str) -> str:
    return str(actor).replace("_", " ").strip().lower()


def _payoff_cents(payload: dict[str, Any]) -> int:
    """Best-effort parse of an expected payoff (dollars) from a request payload into
    cents. Accepts a number or a string like '$50', '50 USD', '1,200'."""
    import re

    val = payload.get("expected_payoff", payload.get("payoff"))
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return max(0, int(round(float(val) * 100)))
    match = re.search(r"(\d+(?:\.\d+)?)", str(val).replace(",", ""))
    return int(round(float(match.group(1)) * 100)) if match else 0
