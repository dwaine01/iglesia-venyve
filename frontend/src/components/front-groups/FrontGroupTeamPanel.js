import React, { useState } from 'react';
import axios from 'axios';
import { ArrowRightLeft, BadgeCheck, Loader2, UserCog, UserMinus } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { isPastoralAuthority } from '../../lib/accessControl';
import { apiErrorMessage } from '../../lib/apiErrors';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { CreateAccessInviteDialog } from './CreateAccessInviteDialog';
import { PersonQuickPicker } from './PersonQuickPicker';

const ROLE_LABELS = { leader: 'Líder', co_leader: 'Colíder', member: 'Miembro', mentor: 'Mentoría', team: 'Miembro' };

export const FrontGroupTeamPanel = ({ group, assignments, groups = [], canManage, canSupport = false, onChanged }) => {
  const { API, getAuthHeaders, user } = useAuth();
  const canAssign = canManage || canSupport;
  const [selectedPerson, setSelectedPerson] = useState(null); const [role, setRole] = useState('member'); const [reason, setReason] = useState('Asignación estructural'); const [busy, setBusy] = useState(false);
  const [endingId, setEndingId] = useState(''); const [endReason, setEndReason] = useState('');
  const [transferTarget, setTransferTarget] = useState({}); const [transferReason, setTransferReason] = useState('');

  const submit = async () => {
    if (!selectedPerson) return;
    setBusy(true);
    try {
      const endpoint = role === 'leader' ? `${API}/api/front-groups/${group.front_group_id}/leader`
        : role === 'co_leader' ? `${API}/api/front-groups/${group.front_group_id}/co-leader`
        : `${API}/api/front-groups/${group.front_group_id}/members`;
      const payload = role === 'leader' || role === 'co_leader' ? { person_id: selectedPerson.person_id, reason } : { person_id: selectedPerson.person_id, role, notes: reason };
      await axios.post(endpoint, payload, getAuthHeaders());
      toast.success('Estructura actualizada'); setSelectedPerson(null); await onChanged();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo actualizar el equipo')); } finally { setBusy(false); }
  };

  const endMember = async (personId) => {
    if (endReason.trim().length < 3) { toast.error('Indique un motivo'); return; }
    setBusy(true);
    try {
      await axios.delete(`${API}/api/front-groups/${group.front_group_id}/members/${personId}`, { ...getAuthHeaders(), data: { reason: endReason } });
      toast.success('Integrante dado de baja'); setEndingId(''); setEndReason(''); await onChanged();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo dar de baja')); } finally { setBusy(false); }
  };

  const transferMember = async (personId) => {
    const toGroupId = transferTarget[personId];
    if (!toGroupId) { toast.error('Seleccione el grupo destino'); return; }
    if (transferReason.trim().length < 3) { toast.error('Indique un motivo'); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/api/front-groups/${group.front_group_id}/members/transfer`, { person_id: personId, to_group_id: toGroupId, reason: transferReason }, getAuthHeaders());
      toast.success('Integrante trasladado'); setTransferReason(''); await onChanged();
    } catch (error) { toast.error(apiErrorMessage(error, 'No se pudo trasladar')); } finally { setBusy(false); }
  };

  const otherGroups = groups.filter((item) => item.front_group_id !== group.front_group_id && item.permissions?.manage);

  return <div className="grid gap-6 xl:grid-cols-[1fr_360px]" data-testid="front-group-team-panel">
    <section className="border border-slate-200 bg-white"><header className="border-b border-slate-200 px-5 py-4"><h3 className="font-['Spectral'] text-xl font-semibold">Equipo e historial</h3></header>
      {assignments.length ? <div className="divide-y divide-slate-200">{assignments.map((item) => <div key={item.assignment_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4" data-testid={`front-group-assignment-${item.assignment_id}`}>
        <div className="min-w-0">
          <b>{item.person_name || item.person_id}</b>
          <span className="block text-xs text-slate-500">{ROLE_LABELS[item.role] || item.role} · {item.notes || 'Sin nota'}</span>
          {item.active && !item.has_account && ['leader', 'co_leader'].includes(item.role) && isPastoralAuthority(user) && <div className="mt-1.5"><CreateAccessInviteDialog personId={item.person_id} personName={item.person_name || 'esta persona'} /></div>}
        </div>
        <div className="flex items-center gap-2">
          <span className={`border px-2 py-1 text-[10px] uppercase ${item.active ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>{item.active ? 'Activo' : 'Histórico'}</span>
          {item.active && canManage && <>
            <Button size="sm" variant="outline" onClick={() => { setEndingId(endingId === item.assignment_id ? '' : item.assignment_id); setEndReason(''); }} data-testid={`front-group-end-member-toggle-${item.person_id}`}><UserMinus className="h-3.5 w-3.5" />Baja</Button>
            {otherGroups.length > 0 && <Select value={transferTarget[item.person_id] || ''} onValueChange={(value) => setTransferTarget((current) => ({ ...current, [item.person_id]: value }))}>
              <SelectTrigger className="h-9 w-40" data-testid={`front-group-transfer-select-${item.person_id}`}><SelectValue placeholder="Trasladar a…" /></SelectTrigger>
              <SelectContent className="bg-white">{otherGroups.map((destination) => <SelectItem key={destination.front_group_id} value={destination.front_group_id}>{destination.display_name || destination.name}</SelectItem>)}</SelectContent>
            </Select>}
          </>}
        </div>
        {endingId === item.assignment_id && <div className="flex w-full items-center gap-2 pt-2" data-testid={`front-group-end-member-form-${item.person_id}`}>
          <Input value={endReason} onChange={(event) => setEndReason(event.target.value)} placeholder="Motivo de la baja" className="h-9" data-testid={`front-group-end-member-reason-${item.person_id}`} />
          <Button size="sm" disabled={busy} onClick={() => endMember(item.person_id)} className="bg-red-700 text-white hover:bg-red-800" data-testid={`front-group-end-member-confirm-${item.person_id}`}>Confirmar</Button>
        </div>}
        {transferTarget[item.person_id] && <div className="flex w-full items-center gap-2 pt-2" data-testid={`front-group-transfer-form-${item.person_id}`}>
          <Input value={transferReason} onChange={(event) => setTransferReason(event.target.value)} placeholder="Motivo del traslado" className="h-9" data-testid={`front-group-transfer-reason-${item.person_id}`} />
          <Button size="sm" disabled={busy} onClick={() => transferMember(item.person_id)} className="bg-slate-900" data-testid={`front-group-transfer-confirm-${item.person_id}`}><ArrowRightLeft className="h-3.5 w-3.5" />Confirmar</Button>
        </div>}
      </div>)}</div> : <p className="p-8 text-center text-sm text-slate-500">No hay asignaciones.</p>}
    </section>
    {canAssign && <section className="space-y-4 border border-slate-200 bg-white p-5" data-testid="front-group-team-assignment-form">
      <h3 className="flex items-center gap-2 font-['Spectral'] text-xl font-semibold"><UserCog className="h-5 w-5 text-amber-700" />Agregar integrante</h3>
      <div><Label>Persona 360</Label>{selectedPerson ? <div className="flex items-center justify-between border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm"><span>{selectedPerson.nombre} {selectedPerson.apellido}</span><button type="button" onClick={() => setSelectedPerson(null)} className="text-xs text-emerald-700 underline">Cambiar</button></div> : <PersonQuickPicker groupId={group.front_group_id} onPicked={setSelectedPerson} role={role === 'mentor' ? 'mentor' : 'member'} />}</div>
      <div><Label>Responsabilidad</Label><Select value={role} onValueChange={setRole}><SelectTrigger data-testid="front-group-role-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="member">Miembro</SelectItem><SelectItem value="mentor">Mentor</SelectItem>{canManage && <SelectItem value="leader">Líder principal</SelectItem>}{canManage && <SelectItem value="co_leader">Colíder</SelectItem>}</SelectContent></Select></div>
      <div><Label htmlFor="fg-team-reason">Motivo</Label><Input id="fg-team-reason" value={reason} onChange={(event) => setReason(event.target.value)} data-testid="front-group-assignment-reason-input" /></div>
      <Button onClick={submit} disabled={busy || !selectedPerson || reason.trim().length < 2} className="w-full bg-slate-900" data-testid="front-group-assign-button">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <BadgeCheck className="h-4 w-4" />}Asignar</Button>
    </section>}
  </div>;
};
