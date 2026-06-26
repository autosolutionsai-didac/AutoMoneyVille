"""Helpers that turn persona decisions into Town Center requests."""

from __future__ import annotations

from typing import Any

try:
    from .event_ledger import EventLedger
    from .town_center import TownCenterStore
except ImportError:
    from event_ledger import EventLedger
    from town_center import TownCenterStore


def submit_town_request_from_step(
    town_center: TownCenterStore,
    *,
    actor: str,
    step_response: Any,
    event_ledger: EventLedger | None = None,
    step: int | None = None,
    sim_time: str | None = None,
) -> dict[str, Any] | None:
    """Persist a parsed persona Town Center request, if one was proposed."""
    town_request = getattr(step_response, "town_request", None)
    if not town_request:
        return None

    payload = dict(getattr(town_request, "payload", {}) or {})
    payload.setdefault("source", "persona_step")

    request = town_center.submit_request(
        actor=actor,
        request_type=str(getattr(town_request, "request_type", "resource")),
        title=str(getattr(town_request, "title", "")),
        rationale=str(getattr(town_request, "rationale", "")),
        payload=payload,
    )

    # Safe (no-approval) tools resolve in-sim immediately: the agent did the
    # research/draft itself, so auto-complete and credit the effort. Risky/external
    # tools stay PROPOSED and wait for human approval. (Sim policy, kept out of the
    # store so submit_request stays a pure PROPOSED append.)
    if not request.get("approval_required", True):
        try:
            transition = town_center.transition_request(
                request["id"],
                "completed",
                reviewer="auto",
                note="auto-completed (safe tool, no approval needed)",
            )
            # Carry the executed tool's result so the caller can ground the
            # requesting persona's memory in the real outcome (Stage 1).
            if isinstance(transition, dict) and transition.get("tool_result"):
                request["tool_result"] = transition["tool_result"]
        except Exception:
            pass

    if event_ledger:
        event_ledger.append(
            "town_request_submitted",
            actor=actor,
            step=step,
            sim_time=sim_time,
            payload={
                "request_id": request["id"],
                "request_type": request["type"],
                "title": request["title"],
                "approval_required": request.get("approval_required", True),
                "tool": payload.get("tool") or payload.get("requested_tool"),
            },
        )

    return request


def submit_latest_town_request(
    town_center: TownCenterStore,
    *,
    actor: str,
    persona: Any,
    event_ledger: EventLedger | None = None,
    step: int | None = None,
    sim_time: str | None = None,
) -> dict[str, Any] | None:
    """Submit a persona's latest parsed request once, then clear it."""
    step_response = getattr(persona, "last_step_response", None)
    if not step_response:
        return None

    try:
        return submit_town_request_from_step(
            town_center,
            actor=actor,
            step_response=step_response,
            event_ledger=event_ledger,
            step=step,
            sim_time=sim_time,
        )
    finally:
        persona.last_step_response = None
