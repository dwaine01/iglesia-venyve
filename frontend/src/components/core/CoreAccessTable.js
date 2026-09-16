import React, { useEffect, useState } from 'react';
import { ExternalLink, Loader2, Save, UserRoundCog } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Switch } from '../ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';

const roleLabel = { pastor: 'Pastor', lider: 'Líder', persona: 'Persona' };

const AccessControls = ({ item, draft, currentUserId, saving, onChange, onSave, onOpenProfile }) => (
  <>
    <Select value={draft.rol} onValueChange={(value) => onChange(item.user_id, 'rol', value)} disabled={item.user_id === currentUserId}>
      <SelectTrigger className="w-full bg-white" data-testid={`core-user-role-select-${item.user_id}`}><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectItem value="pastor">Pastor</SelectItem>
        <SelectItem value="lider">Líder</SelectItem>
        <SelectItem value="persona">Persona</SelectItem>
      </SelectContent>
    </Select>
    <div className="flex items-center gap-2">
      <Switch checked={draft.is_active} onCheckedChange={(value) => onChange(item.user_id, 'is_active', value)} disabled={item.user_id === currentUserId} data-testid={`core-user-active-switch-${item.user_id}`} />
      <span className="text-xs text-gray-600">{draft.is_active ? 'Activa' : 'Inactiva'}</span>
    </div>
    <div className="flex gap-2">
      <Button variant="outline" size="icon" onClick={() => onOpenProfile(item.person_id)} disabled={!item.person_id} aria-label="Abrir Perfil 360" data-testid={`core-user-profile-button-${item.user_id}`}>
        <ExternalLink className="h-4 w-4" />
      </Button>
      <Button size="sm" onClick={() => onSave(item.user_id)} disabled={saving === item.user_id} className="bg-[#101D36] text-white hover:bg-[#1B2A4A]" data-testid={`core-user-save-button-${item.user_id}`}>
        {saving === item.user_id ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />} Guardar
      </Button>
    </div>
  </>
);

export const CoreAccessTable = ({ users, currentUserId, saving, onSave }) => {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState({});
  useEffect(() => {
    setDrafts(Object.fromEntries(users.map((item) => [item.user_id, { rol: item.rol, is_active: item.is_active }])));
  }, [users]);
  const change = (id, field, value) => setDrafts((old) => ({ ...old, [id]: { ...old[id], [field]: value } }));
  const save = (id) => onSave(id, drafts[id]);
  const openProfile = (personId) => personId && navigate(`/personas/${personId}`);

  return (
    <section className="px-4 py-8 sm:px-6 lg:px-8" data-testid="core-access-section">
      <div className="mb-5 flex items-start gap-3">
        <UserRoundCog className="mt-1 h-5 w-5 text-[#9A7A2F]" />
        <div>
          <h2 className="font-['Spectral'] text-2xl font-bold text-[#101D36]">Roles y acceso</h2>
          <p className="mt-1 text-sm text-gray-600">Cada cuenta apunta a una Persona canónica. Cambiar acceso revoca sus sesiones anteriores.</p>
        </div>
      </div>

      <div className="space-y-3 md:hidden">
        {users.map((item) => {
          const draft = drafts[item.user_id] || item;
          return (
            <div key={item.user_id} className="rounded-md border border-[#E5E1D7] bg-white p-4 shadow-sm" data-testid={`core-user-card-${item.user_id}`}>
              <div className="mb-4 flex items-start justify-between gap-3">
                <div className="min-w-0"><p className="truncate font-semibold text-[#101D36]" data-testid={`core-user-name-${item.user_id}`}>{item.nombre}</p><p className="truncate text-xs text-gray-500">{item.email}</p></div>
                <Badge variant="outline">{roleLabel[item.rol]}</Badge>
              </div>
              <div className="grid gap-3"><AccessControls item={item} draft={draft} currentUserId={currentUserId} saving={saving} onChange={change} onSave={save} onOpenProfile={openProfile} /></div>
            </div>
          );
        })}
      </div>

      <div className="hidden overflow-x-auto rounded-md border border-[#E5E1D7] bg-white md:block">
        <Table>
          <TableHeader><TableRow><TableHead>Cuenta</TableHead><TableHead>Perfil 360</TableHead><TableHead>Rol</TableHead><TableHead>Estado</TableHead><TableHead className="text-right">Acciones</TableHead></TableRow></TableHeader>
          <TableBody>
            {users.map((item) => {
              const draft = drafts[item.user_id] || item;
              return (
                <TableRow key={item.user_id} data-testid={`core-user-row-${item.user_id}`}>
                  <TableCell><p className="font-semibold text-[#101D36]" data-testid={`core-user-name-desktop-${item.user_id}`}>{item.nombre}</p><p className="text-xs text-gray-500">{item.email}</p></TableCell>
                  <TableCell><span className="font-mono text-xs text-[#8A6D2F]" data-testid={`core-user-person-id-${item.user_id}`}>{item.person_id ? item.person_id.slice(-8) : 'Sin enlace'}</span></TableCell>
                  <TableCell className="min-w-36"><Select value={draft.rol} onValueChange={(value) => change(item.user_id, 'rol', value)} disabled={item.user_id === currentUserId}><SelectTrigger data-testid={`core-user-role-select-desktop-${item.user_id}`}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="pastor">Pastor</SelectItem><SelectItem value="lider">Líder</SelectItem><SelectItem value="persona">Persona</SelectItem></SelectContent></Select></TableCell>
                  <TableCell><div className="flex items-center gap-2"><Switch checked={draft.is_active} onCheckedChange={(value) => change(item.user_id, 'is_active', value)} disabled={item.user_id === currentUserId} data-testid={`core-user-active-switch-desktop-${item.user_id}`} /><span className="text-xs">{draft.is_active ? 'Activa' : 'Inactiva'}</span></div></TableCell>
                  <TableCell><div className="flex justify-end gap-2"><Button variant="outline" size="icon" onClick={() => openProfile(item.person_id)} disabled={!item.person_id} aria-label="Abrir Perfil 360" data-testid={`core-user-profile-button-desktop-${item.user_id}`}><ExternalLink className="h-4 w-4" /></Button><Button size="sm" onClick={() => save(item.user_id)} disabled={saving === item.user_id} className="bg-[#101D36] text-white hover:bg-[#1B2A4A]" data-testid={`core-user-save-button-desktop-${item.user_id}`}>{saving === item.user_id ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}Guardar</Button></div></TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </section>
  );
};