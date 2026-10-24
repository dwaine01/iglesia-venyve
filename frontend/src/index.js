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

// Se quitó el "Modo Pantalla Gigante" del panel (tamaño normal fijo). Quien lo
// dejó en 135% o 170% tenía el valor guardado en este dispositivo: se borra y
// se quita el zoom del <html> para que nadie quede atrapado. (El zoom de las
// pantallas de Presentación vive en su propio contenedor y no se toca.)
try { window.localStorage.removeItem('venyve_display_scale'); } catch (storageError) { /* sin almacenamiento */ }
document.documentElement.style.removeProperty('zoom');
delete document.documentElement.dataset.displayScale;

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
