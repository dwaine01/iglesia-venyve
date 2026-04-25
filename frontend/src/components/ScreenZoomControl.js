import React, { useState, useEffect } from 'react';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';

/**
 * Control de zoom flotante para vistas de pantalla externa
 * (LED audiencia, TV teleprompter).
 *
 * Diseño: minimalista, semitransparente, en la esquina opuesta al
 * indicador de conexión. Auto-oculta tras 3s de inactividad y
 * reaparece al mover el mouse, para no estorbar durante el servicio.
 */
export const ScreenZoomControl = ({
  zoom,
  increment,
  decrement,
  position = 'bottom-right',
  variant = 'dark',
  testId = 'screen-zoom-control',
}) => {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    let timer;
    const reset = () => {
      setVisible(true);
      clearTimeout(timer);
      timer = setTimeout(() => setVisible(false), 3500);
    };
    reset();
    window.addEventListener('mousemove', reset);
    window.addEventListener('keydown', reset);
    window.addEventListener('touchstart', reset);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('mousemove', reset);
      window.removeEventListener('keydown', reset);
      window.removeEventListener('touchstart', reset);
    };
  }, []);

  const positionClasses = {
    'bottom-right': 'bottom-4 right-4',
    'bottom-left': 'bottom-4 left-4',
    'top-right': 'top-4 right-4',
    'top-left': 'top-4 left-4',
  }[position] || 'bottom-4 right-4';

  const isDark = variant === 'dark';
  const containerClasses = isDark
    ? 'bg-black/70 border-white/20 text-white'
    : 'bg-white/95 border-[#1B2A4A]/20 text-[#1B2A4A]';
  const buttonClasses = isDark
    ? 'hover:bg-white/15 text-white/80 hover:text-white disabled:text-white/30'
    : 'hover:bg-[#1B2A4A]/10 text-[#1B2A4A]/70 hover:text-[#1B2A4A] disabled:text-[#1B2A4A]/30';

  const pct = Math.round(zoom * 100);

  return (
    <div
      data-testid={testId}
      className={`fixed ${positionClasses} z-[60] transition-opacity duration-500 ${
        visible ? 'opacity-100' : 'opacity-0 pointer-events-none'
      }`}
    >
      <div
        className={`flex items-center gap-1 ${containerClasses} backdrop-blur-md border rounded-full shadow-2xl px-2 py-1.5`}
      >
        <button
          onClick={decrement}
          disabled={zoom <= 1.0}
          aria-label="Reducir tamaño"
          data-testid={`${testId}-decrement`}
          className={`${buttonClasses} w-9 h-9 rounded-full flex items-center justify-center transition-colors disabled:cursor-not-allowed`}
        >
          <ZoomOut className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-1.5 px-3">
          <Maximize2 className="w-3.5 h-3.5 text-[#C8A951]" />
          <span
            className="text-sm font-bold font-mono tabular-nums min-w-[3.5ch] text-center"
            data-testid={`${testId}-value`}
          >
            {pct}%
          </span>
        </div>
        <button
          onClick={increment}
          disabled={zoom >= 3.0}
          aria-label="Aumentar tamaño"
          data-testid={`${testId}-increment`}
          className={`${buttonClasses} w-9 h-9 rounded-full flex items-center justify-center transition-colors disabled:cursor-not-allowed`}
        >
          <ZoomIn className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
};

export default ScreenZoomControl;
