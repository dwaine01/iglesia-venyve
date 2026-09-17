import React, { useMemo, useState } from 'react';
import { Save, ShieldCheck } from 'lucide-react';

import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../ui/table';
import { displayLabel } from '../../lib/displayLabels';

const levels = ['persona', 'lider', 'puerta', 'director', 'coordinador', 'pastor'];
const groups = ['membership', 'cellular', 'doors', 'ministries', 'board', 'finance'];
const DOCUMENT_CAPABILITY = 'membership.documents.manage';

export const CoreAccessTable = ({ items = [], currentUser, saving, onSave }) => {
  const initial = useMemo(() => Object.fromEntries(items.map((item) => [item.user_id, {
    access_level: item.access_level || item.rol,
    is_active: item.is_active !== false,
    privilege_groups: item.privilege_groups || [],
    capabilities: item.capabilities || [],
  }])), [items]);
  const [drafts, setDrafts] = useState(initial);

  React.useEffect(() => setDrafts(initial), [initial]);
  const patch = (userId, changes) => setDrafts((current) => ({ ...current, [userId]: { ...current[userId], ...changes } }));

  return <section className="overflow-hidden border bg-white" data-testid="core-access-table">
    <div className="border-b bg-slate-50 p-4"><h2 className="font-['Spectral'] text-xl font-semibold">Accesos del sistema</h2><p className="mt-1 text-xs text-slate-500">Los módulos restringidos requieren concesión explícita del pastor.</p></div>
    <div className="overflow-x-auto"><Table><TableHeader><TableRow><TableHead>Usuario</TableHead><TableHead>Nivel</TableHead><TableHead>Grupos</TableHead><TableHead>Documentos oficiales</TableHead><TableHead>Estado</TableHead><TableHead /></TableRow></TableHeader><TableBody>{items.map((item) => {
      const draft = drafts[item.user_id] || {};
      const locked = item.user_id === currentUser?.user_id;
      const hasDocumentPermission = draft.capabilities?.includes(DOCUMENT_CAPABILITY);
      return <TableRow key={item.user_id} data-testid={`access-row-${item.user_id}`}><TableCell><b>{item.display_name || item.email}</b><small className="block text-slate-500">{item.email}</small></TableCell><TableCell><Select disabled={locked} value={draft.access_level || item.rol} onValueChange={(value) => patch(item.user_id, { access_level: value })}><SelectTrigger data-testid={`access-level-${item.user_id}`}><SelectValue /></SelectTrigger><SelectContent className="bg-white">{levels.map((level) => <SelectItem key={level} value={level}>{displayLabel(level)}</SelectItem>)}</SelectContent></Select></TableCell><TableCell><div className="flex max-w-md flex-wrap gap-2">{groups.map((group) => <label key={group} className="flex items-center gap-1 text-xs"><Checkbox disabled={locked || group === 'finance' && currentUser?.rol !== 'pastor'} checked={draft.privilege_groups?.includes(group)} onCheckedChange={(checked) => patch(item.user_id, { privilege_groups: checked ? [...new Set([...(draft.privilege_groups || []), group])] : (draft.privilege_groups || []).filter((value) => value !== group) })} data-testid={`access-group-${group}-${item.user_id}`} />{displayLabel(group)}</label>)}</div></TableCell><TableCell><label className="flex items-center gap-2 text-sm"><Checkbox disabled={locked || currentUser?.rol !== 'pastor'} checked={hasDocumentPermission} onCheckedChange={(checked) => patch(item.user_id, { capabilities: checked ? [...new Set([...(draft.capabilities || []), DOCUMENT_CAPABILITY])] : (draft.capabilities || []).filter((value) => value !== DOCUMENT_CAPABILITY) })} data-testid={`membership-documents-permission-${item.user_id}`} /><ShieldCheck className="h-4 w-4 text-[#B5953F]" />Emitir carnets/certificados</label></TableCell><TableCell><Select disabled={locked} value={draft.is_active ? 'active' : 'inactive'} onValueChange={(value) => patch(item.user_id, { is_active: value === 'active' })}><SelectTrigger data-testid={`access-status-${item.user_id}`}><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="active">Activo</SelectItem><SelectItem value="inactive">Inactivo</SelectItem></SelectContent></Select></TableCell><TableCell><Button size="sm" disabled={locked || saving === item.user_id} onClick={() => onSave(item.user_id, draft)} data-testid={`save-access-${item.user_id}`}><Save className="h-4 w-4" />Guardar</Button></TableCell></TableRow>;
    })}</TableBody></Table></div>
  </section>;
};