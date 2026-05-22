import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

function mount(widgetId: string, apiUrl: string) {
  const host = document.createElement("div");
  host.id = "maintainers-copilot-root";
  document.body.appendChild(host);
  ReactDOM.createRoot(host).render(
    <React.StrictMode>
      <App widgetId={widgetId} apiUrl={apiUrl} />
    </React.StrictMode>
  );
}

// Globals set synchronously by widget.js before this script loaded.
// Dynamically-injected scripts are async, so globals are always ready here.
const widgetId: string = (window as any).__MC_WIDGET_ID__ || "";
const apiUrl: string = (window as any).__MC_API_URL__ || "http://localhost:8000";

if (widgetId) {
  mount(widgetId, apiUrl);
}
