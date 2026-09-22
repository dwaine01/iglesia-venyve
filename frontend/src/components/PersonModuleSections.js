import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { BadgeCheck, CalendarDays, Droplets, Loader2, MapPin, Save, UserRound } from 'lucide-react';
import { toast } from 'sonner';

import { MembershipDocumentsSection } from './membership/MembershipDocumentsSection';
import { RegularizeMembershipDialog } from './membership/RegularizeMembershipDialog';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Textarea } from './ui/textarea';

const EMPTY_BAPTISM = { status: 'pending', baptized: false, baptism_date: '', location: '', church_name: '', officiant_name: '', testimony: '', notes: '' };

export const MembershipProfileSection = ({ personId, membership, canManage, canRegularize, photoSrc, onChanged }) => (
  <section className="space-y-5" data-testid="profile-membership-section">
    <div className="rounded-lg border border-[#E8E5DE] bg-white p-5">
      <div className="flex items-start gap-3"><BadgeCheck className="mt-1 h-6 w-6 text-emerald-700" /><div><h2 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">Membresía</h2><p className="text-sm text-slate-500">Estado institucional conectado al mismo Perfil 360.</p></div></div>
      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <div className="border bg-slate-50 p-4"><span className="text-xs uppercase text-slate-500">Estado</span><strong className="mt-1 block" data-testid="profile-membership-status">{membership?.status === 'active' ? 'Activa' : 'Sin membresía activa'}</strong></div>
        <div className="border bg-slate-50 p-4"><span className="text-xs uppercase text-slate-500">Número</span><strong className="mt-1 block text-[#0879BE]" data-testid="profile-membership-number">{membership?.member_number || 'Pendiente'}</strong></div>
        <div className="border bg-slate-50 p-4"><span className="text-xs uppercase text-slate-500">Origen</span><strong className="mt-1 block">{membership?.legacy_membership ? 'Miembro preexistente' : membership ? 'Carta de Membresía' : 'Sin registro'}</strong></div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">{!membership?.status && canRegularize && <RegularizeMembershipDialog personId={personId} onChanged={onChanged} />}{membership?.membership_origin === 'historical_regularization' && <p className="text-sm text-slate-600" data-testid="membership-regularization-details">Regularizada {membership.regularized_at?.slice?.(0,10)} · Fecha histórica {membership.historical_membership_date || 'desconocida'}</p>}</div>
      {!canManage && <p className="mt-4 border-l-4 border-amber-500 bg-amber-50 p-3 text-sm text-amber-900" data-testid="membership-read-only-notice">Consulta de estado disponible. La emisión de documentos requiere autorización de Membresía.</p>}
    </div>
    {canManage && <MembershipDocumentsSection personId={personId} photoSrc={photoSrc} />}
  </section>
);

export const BaptismSection = ({ personId, record, canWrite, API, getAuthHeaders, onChanged }) => {
  const [form, setForm] = useState(() => (record ? { ...EMPTY_BAPTISM, ...record } : EMPTY_BAPTISM));
  const [saving, setSaving] = useState(false);
  useEffect(() => { setForm(record ? { ...EMPTY_BAPTISM, ...record } : EMPTY_BAPTISM); }, [record]);

  const save = async (event) => {
    event.preventDefault(); setSaving(true);
    try {
      await axios.put(`${API}/api/core/persons/${personId}/baptism`, { ...form, baptism_date: form.baptism_date || null }, getAuthHeaders());
      toast.success('Bautismo actualizado en el Perfil 360'); await onChanged();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo actualizar Bautismo'); }
    finally { setSaving(false); }
  };

  return <section className="rounded-lg border border-[#E8E5DE] bg-white p-5" data-testid="profile-baptism-section">
    <div className="flex items-start justify-between gap-3"><div className="flex items-start gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-lg bg-[#F4EBCF] text-[#785E24]"><Droplets className="h-5 w-5" /></div><div><h2 className="font-['Spectral'] text-2xl font-semibold text-[#101D36]">Bautismo</h2><p className="text-sm text-slate-500">Registro verificable de programación o bautismo completado.</p></div></div><Badge variant="outline" data-testid="baptism-status-badge">{form.status === 'completed' ? 'Completado' : form.status === 'scheduled' ? 'Programado' : 'Pendiente'}</Badge></div>
    <form onSubmit={save} className="mt-6 grid gap-4 md:grid-cols-2">
      <div className="space-y-2"><Label>Estado</Label><Select value={form.status} onValueChange={(value) => setForm((old) => ({ ...old, status: value }))} disabled={!canWrite}><SelectTrigger data-testid="baptism-status-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="pending">Pendiente</SelectItem><SelectItem value="scheduled">Programado</SelectItem><SelectItem value="completed">Completado</SelectItem></SelectContent></Select></div>
      <div className="space-y-2"><Label htmlFor="baptism-date"><CalendarDays className="mr-1 inline h-4 w-4" />Fecha</Label><Input id="baptism-date" type="date" value={form.baptism_date || ''} onChange={(event) => setForm((old) => ({ ...old, baptism_date: event.target.value }))} disabled={!canWrite} data-testid="baptism-date-input" /></div>
      <div className="space-y-2"><Label htmlFor="baptism-location"><MapPin className="mr-1 inline h-4 w-4" />Lugar</Label><Input id="baptism-location" value={form.location || ''} onChange={(event) => setForm((old) => ({ ...old, location: event.target.value }))} disabled={!canWrite} data-testid="baptism-location-input" /></div>
      <div className="space-y-2"><Label htmlFor="baptism-church">Iglesia</Label><Input id="baptism-church" value={form.church_name || ''} onChange={(event) => setForm((old) => ({ ...old, church_name: event.target.value }))} disabled={!canWrite} data-testid="baptism-church-input" /></div>
      <div className="space-y-2"><Label htmlFor="baptism-officiant"><UserRound className="mr-1 inline h-4 w-4" />Ministro bautizador</Label><Input id="baptism-officiant" value={form.officiant_name || ''} onChange={(event) => setForm((old) => ({ ...old, officiant_name: event.target.value }))} disabled={!canWrite} data-testid="baptism-officiant-input" /></div>
      <div className="space-y-2 md:col-span-2"><Label htmlFor="baptism-testimony">Testimonio</Label><Textarea id="baptism-testimony" value={form.testimony || ''} onChange={(event) => setForm((old) => ({ ...old, testimony: event.target.value }))} disabled={!canWrite} data-testid="baptism-testimony-input" /></div>
      <div className="space-y-2 md:col-span-2"><Label htmlFor="baptism-notes">Notas</Label><Textarea id="baptism-notes" value={form.notes || ''} onChange={(event) => setForm((old) => ({ ...old, notes: event.target.value }))} disabled={!canWrite} data-testid="baptism-notes-input" /></div>
      {canWrite && <Button type="submit" disabled={saving} className="justify-self-end bg-[#132443] md:col-span-2" data-testid="save-baptism-button">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}Guardar Bautismo</Button>}
    </form>
  </section>;
};