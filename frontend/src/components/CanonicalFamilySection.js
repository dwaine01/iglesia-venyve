import React, { useState } from 'react';
import axios from 'axios';
import { Baby, Camera, Check, Search, Trash2, UserPlus, UsersRound, X } from 'lucide-react';
import { toast } from 'sonner';
import PersonCanonicalLink from './PersonCanonicalLink';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Progress } from './ui/progress';
import { uploadPersonPhoto } from '../lib/personPhotoUpload';

const RELATIONSHIPS = [
  ['parent_of', 'Es padre/madre de'],
  ['child_of', 'Es hijo/a de'],
  ['spouse_of', 'Es cónyuge de'],
  ['sibling_of', 'Es hermano/a de'],
  ['grandparent_of', 'Es abuelo/a de'],
  ['grandchild_of', 'Es nieto/a de'],
  ['guardian_of', 'Es tutor/a de'],
  ['other', 'Otra relación familiar'],
];

const EMPTY_PERSON = {
  nombre: '', apellido: '', fecha_nacimiento: '', genero: 'no_especificado',
  telefono: '', email: '', linea1: '', ciudad: '',
};

const ageGroupFromDob = (dob) => {
  if (!dob) return null;
  const born = new Date(`${dob}T12:00:00`);
  const today = new Date();
  let age = today.getFullYear() - born.getFullYear();
  if ((today.getMonth() < born.getMonth()) || (today.getMonth() === born.getMonth() && today.getDate() < born.getDate())) age -= 1;
  if (age < 12) return 'ninez';
  if (age < 18) return 'adolescencia';
  return 'adulto';
};

