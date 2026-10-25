import React, { useCallback, useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Maximize, Minimize, X } from 'lucide-react';

/* «Presentar» de Estadísticas Globales: misma línea visual del Modo Presentar
 * (fondo claro, banda azul marino, tarjetas blancas, títulos en Spectral),
 * medido en cqw para pantalla gigante; 6 indicadores por diapositiva, cada uno
 * con su explicación completa (nada abreviado ni cortado). */
const SINGULAR = { personas: 'persona', grupos: 'grupo', libros: 'libro', invasiones: 'invasión', viviendas: 'vivienda', mentores: 'mentor', 'líderes': 'líder', actividades: 'actividad', asistencias: 'asistencia', inscripciones: 'inscripción', 'matrículas': 'matrícula', certificados: 'certificado', reuniones: 'reunión', mensajes: 'mensaje', 'niños': 'niño', horas: 'hora' };
export const unitText = (value, unit) => (value === 1 && SINGULAR[unit] ? SINGULAR[unit] : unit);
const fs = (value) => `${value}cqw`;
const usd = (value) => (value == null ? '—' : value.toLocaleString('es-US', { style: 'currency', currency: 'USD' }));

export function StatsPresenter({ title, periodText, cards, onClose }) {
  const pages = [];
  for (let index = 0; index < cards.length; index += 6) pages.push(cards.slice(index, index + 6));  // 6 por diapositiva, con su explicación
  const [page, setPage] = useState(0);
  const [size, setSize] = useState({ width: 1280, height: 720 });
  const [full, setFull] = useState(Boolean(document.fullscreenElement));
  const go = useCallback((delta) => setPage((current) => Math.max(0, Math.min(pages.length - 1, current + delta))), [pages.length]);
  useEffect(() => {
    const fit = () => { const width = Math.min(window.innerWidth, window.innerHeight * 16 / 9); setSize({ width, height: width * 9 / 16 }); };
    fit(); window.addEventListener('resize', fit);
    const key = (event) => { if (['ArrowRight', 'PageDown', ' '].includes(event.key)) { event.preventDefault(); go(1); } else if (['ArrowLeft', 'PageUp'].includes(event.key)) { event.preventDefault(); go(-1); } else if (event.key === 'Escape') onClose(); };
    const sync = () => setFull(Boolean(document.fullscreenElement));
    window.addEventListener('keydown', key); document.addEventListener('fullscreenchange', sync);
    return () => { window.removeEventListener('resize', fit); window.removeEventListener('keydown', key); document.removeEventListener('fullscreenchange', sync); };
  }, [go, onClose]);
  const toggleFull = () => { if (document.fullscreenElement) document.exitFullscreen?.(); else document.documentElement.requestFullscreen?.().catch(() => {}); };
  const items = pages[page] || [];
  const nav = { display: 'inline-flex', alignItems: 'center', gap: 8, minHeight: 56, padding: '0 22px', borderRadius: 14, background: '#14213D', color: '#fff', border: '2px solid #C8A951', fontSize: 19, fontWeight: 700 };
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 70, background: '#E9E4D8', display: 'flex', alignItems: 'center', justifyContent: 'center' }} data-testid="stats-presenter">
      <div style={{ width: size.width, height: size.height, containerType: 'inline-size', background: '#F7F5EF', display: 'flex', flexDirection: 'column', color: '#101D36', fontFamily: 'Inter, system-ui, sans-serif', position: 'relative' }}>
        <div style={{ background: 'linear-gradient(90deg, #14213D 0%, #1B2A4A 60%, #0E5B5A 100%)', padding: '1.6cqw 3cqw 1.4cqw', color: '#fff' }}>
          <p style={{ fontSize: fs(1.5), color: '#E7D28D', fontWeight: 700, margin: 0 }}>Estadísticas Globales · {periodText}</p>
          <h2 style={{ fontSize: fs(3), fontWeight: 700, margin: '0.3cqw 0 0', fontFamily: 'Spectral, Georgia, serif', lineHeight: 1.1 }}>{title}{pages.length > 1 ? ` (${page + 1} de ${pages.length})` : ''}</h2>
        </div>
        <div style={{ flex: 1, padding: '1.6cqw 3cqw', display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gridAutoRows: 'minmax(0, 1fr)', gap: '1.3cqw' }}>
          {items.map((item) => (
            <div key={item.key} style={{ background: '#fff', border: '0.12cqw solid #DDD6C6', borderTop: '0.5cqw solid #C8A951', borderRadius: '1cqw', padding: '1.1cqw 1.4cqw', minWidth: 0, overflow: 'hidden' }} data-testid="stats-presenter-card">
              <p style={{ fontSize: fs(1.6), fontWeight: 700, margin: 0, lineHeight: 1.2 }}>{item.label}</p>
              {item.empty_reason
                ? <p style={{ fontSize: fs(1.55), color: '#3F4A5C', margin: '0.6cqw 0 0', lineHeight: 1.25 }}>{item.empty_reason}</p>
                : <p style={{ fontSize: fs(4.2), fontWeight: 800, color: '#132443', margin: '0.3cqw 0 0', lineHeight: 1 }}>{item.unit === 'USD' ? usd(item.value) : (item.value ?? 0).toLocaleString('es')}{item.unit && item.unit !== 'USD' ? <span style={{ fontSize: fs(1.55), fontWeight: 600, color: '#3F4A5C' }}> {unitText(item.value, item.unit)}</span> : null}</p>}
              {!item.empty_reason && item.change_pct != null && <p style={{ fontSize: fs(1.5), color: '#132443', fontWeight: 700, margin: '0.4cqw 0 0' }}>{item.change_pct > 0 ? '↑ +' : item.change_pct < 0 ? '↓ ' : ''}{item.change_pct} % frente al período anterior</p>}
              <p style={{ fontSize: fs(1.5), color: '#3F4A5C', margin: '0.5cqw 0 0', lineHeight: 1.25 }}>{item.definition}</p>
            </div>
          ))}
        </div>
        <p style={{ fontSize: fs(1.5), color: '#3F4A5C', margin: 0, padding: '0 3cqw 4.8cqw' }}>Cada cifra sale del mismo módulo que la registra. No incluye a la pastora ni las cuentas de prueba en participación.</p>
      </div>
      <div style={{ position: 'fixed', top: 10, right: 10, display: 'flex', gap: 8 }}>
        <button type="button" onClick={toggleFull} style={{ ...nav, minHeight: 48, fontSize: 16 }} data-testid="stats-presenter-full">{full ? <><Minimize size={18} />Salir de pantalla completa</> : <><Maximize size={18} />Pantalla completa</>}</button>
        <button type="button" onClick={() => { if (document.fullscreenElement) document.exitFullscreen?.(); onClose(); }} style={{ ...nav, minHeight: 48, fontSize: 16 }} data-testid="stats-presenter-close"><X size={18} />Salir</button>
      </div>
      <div style={{ position: 'fixed', bottom: 10, left: 0, right: 0, display: 'flex', justifyContent: 'center', gap: 10 }}>
        <button type="button" onClick={() => go(-1)} disabled={page === 0} style={{ ...nav, opacity: page === 0 ? 0.5 : 1 }}><ChevronLeft size={24} />Anterior</button>
        <span style={{ ...nav, background: '#fff', color: '#14213D' }}>Diapositiva {page + 1} de {pages.length || 1}</span>
        <button type="button" onClick={() => go(1)} disabled={page >= pages.length - 1} style={{ ...nav, opacity: page >= pages.length - 1 ? 0.5 : 1 }} data-testid="stats-presenter-next">Siguiente<ChevronRight size={24} /></button>
      </div>
    </div>
  );
}
