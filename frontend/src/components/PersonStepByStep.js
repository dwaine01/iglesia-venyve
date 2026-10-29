import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, ChevronDown, Circle, CircleDot, Loader2, MinusCircle } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { CHURCH_TIME_ZONE } from '../lib/churchDate';
import { apiErrorMessage } from '../lib/apiErrors';

/** R3 · «Proceso paso a paso» (solo lectura): de «conocida» a «En proceso con mentor X», los pasos de
 *  Consolidación con su estado, fecha y quién, y los hitos de antes y después. Todo sale de lo que ya guarda cada módulo. */
const fmt = (value) => {
  if (!value) return '—';
  const date = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric', timeZone: CHURCH_TIME_ZONE });
};
const STATE = {
  done: { icon: CheckCircle2, color: 'text-emerald-700', badge: 'border-emerald-200 bg-emerald-50 text-emerald-800' },
  current: { icon: CircleDot, color: 'text-blue-700', badge: 'border-blue-200 bg-blue-50 text-blue-800' },
  overdue: { icon: AlertTriangle, color: 'text-rose-700', badge: 'border-rose-200 bg-rose-50 text-rose-800' },
  pending: { icon: Circle, color: 'text-slate-400', badge: 'border-slate-200 bg-slate-50 text-slate-600' },
  not_applicable: { icon: MinusCircle, color: 'text-slate-400', badge: 'border-slate-200 bg-white text-slate-500' },
};

