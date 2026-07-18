"""Curate and validate Claudeville's licensed Modern Pixels residents."""

from __future__ import annotations

import argparse
import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Union

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

if __package__:
    from tools.mapgen import character_provenance as provenance
else:  # Support direct `python tools/mapgen/character_manifest.py` validation.
    import character_provenance as provenance

PathLike = Union[str, Path]
CONTACT_SHEET_LABEL = "CLAUDEVILLE RESIDENT REVIEW - NATIVE 16x32"
CONTACT_SHEET_SIZE = (1000, 500)
SHEET_SIZE = (896, 640)
FRAME_SIZE = (16, 32)
ACTIVE_RESIDENTS = ("Nora Vale", "Milo Chen", "Iris Morgan", "Theo Grant", "Lena Ortiz",
                    "Ravi Singh", "June Park", "Amara Cole", "Felix Reed", "Sofia Lane")
SUPPLIED_CANDIDATES = (
    "Adrian.png", "Dominic.png", "Elena.png", "Ethan.png", "Felix.png",
    "Henrik.png", "Julian.png", "Lucas.png", "Marcus.png", "Mateo.png",
    "Nathan.png", "Oscar.png", "Owen.png", "Sebastian.png", "Selene.png",
    "Unnamed Character.png",
)
USER_KIND = "user-supplied-limezu-generator-derivative"
COMPOSITE_KIND = "licensed-generator-component-composite"
SOURCE_SPECS = {
    "Nora Vale": (USER_KIND, "Marcus.png"),
    "Milo Chen": (USER_KIND, "Sebastian.png"),
    "Iris Morgan": (USER_KIND, "Elena.png"),
    "Theo Grant": (USER_KIND, "Nathan.png"),
    "Lena Ortiz": (COMPOSITE_KIND, (
        ("body", "Bodies/16x16/Body_03.png"), ("eyes", "Eyes/16x16/Eyes_01.png"),
        ("outfit", "Outfits/16x16/Outfit_13_03.png"),
        ("hairstyle", "Hairstyles/16x16/Hairstyle_07_01.png"))),
    "Ravi Singh": (USER_KIND, "Lucas.png"),
    "June Park": (COMPOSITE_KIND, (
        ("body", "Bodies/16x16/Body_03.png"), ("eyes", "Eyes/16x16/Eyes_01.png"),
        ("outfit", "Outfits/16x16/Outfit_31_03.png"),
        ("hairstyle", "Hairstyles/16x16/Hairstyle_10_06.png"))),
    "Amara Cole": (COMPOSITE_KIND, (
        ("body", "Bodies/16x16/Body_02.png"), ("eyes", "Eyes/16x16/Eyes_01.png"),
        ("outfit", "Outfits/16x16/Outfit_31_02.png"),
        ("hairstyle", "Hairstyles/16x16/Hairstyle_27_05.png"))),
    "Felix Reed": (USER_KIND, "Adrian.png"),
    "Sofia Lane": (USER_KIND, "Oscar.png"),
}
SELECTION_CRITERIA = {
    "Nora Vale": ("strategist", "short gray hair; dark green", "gray side-swept hair; slate formal", "hair and authority"),
    "Milo Chen": ("market researcher", "short brown hair; green", "short brown hair; blue-white", "professional research read"),
    "Iris Morgan": ("offer designer", "long gray hair; lavender", "long gray hair; lavender", "closest silhouette and palette"),
    "Theo Grant": ("sales drafter", "warm orange hair; green", "warm orange hair; pale blue", "approachable warm silhouette"),
    "Lena Ortiz": ("delivery planner", "short blonde hair; green", "short golden hair; green-white", "custom fidelity composite"),
    "Ravi Singh": ("analyst", "medium skin; brown hair; white-blue", "medium-deep skin; dark hair; green-blue", "skin and analytical palette"),
    "June Park": ("operations coordinator", "black bob; blue", "dark bob; structured blue", "custom fidelity composite"),
    "Amara Cole": ("finance scoring", "long blonde hair; lavender", "long golden hair; lavender-white", "custom fidelity composite"),
    "Felix Reed": ("tool advocate", "spiky blonde hair; green", "spiky blonde hair; blue", "hair and technical energy"),
    "Sofia Lane": ("risk officer", "short gray hair; green", "short gray hair; green-white", "palette and serious read"),
}
IDLE_FRAMES = {
    "down": list(range(74, 80)), "left": list(range(56, 62)),
    "right": list(range(68, 74)), "up": list(range(62, 68)),
}
WALK_FRAMES = {
    "down": list(range(130, 136)), "left": list(range(112, 118)),
    "right": list(range(124, 130)), "up": list(range(118, 124)),
}
OPTIONAL_ACTIONS = {"status": "disabled-pending-visual-review",
                    "not_exposed_in_runtime": ["sit", "phone", "hurt"]}
