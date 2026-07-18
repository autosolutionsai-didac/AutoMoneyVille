"""Rendering and catalog writer for curated Claudeville design stamps."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from tools.mapgen import curate_claudeville_design_stamps as stamps


def png_stamp(spec: dict) -> tuple[Image.Image, tuple[int, int], list[dict]]:
    result = Image.new("RGBA", spec["size"], (0, 0, 0, 0))
    evidence = []
    try:
        for path, digest in spec["sources"]:
            layer = stamps._verified_png(path, digest, spec["size"])
            result.alpha_composite(layer)
            layer.close()
            evidence.append({"name": path.name, "sha256": digest})
        if spec["pieces"]:
            working = Image.new("RGBA", spec["output_size"], (0, 0, 0, 0))
            for crop, destination in spec["pieces"]:
                piece = result.crop(crop)
                working.alpha_composite(piece, destination)
                piece.close()
        else:
            working = result.crop(spec["crop"]) if spec["crop"] else result
        try:
            if spec["trim"]:
                return (*stamps._trim(working), evidence)
            if working.getchannel("A").getbbox() is None:
                raise stamps.StampCurationError("design stamp crop rendered empty")
            return working.copy(), (0, 0), evidence
        finally:
            if working is not result:
                working.close()
    finally:
        result.close()


def composite_png_stamp(
    spec: dict,
) -> tuple[Image.Image, tuple[int, int], list[dict]]:
    result = Image.new("RGBA", spec["output_size"], (0, 0, 0, 0))
    sources: dict[Path, Image.Image] = {}
    evidence = []
    try:
        for path, digest, source_size, crop, destination in spec["source_pieces"]:
            if path not in sources:
                sources[path] = stamps._verified_png(path, digest, source_size)
                evidence.append({"name": path.name, "sha256": digest})
            source = sources[path]
            left, top, right, bottom = crop
            x, y = destination
            if not (
                0 <= left < right <= source.width
                and 0 <= top < bottom <= source.height
                and 0 <= x <= result.width - (right - left)
                and 0 <= y <= result.height - (bottom - top)
            ):
                raise stamps.StampCurationError(
                    f"invalid graystone frontage piece: {path.name}"
                )
            piece = source.crop(crop)
            result.alpha_composite(piece, destination)
            piece.close()
        if result.getchannel("A").getbbox() is None:
            raise stamps.StampCurationError("graystone frontage rendered empty")
    except Exception:
        result.close()
        raise
    finally:
        for source in sources.values():
            source.close()
    return result, (0, 0), evidence


def curate(output_root: Path = stamps.OUTPUT_ROOT) -> dict:
    """Write only the used, composited design stamps and their evidence."""
    output = Path(output_root).expanduser().resolve(strict=False)
    output.mkdir(parents=True, exist_ok=True)
    for filename in stamps.RETIRED_OUTPUT_FILES:
        (output / filename).unlink(missing_ok=True)
    records = []
    for spec in stamps.OFFICE_STAMPS:
        image, trim = stamps._office_stamp(spec)
        try:
            target = output / spec["file"]
            stamps._write_png(target, image)
            records.append(
                {
                    "asset_key": spec["asset_key"],
                    "file": spec["file"],
                    "native_size": list(image.size),
                    "pack": spec["pack"],
                    "source_sha256": spec["sha256"],
                    "trim_offset": list(trim),
                    "output_sha256": stamps._digest(target),
                }
            )
        finally:
            image.close()
    jobs = (
        *((spec, png_stamp) for spec in stamps.PNG_STAMPS),
        *((spec, composite_png_stamp) for spec in stamps.COMMUNITY_PRESENTATION_STAMPS),
        *((spec, composite_png_stamp) for spec in stamps.GRAYSTONE_FRONTAGE_STAMPS),
    )
    for spec, renderer in jobs:
        image, trim, evidence = renderer(spec)
        try:
            target = output / spec["file"]
            stamps._write_png(target, image)
            records.append(
                {
                    "asset_key": spec["asset_key"],
                    "file": spec["file"],
                    "native_size": list(image.size),
                    "pack": spec["pack"],
                    "sources": evidence,
                    "trim_offset": list(trim),
                    "output_sha256": stamps._digest(target),
                }
            )
        finally:
            image.close()
    catalog = {
        "generated_by": "tools/mapgen/curate_claudeville_design_stamps.py",
        "license_scope": "Curated derivatives only; vendor sources are not shipped.",
        "pack_credits": stamps._pack_credits(),
        "records": sorted(records, key=lambda item: item["asset_key"]),
        "schema_version": 1,
    }
    stamps._write_json(output / "catalog.json", catalog)
    return catalog


def main() -> int:
    catalog = curate()
    print(f"Curated {len(catalog['records'])} licensed Claudeville design stamps")
    return 0
