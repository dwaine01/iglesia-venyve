// Teclado en pantalla (iPhone y Android): el teclado NO achica la página,
// solo el área visible (visualViewport). Publicamos esa área como variables
// CSS para que diálogos y hojas se ajusten a lo que realmente se ve:
//   --vvh    alto visible (px)
//   --vv-top desplazamiento del área visible (px)
//   --kb     alto que tapa el teclado por abajo (px)
// y html[data-keyboard="open"] mientras el teclado está abierto.
const TYPING = 'input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=range]):not([type=file]):not([type=color]), textarea, select, [contenteditable="true"]';

export function installViewportVars() {
  if (typeof window === 'undefined' || window.__venyveViewport) return;
  window.__venyveViewport = true;
  const root = document.documentElement;
  const viewport = window.visualViewport;
  const update = () => {
    const height = viewport ? viewport.height : window.innerHeight;
    const top = viewport ? viewport.offsetTop : 0;
    const keyboard = Math.max(0, Math.round(window.innerHeight - height - top));
    root.style.setProperty('--vvh', `${Math.round(height)}px`);
    root.style.setProperty('--vv-top', `${Math.round(top)}px`);
    root.style.setProperty('--kb', `${keyboard}px`);
    if (keyboard > 120) root.dataset.keyboard = 'open'; else delete root.dataset.keyboard;
  };
  update();
  viewport?.addEventListener('resize', update);
  viewport?.addEventListener('scroll', update);
  window.addEventListener('resize', update);

  // Al enfocar un campo en un celular, esperar a que suba el teclado y
  // centrar el campo en lo que se ve (no queda tapado).
  const touch = window.matchMedia?.('(pointer: coarse)').matches;
  document.addEventListener('focusin', (event) => {
    const target = event.target;
    if (!touch || !(target instanceof Element) || !target.matches(TYPING)) return;
    setTimeout(() => {
      update();
      if (document.activeElement !== target) return;
      // Solo si quedó tapado (teclado arriba o botón fijo abajo); así no se mueve
      // la pantalla bajo el dedo cuando el campo ya se ve.
      const rect = target.getBoundingClientRect();
      const visibleTop = viewport ? viewport.offsetTop : 0;
      const visibleBottom = visibleTop + (viewport ? viewport.height : window.innerHeight);
      if (rect.top < visibleTop + 56 || rect.bottom > visibleBottom - 80) target.scrollIntoView({ block: 'center', inline: 'nearest' });
    }, 250);
  });
}
