"use strict";

const assert = require("assert");
const renderer = require(process.argv[2]);
const manifest = require(process.argv[3]);
const villeManifest = require(process.argv[4]);
const aliasManifest = require(process.argv[5]);
let installedAliases = null;
global.ClaudevilleAddresses = {setAliases(value) { installedAliases = value; }};

class FakeLoader {
  constructor() {
    this.events = new Map();
    this.calls = [];
  }

  once(name, callback) { this.events.set(name, { callback, once: true }); }
  on(name, callback) { this.events.set(name, { callback, once: false }); }
  emit(name, ...args) {
    const event = this.events.get(name);
    if (!event) return;
    event.callback(...args);
    if (event.once) this.events.delete(name);
  }
  json(...args) { this.calls.push(["json", ...args]); }
  tilemapTiledJSON(...args) { this.calls.push(["tilemap", ...args]); }
  image(...args) { this.calls.push(["image", ...args]); }
  atlas(...args) { this.calls.push(["atlas", ...args]); }
}

function sceneWithLoader() {
  return { load: new FakeLoader() };
}

function fallbackScene(tilemapExists, failedAssets = []) {
  let size = null;
  const layer = {
    setOrigin() { return this; },
    setDepth() { return this; },
    setDisplaySize(width, height) { size = [width, height]; return this; },
  };
  const mapLayer = {
    setDepth() { return this; },
    setCollisionByProperty() { return this; },
    setVisible() { return this; },
  };
  const map = {
    width: 176, height: 96, tileWidth: 16, tileHeight: 16,
    widthInPixels: 2816, heightInPixels: 1536,
    layers: manifest.tile_layers.map(name => ({name})),
    objects: manifest.object_layers.map(layer => ({name: layer.name})),
    addTilesetImage(name, key) { return { name, key }; },
    createLayer() { return mapLayer; },
    getObjectLayer() { return {objects: []}; },
  };
  return {
    __claudevilleWorld: { manifest, failedAssets: new Set(failedAssets) },
    cache: { tilemap: { exists: () => tilemapExists } },
    textures: { exists: () => true, get: () => ({setFilter() {}}) },
    make: { tilemap: () => map },
    add: { image: () => layer },
    fallbackSize: () => size,
  };
}

function testDynamicQueueAndCompletion() {
  const scene = sceneWithLoader();
  const validatedManifests = [];
  const state = renderer.queueWorld(
    scene,
    "http://example.test/static/assets/claudeville/world.json",
    "http://example.test/static/",
    value => validatedManifests.push(value)
  );
  assert.deepStrictEqual(scene.load.calls[0].slice(0, 2), ["json", "world-manifest"]);
  scene.load.emit("filecomplete-json-world-manifest", null, null, manifest);
  assert(scene.load.calls.some(call => call[0] === "json" && call[1] === "world-address-aliases"));
  scene.load.emit("filecomplete-json-world-address-aliases", null, null, aliasManifest);
  assert.deepStrictEqual(state.manifest.aliases, aliasManifest.aliases);
  assert.deepStrictEqual(installedAliases, aliasManifest.aliases);
  assert(scene.load.calls.some(call => call[0] === "tilemap"));
  const expectedImages = manifest.tilesets.length + 1 + manifest.facades.length +
    (manifest.scene_image_url ? 1 : 0);
  assert.strictEqual(scene.load.calls.filter(call => call[0] === "image").length, expectedImages);
  assert.strictEqual(
    scene.load.calls.filter(call => call[0] === "atlas").length,
    1 + (manifest.atlases || []).length
  );
  assert.strictEqual(validatedManifests.length, 1);
  assert.strictEqual(
    validatedManifests[0].resident_manifest_url,
    "http://example.test/static/assets/characters/manifest.json"
  );
  scene.load.emit("complete");
  assert.strictEqual(state.ready, true);
}

function testRootRelativeStaticRootUsesPageOrigin() {
  const originalLocation = global.location;
  global.location = { href: "http://example.test/demo/recording/0/4/" };
  try {
    const scene = sceneWithLoader();
    const state = renderer.queueWorld(
      scene,
      "/static/assets/claudeville/world.json",
      "/static/"
    );
    assert.strictEqual(
      scene.load.calls[0][2],
      "http://example.test/static/assets/claudeville/world.json"
    );
    scene.load.emit("filecomplete-json-world-manifest", null, null, manifest);
    scene.load.emit("filecomplete-json-world-address-aliases", null, null, aliasManifest);
    assert.strictEqual(state.error, null);
    assert(scene.load.calls.some(call =>
      call[0] === "tilemap" &&
      call[2] === new URL(manifest.tilemap_url, "http://example.test/static/").href
    ));
    assert.throws(
      () => renderer.safeUrl("https://evil.test/payload.png", global.location.href, "/static/"),
      /escapes/
    );
    assert.throws(
      () => renderer.safeUrl("../private.json", global.location.href, "/static/"),
      /traversal/
    );
  } finally {
    if (originalLocation === undefined) delete global.location;
    else global.location = originalLocation;
  }
}

