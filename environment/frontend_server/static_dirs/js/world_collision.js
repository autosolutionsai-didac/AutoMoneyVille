(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClaudevilleWorldCollision = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function positiveInteger(value, label) {
    if (!Number.isInteger(value) || value <= 0) {
      throw new TypeError(`${label} must be a positive integer`);
    }
    return value;
  }

  function tileOccupied(tile) {
    if (Number.isInteger(tile)) return tile > 0;
    return Boolean(tile && Number.isInteger(tile.index) && tile.index >= 0);
  }

  function layerTile(layer, x, y, width) {
    const data = layer && layer.data;
    if (!Array.isArray(data)) throw new TypeError("collision layer data is unavailable");
    const row = data[y];
    if (Array.isArray(row)) return row[x];
    return data[y * width + x];
  }

  function createProjector(map, manifest) {
    if (!map || !manifest) throw new TypeError("map and manifest are required");
    const logical = manifest.dimensions;
    const visual = manifest.visual_dimensions;
    const width = positiveInteger(logical && logical.width, "logical width");
    const height = positiveInteger(logical && logical.height, "logical height");
    const visualWidth = positiveInteger(visual && visual.width, "visual width");
    const visualHeight = positiveInteger(visual && visual.height, "visual height");
    const ratioX = visualWidth / width;
    const ratioY = visualHeight / height;
    if (!Number.isInteger(ratioX) || ratioX < 1 || ratioX !== ratioY) {
      throw new TypeError("visual collision grid must evenly expand the logical grid");
    }
    const layer = Array.isArray(map.layers)
      ? map.layers.find(candidate => candidate && candidate.name === manifest.collision_layer)
      : null;
    if (!layer) throw new TypeError("declared collision layer is unavailable");

    function isBlocked(x, y) {
      if (!Number.isInteger(x) || !Number.isInteger(y) ||
          x < 0 || x >= width || y < 0 || y >= height) return true;
      for (let offsetY = 0; offsetY < ratioY; offsetY += 1) {
        for (let offsetX = 0; offsetX < ratioX; offsetX += 1) {
          if (tileOccupied(layerTile(
            layer, x * ratioX + offsetX, y * ratioY + offsetY, visualWidth
          ))) return true;
        }
      }
      return false;
    }

    function project(tile, maxRadius = 8) {
      if (!Array.isArray(tile) || tile.length < 2 ||
          !Number.isFinite(tile[0]) || !Number.isFinite(tile[1])) {
        throw new TypeError("logical tile must contain finite x/y coordinates");
      }
      const origin = [Math.round(tile[0]), Math.round(tile[1])];
      if (!isBlocked(origin[0], origin[1])) return origin;
      const limit = positiveInteger(maxRadius, "projection radius");
      for (let radius = 1; radius <= limit; radius += 1) {
        for (let dy = -radius; dy <= radius; dy += 1) {
          const dx = radius - Math.abs(dy);
          const candidates = dx === 0
            ? [[origin[0], origin[1] + dy]]
            : [[origin[0] - dx, origin[1] + dy], [origin[0] + dx, origin[1] + dy]];
          const match = candidates.find(candidate => !isBlocked(candidate[0], candidate[1]));
          if (match) return match;
        }
      }
      return origin;
    }

    return {isBlocked, project};
  }

  return {createProjector, tileOccupied};
});
