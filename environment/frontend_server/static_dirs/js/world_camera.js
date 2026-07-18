(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClaudevilleCamera = api;
  if (root.ClaudevilleWorld) {
    root.ClaudevilleWorld.zoomCameraAtPointer = api.zoomCameraAtPointer;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function finitePositive(value, label) {
    if (!Number.isFinite(value) || value <= 0) {
      throw new TypeError(`${label} must be a positive finite number`);
    }
    return value;
  }

  function constrainFiniteWorld(camera, worldBounds) {
    if (!camera || typeof camera.setBounds !== "function") {
      throw new TypeError("finite-world camera requires setBounds");
    }
    const worldWidth = finitePositive(worldBounds?.width, "world width");
    const worldHeight = finitePositive(worldBounds?.height, "world height");
    const viewportWidth = finitePositive(camera.width, "camera width");
    const viewportHeight = finitePositive(camera.height, "camera height");
    const zoom = finitePositive(camera.zoom, "camera zoom");
    const visibleWidth = viewportWidth / zoom;
    const visibleHeight = viewportHeight / zoom;
    const padX = Math.max(0, (visibleWidth - worldWidth) / 2);
    const padY = Math.max(0, (visibleHeight - worldHeight) / 2);
    camera.setBounds(
      padX ? -padX : 0, padY ? -padY : 0,
      worldWidth + padX * 2, worldHeight + padY * 2
    );
    return camera;
  }

  function zoomCameraAtPointer(camera, pointer, nextZoom, worldBounds) {
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
    if (worldBounds) constrainFiniteWorld(camera, worldBounds);
    return camera;
  }

  return Object.freeze({constrainFiniteWorld, zoomCameraAtPointer});
});