function testInvalidAndFetchFailureFailClosed() {
  const manifestUrl = "http://example.test/static/assets/claudeville/world.json";
  const root = "http://example.test/static/";
  function expectInvalid(change, pattern) {
    const candidate = JSON.parse(JSON.stringify(manifest));
    change(candidate);
    assert.throws(
      () => renderer.validateWorldManifest(candidate, manifestUrl, root),
      pattern
    );
  }
  const invalid = JSON.parse(JSON.stringify(manifest));
  invalid.foreground_layers = ["not-a-layer"];
  expectInvalid(value => { value.foreground_layers = []; }, /foreground/);
  expectInvalid(value => { value.foreground_layers = ["not-a-layer"]; }, /foreground/);
  expectInvalid(value => { value.collision_layer = "not-a-layer"; }, /collision_layer/);
  expectInvalid(value => { value.collision_tileset = "not-a-tileset"; }, /collision_tileset/);
  expectInvalid(value => { value.tilesets.push(value.tilesets[0]); }, /unique/);
  expectInvalid(value => { value.scene_image_url = "assets/scene.png"; }, /does not accept/);
  expectInvalid(value => { value.aliases = {}; }, /external address aliases/);
  expectInvalid(value => { delete value.address_alias_manifest_url; }, /non-empty/);
  expectInvalid(value => { value.visual_dimensions.width -= 1; }, /pixel bounds/);
  expectInvalid(value => { value.layer_order.splice(10, 1); }, /13-layer/);
  expectInvalid(value => { value.collision_layer = "Wall"; }, /13-layer/);
  expectInvalid(value => { value.foreground_layers.reverse(); }, /13-layer/);
  expectInvalid(value => { value.tile_layers.splice(2, 1); }, /tile_layers/);
  expectInvalid(value => { value.object_layers.splice(0, 1); }, /object_layers/);
  expectInvalid(value => { value.object_layers[1].depth_mode = "foot-y"; }, /object_layers/);
  expectInvalid(value => { value.depth_model.overhead_depth = 1; }, /depth model/);
  expectInvalid(value => {
    value.object_layers = [{name: "Depth Props", atlas: "missing", depth_mode: "foot-y"}];
  }, /object layer/);
  expectInvalid(value => {
    value.resident_manifest_url = "../private-residents.json";
  }, /traversal/);

  const invalidScene = sceneWithLoader();
  const invalidState = renderer.queueWorld(
    invalidScene,
    "http://example.test/static/assets/claudeville/world.json",
    "http://example.test/static/"
  );
  invalidScene.load.emit("filecomplete-json-world-manifest", null, null, invalid);
  assert(invalidState.error instanceof Error);
  assert.strictEqual(invalidScene.load.calls.length, 1);

  const scene = sceneWithLoader();
  const state = renderer.queueWorld(
    scene,
    "http://example.test/static/assets/claudeville/world.json",
    "http://example.test/static/"
  );
  scene.load.emit("loaderror", { key: "world-manifest" });
  assert(state.error instanceof Error);
  assert.strictEqual(scene.load.calls.length, 1);

  assert.throws(() => renderer.validateAliasManifest({...aliasManifest, world: "Other"}, manifest.world));
  const badAliases = sceneWithLoader();
  const badAliasState = renderer.queueWorld(badAliases, manifestUrl, root);
  badAliases.load.emit("filecomplete-json-world-manifest", null, null, manifest);
  badAliases.load.emit("filecomplete-json-world-address-aliases", null, null,
    {...aliasManifest, aliases: []});
  assert(badAliasState.error instanceof Error);
}

function testCollisionLayerUsesOnlyDeclaredCollisionTileset() {
  const validatedVille = renderer.validateWorldManifest(
    villeManifest,
    "http://example.test/static/assets/the_ville/world.json",
    "http://example.test/static/"
  );
  assert.strictEqual(validatedVille.version, 1);
  assert.deepStrictEqual(validatedVille.aliases, villeManifest.aliases);
  let collisionNames = null;
  const layer = {
    setDepth() { return this; },
    setCollisionByProperty() { return this; },
  };
  const map = {
    widthInPixels: 4480,
    heightInPixels: 3200,
    addTilesetImage(name, key) { return { name, key }; },
    createLayer(name, tilesets) {
      if (name === villeManifest.collision_layer) {
        collisionNames = tilesets.map(tileset => tileset.name);
      }
      return layer;
    },
  };
  const scene = {
    cache: { tilemap: { exists: () => true } },
    make: { tilemap: () => map },
  };
  renderer.createWorld(scene, villeManifest);
  assert.deepStrictEqual(collisionNames, [villeManifest.collision_tileset]);
}

