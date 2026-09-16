import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Bot, FileCheck2, RefreshCw, Save, UserRoundCog } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../context/AuthContext';
import { BoardRecorder } from './BoardRecorder';
import { PersonSelect } from '../cellular/CellularFields';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Textarea } from '../ui/textarea';

export const TranscriptMinutesPanel = ({ meeting, members, onReload }) => {
  const { API, getAuthHeaders } = useAuth();
  const [transcript, setTranscript] = useState({ segments: [], mappings: [] });
  const [recordings, setRecordings] = useState([]); const [manual, setManual] = useState(''); const [editing, setEditing] = useState({}); const [aiAck, setAiAck] = useState(false);
  const load = useCallback(async () => {
    const [tx, rec] = await Promise.allSettled([axios.get(`${API}/api/board/meetings/${meeting.meeting_id}/transcript`, getAuthHeaders()), axios.get(`${API}/api/board/meetings/${meeting.meeting_id}/recordings`, getAuthHeaders())]);
    if (tx.status === 'fulfilled') setTranscript(tx.value.data);
    if (rec.status === 'fulfilled') setRecordings(rec.value.data.items || []);
  }, [API, getAuthHeaders, meeting.meeting_id]);
  useEffect(() => { load(); }, [load]);
  const mapSpeaker = async (speaker, personId) => { try { await axios.put(`${API}/api/board/meetings/${meeting.meeting_id}/speaker-mapping`, { speaker_label: speaker, person_id: personId, external_processing_acknowledged: aiAck }, getAuthHeaders()); toast.success('Speaker asociado; derivados en regeneración'); await load(); } catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo asociar'); } };
  const correct = async (segment) => { try { await axios.put(`${API}/api/board/meetings/${meeting.meeting_id}/transcript-segment`, { segment_id: segment.segment_id, text: editing[segment.segment_id] || segment.text, external_processing_acknowledged: aiAck }, getAuthHeaders()); toast.success('Transcript versionado'); await load(); } catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo corregir'); } };
  const generate = async () => { try { await axios.post(`${API}/api/board/meetings/${meeting.meeting_id}/ai-draft`, { external_processing_acknowledged: aiAck }, getAuthHeaders()); toast.success('Borrador IA generado para revisión'); await onReload(); } catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo generar'); } };
  const saveManual = async () => { try { await axios.put(`${API}/api/board/meetings/${meeting.meeting_id}/manual-minute`, { content: manual }, getAuthHeaders()); toast.success('Minuta manual versionada'); await onReload(); } catch (e) { toast.error(e?.response?.data?.detail || 'No se pudo guardar'); } };
  const speakerLabels = [...new Set(transcript.segments.map((item) => item.speaker_label))];
  return <section className="space-y-6" data-testid="transcript-minutes-panel">
    <BoardRecorder meetingId={meeting.meeting_id} enabled={meeting.status === 'open' && meeting.recording_notice_confirmed} onCompleted={load} />
    <div className="border bg-white p-4">
      <div className="flex items-center justify-between"><h2 className="font-semibold">Audio original</h2><Button size="icon" variant="ghost" onClick={load} aria-label="Actualizar audio" data-testid="refresh-transcript-button"><RefreshCw className="h-4 w-4" /></Button></div>
      {recordings.length ? recordings.map((item) => <div key={item.recording_id} className="mt-2 text-xs" data-testid={`board-recording-${item.recording_id}`}><p>{Math.round(item.bytes / 1024)} KB · {item.transcription_status} · SHA {item.sha256?.slice(0, 12)}…</p>{item.transcription_status === 'blocked' && <p className="mt-2 border-l-2 border-amber-500 bg-amber-50 p-2 text-amber-900" data-testid="stt-diarization-blocked-message">Identificación de participantes pendiente de procesamiento STT diarizado.</p>}</div>) : <p className="mt-2 text-xs text-slate-500">Sin grabaciones o sin permiso de audio.</p>}
    </div>
    {speakerLabels.length > 0 && <div className="border bg-white p-4"><h2 className="flex items-center gap-2 font-semibold"><UserRoundCog className="h-4 w-4" />Identificación de speakers</h2><div className="mt-3 grid gap-3 sm:grid-cols-2">{speakerLabels.map((speaker) => <PersonSelect key={speaker} id={`speaker-map-${speaker.replaceAll(' ', '-').toLowerCase()}`} label={speaker} items={members} value={transcript.mappings.find((item) => item.speaker_label === speaker)?.person_id || ''} onChange={(value) => mapSpeaker(speaker, value)} />)}</div></div>}
    <div><h2 className="font-semibold">Transcript versionado</h2><div className="mt-3 space-y-3">{transcript.segments.length ? transcript.segments.map((segment) => <article key={segment.segment_id} className="border bg-white p-4" data-testid={`transcript-segment-${segment.segment_id}`}><p className="text-xs font-semibold text-[#9E8232]">{segment.person?.name || segment.speaker_label} · {Math.floor(segment.start_seconds || 0)}s</p><Textarea value={editing[segment.segment_id] ?? segment.text} onChange={(e) => setEditing((old) => ({ ...old, [segment.segment_id]: e.target.value }))} className="mt-2" data-testid={`transcript-text-${segment.segment_id}`} /><Button size="sm" variant="outline" className="mt-2" onClick={() => correct(segment)} data-testid={`save-transcript-${segment.segment_id}`}><Save className="mr-1 h-3 w-3" />Guardar corrección</Button></article>) : <p className="border border-dashed bg-white p-6 text-center text-sm text-slate-500">El transcript aparecerá cuando se configure y ejecute el proveedor STT diarizado.</p>}</div></div>
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="border bg-white p-4"><h2 className="flex items-center gap-2 font-semibold"><FileCheck2 className="h-4 w-4" />Minuta manual</h2><Textarea value={manual} onChange={(e) => setManual(e.target.value)} className="mt-3 min-h-52" data-testid="manual-minute-editor" /><Button onClick={saveManual} disabled={!manual.trim()} className="mt-3" data-testid="save-manual-minute-button">Guardar versión manual</Button></div>
      <div className="border bg-white p-4"><h2 className="flex items-center gap-2 font-semibold"><Bot className="h-4 w-4" />Borrador IA</h2><p className="mt-2 text-sm text-slate-500">Las fuentes de esta reunión se procesarán mediante el proveedor externo GPT con aliases de identidad. Notas humanas pueden contener datos sensibles. El resultado nunca se publica automáticamente.</p><label className="mt-3 flex items-start gap-2 border p-3 text-xs"><Checkbox checked={aiAck} onCheckedChange={setAiAck} data-testid="ai-external-processing-acknowledgement" />Confirmo el procesamiento externo para generar este borrador revisable.</label><Button onClick={generate} disabled={!aiAck} className="mt-3 bg-[#14213D]" data-testid="generate-ai-minute-button"><Bot className="mr-2 h-4 w-4" />Confirmar y generar</Button><div className="mt-4 space-y-2">{meeting.minutes.filter((item) => item.minute_type === 'ai_draft').map((item) => <div key={item.minute_id} className="border p-3 text-xs" data-testid={`ai-minute-${item.minute_id}`}>Borrador IA v{item.version} · revisión humana pendiente</div>)}</div></div>
    </div>
  </section>;
};