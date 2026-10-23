import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, BarChart3, CalendarDays, Clock3, Footprints, Sunrise, Users } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { MyLibraryHoldingsCard } from '../../components/outreach/MyLibraryHoldingsCard';
import { ProcessError, ProcessLoading, ProcessShell } from '../../components/processes/ProcessShell';
import { Badge } from '../../components/ui/badge';
import { errorDetailText } from '../../lib/errorText';

const DECISION_STATUS_LABEL = {
  contacted: 'Contactado', pending_decision: 'Pendiente de decisión', accepted: 'Aceptó consolidación',
  start_scheduled: 'Inicio programado', in_progress: 'En proceso', paused: 'Pausado o desistió', completed: 'Completado',
};

const formatDate = (isoDate) => {
  if (!isoDate) return '—';
  const [y, m, d] = isoDate.split('-');
  return `${d}/${m}/${y}`;
};

const ActivityBucketCard = ({ icon: Icon, title, tone, items, testId }) => (
  <article className="border bg-white p-4" data-testid={testId}>
    <div className="flex items-center gap-2"><Icon className={`h-5 w-5 ${tone}`} /><b>{title}</b><Badge className="ml-auto bg-slate-100 text-slate-600">{items.length}</Badge></div>
    <div className="mt-3 space-y-2">
      {items.length === 0 && <p className="text-xs text-slate-400">Nada aquí.</p>}
      {items.map((item) => (
        <Link key={item.activity_id} to={`/procesos/consolidacion/${item.enrollment_id}`} className="block border-l-2 border-amber-400 pl-2 text-sm hover:bg-[#F6F4EF]" data-testid={`mentor-panel-activity-${item.activity_id}`}>
          <b className="block">{item.person_name}</b>
          <span className="text-xs text-slate-500">{item.title} · {formatDate(item.scheduled_date)} {item.moment_label}</span>
        </Link>
      ))}
    </div>
  </article>
);

export default function MentorPanelPage() {
  const { API, getAuthHeaders } = useAuth();
  const [panel, setPanel] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    axios.get(`${API}/api/processes/consolidation/my-panel`, getAuthHeaders())
      .then((response) => setPanel(response.data))
      .catch((requestError) => setError(errorDetailText(requestError, 'No se pudo cargar tu panel')));
  }, [API, getAuthHeaders]);

  return (
    <ProcessShell title="Mi Panel de Mentor" eyebrow="Invasiones · Consolidación" description="Solo tus discípulos: lo que te toca hoy, lo atrasado y lo próximo.">
      {!panel && !error ? <ProcessLoading /> : error ? <ProcessError message={error} /> : <div className="space-y-6" data-testid="mentor-panel-page">
        <div className="grid gap-3 sm:grid-cols-2" data-testid="mentor-panel-quick-links">
          <Link to="/mentoria/visitas" className="flex items-center gap-3 rounded-xl border border-[#E8E5DE] bg-white p-4 hover:border-[#132443]/40 hover:shadow-sm" data-testid="mentor-panel-link-outreach">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#132443]/10 text-[#132443]"><Footprints className="h-5 w-5" /></div>
            <div><b className="block text-[#101D36]">Mi invasión</b><span className="text-xs text-slate-500">Registrar una visita o contacto nuevo</span></div>
          </Link>
          <Link to="/mentoria/supervision" className="flex items-center gap-3 rounded-xl border border-[#E8E5DE] bg-white p-4 hover:border-[#132443]/40 hover:shadow-sm" data-testid="mentor-panel-link-progress">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#132443]/10 text-[#132443]"><BarChart3 className="h-5 w-5" /></div>
            <div><b className="block text-[#101D36]">Mi progreso</b><span className="text-xs text-slate-500">Mis números: visitas, aceptaciones, actividades</span></div>
          </Link>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <ActivityBucketCard icon={Sunrise} title="Hoy" tone="text-amber-600" items={panel.today} testId="mentor-panel-bucket-today" />
          <ActivityBucketCard icon={AlertTriangle} title="Atrasado" tone="text-rose-600" items={panel.overdue} testId="mentor-panel-bucket-overdue" />
          <ActivityBucketCard icon={Clock3} title="Próximo" tone="text-sky-600" items={panel.upcoming} testId="mentor-panel-bucket-upcoming" />
        </div>
        <section className="border bg-white p-5" data-testid="mentor-panel-mentees">
          <div className="flex items-center gap-2"><Users className="h-5 w-5 text-slate-600" /><h2 className="font-['Spectral'] text-2xl font-semibold">Mis discípulos</h2></div>
          <div className="mt-4 divide-y">
            {(panel.mentees || []).length === 0 && <p className="py-4 text-sm text-slate-400">Aún no tienes discípulos en Consolidación.</p>}
            {(panel.mentees || []).map((mentee) => (
              <Link key={mentee.enrollment_id} to={`/procesos/consolidacion/${mentee.enrollment_id}`} className="flex items-center justify-between gap-3 py-3 text-sm hover:bg-[#F6F4EF]" data-testid={`mentor-panel-mentee-${mentee.enrollment_id}`}>
                <div><b className="block">{mentee.person_name}</b><span className="text-xs text-slate-500">{mentee.activities_done}/{mentee.activities_total} actividades realizadas</span></div>
                <Badge className="bg-amber-100 text-amber-700">{DECISION_STATUS_LABEL[mentee.decision_status] || mentee.decision_status || '—'}</Badge>
              </Link>
            ))}
          </div>
        </section>
        <div className="flex items-center gap-2 text-sm text-slate-500"><CalendarDays className="h-4 w-4" />Tu inventario de Librería 360, por invasión:</div>
        <MyLibraryHoldingsCard />
      </div>}
    </ProcessShell>
  );
}
