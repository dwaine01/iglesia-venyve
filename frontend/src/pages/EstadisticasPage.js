import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line, Area, AreaChart } from 'recharts';
import { Home, Users, Heart, Award, TrendingUp, Flame, BarChart3, Target } from 'lucide-react';
import { motion } from 'framer-motion';

const COLORS = ['#1B2A4A', '#C8A951', '#1FA6A0', '#7C3AED', '#F59E0B', '#EF4444', '#667085'];
const weekNames = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7'];
const weekFullNames = ['Preparacion', 'Invasion', 'MCD', 'Liberacion', 'Bendicion', 'Sanidad', 'Retiro'];

export default function EstadisticasPage() {
  const { API, getAuthHeaders } = useAuth();
  const [dashboard, setDashboard] = useState(null);
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const [dashRes, contactsRes] = await Promise.all([
        axios.get(`${API}/api/dashboard`, getAuthHeaders()),
        axios.get(`${API}/api/contacts`, getAuthHeaders()),
      ]);
      setDashboard(dashRes.data); setContacts(contactsRes.data);
    } catch (err) { console.error(err); } finally { setLoading(false); }
  }, [API, getAuthHeaders]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <div className="flex items-center justify-center min-h-[60vh]"><motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}><Flame className="w-8 h-8 text-[#C8A951]" /></motion.div></div>;

  const data = dashboard || { totals: {}, checklist_by_week: {}, contacts_by_status: {}, progress_by_week: [] };

  const progressChartData = data.progress_by_week?.map((p, idx) => ({
    name: weekNames[idx], fullName: weekFullNames[idx],
    casas: p.casas_visitadas || 0, contactados: p.personas_contactadas || 0, ganados: p.personas_ganadas || 0,
  })) || [];

  const checklistChartData = Object.entries(data.checklist_by_week || {}).map(([week, d]) => ({
    name: weekNames[parseInt(week) - 1], completado: d.completed, pendiente: d.total - d.completed, porcentaje: d.percentage,
  }));

  const statusPieData = Object.entries(data.contacts_by_status || {}).map(([status, count]) => ({ name: status.replace('_', ' '), value: count }));
  const relationData = contacts.reduce((acc, c) => { const rel = c.relacion || 'otro'; acc[rel] = (acc[rel] || 0) + 1; return acc; }, {});
  const relationPieData = Object.entries(relationData).map(([name, value]) => ({ name, value }));

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#F5F0E8] via-[#FAFAF8] to-[#EDE8DD]">
      <div className="px-3 sm:px-6 lg:px-8 py-4 sm:py-6 lg:py-8 space-y-4 sm:space-y-6">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div className="relative rounded-2xl bg-gradient-to-r from-[#C8A951] to-[#A8893E] p-6 sm:p-8 overflow-hidden shadow-lg">
            <div className="absolute inset-0 animated-dots opacity-10"></div>
            <div className="absolute top-0 right-0 w-40 h-40 bg-white/5 rounded-full -translate-y-16 translate-x-16"></div>
            <div className="relative z-10">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-5 h-5 text-white" />
                <span className="text-white/80 text-xs font-semibold uppercase tracking-widest">Metricas</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Spectral, serif' }}>Estadisticas del Proceso</h1>
              <p className="text-white/60 mt-1 text-sm">Resumen general de progreso, impacto y resultados</p>
            </div>
          </div>
        </motion.div>

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Casas Visitadas', value: data.totals.casas_visitadas || 0, icon: Home, bg: 'bg-gradient-to-br from-[#1FA6A0] to-[#178A85]' },
            { label: 'Personas Contactadas', value: data.totals.personas_contactadas || 0, icon: Users, bg: 'bg-gradient-to-br from-[#1B2A4A] to-[#2A3D63]' },
            { label: 'Personas Ganadas', value: data.totals.personas_ganadas || 0, icon: Heart, bg: 'bg-gradient-to-br from-[#C8A951] to-[#A8893E]' },
            { label: 'Oraciones Realizadas', value: data.totals.oraciones_realizadas || 0, icon: Award, bg: 'bg-gradient-to-br from-purple-500 to-purple-700' },
          ].map((kpi, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 16, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.35, delay: 0.1 + i * 0.08 }} whileHover={{ y: -4 }}>
              <div className={`${kpi.bg} rounded-xl p-5 text-white shadow-lg relative overflow-hidden`}>
                <div className="absolute top-0 right-0 w-20 h-20 bg-white/5 rounded-full -translate-y-8 translate-x-8"></div>
                <div className="flex items-center justify-between mb-2 relative z-10">
                  <span className="text-sm text-white/80">{kpi.label}</span>
                  <div className="w-8 h-8 bg-white/15 rounded-lg flex items-center justify-center"><kpi.icon className="w-4 h-4" /></div>
                </div>
                <p className="text-3xl font-bold relative z-10">{kpi.value}</p>
              </div>
            </motion.div>
          ))}
        </div>

        {/* Charts Row 1 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }}>
            <div className="bg-white rounded-xl shadow-sm border border-[#E7E2D6] overflow-hidden">
              <div className="bg-gradient-to-r from-[#1B2A4A] to-[#2A3D63] px-5 py-3 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-[#C8A951]" />
                <h2 className="text-white font-semibold text-sm" style={{ fontFamily: 'Spectral, serif' }}>Actividad por Semana</h2>
              </div>
              <div className="p-4">
                {progressChartData.some(d => d.casas > 0 || d.contactados > 0 || d.ganados > 0) ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={progressChartData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E7E2D6" />
                      <XAxis dataKey="name" fontSize={12} />
                      <YAxis fontSize={12} />
                      <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid #E7E2D6' }} />
                      <Bar dataKey="casas" name="Casas" fill="#1B2A4A" radius={[6, 6, 0, 0]} />
                      <Bar dataKey="contactados" name="Contactados" fill="#C8A951" radius={[6, 6, 0, 0]} />
                      <Bar dataKey="ganados" name="Ganados" fill="#1FA6A0" radius={[6, 6, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[280px] flex flex-col items-center justify-center">
                    <div className="w-14 h-14 rounded-full bg-[#F5F0E8] flex items-center justify-center mb-3"><TrendingUp className="w-6 h-6 text-[#C8A951]" /></div>
                    <p className="text-muted-foreground text-sm">Registra tu progreso para ver estadisticas</p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.35 }}>
            <div className="bg-white rounded-xl shadow-sm border border-[#E7E2D6] overflow-hidden">
              <div className="bg-gradient-to-r from-[#C8A951] to-[#A8893E] px-5 py-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-white" />
                <h2 className="text-white font-semibold text-sm" style={{ fontFamily: 'Spectral, serif' }}>Progreso de Tareas (%)</h2>
              </div>
              <div className="p-4">
                {checklistChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={checklistChartData}>
                      <defs>
                        <linearGradient id="colorProgress" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#C8A951" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#C8A951" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E7E2D6" />
                      <XAxis dataKey="name" fontSize={12} />
                      <YAxis domain={[0, 100]} fontSize={12} />
                      <Tooltip formatter={(value) => `${value}%`} contentStyle={{ borderRadius: '8px', border: '1px solid #E7E2D6' }} />
                      <Area type="monotone" dataKey="porcentaje" name="Progreso" stroke="#C8A951" strokeWidth={3} fillOpacity={1} fill="url(#colorProgress)" dot={{ fill: '#C8A951', r: 5, strokeWidth: 2, stroke: '#fff' }} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[280px] flex flex-col items-center justify-center">
                    <div className="w-14 h-14 rounded-full bg-[#F5F0E8] flex items-center justify-center mb-3"><Target className="w-6 h-6 text-[#C8A951]" /></div>
                    <p className="text-muted-foreground text-sm">Completa tareas para ver progreso</p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </div>

        {/* Charts Row 2 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
            <div className="bg-white rounded-xl shadow-sm border border-[#E7E2D6] overflow-hidden">
              <div className="bg-gradient-to-r from-[#1FA6A0] to-[#178A85] px-5 py-3 flex items-center gap-2">
                <Users className="w-4 h-4 text-white" />
                <h2 className="text-white font-semibold text-sm" style={{ fontFamily: 'Spectral, serif' }}>Contactos por Estado</h2>
              </div>
              <div className="p-4">
                {statusPieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie data={statusPieData} cx="50%" cy="50%" outerRadius={80} innerRadius={40} dataKey="value" label={({ name, value }) => `${name}: ${value}`} paddingAngle={3}>
                        {statusPieData.map((entry, idx) => (<Cell key={idx} fill={COLORS[idx % COLORS.length]} />))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: '8px' }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[250px] flex flex-col items-center justify-center">
                    <div className="w-14 h-14 rounded-full bg-[#F5F0E8] flex items-center justify-center mb-3"><Users className="w-6 h-6 text-[#1FA6A0]" /></div>
                    <p className="text-muted-foreground text-sm">Registra contactos para ver distribucion</p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }}>
            <div className="bg-white rounded-xl shadow-sm border border-[#E7E2D6] overflow-hidden">
              <div className="bg-gradient-to-r from-purple-500 to-purple-700 px-5 py-3 flex items-center gap-2">
                <Heart className="w-4 h-4 text-white" />
                <h2 className="text-white font-semibold text-sm" style={{ fontFamily: 'Spectral, serif' }}>Contactos por Relacion</h2>
              </div>
              <div className="p-4">
                {relationPieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie data={relationPieData} cx="50%" cy="50%" outerRadius={80} innerRadius={40} dataKey="value" label={({ name, value }) => `${name}: ${value}`} paddingAngle={3}>
                        {relationPieData.map((entry, idx) => (<Cell key={idx} fill={COLORS[(idx + 2) % COLORS.length]} />))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: '8px' }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[250px] flex flex-col items-center justify-center">
                    <div className="w-14 h-14 rounded-full bg-[#F5F0E8] flex items-center justify-center mb-3"><Heart className="w-6 h-6 text-purple-500" /></div>
                    <p className="text-muted-foreground text-sm">Registra contactos para ver relaciones</p>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
