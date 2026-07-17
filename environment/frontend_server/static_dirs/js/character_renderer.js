(function (root, factory) {
  const api = factory(root);
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClaudevilleCharacters = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  const MANIFEST_KEY = "character-manifest";
  const DIRECTIONS = ["down", "left", "right", "up"];
  const DEFAULT_FALLBACK_ACTOR_DEPTH = 2000;
  const ACTIVE_RESIDENTS = [
    "Nora Vale", "Milo Chen", "Iris Morgan", "Theo Grant", "Lena Ortiz",
    "Ravi Singh", "June Park", "Amara Cole", "Felix Reed", "Sofia Lane",
  ];
  let activeManifest = null;

  function safeUrl(value, allowedAssetRoot) {
    if (typeof value !== "string" || !value.trim() || value.startsWith("//")) {
      throw new TypeError("character asset URLs must be non-empty and contained");
    }
    const path = value.split(/[?#]/, 1)[0];
    if (/(^|[\\/])\.\.([\\/]|$)/.test(path) || /%(2e|2f|5c)/i.test(path)) {
      throw new TypeError(`character asset URL contains traversal: ${value}`);
    }
    const allowed = new URL(allowedAssetRoot, documentBase());
    if (!allowed.pathname.endsWith("/")) allowed.pathname += "/";
    allowed.search = "";
    allowed.hash = "";
    const resolved = new URL(value, allowed);
    if (!/^https?:$/.test(resolved.protocol) || resolved.origin !== allowed.origin ||
        !resolved.href.startsWith(allowed.href)) {
      throw new TypeError(`character asset URL escapes the static root: ${value}`);
    }
    return resolved.href;
  }

  function documentBase() {
    if (root.document && root.document.baseURI) return root.document.baseURI;
    if (root.location && root.location.href) return root.location.href;
    return "http://localhost/";
  }

  function validateFrames(values, frameCount, label) {
    if (!Array.isArray(values) || !values.length ||
        values.some(value => !Number.isInteger(value) || value < 0 || value >= frameCount)) {
      throw new TypeError(`${label} must contain valid frame indices`);
    }
  }

  function validateDirectionalAnimations(group, frameCount, label) {
    if (!group || typeof group !== "object" || Array.isArray(group) ||
        Object.keys(group).length !== DIRECTIONS.length ||
        DIRECTIONS.some(direction => !Object.prototype.hasOwnProperty.call(group, direction))) {
      throw new TypeError(`${label} must define down, left, right, and up`);
    }
    DIRECTIONS.forEach(direction => validateFrames(
      group[direction], frameCount, `${label}.${direction}`
    ));
  }

  function sheetFrameCount(sheet, frame, label) {
    const values = [sheet.width, sheet.height, frame.width, frame.height];
    if (values.some(value => !Number.isInteger(value) || value <= 0)) {
      throw new TypeError(`${label} sheet and frame dimensions must be positive integers`);
    }
    const margin = sheet.margin === undefined ? 0 : sheet.margin;
    const spacing = sheet.spacing === undefined ? 0 : sheet.spacing;
    if (![margin, spacing].every(Number.isInteger) || margin < 0 || spacing < 0) {
      throw new TypeError(`${label} sheet margin and spacing must be non-negative integers`);
    }
    const usableWidth = sheet.width - (2 * margin);
    const usableHeight = sheet.height - (2 * margin);
    const columns = Math.floor((usableWidth + spacing) / (frame.width + spacing));
    const rows = Math.floor((usableHeight + spacing) / (frame.height + spacing));
    if (columns < 1 || rows < 1 ||
        columns * frame.width + Math.max(0, columns - 1) * spacing !== usableWidth ||
        rows * frame.height + Math.max(0, rows - 1) * spacing !== usableHeight) {
      throw new TypeError(`${label} frame grid must exactly divide its sheet`);
    }
    return columns * rows;
  }

  function applyNearest(scene, key) {
    const mode = root.Phaser && root.Phaser.Textures && root.Phaser.Textures.FilterMode
      ? root.Phaser.Textures.FilterMode.NEAREST : 1;
    if (!scene.textures || typeof scene.textures.get !== "function") return;
    const texture = scene.textures.get(key);
    if (texture && typeof texture.setFilter === "function") texture.setFilter(mode);
  }

  function validateCharacterManifest(manifest, allowedAssetRoot) {
    if (!manifest || typeof manifest !== "object" || Array.isArray(manifest) ||
        ![1, 2].includes(manifest.schema_version)) {
      throw new TypeError("unsupported character manifest");
    }
    if (manifest.schema_version === 2 &&
        (!manifest.rendering || manifest.rendering.texture_filter !== "nearest")) {
      throw new TypeError("character manifest v2 requires nearest texture filtering");
    }
    if (!Array.isArray(manifest.active_residents) || manifest.active_residents.length !== 10 ||
        new Set(manifest.active_residents).size !== 10 ||
        !Array.isArray(manifest.residents) || manifest.residents.length !== 10) {
      throw new TypeError("character manifest must define ten unique active residents");
    }
    if (ACTIVE_RESIDENTS.some((name, index) => manifest.active_residents[index] !== name)) {
      throw new TypeError("character manifest must use the exact active resident roster");
    }
    const generation = manifest.generation;
    if (!generation || typeof generation !== "object" || Array.isArray(generation) ||
        generation.default_activation !== false) {
      throw new TypeError("generation.default_activation must be false");
    }
    if (generation.free_pack_allowed !== false) {
      throw new TypeError("generation.free_pack_allowed must be false");
    }
    const names = new Set();
    const keys = new Set();
    const sprites = new Set();
    const portraits = new Set();
    const residents = manifest.residents.map(resident => {
      if (!resident || typeof resident.name !== "string" ||
          typeof resident.texture_key !== "string" ||
          !/^[A-Za-z0-9_]+$/.test(resident.texture_key) ||
          typeof resident.source !== "string" || !resident.source.trim()) {
        throw new TypeError("resident identity and source are required");
      }
      if (names.has(resident.name) || keys.has(resident.texture_key)) {
        throw new TypeError("resident names and texture keys must be unique");
      }
      names.add(resident.name);
      keys.add(resident.texture_key);
      const sheet = resident.sheet || {};
      const frame = resident.frame || {};
      const frameCount = sheetFrameCount(sheet, frame, resident.name);
      const origin = resident.origin || {};
      if (![origin.x, origin.y].every(Number.isFinite) ||
          origin.x < 0 || origin.x > 1 || origin.y < 0 || origin.y > 1 ||
          !Number.isFinite(resident.scale) || resident.scale <= 0) {
        throw new TypeError("resident origin and scale are invalid");
      }
      const footOffset = resident.foot_offset === undefined
        ? {x: 0, y: 0} : resident.foot_offset;
      if (!footOffset || typeof footOffset !== "object" || Array.isArray(footOffset) ||
          ![footOffset.x, footOffset.y].every(Number.isFinite) ||
          Math.abs(footOffset.x) > frame.width || Math.abs(footOffset.y) > frame.height) {
        throw new TypeError("resident foot_offset must be a bounded finite x/y pair");
      }
      const animations = resident.animations || {};
      validateDirectionalAnimations(animations.idle, frameCount, `${resident.name}.idle`);
      validateDirectionalAnimations(animations.walk, frameCount, `${resident.name}.walk`);
      const actions = animations.actions === undefined ? {} : animations.actions;
      if (!actions || typeof actions !== "object" || Array.isArray(actions)) {
        throw new TypeError(`${resident.name}.actions must be an object`);
      }
      Object.entries(actions).forEach(([action, frames]) => {
        if (!action.trim()) throw new TypeError(`${resident.name}.actions needs named actions`);
        validateFrames(frames, frameCount, `${resident.name}.actions.${action}`);
      });
      const crop = resident.portrait_crop || {};
      if (![crop.x, crop.y, crop.width, crop.height].every(Number.isInteger) ||
          crop.x < 0 || crop.y < 0 || crop.width < 1 || crop.height < 1) {
        throw new TypeError("resident portrait crop is invalid");
      }
      const spriteUrl = safeUrl(resident.sprite_url, allowedAssetRoot);
      const portraitUrl = safeUrl(resident.portrait_url, allowedAssetRoot);
      if (sprites.has(spriteUrl) || portraits.has(portraitUrl)) {
        throw new TypeError("resident sprite and portrait URLs must be unique");
      }
      sprites.add(spriteUrl);
      portraits.add(portraitUrl);
      return Object.assign({}, resident, {
        sprite_url: spriteUrl,
        portrait_url: portraitUrl,
        foot_offset: {x: footOffset.x, y: footOffset.y},
      });
    });
    if (ACTIVE_RESIDENTS.some(name => !names.has(name))) {
      throw new TypeError("resident entries must match the exact active resident roster");
    }
    return Object.assign({}, manifest, {residents});
  }

  function queueCharacters(scene, manifestUrl, allowedAssetRoot) {
    const resolvedManifestUrl = safeUrl(manifestUrl, allowedAssetRoot);
    const state = {manifest: null, error: null, failedTextures: new Set()};
    scene.__claudevilleCharacters = state;
    scene.load.on("loaderror", file => {
      const key = file && file.key;
      if (key === MANIFEST_KEY) state.error = Error("character manifest failed to load");
      else if (key) state.failedTextures.add(key);
    });
    scene.load.json(MANIFEST_KEY, resolvedManifestUrl);
    scene.load.once(`filecomplete-json-${MANIFEST_KEY}`, (_key, _type, payload) => {
      try {
        const manifest = validateCharacterManifest(payload, allowedAssetRoot);
        state.manifest = manifest;
        activeManifest = manifest;
        manifest.residents.forEach(resident => {
          scene.load.spritesheet(resident.texture_key, resident.sprite_url, {
            frameWidth: resident.frame.width,
            frameHeight: resident.frame.height,
            margin: resident.sheet.margin || 0,
            spacing: resident.sheet.spacing || 0,
          });
        });
        if (root.document) applyPortraits(root.document, manifest, allowedAssetRoot);
      } catch (error) {
        state.error = error;
        if (root.console) root.console.error("Invalid character manifest", error);
      }
    });
    return state;
  }

  function manifestIndex(manifest) {
    const entries = manifest && Array.isArray(manifest.residents) ? manifest.residents : [];
    const index = new Map();
    entries.forEach(resident => {
      index.set(resident.name, resident);
      index.set(resident.texture_key, resident);
    });
    return index;
  }

  function residentFor(manifest, name) {
    const index = manifestIndex(manifest);
    return index.get(name) || index.get(String(name).replace(/_/g, " ")) || null;
  }

  function createAnimation(scene, key, frames) {
    if (scene.anims.exists(key)) return;
    scene.anims.create({key, frames, frameRate: 4, repeat: -1});
  }

  function createFallbackAnimations(scene) {
    const prefixes = {down: "down-walk.", left: "left-walk.",
      right: "right-walk.", up: "up-walk."};
    DIRECTIONS.forEach(direction => createAnimation(
      scene,
      `fallback-${direction}-walk`,
      scene.anims.generateFrameNames("atlas", {
        prefix: prefixes[direction], start: 0, end: 3, zeroPad: 3,
      })
    ));
  }

  function createAnimations(scene, residentNames) {
    const manifest = scene.__claudevilleCharacters && scene.__claudevilleCharacters.manifest;
    if (!manifest) {
      createFallbackAnimations(scene);
      return;
    }
    let needsFallback = false;
    [...new Set(residentNames || [])].forEach(name => {
      const resident = residentFor(manifest, name);
      if (!resident || (scene.textures && !scene.textures.exists(resident.texture_key))) {
        needsFallback = true;
        return;
      }
      applyNearest(scene, resident.texture_key);
      DIRECTIONS.forEach(direction => createAnimation(
        scene,
        `${resident.texture_key}-${direction}-walk`,
        scene.anims.generateFrameNumbers(resident.texture_key, {
          frames: resident.animations.walk[direction],
        })
      ));
    });
    if (needsFallback) createFallbackAnimations(scene);
  }

  function createSprite(scene, residentName, x, y) {
    const manifest = scene.__claudevilleCharacters && scene.__claudevilleCharacters.manifest;
    const resident = residentFor(manifest, residentName);
    const hasTexture = resident && (!scene.textures || scene.textures.exists(resident.texture_key));
    const sprite = hasTexture
      ? scene.physics.add.sprite(x, y, resident.texture_key, resident.animations.idle.down[0])
      : scene.physics.add.sprite(x, y, "atlas", "down");
    applyNearest(scene, hasTexture ? resident.texture_key : "atlas");
    const origin = resident ? resident.origin : {x: 0.5, y: 1};
    const scale = resident ? resident.scale : 1;
    const footOffset = resident ? resident.foot_offset : {x: 0, y: 0};
    sprite.setOrigin(origin.x, origin.y);
    sprite.setScale(scale);
    sprite.spriteKey = hasTexture ? resident.texture_key : null;
    sprite.characterName = resident ? resident.name : String(residentName).replace(/_/g, " ");
    sprite.characterScale = scale;
    sprite.logicalFootAnchor = {x: origin.x, y: origin.y};
    sprite.logicalFootOffset = {x: footOffset.x, y: footOffset.y};
    sprite.frameDimensions = resident
      ? {width: resident.frame.width, height: resident.frame.height}
      : {width: 32, height: 32};
    if (typeof sprite.setSize === "function" && typeof sprite.setOffset === "function") {
      // Movement packets store the logical foot in body.x/body.y. A one-pixel
      // proxy at the frame origin keeps that coordinate independent of art size.
      sprite.setSize(1, 1).setOffset(
        sprite.frameDimensions.width * origin.x,
        sprite.frameDimensions.height * origin.y
      );
      if (sprite.body && typeof sprite.body.updateFromGameObject === "function") {
        sprite.body.updateFromGameObject();
      }
    }
    return sprite;
  }

  function axisScale(sprite, axis) {
    const direct = axis === "x" ? sprite.scaleX : sprite.scaleY;
    const value = Number.isFinite(direct) ? direct
      : Number.isFinite(sprite.characterScale) ? sprite.characterScale
        : Number.isFinite(sprite.scale) ? sprite.scale : 1;
    return Math.abs(value);
  }

  function displayOrigin(sprite, scaleX, scaleY, frame, origin) {
    let x = sprite.x;
    let y = sprite.y;
    const body = sprite.body;
    const offset = body && body.offset;
    if (body && offset && Number.isFinite(body.x) && Number.isFinite(offset.x)) {
      const displayOriginX = Number.isFinite(sprite.displayOriginX)
        ? sprite.displayOriginX : frame.width * origin.x;
      const bodyScaleX = Number.isFinite(body.scaleX) ? Math.abs(body.scaleX) : scaleX;
      x = body.x - bodyScaleX * (offset.x - displayOriginX);
    }
    if (body && offset && Number.isFinite(body.y) && Number.isFinite(offset.y)) {
      const displayOriginY = Number.isFinite(sprite.displayOriginY)
        ? sprite.displayOriginY : frame.height * origin.y;
      const bodyScaleY = Number.isFinite(body.scaleY) ? Math.abs(body.scaleY) : scaleY;
      y = body.y - bodyScaleY * (offset.y - displayOriginY);
    }
    if (![x, y].every(Number.isFinite)) {
      throw new TypeError("character sprite needs a finite display position");
    }
    return {x, y};
  }

  function displayLayout(sprite) {
    if (!sprite || typeof sprite !== "object") {
      throw new TypeError("character sprite is required");
    }
    const frame = sprite.frameDimensions || {width: 32, height: 32};
    const origin = sprite.logicalFootAnchor || {x: 0.5, y: 1};
    const footOffset = sprite.logicalFootOffset || {x: 0, y: 0};
    if (![frame.width, frame.height].every(value => Number.isFinite(value) && value > 0) ||
        ![origin.x, origin.y, footOffset.x, footOffset.y].every(Number.isFinite)) {
      throw new TypeError("character display metadata is invalid");
    }
    const scaleX = axisScale(sprite, "x");
    const scaleY = axisScale(sprite, "y");
    const position = displayOrigin(sprite, scaleX, scaleY, frame, origin);
    const width = frame.width * scaleX;
    const height = frame.height * scaleY;
    return {
      left: position.x - width * origin.x,
      top: position.y - height * origin.y,
      width,
      height,
      foot: {
        x: position.x + footOffset.x * scaleX,
        y: position.y + footOffset.y * scaleY,
      },
    };
  }

  function displayWorldFoot(sprite) {
    return displayLayout(sprite).foot;
  }

  function depthForSprite(sprite, worldController, fallbackActorBase = DEFAULT_FALLBACK_ACTOR_DEPTH) {
    if (!Number.isFinite(fallbackActorBase)) {
      throw new TypeError("fallback actor depth must be finite");
    }
    const foot = displayWorldFoot(sprite);
    if (worldController && typeof worldController.depthForFootY === "function") {
      const depth = worldController.depthForFootY(foot.y);
      if (Number.isFinite(depth)) return depth;
    }
    return fallbackActorBase + foot.y;
  }

  function playWalk(scene, sprite, residentName, direction) {
    if (!DIRECTIONS.includes(direction)) throw new TypeError(`invalid walk direction: ${direction}`);
    const manifest = scene.__claudevilleCharacters && scene.__claudevilleCharacters.manifest;
    const resident = residentFor(manifest, residentName);
    const key = sprite.spriteKey && resident
      ? `${resident.texture_key}-${direction}-walk`
      : `fallback-${direction}-walk`;
    sprite.anims.play(key, true);
  }

  function setIdle(scene, sprite, residentName, direction) {
    if (!DIRECTIONS.includes(direction)) direction = "down";
    const manifest = scene.__claudevilleCharacters && scene.__claudevilleCharacters.manifest;
    const resident = residentFor(manifest, residentName);
    sprite.anims.stop();
    if (sprite.spriteKey && resident) {
      sprite.setFrame(resident.animations.idle[direction][0]);
    } else {
      sprite.setTexture("atlas", direction);
    }
  }

  function portraitUrl(manifest, residentName, allowedAssetRoot) {
    const resident = residentFor(manifest || activeManifest, residentName);
    if (!resident) return null;
    return safeUrl(resident.portrait_url, allowedAssetRoot);
  }

  function applyPortraits(documentLike, manifest, allowedAssetRoot) {
    const nodes = documentLike.querySelectorAll("[data-character-portrait]");
    nodes.forEach(image => {
      const resident = residentFor(manifest, image.dataset.characterPortrait);
      if (!resident) return;
      const crop = resident.portrait_crop;
      image.src = portraitUrl(manifest, resident.name, allowedAssetRoot);
      image.style.objectPosition = `${-crop.x}px ${-crop.y}px`;
      if (!image.style.width) {
        image.style.width = `${crop.width}px`;
        image.style.height = `${crop.height}px`;
      }
    });
  }

  return {
    safeUrl,
    validateCharacterManifest,
    queueCharacters,
    createAnimations,
    createSprite,
    displayLayout,
    displayWorldFoot,
    depthForSprite,
    playWalk,
    setIdle,
    portraitUrl,
    applyPortraits,
  };
});
