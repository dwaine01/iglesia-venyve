import React, { useEffect, useState } from 'react';
import axios from 'axios';
import {
  CalendarCheck2,
  Clock3,
  FileText,
  House,
  Loader2,
  NotebookPen,
  PlaneTakeoff,
  Plus,
  Trash2,
  UserPlus,
  UsersRound,
} from 'lucide-react';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import PersonCanonicalLink from './PersonCanonicalLink';

function Shell({ title, description, icon: Icon, children, action }) {
  return (
    <section className="space-y-4" data-testid={`profile-domain-${title.toLowerCase().replaceAll(' ', '-')}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#F3EACD] text-[#755B21]"><Icon className="h-5 w-5" /></div>
          <div><h2 className="text-xl font-bold text-[#101D36]">{title}</h2><p className="text-sm text-gray-500">{description}</p></div>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

const request = (API, getAuthHeaders, method, path, data) => axios({ method, url: `${API}${path}`, data, ...getAuthHeaders() });

export function HouseholdSection({ personId, record, canWrite, API, getAuthHeaders, onChanged }) {
  const [form, setForm] = useState({ nombre_hogar: '', rol_en_hogar: '', tipo_vivienda: '', miembros_estimados: '', notas: '' });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  useEffect(() => {
    setForm(record ? { ...record, miembros_estimados: record.miembros_estimados || '' } : { nombre_hogar: '', rol_en_hogar: '', tipo_vivienda: '', miembros_estimados: '', notas: '' });
  }, [record]);
  const save = async (event) => {
    event.preventDefault(); setSaving(true); setMessage('');
    try {
      await request(API, getAuthHeaders, 'put', `/api/core/persons/${personId}/household`, { ...form, miembros_estimados: form.miembros_estimados ? Number(form.miembros_estimados) : null });
      setMessage('Household actualizado'); await onChanged();
    } catch (err) { setMessage(err?.response?.data?.detail || 'No se pudo guardar.'); } finally { setSaving(false); }
  };
  return (
    <Shell title="Household" description="Información del hogar actual, separada de las relaciones familiares." icon={House}>
      <form onSubmit={save} className="grid gap-4 rounded-xl border bg-white p-4 sm:grid-cols-2">
        <div className="space-y-2"><Label>Nombre del hogar</Label><Input value={form.nombre_hogar || ''} onChange={(e) => setForm((old) => ({ ...old, nombre_hogar: e.target.value }))} placeholder="Ej. Hogar González" required disabled={!canWrite} /></div>
        <div className="space-y-2"><Label>Rol en el hogar</Label><Input value={form.rol_en_hogar || ''} onChange={(e) => setForm((old) => ({ ...old, rol_en_hogar: e.target.value }))} placeholder="Ej. madre, hijo" disabled={!canWrite} /></div>
        <div className="space-y-2"><Label>Tipo de vivienda</Label><Input value={form.tipo_vivienda || ''} onChange={(e) => setForm((old) => ({ ...old, tipo_vivienda: e.target.value }))} placeholder="Propia, alquilada..." disabled={!canWrite} /></div>
        <div className="space-y-2"><Label>Miembros estimados</Label><Input type="number" min="1" max="50" value={form.miembros_estimados || ''} onChange={(e) => setForm((old) => ({ ...old, miembros_estimados: e.target.value }))} disabled={!canWrite} /></div>
        <div className="space-y-2 sm:col-span-2"><Label>Notas del hogar</Label><Textarea value={form.notas || ''} onChange={(e) => setForm((old) => ({ ...old, notas: e.target.value }))} disabled={!canWrite} /></div>
        <div className="flex items-center justify-between sm:col-span-2">{message && <p className="text-sm text-gray-600">{message}</p>}{canWrite && <Button disabled={saving} className="ml-auto bg-[#132443]">{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Guardar household</Button>}</div>
      </form>
    </Shell>
  );
}

export function FamilySection({ personId, items = [], canWrite, API, getAuthHeaders, onChanged }) {
  const empty = { nombre: '', relacion: '', alcance: 'inmediata', telefono: '', notas: '' };
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const add = async (event) => {
    event.preventDefault(); setSaving(true);
    try { await request(API, getAuthHeaders, 'post', `/api/core/persons/${personId}/family`, form); setForm(empty); await onChanged(); } finally { setSaving(false); }
  };
  const remove = async (id) => { if (!window.confirm('¿Eliminar esta relación familiar?')) return; await request(API, getAuthHeaders, 'delete', `/api/core/persons/${personId}/family/${id}`); await onChanged(); };
  return (
    <Shell title="Familia" description="Familia inmediata y extendida, sin duplicar el registro Person." icon={UsersRound}>
      {canWrite && <form onSubmit={add} className="grid gap-3 rounded-xl border bg-[#FBFAF7] p-4 sm:grid-cols-2 lg:grid-cols-5">
        <Input value={form.nombre} onChange={(e) => setForm((old) => ({ ...old, nombre: e.target.value }))} placeholder="Nombre" required />
        <Input value={form.relacion} onChange={(e) => setForm((old) => ({ ...old, relacion: e.target.value }))} placeholder="Parentesco" required />
        <select value={form.alcance} onChange={(e) => setForm((old) => ({ ...old, alcance: e.target.value }))} className="h-9 rounded-md border bg-white px-3 text-sm"><option value="inmediata">Familia inmediata</option><option value="extendida">Familia extendida</option></select>
        <Input value={form.telefono} onChange={(e) => setForm((old) => ({ ...old, telefono: e.target.value }))} placeholder="Teléfono opcional" />
        <Button disabled={saving} className="bg-[#132443]"><UserPlus className="mr-2 h-4 w-4" />Agregar</Button>
      </form>}
      {items.length === 0 ? <div className="rounded-xl border border-dashed p-10 text-center text-sm text-gray-500">Sin relaciones familiares registradas.</div> : <div className="grid gap-3 md:grid-cols-2">{items.map((item) => <Card key={item.relation_id}><CardContent className="flex items-start gap-3 p-4"><div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#F3EACD]"><UsersRound className="h-5 w-5 text-[#755B21]" /></div><div className="flex-1"><PersonCanonicalLink personId={item.related_person_id} className="font-semibold text-[#101D36]">{item.nombre}</PersonCanonicalLink><p className="text-sm text-gray-500">{item.relacion} · {item.alcance}</p>{item.telefono && <p className="mt-1 text-sm">{item.telefono}</p>}</div>{canWrite && <Button variant="ghost" size="icon" onClick={() => remove(item.relation_id)} className="text-red-600"><Trash2 className="h-4 w-4" /></Button>}</CardContent></Card>)}</div>}
    </Shell>
  );
}

export function ProcessesSection({ personId, arrival, processes = [], canWrite, API, getAuthHeaders, onChanged }) {
  const [form, setForm] = useState({ fecha_llegada: '', tipo: 'visitante', lugar_origen: '', invitado_por: '', motivo: '', notas: '' });
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (arrival) setForm(arrival); }, [arrival]);
  const save = async (event) => { event.preventDefault(); setSaving(true); try { await request(API, getAuthHeaders, 'put', `/api/core/persons/${personId}/arrival`, form); await onChanged(); } finally { setSaving(false); } };
  return (
    <div className="space-y-7">
      <Shell title="Llegada y origen" description="Cómo y cuándo esta persona llegó a la iglesia." icon={PlaneTakeoff}>
        <form onSubmit={save} className="grid gap-3 rounded-xl border bg-white p-4 md:grid-cols-3">
          <div className="space-y-2"><Label>Fecha de llegada</Label><Input type="date" value={form.fecha_llegada || ''} onChange={(e) => setForm((old) => ({ ...old, fecha_llegada: e.target.value }))} required disabled={!canWrite} /></div>
          <div className="space-y-2"><Label>Tipo</Label><select value={form.tipo || 'visitante'} onChange={(e) => setForm((old) => ({ ...old, tipo: e.target.value }))} className="h-9 w-full rounded-md border bg-white px-3 text-sm" disabled={!canWrite}><option value="visitante">Visitante</option><option value="transferencia">Transferencia</option><option value="nacimiento">Nacimiento</option><option value="otro">Otro</option></select></div>
          <div className="space-y-2"><Label>Lugar de origen</Label><Input value={form.lugar_origen || ''} onChange={(e) => setForm((old) => ({ ...old, lugar_origen: e.target.value }))} disabled={!canWrite} /></div>
          <div className="space-y-2"><Label>Invitado por</Label><Input value={form.invitado_por || ''} onChange={(e) => setForm((old) => ({ ...old, invitado_por: e.target.value }))} disabled={!canWrite} /></div>
          <div className="space-y-2 md:col-span-2"><Label>Motivo / contexto</Label><Input value={form.motivo || ''} onChange={(e) => setForm((old) => ({ ...old, motivo: e.target.value }))} disabled={!canWrite} /></div>
          {canWrite && <Button disabled={saving} className="md:col-start-3 bg-[#132443]">Guardar llegada</Button>}
        </form>
      </Shell>
      <Shell title="Procesos" description="Conectores preparados; cada módulo conserva su propia fuente de verdad." icon={Clock3}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{processes.map((item) => <div key={item.key} className="rounded-xl border bg-white p-4"><div className="flex items-center justify-between gap-2"><p className="font-semibold text-[#101D36]">{item.label}</p><Badge variant="outline" className="text-gray-500">No disponible</Badge></div><p className="mt-2 text-sm text-gray-500">Módulo aún no disponible.</p></div>)}</div>
      </Shell>
    </div>
  );
}

export function AttendanceSection({ personId, items = [], canWrite, API, getAuthHeaders, onChanged }) {
  const [form, setForm] = useState({ fecha: new Date().toISOString().slice(0, 10), actividad: '', estado: 'presente', notas: '' });
  const [saving, setSaving] = useState(false);
  const add = async (event) => { event.preventDefault(); setSaving(true); try { await request(API, getAuthHeaders, 'post', `/api/core/persons/${personId}/attendance`, form); setForm((old) => ({ ...old, actividad: '', notas: '' })); await onChanged(); } finally { setSaving(false); } };
  const remove = async (id) => { if (!window.confirm('¿Eliminar este registro de asistencia?')) return; await request(API, getAuthHeaders, 'delete', `/api/core/persons/${personId}/attendance/${id}`); await onChanged(); };
  return (
    <Shell title="Asistencia" description="Registro cronológico de reuniones y actividades." icon={CalendarCheck2}>
      {canWrite && <form onSubmit={add} className="grid gap-3 rounded-xl border bg-[#FBFAF7] p-4 md:grid-cols-4"><Input type="date" value={form.fecha} onChange={(e) => setForm((old) => ({ ...old, fecha: e.target.value }))} required /><Input value={form.actividad} onChange={(e) => setForm((old) => ({ ...old, actividad: e.target.value }))} placeholder="Actividad" required /><select value={form.estado} onChange={(e) => setForm((old) => ({ ...old, estado: e.target.value }))} className="h-9 rounded-md border bg-white px-3 text-sm"><option value="presente">Presente</option><option value="ausente">Ausente</option><option value="justificado">Justificado</option></select><Button disabled={saving} className="bg-[#132443]"><Plus className="mr-2 h-4 w-4" />Registrar</Button></form>}
      <div className="space-y-2">{items.length === 0 ? <div className="rounded-xl border border-dashed p-10 text-center text-sm text-gray-500">Sin asistencias registradas.</div> : items.map((item) => <div key={item.attendance_id} className="flex items-center gap-3 rounded-xl border bg-white p-4"><CalendarCheck2 className="h-5 w-5 text-[#755B21]" /><div className="flex-1"><p className="font-semibold text-[#101D36]">{item.actividad}</p><p className="text-sm text-gray-500">{item.fecha} · {item.estado}</p></div>{canWrite && <Button variant="ghost" size="icon" onClick={() => remove(item.attendance_id)} className="text-red-600"><Trash2 className="h-4 w-4" /></Button>}</div>)}</div>
    </Shell>
  );
}

export function HistorySection({ personId, notes = [], activity = [], canWrite, canPastoral, API, getAuthHeaders, onChanged }) {
  const [content, setContent] = useState('');
  const [category, setCategory] = useState('general');
  const addNote = async (event) => { event.preventDefault(); await request(API, getAuthHeaders, 'post', `/api/core/persons/${personId}/notes`, { contenido: content, categoria: category }); setContent(''); await onChanged(); };
  const removeNote = async (id) => { if (!window.confirm('¿Eliminar esta nota?')) return; await request(API, getAuthHeaders, 'delete', `/api/core/persons/${personId}/notes/${id}`); await onChanged(); };
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Shell title="Notas" description="Notas internas autorizadas sobre esta persona." icon={NotebookPen}>
        {canWrite && <form onSubmit={addNote} className="space-y-3 rounded-xl border bg-[#FBFAF7] p-4"><Textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="Escribe una nota útil y verificable..." required /><div className="flex gap-2"><select value={category} onChange={(e) => setCategory(e.target.value)} className="h-9 flex-1 rounded-md border bg-white px-3 text-sm"><option value="general">General</option>{canPastoral && <option value="pastoral">Pastoral</option>}<option value="seguimiento">Seguimiento</option></select><Button className="bg-[#132443]"><Plus className="mr-2 h-4 w-4" />Agregar nota</Button></div></form>}
        <div className="space-y-2">{notes.map((note) => <div key={note.note_id} className="rounded-xl border bg-white p-4"><div className="flex items-start gap-3"><FileText className="mt-0.5 h-5 w-5 text-[#755B21]" /><div className="flex-1"><Badge variant="outline" className="mb-2 capitalize">{note.categoria}</Badge><p className="whitespace-pre-wrap text-sm text-gray-700">{note.contenido}</p><p className="mt-2 text-xs text-gray-400">{new Date(note.created_at).toLocaleString('es')}</p></div>{canWrite && <Button variant="ghost" size="icon" onClick={() => removeNote(note.note_id)} className="text-red-600"><Trash2 className="h-4 w-4" /></Button>}</div></div>)}</div>
      </Shell>
      <Shell title="Historial de actividad" description="Cambios reales registrados por los dominios del perfil." icon={Clock3}>
        <div className="space-y-0">{activity.length === 0 ? <div className="rounded-xl border border-dashed p-10 text-center text-sm text-gray-500">Sin actividad registrada todavía.</div> : activity.map((item, index) => <div key={item.activity_id} className="relative flex gap-3 pb-5"><div className="relative z-10 mt-1 h-3 w-3 shrink-0 rounded-full bg-[#C8A951]" />{index < activity.length - 1 && <div className="absolute left-[5px] top-4 h-full w-px bg-gray-200" />}<div><p className="font-medium text-[#101D36]">{item.summary}</p><p className="text-xs text-gray-500">{item.domain} · {new Date(item.created_at).toLocaleString('es')}</p></div></div>)}</div>
      </Shell>
    </div>
  );
}
