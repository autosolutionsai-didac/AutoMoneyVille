"""Validation helpers for the hand-authored Claudeville middle district."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

Placement = tuple[str, str, str, str, str, int, int]

REPO_ROOT = Path(__file__).resolve().parents[2]
V2_CATALOG = REPO_ROOT / "output/claudeville/modern_pixels_v2/catalog.json"
V3_CATALOG = REPO_ROOT / "output/claudeville/modern_interiors_v3/catalog.json"


def _read_catalog(path: Path) -> dict[str, dict]:
    root = json.loads(path.read_text(encoding="utf-8"))
    records = root.get("props") if isinstance(root, dict) else None
    if not isinstance(records, list):
        raise ValueError(f"malformed prop catalog: {path}")
    result = {item.get("asset_key"): item for item in records if isinstance(item, dict)}
    if len(result) != len(records) or None in result:
        raise ValueError(f"malformed or duplicate prop key: {path}")
    return result


def validate_catalogs(
    placements: tuple[Placement, ...],
    v2_path: Path = V2_CATALOG,
    v3_path: Path = V3_CATALOG,
) -> dict[str, int]:
    """Validate placements against the curated licensed native-16 catalogs."""
    v2, v3 = _read_catalog(v2_path), _read_catalog(v3_path)
    counts = Counter()
    allowed_v3 = {
        "Community Center": {"community_center"},
        "Claudeville Cafe": {"cafe", "cafeteria", "public_facilities"},
        "Library": {"library"},
    }
    forbidden = ("free", "32x32", "48x48", ".zip", "generator", ".exe")
    for sector, _zone, _role, _cluster, key, _x, _y in placements:
        record = v2.get(key) or v3.get(key)
        if record is None:
            raise ValueError(f"unknown middle-row asset: {key}")
        size = record.get("native_size")
        if not (
            isinstance(size, list)
            and len(size) == 2
            and all(
                isinstance(value, int) and value > 0 and value % 16 == 0
                for value in size
            )
        ):
            raise ValueError(f"asset is not native-16 aligned: {key}")
        source = str(record.get("source", "")).casefold()
        if any(token in source for token in forbidden):
            raise ValueError(f"forbidden middle-row source: {key}")
        if key in v3 and sector in allowed_v3:
            purposes = set(record.get("purposes", []))
            if not purposes & allowed_v3[sector]:
                raise ValueError(f"asset purpose is incompatible with {sector}: {key}")
        counts[str(record.get("pack", "unknown"))] += 1
    return dict(sorted(counts.items()))


def validate(
    placements: tuple[Placement, ...],
    bounds_by_sector: dict[str, tuple[int, int, int, int]],
    required_roles: dict[str, set[str]],
) -> None:
    positions: set[tuple[str, int, int]] = set()
    roles: dict[str, set[str]] = {sector: set() for sector in required_roles}
    clusters: Counter[tuple[str, str]] = Counter()
    for placement in placements:
        sector, _zone, role, cluster, key, x, y = placement
        bounds = bounds_by_sector.get(sector)
        if bounds is None or not (
            bounds[0] <= x < bounds[2] and bounds[1] <= y <= bounds[3]
        ):
            raise ValueError(f"middle-row placement left its traced footprint: {placement}")
        identity = (sector, x, y)
        if identity in positions:
            raise ValueError(f"middle-row props share a foot position: {identity}")
        if not key.startswith("prop.") or not cluster.strip() or not role.strip():
            raise ValueError(f"malformed middle-row placement: {placement}")
        positions.add(identity)
        roles[sector].add(role)
        clusters[(sector, cluster)] += 1
    for sector, required in required_roles.items():
        missing = required - roles[sector]
        if missing:
            raise ValueError(f"{sector} is missing interaction art: {sorted(missing)}")
    singletons = sorted(
        f"{sector}:{cluster}"
        for (sector, cluster), count in clusters.items()
        if count == 1 and cluster not in {"dispatch table", "east reading support"}
    )
    if singletons:
        raise ValueError(f"unpaired purpose clusters: {singletons}")
