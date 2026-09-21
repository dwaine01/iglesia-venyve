import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { BookHeart, CheckCircle2, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { ProcessError, ProcessLoading, ProcessShell } from '../../components/processes/ProcessShell';
import { Button } from '../../components/ui/button';
import { Checkbox } from '../../components/ui/checkbox';

export default function DiscipleshipPage() {
  const [searchParams] = useSearchParams();
  const requestedPersonId = searchParams.get('person');
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { const response = await axios.get(`${API}/api/processes/enrollments?process_key=discipleship`, getAuthHeaders()); const loaded = response.data.items || []; const requested = loaded.find((item) => item.person_id === requestedPersonId); setItems(loaded); setSelected((current) => requested || current || loaded[0] || null); setError(''); }
    catch (requestError) { setError(requestError?.response?.data?.detail || 'No se pudo cargar Discipulado'); }
    finally { setLoading(false); }
  }, [API, getAuthHeaders, requestedPersonId]);
  const loadDetail = useCallback(async () => {
    if (!selected) return setDetail(null);
    const response = await axios.get(`${API}/api/processes/enrollments/${selected.enrollment_id}`, getAuthHeaders()); setDetail(response.data);
  }, [API, getAuthHeaders, selected]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadDetail().catch(() => setDetail(null)); }, [loadDetail]);
  const current = detail?.stages?.find((stage) => stage.stage_key === detail.current_stage_key);
  const act = async (key, request) => { setBusy(key); try { await request(); toast.success('Discipulado actualizado'); await load(); await loadDetail(); } catch (requestError) { toast.error(requestError?.response?.data?.detail || 'No se pudo actualizar'); } finally { setBusy(''); } };
  return <ProcessShell title="Educación / Discipulado" eyebrow="Después del Retiro" description="El expediente se abre automáticamente al cerrar Consolidación y conserva la referencia al recorrido anterior.">
    {loading ? <ProcessLoading /> : error ? <ProcessError message={error} /> : <div className="grid gap-6 lg:grid-cols-[340px_1fr]"><aside className="space-y-2">{items.map((item) => <button key={item.enrollment_id} onClick={() => setSelected(item)} className={`w-full border p-4 text-left ${selected?.enrollment_id === item.enrollment_id ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200 bg-white'}`} data-testid={`discipleship-select-${item.enrollment_id}`}><b className="block font-['Spectral'] text-lg">{item.person?.name}</b><span className="text-xs text-slate-500">{item.current_stage?.stage_name} · {item.progress_pct || 0}%</span></button>)}{!items.length && <div className="border border-dashed bg-white p-8 text-center text-sm text-slate-500" data-testid="discipleship-empty-state">Los expedientes aparecerán al cerrar Retiro.</div>}</aside><section className="border bg-white p-5">{!detail ? <p className="text-sm text-slate-500">Seleccione un expediente.</p> : <div className="space-y-6"><div><BookHeart className="h-6 w-6 text-emerald-700" /><h2 className="mt-3 font-['Spectral'] text-3xl font-semibold">{detail.person?.name}</h2><p className="text-sm text-slate-500">{detail.current_stage?.stage_name} · enlazado a Consolidación</p></div><div className="grid gap-2 sm:grid-cols-5">{detail.stages.map((stage) => <div key={stage.stage_key} className={`border p-2 text-center text-xs ${stage.status === 'completed' ? 'border-emerald-500 bg-emerald-50' : stage.stage_key === detail.current_stage_key ? 'border-amber-500 bg-amber-50' : 'border-slate-200'}`}>{stage.stage_name}</div>)}</div>{current && <div className="space-y-3"><h3 className="font-semibold">Tareas de {current.stage_name}</h3>{current.tasks.map((task) => <label key={task.task_id} className="flex items-center gap-3 border p-3 text-sm"><Checkbox checked={task.completed} disabled={Boolean(busy)} onCheckedChange={(checked) => act(task.task_id, () => axios.put(`${API}/api/processes/enrollments/${detail.enrollment_id}/stages/${current.stage_key}/tasks/${task.task_id}`, { completed: checked }, getAuthHeaders()))} data-testid={`discipleship-task-${task.task_id}`} />{task.label}</label>)}<Button disabled={Boolean(busy)} onClick={() => act('complete', () => axios.put(`${API}/api/processes/enrollments/${detail.enrollment_id}/stages/${current.stage_key}`, { status: 'completed' }, getAuthHeaders()))} data-testid="discipleship-complete-stage-button">{busy === 'complete' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}Completar etapa</Button></div>}</div>}</section></div>}
  </ProcessShell>;
}