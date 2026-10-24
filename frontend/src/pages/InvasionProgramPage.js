import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useParams } from 'react-router-dom';
import { CalendarDays, ClipboardCheck, Clock, HandHeart, Loader2, MapPin, Navigation, Pencil, Phone, Users } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { apiErrorMessage } from '../lib/apiErrors';
import { CreateCampaignDialog } from '../components/outreach/CreateCampaignDialog';

const fmtDay = (iso, options = { weekday: 'long', day: 'numeric', month: 'long' }) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString('es', options) : '');
const duration = (minutes) => (minutes ? `${Math.floor(minutes / 60) ? `${Math.floor(minutes / 60)} h` : ''}${minutes % 60 ? ` ${minutes % 60} min` : ''}`.trim() : '');
const endTime = (start, minutes) => {
  if (!start || !minutes) return '';
  const [hours, mins] = start.split(':').map(Number);
  const total = hours * 60 + mins + minutes;
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
};
const directions = (place) => (place?.maps_url || (place?.address ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(place.address)}` : null));

function Block({ icon: Icon, title, children, testId }) {
  return (
    <section className="min-w-0 rounded-2xl border border-[#E8E5DE] bg-white p-4" data-testid={testId}>
      <h2 className="mb-2 flex items-center gap-2 text-base font-semibold text-[#101D36]"><Icon className="h-5 w-5 text-[#9A7A2F]" />{title}</h2>
      {children}
    </section>
  );
}
const Empty = () => <p className="text-base text-slate-500">Sin indicar</p>;

/** Programa de la invasión: lectura clara para todos sus invitados; el
 * organizador/autoridad lo edita con el mismo formulario por pasos. */
export default function InvasionProgramPage() {
  const { campaignId } = useParams();
  const { API, getAuthHeaders } = useAuth();
  const [program, setProgram] = useState(null);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const load = useCallback(() => {
    axios.get(`${API}/api/invasions/${campaignId}/program`, getAuthHeaders()).then((response) => setProgram(response.data)).catch((requestError) => setError(apiErrorMessage(requestError, 'No se pudo abrir el programa')));
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => { setProgram(null); setError(''); load(); }, [load]);

  if (error) return <div className="p-4 sm:p-6"><p className="rounded-xl border border-red-200 bg-red-50 p-4 text-base text-red-800" data-testid="program-error">{error}</p></div>;
  if (!program) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  const site = program.site_meeting_point;
  const departure = program.departure_point || program.meeting_place;
  const siteLink = directions(site);
  const departureLink = departure ? directions({ address: departure }) : null;
  return (
    <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6" data-testid="program-page">
      <header className="space-y-3">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7A5F22]">Programa de la invasión</p>
        <h1 className="font-['Spectral'] text-3xl font-semibold text-[#101D36]">{program.name}</h1>
        {program.purpose && <p className="text-base text-slate-700">{program.purpose}</p>}
        <div className="grid grid-cols-1 gap-2 sm:flex">
          {program.can_take_attendance && <Link to={`/invasiones/${program.campaign_id}/asistencia`} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg bg-[#132443] px-4 text-[15px] font-semibold text-white" data-testid="program-attendance-link"><ClipboardCheck className="h-5 w-5" />Tomar asistencia</Link>}
          {program.can_take_attendance && <Link to={`/invasiones/${program.campaign_id}/ayuda`} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border-2 border-[#b91c1c] bg-white px-4 text-[15px] font-semibold text-[#b91c1c]" data-testid="program-help-link">Alertas de ayuda</Link>}
          {program.can_edit && <button type="button" onClick={() => setEditing(true)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-lg border border-[#D9D4C7] bg-white px-4 text-[15px] font-semibold text-[#101D36]" data-testid="program-edit"><Pencil className="h-5 w-5" />Editar programa</button>}
        </div>
      </header>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Block icon={CalendarDays} title="Jornadas" testId="program-days">
          {program.schedule_days.length ? <ol className="space-y-2">{program.schedule_days.map((item) => (
            <li key={item.day} className="rounded-xl bg-[#FBFAF7] p-3">
              <p className="text-base font-semibold capitalize text-[#101D36]">{fmtDay(item.day)}</p>
              <p className="flex items-center gap-1 text-[15px] text-slate-700"><Clock className="h-4 w-4 text-slate-400" />{item.start_time ? `${item.start_time}${endTime(item.start_time, item.duration_minutes) ? ` a ${endTime(item.start_time, item.duration_minutes)}` : ''}` : 'Horario por confirmar'}{item.duration_minutes ? ` · ${duration(item.duration_minutes)}` : ''}</p>
            </li>
          ))}</ol> : <Empty />}
        </Block>

        <Block icon={MapPin} title="Lugar y sectores" testId="program-place">
          <p className="text-base font-semibold text-[#101D36]">{program.location}</p>
          {program.sectors?.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{program.sectors.map((sector) => <span key={sector} className="rounded-full border border-[#D9D4C7] px-3 py-1 text-sm text-[#101D36]">{sector}</span>)}</div>}
          {program.zone_notes && <p className="mt-2 whitespace-pre-line text-[15px] text-slate-700">{program.zone_notes}</p>}
        </Block>

        <Block icon={Navigation} title="Puntos de encuentro" testId="program-meeting">
          <div className="space-y-3">
            <div>
              <p className="text-sm text-slate-500">Encuentro inicial (salida){program.meeting_time ? ` · ${program.meeting_time}` : ''}</p>
              <p className="text-base font-semibold text-[#101D36]">{departure || 'Sin indicar'}</p>
              {departureLink && <a href={departureLink} target="_blank" rel="noreferrer" className="mt-1 inline-flex min-h-11 items-center gap-2 rounded-lg border border-[#D9D4C7] px-4 text-[15px] font-semibold text-[#101D36]" data-testid="program-departure-directions"><Navigation className="h-4 w-4" />Cómo llegar</a>}
            </div>
            <div>
              <p className="text-sm text-slate-500">Encuentro en el lugar</p>
              <p className="text-base font-semibold text-[#101D36]">{[site?.address, site?.reference].filter(Boolean).join(' · ') || 'Sin indicar'}</p>
              {siteLink && <a href={siteLink} target="_blank" rel="noreferrer" className="mt-1 inline-flex min-h-11 items-center gap-2 rounded-lg bg-[#132443] px-4 text-[15px] font-semibold text-white" data-testid="program-site-directions"><Navigation className="h-4 w-4" />Cómo llegar</a>}
            </div>
          </div>
        </Block>

        <Block icon={HandHeart} title="Preparación en oración" testId="program-prayer">
          <p className="text-base text-[#101D36]">{program.prayer_start_date ? <>Semana de oración desde el <b>{fmtDay(program.prayer_start_date, { weekday: 'long', day: 'numeric', month: 'long' })}</b></> : 'Sin indicar'}</p>
          {program.prayer_meetings.length > 0
            ? <ul className="mt-2 space-y-1.5">{program.prayer_meetings.map((meeting) => <li key={meeting.meeting_id} className="rounded-lg bg-[#FBF6EA] p-2 text-[15px] text-[#101D36]"><span className="font-semibold capitalize">{fmtDay(meeting.day, { weekday: 'short', day: 'numeric', month: 'short' })} · {meeting.time}</span> — {meeting.place}{meeting.note ? ` (${meeting.note})` : ''}</li>)}</ul>
            : <p className="mt-1 text-sm text-slate-500">Aún no hay reuniones de oración programadas.</p>}
        </Block>

        <Block icon={Users} title="Encargados" testId="program-leads">
          <dl className="space-y-2 text-base">
            <div><dt className="text-sm text-slate-500">Encargado general</dt><dd className="font-semibold text-[#101D36]">{program.general_lead?.name || 'Sin indicar'}</dd></div>
            <div><dt className="text-sm text-slate-500">Logística</dt><dd className="font-semibold text-[#101D36]">{program.logistics_lead?.name || 'Sin indicar'}</dd></div>
          </dl>
        </Block>

        <Block icon={Phone} title="Contacto de emergencias" testId="program-emergency">
          {program.emergency_contact
            ? <><p className="text-base font-semibold text-[#101D36]">{program.emergency_contact.name}</p><a href={`tel:${program.emergency_contact.phone.replace(/[^\d+]/g, '')}`} className="mt-1 inline-flex min-h-12 items-center gap-2 rounded-lg bg-[#8f382f] px-4 text-[15px] font-semibold text-white" data-testid="program-emergency-call"><Phone className="h-5 w-5" />Llamar {program.emergency_contact.phone}</a></>
            : <Empty />}
        </Block>
      </div>

      {(program.instructions || program.description) && <Block icon={ClipboardCheck} title="Instrucciones" testId="program-instructions">
        {program.instructions && <p className="whitespace-pre-line text-base text-[#101D36]">{program.instructions}</p>}
        {program.description && <p className="mt-2 whitespace-pre-line text-[15px] text-slate-700">{program.description}</p>}
      </Block>}

      {program.can_edit && <CreateCampaignDialog open={editing} onOpenChange={setEditing} campaignId={program.campaign_id} onCreated={() => { setEditing(false); load(); }} />}
    </div>
  );
}
