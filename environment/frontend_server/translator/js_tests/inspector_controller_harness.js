"use strict";

const assert = require("assert");
const inspector = require(process.argv[2]);

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return {promise, resolve};
}

async function run() {
  const pending = [];
  const states = [];
  const errors = [];
  const focused = [];
  const controller = inspector.create({
    fetch(url) {
      const item = deferred();
      pending.push({url, ...item});
      return item.promise;
    },
    source: {url: name => `/state/${name}`},
    addresses: {
      translateText: value => value.replace("Oficina de Gobierno", "Town Hall"),
    },
    onState: state => states.push(state.name),
    onError: error => errors.push(error),
    onFocus: sector => focused.push(sector),
  });

  const first = controller.open("Nora Vale");
  const second = controller.open("Milo Chen");
  pending[1].resolve({ok: true, json: async () => ({name: "Milo Chen", address: "Claudeville:Bank:main"})});
  await second;
  pending[0].resolve({ok: true, json: async () => ({name: "Nora Vale", address: "Claudeville:Library:study"})});
  await first;
  assert.deepStrictEqual(states, ["Milo Chen"]);
  assert.deepStrictEqual(focused, ["Bank"]);

  const legacy = controller.open("Iris Morgan");
  pending[2].resolve({ok: true, json: async () => ({name: "Iris Morgan", address: "Claudeville:Oficina de Gobierno:main"})});
  await legacy;
  assert.strictEqual(focused.at(-1), "Town Hall");

  const closing = controller.open("Theo Grant");
  controller.close();
  pending[3].resolve({ok: false, json: async () => ({error: "stale failure"})});
  await closing;
  assert.deepStrictEqual(errors, []);
  assert.strictEqual(focused.at(-1), null);
  assert.deepStrictEqual(states, ["Milo Chen", "Iris Morgan"]);
}

run().then(
  () => process.stdout.write(JSON.stringify({ok: true})),
  error => { console.error(error); process.exitCode = 1; },
);
