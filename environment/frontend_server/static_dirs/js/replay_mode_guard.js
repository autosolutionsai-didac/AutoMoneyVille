(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.ClaudevilleReplayGuard = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function setInert(element, value) {
    element.inert = value;
    if (value) element.setAttribute?.("inert", "");
    else element.removeAttribute?.("inert");
  }

  function create(mode) {
    const replay = mode === "replay";
    return {
      canMutate() {
        return !replay;
      },
      bindMutationClick(element, callback) {
        element.addEventListener("click", event => {
          if (!replay) callback(event);
        });
      },
      bindMutationKey(target, code, callback) {
        target.addEventListener("keydown", event => {
          if (event.code === code && !replay) callback(event);
        });
      },
      freezeControls(document) {
        if (!replay) return;
        document.querySelectorAll("[data-live-mutation]").forEach(element => {
          element.disabled = true;
          element.hidden = true;
          setInert(element, true);
        });
        document.querySelectorAll("[data-live-panel-toggle]").forEach(element => {
          element.disabled = true;
          element.hidden = true;
          setInert(element, true);
          element.setAttribute?.("aria-expanded", "false");
        });
        document.querySelectorAll("[data-live-panel]").forEach(element => {
          element.hidden = true;
          setInert(element, true);
          element.classList?.remove("hud-open");
          element.setAttribute?.("aria-hidden", "true");
        });
      },
    };
  }

  return { create };
});
