import React, { useState } from 'react';
import axios from 'axios';
import { CheckCircle2, Eye, ListOrdered, Loader2, MapPin, Repeat, RotateCcw, Route } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { LocationCapture } from '../outreach/LocationCapture';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { HouseList } from './DoorReport';

const hour = (iso) => (iso ? new Date(iso).toLocaleTimeString('es', { hour: 'numeric', minute: '2-digit' }) : '');
const day = (iso) => (iso ? new Date(iso).toLocaleDateString('es', { day: 'numeric', month: 'short' }) : '');
const duration = (minutes) => (minutes == null ? '' : minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`);
const REASON = { finished: 'Terminada', changed: 'Cerrada al cambiar de calle', auto: 'Cerrada sola al terminar la jornada' };

/** Lista «Mis calles»: estado, viviendas, inicio/fin; reabrir o ver sus viviendas. */
function StreetList({ streets, busy, onReopen, onView }) {
  if (!streets?.length) return null;
  const today = streets.filter((row) => row.today || row.status === 'active');
  const earlier = streets.filter((row) => !row.today && row.status !== 'active');
  const item = (row) => (
    <li key={row.street_key} className="rounded-xl border border-[#E8E5DE] bg-white p-3" data-testid={`door-street-row-${row.street_key}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-base font-semibold text-[#101D36]">{row.street_name}</p>
          <p className="text-sm text-slate-600">{row.houses} vivienda(s) · {row.opened} abrieron · {row.books} libro(s)</p>
          <p className="text-xs text-slate-500">{row.today ? '' : `${day(row.started_at)} · `}{hour(row.started_at)}{row.ended_at ? ` – ${hour(row.ended_at)}` : ' – ahora'}{row.duration_minutes != null ? ` · ${duration(row.duration_minutes)}` : ''}</p>
        </div>
        <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${row.status === 'active' ? 'border-[#bcd8c4] bg-[#eef5f0] text-[#2f6e47]' : 'border-slate-200 bg-slate-50 text-slate-600'}`} title={REASON[row.end_reason] || ''} data-testid="door-street-row-status">{row.status === 'active' ? 'Activa' : 'Terminada'}</span>
      </div>
      {row.end_reason === 'auto' && <p className="mt-1 text-xs text-amber-800">{REASON.auto}</p>}
      <div className="mt-2 grid grid-cols-2 gap-2">
        <button type="button" onClick={() => onView(row)} disabled={!row.houses} className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg border border-[#D9D4C7] bg-white text-[15px] font-semibold text-[#101D36] disabled:opacity-50" data-testid="door-street-row-view"><Eye className="h-4 w-4" />Ver viviendas</button>
        {row.status !== 'active' && <button type="button" onClick={() => onReopen(row)} disabled={busy} className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg border border-[#132443] bg-white text-[15px] font-semibold text-[#132443] disabled:opacity-60" data-testid="door-street-row-reopen"><RotateCcw className="h-4 w-4" />Reabrir</button>}
      </div>
    </li>
  );
  return (
    <div className="space-y-3" data-testid="door-street-list">
      {today.length > 0 && <div><p className="mb-1 text-sm font-semibold text-slate-700">Mis calles de hoy</p><ul className="space-y-2">{today.map(item)}</ul></div>}
      {earlier.length > 0 && <div><p className="mb-1 text-sm font-semibold text-slate-700">Calles de días anteriores</p><ul className="space-y-2">{earlier.map(item)}</ul></div>}
    </div>
  );
}

/** «Comenzar calle» / «Cambiar calle» / «Terminar calle»: una sola calle
 * activa; las terminadas quedan en «Mis calles» para reabrirlas. */
export function StreetCard({ campaignId, street, streets = [], onChange }) {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [location, setLocation] = useState(null);
  const [saving, setSaving] = useState(false);
  const [finishing, setFinishing] = useState(null); // resumen de la calle a terminar
  const [listOpen, setListOpen] = useState(false);
  const [viewing, setViewing] = useState(null);
  const base = `${API}/api/mentorship/outreach/campaigns/${campaignId}/my-street`;
  const start = () => { setName(''); setLocation(null); setOpen(true); };
  const save = async () => {
    if (name.trim().length < 2) { toast.error('Escribe el nombre de la calle'); return; }
    setSaving(true);
    try {
      const response = await axios.put(base, {
        street_name: name.trim(), latitude: location?.latitude ?? null, longitude: location?.longitude ?? null,
        location_accuracy_m: location?.accuracy_m ?? null, location_source: location ? 'gps' : null,
      }, getAuthHeaders());
      onChange(response.data); setOpen(false); // la tarjeta «Calle activa» confirma
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar la calle')); } finally { setSaving(false); }
  };
  const askFinish = async () => {
    setFinishing({ loading: true });
    try {
      // Cifras frescas de la calle (las viviendas recién guardadas incluidas).
      const response = await axios.get(base, getAuthHeaders());
      onChange(response.data);
      if (!response.data.active_street) { setFinishing(null); return; }
      setFinishing(response.data.streets.find((row) => row.street_key === response.data.active_street.street_key) || { houses: 0, visited: 0, opened: 0, books: 0 });
    } catch (error) { setFinishing(null); toast.error(apiErrorMessage(error, 'No se pudo cargar la calle')); }
  };
  const finish = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const response = await axios.post(`${base}/finish`, { street_session_id: street?.street_session_id }, getAuthHeaders());
      onChange(response.data); setFinishing(null);
      toast.success(`Calle «${response.data.finished?.street_name || street?.street_name}» terminada`);
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo terminar la calle')); } finally { setSaving(false); }
  };
  const reopen = async (row) => {
    if (saving) return;
    setSaving(true);
    try {
      const response = await axios.post(`${base}/reopen`, { street_key: row.street_key }, getAuthHeaders());
      onChange(response.data); setListOpen(false);
      toast.success(`Calle «${row.street_name}» reabierta`);
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo reabrir la calle')); } finally { setSaving(false); }
  };
  const view = (row) => setViewing({ metric: 'houses_visited', filter: { street_key: row.street_key }, title: `Viviendas · ${row.street_name}` });
  const others = streets.filter((row) => row.status !== 'active');

  return (
    <>
      {street
        ? <div className="space-y-2 rounded-2xl border-2 border-[#132443] bg-[#F4F6FA] p-3" data-testid="door-street-active">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Calle activa{street.started_at ? ` · desde ${hour(street.started_at)}` : ''}</p>
                <p className="flex items-center gap-1 truncate text-lg font-semibold text-[#101D36]"><Route className="h-5 w-5 shrink-0" />{street.street_name}</p>
                {street.latitude == null && <p className="text-xs text-slate-500">Sin ubicación confirmada</p>}
              </div>
              {streets.length > 0 && <button type="button" onClick={() => setListOpen(true)} className="inline-flex min-h-11 shrink-0 items-center gap-1 rounded-lg px-2 text-sm font-semibold text-[#132443] underline" data-testid="door-street-list-open"><ListOrdered className="h-4 w-4" />Mis calles</button>}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button type="button" onClick={start} className="inline-flex min-h-12 items-center justify-center gap-1.5 rounded-xl border border-[#132443] bg-white px-2 text-[15px] font-semibold text-[#132443]" data-testid="door-street-change"><Repeat className="h-4 w-4" />Cambiar calle</button>
              <button type="button" onClick={askFinish} className="inline-flex min-h-12 items-center justify-center gap-1.5 rounded-xl bg-[#132443] px-2 text-[15px] font-semibold text-white" data-testid="door-street-finish"><CheckCircle2 className="h-4 w-4" />Terminar calle</button>
            </div>
          </div>
        : <div className="space-y-3">
            <button type="button" onClick={start} className="inline-flex min-h-16 w-full items-center justify-center gap-2 rounded-2xl bg-[#132443] px-4 text-lg font-semibold text-white shadow" data-testid="door-street-start"><MapPin className="h-6 w-6" />Comenzar calle</button>
            {others.length > 0 && <p className="text-center text-sm text-slate-600">o reabre una de tus calles para agregar más viviendas:</p>}
            <StreetList streets={streets} busy={saving} onReopen={reopen} onView={view} />
          </div>}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-white sm:max-w-md" data-testid="door-street-dialog">
          <DialogHeader><DialogTitle>{street ? 'Cambiar calle' : 'Comenzar calle'}</DialogTitle><DialogDescription>{street ? `«${street.street_name}» se termina automáticamente y queda en «Mis calles».` : 'Escríbela una sola vez; después solo pones el número de cada casa.'}</DialogDescription></DialogHeader>
          <label className="block"><span className="text-sm font-semibold text-slate-700">Nombre de la calle</span><input value={name} onChange={(event) => setName(event.target.value)} enterKeyHint="done" autoComplete="off" placeholder="Ej.: W 18th St" className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="door-street-name" /></label>
          <div><p className="mb-1 text-sm font-semibold text-slate-700">Confirma la ubicación (recomendado)</p><LocationCapture value={location} onChange={setLocation} testId="door-street-location" /></div>
          <div className="sticky-actions"><button type="button" onClick={save} disabled={saving} className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-60" data-testid="door-street-save">{saving ? <Loader2 className="h-5 w-5 animate-spin" /> : <Route className="h-5 w-5" />}{street ? 'Cambiar a esta calle' : 'Comenzar esta calle'}</button></div>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(finishing)} onOpenChange={(value) => { if (!value) setFinishing(null); }}>
        <DialogContent className="bg-white sm:max-w-md" data-testid="door-street-finish-dialog">
          <DialogHeader><DialogTitle>¿Terminar «{street?.street_name}»?</DialogTitle><DialogDescription>Sus viviendas quedan guardadas; puedes reabrirla desde «Mis calles».</DialogDescription></DialogHeader>
          {finishing?.loading ? <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-400" /> : finishing && (
            <div className="grid grid-cols-3 gap-2" data-testid="door-street-finish-summary">
              {[['visited', 'Viviendas visitadas'], ['opened', 'Abrieron'], ['books', 'Libros']].map(([key, label]) => (
                <div key={key} className="rounded-xl border border-[#EEECE6] bg-[#FBFAF7] p-3 text-center"><p className="text-2xl font-semibold text-[#101D36]" data-testid={`door-street-finish-${key}`}>{finishing[key] || 0}</p><p className="text-xs leading-4 text-slate-600">{label}</p></div>
              ))}
            </div>
          )}
          <div className="sticky-actions grid grid-cols-1 gap-2 sm:grid-cols-2">
            <button type="button" onClick={finish} disabled={saving || finishing?.loading} className="inline-flex min-h-14 items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-60" data-testid="door-street-finish-confirm">{saving ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckCircle2 className="h-5 w-5" />}Sí, terminar calle</button>
            <button type="button" onClick={() => setFinishing(null)} className="inline-flex min-h-12 items-center justify-center rounded-xl border border-[#D9D4C7] bg-white text-base font-semibold text-[#101D36]">Seguir en esta calle</button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={listOpen} onOpenChange={setListOpen}>
        <DialogContent className="bg-white sm:max-w-md" data-testid="door-street-list-dialog">
          <DialogHeader><DialogTitle>Mis calles</DialogTitle><DialogDescription>Reabrir otra calle termina la activa automáticamente.</DialogDescription></DialogHeader>
          <StreetList streets={streets} busy={saving} onReopen={reopen} onView={(row) => { setListOpen(false); view(row); }} />
        </DialogContent>
      </Dialog>
      <HouseList campaignId={campaignId} open={viewing} onClose={() => setViewing(null)} />
    </>
  );
}
