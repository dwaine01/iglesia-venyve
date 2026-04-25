import React, { useState, useEffect, useLayoutEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { SLIDES, RESUMENES_NOTAS } from '../data/presentationData';
import { AlertCircle, Wifi, WifiOff, BookOpen, Zap, FileText, CheckCircle2 } from 'lucide-react';
import { useScreenZoom } from '../hooks/useScreenZoom';
import { ScreenZoomControl } from '../components/ScreenZoomControl';

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * PresentacionNotasPage — "Teleprompter" para el TV detras del escenario.
 *
 * Vista publica (sin login) que se conecta con el codigo de la sesion y
 * muestra UNICAMENTE las notas del slide actual de la pastora en letras
 * GIGANTES, con fondo oscuro y alto contraste para que se lean desde el
 * frente del escenario, mientras la pastora ministra.
 *
 * Se sincroniza por polling (igual que la audiencia): cada vez que la
 * pastora avanza un slide en su tablet/laptop, este TV cambia tambien.
 *
 * URL: /presentacion/notas/:CODIGO
 */
export default function PresentacionNotasPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [currentSlide, setCurrentSlide] = useState(0);
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef(null);
  // 'completo' = notas extendidas (5-7 min) · 'express' = resumen rápido (1-2 min)
  // Se sincroniza con el modo elegido en la laptop pastora vía localStorage.
  const [notesMode, setNotesMode] = useState(() => {
    try {
      return localStorage.getItem('presenter_notes_mode') || 'completo';
    } catch {
      return 'completo';
    }
  });
  const toggleNotesMode = () => {
    setNotesMode((prev) => {
      const next = prev === 'completo' ? 'express' : 'completo';
      try { localStorage.setItem('presenter_notes_mode', next); } catch { /* noop */ }
      return next;
    });
  };

  // Zoom independiente para el TV teleprompter detras del escenario.
  // Default 125% para que la pastora lea desde el escenario sin esfuerzo.
  const { zoom, increment, decrement, containerRef: zoomRef } = useScreenZoom('teleprompter_zoom', 1.25);

  // Polling de la sesion (mismo intervalo que la audiencia: 1.5s)
  useEffect(() => {
    if (!code) {
      navigate('/presentacion/unirse');
      return;
    }

    let mounted = true;
    const poll = async () => {
      try {
        const res = await axios.get(`${API}/api/presentation/session/${code}`);
        if (!mounted) return;
        setCurrentSlide(res.data.current_slide || 0);
        setConnected(true);
        setError(null);
      } catch (err) {
        if (!mounted) return;
        setConnected(false);
        if (err.response?.status === 404) {
          setError('Sesion no encontrada o ya termino');
        }
      }
    };

    poll();
    const interval = setInterval(poll, 1500);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [code, navigate]);

  // Reset scroll al cambiar de slide.
  // useLayoutEffect garantiza que el reset corra ANTES del paint, y los
  // timers adicionales aseguran que sobreviva la animacion de framer-motion
  // (entry de 0.35s) para que la pastora SIEMPRE empiece a leer desde la
  // primera linea sin tener que tocar el cursor.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = 0;
    const timers = [50, 200, 500, 800].map((delay) =>
      setTimeout(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = 0;
      }, delay)
    );
    return () => timers.forEach(clearTimeout);
  }, [currentSlide, notesMode]);

  if (error) {
    return (
      <div
        className="fixed inset-0 bg-[#0A0F1C] flex items-center justify-center z-50"
        data-testid="notas-error-screen"
      >
        <div className="text-center text-white max-w-3xl px-12">
          <AlertCircle className="w-32 h-32 mx-auto text-red-400 mb-8" />
          <h2
            className="text-6xl font-bold mb-6"
            style={{ fontFamily: 'Spectral, serif' }}
          >
            Sesion no disponible
          </h2>
          <p className="text-3xl text-white/60 mb-10">{error}</p>
          <p className="text-xl text-white/40 font-mono">
            Codigo: <span className="text-[#C8A951]">{code}</span>
          </p>
        </div>
      </div>
    );
  }

  const slide = SLIDES[currentSlide] || SLIDES[0];
  const noteEntries = Object.entries(slide.notes || {});

  return (
    <div
      className="fixed inset-0 bg-[#0A0F1C] z-40 overflow-hidden"
      data-testid="notas-view"
    >
      <div ref={zoomRef} className="absolute inset-0 flex flex-col">
      {/* Header sutil con titulo del slide y estado de conexion */}
      <div className="shrink-0 px-10 pt-8 pb-5 border-b border-white/10 bg-gradient-to-b from-[#0F1A33] to-transparent">
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-4 mb-3">
              <BookOpen className="w-8 h-8 text-[#C8A951] shrink-0" />
              <span className="text-xl uppercase tracking-[0.3em] text-[#C8A951] font-bold">
                Notas del Presentador
              </span>
            </div>
            <h1
              className="text-5xl md:text-6xl lg:text-7xl font-bold text-white leading-tight line-clamp-2"
              style={{ fontFamily: 'Spectral, serif' }}
              data-testid="notas-titulo"
            >
              {slide.title}
            </h1>
            {slide.subtitle && (
              <p className="text-2xl md:text-3xl text-white/60 italic mt-2">
                {slide.subtitle}
              </p>
            )}
          </div>

          <div className="shrink-0 flex flex-col items-end gap-2">
            <div className="flex items-center gap-3">
              <button
                onClick={toggleNotesMode}
                data-testid="toggle-notes-mode-tv"
                title={notesMode === 'express' ? 'Cambiar a notas completas' : 'Cambiar a resumen rápido'}
                className={`flex items-center gap-2 text-lg font-bold uppercase tracking-widest px-4 py-2 rounded-lg border-2 transition-colors ${
                  notesMode === 'express'
                    ? 'bg-[#C8A951] text-[#1B2A4A] border-[#C8A951] hover:bg-[#B89841]'
                    : 'bg-transparent text-white border-white/40 hover:border-white hover:bg-white/10'
                }`}
              >
                {notesMode === 'express' ? (
                  <><Zap className="w-5 h-5" /> Express</>
                ) : (
                  <><FileText className="w-5 h-5" /> Completo</>
                )}
              </button>
              <div className="bg-[#C8A951] text-[#1B2A4A] text-2xl font-bold px-5 py-2 rounded-lg font-mono">
                {currentSlide + 1} / {SLIDES.length}
              </div>
            </div>
            <div className="flex items-center gap-2 bg-black/40 backdrop-blur-sm rounded-full px-3 py-1">
              {connected ? (
                <>
                  <Wifi className="w-4 h-4 text-emerald-400" />
                  <span className="text-sm text-white/80 font-mono">{code}</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-4 h-4 text-red-400" />
                  <span className="text-sm text-white/80">Reconectando...</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Contenido principal: notas en letras gigantes */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-10 py-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentSlide}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.35 }}
            className="space-y-10 max-w-[1800px] mx-auto"
          >
            {slide.verse && (
              <div className="bg-[#C8A951]/10 border-l-8 border-[#C8A951] pl-8 py-5 rounded-r-lg">
                <p className="text-2xl uppercase tracking-widest text-[#C8A951] font-bold mb-2">
                  Versiculo
                </p>
                <p
                  className="text-3xl md:text-4xl text-white italic leading-snug"
                  style={{ fontFamily: 'Spectral, serif' }}
                >
                  {slide.verse}
                </p>
              </div>
            )}

            {noteEntries.length === 0 && notesMode !== 'express' && (
              <div className="text-center py-20">
                <p className="text-3xl text-white/40">Sin notas para este slide.</p>
              </div>
            )}

            {/* MODO EXPRESS: resumen rápido para presentar en 1-2 min */}
            {notesMode === 'express' && RESUMENES_NOTAS[slide.id] ? (
              <div className="space-y-10">
                <div className="bg-gradient-to-br from-[#C8A951]/20 to-[#C8A951]/5 border-2 border-[#C8A951] rounded-2xl p-10">
                  <p className="text-2xl uppercase tracking-[0.25em] text-[#C8A951] font-bold mb-5 flex items-center gap-3">
                    <Zap className="w-7 h-7" /> Idea Central
                  </p>
                  <p
                    className="text-4xl md:text-5xl text-white leading-snug font-semibold"
                    style={{ fontFamily: 'Spectral, serif' }}
                  >
                    {RESUMENES_NOTAS[slide.id].idea}
                  </p>
                </div>

                <div className="pb-8 border-b border-white/10">
                  <p className="text-2xl uppercase tracking-[0.25em] text-[#C8A951] font-bold mb-6">
                    Puntos Clave
                  </p>
                  <ul className="space-y-5">
                    {RESUMENES_NOTAS[slide.id].puntos.map((punto, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-5 text-3xl md:text-4xl text-white leading-relaxed"
                      >
                        <CheckCircle2 className="w-10 h-10 text-[#1FA6A0] shrink-0 mt-1" />
                        <span>{punto}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-[#1FA6A0]/10 border-l-8 border-[#1FA6A0] pl-8 py-5 rounded-r-lg">
                  <p className="text-2xl uppercase tracking-[0.25em] text-[#1FA6A0] font-bold mb-3">
                    Transición
                  </p>
                  <p className="text-3xl md:text-4xl text-white italic leading-snug">
                    {RESUMENES_NOTAS[slide.id].transicion}
                  </p>
                </div>
              </div>
            ) : (
              noteEntries.map(([key, value]) => (
                <div key={key} className="pb-8 border-b border-white/10 last:border-0">
                  <p className="text-2xl uppercase tracking-[0.25em] text-[#C8A951] font-bold mb-5">
                    {formatKey(key)}
                  </p>
                  {Array.isArray(value) ? (
                    <ul className="space-y-4">
                      {value.map((item, i) => (
                        <li
                          key={i}
                          className="flex items-start gap-5 text-3xl md:text-4xl text-white leading-relaxed"
                        >
                          <span className="text-[#C8A951] font-bold shrink-0 mt-1">
                            {i + 1}.
                          </span>
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p
                      className="text-3xl md:text-4xl text-white leading-relaxed"
                      style={{ fontFamily: 'Spectral, serif' }}
                    >
                      {value}
                    </p>
                  )}
                </div>
              ))
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Footer minimalista */}
      <div className="shrink-0 px-10 py-3 border-t border-white/10 bg-black/30 flex items-center justify-between">
        <p className="text-sm text-white/30 uppercase tracking-widest">
          Pantalla de Notas · Solo Lectura
        </p>
        <p className="text-sm text-white/30 font-mono">
          Sincronizada en vivo
        </p>
      </div>
      </div>

      {/* Control de zoom flotante (auto-oculta tras 3.5s sin actividad) */}
      <ScreenZoomControl
        zoom={zoom}
        increment={increment}
        decrement={decrement}
        position="bottom-right"
        variant="dark"
        testId="teleprompter-zoom-control"
      />
    </div>
  );
}

function formatKey(key) {
  return key
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}
