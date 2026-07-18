"""Validated JSON and logical-point boundaries for Claudeville compilation."""

from __future__ import annotations

import json
from pathlib import Path

LOGICAL_WIDTH, LOGICAL_HEIGHT = 88, 48
Point = tuple[int, int]


class SemanticCompileError(ValueError):
    """Raised when authored visuals and semantic metadata disagree."""


def read_json(path: Path) -> dict:
    """Read one required JSON object with a stable compiler-facing error."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SemanticCompileError(f"invalid JSON input: {path}") from exc
    if not isinstance(value, dict):
        raise SemanticCompileError(f"JSON root must be an object: {path}")
    return value


def atomic_json(path: Path, payload: dict) -> None:
    """Replace one generated JSON contract atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def logical_point(value: object, label: str) -> Point:
    """Validate one authored point at the logical-grid boundary."""
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 2
        or any(not isinstance(item, int) or isinstance(item, bool) for item in value)
    ):
        raise SemanticCompileError(f"{label} must be an integer point")
    point = (value[0], value[1])
    if not (0 <= point[0] < LOGICAL_WIDTH and 0 <= point[1] < LOGICAL_HEIGHT):
        raise SemanticCompileError(f"{label} is outside the logical grid")
    return point
