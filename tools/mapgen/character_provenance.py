"""Verify Claudeville resident assets against their licensed source files."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError


class ProvenanceError(ValueError):
    """Raised when paid-pack evidence or resident provenance has drifted."""


def validate_paid_source(source_root, evidence_paths, sheet_size, png_size) -> Path:
    """Return a paid source root only when its license evidence is complete."""
    try:
        root = Path(source_root).expanduser().resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise ProvenanceError("source root is missing or inaccessible") from exc
    evidence = {}
    for key, relative in evidence_paths.items():
        candidate = (root / relative).resolve(strict=False)
        if root not in candidate.parents or not candidate.is_file():
            raise ProvenanceError(f"missing {key}: {relative}")
        evidence[key] = candidate
    try:
        license_text = evidence["license"].read_text(encoding="utf-8").lower()
        readme = evidence["readme"].read_text(encoding="utf-8").lower().replace("_", " ")
        third_party = evidence["third_party"].read_text(encoding="utf-8").lower()
    except (OSError, UnicodeError) as exc:
        raise ProvenanceError("license or provenance text is unreadable") from exc
    if "full version license" not in license_text or "limezu.itch.io" not in license_text:
        raise ProvenanceError("license does not identify the credited full version")
    if "modern interiors" not in readme or "0a3r" not in third_party:
        raise ProvenanceError("pack or generator provenance is incomplete")
    if png_size(evidence["premade"], "paid premade") not in {sheet_size, (896, 656)}:
        raise ProvenanceError("paid 16x16 character source has an invalid layout")
    if min(png_size(evidence["guide"], "animation guide")) < 32:
        raise ProvenanceError("animation guide is invalid")
    return root


def validate_paid_provenance(
    manifest, static, source, candidate_names, source_specs, user_kind, sheet_size,
    contained, digest, png_size, component_path, compose, portrait_from_sheet,
) -> None:
    """Bind the manifest's hashes and composites to the supplied source files."""
    actual_candidates = {
        filename: digest(contained(source, f"characters/{filename}", filename))
        for filename in candidate_names
    }
    if manifest["curation_audit"]["candidate_hashes"] != actual_candidates:
        raise ProvenanceError("curation candidate hashes do not match supplied sources")
    for resident in manifest["residents"]:
        name, provenance = resident["name"], resident["provenance"]
        expected_kind, expected_spec = source_specs[name]
        sprite = contained(static, resident["sprite_url"], f"{name} sprite_url")
        if resident["source"] != expected_kind:
            raise ProvenanceError(f"{name} source kind does not match its approved selection")
        if expected_kind == user_kind:
            expected_asset = f"characters/{expected_spec}"
            if provenance.get("source_asset") != expected_asset:
                raise ProvenanceError(f"{name} source asset does not match its approved selection")
            source_sheet = contained(source, expected_asset, f"{name} source asset")
            if png_size(source_sheet, f"{name} source asset") != sheet_size:
                raise ProvenanceError(f"{name} source asset must be 896x640")
            if digest(source_sheet) != provenance.get("source_sha256"):
                raise ProvenanceError(f"{name} source SHA-256 does not match supplied source")
            composed = None
        else:
            components = [
                {"role": role, "path": path, "sha256": digest(component_path(source, path))}
                for role, path in expected_spec
            ]
            if provenance.get("components") != components:
                raise ProvenanceError(f"{name} component provenance does not match supplied sources")
            composed, _metadata, recipe_hash = compose(source, expected_spec)
            if provenance.get("recipe_sha256") != recipe_hash:
                raise ProvenanceError(f"{name} recipe SHA-256 does not match supplied components")
        try:
            with Image.open(sprite) as opened:
                runtime = opened.convert("RGBA")
        except (OSError, SyntaxError, UnidentifiedImageError, ValueError) as exc:
            raise ProvenanceError(f"{name} runtime sprite is unreadable") from exc
        if composed is not None and runtime.tobytes() != composed.tobytes():
            raise ProvenanceError(f"{name} runtime sprite does not match declared components")
        portrait = contained(static, resident["portrait_url"], f"{name} portrait_url")
        try:
            with Image.open(portrait) as opened:
                actual_portrait = opened.convert("RGBA")
        except (OSError, SyntaxError, UnidentifiedImageError, ValueError) as exc:
            raise ProvenanceError(f"{name} portrait is unreadable") from exc
        expected_portrait = portrait_from_sheet(runtime)
        if (actual_portrait.size != expected_portrait.size or
                actual_portrait.tobytes() != expected_portrait.tobytes()):
            raise ProvenanceError(f"{name} portrait does not match its approved sprite")
