"""Licensed resident curation, provenance, and review artifact tests."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw

from tools.mapgen import character_manifest

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "environment/frontend_server/static_dirs"
MANIFEST_PATH = STATIC_ROOT / "assets/characters/manifest.json"


class CharacterManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def _paint_sheet(path: Path, color: tuple[int, int, int, int], role="body"):
        path.parent.mkdir(parents=True, exist_ok=True)
        size = (927, 656) if role == "body" else (896, 656)
        sheet = Image.new("RGBA", size, (0, 0, 0, 0))
        x = (character_manifest.IDLE_FRAMES["down"][0] % 56) * 16
        y = (character_manifest.IDLE_FRAMES["down"][0] // 56) * 32
        boxes = {
            "body": (x + 4, y + 4, x + 11, y + 27),
            "eyes": (x + 6, y + 10, x + 9, y + 11),
            "outfit": (x + 3, y + 17, x + 12, y + 27),
            "hairstyle": (x + 3, y + 3, x + 12, y + 13),
        }
        ImageDraw.Draw(sheet).rectangle(boxes[role], fill=color)
        sheet.save(path)

    def _source_fixture(self, root: Path) -> Path:
        source = root / "Modern Pixels"
        paid = source / "moderninteriors-win"
        paid.mkdir(parents=True)
        (paid / "LICENSE.txt").write_text(
            "MODERN INTERIORS FULL VERSION LICENSE\nCredits required (limezu.itch.io)\n",
            encoding="utf-8",
        )
        (paid / "READ_ME.txt").write_text("Modern_Interiors by LimeZu", encoding="utf-8")
        (paid / "THIRD-PARTY TOOLS.txt").write_text(
            "CHARACTER_GENERATOR Tool by 0a3r", encoding="utf-8"
        )
        generator = paid / "2_Characters/Character_Generator"
        generator.mkdir(parents=True)
        Image.new("RGBA", (64, 64), (1, 2, 3, 255)).save(
            generator / "Spritesheet_animations_GUIDE.png"
        )
        premade = generator / "0_Premade_Characters/16x16"
        premade.mkdir(parents=True)
        Image.new("RGBA", (896, 656), (0, 0, 0, 0)).save(
            premade / "Premade_Character_01.png"
        )
        characters = source / "characters"
        characters.mkdir()
        for index, filename in enumerate(character_manifest.SUPPLIED_CANDIDATES):
            sheet = Image.new("RGBA", (896, 640), (0, 0, 0, 0))
            ImageDraw.Draw(sheet).rectangle(
                (290, 38, 299, 60), fill=(index + 1, 70, 130, 255)
            )
            sheet.save(characters / filename)
        component_paths = {}
        for kind, spec in character_manifest.SOURCE_SPECS.values():
            if kind == character_manifest.COMPOSITE_KIND:
                component_paths.update({path: role for role, path in spec})
        for index, (relative, role) in enumerate(sorted(component_paths.items())):
            self._paint_sheet(
                generator / relative, (100 + index, 40 + index, 180 - index, 255), role
            )
        return source

    def test_active_manifest_has_exact_runtime_and_accurate_provenance(self):
        validated = character_manifest.validate_character_manifest(
            self.manifest, STATIC_ROOT
        )
        self.assertEqual(validated["asset_pack"], "limezu-character-generator-derivatives")
        self.assertEqual(validated["optional_actions"], character_manifest.OPTIONAL_ACTIONS)
        self.assertEqual(
            validated["compatibility_gate"]["purpose"],
            "license-and-component-compatibility-only",
        )
        self.assertEqual(
            list(validated["curation_audit"]["candidate_hashes"]),
            list(character_manifest.SUPPLIED_CANDIDATES),
        )
        kinds = {resident["source"] for resident in validated["residents"]}
        self.assertEqual(
            kinds, {character_manifest.USER_KIND, character_manifest.COMPOSITE_KIND}
        )
        self.assertNotIn("modern-interiors-paid", kinds)
        for resident in validated["residents"]:
            self.assertEqual(resident["sheet"], {"width": 896, "height": 640})
            self.assertEqual(resident["frame"], {"width": 16, "height": 32})
            self.assertEqual(resident["scale"], 1)
            self.assertEqual(resident["origin"], {"x": 0.5, "y": 1})
            self.assertEqual(resident["animations"]["idle"], character_manifest.IDLE_FRAMES)
            self.assertEqual(resident["animations"]["walk"], character_manifest.WALK_FRAMES)
            self.assertEqual(resident["animations"]["actions"], {})
            sprite = STATIC_ROOT / resident["sprite_url"]
            portrait = STATIC_ROOT / resident["portrait_url"]
            self.assertEqual(
                resident["runtime_sha256"], hashlib.sha256(sprite.read_bytes()).hexdigest()
            )
            self.assertEqual(
                resident["portrait_sha256"], hashlib.sha256(portrait.read_bytes()).hexdigest()
            )
            provenance = resident["provenance"]
            if resident["source"] == character_manifest.USER_KIND:
                self.assertTrue(provenance["source_asset"].startswith("characters/"))
                self.assertEqual(provenance["source_sha256"], resident["runtime_sha256"])
            else:
                self.assertEqual(
                    [item["role"] for item in provenance["components"]],
                    ["body", "eyes", "outfit", "hairstyle"],
                )
                self.assertRegex(provenance["recipe_sha256"], r"^[0-9a-f]{64}$")

    def test_validator_rejects_spoofed_assets_actions_scale_and_audit(self):
        cases = []
        unsafe = copy.deepcopy(self.manifest)
        unsafe["residents"][0]["sprite_url"] = "../secrets.png"
        cases.append((unsafe, "contained"))
        bad_hash = copy.deepcopy(self.manifest)
        bad_hash["residents"][0]["runtime_sha256"] = "0" * 64
        cases.append((bad_hash, "does not match"))
        action = copy.deepcopy(self.manifest)
        action["residents"][0]["animations"]["actions"] = {"sit": [224]}
        cases.append((action, "only verified idle and walk"))
        oversized = copy.deepcopy(self.manifest)
        oversized["residents"][0]["scale"] = 2
        cases.append((oversized, "scale 1"))
        spoofed = copy.deepcopy(self.manifest)
        spoofed["residents"][0]["source"] = "modern-interiors-paid"
        cases.append((spoofed, "provenance"))
        incomplete = copy.deepcopy(self.manifest)
        incomplete["curation_audit"]["candidate_hashes"].pop("Unnamed Character.png")
        cases.append((incomplete, "sixteen supplied candidates"))
        for candidate, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(character_manifest.ManifestError, message):
                    character_manifest.validate_character_manifest(candidate, STATIC_ROOT)

    def test_contact_sheet_records_walk_review_selection_policy_and_disabled_actions(self):
        with TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "first.png", Path(tmp) / "second.png"
            metadata_path = Path(tmp) / "contact-sheet.json"
            character_manifest.build_contact_sheet(
                self.manifest, STATIC_ROOT, first, metadata_path=metadata_path
            )
            character_manifest.build_contact_sheet(self.manifest, STATIC_ROOT, second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                             hashlib.sha256(second.read_bytes()).digest())
            with Image.open(first) as image:
                self.assertEqual(image.size, character_manifest.CONTACT_SHEET_SIZE)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["reviewed_animations"], ["idle", "walk"])
            self.assertEqual(metadata["optional_actions"], character_manifest.OPTIONAL_ACTIONS)
            self.assertEqual(len(metadata["selection_policy"]), 5)
            self.assertEqual(len(metadata["selections"]), 10)
            self.assertEqual(
                {entry["name"] for entry in metadata["selections"]},
                set(character_manifest.ACTIVE_RESIDENTS),
            )
            for selection in metadata["selections"]:
                self.assertTrue(selection["fallback_reference"])
                self.assertTrue(selection["selected_profile"])
                self.assertTrue(selection["decision_basis"])
            self.assertEqual(
                len(metadata["candidate_audit"]["candidate_hashes"]), 16
            )

    def test_paid_compatibility_gate_is_separate_and_forbids_free(self):
        with self.assertRaisesRegex(
            character_manifest.ManifestError, "compatibility evidence"
        ):
            character_manifest.require_full_pack(self.manifest)
        free = copy.deepcopy(self.manifest)
        free["generation"]["free_pack_allowed"] = True
        with self.assertRaisesRegex(character_manifest.ManifestError, "top-level"):
            character_manifest.validate_character_manifest(free, STATIC_ROOT)

    def test_paid_gate_recomputes_candidate_component_and_composite_provenance(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._source_fixture(root)
            static = root / "static"
            manifest = character_manifest.curate_residents(
                source, static, static / "assets/characters/manifest.json"
            )
            candidate = source / "characters/Marcus.png"
            with Image.open(candidate) as opened:
                changed = opened.convert("RGBA")
            changed.putpixel((0, 0), (255, 1, 2, 255))
            changed.save(candidate)
            with self.assertRaisesRegex(
                character_manifest.ManifestError, "candidate hashes"
            ):
                character_manifest.require_full_pack(manifest, static, source)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._source_fixture(root)
            static = root / "static"
            manifest = character_manifest.curate_residents(
                source, static, static / "assets/characters/manifest.json"
            )
            nora = next(item for item in manifest["residents"] if item["name"] == "Nora Vale")
            portrait = static / nora["portrait_url"]
            with Image.open(portrait) as opened:
                changed = opened.convert("RGBA")
            changed.putpixel((0, 0), (6, 5, 4, 255))
            changed.save(portrait)
            nora["portrait_sha256"] = hashlib.sha256(portrait.read_bytes()).hexdigest()
            with self.assertRaisesRegex(
                character_manifest.ManifestError, "portrait does not match"
            ):
                character_manifest.require_full_pack(manifest, static, source)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._source_fixture(root)
            static = root / "static"
            manifest = character_manifest.curate_residents(
                source, static, static / "assets/characters/manifest.json"
            )
            component = (
                source / "moderninteriors-win/2_Characters/Character_Generator/"
                "Bodies/16x16/Body_03.png"
            )
            with Image.open(component) as opened:
                changed = opened.convert("RGBA")
            changed.putpixel((0, 0), (3, 4, 5, 255))
            changed.save(component)
            with self.assertRaisesRegex(
                character_manifest.ManifestError, "component provenance"
            ):
                character_manifest.require_full_pack(manifest, static, source)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._source_fixture(root)
            static = root / "static"
            manifest = character_manifest.curate_residents(
                source, static, static / "assets/characters/manifest.json"
            )
            lena = next(item for item in manifest["residents"] if item["name"] == "Lena Ortiz")
            sprite = static / lena["sprite_url"]
            with Image.open(sprite) as opened:
                changed = opened.convert("RGBA")
            changed.putpixel((0, 0), (9, 8, 7, 255))
            changed.save(sprite)
            lena["runtime_sha256"] = hashlib.sha256(sprite.read_bytes()).hexdigest()
            with self.assertRaisesRegex(
                character_manifest.ManifestError, "does not match declared components"
            ):
                character_manifest.require_full_pack(manifest, static, source)

    def test_curation_audits_all_sixteen_and_emits_only_final_ten(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = self._source_fixture(root)
            static = root / "static"
            manifest_path = static / "assets/characters/manifest.json"
            manifest = character_manifest.curate_residents(source, static, manifest_path)
            validated = character_manifest.require_full_pack(manifest, static, source)
            runtime = static / "assets/characters/modern_pixels"
            self.assertEqual(len(list(runtime.glob("*.png"))), 10)
            self.assertEqual(len(list((runtime / "profile").glob("*.png"))), 10)
            self.assertEqual(len(validated["curation_audit"]["candidate_hashes"]), 16)
            composites = [
                resident for resident in validated["residents"]
                if resident["source"] == character_manifest.COMPOSITE_KIND
            ]
            self.assertEqual({item["name"] for item in composites},
                             {"Lena Ortiz", "June Park", "Amara Cole"})
            candidate_hashes = set(validated["curation_audit"]["candidate_hashes"].values())
            self.assertTrue(all(item["runtime_sha256"] not in candidate_hashes for item in composites))
            self.assertEqual(json.loads(manifest_path.read_text(encoding="utf-8")), manifest)


if __name__ == "__main__":
    unittest.main()
