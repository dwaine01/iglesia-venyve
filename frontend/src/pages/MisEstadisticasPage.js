import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
import { Loader2, Sparkles, TriangleAlert, UserCog, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { translateTechnicalText } from '../lib/displayLabels';

// ETAPA 5A: "Mis estadísticas" — resultados del propio trabajo (mentor y/o
// líder); siempre disponible, no depende de ninguna capability asignada.
// Reutiliza la misma agregación de /api/supervision (sin reportes paralelos).
const Stat = ({ label, value }) => (
  <div className="rounded-xl border border-[#E8E5DE] bg-white p-3 text-left" data-testid={`mis-estadisticas-stat-${label.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}>
    <div className="text-2xl font-semibold text-[#101D36]">{value ?? 0}</div>
    <div className="text-xs text-slate-500">{label}</div>
  </div>
);

const Block = ({ icon: Icon, title, subtitle, data, testId }) => (
  <section className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid={testId}>
    <h2 className="flex items-center gap-2 font-['Spectral'] text-lg font-semibold text-[#101D36]"><Icon className="h-4 w-4 text-[#9A7A2F]" />{title}</h2>
    <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
    <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
      <Stat label="Hogares visitados" value={data.invasion.households_visited} />
      <Stat label="Visitas" value={data.invasion.visits_total} />
      <Stat label="Personas únicas contactadas" value={data.invasion.unique_persons_contacted} />
      <Stat label="Interesados" value={data.invasion.interested} />
      <Stat label="Aceptaron consolidación" value={data.consolidation.accepted} />
      <Stat label="Procesos iniciados" value={data.consolidation.started} />
      <Stat label="Actividades realizadas" value={data.consolidation.activities_done} />
      <Stat label="Actividades vencidas" value={data.consolidation.activities_overdue} />
      <Stat label="Libros en custodia" value={data.library.mentor_custody.in_custody} />
    </div>
  </section>
);

export default function MisEstadisticasPage() {
  const { API, getAuthHeaders } = useAuth();
  const [stats, setStats] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API}/api/core/me/stats`, getAuthHeaders())
      .then((response) => setStats(response.data))
      .catch((requestError) => setError(translateTechnicalText(requestError?.response?.data?.detail || 'No se pudieron cargar tus estadísticas.')));
  }, [API, getAuthHeaders]);

  if (error) return <div className="min-h-screen bg-[#F8F6F0] p-4" data-testid="mis-estadisticas-error"><div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"><TriangleAlert className="mt-0.5 h-4 w-4" />{error}</div></div>;
  if (!stats) return <div className="flex min-h-[60vh] items-center justify-center" data-testid="mis-estadisticas-loading"><Loader2 className="h-7 w-7 animate-spin text-[#9A7A2F]" /></div>;

  return (
    <div className="min-h-screen bg-[#F8F6F0] pb-10" data-testid="mis-estadisticas-page">
      <motion.header initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="bg-[#101D36] px-4 py-8 text-white sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl">
          <p className="text-xs font-semibold uppercase text-[#D4B871]">Mis estadísticas</p>
          <h1 className="mt-1 font-['Spectral'] text-2xl font-bold sm:text-3xl">Resultados de tu propio trabajo</h1>
          <p className="mt-2 text-sm text-white/65">Lo que tú contactaste, acompañaste o lideraste. Un número bajo no es un error: es información para investigar el motivo, no para asumir culpas.</p>
        </div>
      </motion.header>

      <div className="mx-auto max-w-3xl space-y-4 px-4 py-6 sm:px-6 lg:px-8">
        {!stats.has_any_activity && <div className="flex items-start gap-2 rounded-xl border border-[#E8E5DE] bg-white p-4 text-sm text-slate-500" data-testid="mis-estadisticas-sin-actividad"><Sparkles className="mt-0.5 h-4 w-4 text-[#9A7A2F]" />Aún no tienes actividad registrada como mentor o líder.</div>}
        {stats.as_mentor && <Block icon={Users} title="Como mentor" subtitle="Tus visitas, hogares y consolidación" data={stats.as_mentor} testId="mis-estadisticas-mentor" />}
        {stats.as_leader && <Block icon={UserCog} title="Como líder" subtitle={`Tu rama: ${stats.as_leader.led_group_count} grupo(s) que lideras y sus descendientes`} data={stats.as_leader} testId="mis-estadisticas-lider" />}
      </div>
    </div>
  );
}