function Step({ step }) {
  const [open, setOpen] = useState(step.state === 'current' || step.state === 'overdue');
  const look = STATE[step.state] || STATE.pending;
  const Icon = look.icon;
  const when = step.state === 'done' ? `${fmt(step.completed_at)}${step.completed_by ? ` · ${step.completed_by}` : ''}`
    : step.state === 'overdue' ? `Venció el ${fmt(step.due_at)}` : step.state === 'current' ? (step.due_at ? `Vence el ${fmt(step.due_at)}` : 'Sin plazo') : null;
  return (
    <li className="border-b border-[#EEECE6] last:border-0" data-testid={`step-${step.stage_key}`}>
      <button type="button" onClick={() => setOpen(!open)} className="flex min-h-14 w-full items-center gap-3 py-2 text-left" aria-expanded={open}>
        <Icon className={`h-6 w-6 shrink-0 ${look.color}`} />
        <span className="min-w-0 flex-1">
          <span className="block text-base font-semibold text-[#101D36]">{step.order}. {step.name}</span>
          {when && <span className="block text-sm text-slate-600">{when}</span>}
        </span>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${look.badge}`} data-testid={`step-state-${step.stage_key}`}>{step.label}</span>
        {step.tasks.length > 0 && <ChevronDown className={`h-4 w-4 shrink-0 text-slate-400 transition ${open ? 'rotate-180' : ''}`} />}
      </button>
      {open && (step.tasks.length > 0 || step.note) && (
        <div className="mb-3 ml-9 space-y-1 text-sm">
          {step.tasks.map((task) => (
            <p key={task.task_id} className={`flex items-start gap-2 ${task.completed ? 'text-slate-700' : 'text-slate-500'}`}>
              {task.completed ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" /> : <Circle className="mt-0.5 h-4 w-4 shrink-0 text-slate-300" />}
              <span>{task.label}{task.completed && task.completed_at ? ` · ${fmt(task.completed_at)}` : ''}{task.evidence_count ? ` · ${task.evidence_count} evidencia(s)` : ''}</span>
            </p>
          ))}
          {step.note && <p className="text-slate-500">{step.note}</p>}
        </div>
      )}
    </li>
  );
}

export function PersonStepByStep({ personId, showEnrollmentLink = true }) {
  const { API, getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [showLog, setShowLog] = useState(false);
  useEffect(() => {
    setData(null); setError('');
    axios.get(`${API}/api/persons/${personId}/step-by-step`, getAuthHeaders()).then((response) => setData(response.data))
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar el proceso paso a paso')));
  }, [API, getAuthHeaders, personId]);

  if (error) return <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</p>;
  if (!data) return <div className="flex justify-center p-6"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  const consolidation = data.consolidation;
  const book = consolidation?.by_the_book;
  return (
    <div className="space-y-5" data-testid="person-step-by-step">
      <section className="rounded-xl border-2 border-[#101D36] bg-[#F7F5EF] p-4" data-testid="step-now">
        <p className="text-xs font-semibold uppercase text-[#9A7A2F]">Dónde está hoy</p>
        <p className="mt-1 font-['Spectral'] text-2xl font-semibold text-[#101D36]" data-testid="step-now-label">{data.now.label}</p>
        <p className="mt-1 text-[15px] text-slate-700">Origen: <b>{data.origin.label}</b>{data.now.step ? <> · Paso actual: <b>{data.now.step}</b></> : null}{data.now.since ? ` · desde ${fmt(data.now.since)}` : ''}</p>
        {showEnrollmentLink && consolidation && <Link to={`/procesos/consolidacion/${consolidation.enrollment_id}`} className="mt-2 inline-flex min-h-11 items-center text-[15px] font-semibold text-[#101D36] underline">Abrir expediente de Consolidación</Link>}
      </section>

      {book && (
        <section className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="step-by-the-book">
          {[['Pasos hechos', book.steps_done], ['A tiempo', book.on_time], ['Hechos tarde', book.late], ['Atrasados ahora', book.overdue_now]].map(([label, value]) => (
            <article key={label} className="rounded-xl border border-[#E8E5DE] bg-white p-3"><span className="block text-sm text-slate-600">{label}</span><b className="font-['Spectral'] text-2xl text-[#101D36]">{value}</b></article>
          ))}
        </section>
      )}

      {consolidation && (
        <section className="rounded-xl border border-[#E8E5DE] bg-white p-4">
          <h3 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">Pasos de Consolidación</h3>
          <p className="text-sm text-slate-500">Toque un paso para ver sus puntos.</p>
          <ul className="mt-2">{consolidation.steps.map((step) => <Step key={step.stage_key} step={step} />)}</ul>
        </section>
      )}

      <section className="rounded-xl border border-[#E8E5DE] bg-white p-4" data-testid="step-milestones">
        <h3 className="font-['Spectral'] text-xl font-semibold text-[#101D36]">Recorrido</h3>
        {data.milestones.length === 0 ? <p className="text-sm text-slate-500">Todavía no hay hitos registrados.</p> : (
          <ol className="mt-2 space-y-3 border-l-2 border-[#E8E5DE] pl-4">
            {data.milestones.map((row, index) => (
              <li key={`${row.key}-${index}`} className="relative" data-testid={`milestone-${row.key}`}>
                <span className="absolute -left-[23px] top-1.5 h-3 w-3 rounded-full border-2 border-white bg-[#9A7A2F]" />
                <span className="block text-sm text-slate-500">{fmt(row.at)}</span>
                <span className="block text-base font-semibold text-[#101D36]">{row.label}</span>
                {(row.by || row.detail) && <span className="block text-sm text-slate-600">{[row.by, row.detail].filter(Boolean).join(' · ')}</span>}
              </li>
            ))}
          </ol>
        )}
      </section>

      {consolidation?.timeline?.length > 0 && (
        <section className="rounded-xl border border-[#E8E5DE] bg-white p-4">
          <button type="button" onClick={() => setShowLog(!showLog)} className="flex min-h-11 w-full items-center justify-between text-left font-semibold text-[#101D36]" aria-expanded={showLog}>
            Historial del expediente ({consolidation.timeline.length})<ChevronDown className={`h-4 w-4 transition ${showLog ? 'rotate-180' : ''}`} />
          </button>
          {showLog && <ul className="mt-2 divide-y divide-[#EEECE6] text-sm">{consolidation.timeline.map((row, index) => (
            <li key={index} className="py-2"><span className="text-slate-500">{fmt(row.at)}{row.by ? ` · ${row.by}` : ''}</span><span className="block text-slate-800">{row.title}{row.detail ? ` — ${row.detail}` : ''}</span></li>
          ))}</ul>}
        </section>
      )}
      {data.history.length > 0 && <p className="text-sm text-slate-500">Además tiene {data.history.length} expediente(s) anterior(es) en el historial.</p>}
      <p className="text-xs text-slate-500">{data.note}</p>
    </div>
  );
}
