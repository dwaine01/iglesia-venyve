import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, MapPin, Repeat, Route } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { LocationCapture } from '../outreach/LocationCapture';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';

/** «Comenzar calle» / «Cambiar calle»: se escribe una sola vez y queda activa. */
export function StreetCard({ campaignId, street, onChange }) {
  const { API, getAuthHeaders } = useAuth();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [location, setLocation] = useState(null);
  const [saving, setSaving] = useState(false);
  const start = () => { setName(''); setLocation(null); setOpen(true); };
  const save = async () => {
    if (name.trim().length < 2) { toast.error('Escribe el nombre de la calle'); return; }
    setSaving(true);
    try {
      const response = await axios.put(`${API}/api/mentorship/outreach/campaigns/${campaignId}/my-street`, {
        street_name: name.trim(), latitude: location?.latitude ?? null, longitude: location?.longitude ?? null,
        location_accuracy_m: location?.accuracy_m ?? null, location_source: location ? 'gps' : null,
      }, getAuthHeaders());
      onChange(response.data.active_street); setOpen(false); toast.success(`Calle activa: ${response.data.active_street.street_name}`, { id: 'door-saved', duration: 2500 });
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo guardar la calle')); } finally { setSaving(false); }
  };
  return (
    <>
      {street
        ? <div className="flex items-center justify-between gap-3 rounded-2xl border-2 border-[#132443] bg-[#F4F6FA] p-3" data-testid="door-street-active">
            <div className="min-w-0"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Calle activa</p><p className="flex items-center gap-1 truncate text-lg font-semibold text-[#101D36]"><Route className="h-5 w-5 shrink-0" />{street.street_name}</p>{street.latitude == null && <p className="text-xs text-slate-500">Sin ubicación confirmada</p>}</div>
            <button type="button" onClick={start} className="inline-flex min-h-12 shrink-0 items-center gap-1.5 rounded-xl border border-[#132443] bg-white px-3 text-[15px] font-semibold text-[#132443]" data-testid="door-street-change"><Repeat className="h-4 w-4" />Cambiar calle</button>
          </div>
        : <button type="button" onClick={start} className="inline-flex min-h-16 w-full items-center justify-center gap-2 rounded-2xl bg-[#132443] px-4 text-lg font-semibold text-white shadow" data-testid="door-street-start"><MapPin className="h-6 w-6" />Comenzar calle</button>}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-white sm:max-w-md" data-testid="door-street-dialog">
          <DialogHeader><DialogTitle>{street ? 'Cambiar calle' : 'Comenzar calle'}</DialogTitle><DialogDescription>Escríbela una sola vez; después solo pones el número de cada casa.</DialogDescription></DialogHeader>
          <label className="block"><span className="text-sm font-semibold text-slate-700">Nombre de la calle</span><input value={name} onChange={(event) => setName(event.target.value)} autoFocus placeholder="Ej.: W 18th St" className="mt-1 h-12 w-full rounded-lg border border-[#D9D4C7] px-3 text-base" data-testid="door-street-name" /></label>
          <div><p className="mb-1 text-sm font-semibold text-slate-700">Confirma la ubicación (recomendado)</p><LocationCapture value={location} onChange={setLocation} testId="door-street-location" /></div>
          <button type="button" onClick={save} disabled={saving} className="inline-flex min-h-14 w-full items-center justify-center gap-2 rounded-xl bg-[#132443] text-base font-semibold text-white disabled:opacity-60" data-testid="door-street-save">{saving ? <Loader2 className="h-5 w-5 animate-spin" /> : <Route className="h-5 w-5" />}{street ? 'Cambiar a esta calle' : 'Comenzar esta calle'}</button>
        </DialogContent>
      </Dialog>
    </>
  );
}
