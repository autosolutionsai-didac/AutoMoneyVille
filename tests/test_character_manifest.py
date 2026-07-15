"""Character manifest, fallback contact sheet, and paid-pack gate tests."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

try:
    from tools.mapgen import character_manifest
except ImportError:
    character_manifest = None


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "environment/frontend_server/static_dirs"
MANIFEST_PATH = STATIC_ROOT / "assets/characters/manifest.json"
EXPECTED = {
    "Nora Vale",
    "Milo Chen",
    "Iris Morgan",
    "Theo Grant",
    "Lena Ortiz",
    "Ravi Singh",
    "June Park",
    "Amara Cole",
    "Felix Reed",
    "Sofia Lane",
}


class CharacterManifestTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            character_manifest,
            "tools.mapgen.character_manifest must provide the manifest API",
        )
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def _build_paid_fixture(self, root: Path):
        static_root = root / "static"
        vendor_root = root / "vendor"
        manifest = copy.deepcopy(self.manifest)
        manifest["asset_pack"] = "modern-interiors-paid"
        for index, resident in enumerate(manifest["residents"]):
            resident["source"] = "modern-interiors-paid"
            resident["sprite_url"] = f"assets/paid/{resident['texture_key']}.png"
            resident["portrait_url"] = (
                f"assets/paid/profile/{resident['texture_key']}.png"
            )
            sprite = static_root / resident["sprite_url"]
            portrait = static_root / resident["portrait_url"]
            sprite.parent.mkdir(parents=True, exist_ok=True)
            portrait.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (96, 128), (index, 20, 40, 255)).save(sprite)
            Image.new("RGBA", (32, 32), (index, 40, 20, 255)).save(portrait)

        paid_root = vendor_root / "moderninteriors-win"
        paid_root.mkdir(parents=True)
        (paid_root / "Modern_Interiors_License.pdf").write_bytes(
            b"%PDF-1.4\nlicensed Modern Interiors fixture\n"
        )
        (paid_root / "READ_ME.txt").write_text(
            "Modern Interiors by LimeZu", encoding="utf-8"
        )
        interiors = (
            paid_root
            / "Modern_Interiors_32x32"
            / "Modern_Interiors_Complete_Tileset_32x32.png"
        )
        interiors.parent.mkdir(parents=True)
        Image.new("RGBA", (32, 32), (1, 2, 3, 255)).save(interiors)
        generator = (
            paid_root
            / "Modern_Interiors_32x32"
            / "Character_Generator_32x32"
            / "base_32x32.png"
        )
        generator.parent.mkdir(parents=True)
        Image.new("RGBA", (32, 64), (4, 5, 6, 255)).save(generator)
        return manifest, static_root, vendor_root

    def test_exact_active_roster_has_valid_unique_fallback_assets_and_frames(self):
        validated = character_manifest.validate_character_manifest(
            self.manifest, STATIC_ROOT
        )
        residents = validated["residents"]
        self.assertEqual(len(residents), 10)
        self.assertEqual({resident["name"] for resident in residents}, EXPECTED)
        self.assertEqual(set(validated["active_residents"]), EXPECTED)
        self.assertFalse(validated["generation"]["default_activation"])
        for field in ("texture_key", "sprite_url", "portrait_url"):
            values = [resident[field] for resident in residents]
            self.assertEqual(len(values), len(set(values)), field)
        for resident in residents:
            self.assertEqual(resident["source"], "fallback")
            self.assertEqual(resident["sheet"], {"width": 96, "height": 128})
            self.assertEqual(resident["frame"], {"width": 32, "height": 32})
            self.assertEqual(resident["origin"], {"x": 0.5, "y": 1})
            self.assertGreater(resident["scale"], 0)
            self.assertEqual(
                resident["portrait_crop"], {"x": 0, "y": 0, "width": 32, "height": 32}
            )
            animations = resident["animations"]
            self.assertEqual(set(animations["idle"]), {"down", "left", "right", "up"})
            self.assertEqual(set(animations["walk"]), {"down", "left", "right", "up"})
            self.assertTrue(all(animations["idle"].values()))
            self.assertTrue(all(animations["walk"].values()))
            self.assertIsInstance(animations.get("actions", {}), dict)

    def test_validator_rejects_unsafe_urls_duplicate_assets_and_bad_frames(self):
        cases = []
        unsafe = copy.deepcopy(self.manifest)
        unsafe["residents"][0]["sprite_url"] = "../secrets.png"
        cases.append((unsafe, "safe contained"))
        duplicate = copy.deepcopy(self.manifest)
        duplicate["residents"][1]["portrait_url"] = duplicate["residents"][0][
            "portrait_url"
        ]
        cases.append((duplicate, "unique portrait_url"))
        bad_frame = copy.deepcopy(self.manifest)
        bad_frame["residents"][0]["animations"]["walk"]["down"] = [12]
        cases.append((bad_frame, "frame index"))
        wrong_origin = copy.deepcopy(self.manifest)
        wrong_origin["residents"][0]["origin"] = {"x": 0.5, "y": 0.5}
        cases.append((wrong_origin, "bottom-center"))
        for candidate, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    character_manifest.ManifestError, message
                ):
                    character_manifest.validate_character_manifest(
                        candidate, STATIC_ROOT
                    )

    def test_contact_sheet_is_deterministic_and_clearly_fallback_labeled(self):
        self.assertIn("FALLBACK", character_manifest.CONTACT_SHEET_LABEL)
        self.assertIn("96x128", character_manifest.CONTACT_SHEET_LABEL)
        with TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.png"
            second = Path(tmp) / "second.png"
            metadata_path = Path(tmp) / "contact-sheet.json"
            character_manifest.build_contact_sheet(
                self.manifest, STATIC_ROOT, first, metadata_path=metadata_path
            )
            character_manifest.build_contact_sheet(self.manifest, STATIC_ROOT, second)
            self.assertEqual(
                hashlib.sha256(first.read_bytes()).hexdigest(),
                hashlib.sha256(second.read_bytes()).hexdigest(),
            )
            with Image.open(first) as image:
                self.assertEqual(image.size, (800, 410))
                self.assertEqual(image.format, "PNG")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["label"], character_manifest.CONTACT_SHEET_LABEL)
            self.assertEqual(metadata["source"], "fallback")
            self.assertEqual(metadata["image_sha256"], hashlib.sha256(first.read_bytes()).hexdigest())
            self.assertEqual(metadata["residents"], self.manifest["active_residents"])

    def test_full_pack_gate_refuses_current_fallback_and_forbids_free_pack(self):
        with self.assertRaisesRegex(
            character_manifest.ManifestError,
            "paid Modern Interiors character assets are absent.*Free pack is forbidden",
        ):
            character_manifest.require_full_pack(self.manifest)

    def test_full_pack_gate_rejects_spoofed_paid_labels(self):
        spoofed = {
            "asset_pack": "modern-interiors-paid",
            "residents": [
                {"source": "modern-interiors-paid"}
                for _ in character_manifest.ACTIVE_RESIDENTS
            ],
        }
        with self.assertRaisesRegex(
            character_manifest.ManifestError,
            "paid Modern Interiors character assets are absent|exact ten-resident roster",
        ):
            character_manifest.require_full_pack(spoofed)

    def test_full_pack_gate_validates_assets_and_curation_evidence(self):
        with TemporaryDirectory() as tmp:
            manifest, static_root, vendor_root = self._build_paid_fixture(Path(tmp))
            with self.assertRaisesRegex(
                character_manifest.ManifestError,
                "verified paid Modern Interiors evidence",
            ):
                character_manifest.require_full_pack(
                    manifest, static_root, Path(tmp) / "missing-vendor"
                )
            validated = character_manifest.require_full_pack(
                manifest, static_root, vendor_root
            )
            self.assertEqual(set(validated["active_residents"]), EXPECTED)

    def test_full_pack_cli_uses_paid_validator_instead_of_fallback_validator(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, static_root, vendor_root = self._build_paid_fixture(root)
            manifest_path = root / "paid-manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(
                character_manifest.main(
                    [
                        "--manifest",
                        str(manifest_path),
                        "--static-root",
                        str(static_root),
                        "--require-full-pack",
                        "--paid-source-root",
                        str(vendor_root),
                    ]
                ),
                0,
            )


if __name__ == "__main__":
    unittest.main()
