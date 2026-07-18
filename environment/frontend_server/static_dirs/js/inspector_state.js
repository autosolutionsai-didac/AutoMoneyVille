(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClaudevilleInspectorSource = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  function create(options) {
    if (!options || typeof options !== "object") {
      throw new Error("Inspector source options are required");
    }
    const isReplay = options.mode === "replay";
    const template = isReplay
      ? options.replayUrlTemplate
      : options.liveUrlTemplate;
    if (typeof template !== "string" || !template.includes("PERSONA_NAME")) {
      throw new Error("Inspector URL template is invalid");
    }
    return Object.freeze({
      shouldPoll: !isReplay,
      url(name) {
        if (typeof name !== "string" || !name.trim()) {
          throw new Error("Persona name is required");
        }
        return template.replace("PERSONA_NAME", encodeURIComponent(name));
      },
    });
  }

  function readableList(items) {
    if (items.length < 2) return items[0] || "none";
    if (items.length === 2) return `${items[0]} and ${items[1]}`;
    return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
  }

  function scopeSummary(state) {
    if (!state || state.state_scope !== "final-recorded-memory") return "";
    const scopedNow = [
      ["position", state.position_scope],
      ["current status", state.currently_scope],
      ["action", state.action_scope],
      ["address", state.address_scope],
    ];
    const stepLocal = scopedNow
      .filter(([, scope]) => scope === "environment-step")
      .map(([name]) => name);
    const finalRecorded = scopedNow
      .filter(([, scope]) => scope !== "environment-step")
      .map(([name]) => name)
      .concat(["schedule", "goals", "relationships", "memories"]);
    return `Replay step ${state.effective_step} (requested ${state.requested_step}). ` +
      `Step-local: ${readableList(stepLocal)}. ` +
      `Final recorded persona state: ${readableList(finalRecorded)}.`;
  }

  return {create, scopeSummary};
});
