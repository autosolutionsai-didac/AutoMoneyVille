(function (root, factory) {
  const moduleApi = factory();
  if (typeof module === "object" && module.exports) module.exports = moduleApi;
  if (!root.document) return;
  const controller = moduleApi.create(root.document);
  root.ClaudevilleHUD = controller;
  if (root.document.readyState === "loading") {
    root.document.addEventListener("DOMContentLoaded", controller.initialize, {once: true});
  } else {
    controller.initialize();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const definitions = {
    personas: {
      panel: "persona-panel", toggle: "toggle-panel",
      content: ["persona-panel-content"],
    },
    events: {
      panel: "event-feed", toggle: "feed-collapse",
      content: ["event-feed-filters", "feed-list"],
    },
    town: {panel: "town-center-panel", toggle: "town-center-toggle", secondary: true},
    runtime: {panel: "runtime-status-panel", toggle: "runtime-status-toggle", secondary: true},
  };

  function setInert(element, value) {
    if (!element) return;
    element.inert = value;
    if (value) element.setAttribute("inert", "");
    else element.removeAttribute("inert");
  }

  function create(document) {
    let initialized = false;

    function elements(name) {
      const definition = definitions[name];
      return definition ? {
        definition,
        panel: document.getElementById(definition.panel),
        toggle: document.getElementById(definition.toggle),
      } : null;
    }

    function isOpen(name) {
      const entry = elements(name);
      if (!entry?.panel) return false;
      return entry.definition.secondary
        ? entry.panel.classList.contains("hud-open") && !entry.panel.hidden
        : !entry.panel.classList.contains("collapsed");
    }

    function toggleUnavailable(toggle) {
      return !toggle || toggle.disabled || toggle.hidden || toggle.inert;
    }

    function setContentState(definition, open) {
      (definition.content || []).forEach(id => {
        const content = document.getElementById(id);
        setInert(content, !open);
        content?.setAttribute("aria-hidden", String(!open));
      });
    }

    function setOpen(name, requestedOpen, restoreFocus = false) {
      const entry = elements(name);
      if (!entry?.panel || !entry.toggle) return;
      const open = Boolean(requestedOpen && !toggleUnavailable(entry.toggle));
      if (entry.definition.secondary) {
        entry.panel.classList.toggle("hud-open", open);
        entry.panel.hidden = !open;
        setInert(entry.panel, !open);
        entry.panel.setAttribute("aria-hidden", String(!open));
      } else {
        entry.panel.classList.toggle("collapsed", !open);
        setContentState(entry.definition, open);
        entry.toggle.textContent = name === "events"
          ? (open ? "▶" : "◀")
          : (open ? "◀" : "▶");
        entry.toggle.setAttribute("aria-label", `${open ? "Close" : "Open"} ${name}`);
      }
      entry.toggle.setAttribute("aria-expanded", String(open));
      if (!open && restoreFocus && !toggleUnavailable(entry.toggle)) entry.toggle.focus();
    }

    function closeDrawers(except) {
      Object.keys(definitions).forEach(name => {
        if (name !== except) setOpen(name, false);
      });
    }

    function toggle(name) {
      const entry = elements(name);
      if (!entry || toggleUnavailable(entry.toggle)) return;
      const next = !isOpen(name);
      closeDrawers(next ? name : null);
      setOpen(name, next, !next);
    }

    function inspectorOpen() {
      const inspector = document.getElementById("inspector-drawer");
      return Boolean(inspector && !inspector.classList.contains("hidden"));
    }

    function blocksCameraInput(target) {
      if (target?.closest?.(".ui-overlay, .menu-overlay")) return true;
      return inspectorOpen() || Object.keys(definitions).some(isOpen);
    }

    function initialize() {
      if (initialized) return;
      initialized = true;
      closeDrawers(null);
      Object.keys(definitions).forEach(name => {
        const entry = elements(name);
        entry?.toggle?.addEventListener("click", event => {
          event.preventDefault();
          event.stopPropagation();
          toggle(name);
        });
      });
      document.addEventListener("keydown", event => {
        if (event.key !== "Escape") return;
        const openDrawers = Object.keys(definitions).filter(isOpen);
        if (!openDrawers.length && !inspectorOpen()) return;
        openDrawers.forEach((name, index) => {
          setOpen(name, false, index === openDrawers.length - 1);
        });
        if (inspectorOpen()) document.getElementById("inspector-close")?.click();
        event.preventDefault();
        event.stopImmediatePropagation();
      }, true);
    }

    return Object.freeze({
      blocksCameraInput,
      closeDrawers,
      initialize,
      inspectorOpened() { closeDrawers(null); },
      isOpen,
      setOpen,
      toggle,
    });
  }

  return Object.freeze({create});
});
