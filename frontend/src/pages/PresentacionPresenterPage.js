import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  ChevronLeft, ChevronRight, Home, Eye, EyeOff, Presentation,
  Copy, Monitor, Users, Clock, ListOrdered, CheckCircle2, Save, Edit3
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import { SLIDES } from '../data/presentationData';
import { SlideRenderer } from '../components/slides/SlideComponents';

export default function PresentacionPresenterPage() {
  const navigate = useNavigate();
  const { API, getAuthHeaders } = useAuth();
  const [current, setCurrent] = useState(0);
  const [session, setSession] = useState(null);
  const [showPreview, setShowPreview] = useState(true);
  const [startTime] = useState(Date.now());
  const [elapsed, setElapsed] = useState('00:00');
  const creatingRef = useRef(false);
  const [customNotes, setCustomNotes] = useState({});
  const [editingNote, setEditingNote] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  // Load custom notes
  useEffect(() => {
    const loadNotes = async () => {
      try {
        const res = await axios.get(`${API}/api/presentation/notes`, getAuthHeaders());
        setCustomNotes(res.data);
      } catch (e) {}
    };
    loadNotes();
  }, [API, getAuthHeaders]);

  // Cronómetro
  useEffect(() => {
    const id = setInterval(() => {
      const secs = Math.floor((Date.now() - startTime) / 1000);
      const m = String(Math.floor(secs / 60)).padStart(2, '0');
      const s = String(secs % 60).padStart(2, '0');
      setElapsed(`${m}:${s}`);
    }, 1000);
    return () => clearInterval(id);
  }, [startTime]);

  // Crear sesión al montar
  useEffect(() => {
    if (creatingRef.current) return;
    creatingRef.current = true;
    const create = async () => {
      try {
        const res = await axios.post(`${API}/api/presentation/session`, {}, getAuthHeaders());
        setSession(res.data);
        toast.success(`Sesión creada: ${res.data.code}`);
      } catch (err) {
        toast.error('No se pudo crear la sesión');
      }
    };
    create();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sincronizar slide con backend
  const syncSlide = useCallback(async (slideIdx) => {
    if (!session) return;
    try {
      await axios.put(
        `${API}/api/presentation/session/${session.code}`,
        { current_slide: slideIdx },
        getAuthHeaders()
      );
    } catch (e) { /* silencioso */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, API]);

  const goTo = useCallback((idx) => {
    if (idx < 0 || idx >= SLIDES.length) return;
    setCurrent(idx);
    syncSlide(idx);
  }, [syncSlide]);

  const next = useCallback(() => goTo(current + 1), [current, goTo]);
  const prev = useCallback(() => goTo(current - 1), [current, goTo]);

  // Teclado
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); next(); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); prev(); }
      else if (e.key === 'Escape') { handleExit(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [next, prev]);

  const handleExit = async () => {
    if (session) {
      try { await axios.delete(`${API}/api/presentation/session/${session.code}`, getAuthHeaders()); } catch (e) {}
    }
    navigate('/presentacion');
  };

  const copyCode = () => {
    if (!session) return;
    navigator.clipboard.writeText(session.code);
    toast.success(`Código copiado: ${session.code}`);
  };

  // Update note text when slide changes
  useEffect(() => {
    const slideId = SLIDES[current]?.id;
    setNoteText(customNotes[slideId] || '');
    setEditingNote(false);
  }, [current, customNotes]);

  const saveNote = async () => {
    setSavingNote(true);
    try {
      const slideId = SLIDES[current]?.id;
      await axios.post(`${API}/api/presentation/notes`, { slide_id: slideId, note_text: noteText }, getAuthHeaders());
      setCustomNotes(prev => ({ ...prev, [slideId]: noteText }));
      setEditingNote(false);
      toast.success('Nota guardada');
    } catch (e) {
      toast.error('Error al guardar nota');
    } finally {
      setSavingNote(false);
    }
  };

  const copyLink = () => {
    if (!session) return;
    const link = `${window.location.origin}/presentacion/audiencia/${session.code}`;
    navigator.clipboard.writeText(link);
    toast.success('Enlace copiado');
  };

  const slide = SLIDES[current];
  const nextSlide = SLIDES[current + 1];
  const progressPct = ((current + 1) / SLIDES.length) * 100;

  return (
    <div className="fixed inset-0 bg-[#0A0F1C] z-40 flex flex-col overflow-hidden" data-testid="presenter-view">
      {/* Top bar */}
      <div className="bg-[#1B2A4A] border-b border-white/10 px-3 sm:px-6 py-2.5 flex items-center gap-2 sm:gap-4 shrink-0">
        <Button variant="ghost" size="sm" onClick={handleExit} className="text-white/80 hover:text-white hover:bg-white/10 gap-1.5" data-testid="btn-salir-presentador">
          <Home className="w-4 h-4" />
          <span className="hidden sm:inline">Salir</span>
        </Button>

        <div className="flex-1 flex items-center justify-center gap-3 min-w-0">
          <Badge className="bg-[#C8A951] text-[#1B2A4A] font-bold">
            <Presentation className="w-3 h-3 mr-1" /> Modo Presentador
          </Badge>
          {session && (
            <div className="flex items-center gap-1.5 bg-white/5 rounded-lg px-2.5 py-1 border border-[#C8A951]/30">
              <span className="text-[10px] text-white/60 uppercase tracking-wider">Código</span>
              <span className="text-xl font-bold text-[#C8A951] font-mono tracking-widest" data-testid="codigo-sesion">{session.code}</span>
              <button onClick={copyCode} className="text-white/60 hover:text-[#C8A951] ml-1" title="Copiar código">
                <Copy className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 text-white/70 text-xs shrink-0">
          <Clock className="w-3.5 h-3.5" />
          <span className="font-mono">{elapsed}</span>
          <span className="hidden sm:inline">· {current + 1}/{SLIDES.length}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-white/10 shrink-0">
        <motion.div className="h-full bg-gradient-to-r from-[#C8A951] to-[#E2CF8A]"
          initial={{ width: 0 }} animate={{ width: `${progressPct}%` }} transition={{ duration: 0.3 }} />
      </div>

      {/* Main content: Slide preview + Notes */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-5 gap-0 overflow-hidden">
        {/* LEFT: Preview actual + siguiente */}
        <div className="lg:col-span-3 flex flex-col bg-[#0A0F1C] overflow-hidden border-r border-white/10">
          {showPreview ? (
            <>
              <div className="flex-1 relative overflow-hidden">
                <div className="absolute inset-2 rounded-xl overflow-hidden border-2 border-[#C8A951]/40 shadow-2xl">
                  <div className="absolute top-2 left-2 z-20 bg-[#C8A951] text-[#1B2A4A] text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest">
                    🔴 En Vivo (Audiencia)
                  </div>
                  <AnimatePresence mode="wait">
                    <motion.div key={current} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                      className="absolute inset-0 overflow-y-auto">
                      <SlideRenderer slide={slide} />
                    </motion.div>
                  </AnimatePresence>
                </div>
              </div>
              {/* Next preview */}
              {nextSlide && (
                <div className="h-32 sm:h-36 border-t border-white/10 px-3 py-2 flex items-center gap-3 bg-[#1B2A4A]/50">
                  <p className="text-[10px] uppercase tracking-widest text-white/50 font-bold">Siguiente</p>
                  <div className="flex-1 rounded-lg overflow-hidden border border-white/10 h-full relative">
                    <div className="absolute inset-0 transform origin-top-left overflow-hidden pointer-events-none" style={{ transform: 'scale(0.25)', width: '400%', height: '400%' }}>
                      <SlideRenderer slide={nextSlide} />
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-[10px] text-white/50">#{current + 2}</p>
                    <p className="text-sm font-bold text-white leading-tight max-w-[120px] truncate">{nextSlide.title}</p>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-white/40">
              <div className="text-center">
                <EyeOff className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p>Vista previa oculta</p>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT: Notas del presentador - GRANDE Y EDITABLE */}
        <div className="lg:col-span-2 bg-white flex flex-col overflow-hidden">
          <div className="p-4 sm:p-6 border-b border-[#E7E2D6] bg-gradient-to-r from-[#F5F0E8] to-[#FAFAF8]">
            <div className="flex items-center justify-between mb-2">
              <Badge className="bg-[#1B2A4A] text-white text-sm px-3 py-1">
                <ListOrdered className="w-4 h-4 mr-2" /> Slide {current + 1} de {SLIDES.length}
              </Badge>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase tracking-widest text-[#C8A951] font-bold">Notas del Presentador</span>
                {!editingNote ? (
                  <Button size="sm" variant="outline" onClick={() => setEditingNote(true)} className="h-8 gap-1 text-xs">
                    <Edit3 className="w-3.5 h-3.5" /> Editar
                  </Button>
                ) : (
                  <Button size="sm" onClick={saveNote} disabled={savingNote} className="h-8 gap-1 text-xs bg-[#1FA6A0] hover:bg-[#178F89] text-white">
                    <Save className="w-3.5 h-3.5" /> {savingNote ? 'Guardando...' : 'Guardar'}
                  </Button>
                )}
              </div>
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold text-[#1B2A4A] leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
              {slide.title}
            </h2>
            {slide.subtitle && <p className="text-lg text-muted-foreground italic mt-1">{slide.subtitle}</p>}
            {slide.verse && (
              <p className="text-base text-[#C8A951] font-bold mt-2">📖 {slide.verse}</p>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-5 sm:p-8 space-y-4">
            {/* Custom editable note */}
            {editingNote ? (
              <div className="mb-4">
                <textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  className="w-full h-48 p-4 text-2xl leading-relaxed text-[#1B2A4A] border-2 border-[#C8A951] rounded-lg resize-y focus:outline-none focus:ring-2 focus:ring-[#C8A951]"
                  placeholder="Escribe tus notas aquí..."
                  autoFocus
                  style={{ fontFamily: 'Spectral, serif' }}
                />
              </div>
            ) : noteText ? (
              <div className="mb-4 p-4 bg-[#FBF9F3] border-l-4 border-[#C8A951] rounded-r-lg">
                <p className="text-2xl sm:text-3xl text-[#1B2A4A] leading-relaxed whitespace-pre-wrap" style={{ fontFamily: 'Spectral, serif' }}>
                  {noteText}
                </p>
              </div>
            ) : null}

            {/* Slide built-in notes */}
            {Object.entries(slide.notes || {}).map(([key, value]) => (
              <div key={key} className="pb-4 border-b border-[#E7E2D6] last:border-0">
                <p className="text-sm font-bold uppercase tracking-widest text-[#C8A951] mb-2">
                  {formatKey(key)}
                </p>
                {Array.isArray(value) ? (
                  <ul className="space-y-3">
                    {value.map((item, i) => (
                      <li key={i} className="flex items-start gap-3 text-xl sm:text-2xl text-[#1B2A4A] leading-relaxed">
                        <CheckCircle2 className="w-6 h-6 text-[#1FA6A0] shrink-0 mt-1" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xl sm:text-2xl text-[#1B2A4A] leading-relaxed">{value}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom bar: controls */}
      <div className="bg-[#1B2A4A] border-t border-white/10 px-3 sm:px-6 py-3 flex items-center justify-between gap-2 shrink-0">
        <Button onClick={prev} disabled={current === 0}
          className="bg-white/10 hover:bg-white/20 text-white disabled:opacity-30 gap-1.5" data-testid="btn-prev">
          <ChevronLeft className="w-4 h-4" />
          <span className="hidden sm:inline">Anterior</span>
        </Button>

        <div className="flex items-center gap-1 flex-wrap justify-center px-2 max-w-2xl overflow-x-auto">
          {SLIDES.map((s, i) => (
            <button key={s.id} onClick={() => goTo(i)}
              className={`transition-all rounded-full shrink-0 ${i === current ? 'w-6 h-2 bg-[#C8A951]' : 'w-2 h-2 bg-white/30 hover:bg-white/50'}`}
              title={s.title} aria-label={`Ir a slide ${i + 1}`} />
          ))}
        </div>

        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={() => setShowPreview(!showPreview)} className="text-white/70 hover:text-white hover:bg-white/10">
            {showPreview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </Button>
          <Button size="sm" variant="ghost" onClick={copyLink} className="text-white/70 hover:text-white hover:bg-white/10 hidden sm:flex" title="Copiar enlace para audiencia">
            <Monitor className="w-4 h-4" />
          </Button>
          <Button onClick={next} disabled={current === SLIDES.length - 1}
            className="bg-[#C8A951] hover:bg-[#E2CF8A] text-[#1B2A4A] disabled:opacity-30 gap-1.5 font-bold" data-testid="btn-next">
            <span className="hidden sm:inline">Siguiente</span>
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function formatKey(key) {
  // Convierte "tiempoSugerido" → "Tiempo Sugerido"
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase()).trim();
}
