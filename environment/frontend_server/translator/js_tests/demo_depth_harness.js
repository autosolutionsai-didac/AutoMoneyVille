"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const template = fs.readFileSync(process.argv[2], "utf8");
const adapter = require(path.resolve(process.argv[3]));
assert(template.includes("ClaudevilleCharacters.displayLayout(curr_persona)"));
assert(template.includes("ClaudevilleCharacters.depthForSprite("));
assert(template.includes("currShadow.y = spriteLayout.foot.y"));
assert(!template.includes("WORLD_DEPTH_BASE"));
assert(!template.includes("body.y + tile_width"));

const sprite = {
  x: 100, y: 200, characterScale: 1.25,
  frameDimensions: {width: 32, height: 32},
  logicalFootAnchor: {x: 0.5, y: 1},
  logicalFootOffset: {x: 0, y: 0},
  displayOriginX: 16, displayOriginY: 32,
  body: {x: 80, y: 160, scaleX: 1.25, scaleY: 1.25, offset: {x: 0, y: 0}},
};
const world = {depthForFootY: y => 2000 + y};
const initial = adapter.displayLayout(sprite);
const depth = adapter.depthForSprite(sprite, world);
assert.deepStrictEqual(initial.foot, {x: 100, y: 200});
assert.strictEqual(initial.top, 160);
assert.strictEqual(depth, 2200);

sprite.body.x += 32;
sprite.body.y += 32;
const moved = adapter.displayLayout(sprite);
const movedDepth = adapter.depthForSprite(sprite, world);
assert.deepStrictEqual(moved.foot, {x: 132, y: 232});
assert.strictEqual(movedDepth, 2232);
process.stdout.write(JSON.stringify({
  depth,
  initialShadow: [initial.foot.x, initial.foot.y],
  movedDepth,
  movingShadow: [moved.foot.x, moved.foot.y],
  ok: true,
}));
