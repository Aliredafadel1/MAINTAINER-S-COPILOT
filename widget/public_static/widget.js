(function () {
  "use strict";

  var script = document.currentScript ||
    document.querySelector("script[data-widget-id]");
  if (!script) return;

  var widgetId = script.getAttribute("data-widget-id");
  var apiUrl = script.getAttribute("data-api-url") || "http://localhost:8000";
  var base = script.src.replace(/\/widget\.js(\?.*)?$/, "");

  if (!widgetId) {
    console.warn("[MaintainersCopilot] data-widget-id is required");
    return;
  }

  // If the React app already mounted (e.g. via direct <script> tag), skip.
  if (document.getElementById("maintainers-copilot-root")) return;

  window.__MC_WIDGET_ID__ = widgetId;
  window.__MC_API_URL__ = apiUrl;

  var s = document.createElement("script");
  s.src = base + "/widget.iife.js";
  document.head.appendChild(s);
})();
