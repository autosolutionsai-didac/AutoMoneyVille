"""Command-line adapter for the Claudeville tilemap compiler."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.mapgen import build_tilemap


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=build_tilemap.__doc__)
    parser.add_argument("--source", type=Path, default=build_tilemap.AUTHORING_MAP)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--promote", type=Path, metavar="CANDIDATE_WORLD_JSON")
    parser.add_argument("--approved-source-sha256")
    args = parser.parse_args(argv)
    try:
        if args.promote:
            if not args.approved_source_sha256:
                parser.error("--promote requires --approved-source-sha256")
            path = build_tilemap.promote_candidate(
                args.promote,
                approved_source_sha256=args.approved_source_sha256,
            )
            print(f"Promoted {path}")
            return 0
        result = build_tilemap.build_candidate(
            args.source,
            candidate_root=args.candidate_root,
        )
    except (OSError, build_tilemap.TilemapError) as exc:
        parser.error(str(exc))
    print(
        f"Built {result.map_path} and {result.preview_path}; "
        "collision mismatches=0"
    )
    return 0