function testStaticRootContainment() {
  const manifestUrl = "http://example.test/static/assets/claudeville/world.json";
  const root = "http://example.test/static/";
  assert.throws(() => renderer.safeUrl("../../../../api/private", manifestUrl, root));
  assert.throws(() => renderer.safeUrl("/api/private", manifestUrl, root));
  assert.throws(() => renderer.safeUrl("../private.json", root, root));
  assert.throws(() => renderer.safeUrl("assets/claudeville/../private.json", root, root));
  assert.throws(() => renderer.safeUrl("assets/%2e%2e/private.json", root, root));
  assert.strictEqual(
    renderer.safeUrl("assets/claudeville/visuals/map.json", root, root),
    "http://example.test/static/assets/claudeville/visuals/map.json"
  );
}

function testTilesetFailureAndFallbackSizing() {
  const failedKey = manifest.tilesets[0].key;
  const failed = sceneWithLoader();
  renderer.queueWorld(
    failed,
    "http://example.test/static/assets/claudeville/world.json",
    "http://example.test/static/"
  );
  failed.load.emit("filecomplete-json-world-manifest", null, null, manifest);
  failed.load.emit("loaderror", { key: failedKey });
  const queuedState = failed.__claudevilleWorld;
  const renderSurface = fallbackScene(true);
  Object.assign(failed, renderSurface);
  failed.__claudevilleWorld = queuedState;
  const failedResult = renderer.createWorld(failed);
  assert.strictEqual(failedResult.usedFallback, true);
  assert.deepStrictEqual(renderSurface.fallbackSize(), [2816, 1536]);

  const missingMap = fallbackScene(false);
  const missingResult = renderer.createWorld(missingMap);
  assert.strictEqual(missingResult.usedFallback, true);
  assert.deepStrictEqual(missingMap.fallbackSize(), [2816, 1536]);
}

function testPointerCenteredZoomRefreshesDirtyCameraTransform() {
  class DirtyCamera {
    constructor(follow = null) {
      this.scrollX = 782;
      this.scrollY = 129;
      this.zoom = 1;
      this.matrixZoom = 1;
      this._follow = follow;
      this.preRenderCalls = 0;
    }
    getWorldPoint(x, y) {
      return {x: this.scrollX + x / this.matrixZoom,
        y: this.scrollY + y / this.matrixZoom};
    }
    setZoom(value) { this.zoom = value; return this; }
    preRender() { this.matrixZoom = this.zoom; this.preRenderCalls += 1; }
  }

  const pointer = {x: 640.17, y: 360};
  const camera = new DirtyCamera();
  const before = camera.getWorldPoint(pointer.x, pointer.y);
  renderer.zoomCameraAtPointer(camera, pointer, 0.9);
  const after = camera.getWorldPoint(pointer.x, pointer.y);
  assert(Math.abs(before.x - after.x) < 1e-9);
  assert(Math.abs(before.y - after.y) < 1e-9);
  assert.strictEqual(camera.preRenderCalls, 1);

  const followed = new DirtyCamera({x: 20, y: 30});
  renderer.zoomCameraAtPointer(followed, pointer, 0.9);
  assert.strictEqual(followed.zoom, 0.9);
  assert.deepStrictEqual([followed.scrollX, followed.scrollY], [782, 129]);
}

function testPermanentCutawayWorldHasNoRuntimeFacades() {
  const sprites = [];
  const layer = {setDepth() {return this;}, setVisible() {return this;},
    setCollisionByProperty() {return this;}};
  const map = {width: 176, height: 96, tileWidth: 16, tileHeight: 16,
    widthInPixels: 2816, heightInPixels: 1536,
    layers: manifest.tile_layers.map(name => ({name})),
    objects: manifest.object_layers.map(value => ({name: value.name})),
    addTilesetImage(name, key) {return {name, key};}, createLayer() {return layer;},
    getObjectLayer() {return {objects: []};}};
  const scene = {
    cache: {tilemap: {exists: () => true}}, make: {tilemap: () => map},
    add: {image(x, y, key) {
      const sprite = {x, y, key, alpha: 1, setOrigin() {return this;},
        setDepth(value) {this.depth = value; return this;},
        setAlpha(value) {this.alpha = value; return this;}};
      sprites.push(sprite);
      return sprite;
    }},
    tweens: {add(config) {config.targets.setAlpha(config.alpha);}},
  };
  const world = renderer.createWorld(scene, manifest);
  assert.strictEqual(world.facades.length, 0);
  world.setFocusedSector("University");
  world.setFocusedSector(null);
  assert.deepStrictEqual(world.facades, []);
}

