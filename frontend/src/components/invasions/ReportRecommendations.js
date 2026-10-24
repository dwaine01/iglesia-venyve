import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Save } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { COLORS } from './reportCharts';

// Sección 8 del Reporte de invasión: recomendaciones generadas por reglas
// (con su evidencia) y las lecciones aprendidas que escriben el organizador
// y el pastor. Ambas siguen editables aunque el reporte final esté congelado.
const PRIORITY = {
  alta: { label: 'Prioridad alta', color: COLORS.red, bg: '#fef2f2' },
  media: { label: 'Prioridad media', color: COLORS.amber, bg: '#fffbeb' },
  baja: { label: 'Prioridad baja', color: COLORS.slate, bg: '#f8fafc' },
};
const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString('es', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }) : '');

// Evidencia: cifra grande y, si hay base, una mini barra con el % (texto + barra).
function Evidence({ evidence, color }) {
  const { label, value, total, pct } = evidence;
  return (
    <div className="mt-2 rounded-lg bg-white/80 p-2 ring-1 ring-slate-200">
      <p className="text-[11px] text-slate-600">{label}</p>
      <p className="text-xl font-semibold" style={{ color }}>{value}{total ? <span className="text-xs font-normal text-slate-600"> de {total} · {pct}%</span> : null}</p>
      {total ? <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${label}: ${pct}%`}><div className="h-full rounded-full" style={{ width: `${Math.min(pct, 100)}%`, background: color }} /></div> : null}
    </div>
  );
}

function RecommendationCard({ item, campaignId, onChange }) {
  const { API, getAuthHeaders } = useAuth();
  const [note, setNote] = useState(item.resolved_note || '');
  const [busy, setBusy] = useState(false);
  const style = PRIORITY[item.priority] || PRIORITY.baja;
  const save = async (resolved) => {
    setBusy(true);
    try {
      await axios.put(`${API}/api/invasions/${campaignId}/report/recommendations/${encodeURIComponent(item.id)}`, { resolved, note: note.trim() || null }, getAuthHeaders());
      onChange({ ...item, resolved, resolved_note: note.trim() || null });
      toast.success(resolved ? 'Marcada como resuelta' : 'Marcada como pendiente');
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar')); } finally { setBusy(false); }
  };
  return (
    <article className={`print-break-avoid flex min-w-0 flex-col rounded-xl border-l-4 p-3 ${item.resolved ? 'opacity-70' : ''}`} style={{ borderColor: style.color, background: style.bg }} data-testid={`rec-${item.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="rounded-full px-2 py-0.5 text-[11px] font-bold text-white" style={{ background: style.color }}>{style.label}</span>
        {item.resolved && <span className="rounded-full border border-[#bcd8c4] bg-[#eef5f0] px-2 py-0.5 text-[11px] font-semibold text-[#2f6e47]">Resuelta</span>}
      </div>
      <h3 className={`mt-2 text-sm font-semibold text-[#101D36] ${item.resolved ? 'line-through' : ''}`}>{item.title}</h3>
      <p className="mt-1 text-sm text-slate-700">{item.detail}</p>
      <Evidence evidence={item.evidence} color={style.color} />
      <p className="mt-2 text-xs text-slate-700"><span className="font-semibold">Responsable sugerido:</span> {item.responsible}</p>
      <p className="text-[11px] text-slate-500">{item.rule}</p>
      <div className="mt-auto pt-2 print:hidden">
        <label className="flex min-h-10 cursor-pointer items-center gap-2 text-sm font-semibold text-[#101D36]">
          <input type="checkbox" className="h-5 w-5 accent-[#2f6e47]" checked={item.resolved} disabled={busy} onChange={(event) => save(event.target.checked)} data-testid={`rec-resolved-${item.id}`} />
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Resuelta
        </label>
        <input type="text" value={note} onChange={(event) => setNote(event.target.value)} onBlur={() => { if (item.resolved && note.trim() !== (item.resolved_note || '')) save(true); }} maxLength={500} placeholder="Nota (opcional): qué se hizo" className="mt-1 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 py-2 text-base sm:text-sm" />
      </div>
      {item.resolved && item.resolved_by && <p className="mt-1 text-[11px] text-slate-500">Por {item.resolved_by}{item.resolved_at ? ` · ${fmtDateTime(item.resolved_at)}` : ''}</p>}
    </article>
  );
}

export function RecommendationsBlock({ campaignId, items: initial }) {
  const [items, setItems] = useState(initial || []);
  const [showResolved, setShowResolved] = useState(false);
  const pending = items.filter((item) => !item.resolved);
  const shown = showResolved ? items : pending;
  const counts = ['alta', 'media', 'baja'].map((key) => [key, pending.filter((item) => item.priority === key).length]);
  if (!items.length) return <p className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-600" data-testid="rec-empty">Ninguna regla se activó con los datos actuales: no hay recomendaciones por ahora.</p>;
  return (
    <div data-testid="report-recommendations-list">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-slate-700">{pending.length ? `${pending.length} pendiente(s): ${counts.filter(([, n]) => n).map(([key, n]) => `${n} ${key}`).join(' · ')}` : 'Todas las recomendaciones están resueltas.'}{items.length - pending.length ? ` · ${items.length - pending.length} resuelta(s)` : ''}</p>
        {items.length > pending.length && <label className="inline-flex min-h-10 items-center gap-2 text-sm print:hidden"><input type="checkbox" className="h-4 w-4" checked={showResolved} onChange={(event) => setShowResolved(event.target.checked)} data-testid="rec-show-resolved" />Mostrar resueltas</label>}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {shown.map((item) => <RecommendationCard key={item.id} item={item} campaignId={campaignId} onChange={(next) => setItems((current) => current.map((row) => (row.id === next.id ? next : row)))} />)}
      </div>
    </div>
  );
}

const LESSON_FIELDS = [
  ['worked', 'Qué funcionó', 'Lo que conviene repetir en la próxima invasión.'],
  ['improve', 'Qué mejorar', 'Lo que no salió como se esperaba.'],
  ['logistics', 'Logística', 'Transporte, materiales, horarios, puntos de encuentro.'],
  ['testimonies', 'Testimonios', 'Historias de personas alcanzadas o de los participantes.'],
];

export function LessonsBlock({ campaignId, notes: initial }) {
  const { API, getAuthHeaders } = useAuth();
  const [notes, setNotes] = useState(initial || {});
  const [draft, setDraft] = useState(() => Object.fromEntries([...LESSON_FIELDS.map(([key]) => key), 'pastor_recommendations'].map((key) => [key, (initial || {})[key] || ''])));
  const [busy, setBusy] = useState(false);
  const dirty = Object.keys(draft).some((key) => (draft[key] || '').trim() !== (notes[key] || ''));
  const save = async () => {
    setBusy(true);
    try {
      const response = await axios.put(`${API}/api/invasions/${campaignId}/report/notes`, draft, getAuthHeaders());
      setNotes(response.data); toast.success('Lecciones guardadas');
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudieron guardar las lecciones')); } finally { setBusy(false); }
  };
  const field = (key, label, hint, rows = 3) => (
    <label key={key} className="block min-w-0">
      <span className="text-sm font-semibold text-[#101D36]">{label}</span>
      <span className="block text-[11px] text-slate-500 print:hidden">{hint}</span>
      <textarea value={draft[key]} onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} rows={rows} maxLength={key === 'testimonies' || key === 'pastor_recommendations' ? 6000 : 4000} placeholder="Aún sin escribir" className="mt-1 w-full rounded-lg border border-[#D9D4C7] p-3 text-base sm:text-sm print:hidden" data-testid={`lesson-${key}`} />
      <p className="hidden whitespace-pre-wrap text-sm text-slate-700 print:block">{notes[key] || 'Aún sin escribir.'}</p>
    </label>
  );
  return (
    <div className="space-y-4" data-testid="report-lessons">
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">{LESSON_FIELDS.map(([key, label, hint]) => field(key, label, hint))}</div>
      <div className="rounded-xl border border-[#D9C9A0] bg-[#FBF7EC] p-3">{field('pastor_recommendations', 'Recomendaciones del pastor', 'Indicaciones del pastor para la próxima invasión.', 4)}</div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between print:hidden">
        <p className="text-[11px] text-slate-500">{notes.updated_by ? `Última edición: ${notes.updated_by} · ${fmtDateTime(notes.updated_at)}` : 'Nadie ha escrito todavía.'} Se puede editar también con el reporte final cerrado.</p>
        <button type="button" onClick={save} disabled={busy || !dirty} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#101D36] px-4 text-sm font-semibold text-white disabled:opacity-50" data-testid="lessons-save">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}Guardar lecciones</button>
      </div>
    </div>
  );
}
