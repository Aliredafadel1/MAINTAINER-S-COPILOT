(function () {
  "use strict";

  var script = document.currentScript;
  var widgetId = script.getAttribute("data-widget-id");
  var apiUrl = script.getAttribute("data-api-url") || window.location.origin;

  if (!widgetId) {
    console.warn("[MaintainersCopilot] data-widget-id is required");
    return;
  }

  // Dynamically load the compiled widget bundle
  var bundleScript = document.createElement("script");
  bundleScript.src = apiUrl + "/static/widget.iife.js";
  bundleScript.setAttribute("data-widget-id", widgetId);
  bundleScript.setAttribute("data-api-url", apiUrl);
  document.head.appendChild(bundleScript);
})();
