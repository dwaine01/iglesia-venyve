import React, { useEffect, useMemo, useState } from 'react';
import { Save, ShieldCheck } from 'lucide-react';

import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { displayLabel } from '../../lib/displayLabels';
import { isPastoralAuthority } from '../../lib/accessControl';

const levels = ['persona', 'lider', 'equipo', 'secretario', 'tesorero', 'director', 'coordinador_general', 'pastor'];
const groups = ['membership', 'board', 'finance'];
const pastorOnlyGroups = new Set(['board', 'finance']);

const toggle = (items, value, checked) => checked
  ? [...new Set([...(items || []), value])]
  : (items || []).filter((item) => item !== value);

export const CoreAccessTable = ({ items = [], currentUser, catalog = [], saving, onSave }) => {
  const initial = useMemo(() => Object.fromEntries(items.map((item) => [item.user_id, {
    access_level: item.access_level || item.rol,
    is_active: item.is_active !== false,
    privilege_groups: item.privilege_groups || [],
    capabilities: item.capabilities || [],
  }])), [items]);
  const [drafts, setDrafts] = useState(initial);
  useEffect(() => setDrafts(initial), [initial]);
  const patch = (userId, changes) => setDrafts((current) => ({ ...current, [userId]: { ...current[userId], ...changes } }));
  const save = (userId, draft) => onSave(userId, {
    access_level: draft.access_level,
    is_active: draft.is_active !== false,
    privilege_groups: (draft.privilege_groups || []).filter((group) => groups.includes(group)),
    capabilities: draft.capabilities || [],
  });

  return <section className="overflow-hidden border bg-white" data-testid="core-access-table">
    <div className="border-b bg-slate-50 p-4">
      <h2 className="font-['Spectral'] text-xl font-semibold">Accesos del sistema</h2>
      <p className="mt-1 text-xs text-slate-500">Los módulos restringidos y autoridades ministeriales requieren concesión pastoral explícita. Para líder/persona la lista marcada aquí es la que queda vigente (permite recortar, no solo agregar).</p>
    </div>
    <div className="overflow-x-auto"><Table><TableHeader><TableRow>
      <TableHead>Usuario</TableHead><TableHead>Nivel</TableHead><TableHead>Grupos</TableHead><TableHead>Módulos asignados</TableHead><TableHead>Estado</TableHead><TableHead />
    </TableRow></TableHeader><TableBody>{items.map((item) => {
      const draft = drafts[item.user_id] || {};
      const locked = item.user_id === (currentUser?.user_id || currentUser?.id);
      return <TableRow key={item.user_id} data-testid={`access-row-${item.user_id}`}>
        <TableCell><b>{item.nombre || item.email}</b><small className="block text-slate-500">{item.email}</small>{item.permissions_mode === 'manual' && <small className="mt-0.5 block text-[#9A7A2F]" data-testid={`access-manual-badge-${item.user_id}`}>Permisos manuales ({(item.capabilities || []).length})</small>}{Object.keys(item.capabilities_by_role || {}).length > 0 && <small className="mt-0.5 block text-sky-800" data-testid={`access-by-role-${item.user_id}`} title={Object.keys(item.capabilities_by_role).join(', ')}>{Object.keys(item.capabilities_by_role).length} permiso(s) por cargo: se quitan retirando el cargo, no aquí</small>}</TableCell>
        <TableCell><Select disabled={locked} value={draft.access_level || item.rol} onValueChange={(value) => patch(item.user_id, { access_level: value })}><SelectTrigger data-testid={`access-level-${item.user_id}`}><SelectValue /></SelectTrigger><SelectContent className="bg-white">{levels.map((level) => <SelectItem key={level} value={level}>{displayLabel(level)}</SelectItem>)}</SelectContent></Select></TableCell>
        <TableCell><div className="flex max-w-xs flex-wrap gap-2">{groups.map((group) => <label key={group} className="flex items-center gap-1 text-xs"><Checkbox disabled={locked || pastorOnlyGroups.has(group) && !isPastoralAuthority(currentUser)} checked={(draft.privilege_groups || []).includes(group)} onCheckedChange={(checked) => patch(item.user_id, { privilege_groups: toggle(draft.privilege_groups, group, checked) })} data-testid={`access-group-${group}-${item.user_id}`} />{displayLabel(group)}</label>)}</div></TableCell>
        <TableCell><div className="grid max-h-56 min-w-[280px] gap-3 overflow-y-auto pr-1" data-testid={`access-capability-matrix-${item.user_id}`}>{catalog.filter((module) => (draft.access_level || item.rol) !== 'persona' || module.module_key !== 'staff_tools').map((module) => <div key={module.module_key}><p className="text-[10px] font-bold uppercase text-[#9A7A2F]">{module.label}</p><div className="mt-1 grid gap-1.5">{module.items.map((entry) => <label key={entry.capability} className="flex items-center gap-2 text-xs"><Checkbox disabled={locked || !isPastoralAuthority(currentUser)} checked={(draft.capabilities || []).includes(entry.capability)} onCheckedChange={(checked) => patch(item.user_id, { capabilities: toggle(draft.capabilities, entry.capability, checked) })} data-testid={`access-capability-${entry.capability.replaceAll('.', '-').replaceAll('_', '-')}-${item.user_id}`} /><ShieldCheck className="h-3.5 w-3.5 shrink-0 text-[#B5953F]" />{entry.label}</label>)}</div></div>)}</div></TableCell>
        <TableCell><Select disabled={locked} value={draft.is_active ? 'active' : 'inactive'} onValueChange={(value) => patch(item.user_id, { is_active: value === 'active' })}><SelectTrigger data-testid={`access-status-${item.user_id}`}><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="active">Activo</SelectItem><SelectItem value="inactive">Inactivo</SelectItem></SelectContent></Select></TableCell>
        <TableCell><Button size="sm" disabled={locked || saving === item.user_id} onClick={() => save(item.user_id, draft)} data-testid={`save-access-${item.user_id}`}><Save className="h-4 w-4" />Guardar</Button></TableCell>
      </TableRow>;
    })}</TableBody></Table></div>
  </section>;
};