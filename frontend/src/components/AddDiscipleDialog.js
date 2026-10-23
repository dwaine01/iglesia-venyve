import React, { useState } from 'react';
import axios from 'axios';
import { Loader2, Search, UserPlus } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from './ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Textarea } from './ui/textarea';

export default function AddDiscipleDialog({ open, onOpenChange, mentorPersonId, API, getAuthHeaders, onCreated }) {
  const [contactType, setContactType] = useState('new');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [zone, setZone] = useState('');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [searching, setSearching] = useState(false);
  const [birthDate, setBirthDate] = useState('');
  const [spiritualStatus, setSpiritualStatus] = useState('unspecified');
  const [attendsChurch, setAttendsChurch] = useState('unspecified');
  const [isBackslidden, setIsBackslidden] = useState('unspecified');
  const [note, setNote] = useState('');
  const [saving, setSaving] = useState(false);

  const search = async (value) => {
    setQuery(value);
    setSelectedPerson(null);
    if (value.trim().length < 2) { setResults([]); return; }
    setSearching(true);
    try {
      const response = await axios.get(`${API}/api/mentorship/outreach/person-search?q=${encodeURIComponent(value.trim())}`, getAuthHeaders());
      setResults(response.data.items || []);
    } finally {
      setSearching(false);
    }
  };

  const reset = () => {
    setContactType('new'); setName(''); setPhone(''); setZone('');
    setQuery(''); setResults([]); setSelectedPerson(null);
    setBirthDate(''); setSpiritualStatus('unspecified'); setAttendsChurch('unspecified'); setIsBackslidden('unspecified'); setNote('');
  };

  const triToBool = (value) => (value === 'yes' ? true : value === 'no' ? false : null);

  const submit = async () => {
    if (contactType === 'existing' && !selectedPerson) { toast.error('Seleccione una persona existente'); return; }
    if (contactType === 'new' && !name.trim()) { toast.error('Escriba el nombre del discípulo'); return; }
    setSaving(true);
    try {
      const visit = await axios.post(`${API}/api/mentorship/outreach/visits`, {
        contact_type: contactType,
        person_id: contactType === 'existing' ? selectedPerson.person_id : null,
        contact_name: contactType === 'new' ? name.trim() : null,
        contact_phone: contactType === 'new' ? (phone || null) : null,
        contact_zone: contactType === 'new' ? (zone || null) : null,
        mentor_person_id: mentorPersonId,
      }, getAuthHeaders());
      const visitId = visit.data.visit_id;
      await axios.put(`${API}/api/mentorship/outreach/visits/${visitId}/report`, {
        status: 'wants_followup', contact_birth_date: birthDate || null,
        spiritual_status: spiritualStatus === 'unspecified' ? null : spiritualStatus,
        attends_church: triToBool(attendsChurch), is_backslidden: triToBool(isBackslidden), note: note || null,
      }, getAuthHeaders());
      await axios.post(`${API}/api/mentorship/outreach/visits/${visitId}/start-seven-weeks`, {}, getAuthHeaders());
      toast.success('Discípulo agregado e iniciado en la Ley de las 7 Semanas');
      reset();
      onOpenChange(false);
      if (onCreated) onCreated();
    } catch (error) {
      toast.error(error?.response?.data?.detail || 'No se pudo agregar el discípulo');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(value) => { if (!value) reset(); onOpenChange(value); }}>
      <DialogContent className="bg-white sm:max-w-lg" data-testid="add-disciple-dialog">
        <DialogHeader><DialogTitle>Agregar discípulo</DialogTitle></DialogHeader>
        <div className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
          <div className="flex gap-2">
            <Button type="button" size="sm" variant={contactType === 'new' ? 'default' : 'outline'} onClick={() => setContactType('new')} className={contactType === 'new' ? 'bg-[#132443]' : ''} data-testid="add-disciple-type-new">Persona nueva</Button>
            <Button type="button" size="sm" variant={contactType === 'existing' ? 'default' : 'outline'} onClick={() => setContactType('existing')} className={contactType === 'existing' ? 'bg-[#132443]' : ''} data-testid="add-disciple-type-existing">Ya está en Perfil 360</Button>
          </div>

          {contactType === 'new' ? (
            <div className="space-y-3">
              <div className="space-y-1.5"><Label>Nombre</Label><Input value={name} onChange={(event) => setName(event.target.value)} data-testid="add-disciple-name-input" /></div>
              <div className="space-y-1.5"><Label>Teléfono</Label><Input value={phone} onChange={(event) => setPhone(event.target.value)} data-testid="add-disciple-phone-input" /></div>
              <div className="space-y-1.5"><Label>Dirección / zona</Label><Input value={zone} onChange={(event) => setZone(event.target.value)} data-testid="add-disciple-zone-input" /></div>
            </div>
          ) : (
            <div className="space-y-1.5">
              <Label>Buscar persona</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                <Input className="pl-8" value={query} onChange={(event) => search(event.target.value)} placeholder="Nombre o apellido" data-testid="add-disciple-search-input" />
              </div>
              {searching && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
              {results.length > 0 && (
                <div className="max-h-40 overflow-y-auto rounded-lg border border-slate-200" data-testid="add-disciple-search-results">
                  {results.map((item) => (
                    <button type="button" key={item.person_id} onClick={() => { setSelectedPerson(item); setQuery(item.name); setResults([]); }} className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50" data-testid={`add-disciple-search-result-${item.person_id}`}>
                      {item.name}
                    </button>
                  ))}
                </div>
              )}
              {selectedPerson && <p className="text-xs text-emerald-700" data-testid="add-disciple-selected">Seleccionado: {selectedPerson.name}</p>}
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Fecha de nacimiento</Label>
              <Input type="date" value={birthDate} onChange={(event) => setBirthDate(event.target.value)} data-testid="add-disciple-birthdate-input" />
            </div>
            <div className="space-y-1.5">
              <Label>Estado espiritual</Label>
              <Select value={spiritualStatus} onValueChange={setSpiritualStatus}>
                <SelectTrigger data-testid="add-disciple-spiritual-status-select"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="unspecified">Sin especificar</SelectItem>
                  <SelectItem value="cristiano">Cristiano</SelectItem>
                  <SelectItem value="no_cristiano">No cristiano</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>¿Asiste a una iglesia?</Label>
              <Select value={attendsChurch} onValueChange={setAttendsChurch}>
                <SelectTrigger data-testid="add-disciple-attends-church-select"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="unspecified">Sin especificar</SelectItem>
                  <SelectItem value="yes">Sí, asiste</SelectItem>
                  <SelectItem value="no">No asiste</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>¿Está descarriado?</Label>
              <Select value={isBackslidden} onValueChange={setIsBackslidden}>
                <SelectTrigger data-testid="add-disciple-backslidden-select"><SelectValue /></SelectTrigger>
                <SelectContent className="bg-white">
                  <SelectItem value="unspecified">Sin especificar</SelectItem>
                  <SelectItem value="yes">Sí, descarriado</SelectItem>
                  <SelectItem value="no">No</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Nota</Label>
            <Textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Aceptó iniciar el proceso de consolidación..." data-testid="add-disciple-note-input" />
          </div>

          <Button className="w-full bg-[#132443]" disabled={saving} onClick={submit} data-testid="add-disciple-submit-button">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />} Agregar discípulo e iniciar la Ley de las 7 Semanas
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
