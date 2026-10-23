import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Loader2, Search, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

// C4: busca en Persona 360 (sin pasar por /api/core/persons) y permite dar de
// alta sin salir del flujo; coincidencia FUERTE bloquea, POSIBLE exige motivo.
export const PersonQuickPicker = ({ groupId, onPicked, role = 'member', placeholder = 'Buscar por nombre…' }) => {
  const { API, getAuthHeaders } = useAuth();
  const [search, setSearch] = useState(''); const [results, setResults] = useState([]); const [searching, setSearching] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ nombre: '', apellido: '', telefono: '', email: '' });
  const [candidates, setCandidates] = useState(null);
  const [confirmDistinct, setConfirmDistinct] = useState(false); const [distinctReason, setDistinctReason] = useState('');
  const [busy, setBusy] = useState(false);
  const idemRef = useRef(`fg-quick-${Date.now()}-${Math.random().toString(36).slice(2)}`);

  useEffect(() => {
    const query = search.trim();
    if (query.length < 2) { setResults([]); return undefined; }
    setSearching(true);
    const handle = setTimeout(() => {
      axios.get(`${API}/api/front-groups/${groupId}/person-search`, { ...getAuthHeaders(), params: { search: query } })
        .then((response) => setResults(response.data.items || []))
        .catch(() => setResults([]))
        .finally(() => setSearching(false));
    }, 300);
    return () => clearTimeout(handle);
  }, [API, getAuthHeaders, groupId, search]);

  const pick = (person) => { onPicked(person); setSearch(''); setResults([]); setShowCreate(false); setCandidates(null); };

  const createPerson = async () => {
    if (form.nombre.trim().length < 1 || form.apellido.trim().length < 1) { toast.error('Nombre y apellido son requeridos'); return; }
    setBusy(true);
    try {
      const response = await axios.post(`${API}/api/front-groups/${groupId}/quick-person`, {
        ...form, role, idempotency_key: idemRef.current,
        confirm_distinct_person: confirmDistinct, distinct_reason: distinctReason || null,
      }, getAuthHeaders());
      toast.success('Persona registrada y agregada');
      pick(response.data.person);
      setForm({ nombre: '', apellido: '', telefono: '', email: '' }); setConfirmDistinct(false); setDistinctReason('');
      idemRef.current = `fg-quick-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    } catch (error) {
      const detail = error.response?.data?.detail;
      if (error.response?.status === 409 && detail?.candidates) {
        setCandidates({ requiresConfirmation: Boolean(detail.requires_confirmation), items: detail.candidates, message: detail.message });
      } else {
        toast.error(apiErrorMessage(error, 'No se pudo registrar la persona'));
      }
    } finally { setBusy(false); }
  };

  return <div className="space-y-2" data-testid="person-quick-picker">
    <div className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={placeholder} className="pl-9" data-testid="person-quick-picker-search-input" /></div>
    {searching && <p className="text-xs text-slate-400">Buscando…</p>}
    {results.length > 0 && <div className="max-h-40 overflow-y-auto border border-slate-200 bg-white" data-testid="person-quick-picker-results">
      {results.map((person) => <button type="button" key={person.person_id} onClick={() => pick(person)} className="block w-full border-b border-slate-100 px-3 py-2 text-left text-sm last:border-0 hover:bg-amber-50" data-testid={`person-quick-picker-result-${person.person_id}`}>{person.nombre} {person.apellido} <span className="text-xs text-slate-400">· {person.person_number}</span></button>)}
    </div>}
    <button type="button" onClick={() => setShowCreate((value) => !value)} className="flex items-center gap-1.5 text-xs font-semibold text-amber-700 hover:underline" data-testid="person-quick-picker-toggle-create">
      <UserPlus className="h-3.5 w-3.5" />{showCreate ? 'Cancelar alta rápida' : 'No está en la lista: registrarla'}
    </button>
    {showCreate && <div className="space-y-2 border border-amber-200 bg-amber-50/50 p-3" data-testid="person-quick-picker-create-form">
      <div className="grid grid-cols-2 gap-2">
        <div><Label className="text-xs">Nombre</Label><Input value={form.nombre} onChange={(event) => setForm({ ...form, nombre: event.target.value })} data-testid="person-quick-picker-nombre-input" /></div>
        <div><Label className="text-xs">Apellido</Label><Input value={form.apellido} onChange={(event) => setForm({ ...form, apellido: event.target.value })} data-testid="person-quick-picker-apellido-input" /></div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div><Label className="text-xs">Teléfono (opcional)</Label><Input value={form.telefono} onChange={(event) => setForm({ ...form, telefono: event.target.value })} data-testid="person-quick-picker-telefono-input" /></div>
        <div><Label className="text-xs">Correo (opcional)</Label><Input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} data-testid="person-quick-picker-email-input" /></div>
      </div>
      {candidates && <div className="space-y-2 border border-red-200 bg-red-50 p-3 text-xs text-red-800" data-testid="person-quick-picker-candidates">
        <p>{candidates.message}</p>
        <div className="space-y-1">{candidates.items.map((item) => <button type="button" key={item.person_id} onClick={() => pick(item)} className="block w-full border border-red-200 bg-white px-2 py-1 text-left hover:bg-red-100" data-testid={`person-quick-picker-candidate-${item.person_id}`}>Usar a {item.nombre} {item.apellido} ({item.person_number})</button>)}</div>
        {candidates.requiresConfirmation && <div className="space-y-1 pt-1">
          <label className="flex items-center gap-2 text-xs text-red-900"><Checkbox checked={confirmDistinct} onCheckedChange={(value) => setConfirmDistinct(Boolean(value))} data-testid="person-quick-picker-confirm-distinct-checkbox" />Es una persona distinta</label>
          {confirmDistinct && <Input value={distinctReason} onChange={(event) => setDistinctReason(event.target.value)} placeholder="Motivo (obligatorio)" data-testid="person-quick-picker-distinct-reason-input" />}
        </div>}
      </div>}
      <Button type="button" onClick={createPerson} disabled={busy || (candidates?.requiresConfirmation && (!confirmDistinct || distinctReason.trim().length < 2))} className="w-full bg-slate-900" data-testid="person-quick-picker-submit-button">
        {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}Registrar y agregar
      </Button>
    </div>}
  </div>;
};
