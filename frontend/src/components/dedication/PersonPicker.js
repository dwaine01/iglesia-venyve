/* eslint-disable react-hooks/exhaustive-deps */
import React, { useState } from 'react';
import axios from 'axios';
import { Search, UserPlus, X } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

export const PersonPicker = ({ label, value, onSelect, testId, createFields = ['nombre', 'apellido', 'fecha_nacimiento'] }) => {
  const { API, getAuthHeaders } = useAuth();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState({ nombre: '', apellido: '', fecha_nacimiento: '', telefono: '' });
  const [saving, setSaving] = useState(false);

  const search = async (text) => {
    setQuery(text);
    if (text.trim().length < 2) return setResults([]);
    setSearching(true);
    try {
      const response = await axios.get(`${API}/api/core/persons/directory/search`, { ...getAuthHeaders(), params: { q: text, limit: 6 } });
      setResults(response.data.items || []);
    } catch { setResults([]); }
    finally { setSearching(false); }
  };

  const createPerson = async () => {
    if (!createForm.nombre.trim() || !createForm.apellido.trim()) return toast.error('Nombre y apellido son obligatorios');
    setSaving(true);
    try {
      const response = await axios.post(`${API}/api/core/persons`, { ...createForm, idempotency_key: `${label}-${Date.now()}-${Math.random().toString(36).slice(2)}` }, getAuthHeaders());
      onSelect({ person_id: response.data.person_id, nombre_completo: `${createForm.nombre} ${createForm.apellido}` });
      setCreating(false); setCreateForm({ nombre: '', apellido: '', fecha_nacimiento: '', telefono: '' });
      toast.success('Persona creada y vinculada');
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo crear la Persona'); }
    finally { setSaving(false); }
  };

  if (value) return <div className="flex items-center justify-between gap-2 border bg-white p-2 text-sm" data-testid={`${testId}-selected`}>
    <span><span className="text-xs uppercase text-slate-400">{label}: </span>{value.nombre_completo}</span>
    <Button size="icon" variant="ghost" onClick={() => onSelect(null)} data-testid={`${testId}-clear`}><X className="h-3.5 w-3.5" /></Button>
  </div>;

  return <div className="space-y-2">
    <Label>{label}</Label>
    <div className="relative"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pl-9" value={query} onChange={(event) => search(event.target.value)} placeholder="Buscar persona existente" data-testid={`${testId}-search-input`} /></div>
    {searching && <p className="text-xs text-slate-400">Buscando…</p>}
    {results.length > 0 && <div className="divide-y border" data-testid={`${testId}-search-results`}>
      {results.map((item) => <div key={item.person_id} className="flex items-center justify-between gap-2 p-2 text-sm">
        <span>{item.nombre_completo} {item.person_number && <span className="text-slate-400">· {item.person_number}</span>}</span>
        <Button size="sm" variant="outline" onClick={() => { onSelect(item); setResults([]); setQuery(''); }} data-testid={`${testId}-pick-${item.person_id}`}>Seleccionar</Button>
      </div>)}
    </div>}
    {!creating ? <Button type="button" size="sm" variant="ghost" onClick={() => setCreating(true)} data-testid={`${testId}-create-toggle`}><UserPlus className="h-3.5 w-3.5" />No está registrado(a), crear nuevo perfil</Button> : (
      <div className="grid gap-2 border bg-slate-50 p-3" data-testid={`${testId}-create-form`}>
        <div className="grid gap-2 sm:grid-cols-2">
          <Input placeholder="Nombre" value={createForm.nombre} onChange={(event) => setCreateForm({ ...createForm, nombre: event.target.value })} data-testid={`${testId}-create-nombre`} />
          <Input placeholder="Apellido" value={createForm.apellido} onChange={(event) => setCreateForm({ ...createForm, apellido: event.target.value })} data-testid={`${testId}-create-apellido`} />
        </div>
        {createFields.includes('fecha_nacimiento') && <Input type="date" value={createForm.fecha_nacimiento} onChange={(event) => setCreateForm({ ...createForm, fecha_nacimiento: event.target.value })} data-testid={`${testId}-create-birthdate`} />}
        {createFields.includes('telefono') && <Input placeholder="Teléfono (opcional)" value={createForm.telefono} onChange={(event) => setCreateForm({ ...createForm, telefono: event.target.value })} data-testid={`${testId}-create-phone`} />}
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => setCreating(false)}>Cancelar</Button>
          <Button size="sm" className="bg-[#132443]" disabled={saving} onClick={createPerson} data-testid={`${testId}-create-submit`}>Crear y seleccionar</Button>
        </div>
      </div>
    )}
  </div>;
};
