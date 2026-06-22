"""Optional world/economy arbiter — a Concordia-style "Game Master" (Phase 6c).

The arbiter adjudicates ambiguous Town Center requests / economy outcomes with a
consistent rubric, returning a verdict (approve / deny / partial), a rationale,
and a reward adjustment. It is **strictly opt-in**: nothing constructs an arbiter
unless ``CLAUDEVILLE_WORLD_ARBITER`` is enabled (or one is passed explicitly), so
the existing approval/reward path is byte-for-byte unchanged by default.

Two adjudication paths share one verdict shape:
- ``adjudicate`` (DEFAULT): a deterministic, no-LLM rubric. Pure, fast, and
  unit-testable. Used whenever the LLM path is unavailable or disabled.
- ``adjudicate_llm`` (OPT-IN within opt-in): consults a Claude judge ONLY when
  the arbiter is enabled AND the SDK is importable; it falls back to the
  deterministic rubric on any failure, so it never blocks a step.

HARD CONSTRAINTS (docs/DECISIONS.md):
- D-002: no vector embeddings. The deterministic rubric is keyword/heuristic.
- One unified LLM call per step for normal personas: the arbiter is NOT part of
  the per-persona step. Its (opt-in) LLM call is a separate, human-triggered or
  review-time adjudication, off the hot path.

Author: Claudeville Project
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any

# Verdicts the arbiter can return. ``partial`` means "approve with conditions /
# reduced scope"; the caller decides how to act on it (e.g. approve but with a
# trimmed reward adjustment).
VERDICT_APPROVE = "approve"
VERDICT_DENY = "deny"
VERDICT_PARTIAL = "partial"
VALID_VERDICTS = (VERDICT_APPROVE, VERDICT_DENY, VERDICT_PARTIAL)

# Env flag that turns the arbiter on. Accept the usual truthy spellings.
_ENABLE_ENV = "CLAUDEVILLE_WORLD_ARBITER"
_MODEL_ENV = "CLAUDEVILLE_CLAUDE_MODEL"
_TRUTHY = {"1", "true", "yes", "on"}

# Risk-tier reward ceilings: a verdict's reward adjustment is clamped into a band
# the request's risk justifies, so the arbiter can never mint runaway reward.
_RISK_REWARD_BAND = {
    "low": (0, 3),
    "medium": (-1, 5),
    "high": (-2, 8),
    "critical": (-3, 10),
}

# Keyword cues that argue FOR / AGAINST a request when the rubric scores it.
# Heuristic only (D-002): matched against the request title + rationale.
_SUPPORT_CUES = (
    "evidence",
    "approved",
    "validated",
    "research",
    "draft",
    "proposal",
    "follow-up",
    "follow up",
    "consent",
    "opt-in",
    "opt in",
    "reply",
    "warm lead",
)
_RISK_CUES = (
    "spam",
    "bulk",
    "mass",
    "scrape",
    "unsolicited",
    "cold blast",
    "buy list",
    "purchase list",
    "deception",
    "fake",
    "urgent spend",
    "wire",
    "credentials",
    "password",
)


@dataclass(frozen=True)
class ArbiterVerdict:
    """A single adjudication outcome (shared by the deterministic + LLM paths)."""

    verdict: str
    rationale: str
    reward_adjustment: int
    confidence: float
    source: str  # "rubric" | "llm" | "llm_fallback_rubric"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def arbiter_enabled() -> bool:
    """True only when the env flag explicitly enables the arbiter (OFF default)."""
    return os.environ.get(_ENABLE_ENV, "").strip().lower() in _TRUTHY


def _clamp_reward(value: int, risk_level: str) -> int:
    """Clamp a reward adjustment into the band the request's risk justifies."""
    lo, hi = _RISK_REWARD_BAND.get(str(risk_level).lower(), _RISK_REWARD_BAND["high"])
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        value = 0
    return max(lo, min(hi, value))


