import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Users, TrendingUp, Award, AlertTriangle, ArrowLeft, MessageSquare, Send, NotebookPen, Home as HomeIcon, Heart, Sparkles, Plus } from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { StatusBadge, ProgressVsExpected } from '../components/StatusBadge';
import { LOGO_IGLESIA } from '../data/presentationData';

export default function DashboardPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const navigate = useNavigate();
  const { liderId } = useParams();
  const [data, setData] = useState(null);
  const [journalStats, setJournalStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [nota, setNota] = useState('');
  const [sendingNote, setSendingNote] = useState(false);

  const isPastorView = user?.rol === 'pastor' && liderId;
  const isLeader = user?.rol === 'lider';

  useEffect(() => {
    const fetchData = async () => {
      try {
        const url = isPastorView
          ? `${API}/api/dashboard/role-based?leader_id=${liderId}`
          : `${API}/api/dashboard/role-based`;
        const res = await axios.get(url, getAuthHeaders());
        setData(res.data);

        // Stats de bitácora solo para líderes viendo su propio dashboard
        if (!isPastorView && isLeader) {
          try {
            const jstatsRes = await axios.get(`${API}/api/journal/stats`, getAuthHeaders());
            setJournalStats(jstatsRes.data);
          } catch {
            // silencioso: si falla, simplemente no muestra widget
          }
        }
      } catch (err) {
        console.error(err);
        toast.error('Error al cargar dashboard');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [API, getAuthHeaders, isPastorView, isLeader, liderId]);

  const handleSendNote = async () => {
    if (!nota.trim()) return;
    setSendingNote(true);
    try {
      await axios.post(
        `${API}/api/pastor/notes`,
        { leader_id: liderId, texto: nota },
        getAuthHeaders()
      );
      toast.success('Nota enviada al líder');
      setNota('');
      // Reload data to show new note
      const res = await axios.get(
        `${API}/api/dashboard/role-based?leader_id=${liderId}`,
        getAuthHeaders()
      );
      setData(res.data);
    } catch (err) {
      toast.error('Error al enviar nota');
    } finally {
      setSendingNote(false);
    }
  };

  if (loading) return <div className="p-8 text-center">Cargando...</div>;
  if (!data) return <div className="p-8 text-center">Error al cargar datos</div>;

  const { total_personas, por_estado, personas_meta_baja, personas, estado_agregado, pastor_notes, lider } = data;

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 space-y-4 sm:space-y-6">
        {/* Pastor View Banner */}
        {isPastorView && lider && (
          <motion.div initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }}>
            <div className="bg-purple-600 text-white rounded-xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Users className="w-5 h-5" />
                <div>
                  <p className="text-xs opacity-80">Viendo dashboard de:</p>
                  <p className="font-bold">{lider.nombre}</p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-white hover:bg-white/20"
                onClick={() => navigate('/dashboard-general')}
              >
                <ArrowLeft className="w-4 h-4 mr-1" />
                Volver a Dashboard General
              </Button>
            </div>
          </motion.div>
        )}

        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <div className="rounded-2xl bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] p-5 sm:p-8 text-white relative overflow-hidden">
            <div className="absolute inset-0 opacity-10">
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage:
                    'radial-gradient(circle at 2px 2px, rgba(255,255,255,0.15) 1px, transparent 0)',
                  backgroundSize: '32px 32px',
                }}
              ></div>
            </div>
            <div className="relative z-10">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 sm:w-14 sm:h-14 bg-[#0F1A33] rounded-lg p-1 flex items-center justify-center shrink-0 border border-[#C8A951]/30">
                    <img src={LOGO_IGLESIA} alt="Ven y Ve" className="w-full h-full object-contain logo-transparent" />
                  </div>
                  <div>
                    <h1 className="text-xl sm:text-3xl font-bold leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
                      Dashboard del Líder
                    </h1>
                    <p className="text-white/60 mt-0.5 text-xs sm:text-base">Resumen de tus personas en consolidación</p>
                  </div>
                </div>
                {estado_agregado && estado_agregado.key !== 'sin_personas' && (
                  <div className="bg-white/10 backdrop-blur-sm rounded-xl p-3 border border-white/20 w-full sm:w-auto sm:min-w-[220px]">
                    <p className="text-[11px] uppercase tracking-wider text-white/60 mb-1.5">Tu Estado General</p>
                    <StatusBadge status={estado_agregado} size="lg" />
                    <div className="mt-2">
                      <ProgressVsExpected status={estado_agregado} compact={false} inverted={true} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Botón: Manual 7 Semanas */}
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}>
          <button onClick={() => navigate('/presentacion')}
            className="w-full group relative rounded-2xl overflow-hidden shadow-xl border-2 border-[#C8A951]/40 hover:border-[#C8A951] transition-all hover:shadow-2xl"
            data-testid="btn-manual-7-semanas">
            <div className="absolute inset-0 bg-gradient-to-r from-[#1B2A4A] via-[#2A3D63] to-purple-900" />
            <div className="absolute inset-0 opacity-20" style={{
              backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(200,169,81,0.4) 1px, transparent 0)',
              backgroundSize: '24px 24px'
            }} />
            <div className="relative z-10 flex items-center gap-4 p-4 sm:p-5 text-left">
              <div className="w-14 h-14 sm:w-16 sm:h-16 rounded-xl bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] flex items-center justify-center shrink-0 shadow-lg group-hover:scale-105 transition-transform">
                <MessageSquare className="w-7 h-7 sm:w-8 sm:h-8 text-[#1B2A4A]" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] sm:text-xs text-[#C8A951] font-bold uppercase tracking-widest">Manual Interactivo</span>
                </div>
                <h3 className="text-lg sm:text-xl font-bold text-white leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
                  La Ley de las 7 Semanas
                </h3>
                <p className="text-xs sm:text-sm text-white/60 mt-0.5 hidden sm:block">
                  Presentar · Ver · Imprimir el Manual Oficial
                </p>
              </div>
              <ArrowLeft className="w-5 h-5 sm:w-6 sm:h-6 text-[#C8A951] shrink-0 group-hover:-translate-x-1 transition-transform rotate-180" />
            </div>
          </button>
        </motion.div>

        {/* Widget Bitácora Evangelística — solo líderes viendo su propio dashboard */}
        {isLeader && !isPastorView && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="relative overflow-hidden rounded-2xl border border-[#C8A951]/30 bg-gradient-to-br from-[#0F1A33] via-[#1B2A4A] to-[#2A3D63] shadow-xl"
            data-testid="widget-bitacora"
          >
            <div className="absolute inset-0 opacity-[0.08] pointer-events-none" style={{
              backgroundImage: 'radial-gradient(circle at 2px 2px, rgba(200,169,81,0.6) 1px, transparent 0)',
              backgroundSize: '24px 24px'
            }} />
            <div className="absolute -top-20 -right-20 w-64 h-64 bg-[#C8A951]/10 rounded-full blur-3xl pointer-events-none" />

            <div className="relative z-10 p-5 sm:p-6 grid grid-cols-1 lg:grid-cols-3 gap-5 items-center">
              {/* Columna 1: Identidad + CTA */}
              <div className="lg:col-span-1">
                <div className="flex items-center gap-3 mb-3">
                  <div className="p-2.5 rounded-xl bg-[#C8A951]/15 border border-[#C8A951]/40">
                    <NotebookPen className="w-5 h-5 text-[#C8A951]" />
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.25em] text-[#C8A951] font-bold">Bitácora</p>
                    <h3 className="text-lg sm:text-xl font-bold text-white leading-tight" style={{ fontFamily: 'Spectral, serif' }}>
                      Evangelística
                    </h3>
                  </div>
                </div>
                <p className="text-xs text-white/60 leading-relaxed mb-3">
                  Registra tu jornada en el campo: casas visitadas, personas contactadas, decisiones por Cristo y oraciones.
                </p>
                <button
                  onClick={() => navigate('/bitacora')}
                  className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-br from-[#C8A951] to-[#E2CF8A] text-[#0F1A33] font-bold px-4 py-2.5 rounded-lg shadow-md hover:shadow-lg hover:-translate-y-0.5 transition-[transform,box-shadow] duration-150"
                  data-testid="btn-registrar-jornada-hoy"
                >
                  <Plus className="w-4 h-4" />
                  <span className="text-sm">Registrar Jornada de Hoy</span>
                </button>
              </div>

              {/* Columna 2-3: Mini-stats */}
              <div className="lg:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
                {[
                  { label: 'Hoy', value: journalStats?.hoy?.entradas || 0, sub: `${journalStats?.hoy?.casas_visitadas || 0} casas`, icon: HomeIcon, accent: '#1FA6A0' },
                  { label: 'Semana', value: journalStats?.semana?.personas_contactadas || 0, sub: 'contactados', icon: Users, accent: '#5578C2' },
                  { label: 'Mes', value: journalStats?.mes?.personas_ganadas || 0, sub: 'ganadas', icon: Heart, accent: '#C8A951' },
                  { label: 'Total', value: journalStats?.total?.oraciones_realizadas || 0, sub: 'oraciones', icon: Sparkles, accent: '#A688D4' },
                ].map((s) => (
                  <div
                    key={s.label}
                    className="rounded-xl bg-white/5 backdrop-blur-sm border border-white/10 p-3 hover:border-[#C8A951]/40 transition-colors"
                    data-testid={`bitacora-stat-${s.label.toLowerCase()}`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-[9px] uppercase tracking-[0.2em] text-white/50 font-bold">{s.label}</p>
                      <s.icon className="w-3.5 h-3.5" style={{ color: s.accent }} />
                    </div>
                    <p className="text-2xl font-bold text-white leading-none" style={{ fontFamily: 'Spectral, serif' }}>
                      {s.value}
                    </p>
                    <p className="text-[10px] text-white/50 mt-0.5 truncate">{s.sub}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Nota motivacional fija al pie del widget */}
            {(!journalStats || (journalStats.total?.entradas || 0) === 0) && (
              <div className="relative z-10 px-5 sm:px-6 pb-4">
                <p className="text-[11px] italic text-[#C8A951]/80 border-t border-[#C8A951]/20 pt-3">
                  Aún no has registrado ninguna jornada. Empieza hoy: Dios honra el primer paso.
                </p>
              </div>
            )}
          </motion.div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <Card className="shadow-lg hover:shadow-xl transition-shadow">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground">Total Personas</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-bold text-[#1B2A4A]">{total_personas}</p>
              </CardContent>
            </Card>
          </motion.div>
          {['contactado', 'visitado', 'en_proceso', 'graduado'].map((estado, idx) => {
            const colors = {
              contactado: 'text-blue-600',
              visitado: 'text-amber-600',
              en_proceso: 'text-purple-600',
              graduado: 'text-emerald-600',
            };
            const labels = {
              contactado: 'Contactados',
              visitado: 'Visitados',
              en_proceso: 'En Proceso',
              graduado: 'Graduados',
            };
            return (
              <motion.div
                key={estado}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 + idx * 0.05 }}
              >
                <Card className="shadow-lg hover:shadow-xl transition-shadow">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-muted-foreground">
                      {labels[estado]}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className={`text-3xl font-bold ${colors[estado]}`}>{por_estado[estado] || 0}</p>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>

        {/* Lista de Personas con Estado */}
        {personas && personas.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
            <Card className="shadow-xl border border-[#E7E2D6]">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-[#1B2A4A]" />
                  <CardTitle style={{ fontFamily: 'Spectral, serif' }}>Mis Personas y su Estado</CardTitle>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {personas.map((persona, idx) => (
                    <motion.div
                      key={persona._id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.04 }}
                      className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-3 bg-gradient-to-r from-[#F5F0E8]/60 to-[#FAFAF8] rounded-lg border border-[#E7E2D6] hover:border-[#C8A951] hover:shadow-md transition-all cursor-pointer"
                      onClick={() => navigate(`/persona/${persona._id}/semana/${persona.semana_actual}`)}
                      data-testid={`persona-row-${persona._id}`}
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {persona.foto_url ? (
                          <img
                            src={persona.foto_url}
                            alt={persona.nombre}
                            className="w-11 h-11 rounded-full object-cover border-2 border-[#C8A951] flex-shrink-0"
                          />
                        ) : (
                          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-[#1B2A4A] to-[#2A3D63] flex items-center justify-center text-white font-bold flex-shrink-0">
                            {persona.nombre.charAt(0)}
                          </div>
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="font-bold text-sm text-[#1B2A4A] truncate">{persona.nombre}</p>
                          <p className="text-xs text-muted-foreground">Semana {persona.semana_actual} · {persona.estado}</p>
                        </div>
                      </div>
                      <div className="flex flex-col items-stretch sm:items-end gap-1.5 w-full sm:w-auto sm:min-w-[200px]">
                        <div className="flex sm:block">
                          <StatusBadge status={persona.estado_dinamico} />
                        </div>
                        {persona.estado_dinamico && (
                          <div className="w-full">
                            <ProgressVsExpected status={persona.estado_dinamico} compact={true} />
                          </div>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Alerta de Personas con Meta Baja */}
        {personas_meta_baja && personas_meta_baja.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
            <Card className="shadow-xl border-2 border-orange-300 bg-gradient-to-br from-orange-50/80 to-[#FAFAF8]">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-orange-600" />
                  <CardTitle style={{ fontFamily: 'Spectral, serif' }}>Atención: Personas con Meta Baja</CardTitle>
                </div>
                <p className="text-xs text-muted-foreground">
                  Estas personas están significativamente atrasadas respecto al ritmo esperado. Dales seguimiento especial.
                </p>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {personas_meta_baja.slice(0, 5).map((persona) => (
                    <div
                      key={persona._id}
                      className="flex items-center justify-between p-3 bg-white rounded-lg border border-orange-200 hover:bg-orange-50 transition-colors cursor-pointer"
                      onClick={() => navigate(`/persona/${persona._id}/semana/${persona.semana_actual}`)}
                    >
                      <div className="flex items-center gap-3">
                        {persona.foto_url ? (
                          <img
                            src={persona.foto_url}
                            alt={persona.nombre}
                            className="w-10 h-10 rounded-full object-cover border-2 border-orange-300"
                          />
                        ) : (
                          <div className="w-10 h-10 rounded-full bg-orange-400 flex items-center justify-center text-white font-bold">
                            {persona.nombre.charAt(0)}
                          </div>
                        )}
                        <div>
                          <p className="font-bold text-sm">{persona.nombre}</p>
                          <p className="text-xs text-muted-foreground">
                            Día {persona.estado_dinamico?.days_elapsed} · {persona.estado_dinamico?.actual_pct}% (esperado {persona.estado_dinamico?.expected_pct}%)
                          </p>
                        </div>
                      </div>
                      <StatusBadge status={persona.estado_dinamico} />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Pastor Notes Section */}
        {isPastorView && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
            <Card className="shadow-xl border-2 border-purple-200">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-purple-600" />
                  <CardTitle style={{ fontFamily: 'Spectral, serif' }}>Notas del Pastor</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Add Note */}
                <div className="bg-purple-50 rounded-lg p-4 border border-purple-200">
                  <p className="text-sm font-medium text-purple-900 mb-2">Dejar una nota al líder:</p>
                  <div className="flex gap-2">
                    <Textarea
                      value={nota}
                      onChange={(e) => setNota(e.target.value)}
                      placeholder="Escribe tu retroalimentación, consejos o palabras de ánimo..."
                      rows={3}
                      className="flex-1"
                    />
                    <Button
                      onClick={handleSendNote}
                      disabled={sendingNote || !nota.trim()}
                      className="bg-purple-600 hover:bg-purple-700 h-auto"
                    >
                      <Send className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {/* Display Notes */}
                {pastor_notes && pastor_notes.length > 0 && (
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-muted-foreground">Notas Anteriores:</p>
                    {pastor_notes.map((note) => (
                      <div key={note._id} className="bg-white rounded-lg p-3 border border-gray-200">
                        <div className="flex items-center justify-between mb-1">
                          <p className="text-xs font-semibold text-purple-600">{note.pastor_nombre}</p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(note.created_at).toLocaleDateString('es-ES')}
                          </p>
                        </div>
                        <p className="text-sm text-foreground">{note.texto}</p>
                      </div>
                    ))}
                  </div>
                )}
                {(!pastor_notes || pastor_notes.length === 0) && (
                  <p className="text-sm text-muted-foreground italic">No hay notas aún.</p>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Notes for Lider (Read-only) */}
        {!isPastorView && pastor_notes && pastor_notes.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.35 }}>
            <Card className="shadow-xl border-2 border-purple-200">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-purple-600" />
                  <CardTitle style={{ fontFamily: 'Spectral, serif' }}>Mensajes del Pastor</CardTitle>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {pastor_notes.map((note) => (
                  <div key={note._id} className="bg-purple-50 rounded-lg p-4 border-l-4 border-purple-600">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-semibold text-purple-600">{note.pastor_nombre}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(note.created_at).toLocaleDateString('es-ES')}
                      </p>
                    </div>
                    <p className="text-sm text-foreground">{note.texto}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Quick Actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card
            className="shadow-lg hover:shadow-xl transition-all cursor-pointer border-2 border-transparent hover:border-[#1FA6A0]"
            onClick={() => navigate('/registro')}
          >
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-[#1FA6A0]/10 flex items-center justify-center">
                  <Users className="w-6 h-6 text-[#1FA6A0]" />
                </div>
                <div>
                  <p className="font-bold text-lg">Gestionar Personas</p>
                  <p className="text-sm text-muted-foreground">Registrar y dar seguimiento</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card
            className="shadow-lg hover:shadow-xl transition-all cursor-pointer border-2 border-transparent hover:border-[#C8A951]"
            onClick={() => navigate('/estadisticas')}
          >
            <CardContent className="p-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-[#C8A951]/10 flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 text-[#C8A951]" />
                </div>
                <div>
                  <p className="font-bold text-lg">Ver Estadísticas</p>
                  <p className="text-sm text-muted-foreground">Análisis y métricas detalladas</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
