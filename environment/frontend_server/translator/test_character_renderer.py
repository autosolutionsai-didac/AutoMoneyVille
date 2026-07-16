"""Node-backed Django tests for manifest-driven character rendering."""

import json
import subprocess
from pathlib import Path

from django.test import SimpleTestCase

FRONTEND_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = FRONTEND_ROOT / "static_dirs"
TEMPLATE_ROOT = FRONTEND_ROOT / "templates"
RENDERER = STATIC_ROOT / "js/character_renderer.js"
MANIFEST = STATIC_ROOT / "assets/characters/manifest.json"


class CharacterRendererTests(SimpleTestCase):
    def test_node_adapter_loads_animates_anchors_crops_and_falls_back(self):
        source = r"""
const assert = require("assert");
const adapter = require(process.argv[1]);
const manifest = require(process.argv[2]);
const root = "http://example.test/static/";
const events = new Map();
const calls = [];
const loader = {
  once(name, callback) { events.set(name, callback); },
  on(name, callback) { events.set(name, callback); },
  json(...args) { calls.push(["json", ...args]); },
  spritesheet(...args) { calls.push(["spritesheet", ...args]); },
};
const queued = adapter.queueCharacters({load: loader}, root + "assets/characters/manifest.json", root);
events.get("filecomplete-json-character-manifest")(null, null, manifest);
assert.strictEqual(queued.manifest.residents.length, 10);
assert.strictEqual(calls.filter(call => call[0] === "spritesheet").length, 10);

const createdAnimations = [];
const sprites = [];
const scene = {
  __claudevilleCharacters: queued,
  textures: {exists: key => key !== "Missing_Person"},
  anims: {
    exists: () => false,
    create: value => createdAnimations.push(value),
    generateFrameNumbers: (key, value) => ({key, frames: value.frames}),
    generateFrameNames: (key, value) => ({key, prefix: value.prefix}),
  },
  physics: {add: {sprite(x, y, key, frame) {
    const sprite = {x, y, key, frame, anims: {play(value) {sprite.played = value;}, stop() {}},
      setOrigin(a, b) {this.origin = [a, b]; return this;},
      setScale(value) {this.scale = value; return this;},
      setFrame(value) {this.frame = value; return this;},
      setTexture(key2, frame2) {this.key = key2; this.frame = frame2; return this;}};
    sprites.push(sprite); return sprite;
  }}},
};
adapter.createAnimations(scene, ["Nora Vale"]);
const resident = adapter.createSprite(scene, "Nora Vale", 10, 20);
assert.deepStrictEqual(resident.origin, [0.5, 1]);
assert.strictEqual(resident.scale, 1);
assert.deepStrictEqual(resident.frameDimensions, {width: 32, height: 32});
assert.deepStrictEqual(resident.logicalFootAnchor, {x: 0.5, y: 1});
assert.deepStrictEqual(resident.logicalFootOffset, {x: 0, y: 0});
assert.deepStrictEqual(adapter.displayLayout(resident), {
  left: -6, top: -12, width: 32, height: 32, foot: {x: 10, y: 20},
});
assert.deepStrictEqual(adapter.displayWorldFoot(resident), {x: 10, y: 20});
assert.strictEqual(adapter.depthForSprite(resident, null), 2020);
assert.strictEqual(createdAnimations.length, 4);
adapter.playWalk(scene, resident, "Nora Vale", "left");
assert.strictEqual(resident.played, "Nora_Vale-left-walk");
adapter.setIdle(scene, resident, "Nora Vale", "up");
assert.strictEqual(resident.frame, 10);

const fallback = adapter.createSprite(scene, "Missing Person", 0, 0);
assert.strictEqual(fallback.key, "atlas");
assert.deepStrictEqual(fallback.origin, [0.5, 1]);
assert.strictEqual(fallback.scale, 1);
adapter.setIdle(scene, fallback, "Missing Person", "down");
assert.strictEqual(fallback.frame, "down");

const image = {dataset: {characterPortrait: "Nora Vale"}, style: {}};
const sizedImage = {dataset: {characterPortrait: "Milo Chen"}, style: {width: "46px"}};
adapter.applyPortraits({querySelectorAll: () => [image, sizedImage]}, manifest, root);
assert(image.src.endsWith("/assets/characters/profile/Nora_Vale.png"));
assert.strictEqual(image.style.objectPosition, "0px 0px");
assert.strictEqual(image.style.width, "32px");
assert.strictEqual(sizedImage.style.width, "46px");
assert.strictEqual(sizedImage.style.height, undefined);
process.stdout.write(JSON.stringify({ok: true}));
"""
        result = subprocess.run(
            ["node", "-e", source, str(RENDERER), str(MANIFEST)],
            cwd=FRONTEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_manifest_accepts_data_driven_frame_sizes_spacing_and_anchors(self):
        source = r"""
const assert = require("assert");
const adapter = require(process.argv[1]);
const original = require(process.argv[2]);
const manifest = JSON.parse(JSON.stringify(original));
const resident = manifest.residents[0];
resident.sheet = {width: 48, height: 128};
resident.frame = {width: 16, height: 32};
resident.origin = {x: 0.5, y: 1};
resident.scale = 2;
resident.foot_offset = {x: 1, y: -2};
const validated = adapter.validateCharacterManifest(
  manifest, "http://example.test/static/"
);
assert.deepStrictEqual(validated.residents[0].frame, {width: 16, height: 32});
assert.deepStrictEqual(validated.residents[0].origin, {x: 0.5, y: 1});
assert.deepStrictEqual(validated.residents[0].foot_offset, {x: 1, y: -2});

const sprite = {
  x: 100, y: 200, characterScale: 2,
  frameDimensions: {width: 16, height: 32},
  logicalFootAnchor: {x: 0.5, y: 1},
  logicalFootOffset: {x: 1, y: -2},
  displayOriginX: 8, displayOriginY: 32,
  body: {x: 84, y: 136, scaleX: 2, scaleY: 2, offset: {x: 0, y: 0}},
};
const initial = adapter.displayLayout(sprite);
assert.deepStrictEqual(initial, {
  left: 84, top: 136, width: 32, height: 64, foot: {x: 102, y: 196},
});
assert.strictEqual(adapter.depthForSprite(
  sprite, {depthForFootY: y => 2000 + y}
), 2196);

sprite.body.x += 10;
sprite.body.y += 20;
const moved = adapter.displayLayout(sprite);
assert.deepStrictEqual(moved.foot, {x: 112, y: 216});
assert.strictEqual(moved.top, 156);
assert.strictEqual(adapter.depthForSprite(sprite, null), 2216);

const invalid = JSON.parse(JSON.stringify(manifest));
invalid.residents[0].sheet.width = 49;
assert.throws(
  () => adapter.validateCharacterManifest(invalid, "http://example.test/static/"),
  /exactly divide/
);
const invalidFoot = JSON.parse(JSON.stringify(manifest));
invalidFoot.residents[0].foot_offset.x = 17;
assert.throws(
  () => adapter.validateCharacterManifest(invalidFoot, "http://example.test/static/"),
  /foot_offset/
);
process.stdout.write(JSON.stringify({ok: true}));
"""
        result = subprocess.run(
            ["node", "-e", source, str(RENDERER), str(MANIFEST)],
            cwd=FRONTEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_browser_validator_rejects_roster_generation_and_action_spoofs(self):
        source = r"""
const assert = require("assert");
const adapter = require(process.argv[1]);
const original = require(process.argv[2]);
const root = "http://example.test/static/";
const clone = () => JSON.parse(JSON.stringify(original));
function rejects(change, pattern) {
  const manifest = clone();
  change(manifest);
  assert.throws(() => adapter.validateCharacterManifest(manifest, root), pattern);
}
rejects(manifest => {
  manifest.active_residents[0] = "Spoof Resident";
  manifest.residents[0].name = "Spoof Resident";
}, /exact active resident roster/);
rejects(manifest => {
  manifest.generation.default_activation = true;
}, /default_activation/);
rejects(manifest => {
  manifest.generation.free_pack_allowed = true;
}, /free_pack_allowed/);
rejects(manifest => {
  manifest.residents[0].animations.actions = {wave: [12]};
}, /actions\.wave/);
rejects(manifest => {
  manifest.residents[0].sheet.width = 97;
}, /exactly divide/);
process.stdout.write(JSON.stringify({ok: true}));
"""
        result = subprocess.run(
            ["node", "-e", source, str(RENDERER), str(MANIFEST)],
            cwd=FRONTEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_load_errors_and_invalid_manifests_use_legacy_atlas_fallback(self):
        source = r"""
const assert = require("assert");
const adapter = require(process.argv[1]);
const root = "http://example.test/static/";

function makeScene() {
  const events = new Map();
  const created = [];
  const scene = {
    load: {
      on(name, callback) { events.set(name, callback); },
      once(name, callback) { events.set(name, callback); },
      json() {},
      spritesheet() {},
    },
    textures: {exists: () => false},
    anims: {
      exists: key => created.some(animation => animation.key === key),
      create: animation => created.push(animation),
      generateFrameNames: (key, value) => ({key, prefix: value.prefix}),
      generateFrameNumbers: (key, value) => ({key, frames: value.frames}),
    },
    physics: {add: {sprite(x, y, key, frame) {
      const sprite = {
        x, y, key, frame,
        anims: {play(value) {sprite.played = value;}, stop() {sprite.stopped = true;}},
        setOrigin(a, b) {this.origin = [a, b]; return this;},
        setScale(value) {this.scale = value; return this;},
        setFrame(value) {this.frame = value; return this;},
        setTexture(nextKey, nextFrame) {this.key = nextKey; this.frame = nextFrame; return this;},
      };
      return sprite;
    }}},
  };
  return {scene, events, created};
}

const failed = makeScene();
adapter.queueCharacters(failed.scene, root + "assets/characters/manifest.json", root);
failed.events.get("loaderror")({key: "character-manifest"});
assert.doesNotThrow(() => adapter.createAnimations(failed.scene, ["Nora Vale"]));
assert.strictEqual(failed.created.length, 4);
const fallback = adapter.createSprite(failed.scene, "Nora Vale", 4, 5);
assert.strictEqual(fallback.key, "atlas");
adapter.playWalk(failed.scene, fallback, "Nora Vale", "left");
assert.strictEqual(fallback.played, "fallback-left-walk");
adapter.setIdle(failed.scene, fallback, "Nora Vale", "up");
assert.strictEqual(fallback.key, "atlas");
assert.strictEqual(fallback.frame, "up");

const invalid = makeScene();
adapter.queueCharacters(invalid.scene, root + "assets/characters/manifest.json", root);
invalid.events.get("filecomplete-json-character-manifest")(null, null, {});
assert.doesNotThrow(() => adapter.createAnimations(invalid.scene, ["Nora Vale"]));
assert.strictEqual(invalid.created.length, 4);
process.stdout.write(JSON.stringify({ok: true}));
"""
        result = subprocess.run(
            ["node", "-e", source, str(RENDERER)],
            cwd=FRONTEND_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"ok": True})

    def test_home_and_demo_consume_shared_adapter_without_hardcoded_frames(self):
        home = (TEMPLATE_ROOT / "home/home.html").read_text(encoding="utf-8")
        home_script = (TEMPLATE_ROOT / "home/main_script.html").read_text(
            encoding="utf-8"
        )
        inspector = (TEMPLATE_ROOT / "home/inspector_script.html").read_text(
            encoding="utf-8"
        )
        demo = (TEMPLATE_ROOT / "demo/demo.html").read_text(encoding="utf-8")
        demo_script = (TEMPLATE_ROOT / "demo/main_script.html").read_text(
            encoding="utf-8"
        )
        home_controls = (TEMPLATE_ROOT / "home/main_phaser_controls.html").read_text(
            encoding="utf-8"
        )
        home_movement = (TEMPLATE_ROOT / "home/main_movement_pipeline.html").read_text(
            encoding="utf-8"
        )
        for page in (home, demo):
            self.assertIn("js/character_renderer.js' %}?v=", page)
            self.assertIn("data-character-portrait", page)
        for script in (home_script, demo_script):
            self.assertIn("ClaudevilleCharacters.queueCharacters", script)
            self.assertIn("ClaudevilleCharacters.createSprite", script)
            self.assertIn("ClaudevilleCharacters.createAnimations", script)
            self.assertIn("ClaudevilleCharacters.setIdle", script)
            self.assertNotIn("generateFrameNumbers", script)
            self.assertNotIn("generateFrameNames", script)
        for script in (home_controls, home_movement, demo_script):
            self.assertIn("ClaudevilleCharacters.displayLayout", script)
            self.assertIn("ClaudevilleCharacters.depthForSprite", script)
            self.assertNotIn("WORLD_DEPTH_BASE", script)
            self.assertNotIn("body.y + 60", script)
        self.assertIn("spriteLayout.foot.x, spriteLayout.foot.y", home_controls)
        self.assertIn(
            "spriteLayout.foot.x, spriteLayout.foot.y, 18, 6", home_controls
        )
        self.assertIn(
            "spriteLayout.foot.x, spriteLayout.foot.y, 18, 6", demo_script
        )
        self.assertIn("followShadow.y = spriteLayout.foot.y", home_movement)
        self.assertIn("personaShadows[persona_name]", demo_script)
        self.assertIn("currShadow.y = spriteLayout.foot.y", demo_script)
        self.assertIn("spriteLayout.top - 6", home_controls)
        self.assertIn("spriteLayout.top - 6", demo_script)
        self.assertIn("ClaudevilleCharacters.portraitUrl", inspector)


class CharacterManifestWorldContractTests(SimpleTestCase):
    def test_all_worlds_declare_shared_resident_manifest(self):
        for world in ("claudeville", "the_ville"):
            manifest = json.loads(
                (STATIC_ROOT / f"assets/{world}/world.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["resident_manifest_url"], "assets/characters/manifest.json"
            )
