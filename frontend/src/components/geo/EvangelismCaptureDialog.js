import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Home, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { isPastoralAuthority } from '../../lib/accessControl';

const emptyForm = { house_number: '', street_name: '', address2: '', city: 'Columbus', state: 'OH', zip: '', language: 'unknown', notes: '', pastoral_notes: '', assigned_to_user_id: '' };

export const EvangelismCaptureDialog = ({ open, onOpenChange, onCreated }) => {
  const { API, getAuthHeaders, user } = useAuth(); const [form, setForm] = useState(emptyForm); const canUsePastoralNotes = isPastoralAuthority(user);
  const [assignees, setAssignees] = useState([]); const [saving, setSaving] = useState(false); const [error, setError] = useState('');
  useEffect(() => { if (!open) return; axios.get(`${API}/api/geo/evangelism/assignees`, getAuthHeaders()).then((response) => setAssignees(response.data.items || [])).catch(() => setAssignees([])); }, [API, getAuthHeaders, open]);
  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }));
  const submit = async (event) => {
    event.preventDefault(); setSaving(true); setError('');
    try { const response = await axios.post(`${API}/api/geo/evangelism`, { ...form, address2: form.address2 || null, zip: form.zip || null, notes: form.notes || null, pastoral_notes: canUsePastoralNotes && form.pastoral_notes ? form.pastoral_notes : null, assigned_to_user_id: form.assigned_to_user_id || null }, getAuthHeaders()); toast.success(response.data.geocoding_status === 'matched' ? 'Casa registrada y ubicada en el mapa' : 'Casa registrada; ubicación pendiente de verificación'); setForm(emptyForm); onOpenChange(false); onCreated?.(response.data); }
    catch (requestError) { setError(apiErrorMessage(requestError, 'No se pudo registrar la casa')); }
    finally { setSaving(false); }
  };
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto bg-white" data-testid="evangelism-capture-dialog"><DialogHeader><DialogTitle className="flex items-center gap-2 font-['Spectral'] text-2xl"><Home className="h-5 w-5 text-emerald-700" />Registrar casa por visitar</DialogTitle><DialogDescription>Registre la dirección operativa y asigne la primera visita. Las notas pastorales tienen acceso restringido.</DialogDescription></DialogHeader><form onSubmit={submit} className="space-y-5" data-testid="evangelism-capture-form">
    {error && <div className="border border-red-300 bg-red-50 p-3 text-sm text-red-800" data-testid="evangelism-capture-error">{error}</div>}
    <div className="grid grid-cols-[110px_1fr] gap-3"><div><Label htmlFor="ev-house-number">Número *</Label><Input id="ev-house-number" required value={form.house_number} onChange={update('house_number')} placeholder="123" data-testid="evangelism-house-number-input" /></div><div><Label htmlFor="ev-street">Calle *</Label><Input id="ev-street" required value={form.street_name} onChange={update('street_name')} placeholder="Demorest Rd" data-testid="evangelism-street-input" /></div></div>
    <div className="grid gap-3 sm:grid-cols-3"><div><Label htmlFor="ev-unit">Unidad</Label><Input id="ev-unit" value={form.address2} onChange={update('address2')} placeholder="Apt 2" data-testid="evangelism-unit-input" /></div><div><Label htmlFor="ev-city">Ciudad</Label><Input id="ev-city" required value={form.city} onChange={update('city')} data-testid="evangelism-city-input" /></div><div className="grid grid-cols-2 gap-2"><div><Label htmlFor="ev-state">Estado</Label><Input id="ev-state" required value={form.state} onChange={update('state')} data-testid="evangelism-state-input" /></div><div><Label htmlFor="ev-zip">ZIP</Label><Input id="ev-zip" value={form.zip} onChange={update('zip')} data-testid="evangelism-zip-input" /></div></div></div>
    <div className="grid gap-3 sm:grid-cols-2"><div><Label htmlFor="ev-language">Idioma aparente</Label><select id="ev-language" value={form.language} onChange={update('language')} className="h-10 w-full border bg-white px-3 text-sm" data-testid="evangelism-language-select"><option value="unknown">No identificado</option><option value="spanish">Español</option><option value="english">Inglés</option><option value="bilingual">Bilingüe</option><option value="other">Otro</option></select></div><div><Label htmlFor="ev-assignee">Asignar visita</Label><select id="ev-assignee" value={form.assigned_to_user_id} onChange={update('assigned_to_user_id')} className="h-10 w-full border bg-white px-3 text-sm" data-testid="evangelism-assignee-select"><option value="">Sin asignar</option>{assignees.map((item) => <option key={item.user_id} value={item.user_id}>{item.name}</option>)}</select></div></div>
    <div><Label htmlFor="ev-notes">Notas no sensibles</Label><Textarea id="ev-notes" value={form.notes} onChange={update('notes')} rows={3} placeholder="Referencia visual o mejor horario observado" data-testid="evangelism-notes-input" /></div>
    {canUsePastoralNotes && <div><Label htmlFor="ev-pastoral-notes">Notas pastorales restringidas</Label><Textarea id="ev-pastoral-notes" value={form.pastoral_notes} onChange={update('pastoral_notes')} rows={3} placeholder="Visible únicamente para autoridad pastoral" data-testid="evangelism-pastoral-notes-input" /></div>}
    <div className="flex justify-end gap-2 border-t pt-4"><Button type="button" variant="outline" onClick={() => onOpenChange(false)} data-testid="evangelism-capture-cancel-button">Cancelar</Button><Button type="submit" disabled={saving} className="bg-emerald-700 hover:bg-emerald-800" data-testid="evangelism-capture-submit-button">{saving && <Loader2 className="h-4 w-4 animate-spin" />}Registrar casa</Button></div>
  </form></DialogContent></Dialog>;
};