export default function CanonicalFamilySection({ personId, items = [], canWrite, API, getAuthHeaders, onChanged }) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState('search');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [relationType, setRelationType] = useState('parent_of');
  const [sameHousehold, setSameHousehold] = useState(false);
  const [quick, setQuick] = useState(EMPTY_PERSON);
  const [photo, setPhoto] = useState(null);
  const [progress, setProgress] = useState(0);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [ministryOptions, setMinistryOptions] = useState([]);
  const [roleOptions, setRoleOptions] = useState([]);
  const [ministryDraft, setMinistryDraft] = useState({ ministry_id: '', role_id: '' });
  const [ministryAssignments, setMinistryAssignments] = useState([]);
  const [duplicatePerson, setDuplicatePerson] = useState(null);
  const suggestedAgeGroup = ageGroupFromDob(quick.fecha_nacimiento);

  const reset = () => {
    setMode('search'); setQuery(''); setResults([]); setSelected(null);
    setRelationType('parent_of'); setSameHousehold(false); setQuick(EMPTY_PERSON);
    setPhoto(null); setProgress(0); setError(''); setDuplicatePerson(null); setMinistryAssignments([]);
    setMinistryDraft({ ministry_id: '', role_id: '' });
  };

  const openDialog = async () => {
    reset(); setOpen(true);
    try {
      const [ministries, roles] = await Promise.all([
        axios.get(`${API}/api/ministries`, getAuthHeaders()),
        axios.get(`${API}/api/ministries/roles/catalog`, getAuthHeaders()),
      ]);
      setMinistryOptions(ministries.data.items || []);
      setRoleOptions(roles.data.items || []);
    } catch {
      setMinistryOptions([]); setRoleOptions([]);
    }
  };

  const addMinistryAssignment = () => {
    if (!ministryDraft.ministry_id || !ministryDraft.role_id) return;
    if (ministryAssignments.some((item) => item.ministry_id === ministryDraft.ministry_id && item.role_id === ministryDraft.role_id)) return;
    setMinistryAssignments((items) => [...items, ministryDraft]);
    setMinistryDraft({ ministry_id: '', role_id: '' });
  };

  const selectMinistry = async (ministryId) => {
    setMinistryDraft({ ministry_id: ministryId, role_id: '' });
    try {
      const response = await axios.get(`${API}/api/ministries/roles/catalog`, {
        ...getAuthHeaders(), params: ministryId ? { ministry_id: ministryId } : {},
      });
      setRoleOptions(response.data.items || []);
    } catch {
      setRoleOptions([]);
    }
  };

  const search = async () => {
    if (query.trim().length < 2) return;
    setError('');
    try {
      const response = await axios.get(
        `${API}/api/core/persons/${personId}/relationships/search`,
        { ...getAuthHeaders(), params: { q: query.trim() } }
      );
      setResults(response.data.items || []);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo buscar Personas.');
    }
  };

  const linkExisting = async () => {
    if (!selected) return;
    setSaving(true); setError('');
    try {
      await axios.post(
        `${API}/api/core/persons/${personId}/relationships`,
        { related_person_id: selected.person_id, relation_type: relationType, same_household: sameHousehold },
        getAuthHeaders()
      );
      setOpen(false); reset(); toast.success('Relación familiar creada.'); await onChanged();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo crear la relación.');
    } finally { setSaving(false); }
  };

  const quickCreate = async (event) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      const response = await axios.post(
        `${API}/api/core/persons/${personId}/family/quick-create`,
        { ...quick, relation_type: relationType, same_household: sameHousehold, ministry_assignments: ministryAssignments },
        getAuthHeaders()
      );
      if (photo) {
        await uploadPersonPhoto({ file: photo, personId: response.data.person_id, API, getAuthHeaders, onProgress: setProgress });
      }
      setOpen(false); reset(); toast.success('Persona creada y vinculada a la familia.'); await onChanged();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setDuplicatePerson(detail?.person_id ? { person_id: detail.person_id, person_number: detail.person_number } : null);
      setError(typeof detail === 'string' ? detail : detail?.message || err.message || 'No se pudo crear la Persona.');
    } finally { setSaving(false); }
  };

  const remove = async (id) => {
    if (!window.confirm('¿Eliminar esta relación? La Persona canónica no se eliminará.')) return;
    await axios.delete(`${API}/api/core/persons/${personId}/relationships/${id}`, getAuthHeaders());
    await onChanged();
  };

  return (
    <section className="space-y-4" data-testid="canonical-family-section">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#F3EACD] text-[#755B21]"><UsersRound className="h-5 w-5" /></div><div><h2 className="text-xl font-bold text-[#101D36]">Familia canónica</h2><p className="text-sm text-gray-500">Cada familiar es una Persona con su propio person_id, VV y ficha 360.</p></div></div>
        {canWrite && <Button onClick={openDialog} data-testid="open-quick-family-modal" className="bg-[#132443]"><UserPlus className="mr-2 h-4 w-4" />Agregar familiar</Button>}
      </div>

      {items.length === 0 ? (
        <div className="rounded-xl border border-dashed p-10 text-center"><UsersRound className="mx-auto mb-3 h-9 w-9 text-[#B99A4B]" /><p className="font-medium text-gray-800">Sin relaciones canónicas</p><p className="mt-1 text-sm text-gray-500">Busca una Persona existente antes de crear una nueva.</p></div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">{items.map((item) => (
          <Card key={item.relationship_id}><CardContent className="flex items-start gap-3 p-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-full bg-[#F3EACD] font-semibold text-[#755B21]">{item.nombre_completo?.split(' ').map((part) => part[0]).slice(0, 2).join('')}</div>
            <div className="min-w-0 flex-1"><PersonCanonicalLink personId={item.related_person_id} testId={`family-profile-link-${item.related_person_id}`} className="font-semibold text-[#101D36]">{item.nombre_completo}</PersonCanonicalLink><p className="font-mono text-xs text-[#8A6D2F]">{item.person_number}</p><div className="mt-2 flex flex-wrap gap-2"><Badge variant="outline">{item.relation_label}</Badge>{item.age_years !== null && <Badge variant="secondary">{item.age_years} años · {item.age_group_label}</Badge>}</div></div>
            {canWrite && <Button variant="ghost" size="icon" aria-label={`Eliminar relación con ${item.nombre_completo}`} data-testid={`delete-family-relationship-${item.relationship_id}`} onClick={() => remove(item.relationship_id)} className="text-red-600"><Trash2 className="h-4 w-4" /></Button>}
          </CardContent></Card>
        ))}</div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl" data-testid="quick-family-dialog">
          <DialogHeader><DialogTitle>Agregar familiar</DialogTitle><DialogDescription>Paso 1: busca la Persona. Solo crea una nueva si confirmas que no existe.</DialogDescription></DialogHeader>
          <div className="flex rounded-lg bg-gray-100 p-1"><Button type="button" variant={mode === 'search' ? 'default' : 'ghost'} onClick={() => setMode('search')} data-testid="family-mode-search-button" className="flex-1">Buscar existente</Button><Button type="button" variant={mode === 'create' ? 'default' : 'ghost'} onClick={() => setMode('create')} data-testid="family-mode-create-button" className="flex-1">Crear Persona</Button></div>

          {mode === 'search' ? <div className="space-y-4">
            <div className="flex gap-2"><Input value={query} data-testid="family-search-input" onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && search()} placeholder="Nombre, VV o teléfono" /><Button type="button" onClick={search} data-testid="family-search-button"><Search className="mr-2 h-4 w-4" />Buscar</Button></div>
            <div className="max-h-56 space-y-2 overflow-y-auto" data-testid="family-search-results">{results.map((person) => <button type="button" key={person.person_id} data-testid={`family-search-result-${person.person_id}`} onClick={() => setSelected(person)} className={`flex w-full items-center gap-3 rounded-lg border p-3 text-left ${selected?.person_id === person.person_id ? 'border-[#C8A951] bg-[#FBF8EF]' : 'bg-white'}`}><div className="flex-1"><p className="font-semibold">{person.nombre_completo}</p><p className="font-mono text-xs text-[#8A6D2F]">{person.person_number}</p></div>{selected?.person_id === person.person_id && <Check className="h-5 w-5 text-emerald-600" />}</button>)}</div>
            {results.length === 0 && query.length >= 2 && <button type="button" data-testid="family-create-from-empty-button" onClick={() => setMode('create')} className="w-full rounded-lg border border-dashed p-5 text-sm text-gray-600 hover:bg-gray-50">No la encontré — crear nueva Persona y relacionarla</button>}
          </div> : <form id="quick-person-form" onSubmit={quickCreate} className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label>Nombre</Label><Input data-testid="family-name-input" value={quick.nombre} onChange={(e) => setQuick((old) => ({ ...old, nombre: e.target.value }))} required /></div>
            <div className="space-y-2"><Label>Apellidos</Label><Input data-testid="family-last-name-input" value={quick.apellido} onChange={(e) => setQuick((old) => ({ ...old, apellido: e.target.value }))} required /></div>
            <div className="space-y-2"><Label>Fecha de nacimiento</Label><Input data-testid="family-birth-date-input" type="date" value={quick.fecha_nacimiento} onChange={(e) => setQuick((old) => ({ ...old, fecha_nacimiento: e.target.value }))} /></div>
            <div className="space-y-2"><Label>Género</Label><select data-testid="family-gender-select" value={quick.genero} onChange={(e) => setQuick((old) => ({ ...old, genero: e.target.value }))} className="h-9 w-full rounded-md border bg-white px-3 text-sm"><option value="no_especificado">No especificado</option><option value="masculino">Masculino</option><option value="femenino">Femenino</option></select></div>
            <div className="space-y-2"><Label>Teléfono</Label><Input data-testid="family-phone-input" value={quick.telefono} onChange={(e) => setQuick((old) => ({ ...old, telefono: e.target.value }))} /></div>
            <div className="space-y-2"><Label>Email</Label><Input data-testid="family-email-input" type="email" value={quick.email} onChange={(e) => setQuick((old) => ({ ...old, email: e.target.value }))} /></div>
            <div className="space-y-2"><Label>Dirección</Label><Input data-testid="family-address-input" value={quick.linea1} onChange={(e) => setQuick((old) => ({ ...old, linea1: e.target.value }))} /></div>
            <div className="space-y-2"><Label>Ciudad</Label><Input data-testid="family-city-input" value={quick.ciudad} onChange={(e) => setQuick((old) => ({ ...old, ciudad: e.target.value }))} /></div>
            <div className="space-y-2 sm:col-span-2"><Label>Fotografía opcional</Label><Input data-testid="family-photo-input" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] || null)} /><p className="text-xs text-gray-500"><Camera className="mr-1 inline h-3 w-3" />Puede capturarse ahora o cargarse después desde su ficha.</p>{progress > 0 && <Progress value={progress} className="mt-2 h-2" data-testid="family-photo-progress" />}</div>
            <div className="space-y-2 sm:col-span-2"><Label>Ministerios opcionales — nunca se asignan automáticamente por edad</Label><div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]"><select data-testid="family-ministry-select" value={ministryDraft.ministry_id} onChange={(e) => selectMinistry(e.target.value)} className="h-9 rounded-md border bg-white px-2 text-sm"><option value="">Seleccionar ministerio</option>{ministryOptions.map((item) => <option key={item.ministry_id} value={item.ministry_id}>{item.nombre}{suggestedAgeGroup && item.suggested_age_groups?.includes(suggestedAgeGroup) ? ' · Sugerido por edad' : ''}</option>)}</select><select data-testid="family-ministry-role-select" value={ministryDraft.role_id} onChange={(e) => setMinistryDraft((old) => ({ ...old, role_id: e.target.value }))} className="h-9 rounded-md border bg-white px-2 text-sm"><option value="">Función</option>{roleOptions.map((item) => <option key={item.role_id} value={item.role_id}>{item.nombre}</option>)}</select><Button type="button" variant="outline" onClick={addMinistryAssignment} data-testid="add-family-ministry-assignment-button">Agregar</Button></div>{ministryAssignments.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{ministryAssignments.map((item) => <Badge key={`${item.ministry_id}:${item.role_id}`} variant="secondary" className="gap-1">{ministryOptions.find((option) => option.ministry_id === item.ministry_id)?.nombre} — {roleOptions.find((option) => option.role_id === item.role_id)?.nombre}<button type="button" aria-label="Quitar asignación" data-testid={`remove-family-ministry-assignment-${item.ministry_id}-${item.role_id}`} onClick={() => setMinistryAssignments((items) => items.filter((entry) => entry !== item))}><X className="h-3 w-3" /></button></Badge>)}</div>}</div>
          </form>}

          <div className="grid gap-3 rounded-lg border bg-[#FBFAF7] p-3 sm:grid-cols-2"><div><Label>Relación desde esta Persona</Label><select data-testid="family-relationship-select" value={relationType} onChange={(e) => setRelationType(e.target.value)} className="mt-1 h-9 w-full rounded-md border bg-white px-3 text-sm">{RELATIONSHIPS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div><label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" data-testid="family-same-household-checkbox" checked={sameHousehold} onChange={(e) => setSameHousehold(e.target.checked)} />¿Pertenece al mismo hogar?</label></div>
          <p className="text-xs text-gray-500"><Baby className="mr-1 inline h-3 w-3" />Parentesco no implica custodia, residencia ni permiso de contacto.</p>
          {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700" data-testid="family-error-alert"><p>{error}</p>{duplicatePerson && <PersonCanonicalLink personId={duplicatePerson.person_id} testId="family-duplicate-profile-link" className="mt-2 inline-block font-semibold">Abrir {duplicatePerson.person_number || 'Persona existente'}</PersonCanonicalLink>}</div>}
          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)} data-testid="cancel-family-dialog-button">Cancelar</Button>{mode === 'search' ? <Button onClick={linkExisting} disabled={!selected || saving} data-testid="link-existing-family-button" className="bg-[#132443]">Relacionar Persona</Button> : <Button form="quick-person-form" type="submit" disabled={saving} data-testid="save-family-button" className="bg-[#132443]">Crear Persona y relacionar</Button>}</DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
