import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Plus, Search, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { errorDetailText } from '../../lib/errorText';

const RESULTS = [
  ['no_answer', 'Sin respuesta'],
  ['not_home', 'No está en casa'],
  ['refused', 'Rechazó'],
  ['contacted', 'Contacto logrado'],
];

const emptyPerson = () => ({ contactType: 'new', name: '', phone: '', query: '', results: [], selected: null, searching: false });

export const LogVisitAttemptDialog = ({ household, open, onOpenChange, onLogged }) => {
  const { API, getAuthHeaders } = useAuth();
  const [result, setResult] = useState('no_answer');
  const [note, setNote] = useState('');
  const [isDraft, setIsDraft] = useState(false);
  const [persons, setPersons] = useState([emptyPerson()]);
  const [saving, setSaving] = useState(false);

  const reset = () => { setResult('no_answer'); setNote(''); setIsDraft(false); setPersons([emptyPerson()]); };

  const updatePerson = (index, patch) => setPersons((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  const searchPerson = async (index, value) => {
    updatePerson(index, { query: value, selected: null });
    if (value.trim().length < 2) { updatePerson(index, { results: [] }); return; }
    updatePerson(index, { searching: true });
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/person-search?q=${encodeURIComponent(value.trim())}`, getAuthHeaders());
      updatePerson(index, { results: response.data.items || [] });
    } finally {
      updatePerson(index, { searching: false });
    }
  };

  const submit = async () => {
    const payloadPersons = result === 'contacted' ? persons
      .filter((item) => (item.contactType === 'new' && item.name.trim()) || (item.contactType === 'existing' && item.selected))
      .map((item) => (item.contactType === 'existing'
        ? { contact_type: 'existing', person_id: item.selected.person_id, contact_phone: item.phone || null }
        : { contact_type: 'new', contact_name: item.name.trim(), contact_phone: item.phone || null })) : [];
    if (result === 'contacted' && payloadPersons.length === 0 && !isDraft) {
      toast.error('Registre al menos un contacto, o guarde este intento como borrador');
      return;
    }
    setSaving(true);
    try {
      await axios.post(`${API}/api/mentorship/outreach/households/${household.household_id}/events`, {
        result, note: note || null, is_draft: isDraft, persons: payloadPersons,
      }, getAuthHeaders());
      toast.success('Intento registrado');
      reset();
      onOpenChange(false);
      if (onLogged) onLogged();
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo registrar el intento'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => { if (!value) reset(); onOpenChange(value); }}>
      <DialogContent className="max-h-[85vh] overflow-y-auto bg-white sm:max-w-lg" data-testid="outreach-log-attempt-dialog">
        <DialogHeader><DialogTitle>Registrar intento de visita</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Resultado del intento</Label>
            <Select value={result} onValueChange={setResult}>
              <SelectTrigger data-testid="outreach-attempt-result-select"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-white">
                {RESULTS.map(([key, label]) => <SelectItem key={key} value={key}>{label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {result === 'contacted' && (
            <div className="space-y-3" data-testid="outreach-attempt-persons">
              <Label>Personas contactadas</Label>
              {persons.map((person, index) => (
                <div key={index} className="space-y-2 rounded-md border border-[#E8E5DE] p-2">
                  <div className="flex items-center justify-between">
                    <div className="flex gap-2">
                      <Button type="button" size="sm" variant={person.contactType === 'new' ? 'default' : 'outline'} className={person.contactType === 'new' ? 'bg-[#132443]' : ''} onClick={() => updatePerson(index, { contactType: 'new' })} data-testid={`outreach-attempt-person-new-${index}`}>Contacto nuevo</Button>
                      <Button type="button" size="sm" variant={person.contactType === 'existing' ? 'default' : 'outline'} className={person.contactType === 'existing' ? 'bg-[#132443]' : ''} onClick={() => updatePerson(index, { contactType: 'existing' })} data-testid={`outreach-attempt-person-existing-${index}`}>Persona existente</Button>
                    </div>
                    {persons.length > 1 && (
                      <button type="button" onClick={() => setPersons((prev) => prev.filter((_, i) => i !== index))} data-testid={`outreach-attempt-person-remove-${index}`}>
                        <Trash2 className="h-4 w-4 text-slate-400" />
                      </button>
                    )}
                  </div>
                  {person.contactType === 'new' ? (
                    <div className="grid gap-2 sm:grid-cols-2">
                      <Input placeholder="Nombre" value={person.name} onChange={(event) => updatePerson(index, { name: event.target.value })} data-testid={`outreach-attempt-person-name-${index}`} />
                      <Input placeholder="Teléfono (opcional)" value={person.phone} onChange={(event) => updatePerson(index, { phone: event.target.value })} data-testid={`outreach-attempt-person-phone-${index}`} />
                    </div>
                  ) : (
                    <div className="space-y-1">
                      <div className="relative">
                        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                        <Input className="pl-8" value={person.query} onChange={(event) => searchPerson(index, event.target.value)} placeholder="Nombre o apellido" data-testid={`outreach-attempt-person-search-${index}`} />
                      </div>
                      {person.searching && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
                      {person.results.length > 0 && (
                        <div className="max-h-32 overflow-y-auto rounded-lg border border-slate-200">
                          {person.results.map((item) => (
                            <button type="button" key={item.person_id} onClick={() => updatePerson(index, { selected: item, query: item.name, results: [] })} className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50" data-testid={`outreach-attempt-person-result-${index}-${item.person_id}`}>
                              {item.name}
                            </button>
                          ))}
                        </div>
                      )}
                      {person.selected && <p className="text-xs text-emerald-700">Seleccionado: {person.selected.name}</p>}
                      {person.selected && <Input placeholder="Teléfono de la persona (el que tiene registrado)" inputMode="tel" value={person.phone} onChange={(event) => updatePerson(index, { phone: event.target.value })} data-testid={`outreach-attempt-existing-phone-${index}`} />}
                    </div>
                  )}
                </div>
              ))}
              <Button type="button" size="sm" variant="outline" onClick={() => setPersons((prev) => [...prev, emptyPerson()])} data-testid="outreach-attempt-add-person">
                <Plus className="h-4 w-4" /> Agregar otra persona
              </Button>
            </div>
          )}

          <label className="flex min-h-11 items-center gap-3 rounded-lg border border-slate-200 px-3 py-2 text-sm" data-testid="outreach-attempt-draft-checkbox">
            <Checkbox checked={isDraft} onCheckedChange={(value) => setIsDraft(Boolean(value))} className="h-6 w-6" />
            Guardar como borrador (sigo registrando)
          </label>

          <div className="space-y-1.5"><Label>Nota (opcional)</Label><Textarea value={note} onChange={(event) => setNote(event.target.value)} data-testid="outreach-attempt-note-input" /></div>

          <Button className="w-full bg-[#132443]" disabled={saving} onClick={submit} data-testid="outreach-attempt-submit">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Registrar intento'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