PAID_EVIDENCE = {
    "license": "moderninteriors-win/LICENSE.txt",
    "readme": "moderninteriors-win/READ_ME.txt",
    "third_party": "moderninteriors-win/THIRD-PARTY TOOLS.txt",
    "guide": "moderninteriors-win/2_Characters/Character_Generator/Spritesheet_animations_GUIDE.png",
    "premade": "moderninteriors-win/2_Characters/Character_Generator/0_Premade_Characters/16x16/Premade_Character_01.png",
}
CREDITS = (
    {"name": "LimeZu", "role": "Modern Interiors artwork", "url": "https://limezu.itch.io/", "required": True},
    {"name": "0a3r", "role": "Modern Interiors Character Generator tool", "url": "https://0a3r.itch.io/modern-interiors-character-generation-tool", "required": True},
)


class ManifestError(ValueError):
    """Raised when resident assets do not satisfy the runtime contract."""


def _contained(root: Path, relative_value, label: str, suffix=".png") -> Path:
    if not isinstance(relative_value, str) or not relative_value.strip():
        raise ManifestError(f"{label} must be a contained file path")
    relative = Path(relative_value)
    if relative.is_absolute() or ".." in relative.parts or "\\" in relative_value:
        raise ManifestError(f"{label} must be a contained file path")
    candidate = (root / relative).resolve(strict=False)
    if root not in candidate.parents or not candidate.is_file():
        raise ManifestError(f"{label} must reference a contained existing file")
    if suffix and candidate.suffix.lower() != suffix:
        raise ManifestError(f"{label} must reference a {suffix} file")
    return candidate


