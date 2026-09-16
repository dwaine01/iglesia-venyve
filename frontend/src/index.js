import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

const isResizeObserverNotice = (message) => typeof message === 'string' && message.includes('ResizeObserver loop');

window.addEventListener('error', (event) => {
  if (isResizeObserverNotice(event.message)) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}, true);

if (window.ResizeObserver) {
  const NativeResizeObserver = window.ResizeObserver;
  window.ResizeObserver = class DeferredResizeObserver extends NativeResizeObserver {
    constructor(callback) {
      super((entries, observer) => window.requestAnimationFrame(() => callback(entries, observer)));
    }
  };
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
