import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { CalendarClock, CheckSquare2, FileText, Gavel, UsersRound, Vote } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { DoorEmpty, DoorError, DoorLoading, DoorShell } from '../../components/doors/DoorShell';
import { displayLabel, meetingModalityLabel } from '../../lib/displayLabels';

const metrics = [['members_current', 'Miembros actuales', UsersRound], ['meetings_held', 'Reuniones realizadas', Gavel], ['open_actions', 'Acuerdos/tareas abiertas', CheckSquare2], ['pending_votes', 'Votaciones pendientes', Vote], ['draft_minutes', 'Minutas en borrador', FileText]];

export default function BoardDashboardPage() {
  const { API, getAuthHeaders } = useAuth(); const [data, setData] = useState(null); const [board, setBoard] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = useCallback(async () => { try { const [dash, detail] = await Promise.all([axios.get(`${API}/api/board/dashboard`, getAuthHeaders()), axios.get(`${API}/api/board`, getAuthHeaders())]); setData(dash.data); setBoard(detail.data); } catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudo cargar la Junta.'); } finally { setLoading(false); } }, [API, getAuthHeaders]);
  useEffect(() => { load(); }, [load]);
  if (loading) return <DoorShell eyebrow="Junta Directiva" title="Gobierno institucional" description="Cargando..." guideKey="board_dashboard"><DoorLoading /></DoorShell>;
  return <DoorShell eyebrow="Junta Directiva" title={board?.name || 'Junta Directiva'} description="Opiniones, votaciones, acuerdos, minutas y reuniones con trazabilidad completa." guideKey="board_dashboard">{error ? <DoorError message={error} /> : <>
    <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{metrics.map(([key, label, Icon]) => <div key={key} className="border bg-white p-4"><Icon className="h-5 w-5 text-[#9E8232]" /><b className="mt-2 block text-3xl" data-testid={`board-metric-${key}`}>{data[key]}</b><span className="text-xs text-slate-500">{label}</span></div>)}</section>
    <section className="grid gap-4 lg:grid-cols-[1fr_.7fr]"><div><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Próximas reuniones</h2><Link to="/junta/reuniones" className="text-sm font-semibold text-blue-700" data-testid="board-open-meetings-link">Ver todas</Link></div><div className="mt-3 space-y-3">{data.upcoming.length ? data.upcoming.map((meeting) => <Link key={meeting.meeting_id} to={`/junta/reuniones/${meeting.meeting_id}`} className="flex items-center justify-between border bg-white p-4" data-testid={`board-upcoming-${meeting.meeting_id}`}><span><b className="block">{meeting.title}</b><span className="text-xs text-slate-500">{new Date(meeting.scheduled_at).toLocaleString('es')} · {meetingModalityLabel(meeting.modality)}</span></span><CalendarClock className="h-5 w-5 text-[#9E8232]" /></Link>) : <DoorEmpty testId="board-upcoming-empty">No hay reuniones programadas.</DoorEmpty>}</div></div><div><h2 className="text-lg font-semibold">Gobierno actual</h2><div className="mt-3 border bg-white p-4"><p className="text-sm">Quórum: <b>{board.quorum_rule.value}{board.quorum_rule.type === 'percentage' ? '%' : ' miembros'}</b></p><p className="mt-2 text-sm">Votación: <b>{displayLabel(board.voting_rule.type)}</b></p><Link to="/junta/miembros" className="mt-5 inline-flex text-sm font-semibold text-blue-700" data-testid="board-open-members-link">Administrar miembros y Puertas</Link></div></div></section>
  </>}</DoorShell>;
}