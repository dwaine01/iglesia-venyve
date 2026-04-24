import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Separator } from '../components/ui/separator';
import { Star, Trophy, Target, CheckCircle2, Flame, Award } from 'lucide-react';
import { motion } from 'framer-motion';
import { StatusBadge, ProgressVsExpected } from '../components/StatusBadge';

export default function MiProgresoPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      // Plan A: endpoint unificado role-based (rapido, trae todo)
      try {
        const res = await axios.get(`${API}/api/dashboard/role-based`, getAuthHeaders());
        setData(res.data);
        setLoading(false);
        return;
      } catch (errA) {
        // Si devuelve 404 "Perfil no encontrado" significa que la persona no tiene
        // registro en la coleccion `people` (registro directo en `users` sin invite-code).
        // Cubrimos el caso con fallback a endpoints individuales.
        console.warn('[MiProgreso] role-based no disponible, usando fallback:', errA?.response?.status);
      }

      // Plan B: componer datos desde endpoints basicos que siempre responden
      try {
        const [dashRes, checklistsRes] = await Promise.all([
          axios.get(`${API}/api/dashboard`, getAuthHeaders()),
          axios.get(`${API}/api/checklists`, getAuthHeaders()),
        ]);

        const dash = dashRes.data || {};
        const checklists = Array.isArray(checklistsRes.data) ? checklistsRes.data : [];

        // Calcular estrellas = semanas con todas las tareas completadas
        // Semana actual = primera semana incompleta (o 7 si todas completas)
        let estrellas = 0;
        let semanaActual = 1;
        let firstIncompleteFound = false;
        const ordered = [...checklists].sort((a, b) => (a.semana || 0) - (b.semana || 0));
        ordered.forEach((cl) => {
          const tareas = Array.isArray(cl.tareas) ? cl.tareas : [];
          const allDone = tareas.length > 0 && tareas.every((t) => t.completada);
          if (allDone) {
            estrellas += 1;
            if (!firstIncompleteFound) semanaActual = Math.min((cl.semana || 1) + 1, 7);
          } else if (!firstIncompleteFound) {
            semanaActual = cl.semana || 1;
            firstIncompleteFound = true;
          }
        });

        setData({
          person: {
            nombre: user?.nombre || 'Discipulo',
            foto_url: null,
          },
          semana_actual: semanaActual,
          estrellas,
          progreso_general: Math.round(dash.overall_progress || 0),
          total_tasks: dash.total_tasks || 0,
          completed_tasks: dash.completed_tasks || 0,
          checklists: ordered,
          estado_dinamico: null,
        });
      } catch (errB) {
        console.error('[MiProgreso] fallback tambien fallo:', errB);
        setData(null);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [API, getAuthHeaders, user]);

  if (loading) return <div className="p-8 text-center">Cargando tu progreso...</div>;
  if (!data) return <div className="p-8 text-center">Error al cargar datos</div>;

  const { person = {}, semana_actual = 1, estrellas = 0, progreso_general = 0, total_tasks = 0, completed_tasks = 0, checklists = [], estado_dinamico } = data;
  const personNombre = person?.nombre || 'Discipulo';

  const getMensajeMotivacional = () => {
    if (estado_dinamico?.key === 'excelente') return '¡Eres un campeón! Vas por encima del ritmo. ¡Sigue brillando!';
    if (estado_dinamico?.key === 'recien_iniciado') return '¡Bienvenido! Este es el comienzo de una gran transformación. ¡Adelante!';
    if (estado_dinamico?.key === 'meta_baja') return '¡No te desanimes! Retoma con fuerza, cada día cuenta. Estamos contigo.';
    if (progreso_general === 100) return '¡FELICIDADES! Has completado todo el proceso. ¡Eres un campeón!';
    if (progreso_general >= 75) return '¡Increíble! Estás muy cerca de terminar. ¡No te detengas!';
    if (progreso_general >= 50) return '¡Vas por buen camino! Sigue así, cada paso cuenta.';
    if (progreso_general >= 25) return 'Buen inicio. Continúa firme, lo estás haciendo bien.';
    return '¡Bienvenido! Este es el comienzo de una gran transformación.';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-10 space-y-4 sm:space-y-6 max-w-5xl mx-auto">
        {/* Header con foto y nombre */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <div className="rounded-2xl bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] p-5 sm:p-8 text-white relative overflow-hidden">
            <div className="absolute inset-0 opacity-10">
              <div className="absolute inset-0" style={{
                backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)',
                backgroundSize: '32px 32px'
              }}></div>
            </div>
            <div className="relative z-10 flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6">
              {person?.foto_url ? (
                <img src={person.foto_url} alt={personNombre}
                     className="w-16 h-16 sm:w-20 sm:h-20 rounded-full border-4 border-[#C8A951] object-cover shrink-0" />
              ) : (
                <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full border-4 border-[#C8A951] bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] flex items-center justify-center text-xl sm:text-2xl font-bold text-[#1B2A4A] shrink-0">
                  {personNombre.charAt(0).toUpperCase()}
                </div>
              )}
              <div className="flex-1 min-w-0">
                <h1 className="text-xl sm:text-3xl font-bold truncate" style={{ fontFamily: 'Spectral, serif' }}>
                  {personNombre}
                </h1>
                <p className="text-white/60 mt-1 text-sm sm:text-base">Tu Proceso de Consolidación</p>
                <div className="flex flex-wrap items-center gap-2 mt-3">
                  <Badge className="bg-[#C8A951] text-[#1B2A4A] font-bold">Semana {semana_actual}</Badge>
                  {estado_dinamico && <StatusBadge status={estado_dinamico} size="lg" />}
                </div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Tarjeta de Estado Dinámico y Motivación */}
        {estado_dinamico && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
            <Card className={`shadow-xl border-2 ${
              estado_dinamico.key === 'excelente' ? 'border-[#C8A951] bg-gradient-to-br from-[#C8A951]/10 via-[#FAFAF8] to-[#E2CF8A]/10'
              : estado_dinamico.key === 'meta_baja' ? 'border-orange-300 bg-gradient-to-br from-orange-50/80 to-[#FAFAF8]'
              : estado_dinamico.key === 'recien_iniciado' ? 'border-blue-300 bg-gradient-to-br from-blue-50/80 to-[#FAFAF8]'
              : 'border-[#1FA6A0] bg-gradient-to-br from-[#1FA6A0]/10 to-[#FAFAF8]'
            }`}>
              <CardContent className="p-5 space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Mi Estado Actual</p>
                    <div className="mt-1.5">
                      <StatusBadge status={estado_dinamico} size="lg" showPct={true} />
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-[11px] text-muted-foreground">Día</p>
                    <p className="text-2xl font-bold text-[#1B2A4A]">{estado_dinamico.days_elapsed}<span className="text-sm text-muted-foreground">/49</span></p>
                  </div>
                </div>
                <ProgressVsExpected status={estado_dinamico} compact={false} />
                <p className="text-sm font-medium text-[#1B2A4A] italic" data-testid="mensaje-motivacional">
                  💬 {getMensajeMotivacional()}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        )}


        {/* Estrellas Ganadas */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card className="border-2 border-[#C8A951] shadow-xl">
            <CardHeader className="bg-gradient-to-r from-[#C8A951]/10 to-[#E2CF8A]/10">
              <CardTitle className="flex items-center gap-2" style={{ fontFamily: 'Spectral, serif' }}>
                <Trophy className="w-6 h-6 text-[#C8A951]" />
                Tus Estrellas Ganadas
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="flex items-center justify-center gap-1.5 sm:gap-3 mb-6 flex-wrap">
                {[1, 2, 3, 4, 5, 6, 7].map((num) => (
                  <motion.div
                    key={num}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: 0.1 * num, type: 'spring' }}
                  >
                    <Star
                      className={`w-8 h-8 sm:w-12 sm:h-12 ${
                        num <= estrellas
                          ? 'fill-[#C8A951] text-[#C8A951] drop-shadow-lg'
                          : 'text-gray-300'
                      }`}
                    />
                  </motion.div>
                ))}
              </div>
              <div className="text-center">
                <p className="text-2xl sm:text-3xl font-bold text-[#1B2A4A] mb-2">
                  {estrellas} de 7 Estrellas
                </p>
                <p className="text-xs sm:text-sm text-muted-foreground px-2">
                  {estrellas === 7
                    ? '¡Has ganado todas las estrellas! 🎉'
                    : `¡Completa la semana ${estrellas + 1} para ganar tu próxima estrella!`}
                </p>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Progreso General */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <Card className="shadow-lg">
            <CardHeader>
              <CardTitle style={{ fontFamily: 'Spectral, serif' }}>Progreso General</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-muted-foreground">
                    {completed_tasks} de {total_tasks} tareas completadas
                  </span>
                  <span className="text-2xl font-bold text-[#1B2A4A]">{progreso_general}%</span>
                </div>
                <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-[#1FA6A0] via-[#C8A951] to-[#1B2A4A]"
                    initial={{ width: 0 }}
                    animate={{ width: `${progreso_general}%` }}
                    transition={{ duration: 1, delay: 0.3 }}
                  />
                </div>
              </div>
              <div className="bg-gradient-to-r from-[#1B2A4A]/5 to-[#C8A951]/5 rounded-lg p-4 border-l-4 border-[#C8A951]">
                <div className="flex items-start gap-3">
                  <Flame className="w-5 h-5 text-[#C8A951] mt-0.5" />
                  <p className="text-sm italic text-[#1B2A4A] font-medium">
                    {getMensajeMotivacional()}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Semanas */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <h2 className="text-xl font-bold mb-4" style={{ fontFamily: 'Spectral, serif' }}>Mis Semanas</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {checklists.map((cl, idx) => {
              const tareas = cl.tareas || [];
              const completadas = tareas.filter(t => t.completada).length;
              const total = tareas.length;
              const pct = total > 0 ? Math.round((completadas / total) * 100) : 0;
              const isCompleted = pct === 100;

              return (
                <motion.div
                  key={cl._id}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.25 + idx * 0.05 }}
                >
                  <Card
                    className={`cursor-pointer transition-all hover:shadow-lg ${
                      isCompleted ? 'border-2 border-[#C8A951] bg-[#C8A951]/5' : 'border border-[#E7E2D6]'
                    }`}
                    onClick={() => navigate(`/mi-semana/${cl.semana}`)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                            isCompleted ? 'bg-[#C8A951] text-white' : 'bg-gray-200 text-gray-600'
                          }`}>
                            {cl.semana}
                          </div>
                          <div>
                            <p className="font-bold text-sm">Semana {cl.semana}</p>
                            <p className="text-xs text-muted-foreground">{completadas}/{total} tareas</p>
                          </div>
                        </div>
                        {isCompleted && (
                          <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring' }}>
                            <Star className="w-6 h-6 fill-[#C8A951] text-[#C8A951]" />
                          </motion.div>
                        )}
                      </div>
                      <Progress value={pct} className="h-2" />
                    </CardContent>
                  </Card>
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
