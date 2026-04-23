import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { motion } from 'framer-motion';
import { Presentation, MonitorPlay, Printer, Home, ArrowRight, DoorOpen, BookOpen } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { LOGO_IGLESIA } from '../data/presentationData';

export default function PresentacionHomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const opciones = [
    {
      titulo: 'Presentar',
      subtitulo: 'Modo Presentador',
      desc: 'Controla la presentación desde tu iPad. Ves las notas completas, la audiencia ve solo los visuales.',
      icon: Presentation,
      color: 'from-[#C8A951] to-[#E2CF8A]',
      textColor: 'text-[#1B2A4A]',
      action: () => navigate('/presentacion/presenter'),
      testid: 'btn-modo-presentador',
    },
    {
      titulo: 'Ver Presentación',
      subtitulo: 'Modo Audiencia',
      desc: 'Conecta este dispositivo a una sesión activa con un código para ver solo los visuales en pantalla grande.',
      icon: MonitorPlay,
      color: 'from-purple-600 to-indigo-700',
      textColor: 'text-white',
      action: () => navigate('/presentacion/unirse'),
      testid: 'btn-modo-audiencia',
    },
    {
      titulo: 'Imprimir Manual',
      subtitulo: 'Versión para papel',
      desc: 'Diseño A4 optimizado para imprimir y entregar a cada persona. Gráficos, texto claro y espaciado amplio.',
      icon: Printer,
      color: 'from-[#1FA6A0] to-teal-600',
      textColor: 'text-white',
      action: () => window.open('/presentacion/imprimir', '_blank'),
      testid: 'btn-modo-imprimir',
    },
  ];

  const backRoute = user?.rol === 'pastor' ? '/dashboard-general' : '/dashboard';

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="px-4 sm:px-6 lg:px-8 py-6 sm:py-10 max-w-5xl mx-auto space-y-6">
        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}>
          <div className="rounded-2xl bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] p-5 sm:p-8 text-white relative overflow-hidden">
            <div className="absolute top-0 right-0 w-48 h-48 bg-[#C8A951]/10 rounded-full blur-2xl -translate-y-16 translate-x-16" />
            <div className="relative z-10 flex items-center gap-4">
              <div className="w-16 h-16 sm:w-20 sm:h-20 bg-[#0F1A33] rounded-xl p-1.5 flex items-center justify-center shrink-0 border border-[#C8A951]/30">
                <img src={LOGO_IGLESIA} alt="Ven y Ve" className="w-full h-full object-contain logo-transparent" />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <BookOpen className="w-4 h-4 text-[#C8A951]" />
                  <span className="text-[#C8A951] text-[10px] sm:text-xs font-bold uppercase tracking-widest">Manual Oficial</span>
                </div>
                <h1 className="text-xl sm:text-3xl font-bold leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
                  La Ley de las 7 Semanas
                </h1>
                <p className="text-white/70 mt-0.5 text-xs sm:text-sm">
                  Sistema Celular · 9 Puertas · Modelo CAP · Operación 72
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {opciones.map((op, i) => {
            const Icon = op.icon;
            return (
              <motion.button
                key={op.testid}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 + i * 0.1 }}
                whileHover={{ y: -4 }}
                onClick={op.action}
                className="group relative rounded-2xl overflow-hidden shadow-xl border-2 border-[#E7E2D6] hover:border-[#C8A951] transition-all text-left"
                data-testid={op.testid}
              >
                <div className={`bg-gradient-to-br ${op.color} ${op.textColor} p-5 sm:p-6`}>
                  <div className="w-14 h-14 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center mb-3">
                    <Icon className="w-7 h-7" />
                  </div>
                  <p className="text-[10px] uppercase tracking-widest font-bold opacity-80">{op.subtitulo}</p>
                  <h3 className="text-2xl font-bold mt-0.5" style={{ fontFamily: 'Spectral, serif' }}>{op.titulo}</h3>
                </div>
                <div className="p-4 bg-white">
                  <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">{op.desc}</p>
                  <div className="flex items-center justify-end mt-3 text-[#C8A951] text-sm font-bold">
                    Entrar
                    <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                  </div>
                </div>
              </motion.button>
            );
          })}
        </div>

        <Button variant="outline" onClick={() => navigate(backRoute)} className="gap-2">
          <Home className="w-4 h-4" /> Volver al Dashboard
        </Button>
      </div>
    </div>
  );
}
