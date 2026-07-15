"use strict";

const assert = require("assert");
const fs = require("fs");
global.ClaudevilleWorld = {};
const cameraApi = require(process.argv[2]);
const controls = fs.readFileSync(process.argv[3], "utf8");
const WORLD = {width: 2816, height: 1536};

class FakeCamera {
  constructor({width, height, zoom, scrollX = 0, scrollY = 0, follow = null}) {
    Object.assign(this, {width, height, zoom, scrollX, scrollY});
    this.matrixZoom = zoom;
    this._follow = follow;
    this.preRenderCalls = 0;
    this.bounds = {x: 0, y: 0, width: WORLD.width, height: WORLD.height};
  }
  get displayWidth() { return this.width / this.zoom; }
  get displayHeight() { return this.height / this.zoom; }
  clampX(value) {
    const low = this.bounds.x + (this.displayWidth - this.width) / 2;
    const high = Math.max(low, low + this.bounds.width - this.displayWidth);
    return Math.max(low, Math.min(high, value));
  }
  clampY(value) {
    const low = this.bounds.y + (this.displayHeight - this.height) / 2;
    const high = Math.max(low, low + this.bounds.height - this.displayHeight);
    return Math.max(low, Math.min(high, value));
  }
  getWorldPoint(x, y) {
    return {x: this.scrollX + x / this.matrixZoom,
      y: this.scrollY + y / this.matrixZoom};
  }
  setBounds(x, y, width, height) {
    this.bounds = {x, y, width, height};
    this.scrollX = this.clampX(this.scrollX);
    this.scrollY = this.clampY(this.scrollY);
    return this;
  }
  setZoom(value) { this.zoom = value; return this; }
  preRender() {
    this.scrollX = this.clampX(this.scrollX);
    this.scrollY = this.clampY(this.scrollY);
    this.matrixZoom = this.zoom;
    this.preRenderCalls += 1;
  }
}

function close(actual, expected) {
  assert(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);
}

function testOversizedViewportCentersBothAxes() {
  const camera = new FakeCamera({
    width: 1440, height: 900, zoom: 0.3, scrollX: 1680, scrollY: 1050,
  });
  cameraApi.constrainFiniteWorld(camera, WORLD);
  assert.deepStrictEqual(camera.bounds, {x: -992, y: -732, width: 4800, height: 3000});
  assert.deepStrictEqual([camera.scrollX, camera.scrollY], [688, 318]);
  assert.deepStrictEqual(
    [camera.scrollX + camera.width / 2, camera.scrollY + camera.height / 2],
    [WORLD.width / 2, WORLD.height / 2]
  );
  camera.scrollX = -5000;
  camera.scrollY = 9000;
  camera.preRender();
  assert.deepStrictEqual([camera.scrollX, camera.scrollY], [688, 318]);
}

function testOnlyOversizedAxisIsCentered() {
  const camera = new FakeCamera({
    width: 1600, height: 720, zoom: 0.5, scrollX: 0, scrollY: 400,
  });
  cameraApi.constrainFiniteWorld(camera, WORLD);
  assert.deepStrictEqual(camera.bounds, {x: -192, y: 0, width: 3200, height: 1536});
  assert.strictEqual(camera.scrollX + camera.width / 2, WORLD.width / 2);
  assert.strictEqual(camera.scrollY, 400);
}

function testNormalZoomRestoresWorldClamping() {
  const camera = new FakeCamera({
    width: 1600, height: 720, zoom: 0.8, scrollX: 9999, scrollY: 9999,
  });
  cameraApi.constrainFiniteWorld(camera, WORLD);
  assert.deepStrictEqual(camera.bounds, {x: 0, y: 0, width: 2816, height: 1536});
  assert.deepStrictEqual([camera.scrollX, camera.scrollY], [1016, 726]);
}

function testPointerAnchorAndFollowSurviveConstraint() {
  const pointer = {x: 640.17, y: 360};
  const camera = new FakeCamera({
    width: 1000, height: 700, zoom: 1, scrollX: 782, scrollY: 329,
  });
  const before = camera.getWorldPoint(pointer.x, pointer.y);
  cameraApi.zoomCameraAtPointer(camera, pointer, 0.9, WORLD);
  const after = camera.getWorldPoint(pointer.x, pointer.y);
  close(before.x, after.x);
  close(before.y, after.y);
  assert.strictEqual(camera.preRenderCalls, 1);

  const followed = new FakeCamera({
    width: 1000, height: 700, zoom: 1, scrollX: 782, scrollY: 329, follow: {x: 20},
  });
  cameraApi.zoomCameraAtPointer(followed, pointer, 0.9, WORLD);
  assert.strictEqual(followed.zoom, 0.9);
  assert.strictEqual(followed.preRenderCalls, 0);
  assert.deepStrictEqual([followed.scrollX, followed.scrollY], [782, 329]);
}

function testValidationAndTemplateWiring() {
  assert.strictEqual(global.ClaudevilleWorld.zoomCameraAtPointer,
    cameraApi.zoomCameraAtPointer);
  assert.throws(() => cameraApi.constrainFiniteWorld({}, WORLD), TypeError);
  assert.throws(() => cameraApi.constrainFiniteWorld(
    new FakeCamera({width: 10, height: 10, zoom: 1}), {width: 0, height: 20}
  ), TypeError);
  assert(controls.includes(
    "ClaudevilleCamera.zoomCameraAtPointer(camera, pointer, zoomLevel, mapBounds);"
  ));
  assert(controls.match(/ClaudevilleCamera\.constrainFiniteWorld\(camera, mapBounds\);/g).length >= 2);
}

testOversizedViewportCentersBothAxes();
testOnlyOversizedAxisIsCentered();
testNormalZoomRestoresWorldClamping();
testPointerAnchorAndFollowSurviveConstraint();
testValidationAndTemplateWiring();
process.stdout.write(JSON.stringify({ok: true}));
