(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClaudevilleAddresses = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  let aliases = [];

  function setAliases(values) {
    if (!values || typeof values !== "object" || Array.isArray(values)) {
      throw new TypeError("world aliases must be an object");
    }
    aliases = Object.entries(values).map(([legacy, canonical]) => {
      if (!legacy.trim() || typeof canonical !== "string" || !canonical.trim()) {
        throw new TypeError("world aliases must map non-empty strings");
      }
      return [legacy, canonical];
    });
    aliases.sort((left, right) => right[0].length - left[0].length);
  }

  function translateText(value) {
    if (typeof value !== "string" || !value) return value || "";
    let translated = value;
    aliases.forEach(([legacy, canonical]) => {
      translated = translated.split(legacy).join(canonical);
    });
    return translated;
  }

  function displayAddress(value) {
    const translated = translateText(value);
    const parts = translated.split(":");
    if (parts.length > 1) parts.shift();
    return parts.join(" › ") || translated;
  }

  return { setAliases, translateText, displayAddress };
});
