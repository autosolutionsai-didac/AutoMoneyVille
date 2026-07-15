(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClaudevilleInspectorController = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function canonicalSector(address, addresses) {
    const raw = String(address || "");
    const canonical = typeof addresses?.translateText === "function"
      ? addresses.translateText(raw)
      : raw;
    const parts = canonical.split(":");
    return parts.length > 1 && parts[1].trim() ? parts[1].trim() : null;
  }

  function create(options) {
    if (!options || typeof options.fetch !== "function" || !options.source) {
      throw new Error("Inspector controller options are invalid");
    }
    const onState = options.onState || (() => {});
    const onError = options.onError || (() => {});
    const onFocus = options.onFocus || (() => {});
    let openName = null;
    let generation = 0;
    let activeRequest = null;

    function abortActive() {
      activeRequest?.abort();
      activeRequest = null;
    }

    async function refresh() {
      if (!openName) return;
      const requestedName = openName;
      const requestedGeneration = ++generation;
      abortActive();
      const request = typeof AbortController === "function" ? new AbortController() : null;
      activeRequest = request;
      try {
        const response = await options.fetch(
          options.source.url(requestedName),
          request ? {signal: request.signal} : undefined,
        );
        const state = await response.json();
        if (requestedGeneration !== generation || requestedName !== openName) return;
        activeRequest = null;
        if (!response.ok || state.error) {
          onError(state.error || "Inspector unavailable (backend offline?)");
          return;
        }
        onState(state, requestedName);
        onFocus(canonicalSector(state.address, options.addresses));
      } catch (error) {
        if (
          requestedGeneration !== generation || requestedName !== openName ||
          error?.name === "AbortError"
        ) return;
        activeRequest = null;
        onError("Inspector unavailable");
      }
    }

    function open(name) {
      if (typeof name !== "string" || !name.trim()) {
        throw new Error("Persona name is required");
      }
      openName = name;
      return refresh();
    }

    function close() {
      openName = null;
      generation += 1;
      abortActive();
      onFocus(null);
    }

    return Object.freeze({
      close,
      currentName() { return openName; },
      open,
      refresh,
    });
  }

  return Object.freeze({canonicalSector, create});
});
