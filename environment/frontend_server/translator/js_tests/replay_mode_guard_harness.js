"use strict";

const assert = require("assert");
const replayGuard = require(process.argv[2]);

class FakeElement {
  constructor() {
    this.disabled = false;
    this.hidden = false;
    this.listeners = {};
  }

  addEventListener(name, callback) {
    this.listeners[name] = callback;
  }

  click() {
    this.listeners.click?.({ target: this });
  }
}

class FakeDocument {
  constructor() {
    this.listeners = {};
  }

  addEventListener(name, callback) {
    this.listeners[name] = callback;
  }

  dispatchSpace() {
    this.listeners.keydown?.({
      code: "Space",
      key: " ",
      target: { tagName: "BODY" },
      preventDefault() {},
    });
  }
}

function exercise(mode) {
  const document = new FakeDocument();
  const play = new FakeElement();
  const skip = new FakeElement();
  const state = { paused: true, skipping: false, liveFetches: 0 };
  const guard = replayGuard.create(mode);
  const liveFetch = () => { state.liveFetches += 1; };

  guard.bindMutationClick(play, () => {
    state.paused = false;
    liveFetch();
  });
  guard.bindMutationClick(skip, () => {
    state.skipping = true;
    liveFetch();
  });
  guard.bindMutationKey(document, "Space", () => {
    state.paused = false;
    liveFetch();
  });

  play.click();
  document.dispatchSpace();
  skip.click();
  return state;
}

assert.deepStrictEqual(exercise("replay"), {
  paused: true,
  skipping: false,
  liveFetches: 0,
});
assert.deepStrictEqual(exercise("simulate"), {
  paused: false,
  skipping: true,
  liveFetches: 3,
});
process.stdout.write(JSON.stringify({ ok: true }));
