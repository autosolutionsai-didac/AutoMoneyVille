"use strict";

const assert = require("assert");
const hudModule = require(process.argv[2]);
const replayGuard = require(process.argv[3]);

class FakeClassList {
  constructor(values = []) { this.values = new Set(values); }
  contains(name) { return this.values.has(name); }
  remove(name) { this.values.delete(name); }
  toggle(name, force) {
    if (force === undefined) force = !this.values.has(name);
    if (force) this.values.add(name); else this.values.delete(name);
  }
}

class FakeElement {
  constructor(id, classes = []) {
    this.id = id;
    this.classList = new FakeClassList(classes);
    this.attributes = {};
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this.inert = false;
    this.focused = false;
    this.textContent = "";
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  getAttribute(name) { return this.attributes[name]; }
  focus() { this.focused = true; }
  click() {
    if (this.disabled || this.hidden || this.inert) return;
    this.listeners.click?.({preventDefault() {}, stopPropagation() {}});
  }
}

class FakeDocument {
  constructor() {
    this.readyState = "complete";
    this.listeners = {};
    this.elements = {};
    this.livePanels = [];
    this.liveToggles = [];
  }
  add(id, classes = []) {
    const element = new FakeElement(id, classes);
    this.elements[id] = element;
    return element;
  }
  getElementById(id) { return this.elements[id] || null; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  querySelectorAll(selector) {
    if (selector === "[data-live-mutation]") return [];
    if (selector === "[data-live-panel]") return this.livePanels;
    if (selector === "[data-live-panel-toggle]") return this.liveToggles;
    return [];
  }
  escape() {
    this.listeners.keydown?.({
      key: "Escape", preventDefault() {}, stopImmediatePropagation() {},
    });
  }
}

function fixture() {
  const document = new FakeDocument();
  const pairs = {
    personas: ["persona-panel", "toggle-panel", ["collapsed"]],
    events: ["event-feed", "feed-collapse", ["collapsed"]],
    town: ["town-center-panel", "town-center-toggle", []],
    runtime: ["runtime-status-panel", "runtime-status-toggle", []],
  };
  Object.values(pairs).forEach(([panel, toggle, classes]) => {
    document.add(panel, classes);
    document.add(toggle);
  });
  ["persona-panel-content", "event-feed-filters", "feed-list"].forEach(id => document.add(id));
  document.add("inspector-drawer", ["hidden"]);
  document.livePanels = [document.elements["town-center-panel"], document.elements["runtime-status-panel"]];
  document.liveToggles = [document.elements["town-center-toggle"], document.elements["runtime-status-toggle"]];
  return document;
}

function assertClosedAndInert(document, hud) {
  assert.strictEqual(hud.isOpen("personas"), false);
  assert.strictEqual(hud.isOpen("events"), false);
  assert.strictEqual(document.elements["persona-panel-content"].inert, true);
  assert.strictEqual(document.elements["event-feed-filters"].inert, true);
  assert.strictEqual(document.elements["feed-list"].inert, true);
  for (const name of ["town", "runtime"]) {
    const panel = document.elements[`${name === "town" ? "town-center" : "runtime-status"}-panel`];
    assert.strictEqual(hud.isOpen(name), false);
    assert.strictEqual(panel.hidden, true);
    assert.strictEqual(panel.inert, true);
  }
}

{
  const document = fixture();
  const hud = hudModule.create(document);
  hud.initialize();
  assertClosedAndInert(document, hud);
  document.elements["town-center-toggle"].click();
  assert.strictEqual(hud.isOpen("town"), true);
  document.elements["town-center-toggle"].click();
  assert.strictEqual(document.elements["town-center-toggle"].focused, true);
  document.elements["toggle-panel"].click();
  assert.strictEqual(document.elements["persona-panel-content"].inert, false);
  document.escape();
  assert.strictEqual(document.elements["persona-panel-content"].inert, true);
  assert.strictEqual(document.elements["toggle-panel"].focused, true);
}

for (const freezeFirst of [true, false]) {
  const document = fixture();
  const hud = hudModule.create(document);
  const guard = replayGuard.create("replay");
  if (freezeFirst) guard.freezeControls(document);
  hud.initialize();
  if (!freezeFirst) {
    document.elements["town-center-toggle"].click();
    guard.freezeControls(document);
  }
  assertClosedAndInert(document, hud);
  for (const toggle of document.liveToggles) {
    assert.strictEqual(toggle.hidden, true);
    assert.strictEqual(toggle.disabled, true);
    assert.strictEqual(toggle.inert, true);
    assert.strictEqual(toggle.getAttribute("aria-expanded"), "false");
    toggle.click();
  }
  assertClosedAndInert(document, hud);
}

process.stdout.write(JSON.stringify({ok: true}));
