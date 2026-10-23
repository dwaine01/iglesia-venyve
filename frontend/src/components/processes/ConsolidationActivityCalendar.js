import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { CalendarClock, CheckCircle2, Loader2, PackageCheck, PhoneMissed, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';

import { useAuth } from '../../context/AuthContext';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../ui/accordion';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../ui/dialog';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { errorDetailText } from '../../lib/errorText';

const STAGE_ORDER = ['mcd', 'npt', 'lbs_1', 'lbs_2', 'lbs_3'];
const STAGE_LABEL = { mcd: 'S3 · Mi Conexión con Dios', npt: 'S4 · Nací Para Triunfar', lbs_1: 'S5 · LBS Liberación', lbs_2: 'S6 · LBS Bendición', lbs_3: 'S7 · LBS Sanidad' };
const BOOK_STAGE = new Set(['mcd', 'npt']);

const STATUS_BADGE = {
  pending: { label: 'Pendiente', className: 'bg-slate-100 text-slate-600' },
  done: { label: 'Realizada', className: 'bg-emerald-100 text-emerald-700' },
  no_answer: { label: 'Sin respuesta', className: 'bg-amber-100 text-amber-700' },
  rescheduled: { label: 'Reprogramada', className: 'bg-sky-100 text-sky-700' },
};

const formatDate = (isoDate) => {
  if (!isoDate) return '—';
  const [y, m, d] = isoDate.split('-');
  return `${d}/${m}/${y}`;
};

export const ConsolidationActivityCalendar = ({ enrollmentId, currentStageKey, canRegister }) => {
  const { API, getAuthHeaders } = useAuth();
  const [items, setItems] = useState(null);
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState(null);
  const [form, setForm] = useState({ status: 'done', note: '', next_step: '', rescheduled_date: '', deliver_book: false });
  const [saving, setSaving] = useState(false);

  const load = () => {
    setLoading(true);
    axios.get(`${API}/api/processes/consolidation/${enrollmentId}/activities`, getAuthHeaders())
      .then((response) => setItems(response.data.items || []))
      .catch((error) => toast.error(errorDetailText(error, 'No se pudo cargar el calendario de actividades')))
      .finally(() => setLoading(false));
  };

  useEffect(() => { if (enrollmentId) load(); }, [API, enrollmentId]); // eslint-disable-line react-hooks/exhaustive-deps

  const byStage = useMemo(() => {
    const grouped = {};
    (items || []).forEach((item) => { (grouped[item.stage_key] ||= []).push(item); });
    return grouped;
  }, [items]);

  const openRegister = (activity) => {
    setActive(activity);
    setForm({ status: 'done', note: '', next_step: '', rescheduled_date: '', deliver_book: false });
  };

  const submit = async () => {
    if (form.status === 'rescheduled' && !form.rescheduled_date) { toast.error('Indique la nueva fecha para reprogramar'); return; }
    setSaving(true);
    try {
      const payload = { status: form.status, note: form.note || null, next_step: form.next_step || null };
      if (form.status === 'rescheduled') payload.rescheduled_date = form.rescheduled_date;
      if (BOOK_STAGE.has(active.stage_key)) payload.deliver_book = form.deliver_book;
      const response = await axios.put(`${API}/api/processes/consolidation/activities/${active.activity_id}/result`, payload, getAuthHeaders());
      setItems((current) => current.map((item) => (item.activity_id === active.activity_id ? response.data : item)));
      toast.success('Actividad registrada');
      setActive(null);
    } catch (error) {
      toast.error(errorDetailText(error, 'No se pudo registrar la actividad'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="border bg-white p-5" data-testid="consolidation-activity-calendar-loading"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>;
  if (!items || items.length === 0) return null;

  return (
    <section className="border bg-white p-5" data-testid="consolidation-activity-calendar">
      <div className="flex items-center gap-2"><CalendarClock className="h-5 w-5 text-amber-600" /><h2 className="font-['Spectral'] text-2xl font-semibold">Calendario individual de actividades</h2></div>
      <p className="mt-1 text-xs text-slate-500">Fecha y horario propios de este discípulo; el avance solo cuenta las actividades "Realizada".</p>
      <Accordion type="single" collapsible defaultValue={currentStageKey} className="mt-4">
        {STAGE_ORDER.filter((stageKey) => byStage[stageKey]?.length).map((stageKey) => {
          const stageItems = byStage[stageKey];
          const done = stageItems.filter((item) => item.status === 'done').length;
          return (
            <AccordionItem key={stageKey} value={stageKey} data-testid={`activity-stage-${stageKey}`}>
              <AccordionTrigger data-testid={`activity-stage-trigger-${stageKey}`}>
                <span className="flex-1 text-left">{STAGE_LABEL[stageKey]}{stageKey === currentStageKey && <Badge className="ml-2 bg-amber-100 text-amber-700">Etapa actual</Badge>}</span>
                <span className="mr-2 text-xs text-slate-500">{done}/{stageItems.length} realizadas</span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-1.5">
                  {stageItems.map((activity) => {
                    const badge = STATUS_BADGE[activity.status];
                    return (
                      <div key={activity.activity_id} className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 py-2 text-sm" data-testid={`activity-row-${activity.activity_id}`}>
                        <div className="min-w-0 flex-1">
                          <b className="block">{activity.title}</b>
                          <span className="text-xs text-slate-500">{formatDate(activity.scheduled_date)} · {activity.moment_label}{activity.note ? ` · "${activity.note}"` : ''}</span>
                        </div>
                        <Badge className={badge.className} data-testid={`activity-status-${activity.activity_id}`}>{badge.label}</Badge>
                        {activity.book_delivery_movement_id && <Badge className="bg-indigo-100 text-indigo-700"><PackageCheck className="mr-1 h-3 w-3" />Libro entregado</Badge>}
                        {canRegister && activity.status === 'pending' && (
                          <Button size="sm" variant="outline" onClick={() => openRegister(activity)} data-testid={`activity-register-button-${activity.activity_id}`}>Registrar</Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>
          );
        })}
      </Accordion>

      <Dialog open={!!active} onOpenChange={(open) => !open && setActive(null)}>
        <DialogContent data-testid="activity-result-dialog">
          <DialogHeader><DialogTitle>{active?.title}</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Resultado</Label>
              <Select value={form.status} onValueChange={(value) => setForm((current) => ({ ...current, status: value }))}>
                <SelectTrigger data-testid="activity-result-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="done"><CheckCircle2 className="mr-1 inline h-3.5 w-3.5 text-emerald-600" />Realizada</SelectItem>
                  <SelectItem value="no_answer"><PhoneMissed className="mr-1 inline h-3.5 w-3.5 text-amber-600" />Sin respuesta</SelectItem>
                  <SelectItem value="rescheduled"><RotateCcw className="mr-1 inline h-3.5 w-3.5 text-sky-600" />Reprogramada</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.status === 'rescheduled' && (
              <div>
                <Label>Nueva fecha</Label>
                <Input type="date" value={form.rescheduled_date} onChange={(event) => setForm((current) => ({ ...current, rescheduled_date: event.target.value }))} data-testid="activity-reschedule-date-input" />
              </div>
            )}
            <div>
              <Label>Observación breve</Label>
              <Textarea value={form.note} onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))} data-testid="activity-note-textarea" />
            </div>
            <div>
              <Label>Próximo paso</Label>
              <Input value={form.next_step} onChange={(event) => setForm((current) => ({ ...current, next_step: event.target.value }))} data-testid="activity-next-step-input" />
            </div>
            {active && BOOK_STAGE.has(active.stage_key) && form.status === 'done' && !active.book_delivery_movement_id && (
              <label className="flex items-center gap-2 text-sm">
                <Checkbox checked={form.deliver_book} onCheckedChange={(checked) => setForm((current) => ({ ...current, deliver_book: !!checked }))} data-testid="activity-deliver-book-checkbox" />
                Entregar {active.stage_key === 'mcd' ? 'Mi Conexión con Dios' : 'Nací Para Triunfar'} ahora (descuenta de mi inventario)
              </label>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActive(null)}>Cancelar</Button>
            <Button onClick={submit} disabled={saving} data-testid="activity-result-save-button">{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Guardar'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
};
