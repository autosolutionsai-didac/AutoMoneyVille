"""Dependency-free text sanitization for untrusted content (LLM-1).

Agent dialogue, recalled chat, and tool output are UNTRUSTED: before any of it
enters a persona's prompt it must not be able to forge prompt structure (=== headers,
``` fences) or control directives. Kept dependency-free so both the prompt layer
(claude_structure) and the economy layer (tool_executor) can import it without
pulling in heavy runtime modules.
"""

from __future__ import annotations

UNTRUSTED_MAX_LEN = 600


def sanitize_external(text: object) -> str:
    """Neutralize untrusted text for safe inclusion in a prompt as quoted content."""
    if text is None:
        return ""
    s = str(text)
    # Break our own structural markers so embedded text can't forge a
    # "=== SECTION ===" header or a ```json fenced block.
    s = s.replace("```", "`'`").replace("===", "= =")
    # Neutralize the JSON control keys that map to privileged actions if they
    # appear in key form (only ever seen in injection attempts, not real speech).
    for key in ('"town_request"', '"action"', '"continuing"', '"schedule_update"'):
        s = s.replace(key, key.replace('"', "'"))
    # Collapse newlines so a single utterance can't open a multi-line fake block.
    s = s.replace("\r", " ").replace("\n", " / ").strip()
    if len(s) > UNTRUSTED_MAX_LEN:
        s = s[:UNTRUSTED_MAX_LEN] + "…"
    return s
