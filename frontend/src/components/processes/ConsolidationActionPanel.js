import React, { useState } from 'react';
import axios from 'axios';
import { BadgeCheck, CheckCircle2, Loader2, RefreshCw, Send, UserRoundCheck } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { hasCapability } from '../../lib/accessControl';

export const ConsolidationActionPanel = ({ journey, assignees, onUpdated, onTasksChanged }) => {
  const { API, getAuthHeaders, user } = useAuth();
  const [busy, setBusy] = useState('');
  const [mentorId, setMentorId] = useState('');
  const [notes, setNotes] = useState('');
  const [certificateDelivery, setCertificateDelivery] = useState('delivered');
  const [cardDelivery, setCardDelivery] = useState('pending');
  const current = journey.stages?.find((stage) => stage.stage_key === journey.current_stage_key);
  const call = async (key, request) => {
    setBusy(key);
    try { await request(); toast.success('Expediente actualizado'); setNotes(''); await onUpdated(); }
    catch (error) { toast.error(typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : error?.response?.data?.detail?.message || 'No se pudo completar la acción'); }
    finally { setBusy(''); }
  };
  const toggleTask = async (task, checked) => {
    const completed = checked === true;
    const previousTasks = current.tasks || [];
    const optimisticTasks = previousTasks.map((item) => item.task_id === task.task_id ? { ...item, completed } : item);
    onTasksChanged(optimisticTasks);
    setBusy(task.task_id);
    try {
      const response = await axios.put(`${API}/api/processes/enrollments/${journey.enrollment_id}/stages/${current.stage_key}/tasks/${task.task_id}`, { completed }, getAuthHeaders());
      onTasksChanged(response.data.tasks || optimisticTasks);
      toast.success(completed ? 'Tarea completada' : 'Tarea reabierta');
    } catch (error) {
      onTasksChanged(previousTasks);
      toast.error(typeof error?.response?.data?.detail === 'string' ? error.response.data.detail : error?.response?.data?.detail?.message || 'No se pudo actualizar la tarea');
    } finally { setBusy(''); }
  };
  const completeStage = () => call('complete-stage', () => axios.put(`${API}/api/processes/enrollments/${journey.enrollment_id}/stages/${current.stage_key}`, { status: 'completed', attendance: current.attendance === 'pending' ? 'present' : current.attendance }, getAuthHeaders()));
  const canAccept = hasCapability(user, 'membership.acceptance.manage');
  const canTransfer = hasCapability(user, 'consolidation.mentor.transfer');
  const canCloseRetreat = hasCapability(user, 'consolidation.retreat.close');
  if (!current) return null;
  return <aside className="space-y-5 border border-slate-200 bg-white p-5" data-testid="consolidation-action-panel">
    <div><p className="font-mono text-[10px] font-semibold uppercase text-amber-700">Etapa actual</p><h2 className="font-['Spectral'] text-2xl font-semibold">{current.stage_name}</h2></div>
    <div className="space-y-2">{current.tasks?.map((task) => <label key={task.task_id} className="flex items-start gap-3 border border-slate-100 p-3 text-sm"><Checkbox checked={task.completed} disabled={Boolean(busy)} onCheckedChange={(checked) => toggleTask(task, checked)} data-testid={`stage-task-${task.task_id}`} /><span className="min-w-0 flex-1"><b className="block">{task.label}</b>{task.required && <small className="text-slate-500">Requerida</small>}</span>{busy === task.task_id && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-amber-700" data-testid={`stage-task-saving-${task.task_id}`} />}</label>)}</div>
    {journey.current_stage_key === 'visitor_followup' && <div className="space-y-3 border-t pt-4"><Label>Mentor al iniciar</Label><Select value={mentorId} onValueChange={setMentorId}><SelectTrigger data-testid="visitor-start-mentor-select"><SelectValue placeholder="Seleccionar mentor" /></SelectTrigger><SelectContent className="bg-white">{assignees.map((item) => <SelectItem key={item.person_id} value={item.person_id}>{item.name}</SelectItem>)}</SelectContent></Select><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Respuesta y resultado del seguimiento" data-testid="visitor-start-result-input" /><Button disabled={!mentorId || !notes || Boolean(busy)} onClick={() => call('start', () => axios.post(`${API}/api/processes/consolidation/${journey.enrollment_id}/start`, { mentor_person_id: mentorId, response_result: notes }, getAuthHeaders()))} data-testid="visitor-start-process-button"><Send className="h-4 w-4" />Iniciar MCD</Button></div>}
    {journey.current_stage_key === 'welcome_party' && <div className="space-y-4 border-t pt-4">
      <div className="grid gap-2 sm:grid-cols-2"><Button variant="outline" disabled={Boolean(busy)} onClick={() => call('evaluate', () => axios.post(`${API}/api/processes/consolidation/${journey.enrollment_id}/mentor/evaluate`, {}, getAuthHeaders()))} data-testid="evaluate-lbs-mentor-button"><UserRoundCheck className="h-4 w-4" />Evaluar mentor LBS</Button>{canAccept && <Button variant="outline" disabled={Boolean(busy) || Boolean(journey.membership?.acceptance_signed_at)} onClick={() => call('acceptance', () => axios.post(`${API}/api/processes/consolidation/${journey.enrollment_id}/membership-acceptance`, { notes: notes || null }, getAuthHeaders()))} data-testid="membership-acceptance-button"><BadgeCheck className="h-4 w-4" />{journey.membership?.acceptance_signed_at ? `Miembro ${journey.membership.member_number}` : 'Firmó Carta'}</Button>}</div>
      {journey.mentor_transfer_required && canTransfer && <div className="space-y-2 border border-red-200 bg-red-50 p-3"><b className="text-sm text-red-800">Transferencia LBS requerida</b><Select value={mentorId} onValueChange={setMentorId}><SelectTrigger data-testid="mentor-transfer-select"><SelectValue placeholder="Nuevo mentor autorizado" /></SelectTrigger><SelectContent className="bg-white">{assignees.map((item) => <SelectItem key={item.person_id} value={item.person_id}>{item.name}</SelectItem>)}</SelectContent></Select><Input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Motivo de transferencia" data-testid="mentor-transfer-reason-input" /><Button disabled={!mentorId || !notes || Boolean(busy)} onClick={() => call('transfer', () => axios.post(`${API}/api/processes/consolidation/${journey.enrollment_id}/mentor/transfer`, { new_mentor_person_id: mentorId, reason: notes }, getAuthHeaders()))} data-testid="mentor-transfer-button"><RefreshCw className="h-4 w-4" />Transferir formalmente</Button></div>}
    </div>}
    {journey.current_stage_key === 'retreat' && canCloseRetreat && <div className="space-y-3 border-t pt-4"><div className="space-y-2"><Label>Entrega de certificado</Label><Select value={certificateDelivery} onValueChange={setCertificateDelivery}><SelectTrigger data-testid="retreat-certificate-status-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="delivered">Entregado</SelectItem><SelectItem value="pending_exception">Pendiente con excepción</SelectItem></SelectContent></Select></div><div className="space-y-2"><Label>Entrega de carnet</Label><Select value={cardDelivery} onValueChange={setCardDelivery}><SelectTrigger data-testid="retreat-card-status-select"><SelectValue /></SelectTrigger><SelectContent className="bg-white"><SelectItem value="delivered">Entregado</SelectItem><SelectItem value="pending">Pendiente</SelectItem><SelectItem value="not_applicable">No aplica</SelectItem></SelectContent></Select></div><Textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Observaciones de entrega" data-testid="retreat-delivery-notes-input" /><Button disabled={Boolean(busy)} onClick={() => call('retreat', () => axios.post(`${API}/api/processes/consolidation/${journey.enrollment_id}/retreat-close`, { certificate_delivery_status: certificateDelivery, card_delivery_status: cardDelivery, delivery_notes: notes || null }, getAuthHeaders()))} className="bg-emerald-700 text-white hover:bg-emerald-800" data-testid="retreat-close-button"><CheckCircle2 className="h-4 w-4" />Cerrar Retiro y abrir Discipulado</Button></div>}
    {!['visitor_followup', 'retreat', 'discipleship_handoff'].includes(journey.current_stage_key) && <Button disabled={Boolean(busy)} onClick={completeStage} className="w-full bg-slate-900 text-white hover:bg-slate-800" data-testid="complete-current-stage-button">{busy === 'complete-stage' ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}Completar etapa</Button>}
  </aside>;
};