function testV2ObjectLayersUseStableFramesFootDepthAndNearestFiltering() {
  const candidate = JSON.parse(JSON.stringify(manifest));
  candidate.atlases = [{key: "town-props", image_url: "assets/props.png",
    data_url: "assets/props.json"}];
  candidate.object_layers = [
    {name: "Depth Props", atlas: "town-props", depth_mode: "foot-y"},
    {name: "Overhead Props", atlas: "town-props", depth_mode: "fixed", depth: 90000},
  ];
  const validated = renderer.validateWorldManifest(
    candidate,
    "http://example.test/static/assets/claudeville/world.json",
    "http://example.test/static/"
  );
  const filters = [];
  const sprites = [];
  const tileLayer = {setDepth(value) {this.depth = value; return this;},
    setVisible(value) {this.visible = value; return this;},
    setCollisionByProperty() {return this;}};
  const map = {
    width: 176, height: 96, tileWidth: 16, tileHeight: 16,
    widthInPixels: 2816, heightInPixels: 1536,
    layers: candidate.tile_layers.map(name => ({name})),
    objects: candidate.object_layers.map(value => ({name: value.name})),
    addTilesetImage(name, key) {return {name, key};},
    createLayer() {return Object.assign({}, tileLayer);},
    getObjectLayer(name) {
      if (name === "Depth Props") return {objects: [{x: 320, y: 480, rotation: 0,
        properties: [{name: "asset_key", value: "prop.landscape.tree_09"},
          {name: "anchor_x", value: 0.5}, {name: "anchor_y", value: 1},
          {name: "display_scale", value: 2},
          {name: "foot_y", value: 470}, {name: "depth_offset", value: 3}]}]};
      return {objects: [{x: 640, y: 320, properties: [
        {name: "asset_key", value: "prop.plaza.fountain_blue"}]}]};
    },
  };
  const scene = {
    cache: {tilemap: {exists: () => true}}, make: {tilemap: () => map},
    textures: {get(key) {return {setFilter(mode) {filters.push([key, mode]);}};}},
    add: {image(x, y, key, frame) {
      const sprite = {x, y, key, frame,
        setOrigin(a, b) {this.origin = [a, b]; return this;},
        setScale(value) {this.scale = value; return this;},
        setDepth(value) {this.depth = value; return this;},
        setAngle() {return this;}, setFlipX() {return this;}, setFlipY() {return this;}};
      sprites.push(sprite); return sprite;
    }},
  };
  const world = renderer.createWorld(scene, validated);
  assert.strictEqual(world.usedFallback, false);
  assert.strictEqual(world.objectSprites.length, 2);
  assert.strictEqual(sprites[0].frame, "prop.landscape.tree_09");
  assert.deepStrictEqual(sprites[0].origin, [0.5, 1]);
  assert.strictEqual(sprites[0].scale, 2);
  assert.strictEqual(sprites[0].depth, 2473);
  assert.strictEqual(sprites[1].depth, 90000);
  assert.strictEqual(world.depthForFootY(470, 3), 2473);
  assert(filters.some(([key]) => key === "town-props"));
}

function testV2TilemapGridAndLayersAreExact() {
  const map = {
    width: 176, height: 96, tileWidth: 16, tileHeight: 16,
    widthInPixels: 2816, heightInPixels: 1536,
    layers: manifest.tile_layers.map(name => ({name})),
    objects: manifest.object_layers.map(value => ({name: value.name})),
  };
  assert.doesNotThrow(() => renderer.validateV2Tilemap(manifest, map));
  for (const changed of [
    {...map, width: 88},
    {...map, tileWidth: 32},
    {...map, layers: map.layers.slice(0, -1)},
    {...map, objects: map.objects.slice().reverse()},
  ]) assert.throws(() => renderer.validateV2Tilemap(manifest, changed));
}

testDynamicQueueAndCompletion();
testRootRelativeStaticRootUsesPageOrigin();
testInvalidAndFetchFailureFailClosed();
testStaticRootContainment();
testTilesetFailureAndFallbackSizing();
testCollisionLayerUsesOnlyDeclaredCollisionTileset();
testPointerCenteredZoomRefreshesDirtyCameraTransform();
testPermanentCutawayWorldHasNoRuntimeFacades();
testV2ObjectLayersUseStableFramesFootDepthAndNearestFiltering();
testV2TilemapGridAndLayersAreExact();
process.stdout.write(JSON.stringify({ ok: true }));