def _png_size(path: Path, label: str) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            image_format, size = image.format, image.size
            image.verify()
    except (OSError, SyntaxError, UnidentifiedImageError, ValueError) as exc:
        raise ManifestError(f"{label} must be a valid PNG") from exc
    if image_format != "PNG":
        raise ManifestError(f"{label} must be a valid PNG")
    return size


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _valid_digest(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _review_digest(candidate_hashes: dict) -> str:
    payload = "".join(f"{name}:{candidate_hashes[name]}\n" for name in sorted(candidate_hashes))
    return sha256(payload.encode("utf-8")).hexdigest()


def _validate_provenance(resident: dict, name: str) -> None:
    provenance = resident.get("provenance")
    if not isinstance(provenance, dict) or resident.get("source") not in {
        USER_KIND, COMPOSITE_KIND
    }:
        raise ManifestError(f"{name} provenance is invalid")
    if provenance.get("kind") != resident["source"]:
        raise ManifestError(f"{name} provenance kind does not match source")
    if resident["source"] == USER_KIND:
        asset = provenance.get("source_asset")
        if not isinstance(asset, str) or not asset.startswith("characters/"):
            raise ManifestError(f"{name} user-supplied source asset is invalid")
        if not _valid_digest(provenance.get("source_sha256")):
            raise ManifestError(f"{name} source SHA-256 is invalid")
        if provenance["source_sha256"] != resident["runtime_sha256"]:
            raise ManifestError(f"{name} copied derivative hash must match runtime")
    else:
        components = provenance.get("components")
        if not isinstance(components, list) or len(components) != 4:
            raise ManifestError(f"{name} composite must declare four components")
        if [item.get("role") for item in components] != [
            "body", "eyes", "outfit", "hairstyle"
        ]:
            raise ManifestError(f"{name} component order is invalid")
        if any(not _valid_digest(item.get("sha256")) for item in components):
            raise ManifestError(f"{name} component SHA-256 is invalid")
        if not _valid_digest(provenance.get("recipe_sha256")):
            raise ManifestError(f"{name} composite recipe SHA-256 is invalid")


def _validate_resident(resident: dict, static: Path) -> tuple[Path, Path]:
    name = resident.get("name")
    if name not in ACTIVE_RESIDENTS:
        raise ManifestError(f"unexpected active resident: {name}")
    key = resident.get("texture_key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_]+", key):
        raise ManifestError(f"{name} texture_key is invalid")
    sprite = _contained(static, resident.get("sprite_url"), f"{name} sprite_url")
    portrait = _contained(static, resident.get("portrait_url"), f"{name} portrait_url")
    if _png_size(sprite, f"{name} sprite") != SHEET_SIZE:
        raise ManifestError(f"{name} sprite must be 896x640")
    if _png_size(portrait, f"{name} portrait") != (32, 32):
        raise ManifestError(f"{name} portrait must be 32x32")
    required = (
        resident.get("sheet") == {"width": 896, "height": 640},
        resident.get("frame") == {"width": 16, "height": 32},
        resident.get("scale") == 1,
        resident.get("origin") == {"x": 0.5, "y": 1},
        resident.get("foot_offset") == {"x": 0, "y": 0},
        resident.get("portrait_crop") == {"x": 0, "y": 0, "width": 32, "height": 32},
    )
    if not all(required):
        raise ManifestError(f"{name} must use native 16x32 bottom-center scale 1")
    for key_name, path in (("runtime_sha256", sprite), ("portrait_sha256", portrait)):
        if not _valid_digest(resident.get(key_name)) or resident[key_name] != _digest(path):
            raise ManifestError(f"{name} {key_name} does not match its PNG")
    _validate_provenance(resident, name)
    animations = resident.get("animations")
    if animations != {"idle": IDLE_FRAMES, "walk": WALK_FRAMES, "actions": {}}:
        raise ManifestError(f"{name} runtime must expose only verified idle and walk")
    return sprite, portrait


def validate_character_manifest(manifest: dict, static_root: PathLike) -> dict:
    """Validate schema v2, reviewed movement, and accurate resident provenance."""
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 2:
        raise ManifestError("character manifest schema_version must be 2")
    expected_top = (
        manifest.get("asset_pack") == "limezu-character-generator-derivatives",
        manifest.get("rendering") == {
            "texture_filter": "nearest", "native_frame": {"width": 16, "height": 32}
        },
        manifest.get("credits") == list(CREDITS),
        manifest.get("active_residents") == list(ACTIVE_RESIDENTS),
        manifest.get("optional_actions") == OPTIONAL_ACTIONS,
        manifest.get("generation") == {
            "default_activation": False,
            "required_compatibility_pack": "Modern Interiors Full Version",
            "free_pack_allowed": False,
        },
        manifest.get("compatibility_gate") == {
            "purpose": "license-and-component-compatibility-only",
            "paid_pack": "Modern Interiors Full Version",
            "runtime_vendor_sources_shipped": False,
        },
    )
    if not all(expected_top):
        raise ManifestError("character manifest top-level contract is invalid")
    audit = manifest.get("curation_audit")
    hashes = audit.get("candidate_hashes") if isinstance(audit, dict) else None
    if not isinstance(hashes, dict) or list(hashes) != list(SUPPLIED_CANDIDATES):
        raise ManifestError("curation audit must cover all sixteen supplied candidates")
    if any(not _valid_digest(value) for value in hashes.values()):
        raise ManifestError("curation candidate SHA-256 is invalid")
    if len(set(hashes.values())) != 16 or audit.get("candidate_pool_sha256") != _review_digest(hashes):
        raise ManifestError("curation candidate audit is not unique or deterministic")
    static = Path(static_root).expanduser().resolve(strict=False)
    if not static.is_dir():
        raise ManifestError("static root must be an existing directory")
    residents = manifest.get("residents")
    if not isinstance(residents, list) or len(residents) != 10:
        raise ManifestError("character manifest must define exactly ten residents")
    if [resident.get("name") for resident in residents] != list(ACTIVE_RESIDENTS):
        raise ManifestError("resident entries must match active_residents in order")
    for field in ("texture_key", "sprite_url", "portrait_url"):
        values = [resident.get(field) for resident in residents]
        if any(not isinstance(value, str) or not value for value in values):
            raise ManifestError(f"residents must define non-empty {field} values")
        if len(set(values)) != 10:
            raise ManifestError(f"residents must use unique {field} values")
    paths: set[Path] = set()
    for resident in residents:
        resident_paths = _validate_resident(resident, static)
        if any(path in paths for path in resident_paths):
            raise ManifestError("residents must use unique sprite and portrait assets")
        paths.update(resident_paths)
    return manifest


def _full_pack_error(detail: str) -> ManifestError:
    return ManifestError(
        "verified paid Modern Interiors compatibility evidence is required; "
        f"{detail}. Modern Interiors Free is forbidden"
    )


def _paid_source(source_root: PathLike) -> Path:
    try:
        return provenance.validate_paid_source(source_root, PAID_EVIDENCE, SHEET_SIZE, _png_size)
    except (ManifestError, provenance.ProvenanceError) as exc:
        raise _full_pack_error(str(exc)) from exc


def require_full_pack(manifest: dict, static_root=None, paid_source_root=None) -> dict:
    """Apply the separate paid-pack license/component compatibility gate."""
    if static_root is None or paid_source_root is None:
        raise _full_pack_error("static assets and paid compatibility evidence are required")
    try:
        validated = validate_character_manifest(manifest, static_root)
    except ManifestError as exc:
        raise _full_pack_error(str(exc)) from exc
    source = _paid_source(paid_source_root)
    try:
        provenance.validate_paid_provenance(
            validated, Path(static_root).expanduser().resolve(strict=False), source,
            SUPPLIED_CANDIDATES, SOURCE_SPECS, USER_KIND, SHEET_SIZE, _contained,
            _digest, _png_size, _component_path, _compose, _portrait,
        )
    except (ManifestError, provenance.ProvenanceError) as exc:
        raise _full_pack_error(str(exc)) from exc
    return validated


def _frame(sheet: Image.Image, index: int) -> Image.Image:
    x, y = (index % 56) * 16, (index // 56) * 32
    return sheet.crop((x, y, x + 16, y + 32))


def _portrait(sheet: Image.Image) -> Image.Image:
    front = _frame(sheet, IDLE_FRAMES["down"][0])
    bounds = front.getbbox()
    top = 6 if bounds is None else max(0, min(16, bounds[1] - 1))
    return front.crop((0, top, 16, top + 16)).resize((32, 32), Image.Resampling.NEAREST)


def _component_path(root: Path, relative: str) -> Path:
    prefix = "moderninteriors-win/2_Characters/Character_Generator/"
    return _contained(root, prefix + relative, "generator component")


def _compose(root: Path, recipe) -> tuple[Image.Image, list[dict], str]:
    sheet = Image.new("RGBA", SHEET_SIZE)
    metadata = []
    for role, relative in recipe:
        path = _component_path(root, relative)
        if _png_size(path, f"{role} component") not in {SHEET_SIZE, (896, 656), (927, 656)}:
            raise ManifestError(f"{role} component has an invalid sheet size")
        with Image.open(path) as opened:
            sheet.alpha_composite(opened.convert("RGBA").crop((0, 0, 896, 640)))
        metadata.append({"role": role, "path": relative, "sha256": _digest(path)})
    recipe_text = "".join(f"{item['role']}:{item['path']}:{item['sha256']}\n" for item in metadata)
    return sheet, metadata, sha256(recipe_text.encode("utf-8")).hexdigest()


def _entry(name: str, sprite: Path, portrait: Path, provenance: dict) -> dict:
    key = name.replace(" ", "_")
    return {
        "name": name, "texture_key": key,
        "sprite_url": f"assets/characters/modern_pixels/{key}.png",
        "portrait_url": f"assets/characters/modern_pixels/profile/{key}.png",
        "source": provenance["kind"], "provenance": provenance,
        "runtime_sha256": _digest(sprite), "portrait_sha256": _digest(portrait),
        "sheet": {"width": 896, "height": 640},
        "frame": {"width": 16, "height": 32}, "scale": 1,
        "origin": {"x": 0.5, "y": 1}, "foot_offset": {"x": 0, "y": 0},
        "portrait_crop": {"x": 0, "y": 0, "width": 32, "height": 32},
        "animations": {"idle": IDLE_FRAMES, "walk": WALK_FRAMES, "actions": {}},
    }


def curate_residents(source_root: PathLike, static_root: PathLike, manifest_path: PathLike) -> dict:
    """Audit all supplied designs, compose fidelity gaps, and emit only ten sheets."""
    source = _paid_source(source_root)
    static = Path(static_root).expanduser().resolve(strict=False)
    candidates = {}
    for filename in SUPPLIED_CANDIDATES:
        path = _contained(source, f"characters/{filename}", "supplied candidate")
        if _png_size(path, filename) != SHEET_SIZE:
            raise ManifestError(f"{filename} must be 896x640")
        candidates[filename] = _digest(path)
    if len(set(candidates.values())) != 16:
        raise ManifestError("all sixteen supplied candidates must be visually distinct")
    residents = []
    for name in ACTIVE_RESIDENTS:
        kind, source_spec = SOURCE_SPECS[name]
        key = name.replace(" ", "_")
        sprite = static / f"assets/characters/modern_pixels/{key}.png"
        portrait = static / f"assets/characters/modern_pixels/profile/{key}.png"
        sprite.parent.mkdir(parents=True, exist_ok=True)
        portrait.parent.mkdir(parents=True, exist_ok=True)
        if kind == USER_KIND:
            source_sheet = _contained(source, f"characters/{source_spec}", name)
            sprite.write_bytes(source_sheet.read_bytes())
            provenance = {
                "kind": USER_KIND, "source_asset": f"characters/{source_spec}",
                "source_sha256": _digest(source_sheet),
            }
        else:
            composed, components, recipe_hash = _compose(source, source_spec)
            composed.save(sprite, format="PNG", compress_level=9, optimize=False)
            provenance = {
                "kind": COMPOSITE_KIND, "components": components,
                "recipe_sha256": recipe_hash,
            }
        with Image.open(sprite) as opened:
            _portrait(opened.convert("RGBA")).save(
                portrait, format="PNG", compress_level=9, optimize=False
            )
        residents.append(_entry(name, sprite, portrait, provenance))
    manifest = {
        "schema_version": 2, "asset_pack": "limezu-character-generator-derivatives",
        "rendering": {"texture_filter": "nearest", "native_frame": {"width": 16, "height": 32}},
        "credits": list(CREDITS), "active_residents": list(ACTIVE_RESIDENTS),
        "generation": {"default_activation": False,
                       "required_compatibility_pack": "Modern Interiors Full Version",
                       "free_pack_allowed": False},
        "compatibility_gate": {"purpose": "license-and-component-compatibility-only",
                               "paid_pack": "Modern Interiors Full Version",
                               "runtime_vendor_sources_shipped": False},
        "optional_actions": OPTIONAL_ACTIONS,
        "curation_audit": {"candidate_hashes": candidates,
                           "candidate_pool_sha256": _review_digest(candidates)},
        "residents": residents,
    }
    output = Path(manifest_path).expanduser().resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return require_full_pack(manifest, static, source)


def _contact_metadata(manifest: dict, output: Path) -> dict:
    selections = []
    by_name = {resident["name"]: resident for resident in manifest["residents"]}
    for name in ACTIVE_RESIDENTS:
        role, fallback, selected, decision = SELECTION_CRITERIA[name]
        resident = by_name[name]
        provenance = resident["provenance"]
        source_ref = provenance.get("source_asset", f"component-composite:{name}")
        selections.append({"name": name, "role": role, "fallback_reference": fallback,
                           "selected_profile": selected, "decision_basis": decision,
                           "source_kind": resident["source"], "source_ref": source_ref})
    return {
        "image": output.name, "image_sha256": _digest(output),
        "label": CONTACT_SHEET_LABEL, "schema_version": 2,
        "size": list(CONTACT_SHEET_SIZE),
        "selection_policy": ["fallback hair silhouette and tone", "primary palette",
                             "skin-tone continuity", "professional role read",
                             "whole-roster visual distinction"],
        "candidate_audit": manifest["curation_audit"], "selections": selections,
        "reviewed_animations": ["idle", "walk"], "optional_actions": OPTIONAL_ACTIONS,
    }


def build_contact_sheet(manifest: dict, static_root: PathLike, output_path: PathLike,
                        *, metadata_path: PathLike | None = None) -> Path:
    """Render idle and walk previews plus deterministic selection metadata."""
    root = Path(static_root).expanduser().resolve(strict=False)
    validated = validate_character_manifest(manifest, root)
    output = Path(output_path).expanduser().resolve(strict=False)
    if output.suffix.lower() != ".png":
        raise ManifestError("contact sheet output must be a PNG")
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", CONTACT_SHEET_SIZE, (15, 20, 26, 255))
    draw, font = ImageDraw.Draw(canvas), ImageFont.load_default()
    draw.text((18, 16), CONTACT_SHEET_LABEL, fill=(244, 207, 96, 255), font=font)
    for index, resident in enumerate(validated["residents"]):
        column, row = index % 5, index // 5
        x, y = 12 + column * 197, 47 + row * 207
        draw.rounded_rectangle((x, y, x + 185, y + 192), 5, fill=(28, 36, 45, 255))
        role = SELECTION_CRITERIA[resident["name"]][0]
        draw.text((x + 8, y + 7), resident["name"], fill=(239, 244, 250, 255), font=font)
        draw.text((x + 8, y + 21), role, fill=(142, 179, 204, 255), font=font)
        with Image.open(root / resident["sprite_url"]) as opened:
            sheet = opened.convert("RGBA")
        for direction_index, direction in enumerate(("left", "up", "right", "down")):
            actor = _frame(sheet, resident["animations"]["idle"][direction][0])
            canvas.alpha_composite(actor.resize((32, 64), Image.Resampling.NEAREST),
                                   (x + 8 + direction_index * 39, y + 38))
        draw.text((x + 8, y + 105), "walk down", fill=(142, 179, 204, 255), font=font)
        for walk_index, frame_index in enumerate((130, 132, 134)):
            actor = _frame(sheet, frame_index).resize((32, 64), Image.Resampling.NEAREST)
            canvas.alpha_composite(actor, (x + 8 + walk_index * 39, y + 117))
        with Image.open(root / resident["portrait_url"]) as opened:
            canvas.alpha_composite(opened.convert("RGBA"), (x + 145, y + 133))
        source_label = "custom components" if resident["source"] == COMPOSITE_KIND else Path(
            resident["provenance"]["source_asset"]
        ).stem
        draw.text((x + 8, y + 179), f"source: {source_label}", fill=(150, 173, 190, 255), font=font)
    draw.text((18, 468), "SIT / PHONE / HURT: DISABLED - PENDING VISUAL REVIEW",
              fill=(239, 143, 132, 255), font=font)
    canvas.save(output, format="PNG", compress_level=9, optimize=False)
    if metadata_path is not None:
        metadata = Path(metadata_path).expanduser().resolve(strict=False)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        metadata.write_text(json.dumps(_contact_metadata(validated, output), indent=2) + "\n",
                            encoding="utf-8")
    return output


def main(argv=None) -> int:
    repo = Path(__file__).resolve().parents[2]
    static = repo / "environment/frontend_server/static_dirs"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=static / "assets/characters/manifest.json")
    parser.add_argument("--static-root", type=Path, default=static)
    parser.add_argument("--curate-source-root", type=Path)
    parser.add_argument("--paid-source-root", type=Path)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.curate_source_root:
            manifest = curate_residents(args.curate_source_root, args.static_root, args.manifest)
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            (require_full_pack if args.paid_source_root else validate_character_manifest)(
                manifest, args.static_root, args.paid_source_root
            ) if args.paid_source_root else validate_character_manifest(manifest, args.static_root)
        if args.contact_sheet:
            build_contact_sheet(manifest, args.static_root, args.contact_sheet,
                                metadata_path=args.metadata)
    except (OSError, UnicodeError, json.JSONDecodeError, ManifestError) as exc:
        parser.error(str(exc))
    print(f"Validated {len(manifest['residents'])} licensed Modern Pixels residents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
