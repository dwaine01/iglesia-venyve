import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Link, useSearchParams } from 'react-router-dom';
import { BarChart3, ClipboardList, Footprints, ListChecks, Loader2, Map as MapIcon, PenSquare, UserPlus } from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { OUTREACH_CHANGED_EVENT, useInvasionToday } from '../context/InvasionTodayContext';
import { DoorForm } from '../components/doors/DoorForm';
import { DoorStats } from '../components/doors/DoorStats';
import { DoorReport } from '../components/doors/DoorReport';
import { StreetCard } from '../components/doors/StreetCard';
import { PendingDoors, RevisitSheet } from '../components/doors/PendingDoors';
import { InvasionHousesMap } from '../components/outreach/InvasionHousesMap';

const VIEWS = [['registrar', 'Registrar', PenSquare], ['pendientes', 'Pendientes', ListChecks], ['mapa', 'Mapa', MapIcon], ['reporte', 'Reporte', BarChart3]];
import { AddVisitDialog } from '../components/outreach/AddVisitDialog';

/** Puerta a puerta: al abrir la invasión activa, las cifras arriba (se
 * actualizan al guardar), la calle activa y el registro de cada puerta. */
export default function DoorToDoorPage() {
  const { API, getAuthHeaders, user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const { data: context, current } = useInvasionToday();
  const active = context?.active || [];
  const campaignId = searchParams.get('invasion') || current?.campaign_id || active[0]?.campaign_id || '';
  const campaign = active.find((item) => item.campaign_id === campaignId) || null;
  const [summary, setSummary] = useState(null);
  const [street, setStreet] = useState(undefined);
  const [books, setBooks] = useState([]);
  const [error, setError] = useState('');
  const [looseOpen, setLooseOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [revisit, setRevisit] = useState(null);
  const view = VIEWS.some(([key]) => key === searchParams.get('vista')) ? searchParams.get('vista') : 'registrar';
  const setView = (key) => { const next = new URLSearchParams(searchParams); next.set('vista', key); if (campaignId) next.set('invasion', campaignId); setSearchParams(next, { replace: true }); };

  const saved = () => { setRefreshKey((value) => value + 1); window.dispatchEvent(new Event(OUTREACH_CHANGED_EVENT)); };
  const loadSummary = useCallback(() => {
    if (!campaignId) return;
    axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/door-summary`, getAuthHeaders()).then((response) => setSummary(response.data)).catch(() => {});
  }, [API, getAuthHeaders, campaignId]);
  useEffect(() => {
    if (!campaignId) return;
    setSummary(null); setStreet(undefined); setError('');
    loadSummary();
    axios.get(`${API}/api/mentorship/outreach/campaigns/${campaignId}/my-street`, getAuthHeaders()).then((response) => setStreet(response.data.active_street || null))
      .catch((requestError) => { setStreet(null); setError(requestError?.response?.data?.detail || 'No puedes registrar viviendas en esta invasión'); });
    axios.get(`${API}/api/mentorship/outreach/door-books`, getAuthHeaders()).then((response) => setBooks(response.data.items || [])).catch(() => setBooks([]));
  }, [API, getAuthHeaders, campaignId, loadSummary]);

  if (!context) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  if (!campaignId) {
    return (
      <div className="mx-auto max-w-xl space-y-3 p-4" data-testid="door-no-invasion">
        <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">Puerta a puerta</h1>
        <p className="rounded-xl border border-dashed border-slate-300 bg-white p-4 text-base text-slate-600">Hoy no tienes una invasión activa. Para un contacto fuera del puerta a puerta usa «Persona sin vivienda».</p>
        <button type="button" onClick={() => setLooseOpen(true)} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border-2 border-[#132443] bg-white text-base font-semibold text-[#132443]" data-testid="door-loose-person"><UserPlus className="h-5 w-5" />Persona sin vivienda</button>
        <AddVisitDialog open={looseOpen} onOpenChange={setLooseOpen} campaigns={[]} forcedMentorId={user?.person_id} onCreated={() => window.dispatchEvent(new Event(OUTREACH_CHANGED_EVENT))} />
      </div>
    );
  }
  return (
    <div className="mx-auto w-full max-w-5xl space-y-4 p-4 sm:p-6" data-testid="door-page">
      <header className="space-y-2">
        <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-[0.2em] text-[#7A5F22]"><Footprints className="h-4 w-4" />Puerta a puerta</p>
        {active.length > 1
          ? <select value={campaignId} onChange={(event) => setSearchParams({ invasion: event.target.value, vista: view }, { replace: true })} className="h-12 w-full rounded-lg border border-[#D9D4C7] bg-white px-3 text-lg font-semibold text-[#101D36]" data-testid="door-campaign">{active.map((item) => <option key={item.campaign_id} value={item.campaign_id}>{item.name}</option>)}</select>
          : <h1 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">{campaign?.name || 'Invasión'}</h1>}
        {campaign?.day_label && <p className="text-sm text-slate-600">{campaign.day_label}{campaign.location ? ` · ${campaign.location}` : ''}</p>}
      </header>

      <DoorStats campaignId={campaignId} summary={summary} />

      {/* Segmentos que caben en el celular: registrar, pendientes, mapa y reporte. */}
      <div className="grid grid-cols-4 gap-1 rounded-xl bg-[#EEECE6] p-1" role="tablist" data-testid="door-views">
        {VIEWS.map(([key, label, Icon]) => <button key={key} type="button" role="tab" aria-selected={view === key} onClick={() => setView(key)} className={`relative inline-flex min-h-12 min-w-0 items-center justify-center gap-1.5 rounded-lg px-0.5 text-[14px] font-semibold sm:text-[15px] ${view === key ? 'bg-white text-[#101D36] shadow' : 'text-slate-600'}`} data-testid={`door-view-${key}`}><Icon className="h-4 w-4 shrink-0 max-[419px]:hidden" /><span className="truncate">{label}</span>{key === 'pendientes' && summary?.pending_revisit ? <span className="rounded-full bg-[#c2410c] px-1.5 text-xs text-white max-[419px]:absolute max-[419px]:right-0.5 max-[419px]:top-0.5 max-[419px]:text-[10px]">{summary.pending_revisit}</span> : null}</button>)}
      </div>

      {view === 'registrar' && (error
        ? <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-base text-amber-900" data-testid="door-error">{error}</p>
        : street === undefined ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : <>
          <StreetCard campaignId={campaignId} street={street} onChange={setStreet} />
          {street && <DoorForm key={street.street_name} campaignId={campaignId} street={street} books={books} onSaved={() => { loadSummary(); saved(); }} />}
        </>)}
      {view === 'pendientes' && <PendingDoors campaignId={campaignId} books={books} refreshKey={refreshKey} onChanged={() => { loadSummary(); saved(); }} />}
      {view === 'mapa' && <>
        <InvasionHousesMap campaigns={[{ campaign_id: campaignId, name: campaign?.name || 'Invasión' }]} colorBy="door" fixedHeight={480} refreshKey={refreshKey} mentorPersonId={user?.person_id}
          onRegisterVisit={(point) => setRevisit(point)} onChanged={() => { loadSummary(); saved(); }} />
        <RevisitSheet household={revisit} books={books} onClose={() => setRevisit(null)} onSaved={() => { loadSummary(); saved(); }} />
      </>}

      {view === 'reporte' && <DoorReport key={refreshKey} campaignId={campaignId} fileTag={(campaign?.name || 'invasion').replace(/\s+/g, '-')} />}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <button type="button" onClick={() => setLooseOpen(true)} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[#D9D4C7] bg-white px-4 text-[15px] font-semibold text-[#101D36]" data-testid="door-loose-person"><UserPlus className="h-5 w-5" />Persona sin vivienda</button>
        <Link to={`/invasiones/${campaignId}/programa`} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-[#D9D4C7] bg-white px-4 text-[15px] font-semibold text-[#101D36]" data-testid="door-program"><ClipboardList className="h-5 w-5" />Programa de la invasión</Link>
      </div>
      <AddVisitDialog open={looseOpen} onOpenChange={setLooseOpen} campaigns={active} forcedMentorId={user?.person_id} defaultCampaignId={campaignId} invasionDay={campaign?.day || null} invasionLabel={campaign?.day_label || ''}
        onCreated={() => { loadSummary(); window.dispatchEvent(new Event(OUTREACH_CHANGED_EVENT)); }} />
    </div>
  );
}
