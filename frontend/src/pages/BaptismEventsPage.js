/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, CalendarPlus, Droplets, Loader2, Search, ShieldCheck, Trash2, UserPlus, X } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../context/AuthContext';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Textarea } from '../components/ui/textarea';
import { BaptismDocumentDialog } from '../components/baptism/BaptismDocumentDialog';

const EMPTY_EVENT = { name: '', event_date: '', location: '', officiant_name: '', capacity: '', notes: '' };
const statusLabel = { scheduled: 'Programado', completed: 'Completado', cancelled: 'Cancelado' };
const candidateStatusLabel = { pending: 'Pendiente', scheduled: 'Programado', completed: 'Completado' };

export default function BaptismEventsPage() {  const { API, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_EVENT);
  const [saving, setSaving] = useState(false);
  const [activeEvent, setActiveEvent] = useState(null);
  const [roster, setRoster] = useState([]);
  const [search, setSearch] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [completing, setCompleting] = useState(null);
  const [completeForm, setCompleteForm] = useState({ testimony: '', notes: '' });
  const [signatureSrc, setSignatureSrc] = useState(null);
  const [preview, setPreview] = useState({ open: false, data: null });

  const loadEvents = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/api/baptism/events`, getAuthHeaders());
      setEvents(response.data.items || []);
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudieron cargar los eventos de bautismo'); }
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
      await axios.post(`${API}/api/baptism/events`, { ...form, capacity: form.capacity ? Number(form.capacity) : null }, getAuthHeaders());
      toast.success('Evento de bautismo creado'); setCreateOpen(false); setForm(EMPTY_EVENT); await loadEvents();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo crear el evento'); }
    finally { setSaving(false); }
  };

  const openEvent = async (eventId) => {
    try {
      const response = await axios.get(`${API}/api/baptism/events/${eventId}`, getAuthHeaders());
      setActiveEvent(response.data.event); setRoster(response.data.roster || []); setSearch(''); setSearchResults([]);
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo abrir el evento'); }
  };

  const runSearch = async (query) => {
    setSearch(query);
    if (query.trim().length < 2) return setSearchResults([]);
    setSearching(true);
    try {
      const response = await axios.get(`${API}/api/core/persons/directory/search`, { ...getAuthHeaders(), params: { q: query, limit: 8 } });
      setSearchResults(response.data.items || []);
    } catch { setSearchResults([]); }
    finally { setSearching(false); }
  };

  const addCandidate = async (personId) => {
    try {
      const response = await axios.post(`${API}/api/baptism/events/${activeEvent.event_id}/candidates`, { person_id: personId }, getAuthHeaders());
      setRoster(response.data.roster || []); setSearch(''); setSearchResults([]);
      toast.success('Candidato agregado al listado'); await loadEvents();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo agregar el candidato'); }
  };

  const removeCandidate = async (personId) => {
    try {
      const response = await axios.delete(`${API}/api/baptism/events/${activeEvent.event_id}/candidates/${personId}`, getAuthHeaders());
      setRoster(response.data.roster || []); toast.success('Candidato removido del evento'); await loadEvents();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo quitar el candidato'); }
  };

  const completeCandidate = async (personId) => {
    try {
      const response = await axios.post(`${API}/api/baptism/events/${activeEvent.event_id}/candidates/${personId}/complete`, completeForm, getAuthHeaders());
      setRoster(response.data.roster || []); setCompleting(null); setCompleteForm({ testimony: '', notes: '' });
      toast.success('Bautismo marcado como completado'); await loadEvents();
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo completar el registro'); }
  };

  const issueCertificate = async (personId) => {
    try {
      const response = await axios.post(`${API}/api/baptism/persons/${personId}/certificate/issue`, {}, getAuthHeaders());
      setPreview({ open: true, data: response.data.data });
      toast.success(response.data.action === 'issued' ? 'Certificado emitido' : 'Reimpresión registrada');
    } catch (error) { toast.error(error?.response?.data?.detail || 'No se pudo emitir el certificado'); }
  };

  return <main className="min-h-screen bg-[#F4F1EA] px-4 py-6 sm:px-6 lg:px-8" data-testid="baptism-events-page"><div className="mx-auto max-w-6xl space-y-6">
    <button type="button" onClick={() => navigate(-1)} className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-950" data-testid="baptism-events-back-button"><ArrowLeft className="h-4 w-4" />Volver</button>
    <header className="flex flex-wrap items-start justify-between gap-4 border-l-4 border-[#132443] bg-white p-5 shadow-sm">
      <div><p className="flex items-center gap-2 text-xs font-bold uppercase text-[#0879BE]"><Droplets className="h-4 w-4" />Bautismos</p><h1 className="mt-2 font-['Spectral'] text-3xl font-semibold text-slate-950 sm:text-4xl">Eventos de bautismo</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Organiza cada servicio de bautismo, registra candidatos con cupo y emite el certificado oficial al completarse.</p></div>
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogTrigger asChild><Button className="bg-[#132443]" data-testid="new-baptism-event-button"><CalendarPlus className="h-4 w-4" />Nuevo evento</Button></DialogTrigger>
        <DialogContent data-testid="new-baptism-event-dialog"><DialogHeader><DialogTitle>Nuevo evento de bautismo</DialogTitle><DialogDescription>Define fecha, lugar y cupo. Cada candidato agregado heredará estos datos.</DialogDescription></DialogHeader>
          <div className="grid gap-3">
            <div><Label>Nombre del evento</Label><Input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Bautismo Diciembre 2026" data-testid="baptism-event-name-input" /></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div><Label>Fecha</Label><Input type="date" value={form.event_date} onChange={(event) => setForm({ ...form, event_date: event.target.value })} data-testid="baptism-event-date-input" /></div>
              <div><Label>Cupo (opcional)</Label><Input type="number" min="1" value={form.capacity} onChange={(event) => setForm({ ...form, capacity: event.target.value })} data-testid="baptism-event-capacity-input" /></div>
            </div>
            <div><Label>Lugar</Label><Input value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} data-testid="baptism-event-location-input" /></div>
            <div><Label>Ministro oficiante</Label><Input value={form.officiant_name} onChange={(event) => setForm({ ...form, officiant_name: event.target.value })} data-testid="baptism-event-officiant-input" /></div>
            <div><Label>Notas</Label><Textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} data-testid="baptism-event-notes-input" /></div>
            <Button onClick={createEvent} disabled={saving} className="justify-self-end bg-[#132443]" data-testid="save-baptism-event-button">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarPlus className="h-4 w-4" />}Crear evento</Button>
          </div>
        </DialogContent>
      </Dialog>
    </header>

    <section className="border bg-white p-5" data-testid="baptism-events-list">
      {loading ? <p className="text-sm text-slate-500">Cargando eventos…</p> : events.length === 0 ? <p className="text-sm text-slate-500" data-testid="baptism-events-empty">Aún no hay eventos de bautismo programados.</p> : (
        <Table>
          <TableHeader><TableRow><TableHead>Evento</TableHead><TableHead>Fecha</TableHead><TableHead>Lugar</TableHead><TableHead>Candidatos</TableHead><TableHead>Estado</TableHead><TableHead /></TableRow></TableHeader>
          <TableBody>
            {events.map((event) => (
              <TableRow key={event.event_id} data-testid={`baptism-event-row-${event.event_id}`}>
                <TableCell className="font-medium">{event.name}</TableCell>
                <TableCell>{event.event_date}</TableCell>
                <TableCell>{event.location || '—'}</TableCell>
                <TableCell>{event.completed_count}/{event.candidate_count}{event.capacity ? ` · cupo ${event.capacity}` : ''}</TableCell>
                <TableCell><Badge variant="outline">{statusLabel[event.status] || event.status}</Badge></TableCell>
                <TableCell><Button size="sm" variant="outline" onClick={() => openEvent(event.event_id)} data-testid={`open-baptism-event-${event.event_id}`}>Ver listado</Button></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>

    <Dialog open={Boolean(activeEvent)} onOpenChange={(open) => { if (!open) setActiveEvent(null); }}>
      <DialogContent className="max-w-3xl" data-testid="baptism-event-roster-dialog">
        <DialogHeader><DialogTitle>{activeEvent?.name}</DialogTitle><DialogDescription>{activeEvent?.event_date} · {activeEvent?.location || 'Sin lugar definido'}</DialogDescription></DialogHeader>
        {activeEvent?.status === 'scheduled' && (
          <div className="relative">
            <Label>Agregar candidato</Label>
            <div className="relative mt-1"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" /><Input className="pl-9" value={search} onChange={(event) => runSearch(event.target.value)} placeholder="Buscar por nombre o N.º de persona" data-testid="baptism-candidate-search-input" /></div>
            {searching && <p className="mt-1 text-xs text-slate-400">Buscando…</p>}
            {searchResults.length > 0 && <div className="mt-2 divide-y border" data-testid="baptism-candidate-search-results">
              {searchResults.map((item) => <div key={item.person_id} className="flex items-center justify-between gap-2 p-2 text-sm">
                <span>{item.nombre_completo} {item.person_number && <span className="text-slate-400">· {item.person_number}</span>}</span>
                <Button size="sm" variant="outline" onClick={() => addCandidate(item.person_id)} data-testid={`add-baptism-candidate-${item.person_id}`}><UserPlus className="h-3.5 w-3.5" />Agregar</Button>
              </div>)}
            </div>}
          </div>
        )}
        <div className="mt-2 divide-y border" data-testid="baptism-event-roster">
          {roster.length === 0 ? <p className="p-3 text-sm text-slate-500">Sin candidatos registrados.</p> : roster.map((candidate) => (
            <div key={candidate.person_id} className="flex flex-wrap items-center justify-between gap-2 p-3 text-sm" data-testid={`baptism-roster-row-${candidate.person_id}`}>
              <div><span className="font-medium">{candidate.person_name}</span> <Badge variant="outline" className="ml-2">{candidateStatusLabel[candidate.status] || candidate.status}</Badge></div>
              <div className="flex flex-wrap items-center gap-2">
                {candidate.status === 'scheduled' && completing !== candidate.person_id && <>
                  <Button size="sm" variant="outline" onClick={() => setCompleting(candidate.person_id)} data-testid={`complete-baptism-candidate-${candidate.person_id}`}>Completar</Button>
                  <Button size="sm" variant="ghost" onClick={() => removeCandidate(candidate.person_id)} data-testid={`remove-baptism-candidate-${candidate.person_id}`}><Trash2 className="h-3.5 w-3.5 text-red-600" /></Button>
                </>}
                {candidate.status === 'completed' && <Button size="sm" className="bg-[#132443]" onClick={() => issueCertificate(candidate.person_id)} data-testid={`issue-baptism-certificate-roster-${candidate.person_id}`}><ShieldCheck className="h-3.5 w-3.5" />{candidate.certificate_issue_date ? 'Reimprimir' : 'Emitir certificado'}</Button>}
              </div>
              {completing === candidate.person_id && <div className="mt-2 grid w-full gap-2" data-testid={`complete-baptism-form-${candidate.person_id}`}>
                <Textarea placeholder="Testimonio (opcional)" value={completeForm.testimony} onChange={(event) => setCompleteForm({ ...completeForm, testimony: event.target.value })} data-testid="complete-baptism-testimony-input" />
                <div className="flex justify-end gap-2">
                  <Button size="sm" variant="ghost" onClick={() => { setCompleting(null); setCompleteForm({ testimony: '', notes: '' }); }}><X className="h-3.5 w-3.5" />Cancelar</Button>
                  <Button size="sm" className="bg-[#132443]" onClick={() => completeCandidate(candidate.person_id)} data-testid="confirm-complete-baptism-button">Confirmar bautismo</Button>
                </div>
              </div>}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
    <BaptismDocumentDialog open={preview.open} onOpenChange={(open) => setPreview((old) => ({ ...old, open }))} data={preview.data} signatureSrc={signatureSrc} />
  </div></main>;
}
