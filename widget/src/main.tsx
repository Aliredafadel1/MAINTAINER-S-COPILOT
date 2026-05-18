import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

function mount(widgetId: string, apiUrl: string) {
  const host = document.createElement("div");
  host.id = "maintainers-copilot-root";
  document.body.appendChild(host);

  // Shadow DOM for style isolation
  const shadow = host.attachShadow({ mode: "open" });
  const mountPoint = document.createElement("div");
  shadow.appendChild(mountPoint);

  ReactDOM.createRoot(mountPoint).render(
    <React.StrictMode>
      <App widgetId={widgetId} apiUrl={apiUrl} />
    </React.StrictMode>
  );
}

// Auto-initialize from the loader script's data attributes
const loaderScript = document.currentScript as HTMLScriptElement | null;
if (loaderScript) {
  const widgetId = loaderScript.dataset.widgetId ?? "";
  const apiUrl = loaderScript.dataset.apiUrl ?? "http://localhost:8000";
  if (widgetId) mount(widgetId, apiUrl);
}
