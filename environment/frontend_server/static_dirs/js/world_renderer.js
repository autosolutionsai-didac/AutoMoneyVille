(function (root, factory) {
  const api = factory(root);
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClaudevilleWorld = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";
  const MANIFEST_KEY = "world-manifest";
  const TILEMAP_KEY = "world-tilemap";
  const ALIASES_KEY = "world-address-aliases";
  const FALLBACK_KEY = "world-legacy-background";
  const SCENE_KEY = "world-authored-scene";
  const CHARACTER_KEY = "atlas";
  const DEFAULT_ACTOR_DEPTH = 2000;
  const DEFAULT_OVERHEAD_DEPTH = 90000;
  const V2_LAYER_ORDER = [
    "Bottom Ground", "Exterior Ground", "Exterior Decoration L1", "Exterior Decoration L2",
    "Interior Ground", "Wall", "Interior Furniture L1", "Interior Furniture L2",
    "Foreground L1", "Foreground L2", "Depth Props", "Overhead Props", "Collisions",
  ];
  const V2_OBJECT_LAYERS = ["Depth Props", "Overhead Props"];
  const V2_TILE_LAYERS = V2_LAYER_ORDER.filter(name => !V2_OBJECT_LAYERS.includes(name));
  function positiveInteger(value, label) {
    if (!Number.isInteger(value) || value <= 0) throw new TypeError(`${label} must be a positive integer`);
  }
  function finiteNumber(value, label) {
    if (!Number.isFinite(value)) throw new TypeError(`${label} must be finite`);
    return value;
  }
  function documentBase() {
    if (root.document && root.document.baseURI) return root.document.baseURI;
    if (root.location && root.location.href) return root.location.href;
    return "http://localhost/";
  }
  function safeUrl(value, baseUrl, allowedAssetRoot) {
    if (typeof value !== "string" || !value.trim() || value.startsWith("//"))
      throw new TypeError("world asset URLs must be non-empty relative or same-origin URLs");
    const rawPath = value.split(/[?#]/, 1)[0];
    if (/(^|[\\/])\.\.([\\/]|$)/.test(rawPath) || /%(2e|2f|5c)/i.test(rawPath)) {
      throw new TypeError(`world asset URL may not contain traversal: ${value}`);
    }
    if (typeof allowedAssetRoot !== "string" || !allowedAssetRoot.trim())
      throw new TypeError("an explicit allowed static asset root is required");
    const absoluteBase = new URL(baseUrl, documentBase());
    const resolved = new URL(value, absoluteBase);
    const allowed = new URL(allowedAssetRoot, absoluteBase);
    if (!allowed.pathname.endsWith("/")) allowed.pathname += "/";
    allowed.search = "";
    allowed.hash = "";
    if (!/^https?:$/.test(resolved.protocol) || resolved.origin !== allowed.origin ||
        !resolved.href.startsWith(allowed.href)) {
      throw new TypeError(`world asset URL escapes the allowed static root: ${value}`);
    }
    return resolved.href;
  }
  function validateAliases(values) {
    if (!values || typeof values !== "object" || Array.isArray(values))
      throw new TypeError("world aliases must be an object");
    Object.entries(values).forEach(([legacy, canonical]) => {
      if (!legacy.trim() || typeof canonical !== "string" || !canonical.trim())
        throw new TypeError("world aliases must map non-empty strings");
    });
    return values;
  }
  function validateAliasManifest(payload, world) {
    if (!payload || typeof payload !== "object" || Array.isArray(payload) ||
        payload.schema_version !== 1 || typeof payload.world !== "string" ||
        payload.world.toLowerCase() !== world.toLowerCase()) {
      throw new TypeError("world address alias manifest is invalid");
    }
    return Object.assign({}, validateAliases(payload.aliases));
  }
  function validateNames(values, label, {allowEmpty = false, referencedBy = null} = {}) {
    if (!Array.isArray(values) || (!allowEmpty && !values.length) ||
        new Set(values).size !== values.length ||
        values.some(name => typeof name !== "string" || !name ||
          (referencedBy && !referencedBy.includes(name)))) {
      throw new TypeError(`${label} must contain unique${allowEmpty ? "" : " referenced"} names`);
    }
    return values;
  }
  function resolveTilesets(manifest, allowedAssetRoot) {
    if (!Array.isArray(manifest.tilesets) || !manifest.tilesets.length)
      throw new TypeError("world tilesets must be a non-empty array");
    const names = manifest.tilesets.map(value => value && value.name);
    const keys = manifest.tilesets.map(value => value && value.key);
    if (new Set(names).size !== names.length || new Set(keys).size !== keys.length)
      throw new TypeError("world tileset names and keys must be unique");
    return manifest.tilesets.map((tileset, index) => {
      if (!tileset || typeof tileset.name !== "string" || !tileset.name ||
          typeof tileset.key !== "string" || !tileset.key) {
        throw new TypeError(`world tileset ${index} needs name and key`);
      }
      return Object.assign({}, tileset, {
        image_url: safeUrl(tileset.image_url, allowedAssetRoot, allowedAssetRoot),
      });
    });
  }
  function resolveFacades(manifest, allowedAssetRoot) {
    const facades = manifest.facades || [];
    if (!Array.isArray(facades) || new Set(facades.map(item => item && item.key)).size !== facades.length ||
        new Set(facades.map(item => item && item.sector)).size !== facades.length) {
      throw new TypeError("world facades must use unique keys and sectors");
    }
    return facades.map((facade, index) => {
      const position = facade && facade.position;
      const size = facade && facade.native_size;
      if (!facade || typeof facade.key !== "string" || !/^facade-[a-z0-9-]+$/.test(facade.key) ||
          typeof facade.sector !== "string" || !facade.sector.trim() ||
          !Array.isArray(position) || position.length !== 2 ||
          position.some(value => !Number.isInteger(value) || value < 0) ||
          !Array.isArray(size) || size.length !== 2 ||
          size.some(value => !Number.isInteger(value) || value <= 0) ||
          !Number.isFinite(facade.depth) || facade.depth < 0 ||
          !Number.isFinite(facade.fade_alpha) || facade.fade_alpha < 0 || facade.fade_alpha > 1) {
        throw new TypeError(`world facade ${index} is invalid`);
      }
      return Object.assign({}, facade, {
        image_url: safeUrl(facade.image_url, allowedAssetRoot, allowedAssetRoot),
      });
    });
  }
  function resolveV2(manifest, resolved, allowedAssetRoot) {
    if (Object.prototype.hasOwnProperty.call(manifest, "scene_image_url"))
      throw new TypeError("world manifest v2 does not accept scene_image_url");
    if (Object.prototype.hasOwnProperty.call(manifest, "aliases"))
      throw new TypeError("world manifest v2 requires external address aliases");
    if (manifest.layer_order.length !== V2_LAYER_ORDER.length ||
        manifest.layer_order.some((name, index) => name !== V2_LAYER_ORDER[index]) ||
        manifest.collision_layer !== "Collisions" || manifest.foreground_layers.length !== 2 ||
        manifest.foreground_layers.some((name, index) => name !== V2_LAYER_ORDER[index + 8])) {
      throw new TypeError("world manifest v2 requires the ordered 13-layer contract");
    }
    resolved.tile_layers = validateNames(manifest.tile_layers, "tile_layers", {referencedBy: manifest.layer_order});
    if (resolved.tile_layers.length !== V2_TILE_LAYERS.length ||
        resolved.tile_layers.some((name, index) => name !== V2_TILE_LAYERS[index])) {
      throw new TypeError("world manifest v2 tile_layers do not match the layer contract");
    }
    const visual = manifest.visual_dimensions || {};
    positiveInteger(visual.width, "visual world width");
    positiveInteger(visual.height, "visual world height");
    positiveInteger(visual.tile_size, "visual world tile size");
    if (visual.width * visual.tile_size !== manifest.dimensions.width * manifest.dimensions.tile_size ||
        visual.height * visual.tile_size !== manifest.dimensions.height * manifest.dimensions.tile_size) {
      throw new TypeError("visual_dimensions must preserve the logical world pixel bounds");
    }
    resolved.visual_dimensions = Object.assign({}, visual);
    resolved.address_alias_manifest_url = safeUrl(manifest.address_alias_manifest_url, allowedAssetRoot, allowedAssetRoot);
    resolved.aliases = {};
    const rendering = manifest.rendering || {};
    if (rendering.texture_filter !== "nearest")
      throw new TypeError("world manifest v2 requires nearest texture filtering");
    resolved.rendering = {texture_filter: "nearest"};
    const depth = manifest.depth_model || {};
    finiteNumber(depth.actor_base, "depth_model.actor_base");
    finiteNumber(depth.overhead_depth, "depth_model.overhead_depth");
    if (depth.actor_base < 0 || depth.overhead_depth <= depth.actor_base)
      throw new TypeError("world depth model must place overhead above actors");
    resolved.depth_model = {actor_base: depth.actor_base, overhead_depth: depth.overhead_depth};
    const atlases = manifest.atlases === undefined ? [] : manifest.atlases;
    if (!Array.isArray(atlases) || new Set(atlases.map(value => value && value.key)).size !== atlases.length)
      throw new TypeError("world atlases must use unique keys");
    resolved.atlases = atlases.map((atlas, index) => {
      if (!atlas || typeof atlas.key !== "string" || !/^[A-Za-z0-9_.-]+$/.test(atlas.key)) {
        throw new TypeError(`world atlas ${index} has an invalid key`);
      }
      return Object.assign({}, atlas, {
        image_url: safeUrl(atlas.image_url, allowedAssetRoot, allowedAssetRoot),
        data_url: safeUrl(atlas.data_url, allowedAssetRoot, allowedAssetRoot),
      });
    });
    const atlasKeys = resolved.atlases.map(value => value.key);
    if (resolved.tilesets.some(value => atlasKeys.includes(value.key)))
      throw new TypeError("world atlas and tileset keys must be unique");
    const objectLayers = manifest.object_layers === undefined ? [] : manifest.object_layers;
    if (!Array.isArray(objectLayers) ||
        new Set(objectLayers.map(value => value && value.name)).size !== objectLayers.length) {
      throw new TypeError("world object_layers must use unique names");
    }
    resolved.object_layers = objectLayers.map((layer, index) => {
      if (!layer || typeof layer.name !== "string" || !layer.name ||
          typeof layer.atlas !== "string" || !atlasKeys.includes(layer.atlas) ||
          !["foot-y", "fixed"].includes(layer.depth_mode)) {
        throw new TypeError(`world object layer ${index} is invalid`);
      }
      if (layer.depth_mode === "fixed") finiteNumber(layer.depth, `${layer.name}.depth`);
      return Object.assign({}, layer);
    });
    if (resolved.object_layers.length !== V2_OBJECT_LAYERS.length ||
        resolved.object_layers.some((layer, index) => layer.name !== V2_OBJECT_LAYERS[index]) ||
        resolved.object_layers[0].depth_mode !== "foot-y" || resolved.object_layers[1].depth_mode !== "fixed") {
      throw new TypeError("world manifest v2 object_layers do not match the layer contract");
    }
  }
  function validateWorldManifest(manifest, manifestUrl, allowedAssetRoot) {
    if (!manifest || typeof manifest !== "object" || Array.isArray(manifest))
      throw new TypeError("world manifest must be an object");
    if (![1, 2].includes(manifest.version)) throw new TypeError("unsupported world manifest version");
    if (typeof manifest.world !== "string" || !/^[a-z0-9_]+$/.test(manifest.world))
      throw new TypeError("world manifest has an invalid world id");
    const dimensions = manifest.dimensions || {};
    positiveInteger(dimensions.width, "world width");
    positiveInteger(dimensions.height, "world height");
    positiveInteger(dimensions.tile_size, "world tile size");
    validateNames(manifest.layer_order, "layer_order");
    validateNames(manifest.foreground_layers, "foreground_layers", {
      referencedBy: manifest.layer_order,
    });
    if (typeof manifest.collision_layer !== "string" || !manifest.layer_order.includes(manifest.collision_layer))
      throw new TypeError("collision_layer must reference layer_order");
    const resolved = Object.assign({}, manifest, {
      tilemap_url: safeUrl(manifest.tilemap_url, allowedAssetRoot, allowedAssetRoot),
      character_manifest_url: safeUrl(
        manifest.character_manifest_url, allowedAssetRoot, allowedAssetRoot
      ),
      character_atlas_image_url: safeUrl(
        manifest.character_atlas_image_url, allowedAssetRoot, allowedAssetRoot
      ),
      resident_manifest_url: safeUrl(
        manifest.resident_manifest_url, allowedAssetRoot, allowedAssetRoot
      ),
      legacy_background_fallback_url: safeUrl(
        manifest.legacy_background_fallback_url, allowedAssetRoot, allowedAssetRoot
      ),
      tilesets: resolveTilesets(manifest, allowedAssetRoot),
      facades: resolveFacades(manifest, allowedAssetRoot),
    });
    const tilesetNames = resolved.tilesets.map(value => value.name);
    if (typeof manifest.collision_tileset !== "string" || !tilesetNames.includes(manifest.collision_tileset))
      throw new TypeError("collision_tileset must reference a declared tileset");
    if (manifest.version === 2) {
      resolveV2(manifest, resolved, allowedAssetRoot);
    } else {
      resolved.aliases = Object.assign({}, validateAliases(manifest.aliases));
      resolved.tile_layers = manifest.layer_order.slice();
      resolved.object_layers = [];
      resolved.atlases = [];
      resolved.depth_model = {actor_base: DEFAULT_ACTOR_DEPTH, overhead_depth: DEFAULT_OVERHEAD_DEPTH};
      if (manifest.scene_image_url !== undefined) {
        resolved.scene_image_url = safeUrl(
          manifest.scene_image_url, allowedAssetRoot, allowedAssetRoot
        );
      }
    }
    return resolved;
  }
  function zoomCameraAtPointer(camera, pointer, nextZoom) {
    if (!camera || typeof camera.getWorldPoint !== "function" ||
        typeof camera.setZoom !== "function" || typeof camera.preRender !== "function" ||
        !pointer || !Number.isFinite(pointer.x) || !Number.isFinite(pointer.y) ||
        !Number.isFinite(nextZoom) || nextZoom <= 0) {
      throw new TypeError("pointer-centered zoom requires a valid camera, pointer, and zoom");
    }
    const worldBefore = camera.getWorldPoint(pointer.x, pointer.y);
    camera.setZoom(nextZoom);
    if (!camera._follow) {
      camera.preRender();
      const worldAfter = camera.getWorldPoint(pointer.x, pointer.y);
      camera.scrollX += worldBefore.x - worldAfter.x;
      camera.scrollY += worldBefore.y - worldAfter.y;
    }
    return camera;
  }
  function queueWorld(scene, manifestUrl, allowedAssetRoot, onManifest) {
    if (onManifest !== undefined && typeof onManifest !== "function")
      throw new TypeError("world manifest callback must be a function");
    const resolvedManifestUrl = safeUrl(manifestUrl, documentBase(), allowedAssetRoot);
    const state = {manifest: null, error: null, failedAssets: new Set(), ready: false};
    scene.__claudevilleWorld = state;
    scene.load.on("loaderror", file => {
      const key = file && file.key || "unknown";
      if (key === MANIFEST_KEY) state.error = Error("world manifest failed to load");
      else if (key === ALIASES_KEY) state.error = Error("world address aliases failed to load");
      else state.failedAssets.add(key);
    });
    scene.load.once("complete", () => { state.ready = Boolean(state.manifest && !state.error); });
    scene.load.json(MANIFEST_KEY, resolvedManifestUrl);
    scene.load.once(`filecomplete-json-${MANIFEST_KEY}`, (_key, _type, payload) => {
      try {
        const manifest = validateWorldManifest(payload, resolvedManifestUrl, allowedAssetRoot);
        state.manifest = manifest;
        if (manifest.version === 2) {
          scene.load.json(ALIASES_KEY, manifest.address_alias_manifest_url);
          scene.load.once(`filecomplete-json-${ALIASES_KEY}`, (_aliasKey, _aliasType, aliasPayload) => {
            try {
              manifest.aliases = validateAliasManifest(aliasPayload, manifest.world);
              if (root.ClaudevilleAddresses) root.ClaudevilleAddresses.setAliases(manifest.aliases);
            } catch (error) {
              state.error = error;
              if (root.console) root.console.error("Invalid world address aliases", error);
            }
          });
        } else if (root.ClaudevilleAddresses) root.ClaudevilleAddresses.setAliases(manifest.aliases);
        if (onManifest) onManifest(manifest);
        scene.load.tilemapTiledJSON(TILEMAP_KEY, manifest.tilemap_url);
        manifest.tilesets.forEach(value => scene.load.image(value.key, value.image_url));
        manifest.atlases.forEach(value => scene.load.atlas(value.key, value.image_url, value.data_url));
        scene.load.image(FALLBACK_KEY, manifest.legacy_background_fallback_url);
        if (manifest.scene_image_url) scene.load.image(SCENE_KEY, manifest.scene_image_url);
        manifest.facades.forEach(value => scene.load.image(value.key, value.image_url));
        scene.load.atlas(CHARACTER_KEY, manifest.character_atlas_image_url, manifest.character_manifest_url);
      } catch (error) {
        state.error = error;
        if (root.console) root.console.error("Invalid world manifest", error);
      }
    });
    return state;
  }
  function depthForFootY(manifestOrDepth, footY, offset = 0) {
    const depth = manifestOrDepth && manifestOrDepth.depth_model || manifestOrDepth || {};
    const base = Number.isFinite(depth.actor_base) ? depth.actor_base : DEFAULT_ACTOR_DEPTH;
    finiteNumber(footY, "footY");
    finiteNumber(offset, "depth offset");
    return base + footY + offset;
  }
  function applyNearest(scene, keys) {
    const mode = root.Phaser && root.Phaser.Textures && root.Phaser.Textures.FilterMode
      ? root.Phaser.Textures.FilterMode.NEAREST : 1;
    if (!scene.textures || typeof scene.textures.get !== "function") return;
    keys.forEach(key => {
      const texture = scene.textures.get(key);
      if (texture && typeof texture.setFilter === "function") texture.setFilter(mode);
    });
  }
  function objectProperties(object) {
    const result = {};
    (object && Array.isArray(object.properties) ? object.properties : []).forEach(property => {
      if (property && typeof property.name === "string") result[property.name] = property.value;
    });
    return result;
  }
  function createObjectSprites(scene, map, manifest) {
    const entries = [];
    manifest.object_layers.forEach(definition => {
      const layer = typeof map.getObjectLayer === "function" ? map.getObjectLayer(definition.name) : null;
      if (!layer || !Array.isArray(layer.objects))
        throw Error(`world object layer unavailable: ${definition.name}`);
      layer.objects.forEach(object => {
        const properties = objectProperties(object);
        if (object.visible === false || properties.visible === false) return;
        const assetKey = properties.asset_key;
        if (typeof assetKey !== "string" || !/^[A-Za-z0-9_.-]+$/.test(assetKey))
          throw Error(`world object in ${definition.name} needs asset_key`);
        const texture = scene.textures && typeof scene.textures.get === "function"
          ? scene.textures.get(definition.atlas) : null;
        if (texture && typeof texture.has === "function" && !texture.has(assetKey))
          throw Error(`world atlas ${definition.atlas} has no frame ${assetKey}`);
        const anchorX = properties.anchor_x === undefined ? 0.5 : properties.anchor_x;
        const anchorY = properties.anchor_y === undefined ? 1 : properties.anchor_y;
        if (![anchorX, anchorY].every(Number.isFinite) || anchorX < 0 || anchorX > 1 ||
            anchorY < 0 || anchorY > 1 || !Number.isFinite(object.x) || !Number.isFinite(object.y)) {
          throw Error(`world object ${assetKey} has invalid anchor or position`);
        }
        const offset = properties.depth_offset === undefined ? 0 : properties.depth_offset;
        finiteNumber(offset, `${assetKey}.depth_offset`);
        const displayScale = properties.display_scale === undefined ? 1 : properties.display_scale;
        if (!Number.isFinite(displayScale) || displayScale <= 0 || displayScale > 4)
          throw Error(`world object ${assetKey} has invalid display_scale`);
        const sprite = scene.add.image(object.x, object.y, definition.atlas, assetKey)
          .setOrigin(anchorX, anchorY);
        if (typeof sprite.setScale === "function") sprite.setScale(displayScale);
        const footY = properties.foot_y === undefined ? object.y : properties.foot_y;
        const depth = definition.depth_mode === "foot-y"
          ? depthForFootY(manifest, footY, offset) : definition.depth + offset;
        sprite.setDepth(depth);
        if (typeof sprite.setAngle === "function" && Number.isFinite(object.rotation)) {
          sprite.setAngle(object.rotation);
        }
        if (typeof sprite.setFlipX === "function") sprite.setFlipX(Boolean(object.flippedHorizontal));
        if (typeof sprite.setFlipY === "function") sprite.setFlipY(Boolean(object.flippedVertical));
        entries.push({definition, object, sprite, displayScale});
      });
    });
    return entries;
  }
  function fallbackWorld(scene, manifest) {
    const dimensions = manifest.dimensions;
    const bounds = {
      width: dimensions.width * dimensions.tile_size,
      height: dimensions.height * dimensions.tile_size,
    };
    if (!scene.textures || scene.textures.exists(FALLBACK_KEY)) {
      scene.add.image(0, 0, FALLBACK_KEY).setOrigin(0, 0)
        .setDisplaySize(bounds.width, bounds.height).setDepth(-1);
    }
    return {
      bounds, layers: [], objectSprites: [], facades: [], sceneImage: null,
      depthForFootY: (footY, offset) => depthForFootY(manifest, footY, offset),
      setFocusedSector() {}, usedFallback: true,
    };
  }
  function createFacades(scene, manifest) {
    const facades = manifest.facades.map(definition => ({
      definition,
      sprite: scene.add.image(definition.position[0], definition.position[1], definition.key)
        .setOrigin(0, 0).setDepth(definition.depth),
    }));
    const setFocusedSector = sector => {
      facades.forEach(entry => {
        const alpha = entry.definition.sector === sector ? entry.definition.fade_alpha : 1;
        if (scene.tweens && typeof scene.tweens.add === "function") {
          scene.tweens.add({targets: entry.sprite, alpha, duration: 180, ease: "Sine.easeOut"});
        } else if (typeof entry.sprite.setAlpha === "function") entry.sprite.setAlpha(alpha);
        else entry.sprite.alpha = alpha;
      });
    };
    return {facades, setFocusedSector};
  }
  function validateV2Tilemap(manifest, map) {
    const visual = manifest.visual_dimensions;
    if (map.width !== visual.width || map.height !== visual.height ||
        map.tileWidth !== visual.tile_size || map.tileHeight !== visual.tile_size ||
        map.widthInPixels !== visual.width * visual.tile_size ||
        map.heightInPixels !== visual.height * visual.tile_size) {
      throw Error("world tilemap grid does not match manifest visual_dimensions");
    }
    const tileNames = Array.isArray(map.layers) ? map.layers.map(layer => layer && layer.name) : [];
    const objectNames = Array.isArray(map.objects) ? map.objects.map(layer => layer && layer.name) : [];
    if (tileNames.length !== V2_TILE_LAYERS.length ||
        tileNames.some((name, index) => name !== V2_TILE_LAYERS[index]) ||
        objectNames.length !== V2_OBJECT_LAYERS.length ||
        objectNames.some((name, index) => name !== V2_OBJECT_LAYERS[index])) {
      throw Error("world tilemap does not implement the ordered 13-layer contract");
    }
  }
  function createWorld(scene, explicitManifest) {
    const sourceManifest = explicitManifest || scene.__claudevilleWorld && scene.__claudevilleWorld.manifest;
    if (!sourceManifest) throw scene.__claudevilleWorld && scene.__claudevilleWorld.error ||
      Error("world manifest unavailable");
    const manifest = Object.assign({
      atlases: [], object_layers: [], facades: [], tile_layers: sourceManifest.layer_order,
      depth_model: {actor_base: DEFAULT_ACTOR_DEPTH, overhead_depth: DEFAULT_OVERHEAD_DEPTH},
    }, sourceManifest);
    const loadState = scene.__claudevilleWorld;
    const failed = loadState && loadState.failedAssets || new Set();
    const requiredKeys = [TILEMAP_KEY]
      .concat(manifest.tilesets.map(value => value.key))
      .concat(manifest.atlases.map(value => value.key))
      .concat(manifest.facades.map(value => value.key));
    if (manifest.scene_image_url) requiredKeys.push(SCENE_KEY);
    if (loadState && loadState.error || requiredKeys.some(key => failed.has(key)) ||
        !scene.cache.tilemap.exists(TILEMAP_KEY)) {
      return fallbackWorld(scene, manifest);
    }
    try {
      applyNearest(scene, manifest.tilesets.map(value => value.key)
        .concat(manifest.atlases.map(value => value.key), CHARACTER_KEY));
      const map = scene.make.tilemap({key: TILEMAP_KEY});
      const expectedBounds = {
        width: manifest.dimensions.width * manifest.dimensions.tile_size,
        height: manifest.dimensions.height * manifest.dimensions.tile_size,
      };
      if (manifest.version === 2) validateV2Tilemap(manifest, map);
      const tilesetByName = {};
      const tilesets = manifest.tilesets.map(definition => {
        const value = map.addTilesetImage(definition.name, definition.key);
        tilesetByName[definition.name] = value;
        return value;
      }).filter(Boolean);
      if (!tilesets.length) throw Error("world tilesets unavailable");
      const layers = manifest.tile_layers.map((name, index) => {
        const selected = name === manifest.collision_layer
          ? [tilesetByName[manifest.collision_tileset]] : tilesets;
        const layer = map.createLayer(name, selected, 0, 0);
        if (!layer) throw Error(`world layer unavailable: ${name}`);
        if (name === manifest.collision_layer) {
          layer.setCollisionByProperty({collide: true}).setDepth(-100000);
          if (typeof layer.setVisible === "function") layer.setVisible(false);
        } else if (manifest.foreground_layers.includes(name)) {
          layer.setDepth(manifest.depth_model.overhead_depth + index);
        } else {
          layer.setDepth(-1000 + index);
        }
        if (manifest.version === 1 && manifest.scene_image_url &&
            typeof layer.setVisible === "function") layer.setVisible(false);
        return layer;
      });
      const sceneImage = manifest.scene_image_url
        ? scene.add.image(0, 0, SCENE_KEY).setOrigin(0, 0).setDepth(-2) : null;
      const objectSprites = createObjectSprites(scene, map, manifest);
      const facadeController = createFacades(scene, manifest);
      return {
        bounds: {width: map.widthInPixels, height: map.heightInPixels},
        layers, objectSprites, facades: facadeController.facades, sceneImage,
        depthForFootY: (footY, offset) => depthForFootY(manifest, footY, offset),
        setFocusedSector: facadeController.setFocusedSector,
        usedFallback: false,
      };
    } catch (error) {
      if (root.console) root.console.error("Tilemap render failed; using fallback", error);
      return fallbackWorld(scene, manifest);
    }
  }

  return {
    safeUrl, validateWorldManifest, queueWorld, createWorld, zoomCameraAtPointer,
    depthForFootY, objectProperties, validateAliasManifest, validateV2Tilemap,
  };
});
