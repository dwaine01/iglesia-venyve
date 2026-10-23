import React, { useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { Award, Loader2, UserRound, Users } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { apiErrorMessage } from '../../lib/apiErrors';
import { canViewDirectory } from '../../lib/accessControl';

const STATUS = { pending_formation: 'aún no crea su grupo', active: 'grupo creado', inactive: 'grupo inactivo' };

function PrivilegeBadge({ privilege }) {
  if (!privilege) return null;
  return (
    <p className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-[#7A5F22]" data-testid="roster-leader-privilege">
      <Award className="h-3.5 w-3.5" />{privilege.as === 'co_leader' ? 'Colíder' : 'Líder'} de Grupo Frontal · {STATUS[privilege.status] || privilege.status}
      {privilege.assigned_by_name && <span className="text-slate-500">· asignado por {privilege.assigned_by_name}</span>}
    </p>
  );
}

// ETAPA 5C: todas las personas y parejas del grupo; quien administra puede
// asignar el privilegio "Líder de Grupo Frontal" (en pareja: a uno o a ambos).
export function GroupRosterView({ groupId, roster, canManage, onChanged, onShowActivity, onOpenGroup, title = 'Integrantes' }) {
  const { API, getAuthHeaders, user } = useAuth();
  const [busy, setBusy] = useState('');
  const canOpenProfiles = canViewDirectory(user);

  const grant = async (personId, coLeaderId = null) => {
    setBusy(personId);
    try {
      await axios.post(`${API}/api/front-groups/${groupId}/leader-privilege`, { person_id: personId, co_leader_person_id: coLeaderId }, getAuthHeaders());
      toast.success('Privilegio de líder asignado: ya puede crear su grupo desde su portal');
      await onChanged();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'No se pudo asignar el privilegio de líder'));
    } finally { setBusy(''); }
  };

  if (!roster) return null;
  const { totals, entries } = roster;
  const PersonRow = ({ person }) => (
    <div className="min-w-0">
      <p className="flex items-center gap-1.5 text-sm text-slate-800"><UserRound className="h-3.5 w-3.5 shrink-0 text-slate-400" />
        {canOpenProfiles ? <Link to={`/personas/${person.person_id}`} className="truncate underline-offset-2 hover:underline">{person.name || 'Persona'}</Link> : <span className="truncate">{person.name || 'Persona'}</span>}
        {!person.has_account && <span className="shrink-0 text-[10px] text-slate-400">(sin cuenta)</span>}
      </p>
      <PrivilegeBadge privilege={person.leader_privilege} />
      {onOpenGroup && person.leader_privilege && <button type="button" onClick={() => onOpenGroup(person.leader_privilege.front_group_id)} className="mr-3 mt-1 min-h-9 text-xs font-semibold text-[#7A5F22] underline" data-testid={`roster-open-group-${person.person_id}`}>Ver su grupo →</button>}
      {onShowActivity && <button type="button" onClick={() => onShowActivity(person)} className="mt-1 min-h-9 text-xs font-semibold text-[#101D36] underline" data-testid={`roster-activity-${person.person_id}`}>Ver actividad</button>}
    </div>
  );
  const GrantButton = ({ label, onClick, testId }) => <button type="button" disabled={Boolean(busy)} onClick={onClick} className="min-h-10 rounded-md border border-[#D9CFB4] bg-white px-3 text-xs font-semibold text-[#7A5F22] hover:bg-[#FBF6EA] disabled:opacity-50" data-testid={testId}>{busy ? <Loader2 className="inline h-3.5 w-3.5 animate-spin" /> : label}</button>;

  return (
    <section className="space-y-3 rounded-xl border border-[#E8E5DE] bg-white p-4 shadow-sm" data-testid="group-roster-view">
      <div className="flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 font-semibold text-[#101D36]"><Users className="h-4 w-4 text-[#9A7A2F]" />{title}</h3>
        <p className="text-xs text-slate-500" data-testid="group-roster-totals">{totals.people} {totals.people === 1 ? 'persona' : 'personas'} · {totals.pairs} {totals.pairs === 1 ? 'pareja' : 'parejas'} · {totals.individuals} {totals.individuals === 1 ? 'individual' : 'individuales'}</p>
      </div>
      {entries.length ? (
        <ul className="space-y-2">
          {entries.map((entry) => {
            const [first, second] = entry.people;
            const isPair = entry.type === 'pair' && second;
            return (
              <li key={entry.pair_id || first.person_id} className={`rounded-lg border p-3 ${isPair ? 'border-[#D9CFB4] bg-[#FBF6EA]' : 'border-[#EEECE6]'}`} data-testid="group-roster-entry">
                {isPair && <p className="mb-1 text-[10px] font-semibold uppercase text-[#7A5F22]">Pareja</p>}
                <div className="space-y-2">{entry.people.map((person) => <PersonRow key={person.person_id} person={person} />)}</div>
                {canManage && (isPair ? (
                  !first.leader_privilege && !second.leader_privilege && (
                    <div className="mt-3 grid gap-2 sm:grid-cols-3" data-testid="group-roster-pair-actions">
                      <GrantButton label={`Líder: ${first.name?.split(' ')[0] || 'primero'}`} onClick={() => grant(first.person_id)} testId="grant-leader-first" />
                      <GrantButton label={`Líder: ${second.name?.split(' ')[0] || 'segundo'}`} onClick={() => grant(second.person_id)} testId="grant-leader-second" />
                      <GrantButton label="Ambos (líder y colíder)" onClick={() => grant(first.person_id, second.person_id)} testId="grant-leader-both" />
                    </div>
                  )
                ) : !first.leader_privilege && <div className="mt-3"><GrantButton label="Asignar como líder" onClick={() => grant(first.person_id)} testId="grant-leader-individual" /></div>)}
              </li>
            );
          })}
        </ul>
      ) : <p className="text-sm text-slate-400">Aún no hay integrantes.</p>}
    </section>
  );
}
