import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { ShieldCheck, UserRoundCheck, Vote } from 'lucide-react';

import { useAuth } from '../../context/AuthContext';
import { useBoardAccess } from '../../hooks/useBoardAccess';
import { BoardMemberDialog } from '../../components/board/BoardMemberDialog';
import { DoorEmpty, DoorError, DoorLoading, DoorShell } from '../../components/doors/DoorShell';

export default function BoardMembersPage() {
  const { API, getAuthHeaders } = useAuth(); const access = useBoardAccess();
  const [board, setBoard] = useState(null); const [people, setPeople] = useState([]); const [doors, setDoors] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = useCallback(async () => {
    try {
      const detail = await axios.get(`${API}/api/board`, getAuthHeaders()); setBoard(detail.data);
      if (access.full_access) {
        const [persons, doorCatalog] = await Promise.all([axios.get(`${API}/api/cellular/catalog`, getAuthHeaders()), axios.get(`${API}/api/doors/catalog`, getAuthHeaders())]);
        setPeople(persons.data.people || []); setDoors(doorCatalog.data.items || []);
      }
    } catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudieron cargar miembros.'); }
    finally { setLoading(false); }
  }, [API, access.full_access, getAuthHeaders]);
  useEffect(() => { if (!access.loading) load(); }, [access.loading, load]);
  if (loading || access.loading) return <DoorShell eyebrow="Junta Directiva" title="Miembros" description="Cargando membresías..." guideKey="board_dashboard"><DoorLoading /></DoorShell>;
  const activeMembers = (board?.members || []).filter((item) => item.active);
  return <DoorShell eyebrow="Junta Directiva" title="Miembros" description="Información institucional por cargo; los datos pastorales privados quedan fuera de este módulo." guideKey="board_dashboard" actions={access.full_access ? <BoardMemberDialog people={people} positions={board?.positions || []} doors={doors} onSaved={load} /> : null}>{error ? <DoorError message={error} /> : <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{activeMembers.length ? activeMembers.map((member) => <article key={member.membership_id} className="border bg-white p-5" data-testid={`board-member-${member.membership_id}`}><div className="flex items-start justify-between"><UserRoundCheck className="h-6 w-6 text-[#9E8232]" />{member.voting_rights && <span className="flex items-center gap-1 text-xs text-emerald-700"><Vote className="h-3 w-3" />Voto</span>}</div><h2 className="mt-3 text-lg font-semibold text-[#14213D]">{member.person?.name}</h2><p className="text-sm text-slate-500">{member.position?.name}</p><div className="mt-4 border-t pt-3"><p className="flex items-center gap-2 text-xs font-semibold"><ShieldCheck className="h-3 w-3" />Alcance institucional</p><p className="mt-1 text-xs text-slate-500">{member.permissions?.map((item) => item.replace('board.', '')).join(' · ')}</p></div><p className="mt-3 font-mono text-[11px] text-slate-400">Desde {member.started_at}</p></article>) : <DoorEmpty testId="board-members-empty">La Junta aún no tiene membresías activas.</DoorEmpty>}</section>}</DoorShell>;
}