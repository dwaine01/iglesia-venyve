import React from 'react';
import { Badge } from '../ui/badge';

const labels = { planned: 'Planificado', active: 'Activo', paused: 'Pausado', completed: 'Completado', cancelled: 'Cancelado', open: 'Abierto', in_progress: 'En progreso', locked: 'Bloqueado', present: 'Presente', absent: 'Ausente', excused: 'Justificada', pending: 'Pendiente' };
const styles = { active: 'border-emerald-200 bg-emerald-50 text-emerald-800', completed: 'border-blue-200 bg-blue-50 text-blue-800', planned: 'border-slate-200 bg-slate-50 text-slate-700', paused: 'border-amber-200 bg-amber-50 text-amber-800', cancelled: 'border-rose-200 bg-rose-50 text-rose-800', open: 'border-cyan-200 bg-cyan-50 text-cyan-800', in_progress: 'border-amber-200 bg-amber-50 text-amber-800', locked: 'border-slate-200 bg-slate-50 text-slate-500' };

export const ProcessStatus = ({ value, testId }) => <Badge variant="outline" className={styles[value] || 'border-slate-200 bg-white text-slate-700'} data-testid={testId}>{labels[value] || value || 'Sin estado'}</Badge>;

export const SlaPill = ({ dueAt }) => {
  if (!dueAt) return <Badge variant="outline" className="border-slate-200 text-slate-500">Sin vencimiento</Badge>;
  const hours = (new Date(dueAt).getTime() - Date.now()) / 3600000;
  const tone = hours < 0 ? 'border-rose-200 bg-rose-50 text-rose-800' : hours <= 48 ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800';
  const label = hours < 0 ? `Vencida ${Math.ceil(Math.abs(hours) / 24)}d` : hours <= 48 ? `Vence en ${Math.max(1, Math.ceil(hours))}h` : `En SLA · ${Math.ceil(hours / 24)}d`;
  return <Badge variant="outline" className={tone}>{label}</Badge>;
};