import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Clock3, DoorClosed, Timer } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { AiArtifactsPanel } from '../../components/board/AiArtifactsPanel';
import { BoardAgendaPanel } from '../../components/board/BoardAgendaPanel';
import { BoardAttendancePanel } from '../../components/board/BoardAttendancePanel';
import { BoardDocumentsPanel } from '../../components/board/BoardDocumentsPanel';
import { BoardGovernancePanel } from '../../components/board/BoardGovernancePanel';
import { SecretaryNotesPanel } from '../../components/board/SecretaryNotesPanel';
import { TranscriptMinutesPanel } from '../../components/board/TranscriptMinutesPanel';
import { DoorError, DoorLoading, DoorShell } from '../../components/doors/DoorShell';
import { Button } from '../../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { statusLabel } from '../../lib/displayLabels';

export default function BoardMeetingDetailPage() {
  const { meetingId } = useParams();
  const { API, getAuthHeaders } = useAuth();
  const [meeting, setMeeting] = useState(null); const [members, setMembers] = useState([]); const [error, setError] = useState(''); const [now, setNow] = useState(Date.now());
  const load = useCallback(async () => {
    try {
      const [detail, board] = await Promise.all([axios.get(`${API}/api/board/meetings/${meetingId}`, getAuthHeaders()), axios.get(`${API}/api/board`, getAuthHeaders())]);
      setMeeting(detail.data); setMembers(board.data.members.filter((item) => item.active).map((item) => item.person));
    } catch (e) { setError(e?.response?.data?.detail || 'No se pudo abrir la reunión.'); }
  }, [API, getAuthHeaders, meetingId]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  const elapsed = useMemo(() => meeting?.started_at ? Math.max(0, Math.floor(((meeting.ended_at ? new Date(meeting.ended_at).getTime() : now) - new Date(meeting.started_at).getTime()) / 1000)) : 0, [meeting, now]);
  const close = async () => { try { await axios.post(`${API}/api/board/meetings/${meetingId}/close`, {}, getAuthHeaders()); toast.success('Reunión cerrada y duración registrada'); await load(); } catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo cerrar'); } };
  if (!meeting && !error) return <DoorShell eyebrow="Junta Directiva" title="Reunión" description="Abriendo consola..." guideKey="board_meeting"><DoorLoading /></DoorShell>;
  const clock = `${String(Math.floor(elapsed / 3600)).padStart(2, '0')}:${String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`;
  return <DoorShell eyebrow="Reunión de Junta" title={meeting?.title || 'Reunión'} description={meeting ? `${new Date(meeting.scheduled_at).toLocaleString('es')} · ${meeting.location}` : ''} guideKey="board_meeting" actions={meeting?.status === 'open' ? <Button onClick={close} className="bg-red-700" data-testid="close-board-meeting-button"><DoorClosed className="mr-2 h-4 w-4" />Cerrar reunión</Button> : null}>
    {error ? <DoorError message={error} /> : <>
      <section className="grid gap-3 sm:grid-cols-3">
        <div className="border bg-white p-4"><Timer className="h-4 w-4 text-[#9E8232]" /><b className="mt-2 block font-mono text-2xl" data-testid="board-meeting-live-timer">{clock}</b><span className="text-xs text-slate-500">Duración real</span></div>
        <div className="border bg-white p-4"><Clock3 className="h-4 w-4 text-[#9E8232]" /><b className="mt-2 block text-2xl">{meeting.planned_duration_minutes} min</b><span className="text-xs text-slate-500">Duración prevista</span></div>
        <div className="border bg-white p-4"><b className="block text-2xl uppercase" data-testid="board-meeting-status">{statusLabel(meeting.status)}</b><span className="text-xs text-slate-500">Estado formal</span></div>
      </section>
      <Tabs defaultValue="attendance">
        <TabsList className="grid h-auto w-full grid-cols-3 bg-white p-1 sm:grid-cols-5"><TabsTrigger value="attendance" data-testid="meeting-tab-attendance">Asistencia</TabsTrigger><TabsTrigger value="agenda" data-testid="meeting-tab-agenda">Agenda</TabsTrigger><TabsTrigger value="notes" data-testid="meeting-tab-notes">Notas</TabsTrigger><TabsTrigger value="governance" data-testid="meeting-tab-governance">Votos/Tareas</TabsTrigger><TabsTrigger value="recording" data-testid="meeting-tab-recording">Audio/Minuta</TabsTrigger></TabsList>
        <TabsContent value="attendance"><BoardAttendancePanel meeting={meeting} members={members} onReload={load} /></TabsContent>
        <TabsContent value="agenda"><BoardAgendaPanel meeting={meeting} onReload={load} /></TabsContent>
        <TabsContent value="notes"><SecretaryNotesPanel meetingId={meetingId} /></TabsContent>
        <TabsContent value="governance"><BoardGovernancePanel meeting={meeting} members={members} onReload={load} /></TabsContent>
        <TabsContent value="recording"><div className="space-y-5"><BoardDocumentsPanel meetingId={meetingId} /><TranscriptMinutesPanel meeting={meeting} members={members} onReload={load} /><AiArtifactsPanel artifacts={meeting.ai_artifacts || []} /></div></TabsContent>
      </Tabs>
    </>}
  </DoorShell>;
}