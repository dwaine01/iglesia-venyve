import React, { useEffect, useState } from 'react';
import { ExternalLink, Loader2, Save, UserRoundCog } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Switch } from '../ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';

const levelLabel = { pastor: 'Pastor', coordinador_general: 'Coordinador general', director: 'Director/a', secretario: 'Secretario/a', tesorero: 'Tesorero/a', equipo: 'Equipo', lider: 'Líder', persona: 'Persona' };

const LevelSelect = ({ item, draft, currentUser, onChange, testId }) => {
  const protectedLevel = ['pastor', 'coordinador_general'].includes(item.access_level);
  const canEdit = item.user_id !== currentUser?.id && (currentUser?.rol === 'pastor' || !protectedLevel);
  const levels = currentUser?.rol === 'pastor' ? ['pastor', 'coordinador_general', 'director', 'lider', 'secretario', 'tesorero', 'equipo', 'persona'] : currentUser?.access_level === 'coordinador_general' ? ['director', 'lider', 'persona'] : ['secretario', 'tesorero', 'equipo', 'persona'];
  return <Select value={draft.access_level} onValueChange={(value) => onChange(item.user_id, 'access_level', value)} disabled={!canEdit}><SelectTrigger className="w-full bg-white" data-testid={testId}><SelectValue /></SelectTrigger><SelectContent className="bg-white">{levels.map((level) => <SelectItem key={level} value={level}>{levelLabel[level]}</SelectItem>)}</SelectContent></Select>;
};

const PrivilegeEditor = ({ item, draft, currentUser, onChange }) => { const protectedLevel = ['pastor', 'coordinador_general'].includes(item.access_level); const canEdit = item.user_id !== currentUser?.id && (currentUser?.rol === 'pastor' || !protectedLevel); const available = currentUser?.rol === 'pastor' ? [['membership', 'Membresía'], ['board', 'Junta'], ['finance', 'Finanzas']] : [['membership', 'Membresía']]; const toggle = (group, checked) => onChange(item.user_id, 'privilege_groups', checked ? [...new Set([...(draft.privilege_groups || []), group])] : (draft.privilege_groups || []).filter((value) => value !== group)); return <div className="flex flex-wrap gap-3">{available.map(([group, label]) => <label key={group} className="flex items-center gap-1.5 text-xs"><Checkbox checked={(draft.privilege_groups || []).includes(group)} onCheckedChange={(value) => toggle(group, Boolean(value))} disabled={!canEdit} data-testid={`core-user-privilege-${group}-${item.user_id}`} />{label}</label>)}</div>; };

const AccessActions = ({ item, draft, currentUser, saving, onChange, onSave, onOpenProfile, suffix = '' }) => {
  const protectedLevel = ['pastor', 'coordinador_general'].includes(item.access_level);
  const canEdit = item.user_id !== currentUser?.id && (currentUser?.rol === 'pastor' || !protectedLevel);
  return <><div className="flex items-center gap-2"><Switch checked={draft.is_active} onCheckedChange={(value) => onChange(item.user_id, 'is_active', value)} disabled={!canEdit} data-testid={`core-user-active-switch${suffix}-${item.user_id}`} /><span className="text-xs text-gray-600">{draft.is_active ? 'Activa' : 'Inactiva'}</span></div><div className="flex gap-2"><Button variant="outline" size="icon" onClick={() => onOpenProfile(item.person_id)} disabled={!item.person_id} aria-label="Abrir Perfil 360" data-testid={`core-user-profile-button${suffix}-${item.user_id}`}><ExternalLink className="h-4 w-4" /></Button><Button size="sm" onClick={() => onSave(item.user_id)} disabled={!canEdit || saving === item.user_id} className="bg-[#101D36] text-white hover:bg-[#1B2A4A]" data-testid={`core-user-save-button${suffix}-${item.user_id}`}>{saving === item.user_id ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}Guardar</Button></div></>;
};

export const CoreAccessTable = ({ users, currentUser, saving, onSave }) => {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState({});
  useEffect(() => { setDrafts(Object.fromEntries(users.map((item) => [item.user_id, { access_level: item.access_level || item.rol, is_active: item.is_active, privilege_groups: item.privilege_groups || [] }]))); }, [users]);
  const change = (id, field, value) => setDrafts((old) => ({ ...old, [id]: { ...old[id], [field]: value } }));
  const openProfile = (personId) => personId && navigate(`/personas/${personId}`);

  return <section className="px-4 py-8 sm:px-6 lg:px-8" data-testid="core-access-section">
    <div className="mb-5 flex items-start gap-3"><UserRoundCog className="mt-1 h-5 w-5 text-[#9A7A2F]" /><div><h2 className="font-['Spectral'] text-2xl font-bold text-[#101D36]">Cuentas y niveles de acceso</h2><p className="mt-1 text-sm text-gray-600">Cada cuenta apunta a un Perfil 360. Los cambios revocan las sesiones anteriores.</p></div></div>
    <div className="space-y-3 md:hidden">{users.map((item) => { const draft = drafts[item.user_id] || item; return <div key={item.user_id} className="rounded-md border border-[#E5E1D7] bg-white p-4 shadow-sm" data-testid={`core-user-card-${item.user_id}`}><div className="mb-4 flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate font-semibold text-[#101D36]" data-testid={`core-user-name-${item.user_id}`}>{item.nombre}</p><p className="truncate text-xs text-gray-500">{item.email}</p></div><Badge variant="outline">{levelLabel[item.access_level || item.rol]}</Badge></div><div className="grid gap-3"><LevelSelect item={item} draft={draft} currentUser={currentUser} onChange={change} testId={`core-user-role-select-${item.user_id}`} /><PrivilegeEditor item={item} draft={draft} currentUser={currentUser} onChange={change} /><AccessActions item={item} draft={draft} currentUser={currentUser} saving={saving} onChange={change} onSave={(id) => onSave(id, drafts[id])} onOpenProfile={openProfile} /></div></div>; })}</div>
    <div className="hidden overflow-x-auto rounded-md border border-[#E5E1D7] bg-white md:block"><Table><TableHeader><TableRow><TableHead>Cuenta</TableHead><TableHead>Perfil 360</TableHead><TableHead>Nivel</TableHead><TableHead>Privilegios</TableHead><TableHead>Estado y acciones</TableHead></TableRow></TableHeader><TableBody>{users.map((item) => { const draft = drafts[item.user_id] || item; return <TableRow key={item.user_id} data-testid={`core-user-row-${item.user_id}`}><TableCell><p className="font-semibold text-[#101D36]" data-testid={`core-user-name-desktop-${item.user_id}`}>{item.nombre}</p><p className="text-xs text-gray-500">{item.email}</p></TableCell><TableCell><span className="font-mono text-xs text-[#8A6D2F]" data-testid={`core-user-person-id-${item.user_id}`}>{item.person_id ? item.person_id.slice(-8) : 'Sin enlace'}</span></TableCell><TableCell className="min-w-44"><LevelSelect item={item} draft={draft} currentUser={currentUser} onChange={change} testId={`core-user-role-select-desktop-${item.user_id}`} /></TableCell><TableCell><PrivilegeEditor item={item} draft={draft} currentUser={currentUser} onChange={change} /></TableCell><TableCell><AccessActions item={item} draft={draft} currentUser={currentUser} saving={saving} onChange={change} onSave={(id) => onSave(id, drafts[id])} onOpenProfile={openProfile} suffix="-desktop" /></TableCell></TableRow>; })}</TableBody></Table></div>
  </section>;
};