def _request_text(request: dict[str, Any]) -> str:
    """Concatenate the human-readable fields of a request for keyword scoring."""
    parts = [
        str(request.get("title", "")),
        str(request.get("rationale", "")),
        str(request.get("type", "")),
    ]
    payload = request.get("payload") or {}
    if isinstance(payload, dict):
        parts.append(str(payload.get("tool") or payload.get("requested_tool") or ""))
        parts.append(str(payload.get("note", "")))
    return " ".join(p for p in parts if p).lower()


class WorldArbiter:
    """Adjudicates ambiguous requests with a consistent, auditable rubric.

    Construction is cheap and side-effect free. The deterministic path
    (``adjudicate``) never touches the network; the LLM path (``adjudicate_llm``)
    is only reachable when explicitly invoked and degrades to the rubric on any
    failure.
    """

    def __init__(
        self,
        *,
        policy: dict[str, Any] | None = None,
        model: str | None = None,
    ):
        # ``policy`` is the scenario.real_world_policy block (forbidden behaviors,
        # blocked tools). Optional: the rubric works without it.
        self.policy = policy or {}
        self.model = model or os.environ.get(_MODEL_ENV, "claude-sonnet-4-6")

    # --------------------------------------------------------------- rubric path
    def adjudicate(
        self, request: dict[str, Any], *, risk_level: str = "high"
    ) -> ArbiterVerdict:
        """Deterministic, no-LLM adjudication. Pure and unit-testable.

        Scores keyword support vs. risk cues, checks the request against the
        scenario's forbidden behaviors / blocked tools, and returns a verdict
        plus a risk-banded reward adjustment. Identical inputs always yield an
        identical verdict (no randomness, no clock, no network).
        """
        text = _request_text(request)
        support = sum(1 for cue in _SUPPORT_CUES if cue in text)
        risk = sum(1 for cue in _RISK_CUES if cue in text)

        forbidden_hit = self._forbidden_hit(text)
        score = support - risk - (3 if forbidden_hit else 0)

        if forbidden_hit:
            verdict = VERDICT_DENY
            reward = _clamp_reward(-2, risk_level)
            rationale = (
                f"Denied: request matches a forbidden behavior "
                f"('{forbidden_hit}'). The team objective requires legal, "
                f"consent-based actions."
            )
            confidence = 0.9
        elif score >= 2:
            verdict = VERDICT_APPROVE
            reward = _clamp_reward(2 + support, risk_level)
            rationale = (
                f"Approved: {support} supporting signal(s) outweigh {risk} risk "
                f"cue(s); the request is grounded and within policy."
            )
            confidence = 0.7 + min(0.2, 0.05 * support)
        elif score <= -1:
            verdict = VERDICT_DENY
            reward = _clamp_reward(-1, risk_level)
            rationale = (
                f"Denied: {risk} risk cue(s) dominate {support} supporting "
                f"signal(s); the request is too risky/ungrounded to approve."
            )
            confidence = 0.65
        else:
            verdict = VERDICT_PARTIAL
            reward = _clamp_reward(1, risk_level)
            rationale = (
                "Partial: the request is plausible but under-justified; approve "
                "a reduced scope and request more evidence before full credit."
            )
            confidence = 0.5

        return ArbiterVerdict(
            verdict=verdict,
            rationale=rationale,
            reward_adjustment=reward,
            confidence=round(confidence, 3),
            source="rubric",
        )

    def _forbidden_hit(self, text: str) -> str | None:
        """Return the first forbidden behavior present in ``text``, else None."""
        forbidden = self.policy.get("forbidden_behaviors") or []
        for behavior in forbidden:
            token = str(behavior).replace("_", " ").strip().lower()
            if token and token in text:
                return str(behavior)
        return None

    # ------------------------------------------------------------------ LLM path
    def build_prompt(self, request: dict[str, Any], objective: str = "") -> str:
        """Build the (opt-in) Game-Master adjudication prompt for a request."""
        payload = request.get("payload") or {}
        tool = ""
        if isinstance(payload, dict):
            tool = str(payload.get("tool") or payload.get("requested_tool") or "")
        forbidden = ", ".join(
            str(b) for b in (self.policy.get("forbidden_behaviors") or [])
        ) or "(none specified)"
        return f"""You are the Game Master adjudicating a request in a cooperative \
business simulation. Apply a consistent rubric and respond with ONLY a JSON \
object.

TEAM OBJECTIVE: {objective or "(unspecified)"}
FORBIDDEN BEHAVIORS: {forbidden}

REQUEST
- title: {request.get('title', '')}
- type: {request.get('type', '')}
- tool: {tool or '(none)'}
- rationale: {request.get('rationale', '')}

Decide a verdict and a reward adjustment (an integer; positive rewards genuine \
progress, negative penalizes risky/forbidden actions, 0 is neutral). Respond with \
ONLY this JSON shape:
{{"verdict": "approve|deny|partial", "reward_adjustment": 0, \
"rationale": "one concise sentence"}}"""

    def adjudicate_llm(
        self,
        request: dict[str, Any],
        *,
        objective: str = "",
        risk_level: str = "high",
        timeout: float = 60.0,
    ) -> ArbiterVerdict:
        """Adjudicate via a Claude judge, falling back to the rubric on failure.

        This is the ONLY method that may touch the network, and only when the
        SDK imports cleanly. Any error (no SDK, timeout, unparseable response)
        returns the deterministic rubric verdict tagged ``llm_fallback_rubric``
        so a hung/absent model never blocks adjudication.
        """
        try:
            import claude_agent_sdk  # noqa: F401
        except Exception:
            return self._fallback(request, risk_level)

        prompt = self.build_prompt(request, objective)
        try:
            import asyncio

            text = asyncio.run(self._query(prompt, timeout))
        except Exception:
            return self._fallback(request, risk_level)

        parsed = parse_arbiter_response(text)
        if not parsed:
            return self._fallback(request, risk_level)
        return ArbiterVerdict(
            verdict=parsed["verdict"],
            rationale=parsed["rationale"],
            reward_adjustment=_clamp_reward(parsed["reward_adjustment"], risk_level),
            confidence=0.8,
            source="llm",
        )

    def _fallback(
        self, request: dict[str, Any], risk_level: str
    ) -> ArbiterVerdict:
        base = self.adjudicate(request, risk_level=risk_level)
        return ArbiterVerdict(
            verdict=base.verdict,
            rationale=base.rationale,
            reward_adjustment=base.reward_adjustment,
            confidence=base.confidence,
            source="llm_fallback_rubric",
        )

    async def _query(self, prompt: str, timeout: float) -> str:
        """Send one prompt through a connected SDK client; return the result text."""
        import asyncio

        from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
        from claude_agent_sdk.types import ResultMessage

        options = ClaudeAgentOptions(
            allowed_tools=[],
            permission_mode="bypassPermissions",
            model=self.model,
        )
        client = ClaudeSDKClient(options)
        await asyncio.wait_for(client.connect(), timeout=30.0)
        try:
            await client.query(prompt)
            result_text = ""
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    result_text = message.result or ""
            return result_text
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass


def parse_arbiter_response(text: str) -> dict[str, Any] | None:
    """Parse a Game-Master JSON response, coercing verdict + reward to safe values.

    Returns None when no JSON object is present so the caller can fall back.
    """
    if not isinstance(text, str):
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return None

    verdict = str(data.get("verdict", "")).strip().lower()
    if verdict not in VALID_VERDICTS:
        return None
    try:
        reward = int(round(float(data.get("reward_adjustment", 0))))
    except (TypeError, ValueError):
        reward = 0
    rationale = str(data.get("rationale", "")).strip()
    return {
        "verdict": verdict,
        "reward_adjustment": reward,
        "rationale": rationale,
    }


def build_arbiter(
    policy: dict[str, Any] | None = None,
    *,
    force: bool = False,
) -> WorldArbiter | None:
    """Return a configured arbiter ONLY when enabled (OFF by default).

    ``force=True`` constructs one regardless of the env flag (used by tests and
    by callers that pass an explicit opt-in). Returns None otherwise, which is
    the signal to the Town Center to keep the unchanged legacy path.
    """
    if force or arbiter_enabled():
        return WorldArbiter(policy=policy)
    return None
