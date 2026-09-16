import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

window.addEventListener('error', (event) => {
  if (event.message?.includes('ResizeObserver loop')) event.stopImmediatePropagation();
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
