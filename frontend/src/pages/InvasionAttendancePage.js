import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { CalendarClock, Check, ClipboardList, Loader2, Search, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { useInvasionToday } from '../context/InvasionTodayContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { PersonPicker } from '../components/outreach/CreateCampaignDialog';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../components/ui/dialog';

const FILTERS = [['all', 'Todos'], ['confirmed', 'Confirmados'], ['invited', 'Sin responder'], ['declined', 'No vendrán'], ['attended', 'Ya asistieron']];
const dayLabel = (iso, options = { weekday: 'short', day: 'numeric', month: 'short' }) => new Date(`${iso}T12:00:00`).toLocaleDateString('es', options);
const STATUS_TONE = { confirmed: 'text-[#2f6e47]', invited: 'text-amber-700', declined: 'text-[#8f382f]' };

const Counter = ({ label, value, strong }) => (
  <div className={`rounded-xl border p-3 ${strong ? 'border-[#bcd8c4] bg-[#eef5f0]' : 'border-[#EEECE6] bg-white'}`}>
    <p className={`text-2xl font-semibold ${strong ? 'text-[#2f6e47]' : 'text-[#101D36]'}`}>{value}</p>
    <p className="text-xs text-slate-600">{label}</p>
  </div>
);

/** Asistencia por invasión y por jornada (pantalla pensada para el celular).
 * Solo la abren coordinadores generales, autoridad, organizador y encargado
 * general: el backend responde 403 a cualquier otra persona. */
export default function InvasionAttendancePage() {
  const { campaignId } = useParams();
  const navigate = useNavigate();
  const { API, getAuthHeaders } = useAuth();
  const { data: context } = useInvasionToday();
  const managed = context?.managed;
  const [day, setDay] = useState('');
  const [view, setView] = useState(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');
  const [busy, setBusy] = useState('');
  const [walkIn, setWalkIn] = useState(false);
  const [person, setPerson] = useState(null);

  // Sin invasión en la URL: la de hoy (o la más próxima) preseleccionada.
  useEffect(() => {
    if (campaignId || !managed) return;
    if (managed.length) navigate(`/invasiones/${managed[0].campaign_id}/asistencia`, { replace: true });
    else setError('No tienes invasiones para tomar asistencia.');
  }, [campaignId, managed, navigate]);

  const load = useCallback((selectedDay) => {
    if (!campaignId) return;
    axios.get(`${API}/api/invasions/${campaignId}/attendance`, { ...getAuthHeaders(), params: selectedDay ? { day: selectedDay } : {} })
      .then((response) => { setView(response.data); setDay(response.data.day); setError(''); })
      .catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo cargar la asistencia')));
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { setView(null); setDay(''); load(); }, [load]);

  const toggle = async (item) => {
    const next = !item.attended_day;
    setBusy(item.person_id);
    try {
      await axios.put(`${API}/api/invasions/${campaignId}/attendance/${item.person_id}`, { day, attended: next }, getAuthHeaders());
      setView((current) => {
        const items = current.items.map((row) => (row.person_id === item.person_id ? { ...row, attended_day: next } : row));
        const attended = items.filter((row) => row.attended_day).length;
        const days = current.days.map((entry) => (entry.day === day ? { ...entry, attended } : entry));
        return { ...current, items, days, counts: { ...current.counts, attended_day: attended, pct_day: current.counts.invited ? Math.round((attended / current.counts.invited) * 100) : null } };
      });
      toast.success(next ? `${item.name}: asistió` : `${item.name}: se quitó la asistencia`, {
        id: `attendance-${item.person_id}`, duration: 4000,
        action: { label: 'Deshacer', onClick: () => toggle({ ...item, attended_day: next }) },
      });
    } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo guardar')); } finally { setBusy(''); }
  };

  const addWalkIn = async () => {
    if (!person) return;
    setBusy('walk-in');
    try {
      const response = await axios.post(`${API}/api/invasions/${campaignId}/attendance/walk-in`, { person_id: person.person_id, day }, getAuthHeaders());
      toast.success(response.data.added ? `${person.name}: agregado y marcado` : `${person.name}: ya estaba en la lista, quedó marcado`);
      setWalkIn(false); setPerson(null); load(day);
    } catch (requestError) { toast.error(apiErrorMessage(requestError, 'No se pudo agregar')); } finally { setBusy(''); }
  };

  const shown = useMemo(() => {
    if (!view) return [];
    const text = query.trim().toLowerCase();
    return view.items.filter((item) => (!text || item.name.toLowerCase().includes(text))
      && (filter === 'all' || (filter === 'attended' ? item.attended_day : item.status === filter)));
  }, [view, query, filter]);

  if (error) return <div className="p-4 sm:p-6"><p className="rounded-xl border border-red-200 bg-red-50 p-4 text-base text-red-800" data-testid="attendance-error">{error}</p></div>;
  if (!view) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  const options = [...(managed || [])];
  if (!options.some((item) => item.campaign_id === view.campaign_id)) options.unshift({ campaign_id: view.campaign_id, name: view.name });
  const counts = view.counts;
  return (
    <div className="mx-auto w-full max-w-3xl space-y-4 p-4 sm:p-6" data-testid="attendance-page">
      <header className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">Asistencia</h1>
          <Link to={`/invasiones/${view.campaign_id}/programa`} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-4 text-[15px] font-semibold text-[#101D36]" data-testid="attendance-program-link"><ClipboardList className="h-4 w-4" />Programa</Link>
        </div>
        <label className="block">
          <span className="text-sm font-semibold text-slate-600">Invasión</span>
          <select value={view.campaign_id} onChange={(event) => navigate(`/invasiones/${event.target.value}/asistencia`)} className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-base text-[#101D36]" data-testid="attendance-campaign">
            {options.map((item) => <option key={item.campaign_id} value={item.campaign_id}>{item.name}{item.active_today ? ' · hoy' : ''}</option>)}
          </select>
        </label>
        <div>
          <span className="text-sm font-semibold text-slate-600">Jornada</span>
          <div className="mt-1 flex gap-2 overflow-x-auto pb-1" data-testid="attendance-days">
            {view.days.map((item) => (
              <button key={item.day} type="button" onClick={() => load(item.day)} className={`flex min-h-12 shrink-0 flex-col items-start justify-center rounded-lg border px-3 text-left ${item.day === day ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`} data-testid={`attendance-day-${item.day}`} aria-pressed={item.day === day}>
                <span className="text-[15px] font-semibold capitalize">{dayLabel(item.day)}</span>
                <span className={`flex items-center gap-1 text-xs ${item.day === day ? 'text-white/80' : 'text-slate-500'}`}><CalendarClock className="h-3 w-3" />{item.start_time || 'Sin hora'} · {item.attended} asistieron</span>
              </button>
            ))}
          </div>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-2 sm:grid-cols-4" data-testid="attendance-counters">
        <Counter label="Asistieron (jornada)" value={counts.attended_day} strong />
        <Counter label="Confirmados" value={counts.confirmed} />
        <Counter label="Invitados" value={counts.invited} />
        <Counter label="% del día" value={counts.pct_day == null ? '—' : `${counts.pct_day}%`} />
      </section>

      <section className="space-y-3">
        <div className="relative"><Search className="absolute left-3 top-3.5 h-5 w-5 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por nombre" className="h-12 w-full rounded-lg border border-[#D9D4C7] bg-white pl-10 pr-3 text-base" data-testid="attendance-search" /></div>
        <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1" data-testid="attendance-filters">
          {FILTERS.map(([key, label]) => <button key={key} type="button" onClick={() => setFilter(key)} className={`min-h-11 shrink-0 rounded-full border px-4 text-[15px] font-semibold ${filter === key ? 'border-[#132443] bg-[#132443] text-white' : 'border-[#D9D4C7] bg-white text-[#101D36]'}`} data-testid={`attendance-filter-${key}`}>{label}</button>)}
        </div>
        <button type="button" onClick={() => setWalkIn(true)} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg border border-dashed border-[#132443] bg-white text-[15px] font-semibold text-[#132443]" data-testid="attendance-walk-in"><UserPlus className="h-5 w-5" />Llegó sin estar invitado: agregar y marcar</button>
      </section>

      <ul className="divide-y divide-[#EEECE6] overflow-hidden rounded-xl border border-[#E8E5DE] bg-white" data-testid="attendance-list">
        {shown.length === 0 && <li className="p-6 text-center text-base text-slate-500">Nadie en esta vista.</li>}
        {shown.map((item) => (
          <li key={item.person_id}>
            <button type="button" onClick={() => toggle(item)} disabled={busy === item.person_id} className={`flex min-h-14 w-full items-center gap-3 px-3 py-2 text-left ${item.attended_day ? 'bg-[#f3f9f5]' : 'bg-white'}`} data-testid={`attendance-row-${item.person_id}`} aria-pressed={item.attended_day}>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-base font-semibold text-[#101D36]">{item.name}</span>
                <span className="block truncate text-xs text-slate-500">{[item.role_labels.join(' · '), item.front_group || 'Sin Grupo Frontal'].join(' · ')}{item.walk_in ? ' · llegó sin invitación' : ''} · <span className={STATUS_TONE[item.status] || ''}>{item.status_label}</span></span>
              </span>
              <span className={`inline-flex min-h-10 shrink-0 items-center gap-1 rounded-full px-3 text-sm font-semibold ${item.attended_day ? 'bg-[#2f6e47] text-white' : 'border border-[#D9D4C7] text-[#101D36]'}`}>
                {busy === item.person_id ? <Loader2 className="h-4 w-4 animate-spin" /> : item.attended_day ? <Check className="h-4 w-4" /> : null}{item.attended_day ? 'Asistió' : 'Marcar'}
              </span>
            </button>
          </li>
        ))}
      </ul>
      <p className="text-center text-xs text-slate-500">Un toque marca la asistencia de esta jornada; otro toque la quita. Se guarda al instante. La pastora no cuenta en los porcentajes.</p>

      <Dialog open={walkIn} onOpenChange={(value) => { setWalkIn(value); if (!value) setPerson(null); }}>
        <DialogContent className="bg-white sm:max-w-md" data-testid="attendance-walk-in-dialog">
          <DialogHeader><DialogTitle>Agregar y marcar asistencia</DialogTitle><DialogDescription>Busca a la persona en Persona 360. Entra como colaborador confirmado y queda marcada en la jornada del {dayLabel(day, { day: 'numeric', month: 'long' })}.</DialogDescription></DialogHeader>
          <PersonPicker value={person} onChange={setPerson} testId="attendance-walk-in-person" />
          <button type="button" onClick={addWalkIn} disabled={!person || busy === 'walk-in'} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#132443] text-[15px] font-semibold text-white disabled:opacity-50" data-testid="attendance-walk-in-save">{busy === 'walk-in' ? <Loader2 className="h-5 w-5 animate-spin" /> : <Check className="h-5 w-5" />}Agregar y marcar</button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
