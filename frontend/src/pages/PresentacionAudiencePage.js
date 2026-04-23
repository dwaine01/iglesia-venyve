import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { SLIDES } from '../data/presentationData';
import { SlideRenderer } from '../components/slides/SlideComponents';
import { AlertCircle, Wifi, WifiOff } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function PresentacionAudiencePage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const [currentSlide, setCurrentSlide] = useState(0);
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(false);
  const [sessionInfo, setSessionInfo] = useState(null);

  useEffect(() => {
    if (!code) { navigate('/presentacion/unirse'); return; }

    let mounted = true;
    const poll = async () => {
      try {
        const res = await axios.get(`${API}/api/presentation/session/${code}`);
        if (!mounted) return;
        setCurrentSlide(res.data.current_slide || 0);
        setSessionInfo(res.data);
        setConnected(true);
        setError(null);
      } catch (err) {
        if (!mounted) return;
        setConnected(false);
        if (err.response?.status === 404) {
          setError('Sesión no encontrada o ya terminó');
        }
      }
    };

    poll();
    const interval = setInterval(poll, 1500);
    return () => { mounted = false; clearInterval(interval); };
  }, [code, navigate]);

  if (error) {
    return (
      <div className="fixed inset-0 bg-[#0F1A33] flex items-center justify-center z-50">
        <div className="text-center text-white max-w-md px-6">
          <AlertCircle className="w-16 h-16 mx-auto text-red-400 mb-4" />
          <h2 className="text-2xl font-bold mb-2" style={{ fontFamily: 'Spectral, serif' }}>Sesión no disponible</h2>
          <p className="text-white/60 mb-6">{error}</p>
          <button onClick={() => navigate('/presentacion/unirse')}
            className="px-5 py-2.5 bg-[#C8A951] text-[#1B2A4A] rounded-lg font-bold hover:bg-[#E2CF8A] transition-colors">
            Volver a Ingresar Código
          </button>
        </div>
      </div>
    );
  }

  const slide = SLIDES[currentSlide] || SLIDES[0];

  return (
    <div className="fixed inset-0 bg-[#0A0F1C] z-40 overflow-hidden" data-testid="audience-view">
      {/* Indicador de conexión minimalista */}
      <div className="absolute top-3 right-3 z-50 flex items-center gap-1.5 bg-black/40 backdrop-blur-sm rounded-full px-2.5 py-1">
        {connected ? (
          <><Wifi className="w-3 h-3 text-emerald-400" /><span className="text-[10px] text-white/80 font-mono">{code}</span></>
        ) : (
          <><WifiOff className="w-3 h-3 text-red-400" /><span className="text-[10px] text-white/80">Reconectando...</span></>
        )}
      </div>

      <AnimatePresence mode="wait">
        <motion.div key={currentSlide}
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 1.02 }}
          transition={{ duration: 0.4 }}
          className="absolute inset-0 overflow-y-auto">
          <SlideRenderer slide={slide} />
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
