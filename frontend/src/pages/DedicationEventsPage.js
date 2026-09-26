/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Baby, CalendarPlus, Loader2, ShieldCheck, Trash2, UserPlus2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Textarea } from '../components/ui/textarea';
import { PersonPicker } from '../components/dedication/PersonPicker';
import { DedicationDocumentDialog } from '../components/dedication/DedicationDocumentDialog';

const EMPTY_EVENT = { name: '', event_date: '', location: '', officiant_name: '', capacity: '', notes: '' };
const EMPTY_CANDIDATE = { child: null, mother: null, father: null, presented_by: '', witnesses: '', dedication_verse: '' };
const EMPTY_STANDALONE = { ...EMPTY_CANDIDATE, dedication_date: '', location: '', officiant_name: '', status: 'completed' };
const statusLabel = { scheduled: 'Programado', completed: 'Completado', cancelled: 'Cancelado' };
const candidateStatusLabel = { pending: 'Pendiente', scheduled: 'Programado', completed: 'Completado' };

export default function DedicationEventsPage() {
  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_EVENT);
  const [saving, setSaving] = useState(false);
  const [activeEvent, setActiveEvent] = useState(null);
  const [roster, setRoster] = useState([]);
  const [candidate, setCandidate] = useState(EMPTY_CANDIDATE);
  const [signatureSrc, setSignatureSrc] = useState(null);
  const [preview, setPreview] = useState({ open: false, data: null });
  const [standaloneOpen, setStandaloneOpen] = useState(false);
  const [standalone, setStandalone] = useState(EMPTY_STANDALONE);
  const [standaloneSaving, setStandaloneSaving] = useState(false);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/api/dedications/events`, getAuthHeaders());
      setEvents(response.data.items || []);
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudieron cargar los eventos de presentación'); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadEvents(); }, [API]);
  useEffect(() => {
    let objectUrl = null;
    axios.get(`${API}/api/membership/settings/signature`, { ...getAuthHeaders(), responseType: 'blob' })
      .then((response) => { objectUrl = URL.createObjectURL(response.data); setSignatureSrc(objectUrl); })
      .catch(() => setSignatureSrc(null));
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [API]);

  const createEvent = async () => {
    if (!form.name.trim() || !form.event_date) return toast.error('Nombre y fecha del evento son obligatorios');
    setSaving(true);
    try {
      await axios.post(`${API}/api/dedications/events`, { ...form, capacity: form.capacity ? Number(form.capacity) : null }, getAuthHeaders());
      toast.success('Evento de presentación creado'); setCreateOpen(false); setForm(EMPTY_EVENT); await loadEvents();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo crear el evento'); }
    finally { setSaving(false); }
  };

  const openEvent = async (eventId) => {
    try {
      const response = await axios.get(`${API}/api/dedications/events/${eventId}`, getAuthHeaders());
      setActiveEvent(response.data.event); setRoster(response.data.roster || []); setCandidate(EMPTY_CANDIDATE);
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo abrir el evento'); }
  };

  const addCandidate = async () => {
    if (!candidate.child) return toast.error('Selecciona o crea al niño/a');
    try {
      const response = await axios.post(`${API}/api/dedications/events/${activeEvent.event_id}/candidates`, {
        child_person_id: candidate.child.person_id,
        mother_person_id: candidate.mother?.person_id || null,
        father_person_id: candidate.father?.person_id || null,
        presented_by: candidate.presented_by || null,
        witnesses: candidate.witnesses ? candidate.witnesses.split(',').map((item) => item.trim()).filter(Boolean) : [],
        dedication_verse: candidate.dedication_verse || null,
      }, getAuthHeaders());
      setRoster(response.data.roster || []); setCandidate(EMPTY_CANDIDATE);
      toast.success('Niño/a agregado(a) al listado'); await loadEvents();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo agregar al listado'); }
  };

  const removeCandidate = async (childPersonId) => {
    try {
      const response = await axios.delete(`${API}/api/dedications/events/${activeEvent.event_id}/candidates/${childPersonId}`, getAuthHeaders());
      setRoster(response.data.roster || []); toast.success('Removido del evento'); await loadEvents();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo quitar'); }
  };

  const completeCandidate = async (childPersonId) => {
    try {
      const response = await axios.post(`${API}/api/dedications/events/${activeEvent.event_id}/candidates/${childPersonId}/complete`, {}, getAuthHeaders());
      setRoster(response.data.roster || []);
      toast.success('Presentación marcada como completada'); await loadEvents();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo completar el registro'); }
  };

  const issueCertificate = async (childPersonId) => {
    try {
      const response = await axios.post(`${API}/api/dedications/children/${childPersonId}/certificate/issue`, {}, getAuthHeaders());
      setPreview({ open: true, data: response.data.data });
      toast.success(response.data.action === 'issued' ? 'Certificado emitido' : 'Reimpresión registrada');
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo emitir el certificado'); }
  };

  const submitStandalone = async () => {
    if (!standalone.child) return toast.error('Selecciona o crea al niño/a');
    if (!standalone.dedication_date) return toast.error('La fecha de presentación es obligatoria');
    setStandaloneSaving(true);
    try {
      const response = await axios.post(`${API}/api/dedications/children`, {
        child_person_id: standalone.child.person_id,
        mother_person_id: standalone.mother?.person_id || null,
        father_person_id: standalone.father?.person_id || null,
        presented_by: standalone.presented_by || null,
        witnesses: standalone.witnesses ? standalone.witnesses.split(',').map((item) => item.trim()).filter(Boolean) : [],
        dedication_verse: standalone.dedication_verse || null,
        dedication_date: standalone.dedication_date,
        location: standalone.location || null,
        officiant_name: standalone.officiant_name || null,
        status: standalone.status,
      }, getAuthHeaders());
      toast.success('Presentación individual registrada'); setStandaloneOpen(false); setStandalone(EMPTY_STANDALONE);
      if (standalone.status === 'completed') setPreview({ open: false, data: response.data.data });
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo registrar la presentación'); }
    finally { setStandaloneSaving(false); }
  };

  return <main className="min-h-screen bg-[#FDFBF7] px-4 py-6 sm:px-6 lg:px-8" data-testid="dedication-events-page"><div className="mx-auto max-w-6xl space-y-6">
    <button type="button" onClick={() => navigate(-1)} className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-950" data-testid="dedication-events-back-button"><ArrowLeft className="h-4 w-4" />Volver</button>
    <header className="flex flex-wrap items-start justify-between gap-4 border-l-4 border-[#0798C8] bg-white p-5 shadow-sm">
      <div><p className="flex items-center gap-2 text-xs font-bold uppercase text-[#0798C8]"><Baby className="h-4 w-4" />Presentación de Niños</p><h1 className="mt-2 font-['Spectral'] text-3xl font-semibold text-slate-950 sm:text-4xl">Presentaciones de niños</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Organiza servicios de dedicación infantil con lista de niños, o registra una presentación individual. Vincula a los padres (existentes o nuevos) y emite el certificado oficial.</p></div>
      <div className="flex flex-wrap gap-2">
        <Dialog open={standaloneOpen} onOpenChange={setStandaloneOpen}>
          <DialogTrigger asChild><Button variant="outline" data-testid="new-standalone-dedication-button"><UserPlus2 className="h-4 w-4" />Presentación individual</Button></DialogTrigger>
          <DialogContent className="max-h-[90vh] overflow-y-auto" data-testid="standalone-dedication-dialog">
            <DialogHeader><DialogTitle>Registrar presentación individual</DialogTitle><DialogDescription>Sin necesidad de agrupar por evento.</DialogDescription></DialogHeader>
            <div className="grid gap-3">
              <PersonPicker label="Niño/a" value={standalone.child} onSelect={(value) => setStandalone({ ...standalone, child: value })} testId="standalone-child-picker" />
              <PersonPicker label="Madre" value={standalone.mother} onSelect={(value) => setStandalone({ ...standalone, mother: value })} testId="standalone-mother-picker" createFields={['telefono']} />
              <PersonPicker label="Padre" value={standalone.father} onSelect={(value) => setStandalone({ ...standalone, father: value })} testId="standalone-father-picker" createFields={['telefono']} />
              <div className="grid gap-3 sm:grid-cols-2">
                <div><Label>Fecha de presentación</Label><Input type="date" value={standalone.dedication_date} onChange={(event) => setStandalone({ ...standalone, dedication_date: event.target.value })} data-testid="standalone-dedication-date-input" /></div>
                <div><Label>Lugar</Label><Input value={standalone.location} onChange={(event) => setStandalone({ ...standalone, location: event.target.value })} data-testid="standalone-location-input" /></div>
              </div>
              <div><Label>Ministro oficiante</Label><Input value={standalone.officiant_name} onChange={(event) => setStandalone({ ...standalone, officiant_name: event.target.value })} data-testid="standalone-officiant-input" /></div>
              <div><Label>Quién presenta</Label><Input value={standalone.presented_by} onChange={(event) => setStandalone({ ...standalone, presented_by: event.target.value })} data-testid="standalone-presented-by-input" /></div>
              <div><Label>Testigos / padrinos (separados por coma)</Label><Input value={standalone.witnesses} onChange={(event) => setStandalone({ ...standalone, witnesses: event.target.value })} data-testid="standalone-witnesses-input" /></div>
              <div><Label>Versículo / texto de dedicación</Label><Textarea value={standalone.dedication_verse} onChange={(event) => setStandalone({ ...standalone, dedication_verse: event.target.value })} data-testid="standalone-verse-input" /></div>
              <Button onClick={submitStandalone} disabled={standaloneSaving} className="justify-self-end bg-[#0798C8]" data-testid="save-standalone-dedication-button">{standaloneSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus2 className="h-4 w-4" />}Registrar</Button>
            </div>
          </DialogContent>
        </Dialog>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild><Button className="bg-[#0798C8]" data-testid="new-dedication-event-button"><CalendarPlus className="h-4 w-4" />Nuevo evento</Button></DialogTrigger>
          <DialogContent data-testid="new-dedication-event-dialog"><DialogHeader><DialogTitle>Nuevo evento de presentación</DialogTitle><DialogDescription>Define fecha, lugar y cupo. Cada niño/a agregado heredará estos datos.</DialogDescription></DialogHeader>
            <div className="grid gap-3">
              <div><Label>Nombre del evento</Label><Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Presentación de Niños Mayo 2026" data-testid="dedication-event-name-input" /></div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div><Label>Fecha</Label><Input type="date" value={form.event_date} onChange={(event) => setForm({ ...form, event_date: event.target.value })} data-testid="dedication-event-date-input" /></div>
                <div><Label>Cupo (opcional)</Label><Input type="number" min="1" value={form.capacity} onChange={(event) => setForm({ ...form, capacity: event.target.value })} data-testid="dedication-event-capacity-input" /></div>
              </div>
              <div><Label>Lugar</Label><Input value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} data-testid="dedication-event-location-input" /></div>
              <div><Label>Ministro oficiante</Label><Input value={form.officiant_name} onChange={(event) => setForm({ ...form, officiant_name: event.target.value })} data-testid="dedication-event-officiant-input" /></div>
              <div><Label>Notas</Label><Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} data-testid="dedication-event-notes-input" /></div>
              <Button onClick={createEvent} disabled={saving} className="justify-self-end bg-[#0798C8]" data-testid="save-dedication-event-button">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarPlus className="h-4 w-4" />}Crear evento</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </header>

    <section className="border bg-white p-5" data-testid="dedication-events-list">
      {loading ? <p className="text-sm text-slate-500">Cargando eventos…</p> : events.length === 0 ? <p className="text-sm text-slate-500" data-testid="dedication-events-empty">Aún no hay eventos de presentación programados.</p> : (
        <Table>
          <TableHeader><TableRow><TableHead>Evento</TableHead><TableHead>Fecha</TableHead><TableHead>Lugar</TableHead><TableHead>Niños</TableHead><TableHead>Estado</TableHead><TableHead /></TableRow></TableHeader>
          <TableBody>
            {events.map((event) => (
              <TableRow key={event.event_id} data-testid={`dedication-event-row-${event.event_id}`}>
                <TableCell className="font-medium">{event.name}</TableCell>
                <TableCell>{event.event_date}</TableCell>
                <TableCell>{event.location || '—'}</TableCell>
                <TableCell>{event.completed_count}/{event.candidate_count}{event.capacity ? ` · cupo ${event.capacity}` : ''}</TableCell>
                <TableCell><Badge variant="outline">{statusLabel[event.status] || event.status}</Badge></TableCell>
                <TableCell><Button size="sm" variant="outline" onClick={() => openEvent(event.event_id)} data-testid={`open-dedication-event-${event.event_id}`}>Ver listado</Button></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>

    <Dialog open={Boolean(activeEvent)} onOpenChange={(open) => { if (!open) setActiveEvent(null); }}>
      <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto" data-testid="dedication-event-roster-dialog">
        <DialogHeader><DialogTitle>{activeEvent?.name}</DialogTitle><DialogDescription>{activeEvent?.event_date} · {activeEvent?.location || 'Sin lugar definido'}</DialogDescription></DialogHeader>
        {activeEvent?.status === 'scheduled' && (
          <div className="space-y-3 border-b pb-4">
            <PersonPicker label="Niño/a" value={candidate.child} onSelect={(value) => setCandidate({ ...candidate, child: value })} testId="event-child-picker" />
            <PersonPicker label="Madre" value={candidate.mother} onSelect={(value) => setCandidate({ ...candidate, mother: value })} testId="event-mother-picker" createFields={['telefono']} />
            <PersonPicker label="Padre" value={candidate.father} onSelect={(value) => setCandidate({ ...candidate, father: value })} testId="event-father-picker" createFields={['telefono']} />
            <Input placeholder="Quién presenta (opcional)" value={candidate.presented_by} onChange={(event) => setCandidate({ ...candidate, presented_by: event.target.value })} data-testid="event-presented-by-input" />
            <Input placeholder="Testigos / padrinos (separados por coma)" value={candidate.witnesses} onChange={(event) => setCandidate({ ...candidate, witnesses: event.target.value })} data-testid="event-witnesses-input" />
            <Textarea placeholder="Versículo / texto de dedicación (opcional)" value={candidate.dedication_verse} onChange={(event) => setCandidate({ ...candidate, dedication_verse: event.target.value })} data-testid="event-verse-input" />
            <Button onClick={addCandidate} className="bg-[#0798C8]" data-testid="add-dedication-candidate-button"><UserPlus2 className="h-4 w-4" />Agregar al listado</Button>
          </div>
        )}
        <div className="mt-2 divide-y border" data-testid="dedication-event-roster">
          {roster.length === 0 ? <p className="p-3 text-sm text-slate-500">Sin niños registrados.</p> : roster.map((entry) => (
            <div key={entry.child_person_id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm" data-testid={`dedication-roster-row-${entry.child_person_id}`}>
              <div><span className="font-medium">{entry.child_name}</span> <Badge variant="outline" className="ml-2">{candidateStatusLabel[entry.status] || entry.status}</Badge></div>
              <div className="flex flex-wrap items-center gap-2">
                {entry.status === 'scheduled' && <>
                  <Button size="sm" variant="outline" onClick={() => completeCandidate(entry.child_person_id)} data-testid={`complete-dedication-candidate-${entry.child_person_id}`}>Completar</Button>
                  <Button size="sm" variant="ghost" onClick={() => removeCandidate(entry.child_person_id)} data-testid={`remove-dedication-candidate-${entry.child_person_id}`}><Trash2 className="h-3.5 w-3.5 text-red-600" /></Button>
                </>}
                {entry.status === 'completed' && <Button size="sm" className="bg-[#0798C8]" onClick={() => issueCertificate(entry.child_person_id)} data-testid={`issue-dedication-certificate-roster-${entry.child_person_id}`}><ShieldCheck className="h-3.5 w-3.5" />{entry.certificate_issue_date ? 'Reimprimir' : 'Emitir certificado'}</Button>}
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
    <DedicationDocumentDialog open={preview.open} onOpenChange={(open) => setPreview((old) => ({ ...old, open }))} data={preview.data} signatureSrc={signatureSrc} />
  </div></main>;
}
